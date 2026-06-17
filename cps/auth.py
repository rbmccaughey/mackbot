"""
Uses Playwright to log in and keeps the browser alive for API calls.
All API requests are made via page.evaluate(fetch(...)) so they carry
the browser's natural cookies, auth context, and TLS fingerprint.
"""

import base64
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import sync_playwright, Page
from playwright_stealth import Stealth

from config import SiteConfig, KANANASKIS

_EMAIL_SEL = "input[type='email'], input[name='email'], input[name='Username']"
_PW_SEL = "input[type='password'], input[name='password'], input[name='Password']"

# Real Chrome binary — gives Cloudflare the correct TLS fingerprint (JA3/JA4).
# Playwright's bundled Chromium has a distinct bot fingerprint that Cloudflare detects
# regardless of JS stealth patches.
_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Persistent browser profile so cf_clearance and browser reputation survive across sessions.
_PROFILE_DIR = Path.home() / ".mackbot-chrome-profile"

# sec-ch-ua values matching Chrome 149 / macOS
_SEC_CH_UA = '"Chromium";v="149", "Google Chrome";v="149", "Not-A.Brand";v="99"'

# HTTP-level client hint headers sent with every request
_CH_UA_HEADERS = {
    "sec-ch-ua": _SEC_CH_UA,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

# Stealth patches applied per-page to make JS-visible browser properties consistent
_STEALTH = Stealth(
    navigator_platform_override="MacIntel",
    navigator_languages_override=("en-CA", "en"),
    sec_ch_ua_override=_SEC_CH_UA,
    chrome_runtime=True,
)


@dataclass
class Session:
    access_token: str
    expires_at: float
    golfer_id: int
    acct: str
    site: SiteConfig
    page: Any = field(default=None, repr=False)
    _browser: Any = field(default=None, repr=False)
    _playwright: Any = field(default=None, repr=False)

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60

    def refresh(self, email: str, password: str) -> bool:
        """
        Refreshes the JWT inside the existing browser — never opens a new window.

        Three-stage fallback, all within this browser:
          1. SPA silent refresh — oidc-client may have already updated localStorage
          2. IdentityServer SSO — navigate to verify-email; IS session usually outlasts the JWT
          3. Credential re-entry — fill email+password in this browser if IS session also expired
        """
        base_url = self.site.base_url
        login_url = f"{base_url}/onlineresweb/auth/verify-email"

        def _read_fresh_token() -> bool:
            token_data = _extract_token_from_storage(self.page, base_url)
            if not token_data:
                return False
            new_expires = float(token_data.get("expires_at") or 0)
            if new_expires > time.time() + 60:
                self.access_token = token_data["access_token"]
                self.expires_at = new_expires
                return True
            return False

        try:
            # Stage 1: check if SPA already silently refreshed the token
            if _read_fresh_token():
                print("Token updated from SPA background refresh.")
                return True

            # Stage 2: navigate to verify-email for IdentityServer SSO
            _navigate_to_verify_email(self.page, login_url)
            time.sleep(2)

            # Wait up to 20s: either SSO redirects us back to the app, or the
            # verify-email form appears (meaning IS session also expired)
            for _ in range(20):
                time.sleep(1)
                url = self.page.url
                # SSO worked — redirected back into the app (not on any auth page)
                if "/onlineresweb/" in url and "/auth/" not in url:
                    if _wait_for_token(self.page, base_url, timeout=10_000) and _read_fresh_token():
                        print("Token refreshed via IdentityServer SSO.")
                        return True
                    break
                # We're still on verify-email — email input should be visible
                if "verify-email" in url:
                    try:
                        self.page.wait_for_selector(_EMAIL_SEL, state="visible", timeout=500)
                        break
                    except Exception:
                        pass
                # Redirected to wrong auth page (registration etc.) — go back
                if "/auth/" in url and "verify-email" not in url:
                    _navigate_to_verify_email(self.page, login_url)

            # Stage 3: we're on verify-email and IS session is expired — re-enter credentials.
            # Guard: only proceed if we're actually on verify-email, not a registration page.
            if "verify-email" not in self.page.url:
                print(f"Unexpected page after refresh attempt: {self.page.url}")
                return False

            # Wait up to 60s for email field — covers any slow Cloudflare challenge
            self.page.wait_for_selector(_EMAIL_SEL, state="visible", timeout=60_000)

            print("Re-entering credentials in existing browser...")
            time.sleep(random.uniform(0.8, 1.5))
            self.page.locator(_EMAIL_SEL).first.press_sequentially(email, delay=random.randint(80, 150))
            time.sleep(random.uniform(0.6, 1.2))

            with self.page.expect_response(
                lambda r: "VerifyUser" in r.url and r.request.method == "POST",
                timeout=30_000,
            ):
                _human_click(self.page, "button[type='submit'], input[type='submit']")

            self.page.wait_for_url(f"{base_url}/onlineresweb/auth/login", timeout=15_000)
            self.page.wait_for_selector(_PW_SEL, state="visible", timeout=15_000)
            time.sleep(random.uniform(0.6, 1.2))
            self.page.locator(_PW_SEL).first.press_sequentially(password, delay=random.randint(80, 150))
            time.sleep(random.uniform(0.6, 1.0))

            with self.page.expect_response(
                lambda r: "GetUserInformation" in r.url,
                timeout=45_000,
            ):
                _human_click(self.page, "button[type='submit'], input[type='submit']")

            if _wait_for_token(self.page, base_url) and _read_fresh_token():
                print("Token refreshed via credential re-entry.")
                return True

        except Exception as e:
            print(f"Token refresh error: {e}")

        return False

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass


def _is_cloudflare_challenge(page: Page) -> bool:
    """Return True if the current page appears to be a Cloudflare challenge."""
    # Element-based signals (Cloudflare rotates these IDs occasionally)
    _CF_SELECTORS = (
        "#challenge-running, #cf-challenge-running, #cf-wrapper, "
        "#cf-please-wait, .cf-browser-verification, "
        "iframe[src*='challenges.cloudflare.com']"
    )
    try:
        page.wait_for_selector(_CF_SELECTORS, timeout=2_000)
        return True
    except Exception:
        pass
    # Content-based fallback — catches "Performing security verification" wording
    try:
        body = page.evaluate("document.body.innerText") or ""
        return (
            "security verification" in body.lower()
            or "verifying you are not a bot" in body.lower()
            or "checking your browser" in body.lower()
        )
    except Exception:
        return False


def _handle_cloudflare_challenge(page: Page, timeout_secs: int = 30) -> bool:
    """
    Wait for a Cloudflare challenge to resolve, optionally clicking an interactive checkbox.

    Managed challenges ("Performing security verification") auto-resolve with a real
    browser + stealth — just needs time.  Interactive Turnstile checkbox challenges are
    attempted via frame_locator; image puzzles cannot be automated.

    Returns True once cf_clearance is set or no challenge is detected.
    """
    if not _is_cloudflare_challenge(page):
        return True

    print("Cloudflare challenge detected — waiting for resolution…")

    _CF_IFRAME = "iframe[src*='challenges.cloudflare.com']"

    def _clearance_set() -> bool:
        return any(c["name"] == "cf_clearance" for c in page.context.cookies())

    for _ in range(timeout_secs):
        time.sleep(1)
        if _clearance_set():
            print("Cloudflare challenge resolved.")
            return True

        # Attempt a click on the interactive checkbox if one is visible.
        # bounding_box() on a frame_locator is relative to the iframe viewport,
        # not the page — so we get the iframe element's page-level position for
        # the mouse movement, then let Playwright handle the cross-frame click.
        try:
            frame = page.frame_locator(_CF_IFRAME).first
            checkbox = frame.locator(
                "input[type='checkbox'], .mark, .ctp-checkbox-label, label"
            ).first
            if checkbox.is_visible(timeout=500):
                iframe_box = page.locator(_CF_IFRAME).first.bounding_box()
                if iframe_box:
                    page.mouse.move(random.randint(200, 700), random.randint(100, 400))
                    time.sleep(random.uniform(0.3, 0.6))
                    page.mouse.move(
                        iframe_box["x"] + iframe_box["width"] / 2 + random.uniform(-8, 8),
                        iframe_box["y"] + iframe_box["height"] / 2 + random.uniform(-4, 4),
                    )
                    time.sleep(random.uniform(0.15, 0.3))
                checkbox.click()
                print("Clicked Cloudflare checkbox.")
        except Exception:
            pass

    print("Cloudflare challenge did not resolve automatically — manual intervention may be needed.")
    return _clearance_set()


def _human_click(page: Page, selector: str) -> None:
    """Drift the cursor to a random spot then move to the target before clicking."""
    page.mouse.move(random.randint(300, 900), random.randint(150, 500))
    time.sleep(random.uniform(0.1, 0.25))
    locator = page.locator(selector).first
    box = locator.bounding_box()
    if box:
        x = box["x"] + box["width"] / 2 + random.uniform(-4, 4)
        y = box["y"] + box["height"] / 2 + random.uniform(-2, 2)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.click(x, y)
    else:
        page.click(selector)


def _navigate_to_verify_email(page: Page, login_url: str) -> bool:
    """Navigate to verify-email, retrying if Angular redirects elsewhere or form fails to render."""
    page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
    _handle_cloudflare_challenge(page)
    for _ in range(10):
        time.sleep(1)
        url = page.url
        if "verify-email" in url:
            try:
                page.wait_for_selector(_EMAIL_SEL, state="visible", timeout=5_000)
                return True
            except Exception:
                print("verify-email URL reached but form not visible — reloading...")
                page.reload(wait_until="domcontentloaded", timeout=30_000)
                _handle_cloudflare_challenge(page)
                continue
        if "/onlineresweb/" in url and "/auth/" in url and "verify-email" not in url:
            print(f"Redirected to {url.split('/')[-1]}, re-navigating to verify-email...")
            page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
            _handle_cloudflare_challenge(page)
    return "verify-email" in page.url


def _wait_for_token(page: Page, base_url: str, timeout: int = 15_000) -> bool:
    """Wait for the SPA to write the access token to localStorage."""
    try:
        page.wait_for_function(
            "localStorage.getItem('online-reservation-v5-access_token') !== null",
            timeout=timeout,
        )
        return True
    except Exception:
        pass
    oidc_key = f"oidc.user:{base_url}/identityapi:js1"
    try:
        page.wait_for_function(
            f"localStorage.getItem('{oidc_key}') !== null || sessionStorage.getItem('{oidc_key}') !== null",
            timeout=5_000,
        )
        return True
    except Exception:
        return False


def _extract_token_from_storage(page: Page, base_url: str) -> Optional[dict]:
    access_token = page.evaluate("localStorage.getItem('online-reservation-v5-access_token')")
    if access_token:
        expires_at = page.evaluate("localStorage.getItem('online-reservation-v5-expires_at')")
        return {"access_token": access_token, "expires_at": expires_at}

    oidc_key = f"oidc.user:{base_url}/identityapi:js1"
    raw = page.evaluate(f"localStorage.getItem('{oidc_key}')")
    if raw:
        return json.loads(raw)

    raw = page.evaluate(f"sessionStorage.getItem('{oidc_key}')")
    if raw:
        return json.loads(raw)

    return None


def login(email: str, password: str, site: SiteConfig = KANANASKIS, headless: bool = False) -> "Session":
    """
    Launches a browser, logs in, and returns a Session.
    The browser stays open — all API calls go through page.evaluate(fetch()).
    """
    base_url = site.base_url
    login_url = f"{base_url}/onlineresweb/auth/verify-email"

    _PROFILE_DIR.mkdir(exist_ok=True)
    p = sync_playwright().start()

    launch_kwargs: dict = {
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-CA",
        "timezone_id": "America/Edmonton",
        "extra_http_headers": _CH_UA_HEADERS,
    }
    if os.path.exists(_CHROME_PATH):
        launch_kwargs["executable_path"] = _CHROME_PATH
        print(f"Using system Chrome: {_CHROME_PATH}")
    else:
        print("System Chrome not found — falling back to Playwright Chromium.")

    # launch_persistent_context keeps cf_clearance and browser reputation across restarts.
    # The returned object is a BrowserContext; there is no separate browser handle.
    context = p.chromium.launch_persistent_context(str(_PROFILE_DIR), **launch_kwargs)
    page = context.new_page()
    _STEALTH.apply_stealth_sync(page)

    print("Loading app...")
    search_url = f"{base_url}/onlineresweb/search-teetime?TeeOffTimeMin=0&TeeOffTimeMax=23"
    page.goto(search_url, wait_until="load", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    _handle_cloudflare_challenge(page)
    time.sleep(random.uniform(2.0, 3.5))

    # SPA auth guard will redirect to verify-email if not logged in; if it doesn't, go there directly
    if "verify-email" not in page.url:
        _navigate_to_verify_email(page, login_url)

    page.wait_for_selector(_EMAIL_SEL, state="visible", timeout=30_000)
    time.sleep(random.uniform(1.0, 2.5))
    page.locator(_EMAIL_SEL).first.press_sequentially(email, delay=random.randint(80, 150))
    time.sleep(random.uniform(0.8, 1.5))

    with page.expect_response(
        lambda r: "VerifyUser" in r.url and r.request.method == "POST",
        timeout=30_000,
    ):
        _human_click(page, "button[type='submit'], input[type='submit']")

    # SPA routes to /auth/login after VerifyUser succeeds
    page.wait_for_url(f"{base_url}/onlineresweb/auth/login", timeout=15_000)
    page.wait_for_selector(_PW_SEL, state="visible", timeout=15_000)
    time.sleep(random.uniform(1.0, 2.0))
    page.locator(_PW_SEL).first.press_sequentially(password, delay=random.randint(80, 150))
    time.sleep(random.uniform(0.8, 1.5))

    # Submit password — wait for GetUserInformation as the true "logged in" signal
    with page.expect_response(
        lambda r: "GetUserInformation" in r.url,
        timeout=45_000,
    ):
        _human_click(page, "button[type='submit'], input[type='submit']")

    _wait_for_token(page, base_url)
    token_data = _extract_token_from_storage(page, base_url)

    if not token_data:
        all_keys = page.evaluate("Object.keys(localStorage)")
        raise RuntimeError(f"Could not extract JWT. localStorage keys: {all_keys}")

    access_token = token_data["access_token"]
    expires_at = token_data.get("expires_at") or (time.time() + 3600)

    claims = {}
    id_token_raw = page.evaluate("localStorage.getItem('online-reservation-v5-id_token_claims_obj')")
    if id_token_raw:
        try:
            claims = json.loads(id_token_raw)
        except Exception:
            pass
    if not claims.get("golferId"):
        try:
            payload_b64 = access_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            pass

    golfer_id = int(claims.get("golferId", 0))
    acct = claims.get("acct", "")
    print(f"Logged in as {claims.get('name')} (golferId={golfer_id}, acct={acct})")

    return Session(
        access_token=access_token,
        expires_at=float(expires_at),
        golfer_id=golfer_id,
        acct=acct,
        site=site,
        page=page,
        _browser=context,
        _playwright=p,
    )

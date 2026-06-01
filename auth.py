"""
Uses Playwright to log in and keeps the browser alive for API calls.
All API requests are made via page.evaluate(fetch(...)) so they carry
the browser's natural cookies, auth context, and TLS fingerprint.
"""

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import sync_playwright, Page

from config import SiteConfig, KANANASKIS


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
        email_sel = "input[type='email'], input[name='email'], input[name='Username']"
        pw_sel = "input[type='password'], input[name='password'], input[name='Password']"

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

        def _navigate_to_verify_email():
            """Navigate to verify-email and wait for the URL to settle there."""
            self.page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
            # Wait for Angular router to settle — if it redirects away, bring it back.
            for _ in range(10):
                time.sleep(1)
                url = self.page.url
                if "verify-email" in url:
                    return True
                # Redirected somewhere unexpected (e.g. registration page) — try again
                if "/onlineresweb/" in url and "/auth/" in url and "verify-email" not in url:
                    print(f"Redirected to {url.split('/')[-1]}, re-navigating to verify-email...")
                    self.page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
            return "verify-email" in self.page.url

        try:
            # Stage 1: check if SPA already silently refreshed the token
            if _read_fresh_token():
                print("Token updated from SPA background refresh.")
                return True

            # Stage 2: navigate to verify-email for IdentityServer SSO
            _navigate_to_verify_email()
            time.sleep(2)

            # Wait up to 20s: either SSO redirects us back to the app, or the
            # verify-email form appears (meaning IS session also expired)
            for _ in range(20):
                time.sleep(1)
                url = self.page.url
                # SSO worked — redirected back into the app (not on any auth page)
                if "/onlineresweb/" in url and "/auth/" not in url:
                    time.sleep(3)  # wait for SPA to finish writing new token to localStorage
                    if _read_fresh_token():
                        print("Token refreshed via IdentityServer SSO.")
                        return True
                    break
                # We're still on verify-email — email input should be visible
                if "verify-email" in url:
                    try:
                        self.page.wait_for_selector(email_sel, state="visible", timeout=500)
                        break
                    except Exception:
                        pass
                # Redirected to wrong auth page (registration etc.) — go back
                if "/auth/" in url and "verify-email" not in url:
                    _navigate_to_verify_email()

            # Stage 3: we're on verify-email and IS session is expired — re-enter credentials.
            # Guard: only proceed if we're actually on verify-email, not a registration page.
            if "verify-email" not in self.page.url:
                print(f"Unexpected page after refresh attempt: {self.page.url}")
                return False

            # Wait up to 60s for email field — covers any slow Cloudflare challenge
            self.page.wait_for_selector(email_sel, state="visible", timeout=60_000)

            print("Re-entering credentials in existing browser...")
            time.sleep(random.uniform(0.8, 1.5))
            self.page.fill(email_sel, email)
            time.sleep(random.uniform(0.6, 1.2))
            self.page.click("button[type='submit'], input[type='submit']")
            try:
                self.page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(random.uniform(1.2, 2.0))

            self.page.wait_for_selector(pw_sel, state="visible", timeout=15_000)
            time.sleep(random.uniform(0.6, 1.2))
            self.page.fill(pw_sel, password)
            time.sleep(random.uniform(0.6, 1.0))
            self.page.click("button[type='submit'], input[type='submit']")
            self.page.wait_for_url(f"{base_url}/onlineresweb/**", timeout=45_000)

            for _ in range(30):
                if _read_fresh_token():
                    print("Token refreshed via credential re-entry.")
                    return True
                time.sleep(1)

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


def _extract_token_from_storage(page: Page, base_url: str) -> dict | None:
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

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        )
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = context.new_page()

    print("Clearing Cloudflare...")
    page.goto(base_url, wait_until="load", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    time.sleep(random.uniform(2.0, 3.5))

    print("Opening login page...")
    page.goto(login_url, wait_until="load", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    time.sleep(random.uniform(1.5, 2.5))

    page.wait_for_selector("input[type='email'], input[name='email'], input[name='Username']", state="visible", timeout=20_000)
    time.sleep(random.uniform(1.0, 2.5))
    page.fill("input[type='email'], input[name='email'], input[name='Username']", email)
    time.sleep(random.uniform(0.8, 1.5))
    page.click("button[type='submit'], input[type='submit']")

    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    time.sleep(random.uniform(1.5, 2.5))

    page.wait_for_selector("input[type='password'], input[name='password'], input[name='Password']", state="visible", timeout=20_000)
    time.sleep(random.uniform(1.0, 2.0))
    page.fill("input[type='password'], input[name='password'], input[name='Password']", password)
    time.sleep(random.uniform(0.8, 1.5))
    page.click("button[type='submit'], input[type='submit']")

    page.wait_for_url(f"{base_url}/onlineresweb/**", timeout=45_000)

    token_data = None
    for _ in range(30):
        token_data = _extract_token_from_storage(page, base_url)
        if token_data:
            break
        time.sleep(1)

    if not token_data:
        all_keys = page.evaluate("Object.keys(localStorage)")
        raise RuntimeError(f"Could not extract JWT. localStorage keys: {all_keys}")

    access_token = token_data["access_token"]
    expires_at = token_data.get("expires_at") or (time.time() + 3600)

    import base64
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
        _browser=browser,
        _playwright=p,
    )

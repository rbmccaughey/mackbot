"""
Uses Playwright to log in and extract the JWT + Cloudflare cookies.
The JWT (client_id=js1) lasts 1 hour. Cookies are reused for httpx polling.
"""

import json
import time
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, Page

from config import BASE_URL

OIDC_STORAGE_KEY = f"oidc.user:{BASE_URL}/identityapi:js1"
LOGIN_URL = f"{BASE_URL}/onlineresweb/auth/login"


@dataclass
class Session:
    access_token: str
    expires_at: float
    cookies: dict[str, str]
    golfer_id: int
    acct: str

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60


def _extract_token_from_storage(page: Page) -> dict | None:
    raw = page.evaluate(f"localStorage.getItem('{OIDC_STORAGE_KEY}')")
    if raw:
        return json.loads(raw)

    # Some IdentityServer clients use sessionStorage
    raw = page.evaluate(f"sessionStorage.getItem('{OIDC_STORAGE_KEY}')")
    if raw:
        return json.loads(raw)

    # Fall back: scan all localStorage keys for access_token
    all_keys = page.evaluate("Object.keys(localStorage)")
    for key in all_keys:
        val = page.evaluate(f"localStorage.getItem('{key}')")
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict) and "access_token" in parsed:
                return parsed
        except Exception:
            pass

    return None


def login(email: str, password: str, headless: bool = False) -> Session:
    """
    Launches a browser, logs in, and returns a Session with the JWT and cookies.
    headless=False so Cloudflare challenge can be solved (shows browser window).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print("Opening login page...")
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=60_000)

        # Fill login form — field selectors may need tweaking if the site changes
        page.fill("input[type='email'], input[name='email'], input[name='Username']", email)
        page.fill("input[type='password'], input[name='password'], input[name='Password']", password)
        page.click("button[type='submit'], input[type='submit']")

        # Wait for redirect back to the SPA after successful login
        page.wait_for_url(f"{BASE_URL}/onlineresweb/**", timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=15_000)

        token_data = _extract_token_from_storage(page)
        if not token_data:
            raise RuntimeError(
                "Could not extract JWT from localStorage after login. "
                "Check that login succeeded and that the OIDC key is correct."
            )

        access_token = token_data["access_token"]
        expires_at = token_data.get("expires_at") or (time.time() + 3600)

        raw_cookies = context.cookies()
        cookies = {c["name"]: c["value"] for c in raw_cookies}

        # Pull golfer details from token claims
        import base64
        payload_b64 = access_token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))

        golfer_id = int(claims.get("golferId", 0))
        acct = claims.get("acct", "")

        browser.close()

        print(f"Logged in as {claims.get('name')} (golferId={golfer_id})")
        return Session(
            access_token=access_token,
            expires_at=float(expires_at),
            cookies=cookies,
            golfer_id=golfer_id,
            acct=acct,
        )

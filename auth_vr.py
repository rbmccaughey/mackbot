"""
Valley Ridge Golf (TotalClub Unity) authentication.

Session is cookie-based (PHPSESSID). The Playwright browser stays open so
booking calls can run inside it via page.evaluate(fetch()), carrying session
cookies automatically.
"""

import json
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import sync_playwright

BASE_URL = "https://valleyridgegolf.teetimes.totalclubunity.com"
_EMAIL_SEL = "input[type='email'], input[name='email'], input[name='data[User][email]']"
_PW_SEL = "input[type='password'], input[name='password'], input[name='data[User][password]']"


@dataclass
class VRSession:
    user_id: int
    page: Any = field(default=None, repr=False)
    _browser: Any = field(default=None, repr=False)
    _playwright: Any = field(default=None, repr=False)

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass


def login_vr(email: str, password: str, headless: bool = False) -> VRSession:
    """
    Launches a browser, logs into Valley Ridge, returns a VRSession.
    Browser stays open — booking calls go through page.evaluate(fetch()).
    """
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
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-CA",
        timezone_id="America/Edmonton",
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    page = context.new_page()

    print("Loading Valley Ridge site...")
    page.goto(f"{BASE_URL}/booking", wait_until="domcontentloaded", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass
    time.sleep(2)

    print("Navigating to login...")
    page.goto(f"{BASE_URL}/users/login", wait_until="domcontentloaded", timeout=30_000)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    time.sleep(1)

    page.wait_for_selector(_EMAIL_SEL, state="visible", timeout=20_000)
    time.sleep(0.5)
    page.locator(_EMAIL_SEL).first.fill(email)
    time.sleep(0.4)
    page.locator(_PW_SEL).first.fill(password)
    time.sleep(0.4)
    page.click("button[type='submit'], input[type='submit']")

    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)
    time.sleep(1)

    user_id = _extract_user_id(page)
    if not user_id:
        raise RuntimeError(
            "Login failed — could not extract user ID from rmbme cookie. "
            "Check VR_GOLF_EMAIL / VR_GOLF_PASSWORD."
        )

    print(f"Logged into Valley Ridge as user_id={user_id}")
    return VRSession(user_id=user_id, page=page, _browser=browser, _playwright=p)


def _extract_user_id(page: Any) -> int:
    cookies = page.context.cookies()
    for cookie in cookies:
        if cookie["name"] == "rmbme":
            try:
                val = json.loads(urllib.parse.unquote(cookie["value"]))
                return int(val.get("uk", 0))
            except Exception:
                pass
    return 0

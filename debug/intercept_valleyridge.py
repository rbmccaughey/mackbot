"""
HAR capture for Valley Ridge Golf (valleyridgegolf.teetimes.totalclubunity.com).

Opens a browser, attempts auto-login, then waits for you to browse to a tee time
and complete a booking all the way through the final confirmation. Press Ctrl+C
when done — all POST requests and /booking/ API calls are printed with full
request/response bodies.

Usage:
    python debug_intercept_valleyridge.py

Credentials (add to .env or export before running):
    VR_GOLF_EMAIL=...
    VR_GOLF_PASSWORD=...
"""

import json
import os
import time

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://valleyridgegolf.teetimes.totalclubunity.com"
LOGIN_URL = f"{BASE_URL}/users/login"
BOOKING_URL = f"{BASE_URL}/booking"
HAR_PATH = "/tmp/vr_booking_capture.har"

p = sync_playwright().start()
browser = p.chromium.launch(
    headless=False,
    args=["--disable-blink-features=AutomationControlled"],
)
context = browser.new_context(
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    record_har_path=HAR_PATH,
    record_har_content="attach",
)
context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
page = context.new_page()

email = os.environ.get("VR_GOLF_EMAIL", "")
password = os.environ.get("VR_GOLF_PASSWORD", "")

print("Loading site...")
page.goto(BOOKING_URL, wait_until="domcontentloaded", timeout=60_000)
try:
    page.wait_for_load_state("networkidle", timeout=15_000)
except Exception:
    pass
time.sleep(2)

if email and password:
    print("Auto-login: navigating to login page...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    time.sleep(1)

    try:
        email_sel = "input[type='email'], input[name='email'], input[name='data[User][email]']"
        pw_sel = "input[type='password'], input[name='password'], input[name='data[User][password]']"
        page.wait_for_selector(email_sel, state="visible", timeout=10_000)
        page.fill(email_sel, email)
        time.sleep(0.5)
        page.fill(pw_sel, password)
        time.sleep(0.5)
        page.click("button[type='submit'], input[type='submit']")
        page.wait_for_url(f"{BASE_URL}/**", timeout=20_000)
        time.sleep(1)
        if "/login" not in page.url:
            print(f"Logged in. Current page: {page.url}")
        else:
            print("Auto-login may have failed — check credentials or log in manually.")
    except Exception as e:
        print(f"Auto-login error ({e}) — please log in manually in the browser.")
else:
    print("No VR_GOLF_EMAIL / VR_GOLF_PASSWORD in .env — please log in manually in the browser.")

print()
print("=" * 60)
print("1. Browse to the booking page and pick a tee time.")
print("2. Go all the way through to the final confirmation.")
print("3. Press Ctrl+C when the booking is complete (or fails).")
print("=" * 60)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

print("\nSaving HAR and parsing results...")
try:
    context.close()
except Exception:
    pass
try:
    browser.close()
except Exception:
    pass
try:
    p.stop()
except Exception:
    pass

with open(HAR_PATH) as f:
    har = json.load(f)

entries = har.get("log", {}).get("entries", [])

# Capture everything that could be part of the booking flow:
#   - All POST requests to the site
#   - All /booking/ and /users/ calls (GET or POST)
site_entries = [
    e for e in entries
    if BASE_URL in e["request"]["url"]
    and not any(skip in e["request"]["url"] for skip in [
        "/scripts/", "/css/", "/img/", "/favicon", "/fonts/",
        "digitaloceanspaces", "cloudflare", "jquery", "bootstrap",
    ])
]

print(f"\nFound {len(site_entries)} site requests (excluding static assets):\n")
for e in site_entries:
    req = e["request"]
    resp = e["response"]
    url = req["url"].replace(BASE_URL, "")
    method = req["method"]
    status = resp["status"]
    content = resp.get("content", {})
    mime = content.get("mimeType", "")

    # Always show POSTs; show GETs only for /booking/ and /users/ paths
    is_post = method == "POST"
    is_api = "/booking/" in url or "/users/" in url
    if not (is_post or is_api):
        continue

    print(f"\n{'='*60}")
    print(f"  {method} {status}  {url}")

    # Request cookies (session cookie name)
    cookies = {c["name"]: c["value"][:20] + "..." for c in req.get("cookies", [])}
    if cookies:
        print(f"  COOKIES: {list(cookies.keys())}")

    # Request body
    post_data = req.get("postData", {})
    req_body = post_data.get("text", "")
    req_mime = post_data.get("mimeType", "")
    if req_body:
        print(f"  REQUEST ({req_mime}):")
        if "json" in req_mime:
            try:
                print("   ", json.dumps(json.loads(req_body), indent=2))
            except Exception:
                print("   ", req_body[:800])
        else:
            # Form-encoded or raw — print as-is (may contain CSRF token etc.)
            print("   ", req_body[:800])

    # Response
    resp_body = content.get("text", "")
    if resp_body:
        print(f"  RESPONSE ({mime}):")
        if "json" in mime:
            try:
                parsed = json.loads(resp_body)
                print("   ", json.dumps(parsed, indent=2)[:2000])
            except Exception:
                print("   ", resp_body[:800])
        elif "html" in mime:
            # Just show first 300 chars for HTML (probably an error/redirect page)
            print("   ", resp_body[:300])
        else:
            print("   ", resp_body[:400])
    else:
        print("  RESPONSE: (no body captured)")

print(f"\nFull HAR saved to: {HAR_PATH}")

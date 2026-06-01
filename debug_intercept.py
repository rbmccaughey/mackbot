"""
Opens a browser with full HAR recording enabled, lets you manually log in and
complete a tee time booking, then dumps all booking API calls (request + response
bodies) when you press Ctrl+C.

Usage:
    python debug_intercept.py
"""

import json
import os
import random
import time

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

HAR_PATH = "/tmp/booking_capture.har"

BOOKING_ENDPOINTS = {
    "RegisterTransactionId",
    "LockTeeTimes",
    "TeeTimePricesCalculation",
    "CheckRestrictReservation",
    "CheckBookingLimit",
    "GetAllCreditCardOnFile",
    "ReserveTeeTimes",
    "TeeTime",
}

BASE_URL = "https://kananaskisabresidents.cps.golf"
LOGIN_URL = f"{BASE_URL}/onlineresweb/auth/verify-email"

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

email = os.environ.get("GOLF_EMAIL", "")
password = os.environ.get("GOLF_PASSWORD", "")

print("Clearing Cloudflare...")
page.goto(BASE_URL, wait_until="load", timeout=60_000)
try:
    page.wait_for_load_state("networkidle", timeout=20_000)
except Exception:
    pass
time.sleep(random.uniform(2.0, 3.5))

if email and password:
    print("Logging in automatically...")
    page.goto(LOGIN_URL, wait_until="load", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    time.sleep(random.uniform(1.5, 2.5))

    page.wait_for_selector("input[type='email'], input[name='email'], input[name='Username']", state="visible", timeout=20_000)
    time.sleep(random.uniform(1.0, 2.0))
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
    page.wait_for_url(f"{BASE_URL}/onlineresweb/**", timeout=45_000)
    print("Logged in.\n")
else:
    print("No credentials found — please log in manually in the browser.\n")

print("=" * 60)
print("Now manually search for and book a tee time.")
print("Go all the way through to the final confirmation.")
print("Press Ctrl+C when the booking is complete (or fails).")
print("=" * 60)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

print("\nSaving HAR and parsing results...")
context.close()
browser.close()
p.stop()

# Parse and display the relevant entries
with open(HAR_PATH) as f:
    har = json.load(f)

entries = har.get("log", {}).get("entries", [])
booking_entries = [
    e for e in entries
    if any(ep in e["request"]["url"] for ep in BOOKING_ENDPOINTS)
]

if not booking_entries:
    print("No booking API calls found in HAR. Did you complete a booking?")
else:
    print(f"\nFound {len(booking_entries)} booking API calls:\n")
    for e in booking_entries:
        req = e["request"]
        resp = e["response"]
        url = req["url"]
        name = next((ep for ep in BOOKING_ENDPOINTS if ep in url), url.split("/")[-1])

        print(f"\n{'='*60}")
        print(f"  {req['method']} {name}")

        # Request body
        req_body = req.get("postData", {}).get("text", "")
        if req_body:
            try:
                print(f"  REQUEST:  {json.dumps(json.loads(req_body), indent=2)}")
            except Exception:
                print(f"  REQUEST:  {req_body[:500]}")

        # Response
        print(f"  STATUS:   {resp['status']}")
        resp_body = ""
        content = resp.get("content", {})
        if content.get("text"):
            resp_body = content["text"]
        if resp_body:
            try:
                print(f"  RESPONSE: {json.dumps(json.loads(resp_body), indent=2)}")
            except Exception:
                print(f"  RESPONSE: {resp_body[:500]}")
        else:
            print("  RESPONSE: (empty)")

print(f"\nFull HAR saved to: {HAR_PATH}")

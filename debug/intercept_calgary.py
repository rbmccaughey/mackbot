"""
HAR capture for City of Calgary Golf (cityofcalgarygolf.cps.golf).
Opens a browser, logs in, lands on the tee time search page, then lets you
manually search and complete a booking. Press Ctrl+C when done (or failed) —
all booking API calls (request + response bodies) are printed and saved.

Usage:
    python debug_intercept_calgary.py

Credentials (add to .env or export before running):
    CALGARY_GOLF_EMAIL=...
    CALGARY_GOLF_PASSWORD=...
"""

import json
import os
import random
import time

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://cityofcalgarygolf.cps.golf"
LOGIN_URL = f"{BASE_URL}/onlineresweb/auth/verify-email"
SEARCH_URL = f"{BASE_URL}/onlineresweb/search-teetime?TeeOffTimeMin=0&TeeOffTimeMax=23.999722222222225"
HAR_PATH = "/tmp/calgary_booking_capture.har"

BOOKING_ENDPOINTS = {
    "RegisterTransactionId",
    "LockTeeTimes",
    "TeeTimePricesCalculation",
    "CheckRestrictReservation",
    "CheckBookingLimit",
    "GetAllCreditCardOnFile",
    "ReserveTeeTimes",
    "TeeTime",
    "TeeTimes",
}

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

email = os.environ.get("CALGARY_GOLF_EMAIL", "")
password = os.environ.get("CALGARY_GOLF_PASSWORD", "")

print("Clearing Cloudflare / loading site...")
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
    print("Logged in.")
else:
    print("No CALGARY_GOLF_EMAIL / CALGARY_GOLF_PASSWORD in .env — please log in manually.\n")

print(f"\nNavigating to tee time search...")
page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30_000)

print("\n" + "=" * 60)
print("Search for a tee time and go all the way through to")
print("the final confirmation screen (no payment needed).")
print("Press Ctrl+C when the booking is complete (or fails).")
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
        print(f"  URL: {url}")

        # Request headers (extract the interesting ones)
        hdrs = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
        for key in ("x-websiteid", "x-siteid", "x-componentid", "x-moduleid", "client-id"):
            if key in hdrs:
                print(f"  HDR {key}: {hdrs[key]}")

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

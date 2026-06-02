"""
Valley Ridge Golf (TotalClub Unity) API client.

Tee time search is public (no auth needed). Booking calls run inside the
Playwright browser via page.evaluate(fetch()) so session cookies are included.
"""

import json
import time
import urllib.parse
from datetime import date, datetime

import httpx

from courses.valley_ridge.auth import VRSession

BASE_URL = "https://valleyridgegolf.teetimes.totalclubunity.com"
_XHR_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


# ---------------------------------------------------------------------------
# Public (no auth)
# ---------------------------------------------------------------------------

def search_tee_times_vr(
    target_date: date,
    num_players: int,
    time_min: float,
    time_max: float,
) -> list[dict]:
    """
    Fetch available 18-hole tee times for target_date. Public endpoint.
    Returns slots where available_spots >= num_players and time is in window.
    """
    date_str = f"{target_date.strftime('%A, %b')} {target_date.day} {target_date.year}"
    params = urllib.parse.urlencode({
        "date": date_str,
        "holes": "any",
        "players": "any",
        "time_of_day": "any",
    })
    resp = httpx.get(
        f"{BASE_URL}/booking/teetimes/?{params}",
        headers=_XHR_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    slots = resp.json().get("teetimes", [])

    matches = []
    for slot in slots:
        dt = datetime.fromisoformat(slot["teedatetime"])
        hour = dt.hour + dt.minute / 60
        if hour < time_min or hour >= time_max:
            continue
        if slot.get("available_spots", 0) < num_players:
            continue
        if not slot.get("available_18", False):
            continue
        matches.append(slot)

    return matches


def check_holds_vr(teetime_id: int) -> dict:
    """Check if a tee time slot is still available to book."""
    resp = httpx.get(
        f"{BASE_URL}/booking/checkholds/{teetime_id}/",
        headers=_XHR_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Authenticated (requires VRSession)
# ---------------------------------------------------------------------------

def _browser_fetch(session: VRSession, url: str) -> dict:  # pragma: no cover
    """GET via the Playwright browser so session cookies are included."""
    result = session.page.evaluate(
        """async (url) => {
            const resp = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                credentials: 'include',
            });
            return {status: resp.status, body: await resp.text()};
        }""",
        url,
    )
    if result["status"] >= 400:
        raise Exception(f"GET {url.split('/')[-2]} → {result['status']}: {result['body'][:200]}")
    return json.loads(result["body"])


def get_teetime_details_vr(session: VRSession, teetime_id: int) -> tuple[dict, str]:  # pragma: no cover
    """
    Fetch user-specific tee time details (authenticated).
    Returns (parsed_dict, raw_json_string).
    """
    url = f"{BASE_URL}/booking/teetimedetails/{session.user_id}/{teetime_id}//false"
    result = session.page.evaluate(
        """async (url) => {
            const resp = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                credentials: 'include',
            });
            return {status: resp.status, body: await resp.text()};
        }""",
        url,
    )
    if result["status"] >= 400:
        raise Exception(f"teetimedetails → {result['status']}: {result['body'][:200]}")
    raw = result["body"]
    return json.loads(raw), raw


def find_booking_option(details: dict, raw: str) -> tuple[int, int, int]:
    """
    Extract (booking_option_id, payment_type_id, parent_id) from teetimedetails.

    Selection order:
      1. VR_PAYMENT_TYPE_ID env var — pin the payment type explicitly.
      2. User's payment_type_id found in the 'user' section of the response.
      3. Fallback: lowest-price option (may pick wrong one if multiple are $0).

    Returns (booking_option_id, payment_type_id, parent_id).
    """
    import os
    print(f"teetimedetails top-level keys: {list(details.keys())}")
    print(f"teetimedetails raw (first 1000 chars):\n{raw[:1000]}\n")

    # --- Collect all booking-option-shaped dicts ---
    candidates: list[dict] = []

    def _collect(obj):
        if isinstance(obj, dict):
            if "payment_type_id" in obj and "id" in obj and "parent_id" in obj:
                candidates.append(obj)
            for v in obj.values():
                _collect(v)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(details)

    if not candidates:
        raise RuntimeError(
            f"No booking options found in teetimedetails. Keys: {list(details.keys())}"
        )

    print(f"Found {len(candidates)} booking option candidates:")
    for c in candidates:
        print(f"  id={c.get('id')} payment_type_id={c.get('payment_type_id')} "
              f"parent_id={c.get('parent_id')} price={c.get('price_total')}")

    # --- Try VR_PAYMENT_TYPE_ID env var override first ---
    env_pt = os.environ.get("VR_PAYMENT_TYPE_ID", "").strip()
    if env_pt:
        target_pt = int(env_pt)
        pinned = [c for c in candidates if c.get("payment_type_id") == target_pt]
        if pinned:
            best = pinned[0]
            print(f"Selected (VR_PAYMENT_TYPE_ID={target_pt}): id={best['id']} "
                  f"payment_type_id={best['payment_type_id']} parent_id={best.get('parent_id')}")
            return int(best["id"]), int(best["payment_type_id"]), int(best.get("parent_id", 0))
        print(f"WARNING: VR_PAYMENT_TYPE_ID={target_pt} not found in candidates; falling through")

    # --- Try to find payment_type_id in the user object ---
    user_pt = _find_user_payment_type(details)
    if user_pt:
        matched = [c for c in candidates if c.get("payment_type_id") == user_pt]
        if matched:
            best = matched[0]
            print(f"Selected (user payment_type={user_pt}): id={best['id']} "
                  f"payment_type_id={best['payment_type_id']} parent_id={best.get('parent_id')}")
            return int(best["id"]), int(best["payment_type_id"]), int(best.get("parent_id", 0))

    # --- Fallback: lowest price ---
    def _price(opt) -> float:
        try:
            return float(opt.get("price_total", "9999"))
        except (TypeError, ValueError):
            return 9999.0

    best = min(candidates, key=_price)
    print(f"Selected (lowest price fallback): id={best['id']} "
          f"payment_type_id={best['payment_type_id']} parent_id={best.get('parent_id')} "
          f"price={best.get('price_total')}")
    print("TIP: if this is wrong, set VR_PAYMENT_TYPE_ID=<correct payment_type_id> in .env")
    return int(best["id"]), int(best["payment_type_id"]), int(best.get("parent_id", 0))


def _find_user_payment_type(details: dict) -> int | None:
    """
    Look for the user's payment_type_id in the teetimedetails response.
    Checks common field paths used by TotalClub Unity.
    """
    for path in (
        ("user", "payment_type_id"),
        ("user", "payment_type", "id"),
        ("user", "paymentTypeId"),
        ("member", "payment_type_id"),
        ("member", "payment_type", "id"),
        ("payment_type_id",),
        ("payment_type", "id"),
    ):
        obj = details
        for key in path:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                obj = None
                break
        if isinstance(obj, int):
            print(f"Found user payment_type_id={obj} at path {'.'.join(path)}")
            return obj
    return None


def book_teetime_vr(  # pragma: no cover
    session: VRSession,
    teetime_id: int,
    booking_option_id: int,
    payment_type_id: int,
    parent_id: int,
    num_players: int,
) -> dict:
    """
    Submit the booking form via browser fetch().

    1. Navigate to the booking details GET page — sets the correct Referer and
       allows CSRF token extraction from the DOM.
    2. Extract _csrfToken from the page's hidden input.
    3. POST the booking form to complete the reservation.
    """
    details_url = (
        f"{BASE_URL}/booking/details/{teetime_id}/{booking_option_id}/any/"
        f"?groups={num_players}"
    )
    print(f"Navigating to booking details page: {details_url}")
    session.page.goto(details_url, wait_until="domcontentloaded", timeout=30_000)
    try:
        session.page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    time.sleep(2)

    # Extract CSRF token — try hidden input first, then JS global
    csrf_token = session.page.evaluate(
        "document.querySelector('input[name=\"_csrfToken\"]')?.value"
        " || window._csrfToken || ''"
    )
    if not csrf_token:
        raise Exception("Could not extract _csrfToken from booking details page")
    print(f"Got _csrfToken ({len(csrf_token)} chars)")

    # Build booking_option_details array — one entry per player
    booking_option = {
        "id": booking_option_id,
        "parent_id": parent_id,
        "payment_type_id": payment_type_id,
    }
    booking_option_details = []
    for i in range(num_players):
        booking_option_details.append({
            "user_id": session.user_id if i == 0 else 0,
            "guest_name": "" if i == 0 else f"Guest {i}",
            "guest_info": {},
            "booking_option": booking_option,
        })

    # Build form-encoded body (PHP array notation for booking-users[])
    form_pairs = [
        ("_csrfToken", csrf_token),
        ("addons", "[]"),
        ("booking_option_details", json.dumps(booking_option_details)),
        ("carts", "0"),
        ("booking_holes", "18"),
        ("guests-name", ""),
        ("booking-comment", ""),
    ]
    form_pairs.append(("booking-users[]", str(session.user_id)))
    for _ in range(num_players - 1):
        form_pairs.append(("booking-users[]", "0"))

    form_body = urllib.parse.urlencode(form_pairs)
    post_url = f"{BASE_URL}/booking/details/{teetime_id}/{booking_option_id}/{payment_type_id}"

    print(f"POSTing booking to {post_url}")
    result = session.page.evaluate(
        """async (args) => {
            const resp = await fetch(args.url, {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: args.body,
                credentials: 'include',
            });
            return {status: resp.status, url: resp.url, body: await resp.text()};
        }""",
        {"url": post_url, "body": form_body},
    )
    print(f"Booking POST → status={result['status']} final_url={result['url']}")
    return result

"""
Valley Ridge Golf (TotalClub Unity) booking chain:

  1. check_holds   — verify slot is still available
  2. login_vr      — open browser, log in (auth only needed when booking)
  3. teetimedetails — get user's booking option (id, payment_type_id, parent_id)
  4. book_teetime  — navigate to booking page, extract CSRF, POST form
  5. Confirm redirect to /booking/receipt/
"""

from datetime import datetime

from courses.valley_ridge.api import (
    check_holds_vr,
    get_teetime_details_vr,
    find_booking_option,
    book_teetime_vr,
)
from courses.valley_ridge.auth import VRSession

BASE_URL = "https://valleyridgegolf.teetimes.totalclubunity.com"


def slot_summary_vr(slot: dict) -> str:
    dt = datetime.fromisoformat(slot["teedatetime"])
    spots = slot.get("available_spots", "?")
    return f"Valley Ridge  {dt.strftime('%I:%M %p')}  ({spots} spots)"


def book_slot_vr(session: VRSession, slot: dict, num_players: int) -> tuple[bool, str]:
    teetime_id = slot["id"]
    summary = slot_summary_vr(slot)
    print(f"\nAttempting to book: {summary}")

    # Step 1: Verify still available
    try:
        holds = check_holds_vr(teetime_id)
        success_msg = holds.get("success", "")
        if "available" not in success_msg.lower():
            return False, f"Slot no longer available: {success_msg}"
        if holds.get("hold"):
            return False, f"Slot is held: {holds['hold']}"
    except Exception as e:
        return False, f"checkholds error: {e}"

    # Step 2: Get user-specific booking option
    try:
        details, raw = get_teetime_details_vr(session, teetime_id)
        booking_option_id, payment_type_id, parent_id = find_booking_option(details, raw)
    except Exception as e:
        return False, f"teetimedetails error: {e}"

    # Step 3: Navigate to booking page, submit form
    try:
        result = book_teetime_vr(
            session, teetime_id, booking_option_id, payment_type_id, parent_id, num_players
        )
    except Exception as e:
        return False, f"Booking error: {e}"

    final_url = result.get("url", "")
    status = result.get("status", 0)

    if "/booking/receipt/" in final_url:
        return True, f"Booked: {summary}"

    # Check body for error messages
    body = result.get("body", "")
    if status >= 400:
        return False, f"Booking POST returned {status}: {body[:200]}"

    return False, f"Unexpected final URL after booking: {final_url} (status {status})"

"""
Full booking chain:
  1. CheckBookingLimit          — fast-fail if booking cap is hit
  2. LockTeeTimes               — lock slot (called before navigating, matching real browser flow)
  3. page.goto(checkout_url)    — park browser on checkout page for correct Referer
  4. TeeTimePricesCalculation   — server creates pricing session, returns bookingTransactionId
  5. CheckRestrictReservation   — restriction check
  6. GetAllCreditCardOnFile     — fetch Moneris card-on-file token (Kananaskis only)
  7. RegisterTransactionId      — register a fresh UUID as the booking transactionId
  8. ReserveTeeTimes            — final confirmation; card charged server-side (if payment required)

Key UUID mapping (counterintuitive field names):
  ReserveTeeTimes.transactionId        = fresh UUID from RegisterTransactionId
  ReserveTeeTimes.bookingTransactionId = UUID returned by TeeTimePricesCalculation
"""

import time

from cps.api import (
    check_booking_limit, lock_tee_time, reserve_tee_times,
    get_tee_time_detail, tee_time_prices_calculation, check_restrict_reservation,
    register_transaction_id, get_credit_cards_on_file,
)
from cps.auth import Session
from cps.scanner import slot_summary


def book_slot(session: Session, slot: dict, num_players: int, email: str) -> tuple[bool, str]:
    tee_sheet_id = slot["teeSheetId"]
    course_id = slot.get("courseId", 0)
    summary = slot_summary(slot)

    print(f"\nAttempting to book: {summary}")

    # Step 1: fast-fail booking limit check
    try:
        limit_resp = check_booking_limit(session, tee_sheet_id)
        if not limit_resp.get("isSuccess", True):
            return False, f"Booking limit check failed: {limit_resp}"
    except Exception:
        pass

    # Step 2: Lock the slot before navigating
    try:
        lock_resp, locked_session_id = lock_tee_time(session, tee_sheet_id, num_players, email)
        print(f"LockTeeTimes: sessionId={locked_session_id}, error={lock_resp.get('error')!r}")
        if not lock_resp.get("isSuccess", True):
            return False, f"LockTeeTimes failed: {lock_resp}"
    except Exception as e:
        return False, f"LockTeeTimes error: {e}"

    # Step 3: Navigate to checkout so subsequent fetch() calls carry the correct Referer
    base_url = session.site.base_url
    checkout_url = f"{base_url}/onlineresweb/teetime/checkout?id={tee_sheet_id}&holes=0&numberOfPlayer=0"
    print(f"Navigating to checkout...")
    try:
        session.page.goto(checkout_url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        return False, f"Checkout navigation failed: {e}"
    time.sleep(3)

    # Step 4: Resolve rate code and cart type from tee time detail
    rate_code = slot.get("defaultRateCode", "")
    cart_type = 1
    deposit_amount = session.site.deposit_amount
    num_riders = 6
    try:
        detail = get_tee_time_detail(session, tee_sheet_id, num_players, course_id)
        if isinstance(detail, dict):
            rate_code = detail.get("defaultRateCode", rate_code)
            dbr = detail.get("defaultBookingRate") or {}
            if isinstance(dbr, dict):
                cart_type = dbr.get("cartType", cart_type)
    except Exception as e:
        print(f"TeeTime detail error (non-fatal): {e}")

    # Step 5: TeeTimePricesCalculation
    try:
        prices_resp = tee_time_prices_calculation(
            session, tee_sheet_id, num_players, session.golfer_id, session.acct,
            rate_code, cart_type, deposit_amount, num_riders,
        )
        prices_tx_id = prices_resp.get("transactionId") if isinstance(prices_resp, dict) else None
        if not prices_tx_id:
            return False, f"TeeTimePricesCalculation returned no transactionId: {str(prices_resp)[:300]}"
        print(f"TeeTimePricesCalculation: bookingTransactionId={prices_tx_id}")
    except Exception as e:
        return False, f"TeeTimePricesCalculation failed: {e}"

    # Step 6: Restriction check (siteId varies per Calgary course)
    try:
        slot_site_id = slot.get("siteId")
        check_restrict_reservation(session, tee_sheet_id, course_id, site_id=slot_site_id)
    except Exception as e:
        print(f"CheckRestrict error (non-fatal): {e}")

    # Step 7: Card on file (Kananaskis only — Calgary has no deposit)
    card_token = None
    if session.site.requires_payment:
        try:
            cards = get_credit_cards_on_file(session)
            if cards:
                card_token = cards[0].get("ccToken")
        except Exception as e:
            return False, f"GetAllCreditCardOnFile error: {e}"
        if not card_token:
            return False, "No card on file found"

    # Step 8: Register a fresh UUID as the booking transactionId.
    # NOTE: ReserveTeeTimes.transactionId = this UUID (not the prices one).
    #       ReserveTeeTimes.bookingTransactionId = prices_tx_id from step 5.
    try:
        tx_id = register_transaction_id(session)
        print(f"RegisterTransactionId: transactionId={tx_id}")
    except Exception as e:
        return False, f"RegisterTransactionId error: {e}"

    deposit_total = deposit_amount * num_players
    print(f"Reserving: transactionId={tx_id}, bookingTransactionId={prices_tx_id}, depositTotal={deposit_total}")

    # Step 9: Confirm
    try:
        reserve_resp = reserve_tee_times(session, locked_session_id, tx_id, prices_tx_id, email, card_token, deposit_total)
        print(f"Reserve response: {reserve_resp}")
        if not reserve_resp.get("isSuccess", True):
            return False, f"ReserveTeeTimes failed: {reserve_resp}"
    except Exception as e:
        print(f"ReserveTeeTimes FAILED: {e}")
        return False, f"ReserveTeeTimes error: {e}"

    return True, f"Booked: {summary}"

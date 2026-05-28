"""
Full booking chain:
  1. CheckBookingLimit     — verify we haven't hit a booking cap
  2. LockTeeTimes          — temporarily holds the slot; returns locked_session_id
  3. RegisterTransactionId — registers a fresh transaction UUID
  4. ReserveTeeTimes       — final confirmation; charges card on file server-side
"""

from api import check_booking_limit, lock_tee_time, register_transaction_id, reserve_tee_times
from auth import Session
from scanner import slot_summary


def book_slot(session: Session, slot: dict, num_players: int, email: str) -> bool:
    tee_sheet_id = slot["teeSheetId"]
    summary = slot_summary(slot)

    print(f"\nAttempting to book: {summary}")

    # Step 1: booking limit check
    try:
        limit_resp = check_booking_limit(session, tee_sheet_id)
        if not limit_resp.get("isSuccess", True):
            print(f"Booking limit check failed: {limit_resp}")
            return False
    except Exception as e:
        print(f"Warning: booking limit check error ({e}), proceeding anyway")

    # Step 2: lock the slot
    try:
        lock_resp, locked_session_id = lock_tee_time(session, tee_sheet_id, num_players, email)
        if not lock_resp.get("isSuccess", True):
            print(f"LockTeeTimes failed: {lock_resp}")
            return False
    except Exception as e:
        print(f"LockTeeTimes error: {e}")
        return False

    print(f"Slot locked: {summary}")

    # Step 3: register transaction ID
    try:
        transaction_id = register_transaction_id(session)
    except Exception as e:
        print(f"RegisterTransactionId error: {e}")
        return False

    # Step 4: confirm booking
    try:
        reserve_resp = reserve_tee_times(session, locked_session_id, transaction_id, email)
        if not reserve_resp.get("isSuccess", True):
            print(f"ReserveTeeTimes failed: {reserve_resp}")
            return False
    except Exception as e:
        print(f"ReserveTeeTimes error: {e}")
        return False

    print(f"Booking confirmed: {summary}")
    return True

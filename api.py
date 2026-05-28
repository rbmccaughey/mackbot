"""
Thin httpx wrapper around the CPS Golf API.
All requests use the static headers from config.py plus the Bearer token.
"""

import uuid
from datetime import date

import httpx

from auth import Session
from config import API_BASE, API_HEADERS, BASE_URL, CLASS_CODE, COURSE_IDS_PARAM, MEMBER_STORE_ID


def _headers(session: Session) -> dict:
    return {
        **API_HEADERS,
        "authorization": f"Bearer {session.access_token}",
        "accept": "application/json, text/plain, */*",
        "x-requestid": str(uuid.uuid4()),
    }


def _client(session: Session) -> httpx.Client:
    return httpx.Client(
        headers=_headers(session),
        cookies=session.cookies,
        timeout=15.0,
    )


def search_tee_times(session: Session, target_date: date, num_players: int,
                     time_min: float, time_max: float) -> list[dict]:
    date_str = target_date.strftime("%a %b %-d %Y")  # "Sat May 30 2026"
    params = {
        "searchDate": date_str,
        "holes": 0,
        "numberOfPlayer": num_players,
        "courseIds": COURSE_IDS_PARAM,
        "searchTimeType": 0,
        "transactionId": str(uuid.uuid4()),
        "teeOffTimeMin": int(time_min),
        "teeOffTimeMax": int(time_max),
        "isChangeTeeOffTime": "true",
        "teeSheetSearchView": 5,
        "classCode": CLASS_CODE,
        "defaultOnlineRate": "N",
        "isUseCapacityPricing": "false",
        "memberStoreId": MEMBER_STORE_ID,
        "searchType": 1,
    }
    with _client(session) as client:
        resp = client.get(f"{API_BASE}/TeeTimes", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [])


def lock_tee_time(session: Session, tee_sheet_id: int, num_players: int,
                  email: str) -> tuple[dict, str]:
    """Returns (response_json, session_id). session_id is reused as lockedTeeTimesSessionId."""
    session_id = str(uuid.uuid4())
    payload = {
        "teeSheetIds": [tee_sheet_id],
        "email": email,
        "action": "Online Reservation V5",
        "sessionId": session_id,
        "golferId": session.golfer_id,
        "classCode": CLASS_CODE,
        "numberOfPlayer": num_players,
        "navigateUrl": "",
        "isSmartCard": False,
        "isGroupBooking": False,
    }
    with _client(session) as client:
        resp = client.post(f"{API_BASE}/LockTeeTimes", json=payload)
        resp.raise_for_status()
        return resp.json(), session_id


def register_transaction_id(session: Session) -> str:
    """Registers a fresh transaction UUID with the server. Returns the transaction_id."""
    transaction_id = str(uuid.uuid4())
    with _client(session) as client:
        resp = client.post(
            f"{API_BASE}/RegisterTransactionId",
            json={"transactionId": transaction_id},
        )
        resp.raise_for_status()
    return transaction_id


def reserve_tee_times(session: Session, locked_session_id: str,
                      transaction_id: str, email: str) -> dict:
    """Final booking confirmation. Uses the session_id from lock_tee_time."""
    payload = {
        "cancelReservationLink": (
            f"{BASE_URL}/onlineresweb/auth/verify-email"
            "?returnUrl=cancel-booking"
        ),
        "homePageLink": f"{BASE_URL}/onlineresweb/",
        "affiliateId": None,
        "finalizeSaleModel": {
            "acct": session.acct,
            "playerId": 0,
            "isGuest": False,
            "creditCardInfo": {
                "cardNumber": None,
                "cardHolder": None,
                "expireMM": None,
                "expireYY": None,
                "cvv": None,
                "email": email,
                "cardToken": None,
            },
            "monerisCC": None,
            "ibxCC": None,
        },
        "sessionGuid": None,
        "lockedTeeTimesSessionId": locked_session_id,
        "bookingTransactionId": str(uuid.uuid4()),
        "transactionId": transaction_id,
    }
    with _client(session) as client:
        resp = client.post(f"{API_BASE}/ReserveTeeTimes", json=payload)
        resp.raise_for_status()
        return resp.json()


def check_booking_limit(session: Session, tee_sheet_id: int) -> dict:
    payload = {
        "golferId": session.golfer_id,
        "playerId": "0",
        "dependentId": "0",
        "teesheetId": tee_sheet_id,
        "isBuddy": False,
        "isWriteIn": False,
        "participantNo": 1,
        "reservationId": 0,
        "acct": session.acct,
        "memberClass": CLASS_CODE,
        "transactionId": None,
        "isPriorPlayingPartner": False,
    }
    with _client(session) as client:
        resp = client.post(f"{API_BASE}/CheckBookingLimit", json=payload)
        resp.raise_for_status()
        return resp.json()

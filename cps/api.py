"""
CPS Golf API client. All requests are made via page.evaluate(fetch(...)) so they
run inside the logged-in Playwright browser — Cloudflare, cookies, and auth context
are all handled naturally by the browser.
"""

import json
import uuid
from datetime import date

from cps.auth import Session


def _fetch(session: Session, url: str, method: str = "GET", body=None) -> dict:
    site = session.site
    headers = {
        "x-componentid": "1",
        "x-ismobile": "false",
        "x-moduleid": "7",
        "x-productid": "1",
        "x-siteid": site.header_site_id,
        "x-terminalid": "3",
        "x-timezone-offset": "360",
        "x-timezoneid": "America/Edmonton",
        "x-websiteid": site.website_id,
        "client-id": "onlineresweb",
        "origin": site.base_url,
        "referer": f"{site.base_url}/onlineresweb/",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "sec-ch-ua": '"Chromium";v="149", "Google Chrome";v="149", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "cache-control": "no-cache, no-store, must-revalidate",
        "pragma": "no-cache",
        "expires": "Sat, 01 Jan 2000 00:00:00 GMT",
        "if-modified-since": "0",
        "authorization": f"Bearer {session.access_token}",
        "accept": "application/json, text/plain, */*",
        "x-requestid": str(uuid.uuid4()),
    }
    result = session.page.evaluate(
        """async (args) => {
            const xsrfCookie = document.cookie.split('; ').find(r => r.startsWith('XSRF-TOKEN='));
            if (xsrfCookie) {
                const tok = decodeURIComponent(xsrfCookie.split('=')[1]);
                args.headers['x-xsrf-token'] = tok;
            }
            const opts = {
                method: args.method,
                headers: args.headers,
            };
            if (args.body !== null) {
                opts.body = JSON.stringify(args.body);
                opts.headers['content-type'] = 'application/json';
            }
            const resp = await fetch(args.url, opts);
            const body = await resp.text();
            const hdrs = {};
            resp.headers.forEach((v, k) => { hdrs[k] = v; });
            return { status: resp.status, body, headers: hdrs };
        }""",
        {"url": url, "method": method, "headers": headers, "body": body},
    )
    status = result["status"]
    body_text = result["body"]
    if status >= 400:
        resp_headers = result.get("headers", {})
        print(f"[{status}] {url.split('/')[-1].split('?')[0]} response headers: {resp_headers}")
        raise Exception(f"{method} {url.split('/')[-1].split('?')[0]} {status}: {body_text[:300]}")
    return json.loads(body_text) if body_text else {}


def _api_base(session: Session) -> str:
    return f"{session.site.base_url}/onlineres/onlineapi/api/v1/onlinereservation"


def search_tee_times(session: Session, target_date: date, num_players: int,
                     time_min: float, time_max: float,
                     course_ids: list[int] | None = None) -> tuple[list[dict], str]:
    if course_ids is None:
        course_ids = session.site.course_ids
    date_str = target_date.strftime("%a %b %-d %Y")
    transaction_id = register_transaction_id(session)
    params = "&".join(f"{k}={v}" for k, v in {
        "searchDate": date_str.replace(" ", "+"),
        "holes": 0,
        "numberOfPlayer": num_players,
        "courseIds": ",".join(str(c) for c in course_ids),
        "searchTimeType": 0,
        "transactionId": transaction_id,
        "teeOffTimeMin": int(time_min),
        "teeOffTimeMax": int(time_max),
        "isChangeTeeOffTime": "true",
        "teeSheetSearchView": 5,
        "classCode": session.site.class_code,
        "defaultOnlineRate": "N",
        "isUseCapacityPricing": "false",
        "memberStoreId": session.site.member_store_id,
        "searchType": 1,
    }.items())
    data = _fetch(session, f"{_api_base(session)}/TeeTimes?{params}")
    content = data.get("content", [])
    return (content if isinstance(content, list) else []), transaction_id


def lock_tee_time(session: Session, tee_sheet_id: int, num_players: int,
                  email: str) -> tuple[dict, str]:
    session_id = str(uuid.uuid4())
    payload = {
        "teeSheetIds": [tee_sheet_id],
        "email": email,
        "action": "Online Reservation V5",
        "sessionId": session_id,
        "golferId": session.golfer_id,
        "classCode": session.site.class_code,
        "numberOfPlayer": num_players,
        "navigateUrl": "",
        "isSmartCard": False,
        "isGroupBooking": False,
    }
    data = _fetch(session, f"{_api_base(session)}/LockTeeTimes", method="POST", body=payload)
    return data, data.get("sessionId", session_id)


def register_transaction_id(session: Session, transaction_id: str | None = None) -> str:
    if transaction_id is None:
        transaction_id = str(uuid.uuid4())
    resp = _fetch(session, f"{_api_base(session)}/RegisterTransactionId", method="POST", body={"transactionId": transaction_id})
    print(f"RegisterTransactionId resp: {resp!r}")
    if isinstance(resp, dict) and resp.get("transactionId"):
        return resp["transactionId"]
    return transaction_id


def reserve_tee_times(session: Session, locked_session_id: str,
                      transaction_id: str, booking_transaction_id: str,
                      email: str, card_token: str | None, deposit_total: int) -> dict:
    base_url = session.site.base_url
    payload = {
        "cancelReservationLink": f"{base_url}/onlineresweb/auth/verify-email?returnUrl=cancel-booking",
        "homePageLink": f"{base_url}/onlineresweb/",
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
                "cardToken": card_token,
            },
            "monerisCC": {
                "amount": deposit_total,
                "acct": session.acct,
                "token": card_token,
            } if card_token else None,
            "ibxCC": None,
        },
        "sessionGuid": None,
        "lockedTeeTimesSessionId": locked_session_id,
        "bookingTransactionId": booking_transaction_id,
        "transactionId": transaction_id,
    }
    return _fetch(session, f"{_api_base(session)}/ReserveTeeTimes", method="POST", body=payload)


def get_tee_time_detail(session: Session, tee_sheet_id: int, num_players: int, course_id: int) -> dict:
    params = "&".join(f"{k}={v}" for k, v in {
        "teeSheetId": tee_sheet_id,
        "holes": 0,
        "numberOfPlayer": num_players,
        "classCode": session.site.class_code,
        "defaultOnlineRate": "N",
        "courseIds": course_id,
        "isUseCapacityPricing": "false",
        "memberStoreId": session.site.member_store_id,
    }.items())
    return _fetch(session, f"{_api_base(session)}/TeeTime?{params}")


def tee_time_prices_calculation(session: Session, tee_sheet_id: int, num_players: int,
                                golfer_id: int, acct: str, rate_code: str,
                                cart_type: int = 1, deposit_amount: int = 0,
                                num_riders: int = 6) -> dict:
    booking_list = []
    for i in range(1, num_players + 1):
        entry = {
            "teeSheetId": tee_sheet_id,
            "holes": 18,
            "participantNo": i,
            "golferId": golfer_id,
            "rateCode": rate_code,
            "isUnAssignedPlayer": i > 1,
            "memberClassCode": session.site.class_code if i == 1 else "OUT",
            "memberStoreId": str(session.site.member_store_id),
            "cartType": cart_type,
            "playerId": "0",
            "acct": acct,
            "isGuestOf": False,
            "isUseCapacityPricing": False,
            "isSmartCard": False,
        }
        if i == 1:
            entry["dependentId"] = "0"
        booking_list.append(entry)
    payload = {
        "selectedTeeSheetId": tee_sheet_id,
        "bookingList": booking_list,
        "holes": 18,
        "numberOfPlayer": num_players,
        "numberOfRider": num_riders,
        "cartType": cart_type,
        "coupon": None,
        "depositType": 0,
        "depositAmount": deposit_amount,
        "selectedValuePackageCode": None,
        "isUseCapacityPricing": False,
        "thirdPartyId": None,
        "ibxCardOnFile": None,
        "advancedBookingFee": None,
        "transactionId": None,
        "isPrepayDeposit": False,
    }
    return _fetch(session, f"{_api_base(session)}/TeeTimePricesCalculation", method="POST", body=payload)


def check_restrict_reservation(session: Session, tee_sheet_id: int, course_id: int,
                               site_id: int | None = None) -> dict:
    return _fetch(session, f"{_api_base(session)}/CheckRestrictReservation", method="POST", body={
        "teeSheetId": tee_sheet_id,
        "courseId": course_id,
        "siteId": site_id if site_id is not None else session.site.payload_site_id,
        "classCode": session.site.class_code,
    })


def get_credit_cards_on_file(session: Session) -> list[dict]:
    data = _fetch(session, f"{_api_base(session)}/GetAllCreditCardOnFile?isUseIbxToken=false&isUseHostedTokenizePermanent=true")
    return data if isinstance(data, list) else data.get("content", []) if isinstance(data, dict) else []


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
        "memberClass": session.site.class_code,
        "transactionId": None,
        "isPriorPlayingPartner": False,
    }
    return _fetch(session, f"{_api_base(session)}/CheckBookingLimit", method="POST", body=payload)

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BookingConfig:
    target_date: date
    time_min_hour: float = 8.0
    time_max_hour: float = 10.0
    num_players: int = 4
    # 1 = Mt Lorette, 2 = Mt Kidd. Empty list means any course.
    course_ids: list[int] = field(default_factory=lambda: [1, 2])
    poll_interval_secs: int = 300


# Static headers sent on every API request
API_HEADERS = {
    "x-componentid": "1",
    "x-ismobile": "false",
    "x-moduleid": "7",
    "x-productid": "1",
    "x-siteid": "2",
    "x-terminalid": "3",
    "x-timezone-offset": "360",
    "x-timezoneid": "America/Edmonton",
    "x-websiteid": "ed189e3e-c873-4785-6262-08d8fddc05d5",
    "client-id": "onlineresweb",
    "cache-control": "no-cache, no-store, must-revalidate",
    "pragma": "no-cache",
    "expires": "Sat, 01 Jan 2000 00:00:00 GMT",
    "if-modified-since": "0",
}

BASE_URL = "https://kananaskisabresidents.cps.golf"
API_BASE = f"{BASE_URL}/onlineres/onlineapi/api/v1/onlinereservation"

# User-specific constants extracted from JWT claims
CLASS_CODE = "ABRES"
MEMBER_STORE_ID = 2
COURSE_IDS_PARAM = "2,1"

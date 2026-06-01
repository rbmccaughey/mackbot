from dataclasses import dataclass, field
from datetime import date


@dataclass
class SiteConfig:
    name: str
    base_url: str
    website_id: str
    header_site_id: str      # x-siteid request header
    payload_site_id: int     # siteId in CheckRestrictReservation body
    class_code: str
    member_store_id: int
    course_ids: list[int]    # all courses available on this site
    email_env: str           # env var name for login email
    password_env: str        # env var name for login password
    requires_payment: bool = True
    deposit_amount: int = 0  # per-player deposit in dollars


KANANASKIS = SiteConfig(
    name="Kananaskis",
    base_url="https://kananaskisabresidents.cps.golf",
    website_id="ed189e3e-c873-4785-6262-08d8fddc05d5",
    header_site_id="2",
    payload_site_id=2,
    class_code="ABRES",
    member_store_id=2,
    course_ids=[1, 2],  # 1=Mt Lorette, 2=Mt Kidd
    email_env="GOLF_EMAIL",
    password_env="GOLF_PASSWORD",
    requires_payment=True,
    deposit_amount=35,
)

CALGARY = SiteConfig(
    name="Calgary",
    base_url="https://cityofcalgarygolf.cps.golf",
    website_id="f4cd6968-3078-4e3f-9fdf-08dbc69b5717",
    header_site_id="1",
    payload_site_id=4,
    class_code="ADGF",
    member_store_id=1,
    course_ids=[1, 2, 3, 4, 5, 6, 7, 8, 11, 12],
    email_env="CALGARY_GOLF_EMAIL",
    password_env="CALGARY_GOLF_PASSWORD",
    requires_payment=False,
    deposit_amount=0,
)

SITES: dict[str, SiteConfig] = {
    "kananaskis": KANANASKIS,
    "calgary": CALGARY,
}


@dataclass
class BookingConfig:
    target_date: date
    site: SiteConfig
    time_min_hour: float = 8.0
    time_max_hour: float = 10.0
    num_players: int = 4
    course_ids: list[int] = field(default_factory=list)
    poll_interval_secs: int = 300

    def __post_init__(self):
        if not self.course_ids:
            self.course_ids = list(self.site.course_ids)

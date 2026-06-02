from courses.valley_ridge.auth import VRSession, login_vr
from courses.valley_ridge.api import search_tee_times_vr, check_holds_vr, find_booking_option
from courses.valley_ridge.booker import book_slot_vr, slot_summary_vr
from config import VALLEY_RIDGE as SITE

__all__ = [
    "VRSession", "login_vr",
    "search_tee_times_vr", "check_holds_vr", "find_booking_option",
    "book_slot_vr", "slot_summary_vr",
    "SITE",
]

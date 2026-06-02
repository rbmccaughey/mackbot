from cps.auth import Session, login
from cps.api import search_tee_times
from cps.booker import book_slot
from cps.scanner import find_matching_slots, slot_summary
from config import KANANASKIS as SITE

__all__ = ["Session", "login", "search_tee_times", "book_slot", "find_matching_slots", "slot_summary", "SITE"]

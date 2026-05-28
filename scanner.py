"""
Filters tee time search results against a BookingConfig.
A slot matches when:
  - startTime falls within [time_min_hour, time_max_hour)
  - desired num_players is in availableParticipantNo
  - bookingList is empty (slot not yet taken)
  - courseId is in config.course_ids (or course_ids is empty = any)
"""

from datetime import datetime

from config import BookingConfig


def find_matching_slots(slots: list[dict], cfg: BookingConfig) -> list[dict]:
    matches = []
    for slot in slots:
        start = datetime.fromisoformat(slot["startTime"])
        hour = start.hour + start.minute / 60

        if hour < cfg.time_min_hour or hour >= cfg.time_max_hour:
            continue
        if cfg.num_players not in slot.get("availableParticipantNo", []):
            continue
        if slot.get("bookingList"):
            continue
        if cfg.course_ids and slot.get("courseId") not in cfg.course_ids:
            continue

        matches.append(slot)

    return matches


def slot_summary(slot: dict) -> str:
    start = datetime.fromisoformat(slot["startTime"])
    course = slot.get("courseName", "Unknown")
    players = slot.get("playersDisplay", "")
    return f"{course}  {start.strftime('%I:%M %p')}  ({players})"

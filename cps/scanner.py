"""
Filters tee time search results against a BookingConfig.
A slot matches when:
  - startTime falls within [time_min_hour, time_max_hour)
  - availableParticipantNo has at least num_players open positions
  - courseId is in config.course_ids (or course_ids is empty = any)
"""

from datetime import datetime

from config import BookingConfig


def find_matching_slots(slots: list[dict], cfg: BookingConfig) -> list[dict]:
    matches = []
    for slot in slots:
        start = datetime.fromisoformat(slot["startTime"])
        hour = start.hour + start.minute / 60
        label = f"{start.strftime('%I:%M %p')} (course {slot.get('courseId')})"

        if hour < cfg.time_min_hour or hour >= cfg.time_max_hour:
            print(f"  SKIP {label}: time {hour:.2f} outside [{cfg.time_min_hour}, {cfg.time_max_hour})")
            continue
        if len(slot.get("availableParticipantNo", [])) < cfg.num_players:
            print(f"  SKIP {label}: need {cfg.num_players} spots but availableParticipantNo={slot.get('availableParticipantNo')}")
            continue
        if cfg.course_ids and slot.get("courseId") not in cfg.course_ids:
            print(f"  SKIP {label}: courseId {slot.get('courseId')} not in {cfg.course_ids}")
            continue

        matches.append(slot)

    return matches


def slot_summary(slot: dict) -> str:
    start = datetime.fromisoformat(slot["startTime"])
    course = slot.get("courseName", "Unknown")
    players = slot.get("playersDisplay", "")
    return f"{course}  {start.strftime('%I:%M %p')}  ({players})"

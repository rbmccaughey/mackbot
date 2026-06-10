from datetime import date

import pytest

from config import BookingConfig, KANANASKIS
from cps.scanner import find_matching_slots, slot_summary


def make_slot(start_time, available_positions, booking_list=None, course_id=1):
    return {
        "teeSheetId": 1,
        "startTime": start_time,
        "availableParticipantNo": available_positions,
        "bookingList": booking_list or [],
        "courseId": course_id,
        "courseName": "Mt Lorette",
        "playersDisplay": "4 players",
    }


def make_cfg(**kwargs):
    defaults = {
        "target_date": date(2026, 6, 15),
        "site": KANANASKIS,
        "time_min_hour": 8.0,
        "time_max_hour": 10.0,
        "num_players": 4,
        "course_ids": [1, 2],
    }
    defaults.update(kwargs)
    return BookingConfig(**defaults)


class TestFindMatchingSlots:
    def test_matching_slot_returned(self):
        cfg = make_cfg()
        slots = [make_slot("2026-06-15T09:00:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, cfg) == slots

    def test_empty_input_returns_empty(self):
        assert find_matching_slots([], make_cfg()) == []

    def test_slot_before_time_window_excluded(self):
        slots = [make_slot("2026-06-15T07:59:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, make_cfg(time_min_hour=8.0)) == []

    def test_slot_at_time_min_included(self):
        slots = [make_slot("2026-06-15T08:00:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, make_cfg(time_min_hour=8.0)) == slots

    def test_slot_at_time_max_excluded(self):
        slots = [make_slot("2026-06-15T10:00:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, make_cfg(time_max_hour=10.0)) == []

    def test_slot_just_before_time_max_included(self):
        slots = [make_slot("2026-06-15T09:59:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, make_cfg(time_max_hour=10.0)) == slots

    def test_too_few_positions_excluded(self):
        # 2 open positions, need 4 players
        slots = [make_slot("2026-06-15T09:00:00", [3, 4])]
        assert find_matching_slots(slots, make_cfg(num_players=4)) == []

    def test_exact_positions_available_included(self):
        # 4 open positions, need 4 players
        slots = [make_slot("2026-06-15T09:00:00", [1, 2, 3, 4])]
        assert find_matching_slots(slots, make_cfg(num_players=4)) == slots

    def test_single_player_joins_partial_group(self):
        # 1 open position (position 4), need 1 player — should match
        slots = [make_slot("2026-06-15T09:00:00", [4])]
        assert find_matching_slots(slots, make_cfg(num_players=1)) == slots

    def test_partial_group_too_small_excluded(self):
        # 1 open position, need 2 players — should not match
        slots = [make_slot("2026-06-15T09:00:00", [4])]
        assert find_matching_slots(slots, make_cfg(num_players=2)) == []

    def test_wrong_course_excluded(self):
        slots = [make_slot("2026-06-15T09:00:00", [1, 2, 3, 4], course_id=1)]
        assert find_matching_slots(slots, make_cfg(course_ids=[2])) == []

    def test_matching_course_included(self):
        slots = [make_slot("2026-06-15T09:00:00", [1, 2, 3, 4], course_id=2)]
        assert find_matching_slots(slots, make_cfg(course_ids=[2])) == slots

    def test_no_course_filter_matches_any_course(self):
        cfg = make_cfg()
        cfg.course_ids = []  # force empty to bypass __post_init__ default
        slots = [make_slot("2026-06-15T09:00:00", [1, 2, 3, 4], course_id=999)]
        assert find_matching_slots(slots, cfg) == slots

    def test_multiple_matching_slots_all_returned(self):
        cfg = make_cfg()
        slots = [
            make_slot("2026-06-15T08:00:00", [1, 2, 3, 4]),
            make_slot("2026-06-15T09:00:00", [1, 2, 3, 4]),
            make_slot("2026-06-15T10:30:00", [1, 2, 3, 4]),  # outside window
        ]
        result = find_matching_slots(slots, cfg)
        assert len(result) == 2

    def test_fractional_time_window(self):
        cfg = make_cfg(time_min_hour=8.5, time_max_hour=9.5)
        slots = [
            make_slot("2026-06-15T08:29:00", [1, 2, 3, 4]),  # < 8.5
            make_slot("2026-06-15T08:30:00", [1, 2, 3, 4]),  # == 8.5, included
            make_slot("2026-06-15T09:30:00", [1, 2, 3, 4]),  # == 9.5, excluded
        ]
        result = find_matching_slots(slots, cfg)
        assert len(result) == 1
        assert result[0]["startTime"] == "2026-06-15T08:30:00"

    def test_mixed_valid_invalid_slots(self):
        cfg = make_cfg(num_players=4, course_ids=[1])
        slots = [
            make_slot("2026-06-15T09:00:00", [1, 2, 3, 4], course_id=1),  # match
            make_slot("2026-06-15T09:00:00", [3, 4], course_id=1),         # too few positions
            make_slot("2026-06-15T09:00:00", [1, 2, 3, 4], course_id=2),  # wrong course
            make_slot("2026-06-15T11:00:00", [1, 2, 3, 4], course_id=1),  # outside time window
        ]
        result = find_matching_slots(slots, cfg)
        assert len(result) == 1


class TestSlotSummary:
    def test_contains_course_time_and_players(self):
        slot = {
            "startTime": "2026-06-15T08:30:00",
            "courseName": "Mt Lorette",
            "playersDisplay": "4 players",
        }
        summary = slot_summary(slot)
        assert "Mt Lorette" in summary
        assert "08:30 AM" in summary
        assert "4 players" in summary

    def test_missing_optional_fields_use_defaults(self):
        summary = slot_summary({"startTime": "2026-06-15T08:30:00"})
        assert "Unknown" in summary

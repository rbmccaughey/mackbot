import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from api_vr import search_tee_times_vr, find_booking_option, _find_user_payment_type


def make_vr_slot(teedatetime, available_spots=4, available_18=True):
    return {
        "id": 1,
        "teedatetime": teedatetime,
        "available_spots": available_spots,
        "available_18": available_18,
    }


def mock_httpx_response(slots):
    resp = MagicMock()
    resp.json.return_value = {"teetimes": slots}
    resp.raise_for_status = MagicMock()
    return resp


class TestSearchTeeTimes:
    def test_returns_matching_slots(self):
        slots = [make_vr_slot("2026-06-15T09:00:00")]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert len(result) == 1

    def test_empty_response_returns_empty(self):
        with patch("api_vr.httpx.get", return_value=mock_httpx_response([])):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert result == []

    def test_filters_slot_before_time_min(self):
        slots = [make_vr_slot("2026-06-15T07:59:00"), make_vr_slot("2026-06-15T09:00:00")]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert len(result) == 1

    def test_filters_slot_at_time_max(self):
        slots = [make_vr_slot("2026-06-15T10:00:00"), make_vr_slot("2026-06-15T09:00:00")]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert len(result) == 1

    def test_filters_insufficient_available_spots(self):
        slots = [make_vr_slot("2026-06-15T09:00:00", available_spots=2)]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert result == []

    def test_exact_available_spots_matches(self):
        slots = [make_vr_slot("2026-06-15T09:00:00", available_spots=4)]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert len(result) == 1

    def test_filters_unavailable_18_holes(self):
        slots = [make_vr_slot("2026-06-15T09:00:00", available_18=False)]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert result == []

    def test_multiple_filters_applied_together(self):
        slots = [
            make_vr_slot("2026-06-15T09:00:00", available_spots=4, available_18=True),   # match
            make_vr_slot("2026-06-15T09:00:00", available_spots=2, available_18=True),   # too few spots
            make_vr_slot("2026-06-15T09:00:00", available_spots=4, available_18=False),  # no 18h
            make_vr_slot("2026-06-15T11:00:00", available_spots=4, available_18=True),   # outside window
        ]
        with patch("api_vr.httpx.get", return_value=mock_httpx_response(slots)):
            result = search_tee_times_vr(date(2026, 6, 15), 4, 8.0, 10.0)
        assert len(result) == 1


def make_candidate(id, payment_type_id, parent_id=0, price_total="0"):
    return {
        "id": id,
        "payment_type_id": payment_type_id,
        "parent_id": parent_id,
        "price_total": price_total,
    }


class TestFindBookingOption:
    def test_fallback_selects_lowest_price(self):
        candidates = [
            make_candidate(1, 10, price_total="50"),
            make_candidate(2, 20, price_total="30"),
        ]
        details = {"options": candidates}
        booking_id, pt_id, _ = find_booking_option(details, json.dumps(details))
        assert booking_id == 2
        assert pt_id == 20

    def test_user_payment_type_takes_priority_over_price(self):
        candidates = [
            make_candidate(1, 10, price_total="50"),
            make_candidate(2, 20, price_total="0"),
        ]
        details = {"options": candidates, "user": {"payment_type_id": 10}}
        booking_id, pt_id, _ = find_booking_option(details, json.dumps(details))
        assert booking_id == 1
        assert pt_id == 10

    def test_env_var_overrides_user_payment_type(self, monkeypatch):
        monkeypatch.setenv("VR_PAYMENT_TYPE_ID", "20")
        candidates = [
            make_candidate(1, 10, price_total="0"),
            make_candidate(2, 20, price_total="999"),
        ]
        details = {"options": candidates, "user": {"payment_type_id": 10}}
        booking_id, pt_id, _ = find_booking_option(details, json.dumps(details))
        assert booking_id == 2
        assert pt_id == 20

    def test_raises_when_no_booking_options(self):
        details = {"foo": "bar"}
        with pytest.raises(RuntimeError, match="No booking options found"):
            find_booking_option(details, json.dumps(details))

    def test_returns_parent_id(self):
        candidates = [make_candidate(5, 10, parent_id=99)]
        details = {"options": candidates}
        _, _, parent_id = find_booking_option(details, json.dumps(details))
        assert parent_id == 99

    def test_fallback_handles_non_numeric_price_total(self):
        # Exercises the TypeError/ValueError except branch in _price()
        candidates = [
            make_candidate(1, 10, price_total=None),   # None → except → 9999.0
            make_candidate(2, 20, price_total="30"),
        ]
        details = {"options": candidates}
        booking_id, pt_id, _ = find_booking_option(details, json.dumps(details))
        assert booking_id == 2
        assert pt_id == 20

    def test_env_var_override_falls_through_when_not_found(self, monkeypatch):
        monkeypatch.setenv("VR_PAYMENT_TYPE_ID", "999")
        candidates = [
            make_candidate(1, 10, price_total="50"),
            make_candidate(2, 20, price_total="30"),
        ]
        details = {"options": candidates}
        # Env var 999 not found → falls through to lowest price
        booking_id, pt_id, _ = find_booking_option(details, json.dumps(details))
        assert pt_id == 20


class TestCheckHoldsVR:
    def test_returns_json_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": "teetime available", "hold": None}
        mock_resp.raise_for_status = MagicMock()
        with patch("api_vr.httpx.get", return_value=mock_resp) as mock_get:
            from api_vr import check_holds_vr
            result = check_holds_vr(2001)
        assert result == {"success": "teetime available", "hold": None}
        mock_get.assert_called_once()

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
        with patch("api_vr.httpx.get", return_value=mock_resp):
            from api_vr import check_holds_vr
            with pytest.raises(Exception, match="404"):
                check_holds_vr(9999)


class TestFindUserPaymentType:
    def test_direct_user_payment_type_id(self):
        assert _find_user_payment_type({"user": {"payment_type_id": 42}}) == 42

    def test_nested_payment_type_id(self):
        assert _find_user_payment_type({"user": {"payment_type": {"id": 99}}}) == 99

    def test_member_payment_type_id(self):
        assert _find_user_payment_type({"member": {"payment_type_id": 7}}) == 7

    def test_returns_none_when_absent(self):
        assert _find_user_payment_type({"foo": "bar"}) is None

    def test_returns_none_for_non_int(self):
        assert _find_user_payment_type({"payment_type_id": "not-an-int"}) is None

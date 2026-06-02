from unittest.mock import MagicMock, patch

import pytest


VR_RECEIPT_URL = "https://valleyridgegolf.teetimes.totalclubunity.com/booking/receipt/123"
VR_DETAILS_URL = "https://valleyridgegolf.teetimes.totalclubunity.com/booking/details/2001/5/any/"


def make_vr_session():
    session = MagicMock()
    session.user_id = 99
    return session


def make_vr_slot(teetime_id=2001):
    return {
        "id": teetime_id,
        "teedatetime": "2026-06-15T09:00:00",
        "available_spots": 4,
    }


class TestBookSlotVR:
    @patch("booker_vr.book_teetime_vr", return_value={"status": 200, "url": VR_RECEIPT_URL, "body": ""})
    @patch("booker_vr.find_booking_option", return_value=(5, 10, 0))
    @patch("booker_vr.get_teetime_details_vr", return_value=({"options": []}, "{}"))
    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": None})
    def test_successful_booking(self, mock_holds, mock_details, mock_option, mock_book):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is True
        assert "Booked" in msg

    @patch("booker_vr.check_holds_vr", return_value={"success": "slot is full", "hold": None})
    def test_fails_when_slot_not_available(self, mock_holds):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "Slot no longer available" in msg

    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": "held"})
    def test_fails_when_slot_held(self, mock_holds):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "held" in msg.lower()

    @patch("booker_vr.check_holds_vr", side_effect=Exception("timeout"))
    def test_fails_on_holds_exception(self, mock_holds):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "checkholds error" in msg

    @patch("booker_vr.get_teetime_details_vr", side_effect=Exception("403"))
    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": None})
    def test_fails_on_details_exception(self, mock_holds, mock_details):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "teetimedetails error" in msg

    @patch("booker_vr.book_teetime_vr", side_effect=Exception("CSRF missing"))
    @patch("booker_vr.find_booking_option", return_value=(5, 10, 0))
    @patch("booker_vr.get_teetime_details_vr", return_value=({"options": []}, "{}"))
    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": None})
    def test_fails_on_booking_exception(self, mock_holds, mock_details, mock_option, mock_book):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "Booking error" in msg

    @patch("booker_vr.book_teetime_vr", return_value={"status": 200, "url": VR_DETAILS_URL, "body": ""})
    @patch("booker_vr.find_booking_option", return_value=(5, 10, 0))
    @patch("booker_vr.get_teetime_details_vr", return_value=({"options": []}, "{}"))
    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": None})
    def test_fails_when_not_redirected_to_receipt(self, mock_holds, mock_details, mock_option, mock_book):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "Unexpected" in msg

    @patch("booker_vr.book_teetime_vr", return_value={"status": 422, "url": VR_DETAILS_URL, "body": "Unprocessable"})
    @patch("booker_vr.find_booking_option", return_value=(5, 10, 0))
    @patch("booker_vr.get_teetime_details_vr", return_value=({"options": []}, "{}"))
    @patch("booker_vr.check_holds_vr", return_value={"success": "teetime available", "hold": None})
    def test_fails_on_4xx_response(self, mock_holds, mock_details, mock_option, mock_book):
        from booker_vr import book_slot_vr
        ok, msg = book_slot_vr(make_vr_session(), make_vr_slot(), 4)
        assert ok is False
        assert "422" in msg

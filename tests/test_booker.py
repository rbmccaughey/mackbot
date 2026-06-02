from unittest.mock import MagicMock, patch

import pytest


def make_session(requires_payment=True):
    session = MagicMock()
    session.golfer_id = 12345
    session.acct = "TESTACCT"
    session.site = MagicMock()
    session.site.requires_payment = requires_payment
    session.site.deposit_amount = 35 if requires_payment else 0
    session.site.base_url = "https://kananaskisabresidents.cps.golf"
    session.site.class_code = "ABRES"
    session.site.member_store_id = 2
    return session


def make_slot(tee_sheet_id=1001, course_id=1):
    return {
        "teeSheetId": tee_sheet_id,
        "courseId": course_id,
        "startTime": "2026-06-15T09:00:00",
        "courseName": "Mt Lorette",
        "playersDisplay": "4 players",
        "defaultRateCode": "ABRES",
    }


class TestBookSlot:
    @patch("booker.time.sleep")
    @patch("booker.register_transaction_id", return_value="tx-fresh")
    @patch("booker.reserve_tee_times", return_value={"isSuccess": True})
    @patch("booker.get_credit_cards_on_file", return_value=[{"ccToken": "tok-123"}])
    @patch("booker.check_restrict_reservation", return_value={})
    @patch("booker.tee_time_prices_calculation", return_value={"transactionId": "prices-tx"})
    @patch("booker.get_tee_time_detail", return_value={"defaultRateCode": "ABRES"})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-session-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_successful_booking(
        self, mock_limit, mock_lock, mock_detail, mock_prices,
        mock_restrict, mock_cards, mock_reserve, mock_reg_tx, mock_sleep
    ):
        from booker import book_slot
        session = make_session()
        ok, msg = book_slot(session, make_slot(), 4, "test@test.com")
        assert ok is True
        assert "Booked" in msg

    @patch("booker.time.sleep")
    @patch("booker.register_transaction_id", return_value="tx-fresh")
    @patch("booker.reserve_tee_times", return_value={"isSuccess": True})
    @patch("booker.get_credit_cards_on_file", return_value=[{"ccToken": "tok-123"}])
    @patch("booker.check_restrict_reservation", return_value={})
    @patch("booker.tee_time_prices_calculation", return_value={"transactionId": "prices-tx"})
    @patch("booker.get_tee_time_detail", return_value={})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-session-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_reserve_called_with_correct_uuid_mapping(
        self, mock_limit, mock_lock, mock_detail, mock_prices,
        mock_restrict, mock_cards, mock_reserve, mock_reg_tx, mock_sleep
    ):
        # ReserveTeeTimes.transactionId == RegisterTransactionId result
        # ReserveTeeTimes.bookingTransactionId == TeeTimePricesCalculation result
        from booker import book_slot
        session = make_session()
        book_slot(session, make_slot(), 4, "test@test.com")
        _, kwargs = mock_reserve.call_args
        call_args = mock_reserve.call_args[0]
        # (session, locked_session_id, tx_id, booking_transaction_id, email, card_token, deposit_total)
        locked_session_id, tx_id, booking_tx_id = call_args[1], call_args[2], call_args[3]
        assert tx_id == "tx-fresh"
        assert booking_tx_id == "prices-tx"

    @patch("booker.check_booking_limit", return_value={"isSuccess": False})
    def test_fails_on_booking_limit(self, mock_limit):
        from booker import book_slot
        ok, msg = book_slot(make_session(), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "limit" in msg.lower()

    @patch("booker.lock_tee_time", return_value=({"isSuccess": False}, ""))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_fails_on_lock_failure(self, mock_limit, mock_lock):
        from booker import book_slot
        ok, msg = book_slot(make_session(), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "LockTeeTimes" in msg

    @patch("booker.lock_tee_time", side_effect=Exception("network error"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_fails_on_lock_exception(self, mock_limit, mock_lock):
        from booker import book_slot
        ok, msg = book_slot(make_session(), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "LockTeeTimes error" in msg

    @patch("booker.time.sleep")
    @patch("booker.tee_time_prices_calculation", return_value={})  # no transactionId
    @patch("booker.get_tee_time_detail", return_value={})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_fails_when_prices_calc_returns_no_transaction_id(
        self, mock_limit, mock_lock, mock_detail, mock_prices, mock_sleep
    ):
        from booker import book_slot
        ok, msg = book_slot(make_session(), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "transactionId" in msg

    @patch("booker.time.sleep")
    @patch("booker.get_credit_cards_on_file", return_value=[])
    @patch("booker.check_restrict_reservation", return_value={})
    @patch("booker.tee_time_prices_calculation", return_value={"transactionId": "prices-tx"})
    @patch("booker.get_tee_time_detail", return_value={})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_fails_when_no_card_on_file(
        self, mock_limit, mock_lock, mock_detail, mock_prices,
        mock_restrict, mock_cards, mock_sleep
    ):
        from booker import book_slot
        ok, msg = book_slot(make_session(requires_payment=True), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "card" in msg.lower()

    @patch("booker.time.sleep")
    @patch("booker.register_transaction_id", return_value="tx-fresh")
    @patch("booker.reserve_tee_times", return_value={"isSuccess": True})
    @patch("booker.check_restrict_reservation", return_value={})
    @patch("booker.tee_time_prices_calculation", return_value={"transactionId": "prices-tx"})
    @patch("booker.get_tee_time_detail", return_value={})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_no_card_required_for_non_payment_site(
        self, mock_limit, mock_lock, mock_detail, mock_prices,
        mock_restrict, mock_reserve, mock_reg_tx, mock_sleep
    ):
        from booker import book_slot
        ok, msg = book_slot(make_session(requires_payment=False), make_slot(), 4, "test@test.com")
        assert ok is True

    @patch("booker.time.sleep")
    @patch("booker.register_transaction_id", return_value="tx-fresh")
    @patch("booker.reserve_tee_times", side_effect=Exception("payment failed"))
    @patch("booker.get_credit_cards_on_file", return_value=[{"ccToken": "tok"}])
    @patch("booker.check_restrict_reservation", return_value={})
    @patch("booker.tee_time_prices_calculation", return_value={"transactionId": "prices-tx"})
    @patch("booker.get_tee_time_detail", return_value={})
    @patch("booker.lock_tee_time", return_value=({"isSuccess": True}, "lock-id"))
    @patch("booker.check_booking_limit", return_value={"isSuccess": True})
    def test_fails_on_reserve_exception(
        self, mock_limit, mock_lock, mock_detail, mock_prices,
        mock_restrict, mock_cards, mock_reserve, mock_reg_tx, mock_sleep
    ):
        from booker import book_slot
        ok, msg = book_slot(make_session(), make_slot(), 4, "test@test.com")
        assert ok is False
        assert "ReserveTeeTimes error" in msg

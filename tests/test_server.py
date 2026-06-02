import os
import threading
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from server import app, _scans, _hour, _public, _log


@pytest.fixture
def client():
    return TestClient(app)


class TestHourHelper:
    def test_whole_hour(self):
        assert _hour("08:00") == 8.0

    def test_half_hour(self):
        assert _hour("08:30") == 8.5

    def test_quarter_hour(self):
        assert _hour("08:15") == 8.25

    def test_midnight(self):
        assert _hour("00:00") == 0.0


class TestPublicHelper:
    def test_strips_underscore_keys(self):
        scan = {"id": "abc", "status": "scanning", "_stop": "private", "_thread": "hidden"}
        result = _public(scan)
        assert "_stop" not in result
        assert "_thread" not in result

    def test_preserves_public_keys(self):
        scan = {"id": "abc", "status": "scanning", "_stop": object()}
        result = _public(scan)
        assert result["id"] == "abc"
        assert result["status"] == "scanning"


class TestListScans:
    def test_empty_list_initially(self, client):
        resp = client.get("/scans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_scans(self, client):
        stop = threading.Event()
        _scans["a1"] = {"id": "a1", "status": "scanning", "_stop": stop, "log": []}
        _scans["a2"] = {"id": "a2", "status": "booked", "_stop": stop, "log": []}
        resp = client.get("/scans")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert ids == {"a1", "a2"}

    def test_private_keys_not_in_response(self, client):
        stop = threading.Event()
        _scans["b1"] = {"id": "b1", "status": "scanning", "_stop": stop, "log": []}
        data = client.get("/scans").json()
        assert all("_stop" not in s for s in data)


class TestGetScan:
    def test_404_for_unknown_id(self, client):
        assert client.get("/scans/nonexistent").status_code == 404

    def test_returns_scan_by_id(self, client):
        stop = threading.Event()
        _scans["c1"] = {"id": "c1", "status": "scanning", "_stop": stop, "log": []}
        resp = client.get("/scans/c1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "c1"

    def test_private_keys_not_in_response(self, client):
        stop = threading.Event()
        _scans["c2"] = {"id": "c2", "status": "scanning", "_stop": stop, "log": []}
        resp = client.get("/scans/c2")
        assert "_stop" not in resp.json()


class TestCreateScan:
    def test_400_when_env_vars_missing(self, client):
        with patch.dict(os.environ, {"GOLF_EMAIL": "", "GOLF_PASSWORD": ""}):
            resp = client.post("/scans", json={
                "date": "2026-06-15",
                "time_from": "08:00",
                "time_to": "10:00",
                "players": 4,
                "site": "kananaskis",
            })
        assert resp.status_code == 400

    def test_creates_scan_and_starts_thread(self, client):
        with patch.dict(os.environ, {"GOLF_EMAIL": "t@test.com", "GOLF_PASSWORD": "pass"}):
            with patch("server.threading.Thread") as mock_thread:
                mock_thread.return_value.start.return_value = None
                resp = client.post("/scans", json={
                    "date": "2026-06-15",
                    "time_from": "08:00",
                    "time_to": "10:00",
                    "players": 4,
                    "site": "kananaskis",
                })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scanning"
        assert data["date"] == "2026-06-15"
        assert data["players"] == 4
        assert "_stop" not in data
        mock_thread.return_value.start.assert_called_once()

    def test_created_scan_appears_in_list(self, client):
        with patch.dict(os.environ, {"GOLF_EMAIL": "t@test.com", "GOLF_PASSWORD": "pass"}):
            with patch("server.threading.Thread") as mock_thread:
                mock_thread.return_value.start.return_value = None
                client.post("/scans", json={
                    "date": "2026-06-15",
                    "time_from": "08:00",
                    "time_to": "10:00",
                    "players": 4,
                    "site": "kananaskis",
                })
        assert len(client.get("/scans").json()) == 1

    def test_vr_site_uses_vr_env_vars(self, client):
        with patch.dict(os.environ, {"VR_GOLF_EMAIL": "", "VR_GOLF_PASSWORD": ""}):
            resp = client.post("/scans", json={
                "date": "2026-06-15",
                "time_from": "08:00",
                "time_to": "10:00",
                "players": 4,
                "site": "valley_ridge",
            })
        assert resp.status_code == 400

    def test_unknown_site_falls_back_to_kananaskis(self, client):
        # Unknown site keys fall back to KANANASKIS in _run_scan; env var check uses KANANASKIS vars
        with patch.dict(os.environ, {"GOLF_EMAIL": "", "GOLF_PASSWORD": ""}):
            resp = client.post("/scans", json={
                "date": "2026-06-15",
                "time_from": "08:00",
                "time_to": "10:00",
                "players": 4,
                "site": "unknown_site",
            })
        assert resp.status_code == 400


class TestCancelScan:
    def test_404_for_unknown_id(self, client):
        assert client.delete("/scans/nonexistent").status_code == 404

    def test_cancels_scanning_scan(self, client):
        stop = threading.Event()
        _scans["d1"] = {"id": "d1", "status": "scanning", "_stop": stop, "log": []}
        resp = client.delete("/scans/d1")
        assert resp.status_code == 200
        assert stop.is_set()

    def test_cancels_found_scan(self, client):
        stop = threading.Event()
        _scans["d2"] = {"id": "d2", "status": "found", "_stop": stop, "log": []}
        resp = client.delete("/scans/d2")
        assert resp.status_code == 200
        assert stop.is_set()

    def test_400_for_already_booked_scan(self, client):
        stop = threading.Event()
        _scans["d3"] = {"id": "d3", "status": "booked", "_stop": stop, "log": []}
        assert client.delete("/scans/d3").status_code == 400

    def test_400_for_cancelled_scan(self, client):
        stop = threading.Event()
        _scans["d4"] = {"id": "d4", "status": "cancelled", "_stop": stop, "log": []}
        assert client.delete("/scans/d4").status_code == 400


def _make_scan(scan_id, stop):
    return {
        "date": "2026-06-15",
        "time_from": "08:00",
        "time_to": "10:00",
        "players": 4,
        "interval": 300,
        "courses": [],
        "log": [],
        "_stop": stop,
        "status": "scanning",
    }


class TestLogHelper:
    def test_appends_timestamped_message(self):
        _scans["log-t"] = {"log": []}
        _log("log-t", "hello world")
        assert len(_scans["log-t"]["log"]) == 1
        assert "hello world" in _scans["log-t"]["log"][0]


class TestRunScanVR:
    def test_cancelled_immediately(self):
        from server import _run_scan_vr
        stop = threading.Event()
        stop.set()
        _scans["vr-c"] = _make_scan("vr-c", stop)
        _run_scan_vr("vr-c", "u@test.com", "pass")
        assert _scans["vr-c"]["status"] == "cancelled"

    @patch("server.search_tee_times_vr", return_value=[])
    def test_no_slots_logs_and_cancels(self, mock_search):
        from server import _run_scan_vr
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["vr-ns"] = _make_scan("vr-ns", stop)
        _run_scan_vr("vr-ns", "u@test.com", "pass")
        assert _scans["vr-ns"]["status"] == "cancelled"
        mock_search.assert_called_once()

    @patch("server.notify")
    @patch("server.slot_summary_vr", return_value="09:00 Valley Ridge")
    @patch("server.book_slot_vr", return_value=(True, "Booked: 09:00"))
    @patch("server.login_vr")
    @patch("server.search_tee_times_vr", return_value=[{"id": 1}])
    def test_books_successfully(self, mock_search, mock_login, mock_book, mock_summary, mock_notify):
        from server import _run_scan_vr
        mock_session = MagicMock()
        mock_login.return_value = mock_session
        stop = MagicMock()
        stop.is_set.return_value = False
        stop.wait = MagicMock()
        _scans["vr-ok"] = _make_scan("vr-ok", stop)
        _run_scan_vr("vr-ok", "u@test.com", "pass")
        assert _scans["vr-ok"]["status"] == "booked"
        mock_session.close.assert_called_once()

    @patch("server.notify")
    @patch("server.slot_summary_vr", return_value="09:00")
    @patch("server.book_slot_vr", return_value=(False, "conflict"))
    @patch("server.login_vr")
    @patch("server.search_tee_times_vr", return_value=[{"id": 1}])
    def test_booking_fails_then_cancels(self, mock_search, mock_login, mock_book, mock_summary, mock_notify):
        from server import _run_scan_vr
        mock_login.return_value = MagicMock()
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["vr-bf"] = _make_scan("vr-bf", stop)
        _run_scan_vr("vr-bf", "u@test.com", "pass")
        assert _scans["vr-bf"]["status"] == "cancelled"

    @patch("server.search_tee_times_vr", side_effect=Exception("network error"))
    def test_exception_is_caught_and_cancels(self, mock_search):
        from server import _run_scan_vr
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["vr-ex"] = _make_scan("vr-ex", stop)
        _run_scan_vr("vr-ex", "u@test.com", "pass")
        assert _scans["vr-ex"]["status"] == "cancelled"
        assert any("Error" in e for e in _scans["vr-ex"]["log"])


class TestRunScan:
    def test_cancelled_immediately(self):
        from server import _run_scan
        stop = threading.Event()
        stop.set()
        _scans["cps-c"] = _make_scan("cps-c", stop)
        _run_scan("cps-c", "u@test.com", "pass", "kananaskis")
        assert _scans["cps-c"]["status"] == "cancelled"

    @patch("server.search_tee_times", return_value=([], ""))
    @patch("server.find_matching_slots", return_value=[])
    @patch("server.login")
    def test_no_matches_then_cancels(self, mock_login, mock_matches, mock_search):
        from server import _run_scan
        mock_session = MagicMock()
        mock_session.is_expired.return_value = False
        mock_login.return_value = mock_session
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["cps-nm"] = _make_scan("cps-nm", stop)
        _run_scan("cps-nm", "u@test.com", "pass", "kananaskis")
        assert _scans["cps-nm"]["status"] == "cancelled"

    @patch("server.notify")
    @patch("server.slot_summary", return_value="09:00 Mt Lorette")
    @patch("server.book_slot", return_value=(True, "Booked: 09:00"))
    @patch("server.find_matching_slots", return_value=[{"teeSheetId": 1}])
    @patch("server.search_tee_times", return_value=([{"teeSheetId": 1}], ""))
    @patch("server.login")
    def test_books_successfully(self, mock_login, mock_search, mock_matches, mock_book, mock_summary, mock_notify):
        from server import _run_scan
        mock_session = MagicMock()
        mock_session.is_expired.return_value = False
        mock_login.return_value = mock_session
        stop = MagicMock()
        stop.is_set.return_value = False
        stop.wait = MagicMock()
        _scans["cps-ok"] = _make_scan("cps-ok", stop)
        _run_scan("cps-ok", "u@test.com", "pass", "kananaskis")
        assert _scans["cps-ok"]["status"] == "booked"
        mock_session.close.assert_called_once()

    @patch("server.notify")
    @patch("server.slot_summary", return_value="09:00")
    @patch("server.book_slot", return_value=(False, "taken"))
    @patch("server.find_matching_slots", return_value=[{"teeSheetId": 1}])
    @patch("server.search_tee_times", return_value=([{"teeSheetId": 1}], ""))
    @patch("server.login")
    def test_booking_fails_then_cancels(self, mock_login, mock_search, mock_matches, mock_book, mock_summary, mock_notify):
        from server import _run_scan
        mock_session = MagicMock()
        mock_session.is_expired.return_value = False
        mock_login.return_value = mock_session
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["cps-bf"] = _make_scan("cps-bf", stop)
        _run_scan("cps-bf", "u@test.com", "pass", "kananaskis")
        assert _scans["cps-bf"]["status"] == "cancelled"

    @patch("server.login", side_effect=Exception("auth failed"))
    def test_exception_is_caught_and_cancels(self, mock_login):
        from server import _run_scan
        stop = MagicMock()
        stop.is_set.side_effect = [False, True]
        stop.wait = MagicMock()
        _scans["cps-ex"] = _make_scan("cps-ex", stop)
        _run_scan("cps-ex", "u@test.com", "pass", "kananaskis")
        assert _scans["cps-ex"]["status"] == "cancelled"
        assert any("Error" in e for e in _scans["cps-ex"]["log"])


class TestCreateScanVRPath:
    def test_creates_vr_scan_for_valley_ridge_site(self, client=None):
        if client is None:
            client = TestClient(app)
        with patch.dict(os.environ, {"VR_GOLF_EMAIL": "vr@test.com", "VR_GOLF_PASSWORD": "pass"}):
            with patch("server.threading.Thread") as mock_thread:
                mock_thread.return_value.start.return_value = None
                resp = client.post("/scans", json={
                    "date": "2026-06-15",
                    "time_from": "08:00",
                    "time_to": "10:00",
                    "players": 4,
                    "site": "valley_ridge",
                })
        assert resp.status_code == 201
        call_kwargs = mock_thread.call_args[1]
        assert call_kwargs["target"].__name__ == "_run_scan_vr"

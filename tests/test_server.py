import os
import threading
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from server import app, _scans, _hour, _public


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

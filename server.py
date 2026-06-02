"""
FastAPI server — wraps mackbot's scanner/booker for the web UI.

Run:
    uvicorn server:app --reload

Then open http://localhost:5173 (Vite dev server) or run `npm run build`
and point your browser at http://localhost:8000 if the frontend/dist exists.
"""

import os
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cps.auth import Session, login
from cps.api import search_tee_times
from cps.booker import book_slot
from config import BookingConfig, SITES, KANANASKIS
from notifier import notify
from cps.scanner import find_matching_slots, slot_summary
from courses.valley_ridge.api import search_tee_times_vr
from courses.valley_ridge.auth import VRSession, login_vr
from courses.valley_ridge.booker import book_slot_vr, slot_summary_vr

load_dotenv()

app = FastAPI(title="mackbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory scan registry. Keys starting with "_" are stripped from API responses.
_scans: dict[str, dict] = {}


class CreateScanRequest(BaseModel):
    date: str
    time_from: str
    time_to: str
    players: int = 4
    courses: list[int] = []
    interval: int = 300
    site: str = "kananaskis"


def _hour(t: str) -> float:
    h, m = t.split(":")
    return int(h) + int(m) / 60


def _log(scan_id: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    _scans[scan_id]["log"].append(f"[{ts}] {msg}")


def _run_scan_vr(scan_id: str, email: str, password: str) -> None:
    scan = _scans[scan_id]
    stop: threading.Event = scan["_stop"]
    time_min = _hour(scan["time_from"])
    time_max = _hour(scan["time_to"])
    num_players = scan["players"]
    target_date = date.fromisoformat(scan["date"])
    poll_interval = scan["interval"]

    session: VRSession | None = None

    while not stop.is_set():
        try:
            slots = search_tee_times_vr(target_date, num_players, time_min, time_max)

            if slots:
                best = slots[0]
                _log(scan_id, f"{len(slots)} slot(s) found — booking {slot_summary_vr(best)}")
                scan["status"] = "found"
                notify("Tee time found!", f"{slot_summary_vr(best)} — booking now")

                if not session:
                    _log(scan_id, "Authenticating…")
                    session = login_vr(email, password)

                ok, msg = book_slot_vr(session, best, num_players)
                if ok:
                    _log(scan_id, msg)
                    scan["status"] = "booked"
                    notify("Tee time booked!", slot_summary_vr(best))
                    session.close()
                    return
                else:
                    _log(scan_id, f"Booking failed: {msg}")
                    scan["status"] = "scanning"
                    if session:
                        session.close()
                    session = None
            else:
                _log(scan_id, f"No matches. Next in {poll_interval}s.")

        except Exception as exc:
            _log(scan_id, f"Error: {exc}")
            if session:
                session.close()
            session = None

        stop.wait(poll_interval)

    scan["status"] = "cancelled"
    _log(scan_id, "Scan cancelled.")
    if session:
        session.close()


def _run_scan(scan_id: str, email: str, password: str, site_key: str) -> None:
    scan = _scans[scan_id]
    stop: threading.Event = scan["_stop"]
    site = SITES.get(site_key, KANANASKIS)
    cfg = BookingConfig(
        target_date=date.fromisoformat(scan["date"]),
        site=site,
        time_min_hour=_hour(scan["time_from"]),
        time_max_hour=_hour(scan["time_to"]),
        num_players=scan["players"],
        course_ids=scan["courses"] or list(site.course_ids),
        poll_interval_secs=scan["interval"],
    )

    session: Session | None = None

    while not stop.is_set():
        try:
            if not session:
                _log(scan_id, "Authenticating…")
                session = login(email, password, site)
            elif session.is_expired():
                _log(scan_id, "Token expired — refreshing in existing browser…")
                session.refresh(email, password)

            slots, _ = search_tee_times(
                session, cfg.target_date, cfg.num_players,
                cfg.time_min_hour, cfg.time_max_hour,
                course_ids=cfg.course_ids,
            )
            matches = find_matching_slots(slots, cfg)

            if matches:
                best = matches[0]
                _log(scan_id, f"{len(matches)} slot(s) found — booking {slot_summary(best)}")
                scan["status"] = "found"
                notify("Tee time found!", f"{slot_summary(best)} — booking now")

                ok, msg = book_slot(session, best, cfg.num_players, email)
                if ok:
                    _log(scan_id, msg)
                    scan["status"] = "booked"
                    notify("Tee time booked!", slot_summary(best))
                    session.close()
                    return
                else:
                    _log(scan_id, f"Booking failed: {msg}")
                    scan["status"] = "scanning"
            else:
                _log(
                    scan_id,
                    f"No matches ({len(slots)} slots checked). Next in {cfg.poll_interval_secs}s.",
                )

        except Exception as exc:
            _log(scan_id, f"Error: {exc}")
            if session:
                session.close()
            session = None

        stop.wait(cfg.poll_interval_secs)

    scan["status"] = "cancelled"
    _log(scan_id, "Scan cancelled.")
    if session:
        session.close()


def _public(scan: dict) -> dict:
    return {k: v for k, v in scan.items() if not k.startswith("_")}


@app.post("/scans", status_code=201)
def create_scan(req: CreateScanRequest) -> dict:
    site = SITES.get(req.site, KANANASKIS)
    email = os.environ.get(site.email_env)
    password = os.environ.get(site.password_env)
    if not email or not password:
        raise HTTPException(400, f"{site.email_env} and {site.password_env} must be set in .env")

    scan_id = str(uuid.uuid4())[:8]
    stop = threading.Event()

    _scans[scan_id] = {
        "id": scan_id,
        "site": req.site,
        "date": req.date,
        "time_from": req.time_from,
        "time_to": req.time_to,
        "players": req.players,
        "courses": req.courses,
        "interval": req.interval,
        "status": "scanning",
        "log": [],
        "created_at": datetime.now().isoformat(),
        "_stop": stop,
    }

    if site.platform == "tcu":
        target_fn = _run_scan_vr
        thread_args = (scan_id, email, password)
    else:
        target_fn = _run_scan
        thread_args = (scan_id, email, password, req.site)

    threading.Thread(target=target_fn, args=thread_args, daemon=True).start()

    return _public(_scans[scan_id])


@app.get("/scans")
def list_scans() -> list[dict]:
    return [_public(s) for s in _scans.values()]


@app.get("/scans/{scan_id}")
def get_scan(scan_id: str) -> dict:
    if scan_id not in _scans:
        raise HTTPException(404, "Scan not found")
    return _public(_scans[scan_id])


@app.delete("/scans/{scan_id}")
def cancel_scan(scan_id: str) -> dict:
    if scan_id not in _scans:
        raise HTTPException(404, "Scan not found")
    if _scans[scan_id]["status"] not in ("scanning", "found"):
        raise HTTPException(400, "Scan is not active")
    _scans[scan_id]["_stop"].set()
    return {"ok": True}


# Serve the built frontend if present (npm run build → frontend/dist)
_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")

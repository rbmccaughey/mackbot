"""
mackbot — tee time scanner and booker for Kananaskis (CPS Golf)

Usage:
    python main.py --date 2026-05-30 --from 08:00 --to 10:00 --players 4
    python main.py --date 2026-05-30  # uses defaults from .env / config

Stops automatically after a successful booking.
"""

import argparse
import os
import sys
import time
from datetime import date, datetime

from dotenv import load_dotenv

from auth import Session, login
from booker import book_slot
from config import BookingConfig
from api import search_tee_times
from notifier import notify
from scanner import find_matching_slots, slot_summary

load_dotenv()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan for and book a Kananaskis tee time")
    p.add_argument("--date", required=True, help="Target date (YYYY-MM-DD)")
    p.add_argument("--from", dest="time_from", default="08:00", help="Earliest tee time (HH:MM)")
    p.add_argument("--to", dest="time_to", default="10:00", help="Latest tee time (HH:MM)")
    p.add_argument("--players", type=int, default=4, help="Number of players (default: 4)")
    p.add_argument("--interval", type=int, default=300, help="Poll interval in seconds (default: 300)")
    p.add_argument("--courses", default="", help="Comma-separated course IDs to filter (1=Mt Lorette, 2=Mt Kidd). Empty = any.")
    return p.parse_args()


def _hour(t: str) -> float:
    h, m = t.split(":")
    return int(h) + int(m) / 60


def get_session(email: str, password: str, current: Session | None) -> Session:
    if current and not current.is_expired():
        return current
    print("Authenticating...")
    return login(email, password)


def main() -> None:
    args = parse_args()

    email = os.environ.get("GOLF_EMAIL")
    password = os.environ.get("GOLF_PASSWORD")
    if not email or not password:
        sys.exit("Set GOLF_EMAIL and GOLF_PASSWORD in .env")

    target_date = date.fromisoformat(args.date)
    course_ids = [int(x) for x in args.courses.split(",") if x.strip()] if args.courses else [1, 2]

    cfg = BookingConfig(
        target_date=target_date,
        time_min_hour=_hour(args.time_from),
        time_max_hour=_hour(args.time_to),
        num_players=args.players,
        course_ids=course_ids,
        poll_interval_secs=args.interval,
    )

    print(
        f"Scanning for {cfg.num_players} players on {target_date} "
        f"between {args.time_from} and {args.time_to} "
        f"(checking every {cfg.poll_interval_secs}s)"
    )

    session: Session | None = None
    attempt = 0

    while True:
        attempt += 1
        try:
            session = get_session(email, password, session)

            slots = search_tee_times(
                session,
                cfg.target_date,
                cfg.num_players,
                cfg.time_min_hour,
                cfg.time_max_hour,
            )

            matches = find_matching_slots(slots, cfg)
            now = datetime.now().strftime("%H:%M:%S")

            if matches:
                print(f"\n[{now}] {len(matches)} slot(s) found!")
                for m in matches:
                    print(f"  {slot_summary(m)}")

                best = matches[0]
                notify(
                    "Tee time found!",
                    f"{slot_summary(best)} — booking now",
                )

                if book_slot(session, best, cfg.num_players, email):
                    notify("Tee time booked!", slot_summary(best))
                    print("\nBooking confirmed. Check your email for confirmation. Exiting.")
                    sys.exit(0)
                else:
                    print("Booking failed — will retry next poll.")
            else:
                print(f"[{now}] No matching slots (checked {len(slots)} total). Next check in {cfg.poll_interval_secs}s.")

        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)
        except Exception as e:
            print(f"Error on attempt {attempt}: {e}")
            session = None  # force re-auth on next loop

        time.sleep(cfg.poll_interval_secs)


if __name__ == "__main__":
    main()

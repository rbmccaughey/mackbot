"""
mackbot — tee time scanner and booker for CPS Golf sites

Usage:
    python main.py --date 2026-05-30 --from 08:00 --to 10:00 --players 4
    python main.py --date 2026-05-30 --site calgary --courses 3

Stops automatically after a successful booking.
"""

import argparse
import os
import sys
import time
from datetime import date, datetime

from dotenv import load_dotenv

from cps.auth import Session, login
from cps.booker import book_slot
from config import BookingConfig, SITES, KANANASKIS
from cps.api import search_tee_times
from notifier import notify
from cps.scanner import find_matching_slots, slot_summary

load_dotenv()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan for and book a CPS Golf tee time")
    p.add_argument("--date", required=True, help="Target date (YYYY-MM-DD)")
    p.add_argument("--from", dest="time_from", default="08:00", help="Earliest tee time (HH:MM)")
    p.add_argument("--to", dest="time_to", default="10:00", help="Latest tee time (HH:MM)")
    p.add_argument("--players", type=int, default=4, help="Number of players (default: 4)")
    p.add_argument("--interval", type=int, default=300, help="Poll interval in seconds (default: 300)")
    p.add_argument("--courses", default="", help="Comma-separated course IDs to filter. Empty = all for site.")
    p.add_argument("--site", default="kananaskis", choices=list(SITES.keys()), help="Site to book (default: kananaskis)")
    return p.parse_args()


def _hour(t: str) -> float:
    h, m = t.split(":")
    return int(h) + int(m) / 60


def get_session(email: str, password: str, site, current: Session | None) -> Session:
    if current and not current.is_expired():
        return current
    if current and current.is_expired():
        print("Token expired — refreshing in existing browser...")
        if current.refresh(email, password):
            return current
        print("Refresh failed — closing and re-authenticating from scratch...")
        current.close()
    print("Authenticating...")
    return login(email, password, site)


def main() -> None:
    args = parse_args()
    site = SITES[args.site]

    email = os.environ.get(site.email_env)
    password = os.environ.get(site.password_env)
    if not email or not password:
        sys.exit(f"Set {site.email_env} and {site.password_env} in .env")

    target_date = date.fromisoformat(args.date)
    course_ids = [int(x) for x in args.courses.split(",") if x.strip()] if args.courses else []

    cfg = BookingConfig(
        target_date=target_date,
        site=site,
        time_min_hour=_hour(args.time_from),
        time_max_hour=_hour(args.time_to),
        num_players=args.players,
        course_ids=course_ids,
        poll_interval_secs=args.interval,
    )

    print(
        f"Scanning {site.name} for {cfg.num_players} players on {target_date} "
        f"between {args.time_from} and {args.time_to} "
        f"(checking every {cfg.poll_interval_secs}s)"
    )

    session: Session | None = None
    attempt = 0

    while True:
        attempt += 1
        try:
            session = get_session(email, password, site, session)

            slots, _ = search_tee_times(
                session,
                cfg.target_date,
                cfg.num_players,
                cfg.time_min_hour,
                cfg.time_max_hour,
                course_ids=cfg.course_ids,
            )

            matches = find_matching_slots(slots, cfg)
            now = datetime.now().strftime("%H:%M:%S")

            if matches:
                print(f"\n[{now}] {len(matches)} slot(s) found!")
                for m in matches:
                    print(f"  {slot_summary(m)}")

                best = matches[0]
                notify("Tee time found!", f"{slot_summary(best)} — booking now")

                ok, msg = book_slot(session, best, cfg.num_players, email)
                if ok:
                    notify("Tee time booked!", slot_summary(best))
                    print(f"\n{msg}. Check your email for confirmation. Exiting.")
                    sys.exit(0)
                else:
                    print(f"Booking failed: {msg} — will retry next poll.")
            else:
                print(f"[{now}] No matching slots (checked {len(slots)} total). Next check in {cfg.poll_interval_secs}s.")

        except KeyboardInterrupt:
            if session:
                session.close()
            print("\nStopped.")
            sys.exit(0)
        except Exception as e:
            print(f"Error on attempt {attempt}: {e}")
            if session:
                session.close()
            session = None  # force re-auth on next loop

        time.sleep(cfg.poll_interval_secs)


if __name__ == "__main__":
    main()

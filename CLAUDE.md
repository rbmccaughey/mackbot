# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

mackbot is a personal tee time scanner and booker for Kananaskis Golf (kananaskisabresidents.cps.golf). It polls the CPS Golf API for available tee times matching a date/time/player-count criteria and fully books the first match — including payment via card on file.

## Setup and running

```bash
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Fill in GOLF_EMAIL and GOLF_PASSWORD
```

**Web UI (preferred):**
```bash
# Terminal 1 — FastAPI backend
uvicorn server:app --reload

# Terminal 2 — Vite dev server
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

**CLI (alternative):**
```bash
python main.py --date 2026-05-30 --from 08:00 --to 10:00 --players 4
# Optional flags:
#   --interval 300     poll interval in seconds (default 300)
#   --courses 1,2      filter by course ID: 1=Mt Lorette, 2=Mt Kidd (default: both)
```

On first run a visible Chrome window opens for login (required to pass Cloudflare). Subsequent polls use httpx with the saved session cookies.

## Architecture

```
server.py     FastAPI server. Wraps scanner/booker — each scan runs as a daemon thread.
main.py       CLI entry point. Parses args, drives the poll loop, handles re-auth on token expiry.
auth.py       Playwright login → extracts JWT from localStorage + Cloudflare cookies → Session.
api.py        httpx API client. All endpoints live here; each call adds a fresh x-requestid UUID.
scanner.py    Pure filtering logic. find_matching_slots() is the core match check.
booker.py     Runs the full booking chain on a matched slot.
notifier.py   macOS desktop notification via osascript.
config.py     BookingConfig dataclass + static request headers + API base URL constants.
frontend/     Vite + React + TypeScript + Tailwind. Polls GET /scans every 3s for live updates.
```

## Web server API

| Method | Path | Description |
|---|---|---|
| `POST` | `/scans` | Start a new scan (returns scan object) |
| `GET` | `/scans` | List all scans |
| `GET` | `/scans/{id}` | Get one scan |
| `DELETE` | `/scans/{id}` | Cancel an active scan |

Scans are in-memory only — they are lost on server restart. Each scan's `log` field is a list of timestamped strings updated by the background thread.

## Authentication

The site uses **IdentityServer OIDC** + **Cloudflare**. Direct HTTP requests return 403. The auth flow:

1. Playwright launches a visible Chrome window (`headless=False`) to pass Cloudflare
2. Visits root domain first to obtain `cf_clearance`, then navigates to `/onlineresweb/auth/verify-email`
3. Two-step login: email first, then password on next page
4. Extracts the JWT from localStorage keys: `online-reservation-v5-access_token` and `online-reservation-v5-expires_at`
5. Saves `cf_clearance` and other cookies for reuse in httpx calls
6. JWT lasts **1 hour** — `Session.is_expired()` triggers re-auth automatically; the browser reopens

User identity (`golfer_id`, `acct`) is parsed from the JWT claims on every login, not hardcoded.

## Booking flow

`booker.py` uses a hybrid browser + API approach:

1. `CheckBookingLimit` — fast-fail if the account has hit a reservation cap
2. `LockTeeTimes` — lock the slot (called before navigating to checkout, matching the real browser flow where the SPA calls this from the search page)
3. `page.goto(checkout_url)` — park the Playwright browser on `/teetime/checkout?id=...` so all subsequent `fetch()` calls carry the correct `Referer` header
4. `TeeTimePricesCalculation` — server creates a pricing session and returns a `transactionId` (used as `bookingTransactionId` in ReserveTeeTimes)
5. `CheckRestrictReservation` — restriction check
6. `GetAllCreditCardOnFile` — fetch Moneris card-on-file token
7. `RegisterTransactionId` — register a fresh UUID; this UUID becomes `transactionId` in ReserveTeeTimes
8. `ReserveTeeTimes` — final confirmation; card on file is charged server-side

**Critical UUID mapping** (field names are counterintuitive):
- `ReserveTeeTimes.transactionId` = fresh UUID from `RegisterTransactionId`
- `ReserveTeeTimes.bookingTransactionId` = UUID returned by `TeeTimePricesCalculation`

## Key API endpoints

All under `https://kananaskisabresidents.cps.golf/onlineres/onlineapi/api/v1/onlinereservation/`

| Endpoint | Method | Called by |
|---|---|---|
| `TeeTimes` | GET | `api.search_tee_times` |
| `CheckBookingLimit` | POST | `api.check_booking_limit` |
| `LockTeeTimes` | POST | `api.lock_tee_time` |
| `RegisterTransactionId` | POST | `api.register_transaction_id` |
| `ReserveTeeTimes` | POST | `api.reserve_tee_times` |

## Slot availability detection

A slot from `TeeTimes` is considered bookable when all of these hold:
- `startTime` falls within the configured `[time_min_hour, time_max_hour)` window
- desired `num_players` appears in `availableParticipantNo`
- `courseId` matches `config.course_ids` (if filtered)

## Site constants

- `classCode`: `ABRES` (Alberta residents rate)
- `memberStoreId`: `2`
- `x-websiteid`: `ed189e3e-c873-4785-6262-08d8fddc05d5`
- Course IDs: `1` = Mt Lorette, `2` = Mt Kidd

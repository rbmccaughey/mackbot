# mackbot — Handoff Document

## What it does

mackbot polls CPS Golf (Club Prophet Systems) booking sites for available tee times matching a date, time window, player count, and course filter. When a matching slot is found, it books it end-to-end — locking the time, running the pricing chain, and confirming the reservation. Payment is only charged for Kananaskis (deposit via Moneris card on file); Calgary bookings are free at booking time.

**Supported sites:**
- **Kananaskis** — `kananaskisabresidents.cps.golf` — Mt Lorette (1), Mt Kidd (2) — $35/player deposit
- **Calgary** — `cityofcalgarygolf.cps.golf` — 10 courses (see below) — no deposit

---

## Running it

```bash
# One-time setup
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in credentials

# Web UI (preferred)
uvicorn server:app --reload          # terminal 1
cd frontend && npm run dev           # terminal 2
# open http://localhost:5173

# CLI
python main.py --date 2026-06-15 --from 08:00 --to 10:00 --players 4
python main.py --date 2026-06-15 --site calgary --courses 3,4
```

**Credentials in `.env`:**
```
GOLF_EMAIL=...            # Kananaskis account
GOLF_PASSWORD=...
CALGARY_GOLF_EMAIL=...    # Calgary account
CALGARY_GOLF_PASSWORD=...
```

---

## Architecture

```
config.py     SiteConfig dataclass — all site-specific constants live here.
              KANANASKIS and CALGARY instances. BookingConfig references a SiteConfig.
auth.py       Playwright login → JWT extraction → Session dataclass.
              Session.refresh() handles token renewal in the existing browser.
api.py        All HTTP calls via page.evaluate(fetch(...)). Headers built dynamically
              from session.site. _api_base() returns the right URL per site.
scanner.py    Pure filtering logic. No side effects.
booker.py     Full booking chain. Uses session.site for deposit/payment behaviour.
server.py     FastAPI. Each scan is a daemon thread. In-memory only (lost on restart).
main.py       CLI entry point.
notifier.py   macOS desktop notification via osascript.
frontend/     Vite + React + TypeScript + Tailwind. Polls GET /scans every 3s.
```

---

## The booking chain (critical)

This is the most important thing to understand. The chain must run in this exact order:

1. `CheckBookingLimit` — fast-fail if account is at reservation cap
2. `LockTeeTimes` → returns `sessionId` (= `lockedTeeTimesSessionId` in step 8)
3. `page.goto(checkout_url)` — park the browser on checkout so subsequent `fetch()` calls carry the correct `Referer` header
4. `TeeTimePricesCalculation` → returns `transactionId` (= `bookingTransactionId` in step 8)
5. `CheckRestrictReservation`
6. `GetAllCreditCardOnFile` — **Kananaskis only** (skipped for Calgary)
7. `RegisterTransactionId` → returns a fresh UUID (= `transactionId` in step 8)
8. `ReserveTeeTimes`

### Critical UUID mapping

The field names in `ReserveTeeTimes` are counterintuitive and were the root cause of a multi-session debugging effort:

| ReserveTeeTimes field | Value comes from |
|---|---|
| `transactionId` | Fresh UUID from **RegisterTransactionId** (step 7) |
| `bookingTransactionId` | UUID returned by **TeeTimePricesCalculation** (step 4) |

These are the opposite of what the names suggest. Swapping them causes HTTP 400 "Current online booking transaction is invalid."

---

## Authentication and token refresh

The site uses IdentityServer OIDC + Cloudflare. All API calls run inside the Playwright browser via `page.evaluate(fetch(...))` so Cloudflare cookies and auth context are handled natively.

**JWT lifetime:** 1 hour.

**Token refresh** (`Session.refresh()`): when the token is about to expire, the scanner tries to renew it in the **existing browser** — never opening a new window. Three-stage fallback:

1. Check if the SPA already silently refreshed (oidc-client runs background refresh)
2. Navigate to `verify-email` — IdentityServer SSO usually auto-issues a new JWT since the IS session outlasts the JWT
3. If IS session also expired, fill credentials in the existing browser

**Known issue with step 2:** The Angular router sometimes redirects to the registration page instead of the verify-email login form when navigating mid-session. `_navigate_to_verify_email()` detects this by polling the URL and re-navigates if it lands on any `/auth/` page that isn't `verify-email`. If it still can't land on the right page after 10 seconds, `refresh()` returns `False` and the scan logs a warning. This has not yet been observed succeeding in a full one-hour test — it needs another real-world run to confirm it works.

**If refresh fails:** the scan logs the failure and continues with the existing session object. The next API call will fail with 401, the exception handler will log it, and the following poll cycle will try `refresh()` again. A new browser is never opened mid-scan.

---

## Calgary — site-specific notes

Calgary has 10 courses across 5 physical sites. Each course has its own `siteId` which must be sent in the `CheckRestrictReservation` payload. The `siteId` is embedded in every slot returned by the TeeTimes search, so `booker.py` reads `slot.get("siteId")` rather than using a static config value.

| courseId | Name | Holes | siteId |
|---|---|---|---|
| 1 | Confederation Park | 9 | 2 |
| 2 | Lakeview | 9 | 3 |
| 3 | Maple Ridge | 18 | 4 |
| 4 | McCall Lake | 18 | 5 |
| 5 | Shaganappi | 18 | 6 |
| 6 | Valley 9 | 9 | 6 |
| 7 | McCall Par 3 | 9 | 5 |
| 8 | Shaganappi Back 9 | 9 | 6 |
| 11 | Maple Ridge Back 9 | 9 | 4 |
| 12 | McCall Back 9 | 9 | 5 |

Calgary auto-login (`login()`) did not work during initial testing — had to log in manually. The login selectors are the same as Kananaskis but timing or Cloudflare behaviour may differ. Not yet debugged.

---

## How site config works

Everything site-specific lives in `config.py`:

```python
@dataclass
class SiteConfig:
    name: str
    base_url: str
    website_id: str       # x-websiteid header
    header_site_id: str   # x-siteid header
    payload_site_id: int  # siteId in CheckRestrictReservation (Kananaskis fallback;
                          # Calgary uses per-slot siteId from search results)
    class_code: str       # ABRES (Kananaskis) or ADGF (Calgary)
    member_store_id: int
    course_ids: list[int] # all courses on this site
    email_env: str        # name of env var for login email
    password_env: str     # name of env var for login password
    requires_payment: bool
    deposit_amount: int   # per player, dollars
```

To add a third CPS Golf site: add a new `SiteConfig` instance in `config.py`, add it to `SITES`, add its courses to the frontend `SITES` object in `CreateScanForm.tsx`, and add its credentials to `.env`.

---

## Known issues and open work

| Issue | Status |
|---|---|
| Token refresh → registration page redirect | Mitigated (URL polling + re-nav), not yet confirmed fixed in production |
| Calgary auto-login fails | Not debugged — requires manual login on first run |
| Calgary course IDs only partially confirmed | courseId 3 (Maple Ridge) confirmed via HAR; others sourced from the site's course config API but not tested |
| Single-instance only | Scans are in-memory; server restart loses all scans |
| No persistence | Intended for personal use; would need a DB for multi-user/shared deployment |
| Share with friends | Discussed: Docker+Xvfb, Electron, or a setup.sh approach. Not implemented. headless=False is the main obstacle for Docker. |

---

## Debugging tools

**`debug_intercept.py`** — HAR capture for Kananaskis. Opens a browser, lets you manually book, captures all booking API calls (request + response bodies) on Ctrl+C. Use this whenever a new HTTP 400/401 appears and you don't know why — response bodies give ground truth that request payloads alone can't.

**`debug_intercept_calgary.py`** — same thing for Calgary.

HAR response bodies are stored as hash-named files in `/tmp/` alongside the `.har` file when using `record_har_content="attach"`. The scripts resolve these automatically.

---

## How the debugging was done (context for future issues)

The booking chain took multiple sessions to get working. Every fix was wrong until we used HAR recording to capture a real successful booking from the browser. The HAR immediately showed that `transactionId` and `bookingTransactionId` were swapped. **If you hit a new 400 error from any booking endpoint, reach for HAR capture first, not hypothesis iteration.**

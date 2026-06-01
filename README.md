# mackbot

Automatically scans and books Kananaskis Golf tee times (Mt Lorette & Mt Kidd) for Alberta residents. Polls the CPS Golf API on a schedule and books the first available slot matching your criteria — including payment via card on file.

---

## Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)

To check if you have them:
```bash
python3 --version
node --version
```

---

## Setup

**1. Download the project**

Either clone with Git or download and unzip from GitHub, then open a terminal in the project folder.

```bash
git clone https://github.com/rbmccaughey/mackbot.git
cd mackbot
```

**2. Run setup**

This creates the Python environment, installs all dependencies, and sets up the frontend. Takes about a minute on first run.

```bash
make setup
```

**3. Add your credentials**

Open the `.env` file that was created and fill in your Kananaskis Golf account details:

```
GOLF_EMAIL=your@email.com
GOLF_PASSWORD=yourpassword
```

---

## Running

```bash
make run
```

Then open **http://localhost:8000** in your browser.

> **Note:** On the first scan, a Chrome window will open automatically for login. This is required to pass Cloudflare's bot detection — just leave it alone and it will log in and minimize. It only appears on first launch or when your session expires (~1 hour).

---

## Usage

1. Click **New Scan**
2. Enter your target date, time window, and number of players
3. Optionally filter by course (Mt Lorette or Mt Kidd, or leave blank for both)
4. Click **Start**

mackbot will poll every 5 minutes. When a matching tee time opens up, it books it immediately and charges your card on file. You'll get a macOS notification when it's booked.

To stop a scan before it finds anything, click **Cancel**.

---

## Notes

- Scans are stored in memory and are lost if the server is restarted
- The poll interval defaults to 5 minutes — changing it shorter won't help as the API caches results
- Cards on file are managed through your Kananaskis Golf account at [kananaskisabresidents.cps.golf](https://kananaskisabresidents.cps.golf)
- Desktop notifications only work on macOS

---

## Development

To run the frontend with live reload (for UI changes):

```bash
make dev
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

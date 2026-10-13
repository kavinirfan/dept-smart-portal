# Department Smart Portal

A working prototype of the portal described in the capstone report. One login and one set of roles cover
seven modules: split marks, lab booking, faculty availability, a jobs and internships board, an
identity-verified campus chat, notifications and a live HOD dashboard.

**Stack:** FastAPI + SQLAlchemy (Python), React + Vite + Recharts, SQLite for local runs or PostgreSQL
in Docker, JWT login with bcrypt password hashing, WebSockets for chat, WebAuthn for fingerprint/Face ID
unlock, openpyxl for Excel exports.

## Run it on your Mac

You need **Python 3.10+** ([python.org](https://www.python.org/downloads/)) and **Node.js 18+** ([nodejs.org](https://nodejs.org/), LTS).

1. Unzip the project and open **Terminal**.
2. Type `cd ` (with a space), drag the `portal` folder into the window, and press Return.
3. Run:

   ```bash
   bash start.sh
   ```

4. Open **http://localhost:8000** (use `localhost`, not `127.0.0.1`, or Touch ID unlock will not work).

The first run takes a minute or two. Press `Ctrl+C` in Terminal to stop. On Windows, double-click
`start.bat` instead.

### Or with Docker (uses PostgreSQL)

```bash
docker compose up --build
```

Then open http://localhost:8000. Data lives in Docker volumes; `docker compose down -v` wipes it.

### Demo accounts

Every account's password is `portal123`. The login page has one-click buttons for each role.

| Role | Email | Good for showing |
| --- | --- | --- |
| HOD / Admin | hod@dept.edu | Dashboard, ID approvals, chat moderation, users, credentials, audit log |
| Teacher | arjun@dept.edu | Entering marks (holds CS501 and CS504), booking labs, setting status |
| Teacher | lakshmi@dept.edu, rahul@dept.edu | A teacher without the CS501 credential is blocked from its marks |
| Lab In-charge | labincharge@dept.edu | Setting labs free / occupied / maintenance |
| Student (verified) | kavin@dept.edu, priya@dept.edu, farhan@dept.edu | Marks charts, notices, chat |
| Student (ID pending) | aditya@dept.edu | The HOD approves him, then he sets up Touch ID |
| Student (ID rejected) | divya@dept.edu | Re-upload flow |
| Student (no ID yet) | gayathri@dept.edu | First-time ID upload |

A step-by-step walkthrough for a viva or review is in [docs/DEMO.md](docs/DEMO.md), and every screen is in
[docs/screenshots](docs/screenshots).

To reset all demo data: `cd backend && ../.venv/bin/python -m app.seed --reset`

## What each module does

| Module (report section) | What's built |
| --- | --- |
| **Users & roles** (3.1, 7.1) | Student, Teacher, Lab In-charge and HOD/Admin. The admin adds and disables users, adds subjects and grants teachers subject-level marks credentials. Every route checks the role on the server. |
| **Split marks** (4.1, 7.2) | Teachers enter question-wise marks only for subjects they hold a credential for, add tests (max per question + weightage) and mark absentees. Marks above a question's maximum are rejected. Students see only their own marks: a chart of each test against the class average, the question-wise table and their weighted internal total. Staff can look up any student. |
| **Lab booking** (4.2, 7.3) | A live board shows each lab as free, occupied or under maintenance. The lab in-charge sets the status. Overlapping requests are refused first come, first served, and the refusal names whoever holds the slot. Labs under maintenance cannot be booked. |
| **Faculty availability** (4.3, 7.4) | Staff set Available / In Class / On Leave / Unavailable with a note. Everyone sees the live board. Every change is kept, so the HOD can export a day-by-day attendance sheet. |
| **Jobs & internships** (4.4, 7.5) | Anyone can post. Search, a type filter and deadline countdowns; expired notices are hidden by default. The poster or the HOD can remove a notice. |
| **Verified chat** (4.5, 7.6) | Gate 1: upload a photo of the college ID card and an admin approves it. Gate 2: unlock on your own device with WebAuthn (Touch ID, Face ID, Windows Hello, Android fingerprint or the device PIN). Only a public key is stored, never biometric data. Access stays open for a 2-hour window. Messages arrive live over WebSockets. Anyone can report a message; the HOD removes it or dismisses the report. |
| **Notifications** (4.6, 7.7) | A bell with an unread count. It covers marks entered or changed, new notices, lab bookings on your lab, your booking cancelled by someone else, a lab you booked going into maintenance, ID card decisions, new ID cards (admin) and reported messages (admin). |
| **HOD dashboard** (4.7) | Live tiles (students, faculty present, labs free, students at risk, open opportunities, items to review), the average internal per subject, lab use this week, the at-risk list, deadlines closing this week and recent activity. It refreshes every 30 seconds. |
| **Excel export** (3.1) | Marks per subject (an internal summary plus one sheet per test), lab bookings, faculty attendance (HOD only) and notices. Each file is generated from the database when downloaded, so the database stays the single source of truth. |
| **Audit log** (8) | Every change to marks, labs, faculty status, users, credentials, notices, ID cards and chat moderation records who made it and when. |

### Deliberate simplifications (worth stating in the viva)

- **Marks are typed in, not scanned.** Reading marks from photographed answer sheets (OCR, Section 4.1) is
  future work. The scan tables from Section 7.2 (`answer_sheet_scans`, `detected_marks`) would sit in front of
  today's `marks` table, and the report's rule that a person confirms every mark is what manual entry
  already enforces.
- **Password unlock fallback for chat.** Devices with no fingerprint, face or PIN authenticator can unlock
  with the account password. Set `CHAT_PASSWORD_FALLBACK=0` to require WebAuthn only.
- **In-app notifications only.** Email is not sent.
- **Live boards refresh by polling** (every 20 to 30 seconds); only chat uses WebSockets.
- **First come, first served** is enforced with a lock inside one server process plus a row lock on
  PostgreSQL. Running several server processes would need the PostgreSQL setup.

## Tests

```bash
cd backend
../.venv/bin/python -m pytest          # 29 tests on SQLite
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/portal_test ../.venv/bin/python -m pytest   # same tests on PostgreSQL (needs psycopg)
```

The tests cover login and roles, credential checks on marks, mark validation and the student view,
first-come-first-served booking and cancellation, maintenance blocking, faculty status, notices,
notifications, the dashboard, the ID card flow, live chat over WebSockets, moderation and the WebAuthn
origin check.

## Developing

Run the backend and frontend separately so the web app hot-reloads:

```bash
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload   # API on :8000
cd frontend && npm run dev                                           # web app on :5173
```

API docs, generated automatically: http://localhost:8000/docs

## Project layout

```
backend/
  app/
    main.py            FastAPI app; also serves the built web app
    database.py        SQLite by default, PostgreSQL via DATABASE_URL
    models.py          All tables (Section 7 of the report)
    security.py        bcrypt, JWT, role guard, audit and notify helpers
    seed.py            Demo data
    routers/
      auth.py users.py marks.py labs.py faculty.py notices.py
      exports.py notifications.py chat.py dashboard.py
  tests/
frontend/
  src/
    pages/             One file per screen
    components/        Layout, notification bell, student marks report
    api.js auth.jsx nav.js usePolling.js
docs/
  DEMO.md              Walkthrough script
  screenshots/         Every screen
Dockerfile, docker-compose.yml, start.sh, start.bat
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./portal.db` | e.g. `postgresql+psycopg://user:pass@host/db` |
| `SECRET_KEY` | `dev-only-change-me` | **Change this** for any real deployment |
| `TOKEN_MINUTES` | `480` | How long a login lasts |
| `CHAT_SESSION_MINUTES` | `120` | How long chat stays unlocked |
| `CHAT_PASSWORD_FALLBACK` | `1` | `0` requires fingerprint/face/PIN to unlock chat |
| `WEBAUTHN_ORIGINS` | `http://localhost:8000,http://localhost:5173` | Addresses allowed for fingerprint unlock. A real deployment needs HTTPS and its own domain here. |
| `UPLOAD_DIR` | `backend/uploads` | Where ID card photos are stored |

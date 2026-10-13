#!/usr/bin/env bash
# One-command start (macOS / Linux): sets up a private Python environment, builds the web app,
# seeds demo data on first run, and starts the server at http://localhost:8000.
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "Python 3 is missing. Install it from https://www.python.org/downloads/"; exit 1; }
command -v npm >/dev/null || { echo "Node.js is missing. Install the LTS version from https://nodejs.org/"; exit 1; }

# A virtual environment avoids macOS/Homebrew "externally managed environment" errors.
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r backend/requirements.txt

(cd frontend && npm install --silent && npm run build --silent)
(cd backend && ../.venv/bin/python -m app.seed)

echo
echo "Portal running at http://localhost:8000  (demo password: portal123). Press Ctrl+C to stop."
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

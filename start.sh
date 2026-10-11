#!/usr/bin/env bash
# SoTaiSan: one command, one URL, on macOS and Linux.
#
# Builds the frontend into frontend/dist (which FastAPI then serves itself) and
# starts the backend, so everything lives on http://localhost:8010 — no second
# terminal, no CORS, no leftover Node process.
#
#   ./start.sh                 your own data, in backend/data.db
#   ./start.sh --demo          an invented portfolio in backend/demo.db
#   ./start.sh --no-browser    start without opening a browser
#
# For day-to-day development, run two terminals instead: `pnpm dev` in
# frontend/ gives hot reload and proxies /api to the backend.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port=8010
demo=0
browser=1

for arg in "$@"; do
  case "$arg" in
    --demo) demo=1 ;;
    --no-browser) browser=0 ;;
    -h|--help)
      sed -n '2,14p' "$0" | cut -c3-
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (the options are --demo and --no-browser)" >&2
      exit 2
      ;;
  esac
done

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "SoTaiSan needs $1, and this machine does not have it. $2" >&2
    exit 1
  fi
}

need pnpm "Install Node.js 22 or later from https://nodejs.org, then 'corepack enable pnpm'."
need uv "Install uv from https://docs.astral.sh/uv/ (it brings the Python it needs)."

echo "Building the interface..."
cd "$root/frontend"
[ -d node_modules ] || pnpm install
pnpm build

cd "$root/backend"
[ -d .venv ] || uv sync

if [ "$demo" = 1 ]; then
  export DATABASE_URL="sqlite:///demo.db"
  uv run python -m app.seed --if-missing
  echo "Demo portfolio: backend/demo.db. Your own data.db is not opened."
fi

echo "Starting SoTaiSan on http://localhost:$port"
if [ "$browser" = 1 ]; then
  # Give uvicorn a moment to bind before the browser asks for the page.
  (
    sleep 2
    if [ "$(uname -s)" = "Darwin" ] && command -v open >/dev/null 2>&1; then
      open "http://localhost:$port"
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "http://localhost:$port" >/dev/null 2>&1
    fi
  ) &
fi

exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$port"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "${ROOT_DIR}/backend/.venv" ]]; then
  echo "Missing backend/.venv. Please set it up first."
  exit 1
fi

cleanup() {
  echo ""
  echo "Stopping Job Copilot..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend on http://127.0.0.1:8000 ..."
(
  cd "${ROOT_DIR}/backend"
  exec "${ROOT_DIR}/backend/.venv/bin/uvicorn" app.main:app --reload --port 8000
) &
BACKEND_PID=$!

echo "Starting Vite frontend on http://localhost:5173 ..."
(
  cd "${ROOT_DIR}/frontend"
  exec npm run dev
) &
FRONTEND_PID=$!

wait

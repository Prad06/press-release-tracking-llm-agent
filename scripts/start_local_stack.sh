#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
MLFLOW_HOST="${MLFLOW_HOST:-127.0.0.1}"
MLFLOW_PORT="${MLFLOW_PORT:-5001}"

MLFLOW_BACKEND_STORE_URI="${MLFLOW_BACKEND_STORE_URI:-sqlite:///$ROOT_DIR/mlflow.db}"
MLFLOW_ARTIFACT_ROOT="${MLFLOW_ARTIFACT_ROOT:-$ROOT_DIR/mlruns}"
MLFLOW_EXPERIMENT_NAME="${MLFLOW_EXPERIMENT_NAME:-pr_flow_ingestion}"

if [[ -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

if [[ -d "$ROOT_DIR/.venv" && ! -x "$ROOT_DIR/.venv/bin/mlflow" ]]; then
  echo "mlflow is not installed in .venv."
  echo "Run: source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ -x "$ROOT_DIR/.venv/bin/mlflow" ]]; then
  MLFLOW_BIN="$ROOT_DIR/.venv/bin/mlflow"
elif command -v mlflow >/dev/null 2>&1; then
  MLFLOW_BIN="$(command -v mlflow)"
else
  echo "mlflow CLI not found. Install dependencies first: pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$MLFLOW_ARTIFACT_ROOT"

export MLFLOW_TRACKING_URI="http://${MLFLOW_HOST}:${MLFLOW_PORT}"
export MLFLOW_EXPERIMENT_NAME

echo "Starting local stack:"
echo "  Backend:  http://${API_HOST}:${API_PORT}"
echo "  Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "  MLflow:   http://${MLFLOW_HOST}:${MLFLOW_PORT}"
echo

"$MLFLOW_BIN" server \
  --host "$MLFLOW_HOST" \
  --port "$MLFLOW_PORT" \
  --workers 1 \
  --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
  --default-artifact-root "$MLFLOW_ARTIFACT_ROOT" \
  >/tmp/pr_flow_mlflow.log 2>&1 &
MLFLOW_PID=$!

uvicorn api.main:app --reload --host "$API_HOST" --port "$API_PORT" \
  >/tmp/pr_flow_backend.log 2>&1 &
API_PID=$!

(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) >/tmp/pr_flow_frontend.log 2>&1 &
FRONTEND_PID=$!

cleanup() {
  for pid in "$FRONTEND_PID" "$API_PID" "$MLFLOW_PID"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

echo "Logs:"
echo "  /tmp/pr_flow_frontend.log"
echo "  /tmp/pr_flow_backend.log"
echo "  /tmp/pr_flow_mlflow.log"
echo
echo "Press Ctrl+C to stop all services."

wait "$FRONTEND_PID" "$API_PID" "$MLFLOW_PID"

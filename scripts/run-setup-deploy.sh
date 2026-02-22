#!/usr/bin/env bash
set -euo pipefail

LOG_OUT="/tmp/setup_deploy.log"
LOG_ERR="/tmp/setup_deploy.err"
PID_FILE="/tmp/setup_deploy.pid"
DEPLOY_LOG_FILE="${DEPLOY_LOG_FILE:-data/logs/deploy.log}"
INTERVAL=30
WATCH=false

usage() {
  cat <<USAGE
Usage: scripts/run-setup-deploy.sh [--watch] [--interval SECONDS]

Runs \`python setup.py deploy\` in the background with stdout/stderr captured.

Options:
  --watch              Tail stdout/stderr every 30 seconds (default interval).
  --interval SECONDS   Tail interval for --watch (default: 30).
  -h, --help           Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)
      WATCH=true
      shift
      ;;
    --interval)
      INTERVAL="${2:-}"
      if [[ -z "$INTERVAL" || ! "$INTERVAL" =~ ^[0-9]+$ ]]; then
        echo "Error: --interval requires a positive integer." >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

mkdir -p "$(dirname "$DEPLOY_LOG_FILE")"
export PYTHONUNBUFFERED=1
export DEPLOY_LOG_FILE

echo "Starting: python setup.py deploy"
nohup python setup.py deploy >"$LOG_OUT" 2>"$LOG_ERR" &
PID=$!
echo "$PID" > "$PID_FILE"

echo "PID: $PID"
echo "stdout: $LOG_OUT"
echo "stderr: $LOG_ERR"
echo "deploy log: $DEPLOY_LOG_FILE"

if [[ "$WATCH" == "true" ]]; then
  echo "Tailing logs every ${INTERVAL}s. Press Ctrl+C to stop watching."
  while true; do
    date "+%Y-%m-%d %H:%M:%S"
    echo "--- stdout (last 30 lines) ---"
    tail -n 30 "$LOG_OUT" || true
    echo "--- stderr (last 30 lines) ---"
    tail -n 30 "$LOG_ERR" || true
    echo
    sleep "$INTERVAL"
  done
fi

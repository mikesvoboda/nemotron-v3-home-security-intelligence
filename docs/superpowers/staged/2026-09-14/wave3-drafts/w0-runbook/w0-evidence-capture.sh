#!/usr/bin/env bash
# w0-evidence-capture.sh — W0 runbook STEP 3(collision-check)/STEP 4 evidence block, copy-paste-ready.
# DRAFT — NOT EXECUTED (box lease held; this script touches compose — executor runs it ONLY after:
#   gate 14 verdict GREEN per STEP 1 + .env restored per STEP 2 + reconciliation decision per STEP 3).
# Safe pattern rules honored: podman-only compose (CLAUDE.md), never bare docker on the project stack,
# never touch dgx-inference-*, read-only ss/podman inspect/curl/ps, no builds beyond bootstrap phase-b.
set -uo pipefail   # no -e: capture EVERY evidence line even if one probe fails; failures are data

REPO=/agents/agent-nemo2/workspace
cd "$REPO" || exit 3
OUT=/tmp/w0-evidence; mkdir -p "$OUT"
COMPOSE="podman compose -f docker-compose.prod.yml -f config/docker-compose.gb300.yml"   # bootstrap-gb300.sh:42 verbatim
API_PORT=$(awk -F= '/^API_PORT=/{print $2; exit}' .env)
FE_PORT=$(awk -F= '/^FRONTEND_HTTP_PORT=/{print $2; exit}' .env)
PROJ=nemotron-v3-home-security-intelligence

{ echo "### $(date -Is) collision check ss -ltnp (5432/5433/6379/6380) — BEFORE bring-up"
  ss -ltnp | grep -E ':(5432|5433|6379|6380)\b' || echo "(none listening)"; } >  "$OUT/ss-before.txt" 2>&1

# bring-up (bootstrap codifies idempotency + churn proof):
bash scripts/bootstrap-gb300.sh phase-a  > "$OUT/phase-a.log" 2>&1
bash scripts/bootstrap-gb300.sh phase-b  > "$OUT/phase-b.log" 2>&1
bash scripts/bootstrap-gb300.sh gate     > "$OUT/gate.log"    2>&1
bash scripts/bootstrap-gb300.sh phase-a  > "$OUT/phase-a-rerun.log" 2>&1   # Step 2b no-op check
bash -n scripts/bootstrap-gb300.sh; echo "bash -n rc=$?" >> "$OUT/gate.log"

{ echo '### (a) services table'; $COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"; } >  "$OUT/ps.txt" 2>&1
{ echo '### (b) foscam-init exit code'; podman inspect "${PROJ}-foscam-init-1" --format '{{.State.ExitCode}}'; } >> "$OUT/ps.txt" 2>&1
{ echo '### (c) GPU-exclusion proof'; podman ps -a --format '{{.Names}}' | grep -E '(^|[-_])(ai-[a-z0-9-]+|dcgm-exporter)([-_]|$)'; echo "absent-rc=$?  (want 1)"; } >> "$OUT/ps.txt" 2>&1
{ echo '### (d) endpoints';
  echo "ready direct   : $(curl -s -o /dev/null -w '%{http_code}' "localhost:${API_PORT}/api/system/health/ready")"
  echo "ready proxied  : $(curl -s -o /dev/null -w '%{http_code}' "localhost:${FE_PORT}/api/system/health/ready")"
  echo "aggregate      : $(curl -s -o /dev/null -w '%{http_code}' "localhost:${API_PORT}/api/system/health")  (503 = M1 design)"
  echo "frontend /health: $(curl -s -o /dev/null -w '%{http_code}' "localhost:${FE_PORT}/health")"; } > "$OUT/endpoints.txt" 2>&1
{ echo '### (e) pipeline workers (needs LOG_LEVEL=INFO)';
  podman logs "${PROJ}-backend-1" 2>&1 | grep -n 'Pipeline workers started' || echo 'MISSING — check LOG_LEVEL + recreate'; } > "$OUT/workers.txt" 2>&1
{ echo '### (f) logs --tail=50 scan'; $COMPOSE logs --tail=50 > /tmp/w0-compose-logs-tail50.log 2>&1
  grep -niE 'error|fatal|panic|exception|traceback' /tmp/w0-compose-logs-tail50.log || echo '0 hits'; } > "$OUT/logscan.txt" 2>&1

{ echo '### ss AFTER bring-up'; ss -ltnp | grep -E ':(5432|5433|6379|6380)\b' || echo '(none)'; } > "$OUT/ss-after.txt" 2>&1
echo "evidence in $OUT — paste per-file into the ledger template slots, then run /platform-healthcheck (STEP 6)."

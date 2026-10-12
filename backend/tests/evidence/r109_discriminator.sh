#!/usr/bin/env bash
# r109 discriminator — the committed tool behind PR #7003's "(b) discriminator"
# table (contract rule 3: tools live in the repo).
#
# WHY this file exists (self-review finding F3): the table's first version cited
# 3.08/2.89/2.69/2.12 s that appear in NO saved artifact — the full-tier run that
# produced those four reds was never passed --durations, so the figures were
# quoted, not read. They are withdrawn and replaced by figures THIS script
# prints. The claim it measures: the nightly's 5 s-budget victims are not
# genuinely slow — they pass on one idle CPU and run a few seconds under the
# hosted 4x-oversubscription shape (2 CPUs while addopts asks for 8 xdist
# workers, which is what a 4-vCPU ubuntu-latest runner does to `-n 8`).
#
# The victim list is the COMPLETE red set of the two 2-CPU seed runs in #7003's
# Evidence section — 4 reds at seed 4073384164 (tick4) + 7 at seed 4183883467
# (tick5), one shared (clip_render) = 10 distinct. F3 also caught that the old
# table said "all four reds in my repro" while the repro produced ELEVEN red
# lines; this list is the honest scope of the pass-on-idle-hardware claim.
#
# --timeout=60 here measures durations without letting the 5 s ini budget clamp
# them; it does NOT change any gated timeout (ruling 83): the tier's `timeout = 5`
# in pyproject.toml still governs every nightly/PR test, untouched.
#
# Usage: LOG=/tmp/r109-discriminator.log backend/tests/evidence/r109_discriminator.sh
# Single draws by design — timing figures are one measurement per cell, like the
# seed-pinned runs they replace; the durable claim is PASS/PASS + magnitude order.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://security:security_dev_password@localhost:15432/security}" # pragma: allowlist secret
export TEST_REDIS_URL="${TEST_REDIS_URL:-redis://localhost:16379/0}"
export CI=true ENVIRONMENT=development LOG_DB_ENABLED=false
LOG="${LOG:-/tmp/r109-discriminator.log}"
IDS=(
  "backend/tests/unit/models/test_event_audit.py::TestEventAuditProperties::test_all_scores_roundtrip"
  "backend/tests/unit/models/test_zone_anomaly.py::TestZoneAnomalyProperties::test_anomaly_type_severity_roundtrip"
  "backend/tests/unit/synthbench/test_clip_render.py::test_a_flux_renderer_is_freed_warmed_to_h3_once_then_renders"
  "backend/tests/unit/core/test_json_utils.py::TestSafeJsonLoadsPropertyBased::test_preserves_integer_values"
  "backend/tests/unit/models/test_audit_log.py::TestAuditLogUnicodeProperties::test_resource_type_unicode_roundtrip"
  "backend/tests/unit/models/test_job_attempt.py::TestJobAttemptProperties::test_error_message_roundtrip"
  "backend/tests/unit/services/test_risk_rubrics.py::TestRubricScoresProperties::test_valid_inputs_always_create_model"
  "backend/tests/unit/models/test_scene_change.py::TestSceneChangeProperties::test_multiple_fields_roundtrip"
  "backend/tests/unit/services/test_key_frame_selector.py::TestTemporalSpread::test_spread_keeps_every_shipped_property"
  "backend/tests/unit/synthbench/test_clip_audit_command.py::TestPage::test_the_clip_route_serves_the_ready_attempts_mp4_bytes"
)
{
  echo "START $(date -u +%FT%TZ) head=$(git rev-parse HEAD)"
  echo "cpus: A=$(taskset -c 0 python3 -c 'import os;print(len(os.sched_getaffinity(0)))') \
B=$(taskset -c 0,1 python3 -c 'import os;print(len(os.sched_getaffinity(0)))') (B runs addopts' -n 8 on 2 CPUs = hosted oversubscription)"
  echo "===== A: 1 CPU, serial (-n 0) ====="
  taskset -c 0 uv run pytest "${IDS[@]}" -n 0 -p no:randomly --no-cov --durations=0 \
    --timeout=60 -q -rA 2>&1 | grep -E "passed|failed|error|durations ===|^[0-9.]+s call|^PASSED|^FAILED"
  echo "EXIT_A=${PIPESTATUS[0]}"
  echo "===== B: 2 CPUs with addopts' -n 8 (the hosted shape) ====="
  taskset -c 0,1 uv run pytest "${IDS[@]}" -p no:randomly --no-cov --durations=0 \
    --timeout=60 -q -rA 2>&1 | grep -E "passed|failed|error|durations ===|^[0-9.]+s call|^PASSED|^FAILED"
  echo "EXIT_B=${PIPESTATUS[0]}"
  echo "END $(date -u +%FT%TZ)"
} >> "$LOG" 2>&1

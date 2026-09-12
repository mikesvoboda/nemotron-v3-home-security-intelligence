#!/usr/bin/env bash
# scripts/bootstrap-gb300.sh — codified arm64/GB300 Milestone-1 bring-up + gate.
#
# Codifies the PROVEN sequence from Tasks 1-7 of the arm64/GB300 M1 plan
# (docs/superpowers/specs/2026-09-12-arm64-gb300-milestone1-design.md), as executed
# and recorded in .superpowers/sdd/2026-09-12-arm64-gb300-milestone1/ task reports
# (2026-09-12) — this script is transcription, not re-invention. Deviations from the
# generic amd64 path are host facts, cited inline.
#
# TWO-DAEMON HOST RULE (ledger Phase A): `podman compose` talks to the ROOTLESS
# podman socket where this project lives; a bare `docker` CLI would talk to the
# co-resident ROOTFUL dockerd holding dgx-inference-* containers. This script NEVER
# invokes bare `docker` and never touches dgx-inference containers. The only global
# (unfiltered) podman listing is the read-only GPU-exclusion name check in `gate`
# (spec §6: "ai-* and dcgm-exporter absent from podman ps") — anchored patterns that
# cannot match dgx-inference-* names, and nothing is ever acted on from it.
#
# API_PORT is read from .env (resolves to 8001 on this host — dgx-inference-vllm
# holds 8000). Never hardcoded.
#
# M1 design (spec §8): GPU/AI services are OUT OF SCOPE. `/api/system/health` is
# 503-degraded BY DESIGN without them; the gate checks /api/system/health/ready,
# pipeline-worker startup evidence, and Prometheus targets against an explicit
# TARGETS-DOWN allowlist instead. No AI service is ever started, built, or pulled
# by this script — the only place AI names appear is the exclusion proof and the
# targets allowlist.
#
# Lint (host note): no shellcheck binary is installed host-side and no shellcheck
# pre-commit hook exists, but shellcheck IS reachable without installing anything:
#   uvx --from shellcheck-py shellcheck scripts/bootstrap-gb300.sh
# (the --from form is required — `uvx shellcheck-py` alone does not expose the
# executable). Run it on any edit.
#
# Usage: bootstrap-gb300.sh [require-podman|env|phase-a|phase-b|gate|probe|all] [--probe]
# Subcommands are individually idempotent; each no-ops cleanly when its work is done.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants — proven spellings (task-8 controller addendum, verbatim)
# ---------------------------------------------------------------------------
PROJECT_NAME="nemotron-v3-home-security-intelligence"
COMPOSE="podman compose -f docker-compose.prod.yml -f config/docker-compose.gb300.yml"

# Phase-A service list (exact 15 names, spec §6 / task-5 report).
PHASE_A_SERVICES=(postgres redis foscam-init go2rtc prometheus grafana loki tempo
	alloy alertmanager pyroscope node-exporter redis-exporter json-exporter
	blackbox-exporter)
# Services that have no (or disabled) healthchecks — plain "Up" is CORRECT for them.
NO_HEALTHCHECK_SERVICES=(redis-exporter json-exporter)

# TARGETS-DOWN handling (addendum FINAL ruling + task-6 live table):
# - ALLOWLIST: expected DOWN in M1 outright (M1-absent services).
#   hsi-health: backend /health is 503-degraded without AI (json-exporter v0.6.0
#   refuses non-2xx upstreams) — down BY DESIGN until AI exclusion semantics change (M2).
# - BACKEND-DEPENDENT: flip UP when backend arrives (task-6 table). DOWN is normal
#   pre-phase-b (reported as info), but down-with-backend-running is a hard FAIL.
# Any other down job = FAIL.
TARGETS_DOWN_ALLOWLIST="ai-llm-metrics triton-metrics cadvisor dcgm-exporter hsi-health"
BACKEND_DEPENDENT_TARGETS="hsi-backend-metrics hsi-gpu hsi-stats hsi-telemetry"

BACKEND_CONTAINER="${PROJECT_NAME}-backend-1"
FRONTEND_TAG_LOCALHOST="localhost/${PROJECT_NAME}-frontend:latest"
FRONTEND_TAG_DOCKERIO="docker.io/library/${PROJECT_NAME}-frontend:latest"
# Pipeline-worker startup line (backend/main.py:794). Requires LOG_LEVEL=INFO — the
# compose default (WARNING) suppresses the INFO lifespan line, making this gate
# vacuous (proven in task-6 report; .env sets INFO).
WORKER_LOG_PATTERN='Pipeline workers started'

PROBE_LOG_PATH="/tmp/gb300-probe-log.md"

PASS=0
FAIL=0
declare -a FAILURES=()

fail() { printf 'FAIL: %s\n' "$1" >&2; FAIL=$((FAIL + 1)); FAILURES+=("$1"); }
pass() { printf 'ok:   %s\n' "$1"; PASS=$((PASS + 1)); }

banner() { printf '\n=== %s ===\n' "$1"; }

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

require_repo_root() {
	[ -f docker-compose.prod.yml ] || die "not at repo root (docker-compose.prod.yml missing); run from the repo root"
}

require_env() {
	[ -f .env ] || die ".env missing — run 'bootstrap-gb300.sh env' first"
}

# Read a KEY from .env (first match). stdout = value; empty if absent.
env_get() {
	awk -F= -v key="$1" '$1 == key { print substr($0, index($0, "=") + 1); exit }' .env
}

# ---------------------------------------------------------------------------
# require-podman: install check ONLY (no apt — host prep belongs to the owner)
# ---------------------------------------------------------------------------
cmd_require_podman() {
	banner "require-podman"
	local ok=1
	if ! command -v podman >/dev/null 2>&1; then
		echo "podman NOT installed. Install it host-side (no sudo from this script):"
		echo "  sudo apt install podman podman-compose    # Ubuntu 24.04 ships 4.9.x"
		ok=0
	else
		pass "podman installed: $(podman --version 2>/dev/null || echo 'version check failed')"
	fi

	local uid sock
	uid="$(id -u)"
	sock="/run/user/${uid}/podman/podman.sock"
	if [ ! -S "$sock" ]; then
		echo "podman socket MISSING at $sock (rootless). Enable it host-side:"
		echo "  systemctl --user enable --now podman.socket"
		ok=0
	else
		pass "podman socket present: $sock"
	fi

	# User-unit check (NO sudo — this is a rootless stack).
	if ! systemctl --user is-active --quiet podman.socket 2>/dev/null; then
		echo "systemd user unit podman.socket is NOT active. Enable it host-side:"
		echo "  systemctl --user enable --now podman.socket"
		ok=0
	else
		pass "systemd user unit podman.socket active"
	fi

	if ! podman compose version >/dev/null 2>&1; then
		echo "'podman compose' provider check failed. Expected: external docker-compose"
		echo "provider (v2.40.3 on this host). Verify with: podman compose version"
		ok=0
	else
		pass "compose provider reachable: $(podman compose version 2>/dev/null | head -n1)"
	fi

	[ "$ok" -eq 1 ] || die "require-podman: see install instructions above (run them yourself; this script never uses sudo)"
}

# ---------------------------------------------------------------------------
# env: .env generation + template deltas (Task 3 mechanics, idempotent)
# ---------------------------------------------------------------------------
# Only touches .env when it does not exist. A pre-existing .env is never edited
# (owner-managed host artifact, gitignored).
cmd_env() {
	banner "env"
	if [ -f .env ]; then
		pass ".env already exists — skipping generation (idempotent no-op)"
		return 0
	fi

	echo ".env absent — generating via setup.py machinery (never setup.py main())"
	# setup.py has no top-level 'import os' but run_defaults_mode() calls os.getuid()
	# (setup.py:1116) — inject the stdlib module into the loaded object in-memory
	# only (proven workaround, task-3 report; disk setup.py stays untouched).
	python3 - <<'PYEOF'
import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location("setup_mod", "setup.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.os = os  # setup.py has no top-level "import os"; run_defaults_mode() calls os.getuid() @1116
cfg = m.run_defaults_mode()
Path(".env").write_text(m.generate_env_content(cfg))
Path(".env").chmod(0o600)
print("generated .env (mode 600)")
PYEOF

	# Template deltas: NAME-first sed for the two placeholders, KEY=VALUE lines only,
	# then replace-or-append each into .env (Task 3 Step 3 mechanics verbatim).
	sed -e "s/UID_NAME_PLACEHOLDER/$(id -un)/" -e "s/UID_PLACEHOLDER/$(id -u)/" env-templates/gb300.env.template |
		while IFS= read -r line; do
			line="${line%%#*}"
			line="${line// /}"
			[[ "$line" == *=* ]] || continue
			printf '%s\n' "$line"
		done |
		while IFS= read -r kv; do
			k="${kv%%=*}"
			if grep -q "^$k=" .env; then
				sed -i "s|^$k=.*|$kv|" .env
			else
				echo "$kv" >>.env
			fi
		done

	# Host paths under owner-writable dirs (generation defaults /export/* belong to a
	# co-resident product; compose defaults /home/ubuntu/* un-creatable rootless).
	mkdir -p "$(env_get FOSCAM_BASE_PATH || true)" 2>/dev/null || true
	mkdir -p "$(env_get AI_MODELS_PATH || true)" 2>/dev/null || true
	mkdir -p "$(env_get TMPDIR || true)" 2>/dev/null || true
	mkdir -p "$(env_get HF_CACHE_PATH || true)" 2>/dev/null || true

	# Two REQUIRED post-apply deltas (addendum; ledger Task 6 rulings):
	# HF_CACHE_PATH — compose default /home/ubuntu/... is un-creatable rootless (statfs probe).
	# LOG_LEVEL=INFO — compose default WARNING masks the main.py:794 worker line the gate greps.
	ensure_env_kv "HF_CACHE_PATH" "$HOME/.cache/huggingface"
	ensure_env_kv "LOG_LEVEL" "INFO"

	# Guard: .env must exist, be mode 600, and parse through compose.
	[ -f .env ] || die ".env generation failed"
	chmod 600 .env
	$COMPOSE config -q || die "rendered compose config does not parse with generated .env"
	pass ".env generated + deltas applied + compose config -q OK"
}

# Replace-or-append KEY=VALUE in .env (first occurrence replaced; appended if absent).
ensure_env_kv() {
	local key="$1" value="$2"
	if grep -q "^${key}=" .env; then
		sed -i "s|^${key}=.*|${key}=${value}|" .env
	else
		printf '%s=%s\n' "$key" "$value" >>.env
	fi
}

# ---------------------------------------------------------------------------
# Image builds (addendum "image builds" section, ruling C4 asymmetry)
# ---------------------------------------------------------------------------
# backend: via $COMPOSE build (provider path works for backend).
# frontend: DIRECT podman build with raised nofile — the provider's build path runs
# RUN steps at nofile soft=hard=1024 and the Dockerfile:93 `ulimit -n 65536` raise
# dies EPERM (task-6 probes: compose `ulimits:` is a runtime-only key, inert for
# build containers; docker-compose v2.40.3 build has NO ulimit flag). Never "fixed"
# by committing an overlay ulimits key.
# NOTE: builds are deliberately NOT idempotent cheap no-ops (--no-cache is the
# proven spelling); rerunning them is expensive by design. The idempotent paths are
# the tag-alias + up steps that follow.
build_images() {
	banner "build images"
	$COMPOSE build --no-cache backend
	podman build --ulimit nofile=65536:65536 --no-cache --target prod --layers \
		-t "$FRONTEND_TAG_LOCALHOST" frontend/
	# Tag reconciliation: rendered compose config has NO `image:` key for
	# backend/frontend (build:-only), so the provider derives refs itself and the two
	# spellings must both resolve (task-6 report 1d). After aliasing, `up` must print
	# NO "Building" line (a rebuild = ulimit wall again).
	podman tag "$FRONTEND_TAG_LOCALHOST" "$FRONTEND_TAG_DOCKERIO"
	podman image exists "$FRONTEND_TAG_LOCALHOST" || die "frontend image missing after build"
	podman image exists "$FRONTEND_TAG_DOCKERIO" || die "frontend docker.io/library alias missing"
	podman image exists "docker.io/library/${PROJECT_NAME}-backend:latest" || die "backend image missing after build"
	pass "images built + both frontend tag spellings resolve"
}

# ---------------------------------------------------------------------------
# phase-a: infra/media/observability up (exact 15 names, no AI deps)
# ---------------------------------------------------------------------------
cmd_phase_a() {
	banner "phase-a"
	require_env
	# Idempotency evidence for the ledger: snapshot pids before/after (addendum:
	# "no container churn: compare podman ps -q before/after phase-a when already up").
	# Scoped to project labels — never lists or touches dgx-inference containers.
	local before after
	before="$(podman ps -aq --filter "label=com.docker.compose.project=${PROJECT_NAME}" | sort)"
	# shellcheck disable=SC2086 # intentional word splitting of the service list
	$COMPOSE up -d "${PHASE_A_SERVICES[@]}" || die "phase-a up failed"
	after="$(podman ps -aq --filter "label=com.docker.compose.project=${PROJECT_NAME}" | sort)"
	if [ "$before" = "$after" ]; then
		pass "phase-a up complete (no container churn — already up)"
	else
		pass "phase-a up complete (created/changed: $(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | wc -l) container(s))"
	fi
}

# ---------------------------------------------------------------------------
# phase-b: backend + frontend with --no-deps (never plain `up` — GPU deps)
# ---------------------------------------------------------------------------
cmd_phase_b() {
	banner "phase-b"
	require_env
	build_images
	$COMPOSE up -d --no-deps backend frontend || die "phase-b up failed"
	pass "phase-b up complete (--no-deps; no ai-* dragged)"
}

# ---------------------------------------------------------------------------
# gate: the M1 exit-criteria checklist (spec §6), reporting honestly
# ---------------------------------------------------------------------------
# Runs every §6 check and prints per-check results; exits nonzero listing failures.
# Currently-down services are reported as found (the checklist shape is per-service,
# not assume-green).
cmd_gate() {
	banner "gate (spec §6 M1 exit criteria)"
	require_env
	local services_json
	services_json="$($COMPOSE ps -a --format json)" || die "compose ps failed"

	# --- 1. Per-service Up/healthy table (spec §6 core list + foscam-init one-shot) ---
	# NOTE: the TSV feed must never contain EMPTY middle fields — bash `read` treats
	# tab as IFS whitespace and collapses consecutive delimiters, which would shift
	# columns (the bug this comment guards against). A missing healthcheck renders as
	# Health:"" in this provider's JSON (empty string, NOT null — jq's `//` does not
	# fire on ""), so the explicit empty-test below is required, not cosmetic.
	local svc state health exitcode
	{
		echo
		printf '%-22s %-10s %-10s %s\n' "SERVICE" "STATE" "HEALTH" "NOTE"
		while IFS=$'\t' read -r svc state health exitcode; do
			[ -n "$svc" ] || continue
			local note=""
			if [ "$state" = "exited" ]; then
				if [ "$svc" = "foscam-init" ] && [ "$exitcode" = "0" ]; then
					note="one-shot completed (exit 0) — expected"
					pass "foscam-init exited 0 (service_completed_successfully one-shot)"
				else
					note="EXITED code=$exitcode — unexpected"
					fail "$svc exited with code $exitcode (not a planned one-shot exit)"
				fi
			elif [ "$state" = "running" ]; then
				case " ${NO_HEALTHCHECK_SERVICES[*]} " in
					*" $svc "*)
						note="no healthcheck (by design)"
						pass "$svc running (plain Up correct — no healthcheck defined)"
						;;
					*)
						if [ "$health" = "healthy" ]; then
							note=""
							pass "$svc Up (healthy)"
						elif [ "$health" = "starting" ]; then
							note="healthcheck starting"
							fail "$svc Up but healthcheck still starting"
						else
							note="health=${health}"
							fail "$svc Up but NOT healthy (health=${health})"
						fi
						;;
				esac
			else
				note="state=$state"
				fail "$svc in state $state (expected running or exited-0)"
			fi
			[ "$health" = "none" ] && health="-"
			printf '%-22s %-10s %-10s %s\n' "$svc" "$state" "$health" "$note"
		done <<<"$(
			printf '%s\n' "$services_json" | jq -r '[(.Service // "unknown"), (.State // "unknown"), (if (.Health // "") == "" then "none" else .Health end), ((.ExitCode // "none") | tostring)] | @tsv' | sort
		)"
	}

	# --- 2. GPU exclusion proof: ai-* + dcgm-exporter absent from podman ps (spec §6) ---
	# Read-only name check on the global podman ps (see two-daemon note in header):
	# anchored to the project's own naming shapes; dgx-inference-* names cannot match,
	# and nothing is acted on from this listing.
	banner "gate: GPU exclusion"
	local excluded
	excluded="$(podman ps --format '{{.Names}}' 2>/dev/null | grep -E '(^|-)ai-[a-z0-9-]+-[0-9]+$|^dcgm-exporter$|^cadvisor$' || true)"
	if [ -n "$excluded" ]; then
		fail "GPU/AI containers present despite M1 exclusion: $excluded"
	else
		pass "no ai-* / dcgm-exporter / cadvisor containers running (M1 exclusion holds)"
	fi

	# --- 3. Prometheus ready + targets against TARGETS-DOWN allowlist ---
	banner "gate: prometheus"
	local backend_running_cached
	backend_running_cached="$(podman ps -q --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.service=backend" || true)"
	local prom_port
	prom_port="$(env_get PROMETHEUS_PORT)"
	prom_port="${prom_port:-9090}"
	if curl -sf "localhost:${prom_port}/-/ready" >/dev/null 2>&1; then
		pass "prometheus /-/ready (port $prom_port)"
	else
		fail "prometheus /-/ready not reachable on port $prom_port"
	fi
	local down_jobs unexpected_down
	down_jobs="$(curl -sf "localhost:${prom_port}/api/v1/targets" 2>/dev/null |
		jq -r '.data.activeTargets[] | select(.health != "up") | .labels.job' | sort -u || true)"
	if [ -z "$down_jobs" ]; then
		pass "no prometheus targets down"
	else
		unexpected_down=""
		while IFS= read -r job; do
			[ -n "$job" ] || continue
			case " $TARGETS_DOWN_ALLOWLIST " in
				*" $job "*)
					printf 'ok:   target %s down (M1 allowlist)\n' "$job"
					;;
				*)
					case " $BACKEND_DEPENDENT_TARGETS " in
						*" $job "*)
							# hsi-backend-metrics/hsi-gpu/hsi-stats/hsi-telemetry depend on
							# the backend: down is the normal pre-phase-b state (task-6
							# table — they flip UP when backend arrives); down WITH backend
							# running is a hard FAIL.
							if [ -z "$backend_running_cached" ]; then
								printf 'info: target %s down (pre-phase-b state — flips UP with backend)\n' "$job"
							else
								fail "target $job down although backend IS running (expected UP per task-6)"
							fi
							;;
						*) unexpected_down="$unexpected_down $job" ;;
					esac
					;;
			esac
		done <<<"$down_jobs"
		if [ -n "$unexpected_down" ]; then
			fail "prometheus targets down OUTSIDE the M1 allowlist:$unexpected_down"
		else
			pass "all down targets accounted for (M1 allowlist + pre-phase-b backend-dependent)"
		fi
	fi

	# --- 4. Backend: container + worker evidence + /health/ready (direct + proxied) ---
	# NOTE (addendum ruling): /api/system/health returns 503-degraded in M1 BY DESIGN
	# (aggregates AI services; spec §8 defers them). Gate on /health/ready, NOT /health.
	banner "gate: backend health + workers"
	local api_port fe_port
	api_port="$(env_get API_PORT)"
	fe_port="$(env_get FRONTEND_HTTP_PORT)"
	if [ -z "$backend_running_cached" ]; then
		fail "backend container not running (phase-b not started on this host?)"
		echo "  -> workers + readiness checks SKIPPED (nothing to probe)"
	else
		# Worker evidence: the main.py:794 lifespan line. Requires LOG_LEVEL=INFO in
		# .env (compose default WARNING masks it — proven task-6). Podman-level logs
		# (container name is deterministic for this provider: project-service-1).
		# R-PIPEFAIL-GREPQ: under `set -o pipefail`, `... | grep -q` on content larger
		# than the 64 KiB pipe buffer returns 141 (the writer takes SIGPIPE when
		# grep -q exits at the first match) — a successful match reads as FAILURE.
		# grep -c/-n read to EOF and are immune. Capture once; test without a pipe.
		backend_worker_log="$(podman logs "$BACKEND_CONTAINER" 2>&1 || true)"
		if [[ "$backend_worker_log" == *"Pipeline workers started"* ]]; then
			pass "pipeline workers evidenced in backend logs (main.py:794 line)"
		else
			fail "worker line '$WORKER_LOG_PATTERN' not in backend logs — check LOG_LEVEL=INFO in .env and recreate backend"
		fi

		# Readiness: 200 direct (API_PORT from .env; 8001 on this host) AND proxied
		# through the frontend nginx (:8080). /health 503-degraded is NOT a failure.
		if [ "$(curl -s -o /dev/null -w '%{http_code}' "localhost:${api_port}/api/system/health/ready" 2>/dev/null || true)" = "200" ]; then
			pass "/api/system/health/ready = 200 direct (localhost:$api_port)"
		else
			fail "/api/system/health/ready not 200 direct on localhost:$api_port"
		fi
		if [ "$(curl -s -o /dev/null -w '%{http_code}' "localhost:${fe_port}/api/system/health/ready" 2>/dev/null || true)" = "200" ]; then
			pass "/api/system/health/ready = 200 proxied through frontend (localhost:$fe_port)"
		else
			fail "/api/system/health/ready not 200 proxied on localhost:$fe_port"
		fi

		# /health: record the DESIGN-EXPECTED 503-degraded; a 200 here would mean AI
		# services are up (unexpected in M1) — recorded, not gated either way.
		local health_code
		health_code="$(curl -s -o /dev/null -w '%{http_code}' "localhost:${api_port}/api/system/health" 2>/dev/null || true)"
		case "$health_code" in
			503) pass "/api/system/health = 503-degraded (M1 design: AI services deferred, DB/Redis green in body)" ;;
			200) pass "/api/system/health = 200 (AI services present — NOT expected in M1; recorded)" ;;
			*) fail "/api/system/health unexpected code $health_code (expected 503-degraded by M1 design)" ;;
		esac
	fi

	# --- 5. Frontend: nginx health + SSL redirect (301 on / is DESIGN — do not "fix") ---
	banner "gate: frontend"
	local fe_running
	fe_running="$(podman ps -q --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.service=frontend" || true)"
	if [ -z "$fe_running" ]; then
		fail "frontend container not running (phase-b not started on this host?)"
	else
		if [ "$(curl -s -o /dev/null -w '%{http_code}' "localhost:${fe_port}/health" 2>/dev/null || true)" = "200" ]; then
			pass "frontend /health on :$fe_port"
		else
			fail "frontend /health on :$fe_port not 200"
		fi
		local root_code
		root_code="$(curl -s -o /dev/null -w '%{http_code}' "localhost:${fe_port}/" 2>/dev/null || true)"
		case "$root_code" in
			301) pass "/ = 301 (SSL_ENABLED=true design — HTTP→HTTPS redirect; do not 'fix')" ;;
			200) pass "/ = 200 (SSL redirect disabled in this .env; recorded)" ;;
			*) fail "/ unexpected code $root_code (expected 301 by SSL_ENABLED design)" ;;
		esac
	fi

	# --- 6. Log scan (--tail=50, per-service, classification not grep-and-pray) ---
	# Spec §6: "no error logs in --tail=50 across services". Literal substring grep is
	# unusable here (INFO lines legitimately contain the word "ERROR" — grafana/loki
	# alerting queries), so the gate matches structured error emissions only and
	# applies the ledger's known-benign classes:
	#   alertmanager "Notify for alerts failed ... lookup backend"  — backend down
	#     (pre-phase-b) or AI-degraded alerts; resolves after bring-up (ledger Phase A)
	#   node-exporter "write: broken pipe"                          — its own HTTP healthcheck
	#     scraping :9100 (self-scrape teardown race)
	#   alloy "...pyroscope.ebpf.native_profiling... MEMLOCK"       — eBPF under rootless,
	#     expected without BPF privileges (ledger Phase A, M2 territory); message text
	#     varies ("failed/too many errors starting profiling session"), so the filter
	#     anchors on the component id, which is stable.
	#   postgres "redo in progress|not yet accepting connections"   — crash-recovery replay
	#     in progress (transient); flips healthy when replay finishes (observed live)
	# Anything else is a genuine finding → FAIL.
	banner "gate: log scan (tail=50 per service)"
	local name errlog
	while IFS=$'\t' read -r svc state; do
		[ -n "$svc" ] || continue
		[ "$state" != "exited" ] || continue # one-shot: empty log expected (chown || true)
		name="$(podman ps -aq --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.service=$svc" | head -n1)"
		[ -n "$name" ] || continue
		errlog="$(podman logs --tail=50 "$name" 2>&1 |
			grep -E 'level=(error|fatal)|level=fatal|FATAL|Traceback|panic' |
			grep -vE 'Notify for alerts failed|write: broken pipe|pyroscope\.ebpf\.native_profiling|redo in progress|not yet accepting connections' || true)"
		if [ -n "$errlog" ]; then
			printf 'FAIL: %s: unexpected error lines in tail=50 (first 2):\n%s\n' "$svc" "$(printf '%s\n' "$errlog" | head -n 2 | sed 's/^/  /')" >&2
			FAIL=$((FAIL + 1))
			FAILURES+=("$svc log scan")
		else
			pass "$svc: log scan clean (or only known-benign classes)"
		fi
	done <<<"$(printf '%s\n' "$services_json" | jq -r 'select(.State != "exited") | [.Service, .State] | @tsv' | sort)"

	# --- Summary ---
	banner "gate summary"
	if [ "$FAIL" -eq 0 ]; then
		echo "GATE: PASS ($PASS checks passed)"
		return 0
	else
		echo "GATE: FAIL ($PASS passed, $FAIL failed):"
		local f
		for f in "${FAILURES[@]}"; do
			echo "  - $f"
		done
		return 1
	fi
}

# ---------------------------------------------------------------------------
# probe: P0/P1/P2 record-only probes (spec §4 steps 1-3; non-gating, append Probe Log)
# ---------------------------------------------------------------------------
# P0: does the active compose provider parse `!override`? (spec §3.2 decision)
# P1: CDI GPU visibility (M2-relevant info, recorded either way — NOT M1-gating).
#     Uses --device nvidia.com/gpu=all on a stock CUDA arm64 container.
# P2: provider identity + prod-file parse on the untouched prod file.
cmd_probe() {
	banner "probe (P0/P1/P2 — record-only, non-gating)"
	local p0_result p1_result p2_result

	# P0 — `!override` parse, in a disposable dir (never repo state).
	local probe_dir
	probe_dir="$(mktemp -d /tmp/gb300-p0probe.XXXXXX)"
	printf 'services:\n  a:\n    image: busybox\n    depends_on: {b: {condition: service_started}}\n  b: {image: busybox}\n' >"$probe_dir/base.yml"
	printf 'services:\n  a:\n    depends_on: !override\n      c: {condition: service_started}\n  c: {image: busybox}\n' >"$probe_dir/over.yml"
	if (cd "$probe_dir" && podman compose -f base.yml -f over.yml config >/dev/null 2>&1); then
		p0_result="override-parseable-yes"
	else
		p0_result="override-parseable-NO"
	fi
	rm -rf "$probe_dir"
	pass "P0: $p0_result"

	# P1 — CDI GPU visibility (pulls only if the tag is not already in the store).
	if podman run --rm --device nvidia.com/gpu=all docker.io/nvidia/cuda:13.0.0-base-ubuntu24.04 \
		nvidia-smi --query-gpu=name,compute_cap --format=csv >/dev/null 2>&1; then
		p1_result="cdi-gpu-visible"
	else
		p1_result="cdi-gpu-FAILED"
	fi
	pass "P1: $p1_result (record-only; failure is M2-relevant information, not an M1 gate)"

	# P2 — provider identity + prod-file parse. With .env present the as-written
	# command passes; without it, the FAIL is a missing-env artifact, never a compose
	# defect (task-1 forensics).
	if [ -f .env ] && $COMPOSE config -q >/dev/null 2>&1; then
		p2_result="config-ok (with .env)"
	elif $COMPOSE config -q >/dev/null 2>&1; then
		p2_result="config-ok (no .env needed)"
	else
		p2_result="config-FAIL (with .env present — a real parse defect; without .env it is the missing-env artifact)"
	fi
	pass "P2: $p2_result (provider: $(podman compose version 2>/dev/null | head -n1))"

	# Append to the Probe Log (local copy at PROBE_LOG_PATH; the ledger row itself is
	# committed by hand — this is evidence collection, not a repo write).
	{
		echo "| $(date +%Y-%m-%d) | bootstrap-gb300.sh probe rerun (P0/P1/P2) | $(podman compose version 2>/dev/null | head -n1) | P0=$p0_result; P1=$p1_result; P2=$p2_result | record-only; compare with Task 1 rows |"
	} >>"$PROBE_LOG_PATH"
	echo "Probe row appended to $PROBE_LOG_PATH"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
	local cmd="${1:-}"
	require_repo_root

	case "$cmd" in
		require-podman) cmd_require_podman ;;
		env) cmd_env ;;
		phase-a) cmd_phase_a ;;
		phase-b) cmd_phase_b ;;
		gate) cmd_gate ;;
		probe) cmd_probe ;;
		all)
			cmd_require_podman
			cmd_env
			cmd_phase_a
			cmd_phase_b
			cmd_gate
			;;
		*)
			cat >&2 <<EOF
usage: bootstrap-gb300.sh <subcommand>

Subcommands (all idempotent except builds, which are --no-cache by design):
  require-podman   install check only (prints instructions; never apt/sudo)
  env              .env generation + template deltas (skips if .env exists)
  phase-a          infra/media/observability up (15 services, no AI deps)
  phase-b          build + up backend/frontend (--no-deps; frontend needs
                   the direct podman build --ulimit path, see header)
  gate             spec §6 M1 exit-criteria checklist (honest reporting)
  probe            P0/P1/P2 record-only probes, appends to $PROBE_LOG_PATH
  all              require-podman → env → phase-a → phase-b → gate

Two-daemon host: never bare 'docker' (co-resident rootful dockerd holds
dgx-inference-*). API_PORT etc. are read from .env, never hardcoded.
EOF
			exit 2
			;;
	esac
}

main "$@"

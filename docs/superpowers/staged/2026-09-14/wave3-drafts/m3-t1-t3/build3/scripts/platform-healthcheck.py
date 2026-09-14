#!/usr/bin/env python3
"""Exhaustive AI pipeline health check with Nemotron reasoning analysis.

Run in a loop during backfill/seeding to monitor platform health and
AI enrichment quality in real-time.

Usage:
    # Single run (includes DB reasoning + validation report by default)
    uv run python scripts/platform-healthcheck.py

    # Loop every 30s
    uv run python scripts/platform-healthcheck.py --loop 30

    # Skip DB or validation analysis
    uv run python scripts/platform-healthcheck.py --no-db --no-validation

    # Custom validation report path
    uv run python scripts/platform-healthcheck.py --validation-report /path/to/report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Colour helpers (ANSI)
# ---------------------------------------------------------------------------
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _ok(msg: str) -> str:
    return f"{_GREEN}✓{_RESET} {msg}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}⚠{_RESET} {msg}"


def _fail(msg: str) -> str:
    return f"{_RED}✗{_RESET} {msg}"


def _header(msg: str) -> str:
    return f"\n{_BOLD}{_CYAN}{'═' * 60}\n  {msg}\n{'═' * 60}{_RESET}"


def _sub(msg: str) -> str:
    return f"{_BOLD}{msg}{_RESET}"


# ---------------------------------------------------------------------------
# Shell / HTTP helpers
# ---------------------------------------------------------------------------
def _run(cmd: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"


def _curl_json(url: str, timeout: int = 10) -> dict | list | None:
    rc, out = _run(f"curl -s --max-time {timeout} {url}")
    if rc != 0 or not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _curl_text(url: str, timeout: int = 10) -> str | None:
    rc, out = _run(f"curl -s --max-time {timeout} {url}")
    return out if rc == 0 else None


# ===================================================================
# SECTION 1: Container & Infrastructure Health
# ===================================================================
def check_containers() -> list[str]:
    lines = []
    lines.append(_header("CONTAINER STATUS"))

    rc, out = _run("podman ps --format '{{.Names}}|{{.Status}}' --no-trunc")
    if rc != 0:
        lines.append(_fail(f"podman ps failed: {out}"))
        return lines

    containers = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, status = line.split("|", 1)
        containers[name] = status

    healthy = sum(1 for s in containers.values() if "healthy" in s.lower())
    running = len(containers)
    lines.append(f"  Containers: {running} running, {healthy} healthy")

    for name, status in sorted(containers.items()):
        short = name.replace("nemotron-v3-home-security-intelligence_", "").replace("_1", "")
        if "healthy" in status.lower():
            lines.append(f"    {_ok(f'{short:35s}')} {_DIM}{status}{_RESET}")
        elif "starting" in status.lower():
            lines.append(f"    {_warn(f'{short:35s}')} {status}")
        else:
            lines.append(f"    {_warn(f'{short:35s}')} {status}")
    return lines


# ===================================================================
# SECTION 2: GPU Status
# ===================================================================
def check_gpu() -> list[str]:
    lines = []
    lines.append(_header("GPU STATUS"))
    rc, out = _run(
        "nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory,"
        "memory.used,memory.total,temperature.gpu,power.draw "
        "--format=csv,noheader,nounits"
    )
    if rc != 0:
        lines.append(_fail("nvidia-smi not available"))
        return lines

    parts = [p.strip() for p in out.split(",")]
    if len(parts) >= 7:
        name, gpu_util, mem_util, mem_used, mem_total, temp, power = parts[:7]
        gpu_pct = int(gpu_util)
        mem_gb = int(mem_used) / 1024
        total_gb = int(mem_total) / 1024
        mem_pct = int(mem_used) / int(mem_total) * 100

        gpu_color = _GREEN if gpu_pct < 80 else (_YELLOW if gpu_pct < 95 else _RED)
        mem_color = _GREEN if mem_pct < 80 else (_YELLOW if mem_pct < 95 else _RED)

        lines.append(f"  {name}")
        lines.append(f"  GPU Utilization:  {gpu_color}{gpu_pct}%{_RESET}")
        lines.append(f"  VRAM:             {mem_color}{mem_gb:.1f} / {total_gb:.1f} GB ({mem_pct:.0f}%){_RESET}")
        lines.append(f"  Temperature:      {temp}°C")
        lines.append(f"  Power:            {power} W")
    return lines


# ===================================================================
# SECTION 3: AI Service Endpoints
# ===================================================================
def check_ai_services() -> list[str]:
    lines = []
    lines.append(_header("AI SERVICE HEALTH"))

    # ai-llm (Nemotron)
    lines.append(_sub("  Nemotron LLM (ai-llm):"))
    health = _curl_json("http://127.0.0.1:8091/health")
    if health and health.get("status") == "ok":
        lines.append(f"    {_ok('Health: OK')}")
    else:
        lines.append(f"    {_fail(f'Health: {health}')}")

    models = _curl_json("http://127.0.0.1:8091/v1/models")
    if models and "data" in models:
        for m in models["data"]:
            name = m.get("id", "?")
            meta = m.get("meta", {})
            params = meta.get("n_params", 0)
            ctx = meta.get("n_ctx_train", 0)
            lines.append(f"    {_ok(f'Model: {name}')}")
            lines.append(f"      Params: {params/1e9:.1f}B  Context: {ctx:,}")

    # llama.cpp slots
    slots = _curl_json("http://127.0.0.1:8091/slots")
    if isinstance(slots, list):
        active = sum(1 for s in slots if s.get("is_processing"))
        idle = len(slots) - active
        lines.append(f"    Slots: {active} active, {idle} idle (total {len(slots)})")

    # ai-gateway (Triton)
    lines.append(_sub("  AI Gateway (Triton):"))
    gw = _curl_json("http://127.0.0.1:8090/health")
    if gw:
        status = gw.get("status", "?")
        loaded = gw.get("models_loaded", "?")
        total = gw.get("models_total", "?")
        models_dict = gw.get("models", {})
        if status == "healthy":
            lines.append(f"    {_ok(f'Status: {status}  Models: {loaded}/{total}')}")
        else:
            lines.append(f"    {_fail(f'Status: {status}  Models: {loaded}/{total}')}")

        failed_models = [k for k, v in models_dict.items() if not v]
        if failed_models:
            lines.append(f"    {_fail(f'Failed models: {failed_models}')}")
    else:
        lines.append(f"    {_fail('Gateway unreachable')}")

    # Backend
    lines.append(_sub("  Backend:"))
    bh = _curl_json("http://127.0.0.1:8000/health")
    if bh and bh.get("status") == "alive":
        lines.append(f"    {_ok('Status: alive')}")
    else:
        lines.append(f"    {_fail(f'Status: {bh}')}")

    return lines


# ===================================================================
# SECTION 4: Pipeline Data Flow
# ===================================================================
def check_pipeline() -> list[str]:
    lines = []
    lines.append(_header("PIPELINE DATA FLOW"))

    # Redis streams
    for stream in ["detections:stream", "analysis:stream"]:
        rc, out = _run(
            f"podman exec nemotron-v3-home-security-intelligence_redis_1 "
            f"redis-cli XLEN {stream}"
        )
        count = out.strip() if rc == 0 else "ERR"
        lines.append(f"  {stream:30s} depth = {count}")

    # Redis DLQ
    for dlq in ["detections:dlq", "analysis:dlq"]:
        rc, out = _run(
            f"podman exec nemotron-v3-home-security-intelligence_redis_1 "
            f"redis-cli XLEN {dlq}"
        )
        count = out.strip() if rc == 0 else "N/A"
        if count not in ("N/A", "0", "(integer) 0"):
            lines.append(f"  {_warn(f'{dlq:30s} depth = {count}')}")
        else:
            lines.append(f"  {dlq:30s} depth = 0")

    # Events count
    events = _curl_json("http://127.0.0.1:8000/api/events?limit=1")
    if events and "pagination" in events:
        total = events["pagination"].get("total", "?")
        lines.append(f"  Events in database:              {total}")

    return lines


# ===================================================================
# SECTION 5: Circuit Breaker Status
# ===================================================================
def check_circuit_breakers() -> list[str]:
    lines = []
    lines.append(_header("CIRCUIT BREAKERS & ERROR RATES"))

    rc, out = _run(
        "podman logs --since 60s nemotron-v3-home-security-intelligence_backend_1 2>&1"
    )
    if rc != 0:
        lines.append(_warn("Could not read backend logs"))
        return lines

    cb_pattern = re.compile(r"CircuitBreaker '(\w+)' transitioned (\S+)")
    open_breakers = set()
    for match in cb_pattern.finditer(out):
        name, state = match.groups()
        if "OPEN" in state.upper() and "HALF" not in state.upper():
            open_breakers.add(name)

    cb_open_count = out.count("circuit breaker is open")
    e503_count = out.count("503")
    timeout_count = out.lower().count("timeout")

    if open_breakers:
        for cb in sorted(open_breakers):
            lines.append(f"  {_warn(f'OPEN: {cb}')}")
    else:
        lines.append(f"  {_ok('All circuit breakers closed')}")

    lines.append(f"  503 errors (last 60s):   {e503_count}")
    lines.append(f"  Timeouts (last 60s):     {timeout_count}")
    lines.append(f"  CB rejections (last 60s): {cb_open_count}")

    return lines


# ===================================================================
# SECTION 6: Monitoring Stack
# ===================================================================
def check_monitoring() -> list[str]:
    lines = []
    lines.append(_header("MONITORING STACK"))

    # Prometheus targets
    targets = _curl_json("http://127.0.0.1:9090/api/v1/targets")
    if targets:
        active = targets.get("data", {}).get("activeTargets", [])
        up = sum(1 for t in active if t.get("health") == "up")
        down = sum(1 for t in active if t.get("health") == "down")
        total = len(active)
        if down == 0:
            lines.append(f"  {_ok(f'Prometheus: {up}/{total} targets UP')}")
        else:
            lines.append(f"  {_warn(f'Prometheus: {up}/{total} UP, {down} DOWN')}")
            for t in active:
                if t.get("health") == "down":
                    job = t.get("labels", {}).get("job", "?")
                    lines.append(f"    {_fail(job)}")
    else:
        lines.append(f"  {_fail('Prometheus unreachable')}")

    # Loki
    loki = _curl_text("http://127.0.0.1:3100/ready")
    lines.append(
        f"  {_ok('Loki: ready')}" if loki and "ready" in loki else f"  {_fail('Loki: not ready')}"
    )

    # Tempo
    tempo = _curl_text("http://127.0.0.1:3200/ready")
    lines.append(
        f"  {_ok('Tempo: ready')}" if tempo and "ready" in tempo else f"  {_fail('Tempo: not ready')}"
    )

    # Pyroscope
    pyro = _curl_text("http://127.0.0.1:4040/ready")
    lines.append(
        f"  {_ok('Pyroscope: ready')}"
        if pyro and "ready" in pyro
        else f"  {_fail('Pyroscope: not ready')}"
    )

    return lines


# ===================================================================
# SECTION 7: Resource Usage
# ===================================================================
def check_resources() -> list[str]:
    lines = []
    lines.append(_header("RESOURCE USAGE (TOP CONSUMERS)"))

    rc, out = _run(
        "podman stats --no-stream --format "
        "'{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}'"
    )
    if rc != 0:
        lines.append(_fail("podman stats failed"))
        return lines

    entries = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        name = parts[0].replace("nemotron-v3-home-security-intelligence_", "").replace("_1", "")
        cpu = parts[1]
        mem = parts[2]
        mem_pct = parts[3]
        try:
            cpu_val = float(cpu.replace("%", ""))
        except ValueError:
            cpu_val = 0
        entries.append((cpu_val, name, cpu, mem, mem_pct))

    entries.sort(reverse=True)
    lines.append(f"  {'Container':35s} {'CPU':>8s}  {'Memory':>25s}  {'Mem%':>6s}")
    lines.append(f"  {'─' * 78}")
    for cpu_val, name, cpu, mem, mem_pct in entries[:10]:
        color = _RED if cpu_val > 80 else (_YELLOW if cpu_val > 40 else "")
        end = _RESET if color else ""
        lines.append(f"  {color}{name:35s} {cpu:>8s}  {mem:>25s}  {mem_pct:>6s}{end}")

    # Disk
    rc, out = _run("df -h / --output=size,used,avail,pcent | tail -1")
    if rc == 0:
        lines.append(f"\n  Disk (root): {out.strip()}")

    return lines


# ===================================================================
# SECTION 8: Nemotron Inference Stats (from llama.cpp /slots)
# ===================================================================
def check_nemotron_inference() -> list[str]:
    lines = []
    lines.append(_header("NEMOTRON INFERENCE PERFORMANCE"))

    # Get recent completion stats from backend logs
    rc, out = _run(
        "podman logs --since 120s nemotron-v3-home-security-intelligence_ai-llm_1 2>&1"
    )
    if rc != 0:
        lines.append(_warn("Cannot read ai-llm logs"))
        return lines

    prompt_rates = []
    gen_rates = []
    total_times = []
    for line in out.splitlines():
        if "prompt eval time" in line:
            m = re.search(r"([\d.]+) tokens per second", line)
            if m:
                prompt_rates.append(float(m.group(1)))
        elif "eval time" in line and "prompt" not in line:
            m = re.search(r"([\d.]+) tokens per second", line)
            if m:
                gen_rates.append(float(m.group(1)))
        elif "total time" in line:
            m = re.search(r"([\d.]+) ms", line)
            if m:
                total_times.append(float(m.group(1)))

    if prompt_rates:
        avg_prompt = sum(prompt_rates) / len(prompt_rates)
        lines.append(f"  Prompt throughput:  {avg_prompt:.0f} tok/s (avg of {len(prompt_rates)} completions)")
    if gen_rates:
        avg_gen = sum(gen_rates) / len(gen_rates)
        lines.append(f"  Generation speed:   {avg_gen:.1f} tok/s (avg of {len(gen_rates)} completions)")
    if total_times:
        avg_total = sum(total_times) / len(total_times) / 1000
        lines.append(f"  Avg completion:     {avg_total:.1f}s")

    if not prompt_rates and not gen_rates:
        lines.append(f"  {_DIM}No recent completions in last 120s{_RESET}")

    # Slot utilization
    slots = _curl_json("http://127.0.0.1:8091/slots")
    if isinstance(slots, list):
        processing = [s for s in slots if s.get("is_processing")]
        lines.append(f"  Active slots:       {len(processing)}/{len(slots)}")
        for s in processing:
            prompt_n = s.get("n_past", 0)
            predicted = s.get("n_predicted", 0)
            lines.append(f"    slot {s.get('id',0)}: {prompt_n} ctx tokens, {predicted} generated")

    return lines


# ===================================================================
# SECTION 9: Validation Report Analysis
# ===================================================================
def analyze_validation_report(report_path: str) -> list[str]:
    lines = []
    lines.append(_header("VALIDATION REPORT ANALYSIS"))

    path = Path(report_path)
    if not path.exists():
        lines.append(f"  {_DIM}Report not yet available: {report_path}{_RESET}")
        lines.append(f"  {_DIM}(will appear after seed --validate completes){_RESET}")
        return lines

    with open(path) as f:
        report = json.load(f)

    generated = report.get("generated_at", "?")
    lines.append(f"  Generated: {generated}")

    # Summary
    s = report.get("summary", {})
    total = s.get("total_scenarios", 0)
    passed = s.get("passed", 0)
    failed = s.get("failed", 0)
    rate = s.get("pass_rate", "?")
    color = _GREEN if failed == 0 else (_YELLOW if passed > failed else _RED)
    lines.append(f"\n  {_sub('Overall')}: {color}{passed}/{total} passed ({rate}){_RESET}")

    # Accuracy dimensions
    dims = report.get("accuracy_dimensions", {})
    lines.append(f"\n  {_sub('Accuracy Dimensions:')}")
    for key, dim in dims.items():
        r = dim.get("rate", "?")
        desc = dim.get("description", "")
        lines.append(f"    {key:25s} {r:>8s}  {_DIM}{desc}{_RESET}")

    # By category
    cats = report.get("by_category", {})
    if cats:
        lines.append(f"\n  {_sub('By Category:')}")
        for cat, data in sorted(cats.items()):
            t = data.get("total", 0)
            p = data.get("passed", 0)
            em = data.get("events_matched", 0)
            dc = data.get("detection_correct", 0)
            sc = data.get("scoring_correct", 0)
            lines.append(
                f"    {cat:15s}  pass={p}/{t}  matched={em}  "
                f"detect={dc}  score={sc}"
            )

    # Enrichment quality
    eq = report.get("enrichment_quality", {})
    if eq:
        lines.append(f"\n  {_sub('Enrichment Quality:')}")
        ps = eq.get("prompt_size", {})
        if ps.get("count"):
            lines.append(
                f"    Prompt size:  avg={ps['avg_chars']} chars "
                f"(~{ps['estimated_avg_tokens']} tokens)  "
                f"min={ps['min_chars']}  max={ps['max_chars']}"
            )
        lat = eq.get("llm_latency_ms", {})
        if lat.get("count"):
            lines.append(
                f"    LLM latency:  avg={lat['avg']}ms  "
                f"p50={lat['p50']}ms  max={lat['max']}ms"
            )
        sections = eq.get("enrichment_sections_coverage", {})
        if sections:
            lines.append(f"    Enrichment sections present:")
            for sec, info in sections.items():
                lines.append(f"      {sec:30s} {info['pct']:>6s} ({info['count']})")

    # Enrichment accuracy by service
    ea = report.get("enrichment_accuracy", {})
    if ea:
        lines.append(f"\n  {_sub('Enrichment Service Accuracy:')}")
        for svc, data in sorted(ea.items()):
            tested = data.get("tested", 0)
            p = data.get("passed", 0)
            f_ = data.get("failed", 0)
            pct = f"{p / tested * 100:.0f}%" if tested else "N/A"
            color = _GREEN if f_ == 0 else (_YELLOW if p > f_ else _RED)
            lines.append(f"    {svc:20s} {color}{p}/{tested} ({pct}){_RESET}")

    # Detection analysis
    da = report.get("detection_analysis", {})
    missed = da.get("most_missed_classes", {})
    detected = da.get("most_detected_classes", {})
    if missed:
        lines.append(f"\n  {_sub('Most Missed YOLO Classes:')}")
        for cls, count in list(missed.items())[:7]:
            lines.append(f"    {_fail(f'{cls:25s} missed {count}x')}")
    if detected:
        lines.append(f"\n  {_sub('Most Detected YOLO Classes:')}")
        for cls, count in list(detected.items())[:7]:
            lines.append(f"    {_ok(f'{cls:25s} detected {count}x')}")

    # Risk calibration analysis
    cal = report.get("risk_calibration", [])
    if cal:
        lines.append(f"\n  {_sub('Risk Score Calibration:')}")
        in_range = sum(1 for c in cal if c.get("in_range"))
        total_cal = len(cal)
        pct = f"{in_range / total_cal * 100:.0f}%" if total_cal else "N/A"
        color = _GREEN if in_range == total_cal else _YELLOW
        lines.append(f"    Scores in expected range: {color}{in_range}/{total_cal} ({pct}){_RESET}")

        # Show worst miscalibrations
        outliers = sorted(
            [c for c in cal if not c.get("in_range")],
            key=lambda x: abs(x["actual"] - (x["expected_min"] + x["expected_max"]) / 2),
            reverse=True,
        )
        if outliers:
            lines.append(f"    Worst miscalibrations:")
            for o in outliers[:5]:
                name = o["scenario"][:35]
                lines.append(
                    f"      {name:35s} actual={o['actual']:3d}  "
                    f"expected=[{o['expected_min']}-{o['expected_max']}]  "
                    f"cat={o['category']}"
                )

    # Failure analysis (focus on reasoning)
    failures = report.get("failures", [])
    if failures:
        reasoning_fails = [
            f for f in failures if any("eason" in e.lower() for e in f.get("errors", []))
        ]
        scoring_fails = [
            f for f in failures if any("score" in e.lower() or "risk" in e.lower() for e in f.get("errors", []))
        ]
        enrichment_fails = [f for f in failures if f.get("enrichment_errors")]
        detection_fails = [
            f for f in failures if any("detect" in e.lower() for e in f.get("errors", []))
        ]

        lines.append(f"\n  {_sub('Failure Breakdown:')}")
        lines.append(f"    Total failures:     {len(failures)}")
        lines.append(f"    Reasoning issues:   {len(reasoning_fails)}")
        lines.append(f"    Scoring issues:     {len(scoring_fails)}")
        lines.append(f"    Enrichment issues:  {len(enrichment_fails)}")
        lines.append(f"    Detection issues:   {len(detection_fails)}")

        if reasoning_fails:
            lines.append(f"\n  {_sub('Reasoning Failures (Nemotron quality):')}")
            for rf in reasoning_fails[:8]:
                name = rf.get("name", rf.get("scenario", "?"))
                cat = rf.get("category", "?")
                errs = [e for e in rf.get("errors", []) if "eason" in e.lower()]
                lines.append(f"    {_fail(f'{name} [{cat}]')}")
                for e in errs[:3]:
                    lines.append(f"      → {e}")

    return lines


# ===================================================================
# SECTION 10: Live DB Reasoning Analysis
# ===================================================================
def analyze_db_reasoning() -> list[str]:
    lines = []
    lines.append(_header("LIVE NEMOTRON REASONING ANALYSIS (from DB)"))

    query = textwrap.dedent("""\
        SELECT
            e.id,
            e.summary,
            e.reasoning,
            e.risk_score,
            e.risk_level,
            e.camera_id,
            length(e.reasoning) AS reasoning_len,
            length(e.llm_prompt) AS prompt_len,
            li.raw_response IS NOT NULL AS has_raw_response,
            jsonb_array_length(COALESCE(li.enrichment_snapshot->'detections', '[]'::jsonb)) AS detection_count,
            li.context_sources,
            li.truncation_log,
            e.started_at
        FROM events e
        LEFT JOIN llm_interactions li ON li.event_id = e.id
        WHERE e.reasoning IS NOT NULL
        ORDER BY e.started_at DESC
        LIMIT 30;
    """)

    rc, out = _run(
        f"podman exec nemotron-v3-home-security-intelligence_postgres_1 "
        f"psql -U security -d security -t -A -F '|' "
        f"-c \"{query}\"",
        timeout=15,
    )
    if rc != 0:
        lines.append(f"  {_warn(f'DB query failed: {out[:120]}')}")
        return lines
    if not out.strip():
        lines.append(f"  {_DIM}No events with reasoning found yet{_RESET}")
        return lines

    rows = []
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 12:
            rows.append(parts)

    if not rows:
        lines.append(f"  {_DIM}No events with reasoning found yet{_RESET}")
        return lines

    lines.append(f"  Analyzed {len(rows)} recent events with Nemotron reasoning\n")

    # Aggregate stats
    reasoning_lengths = []
    prompt_lengths = []
    risk_scores = []
    risk_levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    short_reasoning = 0
    generic_count = 0
    has_enrichment = 0
    truncated = 0

    generic_markers = [
        "no threat indicators detected",
        "routine household environment",
        "normal object detections",
    ]

    for row in rows:
        eid, summary, reasoning, risk_score, risk_level = row[0], row[1], row[2], row[3], row[4]
        r_len = int(row[6]) if row[6] else 0
        p_len = int(row[7]) if row[7] else 0
        det_count = int(row[9]) if row[9] else 0
        context_src = row[10]
        trunc_log = row[11]

        reasoning_lengths.append(r_len)
        if p_len:
            prompt_lengths.append(p_len)
        try:
            risk_scores.append(int(risk_score))
        except (ValueError, TypeError):
            pass
        if risk_level and risk_level in risk_levels:
            risk_levels[risk_level] += 1
        if r_len < 140:
            short_reasoning += 1
        summary_lower = (summary or "").lower()
        if any(m in summary_lower for m in generic_markers):
            generic_count += 1
        if det_count > 0:
            has_enrichment += 1
        if trunc_log and trunc_log not in ("", "null", "None"):
            truncated += 1

    total = len(rows)
    avg_reasoning = sum(reasoning_lengths) / total if total else 0
    avg_prompt = sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0

    lines.append(_sub("  Reasoning Quality:"))
    lines.append(f"    Avg reasoning length:  {avg_reasoning:.0f} chars")
    lines.append(f"    Avg prompt length:     {avg_prompt:.0f} chars (~{avg_prompt/4:.0f} tokens)")
    color = _GREEN if short_reasoning == 0 else _YELLOW
    lines.append(f"    Short reasoning (<140): {color}{short_reasoning}/{total}{_RESET}")
    color = _GREEN if generic_count == 0 else _YELLOW
    lines.append(f"    Generic summaries:     {color}{generic_count}/{total}{_RESET}")
    lines.append(f"    With enrichment data:  {has_enrichment}/{total}")
    if truncated:
        lines.append(f"    {_warn(f'Prompts truncated: {truncated}/{total}')}")

    lines.append(f"\n{_sub('  Risk Score Distribution:')}")
    if risk_scores:
        avg_risk = sum(risk_scores) / len(risk_scores)
        lines.append(f"    Avg score: {avg_risk:.0f}  Min: {min(risk_scores)}  Max: {max(risk_scores)}")
    for level, count in risk_levels.items():
        if count > 0:
            bar = "█" * min(count, 30)
            lines.append(f"    {level:10s} {count:3d} {bar}")

    # Show a few example reasoning snippets
    lines.append(f"\n{_sub('  Recent Reasoning Samples:')}")
    for row in rows[:5]:
        eid, summary, reasoning, risk_score, risk_level, camera = (
            row[0], row[1], row[2], row[3], row[4], row[5],
        )
        r_len = int(row[6]) if row[6] else 0
        summary_trunc = (summary or "")[:80]
        reasoning_trunc = (reasoning or "")[:120]

        score_color = _GREEN if risk_level in ("low",) else (
            _YELLOW if risk_level == "medium" else _RED
        )
        lines.append(
            f"    Event #{eid} | {score_color}risk={risk_score} ({risk_level}){_RESET} "
            f"| camera={camera} | reasoning={r_len} chars"
        )
        lines.append(f"      Summary:   {_DIM}{summary_trunc}{_RESET}")
        lines.append(f"      Reasoning: {_DIM}{reasoning_trunc}...{_RESET}")

    return lines


# ===================================================================
# SECTION 11: Seed Script Progress
# ===================================================================
def check_seed_progress() -> list[str]:
    lines = []
    lines.append(_header("SEED SCRIPT PROGRESS"))

    # Find the most recent terminal file with seed-events in it
    terminals_dir = Path.home() / ".cursor/projects/home-ubuntu/terminals"
    if not terminals_dir.exists():
        lines.append(f"  {_DIM}No terminal files found{_RESET}")
        return lines

    seed_file = None
    for f in sorted(terminals_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            head = f.read_text(errors="replace")[:500]
            if "seed-events" in head:
                seed_file = f
                break
        except OSError:
            continue

    if not seed_file:
        lines.append(f"  {_DIM}No active seed script found{_RESET}")
        return lines

    content = seed_file.read_text(errors="replace")
    tail_lines = content.strip().splitlines()[-15:]

    # Check if still running
    if "running_for_seconds" in content[:500]:
        m = re.search(r"running_for_seconds:\s*(\d+)", content[:500])
        if m:
            secs = int(m.group(1))
            lines.append(f"  Running for: {secs // 60}m {secs % 60}s")

    if "exit_code" in content[-200:]:
        m = re.search(r"exit_code:\s*(\d+)", content[-500:])
        if m:
            code = int(m.group(1))
            if code == 0:
                lines.append(f"  {_ok('Seed script completed successfully')}")
            else:
                lines.append(f"  {_fail(f'Seed script exited with code {code}')}")

    for line in tail_lines:
        line = line.strip()
        if line and not line.startswith("---"):
            lines.append(f"  {_DIM}{line}{_RESET}")

    return lines


# ===================================================================
# Main
# ===================================================================
def run_healthcheck(
    *,
    validation_report: str | None = None,
    include_db: bool = False,
) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{_BOLD}{'━' * 60}")
    print(f"  AI PIPELINE HEALTH CHECK — {timestamp}")
    print(f"{'━' * 60}{_RESET}")

    sections = [
        check_containers,
        check_gpu,
        check_ai_services,
        check_nemotron_inference,
        check_pipeline,
        check_circuit_breakers,
        check_monitoring,
        check_resources,
        check_seed_progress,
    ]

    for section_fn in sections:
        for line in section_fn():
            print(line)

    if include_db:
        for line in analyze_db_reasoning():
            print(line)

    if validation_report:
        for line in analyze_validation_report(validation_report):
            print(line)

    print(f"\n{_DIM}{'─' * 60}{_RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exhaustive AI pipeline health check with Nemotron reasoning analysis",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Re-run every N seconds (0 = single run)",
    )
    parser.add_argument(
        "--validation-report",
        type=str,
        default="data/synthetic/validation_report.json",
        help="Path to validation_report.json from seed --validate (default: data/synthetic/validation_report.json)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip Postgres reasoning analysis",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip validation report analysis",
    )
    args = parser.parse_args()

    include_db = not args.no_db
    validation_report = None if args.no_validation else args.validation_report

    if args.loop > 0:
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{_BOLD}[Iteration {iteration}]{_RESET}")
            try:
                run_healthcheck(
                    validation_report=validation_report,
                    include_db=include_db,
                )
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as e:
                print(f"{_RED}Error: {e}{_RESET}")
            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
    else:
        run_healthcheck(
            validation_report=validation_report,
            include_db=include_db,
        )


if __name__ == "__main__":
    main()

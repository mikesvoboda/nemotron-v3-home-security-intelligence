#!/usr/bin/env python3
"""LLM quantization benchmark: compare risk score accuracy across GGUF quantizations.

Sends standardized security scenarios to Nemotron (via llama.cpp /completion API)
and measures risk score accuracy, tier agreement, throughput, and latency across
different GGUF quantization formats (e.g., Q4_K_M vs IQ4_XS).

The baseline quantization is run first, then each candidate is compared against it.

Usage:
    # Compare IQ4_XS against Q4_K_M baseline
    uv run python scripts/benchmark/llm_quantization_benchmark.py \
        --baseline q4_k_m --candidate iq4_xs

    # Compare multiple candidates
    uv run python scripts/benchmark/llm_quantization_benchmark.py \
        --baseline q4_k_m --candidate iq4_xs q4_k_s q3_k_m

    # Custom LLM endpoint and output directory
    uv run python scripts/benchmark/llm_quantization_benchmark.py \
        --baseline q4_k_m --candidate iq4_xs \
        --llm-url http://localhost:8091 \
        --output results/benchmarks/quantization

    # Increase runs per scenario for statistical significance
    uv run python scripts/benchmark/llm_quantization_benchmark.py \
        --baseline q4_k_m --candidate iq4_xs --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
# These scenarios mirror the categories from data/synthetic/ and
# scripts/seed-events.py (normal / suspicious / threats).  Each scenario
# provides a structured enrichment context that exercises the full risk
# scoring range of the model.

BENCHMARK_SCENARIOS: list[dict[str, Any]] = [
    # ── Normal / Low risk (expected 0-20) ─────────────────────────────
    {
        "id": "normal_delivery",
        "category": "normal",
        "camera_name": "front_door",
        "time_of_day": "14:30",
        "detections": "person (conf 0.92), package (conf 0.85)",
        "description": "Delivery driver dropping off a package at the front door during daytime",
        "expected_risk_range": [0, 20],
        "expected_tier": "low",
    },
    {
        "id": "normal_resident",
        "category": "normal",
        "camera_name": "driveway",
        "time_of_day": "08:15",
        "detections": "person (conf 0.95), car (conf 0.90)",
        "description": "Resident leaving for work in the morning, walking to car in driveway",
        "expected_risk_range": [0, 15],
        "expected_tier": "low",
    },
    {
        "id": "normal_pet",
        "category": "normal",
        "camera_name": "backyard",
        "time_of_day": "16:00",
        "detections": "dog (conf 0.88)",
        "description": "Family dog playing in the backyard during afternoon",
        "expected_risk_range": [0, 10],
        "expected_tier": "low",
    },
    {
        "id": "normal_mail_carrier",
        "category": "normal",
        "camera_name": "front_door",
        "time_of_day": "11:20",
        "detections": "person (conf 0.91)",
        "description": "Mail carrier approaching the mailbox at usual delivery time",
        "expected_risk_range": [0, 15],
        "expected_tier": "low",
    },
    {
        "id": "normal_neighbor_walking",
        "category": "normal",
        "camera_name": "sidewalk",
        "time_of_day": "18:45",
        "detections": "person (conf 0.87)",
        "description": "Neighbor walking past the house on the sidewalk during evening",
        "expected_risk_range": [0, 20],
        "expected_tier": "low",
    },
    # ── Elevated / Suspicious (expected 21-60) ────────────────────────
    {
        "id": "suspicious_loitering",
        "category": "suspicious",
        "camera_name": "front_door",
        "time_of_day": "22:30",
        "detections": "person (conf 0.89)",
        "description": "Unknown person standing near front door for 12 minutes at night, looking around",
        "expected_risk_range": [40, 65],
        "expected_tier": "moderate",
    },
    {
        "id": "suspicious_vehicle_night",
        "category": "suspicious",
        "camera_name": "driveway",
        "time_of_day": "02:15",
        "detections": "car (conf 0.82), person (conf 0.75)",
        "description": "Unknown vehicle parked in driveway at 2 AM with person sitting inside, headlights off",
        "expected_risk_range": [35, 60],
        "expected_tier": "moderate",
    },
    {
        "id": "suspicious_backyard_motion",
        "category": "suspicious",
        "camera_name": "backyard",
        "time_of_day": "01:45",
        "detections": "person (conf 0.72)",
        "description": "Motion detected in backyard at 1:45 AM, person partially visible near fence",
        "expected_risk_range": [45, 70],
        "expected_tier": "moderate",
    },
    {
        "id": "suspicious_clipboard_visitors",
        "category": "suspicious",
        "camera_name": "front_door",
        "time_of_day": "13:00",
        "detections": "person (conf 0.93), person (conf 0.91)",
        "description": "Two unknown people approaching front door together, one carrying a clipboard, daytime",
        "expected_risk_range": [15, 40],
        "expected_tier": "elevated",
    },
    {
        "id": "suspicious_garage_inspection",
        "category": "suspicious",
        "camera_name": "garage",
        "time_of_day": "23:15",
        "detections": "person (conf 0.78)",
        "description": "Person walking along the side of the house and peering into garage windows at night",
        "expected_risk_range": [50, 75],
        "expected_tier": "high",
    },
    # ── Threats / High-Critical risk (expected 61-100) ────────────────
    {
        "id": "threat_forced_entry",
        "category": "threats",
        "camera_name": "front_door",
        "time_of_day": "03:30",
        "detections": "person (conf 0.91)",
        "description": "Person attempting to force open the front door at 3:30 AM, pulling on door handle aggressively",
        "expected_risk_range": [75, 100],
        "expected_tier": "critical",
    },
    {
        "id": "threat_window_break",
        "category": "threats",
        "camera_name": "side_yard",
        "time_of_day": "02:00",
        "detections": "person (conf 0.86)",
        "description": "Person breaking a side window with a tool at 2 AM, glass fragments visible",
        "expected_risk_range": [80, 100],
        "expected_tier": "critical",
    },
    {
        "id": "threat_package_theft",
        "category": "threats",
        "camera_name": "front_door",
        "time_of_day": "15:30",
        "detections": "person (conf 0.90), package (conf 0.80)",
        "description": "Person taking a delivery package from the porch and quickly walking away",
        "expected_risk_range": [65, 90],
        "expected_tier": "high",
    },
    {
        "id": "threat_vandalism",
        "category": "threats",
        "camera_name": "garage",
        "time_of_day": "00:45",
        "detections": "person (conf 0.84)",
        "description": "Person spray-painting graffiti on the garage door at night",
        "expected_risk_range": [65, 85],
        "expected_tier": "high",
    },
    {
        "id": "threat_vehicle_breakin",
        "category": "threats",
        "camera_name": "driveway",
        "time_of_day": "04:00",
        "detections": "person (conf 0.81), car (conf 0.88)",
        "description": "Person checking car door handles in the driveway at 4 AM, flashlight visible",
        "expected_risk_range": [65, 85],
        "expected_tier": "high",
    },
]

# Risk tier boundaries (consistent with backend/services/prompts.py)
TIER_BOUNDARIES = {
    "low": (0, 20),
    "elevated": (21, 40),
    "moderate": (41, 60),
    "high": (61, 80),
    "critical": (81, 100),
}


def score_to_tier(score: int) -> str:
    """Map a 0-100 risk score to its tier name."""
    for tier, (lo, hi) in TIER_BOUNDARIES.items():
        if lo <= score <= hi:
            return tier
    return "critical" if score > 100 else "low"


# ---------------------------------------------------------------------------
# Prompt builder  (mirrors backend/services/prompts.py RISK_ANALYSIS_PROMPT)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a home security analyst for a residential property.\n"
    "\n"
    "CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,\n"
    "delivery workers, and pets represent normal household activity. Your job is to\n"
    "identify genuine anomalies, not flag everyday life.\n"
    "\n"
    "SCORE CALIBRATION:\n"
    "- 0-20 (LOW): Routine activity (deliveries, residents, pets, maintenance)\n"
    "- 21-40 (ELEVATED): Unusual but likely benign (unknown visitors at reasonable hours)\n"
    "- 41-60 (MODERATE): Suspicious, requires attention (loitering 10+ min, unusual hours)\n"
    "- 61-80 (HIGH): Clear threat indicators (trespassing, aggressive behavior, tampering, property crimes)\n"
    "- 81-100 (CRITICAL): Active threat (weapons, forced entry, violence, active theft/vandalism)\n"
    "\n"
    "IMPORTANT: Default to LOWER scores without clear threat indicators.\n"
    "EXCEPTION: Property crimes (theft, vandalism, breaking & entering) are ALWAYS scored 60+ as they are criminal acts.\n"
    "\n"
    "Output ONLY valid JSON. No preamble, no explanation."
)


def build_prompt(scenario: dict[str, Any]) -> str:
    """Build a llama.cpp-compatible prompt string for a benchmark scenario.

    Uses the same ChatML token structure as the production prompt
    (RISK_ANALYSIS_PROMPT in backend/services/prompts.py).
    """
    user_content = (
        f"## EVENT CONTEXT\n"
        f"Camera: {scenario['camera_name']}\n"
        f"Time: {scenario['time_of_day']}\n"
        f"\n"
        f"## DETECTIONS\n"
        f"{scenario['detections']}\n"
        f"\n"
        f"## DESCRIPTION\n"
        f"{scenario['description']}\n"
        f"\n"
        f"## YOUR TASK\n"
        f"Analyze this security event and provide a risk assessment.\n"
        f"Risk levels: low (0-20), elevated (21-40), moderate (41-60), "
        f"high (61-80), critical (81-100)\n"
        f"\n"
        f'Output JSON: {{"risk_score": N, "risk_level": "level", '
        f'"summary": "1-2 sentence summary", '
        f'"reasoning": "detailed explanation"}}'
    )
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_content}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """Result of running a single scenario against the LLM."""

    scenario_id: str
    category: str
    expected_tier: str
    expected_risk_range: list[int]
    risk_score: int | None = None
    risk_level: str | None = None
    summary: str | None = None
    reasoning: str | None = None
    tokens_per_sec: float = 0.0
    time_to_first_token_ms: float = 0.0
    total_time_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    raw_response: str = ""


@dataclass
class QuantizationRunResult:
    """Aggregate results for one quantization format."""

    quantization: str
    scenario_results: list[ScenarioResult] = field(default_factory=list)
    timestamp: str = ""

    # Computed metrics (populated by compute_metrics)
    mean_risk_score_mad: float = 0.0
    tier_agreement_rate: float = 0.0
    mean_tokens_per_sec: float = 0.0
    mean_time_to_first_token_ms: float = 0.0
    mean_total_time_ms: float = 0.0
    valid_response_rate: float = 0.0
    json_parse_rate: float = 0.0

    def compute_metrics(self, baseline: QuantizationRunResult | None = None) -> None:
        """Compute aggregate metrics from individual scenario results.

        Args:
            baseline: If provided, MAD is computed against baseline scores.
                      If None, MAD is computed against expected_risk_range midpoints.
        """
        valid = [r for r in self.scenario_results if r.risk_score is not None]
        total = len(self.scenario_results)

        if not total:
            return

        self.valid_response_rate = len(valid) / total
        self.json_parse_rate = len(valid) / total

        if valid:
            # Tokens/sec and latency
            tps_values = [r.tokens_per_sec for r in valid if r.tokens_per_sec > 0]
            ttft_values = [r.time_to_first_token_ms for r in valid if r.time_to_first_token_ms > 0]
            total_time_values = [r.total_time_ms for r in valid if r.total_time_ms > 0]

            self.mean_tokens_per_sec = statistics.mean(tps_values) if tps_values else 0.0
            self.mean_time_to_first_token_ms = statistics.mean(ttft_values) if ttft_values else 0.0
            self.mean_total_time_ms = (
                statistics.mean(total_time_values) if total_time_values else 0.0
            )

            # Risk score MAD (mean absolute deviation)
            if baseline is not None:
                # Compare against baseline scores for same scenarios
                baseline_map = {
                    r.scenario_id: r.risk_score
                    for r in baseline.scenario_results
                    if r.risk_score is not None
                }
                deviations = []
                for r in valid:
                    baseline_score = baseline_map.get(r.scenario_id)
                    if baseline_score is not None and r.risk_score is not None:
                        deviations.append(abs(r.risk_score - baseline_score))
                self.mean_risk_score_mad = statistics.mean(deviations) if deviations else 0.0
            else:
                # Compare against midpoint of expected range
                deviations = []
                for r in valid:
                    midpoint = (r.expected_risk_range[0] + r.expected_risk_range[1]) / 2
                    if r.risk_score is not None:
                        deviations.append(abs(r.risk_score - midpoint))
                self.mean_risk_score_mad = statistics.mean(deviations) if deviations else 0.0

            # Tier agreement
            tier_matches = sum(
                1
                for r in valid
                if r.risk_score is not None and score_to_tier(r.risk_score) == r.expected_tier
            )
            self.tier_agreement_rate = tier_matches / len(valid) if valid else 0.0


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

_JSON_PATTERN = re.compile(r"\{[^{}]*\}")


def parse_risk_json(text: str) -> dict[str, Any] | None:
    """Extract and parse the first JSON object from LLM output.

    Handles common issues like markdown fences and think blocks.
    """
    # Strip <think>...</think> blocks if present
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Strip markdown fences
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*", "", cleaned)

    # Try to find a JSON object
    match = _JSON_PATTERN.search(cleaned)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict) and "risk_score" in data:
            return data
    except json.JSONDecodeError:
        pass

    return None


async def send_completion(
    client: httpx.AsyncClient,
    llm_url: str,
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Send a /completion request to llama.cpp and return the raw response dict.

    Args:
        client: httpx async client
        llm_url: Base URL of the llama.cpp server (e.g., http://localhost:8091)
        prompt: Full prompt string (with ChatML tokens)
        max_tokens: Maximum output tokens
        temperature: Sampling temperature (low for reproducibility)

    Returns:
        Raw JSON response from llama.cpp /completion endpoint
    """
    payload = {
        "prompt": prompt,
        "temperature": temperature,
        "top_p": 0.95,
        "max_tokens": max_tokens,
        "stop": ["<|im_end|>", "<|im_start|>"],
    }
    response = await client.post(
        f"{llm_url}/completion",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


async def run_scenario(
    client: httpx.AsyncClient,
    llm_url: str,
    scenario: dict[str, Any],
) -> ScenarioResult:
    """Run a single benchmark scenario and return the result."""
    result = ScenarioResult(
        scenario_id=scenario["id"],
        category=scenario["category"],
        expected_tier=scenario["expected_tier"],
        expected_risk_range=scenario["expected_risk_range"],
    )

    prompt = build_prompt(scenario)

    try:
        wall_start = time.perf_counter()
        llm_response = await send_completion(client, llm_url, prompt)
        wall_ms = (time.perf_counter() - wall_start) * 1000

        # Extract llama.cpp timing fields
        content = llm_response.get("content", "")
        result.raw_response = content
        result.total_time_ms = wall_ms

        # llama.cpp /completion returns timings in the response
        timings = llm_response.get("timings", {})
        if timings:
            # predicted_per_second = tokens/sec for generation
            result.tokens_per_sec = timings.get("predicted_per_second", 0.0)
            # prompt_ms = time to process prompt (approximation of TTFT)
            result.time_to_first_token_ms = timings.get("prompt_ms", 0.0)
            result.prompt_tokens = timings.get("prompt_n", 0)
            result.completion_tokens = timings.get("predicted_n", 0)
        else:
            # Fallback: estimate from wall time
            tokens = llm_response.get("tokens_predicted", 0)
            if tokens and wall_ms > 0:
                result.tokens_per_sec = tokens / (wall_ms / 1000)
            result.completion_tokens = tokens

        # Parse the risk assessment JSON
        parsed = parse_risk_json(content)
        if parsed:
            score = parsed.get("risk_score")
            if isinstance(score, int | float):
                result.risk_score = int(max(0, min(100, score)))
            result.risk_level = parsed.get("risk_level", "")
            result.summary = parsed.get("summary", "")
            result.reasoning = parsed.get("reasoning", "")
        else:
            result.error = "Failed to parse JSON from LLM response"

    except httpx.HTTPStatusError as e:
        result.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except httpx.ConnectError as e:
        result.error = f"Connection error: {e}"
    except httpx.TimeoutException:
        result.error = "Request timed out (120s)"
    except Exception as e:
        result.error = f"Unexpected error: {type(e).__name__}: {e}"

    return result


async def run_quantization(
    llm_url: str,
    quantization_name: str,
    scenarios: list[dict[str, Any]],
    runs: int = 1,
) -> QuantizationRunResult:
    """Run all benchmark scenarios for a given quantization.

    Args:
        llm_url: Base URL of the llama.cpp server
        quantization_name: Human-readable quantization name (e.g., "q4_k_m")
        scenarios: List of scenario dicts to benchmark
        runs: Number of times to run each scenario (for averaging)

    Returns:
        QuantizationRunResult with all scenario results
    """
    run_result = QuantizationRunResult(
        quantization=quantization_name,
        timestamp=datetime.now(UTC).isoformat(),
    )

    async with httpx.AsyncClient() as client:
        # Verify LLM is reachable
        try:
            health = await client.get(f"{llm_url}/health", timeout=10.0)
            if health.status_code != 200:
                print(f"  WARNING: LLM health check returned {health.status_code}")
        except httpx.ConnectError:
            print(f"  ERROR: Cannot connect to LLM at {llm_url}")
            print("  Make sure the llama.cpp server is running with the correct model loaded.")
            return run_result

        for scenario in scenarios:
            all_results: list[ScenarioResult] = []
            for _run_idx in range(runs):
                r = await run_scenario(client, llm_url, scenario)
                all_results.append(r)

            # If multiple runs, pick the result with median risk score
            if runs > 1:
                valid_results = [r for r in all_results if r.risk_score is not None]
                if valid_results:
                    valid_results.sort(key=lambda x: x.risk_score or 0)
                    median_idx = len(valid_results) // 2
                    best = valid_results[median_idx]
                    # Average the timing metrics
                    best.tokens_per_sec = statistics.mean(
                        [r.tokens_per_sec for r in valid_results if r.tokens_per_sec > 0] or [0]
                    )
                    best.time_to_first_token_ms = statistics.mean(
                        [
                            r.time_to_first_token_ms
                            for r in valid_results
                            if r.time_to_first_token_ms > 0
                        ]
                        or [0]
                    )
                    best.total_time_ms = statistics.mean(
                        [r.total_time_ms for r in valid_results if r.total_time_ms > 0] or [0]
                    )
                    run_result.scenario_results.append(best)
                else:
                    run_result.scenario_results.append(all_results[0])
            else:
                run_result.scenario_results.append(all_results[0])

            # Progress indicator
            r = run_result.scenario_results[-1]
            status = f"score={r.risk_score}" if r.risk_score is not None else f"ERROR: {r.error}"
            print(f"  [{scenario['id']}] {status}")

    return run_result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def generate_json_report(
    baseline: QuantizationRunResult,
    candidates: list[QuantizationRunResult],
) -> dict[str, Any]:
    """Generate a JSON-serializable benchmark report."""
    report: dict[str, Any] = {
        "benchmark": "llm_quantization_comparison",
        "timestamp": datetime.now(UTC).isoformat(),
        "baseline": {
            "quantization": baseline.quantization,
            "metrics": {
                "mean_risk_score_mad": round(baseline.mean_risk_score_mad, 2),
                "tier_agreement_rate": round(baseline.tier_agreement_rate * 100, 1),
                "mean_tokens_per_sec": round(baseline.mean_tokens_per_sec, 1),
                "mean_time_to_first_token_ms": round(baseline.mean_time_to_first_token_ms, 1),
                "mean_total_time_ms": round(baseline.mean_total_time_ms, 1),
                "valid_response_rate": round(baseline.valid_response_rate * 100, 1),
            },
            "scenarios": [
                {
                    "id": r.scenario_id,
                    "category": r.category,
                    "expected_tier": r.expected_tier,
                    "expected_risk_range": r.expected_risk_range,
                    "risk_score": r.risk_score,
                    "risk_level": r.risk_level,
                    "actual_tier": score_to_tier(r.risk_score)
                    if r.risk_score is not None
                    else None,
                    "tokens_per_sec": round(r.tokens_per_sec, 1),
                    "time_to_first_token_ms": round(r.time_to_first_token_ms, 1),
                    "total_time_ms": round(r.total_time_ms, 1),
                    "error": r.error,
                }
                for r in baseline.scenario_results
            ],
        },
        "candidates": [],
    }

    for cand in candidates:
        report["candidates"].append(
            {
                "quantization": cand.quantization,
                "metrics": {
                    "mean_risk_score_mad_vs_baseline": round(cand.mean_risk_score_mad, 2),
                    "tier_agreement_rate": round(cand.tier_agreement_rate * 100, 1),
                    "mean_tokens_per_sec": round(cand.mean_tokens_per_sec, 1),
                    "mean_time_to_first_token_ms": round(cand.mean_time_to_first_token_ms, 1),
                    "mean_total_time_ms": round(cand.mean_total_time_ms, 1),
                    "valid_response_rate": round(cand.valid_response_rate * 100, 1),
                },
                "scenarios": [
                    {
                        "id": r.scenario_id,
                        "category": r.category,
                        "expected_tier": r.expected_tier,
                        "expected_risk_range": r.expected_risk_range,
                        "risk_score": r.risk_score,
                        "risk_level": r.risk_level,
                        "actual_tier": score_to_tier(r.risk_score)
                        if r.risk_score is not None
                        else None,
                        "tokens_per_sec": round(r.tokens_per_sec, 1),
                        "time_to_first_token_ms": round(r.time_to_first_token_ms, 1),
                        "total_time_ms": round(r.total_time_ms, 1),
                        "error": r.error,
                    }
                    for r in cand.scenario_results
                ],
            }
        )

    return report


def generate_markdown_report(
    baseline: QuantizationRunResult,
    candidates: list[QuantizationRunResult],
) -> str:
    """Generate a markdown comparison table."""
    lines: list[str] = [
        "# LLM Quantization Benchmark Results",
        "",
        f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Baseline:** {baseline.quantization}",
        f"**Candidates:** {', '.join(c.quantization for c in candidates)}",
        f"**Scenarios:** {len(BENCHMARK_SCENARIOS)}",
        "",
        "## Summary",
        "",
        "| Quantization | MAD vs Baseline | Tier Agreement | Tokens/sec | TTFT (ms) | Total Time (ms) | Valid % |",
        "|---|---|---|---|---|---|---|",
    ]

    # Baseline row (MAD vs expected midpoints)
    lines.append(
        f"| **{baseline.quantization}** (baseline) "
        f"| {baseline.mean_risk_score_mad:.1f} (vs expected) "
        f"| {baseline.tier_agreement_rate * 100:.0f}% "
        f"| {baseline.mean_tokens_per_sec:.1f} "
        f"| {baseline.mean_time_to_first_token_ms:.0f} "
        f"| {baseline.mean_total_time_ms:.0f} "
        f"| {baseline.valid_response_rate * 100:.0f}% |"
    )

    for cand in candidates:
        lines.append(
            f"| {cand.quantization} "
            f"| {cand.mean_risk_score_mad:.1f} "
            f"| {cand.tier_agreement_rate * 100:.0f}% "
            f"| {cand.mean_tokens_per_sec:.1f} "
            f"| {cand.mean_time_to_first_token_ms:.0f} "
            f"| {cand.mean_total_time_ms:.0f} "
            f"| {cand.valid_response_rate * 100:.0f}% |"
        )

    # Per-scenario breakdown
    lines.extend(
        [
            "",
            "## Per-Scenario Comparison",
            "",
            "| Scenario | Category | Expected | "
            + " | ".join([f"{baseline.quantization}"] + [c.quantization for c in candidates])
            + " |",
            "|---|---|---|" + "|".join(["---"] * (1 + len(candidates))) + "|",
        ]
    )

    for i, scenario in enumerate(BENCHMARK_SCENARIOS):
        row_parts = [
            f"| {scenario['id']}",
            f"| {scenario['category']}",
            f"| {scenario['expected_tier']} ({scenario['expected_risk_range'][0]}-{scenario['expected_risk_range'][1]})",
        ]

        # Baseline score
        if i < len(baseline.scenario_results):
            br = baseline.scenario_results[i]
            score_str = str(br.risk_score) if br.risk_score is not None else "ERR"
            tier = score_to_tier(br.risk_score) if br.risk_score is not None else "?"
            row_parts.append(f"| {score_str} ({tier})")
        else:
            row_parts.append("| N/A")

        # Candidate scores
        for cand in candidates:
            if i < len(cand.scenario_results):
                cr = cand.scenario_results[i]
                score_str = str(cr.risk_score) if cr.risk_score is not None else "ERR"
                tier = score_to_tier(cr.risk_score) if cr.risk_score is not None else "?"
                # Mark disagreement with baseline
                if (
                    br.risk_score is not None
                    and cr.risk_score is not None
                    and abs(cr.risk_score - br.risk_score) > 15
                ):
                    score_str += " (!)"
                row_parts.append(f"| {score_str} ({tier})")
            else:
                row_parts.append("| N/A")

        row_parts.append("|")
        lines.append(" ".join(row_parts))

    # Throughput comparison
    lines.extend(
        [
            "",
            "## Throughput Comparison",
            "",
            "| Quantization | Tokens/sec | TTFT (ms) | Avg Total (ms) |",
            "|---|---|---|---|",
        ]
    )
    lines.append(
        f"| {baseline.quantization} "
        f"| {baseline.mean_tokens_per_sec:.1f} "
        f"| {baseline.mean_time_to_first_token_ms:.0f} "
        f"| {baseline.mean_total_time_ms:.0f} |"
    )
    for cand in candidates:
        tps_delta = ""
        if baseline.mean_tokens_per_sec > 0:
            pct = (
                (cand.mean_tokens_per_sec - baseline.mean_tokens_per_sec)
                / baseline.mean_tokens_per_sec
            ) * 100
            tps_delta = f" ({pct:+.1f}%)"
        lines.append(
            f"| {cand.quantization} "
            f"| {cand.mean_tokens_per_sec:.1f}{tps_delta} "
            f"| {cand.mean_time_to_first_token_ms:.0f} "
            f"| {cand.mean_total_time_ms:.0f} |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark LLM quantization quality: compare risk score accuracy across GGUF quantizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --baseline q4_k_m --candidate iq4_xs\n"
            "  %(prog)s --baseline q4_k_m --candidate iq4_xs q4_k_s --runs 3\n"
            "  %(prog)s --baseline q4_k_m --candidate iq4_xs --llm-url http://localhost:8091\n"
        ),
    )
    parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Baseline quantization name (e.g., q4_k_m). The LLM server must be "
        "running with this quantization loaded when the benchmark starts.",
    )
    parser.add_argument(
        "--candidate",
        type=str,
        nargs="+",
        required=True,
        help="Candidate quantization name(s) to compare against the baseline "
        "(e.g., iq4_xs q4_k_s). NOTE: The benchmark assumes each candidate "
        "is loaded separately. If running a single server, restart with the "
        "candidate model between runs and use --candidate with one name at a time.",
    )
    parser.add_argument(
        "--llm-url",
        type=str,
        default="http://localhost:8091",
        help="Base URL of the llama.cpp server (default: http://localhost:8091)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/benchmarks/quantization"),
        help="Output directory for results (default: results/benchmarks/quantization)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs per scenario for averaging (default: 1)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output JSON (skip markdown report)",
    )
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> int:
    """Async entry point."""
    print("LLM Quantization Benchmark")
    print(f"{'=' * 50}")
    print(f"Baseline:   {args.baseline}")
    print(f"Candidates: {', '.join(args.candidate)}")
    print(f"LLM URL:    {args.llm_url}")
    print(f"Scenarios:  {len(BENCHMARK_SCENARIOS)}")
    print(f"Runs/scenario: {args.runs}")
    print()

    # Run baseline
    print(f"Running baseline ({args.baseline})...")
    baseline_result = await run_quantization(
        args.llm_url, args.baseline, BENCHMARK_SCENARIOS, runs=args.runs
    )
    baseline_result.compute_metrics(baseline=None)  # Compare vs expected ranges

    if not baseline_result.scenario_results:
        print("ERROR: No results from baseline run. Is the LLM server running?")
        return 1

    # Run candidates
    candidate_results: list[QuantizationRunResult] = []
    for cand_name in args.candidate:
        print(f"\nRunning candidate ({cand_name})...")
        if len(args.candidate) > 1:
            print(f"  NOTE: Ensure the LLM server is loaded with {cand_name} quantization.")
            print("  Press Enter to continue or Ctrl+C to abort...")
            try:
                # In non-interactive environments, just proceed
                if sys.stdin.isatty():
                    input()
            except EOFError:
                pass

        cand_result = await run_quantization(
            args.llm_url, cand_name, BENCHMARK_SCENARIOS, runs=args.runs
        )
        cand_result.compute_metrics(baseline=baseline_result)
        candidate_results.append(cand_result)

    # Generate reports
    print(f"\n{'=' * 50}")
    print("Generating reports...")

    args.output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # JSON report
    json_report = generate_json_report(baseline_result, candidate_results)
    json_path = args.output / f"quantization_benchmark_{timestamp}.json"
    json_path.write_text(json.dumps(json_report, indent=2))
    print(f"  JSON: {json_path}")

    # Markdown report
    if not args.json_only:
        md_report = generate_markdown_report(baseline_result, candidate_results)
        md_path = args.output / f"quantization_benchmark_{timestamp}.md"
        md_path.write_text(md_report)
        print(f"  Markdown: {md_path}")

        # Print summary to stdout
        print()
        print(md_report)

    return 0


def main() -> int:
    """Main entry point."""
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())

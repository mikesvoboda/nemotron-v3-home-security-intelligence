#!/usr/bin/env python3
"""Test script to verify 32K context window capacity and monitor VRAM usage.

This script:
1. Measures baseline VRAM usage
2. Generates a large prompt approaching the context limit
3. Sends it to Nemotron and monitors VRAM during inference
4. Reports token counts and memory statistics
"""

import argparse
import shutil
import subprocess
import sys
import time
from typing import NamedTuple

import httpx


class VRAMStats(NamedTuple):
    used_mb: int
    total_mb: int
    free_mb: int


def get_vram_stats() -> VRAMStats:
    """Get current GPU VRAM statistics."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return VRAMStats(used_mb=0, total_mb=0, free_mb=0)
    result = subprocess.run(
        [
            nvidia_smi,
            "--query-gpu=memory.used,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    parts = result.stdout.strip().split(", ")
    return VRAMStats(used_mb=int(parts[0]), total_mb=int(parts[1]), free_mb=int(parts[2]))


def generate_large_prompt(target_tokens: int) -> str:
    """Generate a prompt with approximately target_tokens tokens.

    Uses a realistic security analysis scenario with repeated detection data.
    Rough estimate: 1 token ~ 4 characters for English text.

    NEM-1095: Uses efficient list.append() + ''.join() pattern instead of
    string concatenation with += which is O(n^2) for large prompts.
    """
    # Use list for efficient string building (O(n) vs O(n^2) for += concatenation)
    prompt_parts: list[str] = []

    prompt_parts.append(
        """You are a home security AI analyst. Analyze the following detection events and provide a risk assessment.

SYSTEM CONTEXT:
- Location: Residential property with 8 cameras
- Time: Evening hours (18:00-22:00)
- Weather: Clear
- Historical baseline: Average 15 person detections per hour, 3 vehicle detections per hour

DETECTION EVENTS:
"""
    )

    # Each detection block is roughly 200 tokens
    detection_template = """
Event #{event_id}:
- Timestamp: 2026-01-01 19:{minute:02d}:{second:02d}
- Camera: {camera}
- Objects detected:
  * Person (confidence: 0.{conf}): bbox [0.{x1}, 0.{y1}, 0.{x2}, 0.{y2}]
  * Vehicle (confidence: 0.{vconf}): type={vtype}, color={color}
- Florence-2 caption: "A {desc} walking near a {vcolor} {vtype} in the driveway"
- Zone: {zone}
- Cross-camera tracking: Entity RE-ID embedding similarity 0.{sim} with camera_{other_cam}
- Enrichment data:
  * Clothing: {clothing}
  * Vehicle segment: {segment}
  * Weather conditions: clear, visibility good
  * Baseline comparison: {baseline}
"""

    cameras = [
        "front_door",
        "driveway",
        "backyard",
        "garage",
        "side_gate",
        "porch",
        "street",
        "garden",
    ]
    vehicle_types = ["sedan", "SUV", "pickup", "van", "motorcycle", "delivery_truck"]
    colors = ["black", "white", "silver", "red", "blue", "gray"]
    clothing = [
        "dark jacket and jeans",
        "light hoodie and shorts",
        "business casual",
        "work uniform",
        "athletic wear",
    ]
    zones = ["entry_zone", "driveway", "perimeter", "high_security", "common_area"]
    baselines = [
        "within normal range",
        "slightly elevated activity",
        "unusual for this time",
        "matches expected pattern",
    ]
    descriptions = ["person", "individual", "figure", "visitor", "delivery worker"]

    event_id = 1

    # Estimate: base_prompt ~100 tokens, each detection ~200 tokens
    # For 30K tokens, we need ~150 detections
    num_detections = (target_tokens - 500) // 200  # Leave room for response

    for i in range(num_detections):
        prompt_parts.append(
            detection_template.format(
                event_id=event_id,
                minute=i % 60,
                second=(i * 7) % 60,
                camera=cameras[i % len(cameras)],
                conf=85 + (i % 10),
                x1=10 + (i % 30),
                y1=20 + (i % 25),
                x2=50 + (i % 30),
                y2=70 + (i % 20),
                vconf=80 + (i % 15),
                vtype=vehicle_types[i % len(vehicle_types)],
                color=colors[i % len(colors)],
                vcolor=colors[(i + 1) % len(colors)],
                desc=descriptions[i % len(descriptions)],
                zone=zones[i % len(zones)],
                sim=75 + (i % 20),
                other_cam=(i + 3) % 8,
                clothing=clothing[i % len(clothing)],
                segment=vehicle_types[i % len(vehicle_types)],
                baseline=baselines[i % len(baselines)],
            )
        )
        event_id += 1

    prompt_parts.append(
        """
ANALYSIS REQUEST:
Based on the above detection events, provide:
1. Overall risk score (0-100)
2. Key risk factors identified
3. Anomalies compared to baseline
4. Recommended actions
5. Cross-camera correlation summary

Be concise but thorough."""
    )

    # Join all parts efficiently in one operation
    return "".join(prompt_parts)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (llama tokenizer averages ~4 chars/token for English)."""
    return len(text) // 4


def test_context_window(  # noqa: PLR0912
    url: str = "http://localhost:8091",
    target_tokens: int = 30000,
    max_new_tokens: int = 500,
    verbose: bool = True,
) -> dict:
    """Test the context window with a large prompt.

    Args:
        url: Nemotron server URL
        target_tokens: Target number of input tokens
        max_new_tokens: Maximum tokens to generate in response
        verbose: Print progress updates

    Returns:
        Dictionary with test results
    """
    results = {
        "success": False,
        "target_tokens": target_tokens,
        "actual_tokens_estimate": 0,
        "prompt_chars": 0,
        "vram_before_mb": 0,
        "vram_during_mb": 0,
        "vram_after_mb": 0,
        "vram_delta_mb": 0,
        "inference_time_s": 0,
        "response_tokens": 0,
        "error": None,
    }

    # Check health first
    if verbose:
        print("Checking Nemotron health...")

    try:
        health = httpx.get(f"{url}/health", timeout=10)
        if health.status_code != 200:
            results["error"] = f"Health check failed: {health.status_code}"
            return results
    except Exception as e:
        results["error"] = f"Connection failed: {e}"
        return results

    if verbose:
        print("✓ Nemotron is healthy")

    # Baseline VRAM
    vram_before = get_vram_stats()
    results["vram_before_mb"] = vram_before.used_mb

    if verbose:
        print(f"\nBaseline VRAM: {vram_before.used_mb} MB / {vram_before.total_mb} MB")

    # Generate large prompt
    if verbose:
        print(f"\nGenerating prompt targeting ~{target_tokens:,} tokens...")

    prompt = generate_large_prompt(target_tokens)
    results["prompt_chars"] = len(prompt)
    results["actual_tokens_estimate"] = estimate_tokens(prompt)

    if verbose:
        print(
            f"✓ Generated prompt: {len(prompt):,} chars (~{results['actual_tokens_estimate']:,} tokens)"
        )

    # Send request
    if verbose:
        print(f"\nSending to Nemotron (max_tokens={max_new_tokens})...")
        print("This may take a while for large contexts...")

    request_body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_new_tokens,
        "temperature": 0.3,
    }

    start_time = time.time()

    try:
        # Monitor VRAM during inference in a simple way
        # (ideally we'd use threading, but keeping it simple)
        response = httpx.post(
            f"{url}/v1/chat/completions",
            json=request_body,
            timeout=300,  # 5 minute timeout for large context
        )

        inference_time = time.time() - start_time
        results["inference_time_s"] = round(inference_time, 2)

        # Check VRAM after (peak usage during inference)
        vram_after = get_vram_stats()
        results["vram_after_mb"] = vram_after.used_mb
        results["vram_during_mb"] = vram_after.used_mb  # Approximate
        results["vram_delta_mb"] = vram_after.used_mb - vram_before.used_mb

        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                response_text = data["choices"][0]["message"]["content"]
                results["response_tokens"] = estimate_tokens(response_text)
                results["success"] = True

                if verbose:
                    print("\n✓ Success!")
                    print(f"  Inference time: {inference_time:.1f}s")
                    print(f"  Response: ~{results['response_tokens']} tokens")
                    print(f"  VRAM delta: {results['vram_delta_mb']:+d} MB")
                    print("\nResponse preview (first 500 chars):")
                    print("-" * 50)
                    print(response_text[:500])
                    print("-" * 50)
            else:
                results["error"] = f"Unexpected response format: {data}"
        else:
            results["error"] = f"Request failed: {response.status_code} - {response.text[:200]}"

    except httpx.TimeoutException:
        results["error"] = "Request timed out (>5 minutes)"
    except Exception as e:
        results["error"] = str(e)

    if results["error"] and verbose:
        print(f"\n✗ Error: {results['error']}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test Nemotron 32K context window")
    parser.add_argument("--url", default="http://localhost:8091", help="Nemotron server URL")
    parser.add_argument(
        "--tokens", type=int, default=30000, help="Target input tokens (default: 30000)"
    )
    parser.add_argument(
        "--max-response", type=int, default=500, help="Max response tokens (default: 500)"
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    print("=" * 60)
    print("Nemotron 32K Context Window Test")
    print("=" * 60)

    results = test_context_window(
        url=args.url,
        target_tokens=args.tokens,
        max_new_tokens=args.max_response,
        verbose=not args.quiet,
    )

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Success:            {results['success']}")
    print(f"Target tokens:      {results['target_tokens']:,}")
    print(f"Actual tokens:      ~{results['actual_tokens_estimate']:,}")
    print(f"Prompt chars:       {results['prompt_chars']:,}")
    print(f"VRAM before:        {results['vram_before_mb']:,} MB")
    print(f"VRAM after:         {results['vram_after_mb']:,} MB")
    print(f"VRAM delta:         {results['vram_delta_mb']:+,} MB")
    print(f"Inference time:     {results['inference_time_s']}s")
    print(f"Response tokens:    ~{results['response_tokens']}")
    if results["error"]:
        print(f"Error:              {results['error']}")
    print("=" * 60)

    # Return exit code based on success
    return 0 if results["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

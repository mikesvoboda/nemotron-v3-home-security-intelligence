#!/usr/bin/env python3
"""S-3 salience re-run on REAL stock imagery (F5), replacing the pillow
placeholder run.

WHY: the first S-3 executed its stated bar on benign scenes but detected
0/4 incidents because the model correctly called the procedural primitives
"stylized minimalist renderings" - placeholder media is not valid salience
evidence. Wikimedia Commons frames (license-clean, attribution beside every
file) are the sanctioned media for this spike.

WHAT: one schema-forced chat call per stock frame (json_schema per S-2,
ENFORCED at this pin), temp 0, bar = verdict for the item's committed label
(benign scenario -> rejected expected; incident scenario -> confirmed).
Emits AGGREGATE metrics only to stdout (privacy rule: per-frame verdicts are
eval data, they land in the off-repo results file, never in git).

Usage: uv run python scripts/vlm_probes/s3_salience_stock.py \
         --base-url http://host.docker.internal:PORT \
         --stock-root /path/out/media/stock --out /path/out/s3_stock/results.json
"""

from __future__ import annotations

import argparse
import base64
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx

# VlmVerdict-shaped core (spec §4) + required const nonce: schema-validity is
# proven, not assumed (the E5 bug class). Ranges are post-validated client-
# side; grammar-level min/max support is unverified at this pin (S-2 note).
PROMPT = (
    "You are a home-security verifier for a doorbell camera. Judge whether "
    "this scene is an incident that a resident should be alerted about, or a "
    "benign everyday scene. Consider context: a delivery driver, resident, "
    "pet, or yard worker doing their normal job is benign; stealth, forced "
    "entry, theft, vandalism, or a visible weapon is an incident."
)


def verdict_schema(nonce: str) -> dict:
    return {
        "type": "object",
        "required": ["probe_const", "verdict", "risk_score", "summary"],
        "properties": {
            "probe_const": {"type": "string", "const": nonce},
            "verdict": {"type": "string", "enum": ["confirmed", "rejected", "uncertain"]},
            "risk_score": {"type": "integer"},
            "summary": {"type": "string"},
        },
    }


def judge(client: httpx.Client, base: str, frame: Path, nonce: str) -> dict:
    uri = f"data:image/jpeg;base64,{base64.b64encode(frame.read_bytes()).decode()}"
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": uri}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 300,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "vlm_verdict", "schema": verdict_schema(nonce)},
        },
    }
    t0 = time.monotonic()
    r = client.post(f"{base}/v1/chat/completions", json=body)
    el = round(time.monotonic() - t0, 1)
    try:
        v = json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception:
        return {"parse_ok": False, "s": el, "status": r.status_code}
    ok = (
        v.get("probe_const") == nonce
        and v.get("verdict") in ("confirmed", "rejected", "uncertain")
        and isinstance(v.get("risk_score"), int)
        and 0 <= v["risk_score"] <= 100
    )
    return {
        "parse_ok": ok,
        "verdict": v.get("verdict"),
        "risk_score": v.get("risk_score"),
        "summary": str(v.get("summary", ""))[:160],
        "s": el,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--stock-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=6, help="frames per scenario")
    args = ap.parse_args()

    root = args.stock_root
    with httpx.Client(timeout=180.0) as client:
        props = client.get(f"{args.base_url.rstrip('/')}/props").json()
        nonce = uuid.uuid4().hex
        rows: list[dict] = []
        for man in sorted(root.glob("*/manifest.json")):
            scenario = man.parent.name
            frames = [Path(r["file"]) for r in json.loads(man.read_text())][: args.limit]
            expected = "rejected" if scenario in _BENIGN else "confirmed"
            for f in frames:
                row = judge(client, args.base_url.rstrip("/"), f, nonce)
                row |= {"scenario": scenario, "expected": expected, "frame": f.name}
                if row["parse_ok"]:
                    row["correct"] = row["verdict"] == expected
                    row["flagged"] = row["verdict"] in ("confirmed", "uncertain")
                rows.append(row)
                print(
                    f"{scenario}/{f.name}: {row.get('verdict', 'PARSE_FAIL')} "
                    f"score={row.get('risk_score', '-')} {row['s']}s",
                    flush=True,
                )

    parsed = [r for r in rows if r.get("parse_ok")]
    benign = [r for r in parsed if r["expected"] == "rejected"]
    incid = [r for r in parsed if r["expected"] == "confirmed"]
    agg = {
        "build_info": props.get("build_info"),
        "frames": len(rows),
        "schema_valid": len(parsed),
        "median_s": statistics.median([r["s"] for r in rows]) if rows else None,
        "benign_correctly_rejected": f"{sum(1 for r in benign if r['correct'])}/{len(benign)}",
        "incident_correctly_confirmed": f"{sum(1 for r in incid if r['correct'])}/{len(incid)}",
        "incident_flagged_any": f"{sum(1 for r in incid if r['flagged'])}/{len(incid)}",
        "per_scenario": {
            s: {
                "correct": sum(1 for r in parsed if r["scenario"] == s and r["correct"]),
                "n": sum(1 for r in rows if r["scenario"] == s),
            }
            for s in sorted({r["scenario"] for r in rows})
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"aggregate": agg, "rows": rows}, indent=2))
    print(json.dumps(agg, indent=2))
    return 0


_BENIGN = {
    "delivery_driver",
    "pet_activity",
    "resident_arrival",
    "vehicle_parking",
    "yard_maintenance",
}

if __name__ == "__main__":
    sys.exit(main())

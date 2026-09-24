#!/usr/bin/env python3
"""S-2: is ``response_format: json_schema`` enforced on IMAGE-BEARING chat
requests at the pinned llama.cpp build (spec §3's load-bearing assumption)?

Static source analysis at b7972 says images and grammar are independent
variables (server-common.cpp:958 sets inputs.json_schema regardless of media),
but template-level handlers can silently drop the schema per checkpoint - so
this is a per-model runtime guard, re-run on every engine or model swap.

Arms (all on /v1/chat/completions, base64 data URIs only - never remote URLs,
which would be an SSRF surface and nondeterministic):

  preflight  assert /props build_info; a 400 mentioning image input proves the
             server lacks --mmproj (loud by design); assert, don't assume.
  A          plain multimodal chat (generation works at all)
  B          correct nested wrapper: response_format.json_schema.schema,
             required const nonce + VlmVerdict-shaped fields
  C          malformed wrapper (schema key missing): llama.cpp then dumps "{}"
             as the grammar - assert the reply is NOT the empty object

Verdicts: ENFORCED / IGNORED / INCONCLUSIVE (never "unsupported" on a bad A).

Usage: uv run python scripts/vlm_probes/s2_multimodal_schema.py \
         --base-url http://host.docker.internal:PORT --image some.png
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

import httpx

TEXT = "Describe what is in this image in one short sentence."

# VlmVerdict-shaped (spec §4) + required const; NO minLength/minimum (their
# grammar-level support is unverified at this pin - ranges are post-validated
# client-side per the design decision).
def schema(nonce: str) -> dict:
    return {
        "type": "object",
        "required": ["probe_const", "description", "is_alert"],
        "properties": {
            "probe_const": {"type": "string", "const": nonce},
            "description": {"type": "string"},
            "is_alert": {"type": "boolean"},
        },
    }


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def chat_body(uri: str, response_format: dict | None = None) -> dict:
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": uri}},
                    {"type": "text", "text": TEXT},
                ],
            }
        ],
        "temperature": 0.1,
        # The grammar cannot close the object before generation completes; a budget
        # that truncates mid-object fabricates an IGNORED verdict (observed at 96).
        "max_tokens": 400,
    }
    if response_format is not None:
        body["response_format"] = response_format
    return body


def content_of(resp: httpx.Response) -> str:
    if resp.status_code != 200:
        return ""
    try:
        return resp.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--image", required=True, type=Path, help="local PNG/JPEG (synthetic only)")
    ap.add_argument("--expect-build", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    report: dict = {"probe": "S-2-multimodal-json-schema", "base_url": base,
                    "image": args.image.name}

    with httpx.Client(timeout=180.0) as c:
        try:
            props = c.get(f"{base}/props").json()
        except Exception:
            props = {}
        report["build_info"] = props.get("build_info", "")
        if args.expect_build and args.expect_build not in props.get("build_info", ""):
            report["verdict"] = "INCONCLUSIVE"
            report["why"] = "build_info mismatch - wrong server"
            return _finish(report, args.report)

        uri = data_uri(args.image)

        # A: plain multimodal generation.
        a = c.post(f"{base}/v1/chat/completions", json=chat_body(uri))
        a_content = content_of(a)
        report["arm_a"] = {"status": a.status_code, "content": a_content[:300]}
        if a.status_code != 200 or not a_content.strip():
            report["verdict"] = "INCONCLUSIVE"
            report["why"] = ("arm A failed (400 about image input => server started "
                             "without --mmproj) - not measuring enforcement")
            return _finish(report, args.report)

        nonce = __import__("uuid").uuid4().hex
        rf_ok = {"type": "json_schema",
                 "json_schema": {"name": "vlm_verdict", "schema": schema(nonce)}}
        b = c.post(f"{base}/v1/chat/completions", json=chat_body(uri, rf_ok))
        b_content = content_of(b)
        echoed = False
        try:
            echoed = json.loads(b_content).get("probe_const") == nonce
        except Exception:
            pass
        report["arm_b_enforced"] = {"status": b.status_code, "content": b_content[:300],
                                    "echoed_const": echoed}

        # C: malformed wrapper -> grammar is literally "{}"; reply must NOT be "{}".
        rf_bad = {"type": "json_schema", "json_schema": {"name": "vlm_verdict"}}
        cc = c.post(f"{base}/v1/chat/completions", json=chat_body(uri, rf_bad))
        cc_content = content_of(cc)
        empty_object_reply = cc_content.strip().replace(" ", "") == "{}"
        report["arm_c_malformed"] = {"status": cc.status_code, "content": cc_content[:300],
                                     "empty_object_reply": empty_object_reply}

    if echoed:
        report["verdict"] = "ENFORCED"
    elif b.status_code == 200:
        report["verdict"] = "IGNORED"
    else:
        report["verdict"] = "INCONCLUSIVE"
    return _finish(report, args.report)


def _finish(report: dict, path: str | None) -> int:
    print(json.dumps(report, indent=2))
    if path:
        Path(path).write_text(json.dumps(report, indent=2))
    return 0 if report["verdict"] != "INCONCLUSIVE" else 2


if __name__ == "__main__":
    sys.exit(main())

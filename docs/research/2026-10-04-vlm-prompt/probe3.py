#!/usr/bin/env python3
"""Probe 3: the Tier-A prompt ladder on the shipped single-still contract, at the 2048 budget.

Probe 1 (4 frames, shipped prompt): 0/17 incident hits, every score 0-10 under a confirmed
verdict - the calibration collapse is the failure, not perception. Probe 2 (at 1024) showed a
rubric moves scores but every rich arm was confounded by truncation; the cap is now 2048
(commit 26b900bc, same commit's README row). Probe 3 is the clean decomposition the draft
promised, on ONE still per event (the production/sweep contract), so arm deltas are text alone:

  ship        shipped prompt, unmodified            (control at 2048: this is what S2/S3 would see)
  A_decouple  two-INDEPENDENT-questions + stakes + band NAMES only, no behavior taxonomy
  A_lite      + band behavior taxonomy (lingering/testing locks...), no tiebreakers, no examples
  A_tiebreak  + the two tiebreaker rules (uncertain-at-night->medium; plainly-resident->routine)
  A_full      + the two point examples = prompt-draft-1.md as written

Every arm rides a transport shim on the chat request (the sweep's EXP_RUBRIC mechanism): shipped
client, shipped grammar, shipped grounding/boxes/frames; only the prompt TEXT changes. The
Detections/Household/Specialists/Camera/Time/Zones lines and the box-guidance sentences are
SPLICED VERBATIM from the shipped rendering, so rows and event-617 scar tissue are identical.

37 events (17 incident + 20 benign; benign = the S2 guardrail, FA = confirmed AND score >= 30).
Incident hit = confirmed AND score >= the item's floor_level. Truncations recorded as degraded
rows (a degraded row is verification_failed + NULL in production), never dropped.
Leakage caveat stands: the taxonomy mirrors the corpus scenarios; a positive is DIAGNOSTIC that
the text levers are alive. The two best arms then go through the real replay on all 450 stills.
"""
import asyncio, csv, json, os, sys
from pathlib import Path
import httpx

sys.path.insert(0, "/agents/agent-vss5/workspace")
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest  # noqa: E402
from synthbench.run import replay as R
from synthbench.run.models import Model

VP = Path(__file__).resolve().parent
SB = Path(os.environ["AGENT_GPU_DIR"]) / "out/sbroot"
URL = os.environ["PROBE_URL"]
SERVED = "Qwen3VL-8B-Instruct-Q4_K_M"
ITEMS_CSV = "/agents/agent-vss5/gpu/out/wt-sweeprep/docs/benchmarks/synthbench/sweep-2026-10-03/items.csv"

# ---- arm heads -------------------------------------------------------------
STAKES = (
    "Score what the camera's owner would pay to know about:\n\n"
    "0-29    routine.\n"
    "30-59   medium.\n"
    "60-84   high.\n"
    "85+     emergency."
)
BANDS = (
    "Score what the camera's owner would pay to know about:\n\n"
    "0-29    routine: residents arriving, planned work or deliveries, ordinary yard or "
    "neighborhood activity for the time of day.\n"
    "30-59   medium: a person at the property with no visible purpose - lingering near windows "
    "or doors, crossing toward the house and repeating it, examining vehicles. No weapon is "
    "needed for this band; repetition and aimless pattern ARE the evidence.\n"
    "60-84   high: conduct that typically precedes an intrusion or threatens a person - reaching "
    "for entry points, testing locks, concealment combined with approach, or an obvious weapon "
    "in hand.\n"
    "85+     emergency: an attack, break-in or fire in progress."
)
DECOUPLE = (
    "You are the risk assessor for a home-security camera. A detector has already flagged a "
    "scene; your job is the second decision on it. You answer two INDEPENDENT questions.\n\n"
    "VERDICT - is each detected candidate real and correctly identified in the image? This is a "
    "question about the detector, not about danger.\n\n"
    "RISK SCORE - what would this scene mean to the household if it is real? Judge what the "
    "scene IMPLIES about intent, not only whether something is visibly harmful right now. "
    "Verdict and risk do not explain each other: a confirmed candidate can be low risk, and a "
    "high-risk scene can contain an ordinary-looking object.\n\n" + STAKES
)
TIEBREAK = (
    "\n\nAn uncertain scene at night near entry points belongs in medium, not in routine. An "
    "uncertain scene that is plainly a resident, a worker, or a planned visit belongs in "
    "routine, not in medium."
)
EXAMPLES = (
    "\n\nExample: a person walking slowly along the side of the house at 22:40, stopping at a "
    "window, with no resident or appointment known - medium. Example: a postal carrier at the "
    "door at noon with a cart - routine."
)
DETECTOR_NOTE = (
    "\n\nThe Detections: line below lists candidates an object detector produced on the "
    "attached frame - deciding whether each is real is the VERDICT question."
)
# contract reminder: the shipped ANSWER sentence kept verbatim + the draft's output discipline.
ANSWER = (
    "\n\nAnswer ONLY with the verdict JSON object: verdict, risk_score, summary, reasoning, "
    "description, criteria (each name/passed/evidence), provenance (engine, model_id - copy the "
    "values from the served model's own reported identity). Fill every field, and keep the reply "
    "short: summary one sentence; description one sentence; reasoning at most two sentences; at "
    "most three criteria, their evidence each one short sentence naming what in the image "
    "supports it. Do not let the JSON run long."
)
SCENE_RULE = (
    "\n\nIf more than one candidate is attached, score the whole scene by its most threatening "
    "component - never an average."
)

ARMS = {
    "ship": None,  # text untouched
    "A_decouple": DECOUPLE + DETECTOR_NOTE + SCENE_RULE + ANSWER,
    "A_lite": DECOUPLE.replace(STAKES, BANDS) + DETECTOR_NOTE + SCENE_RULE + ANSWER,
    "A_tiebreak": DECOUPLE.replace(STAKES, BANDS) + TIEBREAK + DETECTOR_NOTE + SCENE_RULE + ANSWER,
    "A_full": DECOUPLE.replace(STAKES, BANDS) + TIEBREAK + EXAMPLES + DETECTOR_NOTE + SCENE_RULE + ANSWER,
}

MARK = "\nCamera: "  # shipped rendering: intro ends where the context block begins


class Shim(httpx.AsyncBaseTransport):
    """Rebuild the text part for one arm; splice the shipped context block verbatim."""

    def __init__(self, arm):
        self.inner = httpx.AsyncHTTPTransport()
        self.arm = arm
        self.replacements = 0

    async def handle_async_request(self, request):
        # The client's one-off grammar-enforcement probe rides the same path with a
        # synthetic prompt that has no context block; it is left alone (as in probe 2,
        # which only rewrote requests carrying the shipped risk sentence).
        if request.url.path.endswith("/chat/completions") and ARMS[self.arm] is not None:
            body = json.loads(request.content)
            parts = body["messages"][0]["content"]
            for p in parts:
                if p.get("type") != "text" or MARK not in p.get("text", ""):
                    continue
                head, sep, context = p["text"].partition(MARK)
                p["text"] = ARMS[self.arm] + MARK + context
                self.replacements += 1
            data = json.dumps(body).encode()
            headers = [(k, v) for k, v in request.headers.raw if k.lower() != b"content-length"]
            request = httpx.Request(request.method, request.url, headers=headers, content=data,
                                    extensions=request.extensions)
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()


model = Model(name="probe3", transport="ai-vlm", served_id=SERVED, url_env="AI_VLM_URL",
              default_url=URL, read_timeout=180)

recorded = {}
with open(ITEMS_CSV) as f:
    for r in csv.DictReader(f):
        recorded[r["item_id"]] = r

ARM_ORDER = ["ship", "A_decouple", "A_lite", "A_tiebreak", "A_full"]


async def main():
    manifest = json.load(open(VP / "manifest.json"))
    clients = {}
    import sqlite3
    con = sqlite3.connect(f"file:{SB}/eval/tierb-v0/eval.sqlite?mode=ro", uri=True)
    out = open(VP / "results3.jsonl", "a")
    done = set()
    if (VP / "results3.jsonl").exists():
        for l in open(VP / "results3.jsonl"):
            r = json.loads(l); done.add((r["event"], r["arm"]))
    for m in manifest:
        label = m.get("label", "incident")
        item_id = f"generated:{'normal' if label == 'benign' else 'suspicious'}:{m['source']}"
        rec = recorded[item_id]
        assert rec["label"] == ("benign" if label == "benign" else "incident"), (item_id, rec["label"])
        payload = json.loads(con.execute("select payload from items where item_id=?", (item_id,)).fetchone()[0])
        snap = payload["snapshot"]
        ctx = VlmAssessContext(
            camera_id=snap["camera_id"], detections=list(snap["detections"]), zones=list(snap["zones"]),
            zone_crossing=snap["zone_crossing"], household=dict(snap["household"]), timestamp=snap["timestamp"],
            specialist_outputs=dict(snap["specialist_outputs"]),
        )
        cap = VP / "capture"; (cap / m["event"]).mkdir(parents=True, exist_ok=True)
        still = cap / m["event"] / "src.jpg"
        import shutil
        if not still.exists(): shutil.copy(m["source_still"], still)
        for arm in ARM_ORDER:
            if (m["event"], arm) in done:
                continue
            shim = Shim(arm)
            client = clients.setdefault(arm, R.client_factory(model, URL, VP, shim)())
            try:
                v = await client.assess(VlmAssessRequest(image_paths=[str(still)], context=ctx))
                verdict, score = v.verdict, v.risk_score
            except Exception as exc:
                # production degrades these to verification_failed + NULL: record, never drop
                verdict, score = f"degraded:{type(exc).__name__}", None
                print(f"{m['event']} {arm}: DEGRADED {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            if ARMS[arm] is not None and shim.replacements == 0 and not verdict.startswith("degraded"):
                print(f"{m['event']} {arm}: WARN no text replacement happened", flush=True)
            row = {"event": m["event"], "item_id": item_id, "label": label, "scenario": m["scenario"],
                   "arm": arm, "floor": int(rec["floor_level"] or 0), "verdict": verdict, "risk_score": score}
            out.write(json.dumps(row) + "\n"); out.flush()
            print(f"{m['event']} {m['scenario']:<20} {arm:<11} {verdict:<20}{score if score is not None else '  -'}", flush=True)
    out.close()


asyncio.run(main())

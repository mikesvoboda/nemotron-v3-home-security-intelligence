#!/usr/bin/env python3
"""Probe 4: NVIDIA-VSS criterion reformulation + estimator arms, on probe 3's 37 events.

Probe 3 verdict: Tier-A text moves the operating point (ship 0/17 -> 5/17 hits) but not
discrimination (AUROC 0.59; 25-30 plateau sits on the FA line; benign FA 8/20). The two
online researchers (2026-10-04, docs/vss-integration/22) explain why: exemplar stacks do
not help open-weight 8B VLMs (arXiv:2405.09798); band NUMBERS anchor all scores coarsely
(arXiv:2608.25869 - presence shifts, values barely matter, CoT/warnings do not help);
class-specific instructions ARE the lever with evidence (surveillance VAD eval
arXiv:2603.04727, F1 0.09->0.64); and NVIDIA's own VSS blueprints never ask the VLM for a
number - verdict there is 3-valued and severity is rule-based analytics - while their
verification prompts reason BEFORE the constrained answer and attack exactly our failure
with the counterfactual ("if the person had FROZEN in place, would the household be
safer?") and anti-calmness clauses ("near misses can look calm").

Arms (all: single shipped still per event, shipped client+grammar, temp 0, 2048 budget;
only prompt text / request fields change, via the transport shim):

  nc        NVIDIA-CONDENSED criterion text (~230 tok): exposure/precursor criterion,
            operational NEGATIVE class definition, frozen-person counterfactual,
            anti-calmness clause, no behavior exemplar numbers beyond the band ladder.
            (logprobs captured -> offline expected-value estimate of the risk_score digit)
  nc_rp1    same text, request repeat_penalty 1.0 - isolates the sampler-order finding
            (researcher 2: default repeat_penalty 1.1 runs BEFORE temperature; digits
            are penalty-visible). If scores move, our greedy "determinism" was penalty-shaped.
  nc_2turn  same text, describe-then-score INSIDE the one assess call: the shim issues a
            free-text description request first, then replays the real request with the
            description as an assistant turn before the grammar-constrained answer. This
            is the cheap simulation of the Tier-C field reorder (reason-before-score)
            without touching the contract. Floor-60 incidents + the 5 worst benigns only.

EV: not an arm - logprobs ride nc and nc_rp1 (logprobs do not change generation); the
expected value over the top candidates of risk_score's first digit token is computed
offline from results4-logprobs.jsonl and compared with the argmax score.
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

# ---- NVIDIA-condensed criterion text (device names kept: they are the transferables) ----
NC_HEAD = (
    "You are the risk assessor for a home-security camera. A detector has already flagged a "
    "scene; your job is the second decision on it. You answer two INDEPENDENT questions.\n\n"
    "VERDICT - is each detected candidate real and correctly identified in the image? This is "
    "a question about the detector, not about danger.\n\n"
    "RISK SCORE - what this scene EXPOSES the household to, not whether harm is happening "
    "now. Nothing visibly harmful yet is not evidence of low risk: aimless repetition, "
    "approach toward entry points, testing and peering are PRECURSOR behaviors. Would the "
    "household be safer if this person had frozen in place right now? If the meaning of the "
    "scene changes once you know who the person is or why they came, score the exposure, not "
    "the calmness of the frame.\n\n"
    "Score what the camera's owner would pay to know about:\n\n"
    "0-29    routine: an identifiable resident, worker, delivery, or planned visit; ordinary "
    "yard or neighborhood activity for the time of day.\n"
    "30-59   medium: a person at the property with no visible purpose or appointment - "
    "lingering at windows or doors, approaching and retreating repeatedly, examining "
    "vehicles. A calm, ordinary-looking person in this band is still medium; do not dismiss "
    "a precursor because it looked calm.\n"
    "60-84   high: conduct that typically precedes entering a home or threatens a person - "
    "reaching for or forcing entry points, concealment combined with approach, a weapon in "
    "hand. Do not invent danger the frames do not show.\n"
    "85+     emergency: an attack, break-in or fire in progress."
)
DETECTOR_NOTE = (
    "\n\nThe Detections: line below lists candidates an object detector produced on the "
    "attached frame - deciding whether each is real is the VERDICT question."
)
SCENE_RULE = (
    "\n\nIf more than one candidate is attached, score the whole scene by its most threatening "
    "component - never an average."
)
ANSWER = (
    "\n\nAnswer ONLY with the verdict JSON object: verdict, risk_score, summary, reasoning, "
    "description, criteria (each name/passed/evidence), provenance (engine, model_id - copy "
    "the values from the served model's own reported identity). Fill every field, and keep "
    "the reply short: summary one sentence; description one sentence; reasoning at most two "
    "sentences; at most three criteria, their evidence each one short sentence naming what in "
    "the image supports it. Do not let the JSON run long."
)
NC_TEXT = NC_HEAD + DETECTOR_NOTE + SCENE_RULE + ANSWER

DESC_PROMPT = (
    "Describe this security-camera scene in two sentences: who or what is present, what they "
    "are doing, and what they appear to want. Do not score anything."
)
SCORE_NUDGE = "Now assess exactly this scene. Answer with the verdict JSON object."

MARK = "\nCamera: "  # shipped rendering marker: context block start


class Shim(httpx.AsyncBaseTransport):
    """mode: "nc" (text swap + logprobs), "rp1" (same + repeat_penalty 1.0),
    "two_turn" (same + describe-first assistant turn). All capture logprobs where asked."""

    def __init__(self, mode, logpath: Path):
        self.inner = httpx.AsyncHTTPTransport()
        self.mode = mode
        self.logpath = logpath

    def _log(self, rec):
        with self.logpath.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    async def _post(self, body):
        req = self._req(body)
        resp = await self.inner.handle_async_request(req)
        return resp

    def _req(self, body):
        data = json.dumps(body).encode()
        headers = [(k, v) for k, v in [(b"content-type", b"application/json")]]
        return httpx.Request("POST", self.base_url + "/v1/chat/completions",
                             headers=headers, content=data)

    async def handle_async_request(self, request):
        if not request.url.path.endswith("/chat/completions"):
            return await self.inner.handle_async_request(request)
        self.base_url = str(request.url.copy_with(fragment=None, path="")).rstrip("/")
        body = json.loads(request.content)
        parts = body["messages"][0]["content"]
        text_idx = [i for i, p in enumerate(parts) if p.get("type") == "text" and MARK in p.get("text", "")]
        if not text_idx:
            return await self.inner.handle_async_request(request)  # enforcement probe: untouched
        i = text_idx[0]
        head, sep, context = parts[i]["text"].partition(MARK)
        parts[i]["text"] = NC_TEXT + MARK + context
        body["logprobs"] = True
        body["top_logprobs"] = 5
        if self.mode == "rp1":
            body["repeat_penalty"] = 1.0
        if self.mode == "two_turn":
            # NB: the ai-vlm client body carries no "model" key (llama-server serves
            # one model); mirror that here or the describe call KeyErrors.
            dbody = dict(body)
            dbody["messages"] = [{"role": "user", "content":
                                  [p for p in parts if p.get("type") == "image_url"] +
                                  [{"type": "text", "text": DESC_PROMPT}]}]
            dbody["temperature"] = 0
            dbody["max_tokens"] = 96
            dbody.pop("response_format", None)
            dbody.pop("logprobs", None); dbody.pop("top_logprobs", None)
            dresp = await self._post(dbody)
            await dresp.aread()
            desc = json.loads(dresp.content)["choices"][0]["message"]["content"]
            body["messages"] = [
                {"role": "user", "content": parts},
                {"role": "assistant", "content": desc},
                {"role": "user", "content": SCORE_NUDGE},
            ]
            self._log({"kind": "desc", "desc": desc})
        resp = await self.inner.handle_async_request(self._req_for(request, body))
        try:
            await resp.aread()
            data = json.loads(resp.content)
            lp = data["choices"][0].get("logprobs")
            self._log({"kind": "score", "lp": lp, "content": data["choices"][0]["message"]["content"]})
        except Exception:
            pass
        return resp

    def _req_for(self, request, body):
        data = json.dumps(body).encode()
        headers = [(k, v) for k, v in request.headers.raw if k.lower() != b"content-length"]
        return httpx.Request(request.method, request.url, headers=headers, content=data,
                             extensions=request.extensions)

    async def aclose(self):
        await self.inner.aclose()


model = Model(name="probe4", transport="ai-vlm", served_id=SERVED, url_env="AI_VLM_URL",
              default_url=URL, read_timeout=180)

recorded = {}
with open(ITEMS_CSV) as f:
    for r in csv.DictReader(f):
        recorded[r["item_id"]] = r

ARM_ORDER = ["nc", "nc_rp1", "nc_2turn"]
TWO_TURN_BENIGN = {"C-clips-1-148", "C-clips-1-159", "C-clips-1-196", "C-clips-1-206", "C-clips-1-129"}


async def main():
    manifest = json.load(open(VP / "manifest.json"))
    clients, shims = {}, {}
    import sqlite3
    con = sqlite3.connect(f"file:{SB}/eval/tierb-v0/eval.sqlite?mode=ro", uri=True)
    out = open(VP / "results4.jsonl", "a")
    done = set()
    if (VP / "results4.jsonl").exists():
        for l in open(VP / "results4.jsonl"):
            r = json.loads(l); done.add((r["event"], r["arm"]))
    for m in manifest:
        label = m.get("label", "incident")
        item_id = f"generated:{'normal' if label == 'benign' else 'suspicious'}:{m['source']}"
        rec = recorded[item_id]
        assert rec["label"] == ("benign" if label == "benign" else "incident"), (item_id, rec["label"])
        floor = int(rec["floor_level"] or 0)
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
            if arm == "nc_2turn":
                if not (floor >= 60 and label == "incident") and m["event"] not in TWO_TURN_BENIGN:
                    continue
            if arm not in clients:
                mode = {"nc": "nc", "nc_rp1": "rp1", "nc_2turn": "two_turn"}[arm]
                shims[arm] = Shim(mode, VP / f"logprobs4-{arm}.jsonl")
                clients[arm] = R.client_factory(model, URL, VP, shims[arm])()
            client = clients[arm]
            try:
                v = await client.assess(VlmAssessRequest(image_paths=[str(still)], context=ctx))
                verdict, score = v.verdict, v.risk_score
            except Exception as exc:
                verdict, score = f"degraded:{type(exc).__name__}", None
                print(f"{m['event']} {arm}: DEGRADED {type(exc).__name__}: {str(exc)[:120]}", flush=True)
            row = {"event": m["event"], "item_id": item_id, "label": label, "scenario": m["scenario"],
                   "arm": arm, "floor": floor, "verdict": verdict, "risk_score": score}
            out.write(json.dumps(row) + "\n"); out.flush()
            print(f"{m['event']} {m['scenario']:<20} {arm:<10} {verdict:<20}{score if score is not None else '  -'}", flush=True)
    out.close()


asyncio.run(main())

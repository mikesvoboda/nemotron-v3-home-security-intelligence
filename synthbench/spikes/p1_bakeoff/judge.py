"""P1 VLM judge (owner direction 2026-09-28): the flagship describes every bake-off output,
and pure code (`derive`) compares that description with the case's known facts.

Evidence, never a gate: judge = claude-flagship (Qwen3.8-Flash-Next); the pipeline's VLM
stage is Qwen3VL-4B (same family). Nothing here changes a pick; report.py calibrates the
judge against the owner's ratings.

The questions are non-leading: the judge sees only pixels (an image, or a clip's first,
middle and last frames) and one fixed instruction with a fixed JSON schema. It never sees
the generation prompt, the case id or the output path.

Run on the host (the repo's uv environment) with the flagship up, never in a GPU window:
    uv run python -m synthbench.spikes.p1_bakeoff.judge [--limit 3]

Writes <root>/judge.jsonl, one row per ok output (the latest record per output). A failure
(timeout, refusal, bad JSON, unreadable file) writes a row with `error` and the run goes
on. Resumable: an output that already has an error-free row is skipped, so a rerun judges
only what is new or failed.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

import httpx
from PIL import Image

from synthbench.spikes.p1_bakeoff.cases import CASES, CLIPS, DAY_PLATE, LIGHTING, Case, ClipCase
from synthbench.spikes.p1_bakeoff.measure import cer, normalize_plate
from synthbench.spikes.p1_bakeoff.report import THREAT_CASES, latest, read_jsonl

DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DOWN_MESSAGE = "flagship is not up (a GPU window may be open)"
MAX_SIDE = 1344  # px on the longer side: 1920x1088 -> 1344x762, near measure.py's ~1 MP
JPEG_QUALITY = 90
MAX_TOKENS = 2048
DEFAULT_TIMEOUT_S = 180.0

_CASES = {case.id: case for case in CASES}
_CLIPS = {clip.id: clip for clip in CLIPS}

INSTRUCTION = (
    "You are a security-camera analyst. You are shown one image, or several frames of one "
    "video clip in time order. Describe the scene as you would in an "
    "incident log: the people, what they wear and what is in their hands, notable objects, "
    "vehicles and any readable plate, the lighting, the camera viewpoint, whether it looks "
    "like a real photograph, any rendering flaws, and your threat assessment. Report only "
    "what is visible; use unclear or null when you cannot tell. Reply with one JSON object "
    "that follows this JSON schema:"
)


def _enum(values: Sequence[str], description: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values), "description": description}


def _text(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "people_count": {"type": "integer", "minimum": 0, "description": "people in view"},
        "people": {
            "type": "array",
            "maxItems": 3,
            "description": "up to 3 of the people in view",
            "items": {
                "type": "object",
                "properties": {
                    "clothing": _text("what the person wears"),
                    "face_covered": _enum(("yes", "no", "unclear"), "is the face covered"),
                    "holding": _text('what is in their hands, or "nothing"'),
                },
                "required": ["clothing", "face_covered", "holding"],
                "additionalProperties": False,
            },
        },
        "notable_objects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "short names of the notable objects in view",
        },
        "vehicles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": _text("the kind of vehicle"),
                    "plate_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "the plate as read, or null if no plate is readable",
                    },
                },
                "required": ["type", "plate_text"],
                "additionalProperties": False,
            },
        },
        "lighting": _enum(
            ("daylight", "dusk", "night_color", "night_infrared", "unclear"), "the lighting"
        ),
        "viewpoint": _enum(
            ("elevated_security_camera", "eye_level", "other"), "where the camera looks from"
        ),
        "photorealistic": _enum(("yes", "partly", "no"), "does it look like a real photograph"),
        "artifacts": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "visible rendering flaws, short, e.g. extra fingers, garbled text, melted "
                "object; empty if none"
            ),
        },
        "threat_assessment": _enum(("threatening", "ambiguous", "benign"), "your assessment"),
        "threat_reason": _text("one short sentence"),
    },
    "required": [
        "people_count",
        "people",
        "notable_objects",
        "vehicles",
        "lighting",
        "viewpoint",
        "photorealistic",
        "artifacts",
        "threat_assessment",
        "threat_reason",
    ],
    "additionalProperties": False,
}

# The case's lighting (cases.LIGHTING's keys) as the judge's `lighting` value.
JUDGE_LIGHTING: dict[str, str] = {"day": "daylight", "dusk": "dusk", "ir_night": "night_infrared"}
_CAMERA_LIGHTING: dict[str, str] = {camera: key for key, camera in LIGHTING.items()} | {
    DAY_PLATE: "day"
}
# Cases whose prompt specifies a covered face.
COVERED_FACE_CASES = frozenset({"balaclava_ir_night"})
IDENTITY_CASES = frozenset({"identity", "identity_reference"})
# A threat case's prop is its first OWLv2 query's key noun, or one of these synonyms.
PROP_SYNONYMS: dict[str, tuple[str, ...]] = {
    "handgun": ("gun", "pistol", "firearm", "revolver"),
    "knife": ("knives", "blade", "machete", "dagger"),
    "crowbar": ("crow bar", "pry bar", "prybar", "wrecking bar"),
    "ski mask": ("balaclava", "mask"),
    "child": ("children", "kid", "toddler", "boy", "girl"),
}
# These REPLACE the key-noun rule (controller ruling, Task 10 fix round 1): a damage case's
# key noun is a bare structural noun ("window", "door") that nearly every house image names,
# so only words for the damage itself count. No case's terms may be a bare "window"/"door".
PROP_TERM_OVERRIDES: dict[str, tuple[str, ...]] = {
    "pried_window": (
        "open window",
        "broken window",
        "pried",
        "forced window",
        "bent frame",
        "climbing through",
        "pry bar",
        "crowbar",
    ),
    "forced_door": (
        "broken door",
        "forced",
        "splintered",
        "damaged door",
        "kicked in",
        "damaged frame",
    ),
}
# Hazards, not intruders: a judge may fairly call them benign, so judge_good (does the render
# match the case?) does not ask for a non-benign threat assessment.
HAZARD_CASES = frozenset({"child_alone_pool", "smoke_from_eave"})


class JudgeError(RuntimeError):
    """The judge gave no usable answer: an HTTP error, a refusal or bad JSON."""


class Answer(dict[str, Any]):
    """The judge's JSON answer. `fallbacks` records how the request or its parse degraded
    (an option the server rejected, a code fence stripped): empty when all went as asked."""

    def __init__(self, data: dict[str, Any], fallbacks: list[str]) -> None:
        super().__init__(data)
        self.fallbacks = fallbacks


class JudgeClient(Protocol):
    def describe(self, images: Sequence[bytes], schema: dict[str, Any]) -> dict[str, Any]: ...


# --- the answer: JSON as asked, or recovered from a fence, a think block or prose ---


def _required(schema: dict[str, Any]) -> list[str]:
    return [str(key) for key in schema.get("required", [])]


def parse_answer(content: object, required: Sequence[str]) -> tuple[dict[str, Any], list[str]]:
    """The reply's JSON object and the notes on how it was recovered (empty when it parsed
    as sent). Raises JudgeError for no usable object."""
    if not isinstance(content, str) or not content.strip():
        raise JudgeError("empty content")
    text, notes = content.strip(), []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1].strip()
            notes.append("stripped a think block")
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
            notes.append("stripped a code fence")
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise JudgeError(f"no JSON object in the reply: {content[:200]!r}") from None
        if (start, end + 1) != (0, len(text)):
            notes.append("cut the JSON object out of surrounding text")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise JudgeError(f"bad JSON ({exc}): {content[:200]!r}") from exc
    if not isinstance(data, dict):
        raise JudgeError(f"the reply is not a JSON object: {content[:200]!r}")
    missing = [key for key in required if key not in data]
    if missing:
        raise JudgeError(f"the reply misses {', '.join(missing)}")
    return data, notes


# Where vLLM's reasoning parser puts text it took for reasoning (newer builds say `reasoning`).
_REASONING_FIELDS = ("reasoning_content", "reasoning")


def _data_url(image: bytes) -> str:
    mime = "image/png" if image.startswith(b"\x89PNG") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


class OpenAIJudge:
    """A JudgeClient on an OpenAI-compatible chat server (the flagship's vLLM).

    Asks for structured output (`response_format` json_schema) without thinking
    (`chat_template_kwargs`). A 400 is retried along _LADDER, dropping as little as it can:
    without `response_format`, then without `chat_template_kwargs`, then without both. The
    set that passed is remembered, so later requests skip the rejected options at once.
    """

    _LADDER: tuple[frozenset[str], ...] = (
        frozenset(),
        frozenset({"response_format"}),
        frozenset({"chat_template_kwargs"}),
        frozenset({"response_format", "chat_template_kwargs"}),
    )

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout_s)
        self._lock = threading.Lock()
        self._dropped: frozenset[str] = frozenset()  # the options the server rejected

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OpenAIJudge:
        return self

    def __exit__(
        self, _t: type[BaseException] | None, _e: BaseException | None, _tb: TracebackType | None
    ) -> None:
        self.close()

    def body(
        self, images: Sequence[bytes], schema: dict[str, Any], dropped: frozenset[str]
    ) -> dict[str, Any]:
        """The request: the images, then the fixed instruction with the schema as text (it
        still guides the model when `response_format` is dropped). Nothing else."""
        content: list[dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": _data_url(image)}} for image in images
        ]
        content.append({"type": "text", "text": f"{INSTRUCTION}\n{json.dumps(schema)}"})
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
            "max_tokens": MAX_TOKENS,
        }
        if "chat_template_kwargs" not in dropped:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if "response_format" not in dropped:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "camera_description", "schema": schema, "strict": True},
            }
        return body

    def describe(self, images: Sequence[bytes], schema: dict[str, Any]) -> Answer:
        with self._lock:
            known = self._dropped
        fallbacks: list[str] = []
        for dropped in (option_set for option_set in self._LADDER if option_set >= known):
            resp = self._http.post("/chat/completions", json=self.body(images, schema, dropped))
            if resp.status_code != httpx.codes.BAD_REQUEST:
                break
            sent = f"without {' and '.join(sorted(dropped))}" if dropped else "as asked"
            fallbacks.append(f"HTTP 400 {sent}: {resp.text[:200]}")
        if resp.status_code != httpx.codes.OK:
            raise JudgeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        if dropped:
            fallbacks.append(f"sent without {' and '.join(sorted(dropped))}")
            with self._lock:
                self._dropped |= dropped  # it passed without them: later requests skip them
        choice = resp.json()["choices"][0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise JudgeError(f"the judge refused: {str(message['refusal'])[:200]}")
        content = message.get("content")
        notes: list[str] = []
        if not (isinstance(content, str) and content.strip()):
            # The qwen3 reasoning parser may leave the answer in the reasoning field.
            for field in _REASONING_FIELDS:
                reasoning = message.get(field)
                if isinstance(reasoning, str) and reasoning.strip():
                    content, notes = reasoning, [f"{field}: content was empty"]
                    break
        try:
            data, parse_notes = parse_answer(content, _required(schema))
        except JudgeError as exc:
            if choice.get("finish_reason") == "length":
                raise JudgeError(f"{exc} (cut off at max_tokens={MAX_TOKENS})") from exc
            raise
        return Answer(data, fallbacks + notes + parse_notes)


# --- the media: resized JPEGs; a clip's first, middle and last frames ---


def to_jpeg(image: Image.Image) -> bytes:
    """RGB JPEG (quality JPEG_QUALITY), the longer side at most MAX_SIDE (never upscaled)."""
    image = image.convert("RGB")
    longer = max(image.size)
    if longer > MAX_SIDE:
        scale = MAX_SIDE / longer
        size = (max(round(image.width * scale), 1), max(round(image.height * scale), 1))
        image = image.resize(size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def frame_indices(count: int) -> list[int]:
    """The first, middle and last of `count` frames (fewer when they coincide)."""
    return sorted({0, count // 2, count - 1}) if count > 0 else []


def clip_frames(path: Path) -> list[Image.Image]:
    import av

    with av.open(str(path)) as container:
        frames = list(container.decode(video=0))
    picked = [frames[i].to_image() for i in frame_indices(len(frames))]
    if not picked:
        raise ValueError(f"{path}: no video frames")
    return picked


def media_images(record: dict[str, Any], root: Path) -> list[bytes]:
    """What the judge sees of an output: its image, or its clip's three frames, as JPEGs."""
    path = root / record["output"]
    if record["kind"] == "i2v":
        return [to_jpeg(frame) for frame in clip_frames(path)]
    with Image.open(path) as image:
        return [to_jpeg(image)]


# --- derive: the answer against the case's known facts (no model asked) ---


def case_of(record: dict[str, Any]) -> Case | ClipCase | None:
    """The record's case in cases.py: a ClipCase for clips; None for identity shots."""
    if record["kind"] == "i2v":
        return _CLIPS.get(record["case"])
    return _CASES.get(record["case"])


def case_type(record: dict[str, Any]) -> str:
    """The record's case type: clip, threat, identity, or plate (the case with an OCR target)."""
    if record["kind"] == "i2v":
        return "clip"
    if record["case"] in THREAT_CASES:
        return "threat"
    if record["case"] in IDENTITY_CASES:
        return "identity"
    return "plate" if getattr(_CASES.get(record["case"]), "ocr_target", None) else "other"


def case_lighting(record: dict[str, Any], case: Case | ClipCase | None) -> str | None:
    """The case's lighting as a cases.LIGHTING key (day, dusk, ir_night), None if unknown.
    Identity shots carry it in their name (`<shot>_<lighting>`); the reference is day."""
    if isinstance(case, Case):
        return _CAMERA_LIGHTING.get(case.camera)
    if isinstance(case, ClipCase):
        if case.keyframe.startswith("identity:"):
            return case.keyframe.split(":")[2]
        return case_lighting(record, _CASES.get(case.keyframe))
    if record["case"] == "identity_reference":
        return "day"
    if record["case"] == "identity":
        lighting = Path(record["output"]).stem.split("_", 1)[-1]
        return lighting if lighting in LIGHTING else None
    return None


def key_noun(query: str) -> str:
    """An OWLv2 query without its article: "a ski mask" -> "ski mask"."""
    return re.sub(r"^(?:a|an|the)\s+", "", query.strip().lower())


def prop_terms(case: Case) -> tuple[str, ...]:
    """PROP_TERM_OVERRIDES for the case, else its first query's key noun and synonyms."""
    if case.id in PROP_TERM_OVERRIDES:
        return PROP_TERM_OVERRIDES[case.id]
    noun = key_noun(case.owl_queries[0])
    return (noun, *PROP_SYNONYMS.get(noun, ()))


def _norm(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", text.lower()).strip()


def mentions(texts: Sequence[str], terms: Sequence[str]) -> bool:
    """Any term, as whole words (a plural s/es allowed), in any text: "gun" matches
    "two guns" but not "gunmetal"."""
    joined = " | ".join(_norm(text) for text in texts)
    return any(re.search(rf"\b{re.escape(_norm(t))}(?:s|es)?\b", joined) for t in terms)


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _count(value: object) -> int:
    """An integer field that may arrive as a string (a fallback reply); 0 otherwise."""
    if isinstance(value, int):
        return value
    return int(value) if isinstance(value, str) and value.strip().isdigit() else 0


def derive(
    record: dict[str, Any], answer: dict[str, Any], case: Case | ClipCase | None
) -> dict[str, Any]:
    """The answer against the case's known facts; pure code, no model asked.

    judge_good: threat cases: the prop named, photorealistic, and not assessed benign (the
    HAZARD_CASES need not be: a hazard may fairly be called benign); identity shots: the case's lighting, photorealistic, and at least one person; clips:
    photorealistic with no artifacts; None for the plate case (plate_cer is its measure).
    """
    kind = case_type(record)
    people = _dicts(answer.get("people"))
    texts = [
        *(
            p[field]
            for p in people
            for field in ("holding", "clothing")
            if isinstance(p.get(field), str)
        ),
        *_strings(answer.get("notable_objects")),
    ]
    prop_match = (
        mentions(texts, prop_terms(case)) if kind == "threat" and isinstance(case, Case) else None
    )
    face_covered_match = (
        any(p.get("face_covered") == "yes" for p in people)
        if record["case"] in COVERED_FACE_CASES
        else None
    )
    lighting = case_lighting(record, case)
    expected = JUDGE_LIGHTING.get(lighting) if lighting else None
    lighting_match = None if expected is None else answer.get("lighting") == expected
    plate_cer = None
    if isinstance(case, Case) and case.ocr_target:
        target = normalize_plate(case.ocr_target)
        plates = [v.get("plate_text") for v in _dicts(answer.get("vehicles"))]
        read = [normalize_plate(p) for p in plates if isinstance(p, str)]
        plate_cer = min((cer(text, target) for text in read), default=cer("", target))
    realistic = answer.get("photorealistic") == "yes"
    artifact_count = len(_strings(answer.get("artifacts")))
    threat = answer.get("threat_assessment")
    judge_good: bool | None = None
    if kind == "threat" and record["case"] in HAZARD_CASES:
        judge_good = bool(prop_match) and realistic
    elif kind == "threat":
        judge_good = bool(prop_match) and realistic and threat != "benign"
    elif kind == "identity":
        people_count = _count(answer.get("people_count"))
        judge_good = bool(lighting_match) and realistic and people_count >= 1
    elif kind == "clip":
        judge_good = realistic and artifact_count == 0
    return {
        "case_type": kind,
        "prop_match": prop_match,
        "face_covered_match": face_covered_match,
        "lighting_match": lighting_match,
        "viewpoint_ok": answer.get("viewpoint") == "elevated_security_camera",
        "realistic": realistic,
        "plate_cer": plate_cer,
        "judge_threat": threat,
        "artifact_count": artifact_count,
        "judge_good": judge_good,
    }


# --- the run: one row per ok output, resumable ---


def judge_record(
    record: dict[str, Any], root: Path, client: JudgeClient, judge_model: str
) -> dict[str, Any]:
    """One judge.jsonl row. `seconds` is the judge's time (media prep included). A failure
    becomes the row's `error`, never an exception."""
    started = time.monotonic()
    row: dict[str, Any] = {
        "output": record["output"],
        "model": record["model"],
        "kind": record["kind"],
        "case": record["case"],
        "seconds": None,
        "judge_model": judge_model,
        "answer": None,
        "derived": None,
        "error": None,
        "fallbacks": [],
    }
    try:
        answer = client.describe(media_images(record, root), ANSWER_SCHEMA)
        row["fallbacks"] = list(getattr(answer, "fallbacks", []))
        row["answer"] = dict(answer)
        row["derived"] = derive(record, answer, case_of(record))
    except Exception as exc:  # a failure is a row, never fatal: the run goes on
        row["answer"] = row["derived"] = None  # derive may fail after the answer is set
        row["error"] = f"{type(exc).__name__}: {exc}"[:500]
    row["seconds"] = round(time.monotonic() - started, 3)
    return row


def to_judge(records: list[dict[str, Any]], judged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The ok outputs (latest record per output) without an error-free judge row."""
    done = {row["output"] for row in judged if not row.get("error")}
    return [r for r in latest(records).values() if r["ok"] and r["output"] not in done]


def served_model(base_url: str, transport: httpx.BaseTransport | None = None) -> str | None:
    """The first model id GET /v1/models lists; None unless it answers 200 with one."""
    try:
        with httpx.Client(base_url=base_url, transport=transport, timeout=10.0) as http:
            resp = http.get("/models")
        if resp.status_code != httpx.codes.OK:
            return None
        return str(resp.json()["data"][0]["id"])
    except httpx.HTTPError, ValueError, KeyError, IndexError, TypeError:
        return None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.judge")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--workers", type=int, default=8, help="concurrent requests")
    parser.add_argument("--limit", type=int, default=None, help="judge at most N outputs")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    """`transport` is the tests' fake flagship."""
    args = parse_args(argv)
    root: Path = args.root
    judge_model = served_model(args.base_url, transport)
    if judge_model is None:
        sys.stderr.write(f"[p1-judge] {DOWN_MESSAGE}: GET {args.base_url}/models failed\n")
        return 1
    out = root / "judge.jsonl"
    todo = to_judge(read_jsonl(root / "records.jsonl"), read_jsonl(out, missing_ok=True))
    if args.limit is not None:
        todo = todo[: args.limit]
    rows = errors = 0
    pool = ThreadPoolExecutor(max_workers=max(args.workers, 1))
    try:
        with (
            OpenAIJudge(
                args.base_url, judge_model, timeout_s=args.timeout_s, transport=transport
            ) as client,
            out.open("a") as fh,
        ):
            futures = [
                pool.submit(judge_record, record, root, client, judge_model) for record in todo
            ]
            for future in as_completed(futures):
                row = future.result()
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                rows += 1
                if row["error"]:
                    errors += 1
                    sys.stderr.write(f"[p1-judge] {row['output']}: {row['error']}\n")
    finally:
        # On Ctrl-C, drop the queued outputs rather than judge them with nowhere to write.
        pool.shutdown(wait=True, cancel_futures=True)
    sys.stderr.write(f"[p1-judge] {judge_model}: {rows} rows, {errors} errors -> {out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

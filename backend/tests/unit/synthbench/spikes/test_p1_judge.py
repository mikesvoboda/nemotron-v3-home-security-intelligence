"""P1 VLM judge against a fake flagship (httpx.MockTransport): the non-leading request,
its fallbacks, `derive` per case type, and the resumable CLI. No GPU, no network."""

from __future__ import annotations

import base64
import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from synthbench.spikes.p1_bakeoff import judge as j
from synthbench.spikes.p1_bakeoff.cases import CASES, CLIPS, IDENTITY_REFERENCE

_CASES = {case.id: case for case in CASES}
BASE_URL = "http://flagship/v1"


def _answer(**kw: Any) -> dict[str, Any]:
    """A well-formed judge answer: one armed person in daylight, seen from above."""
    return {
        "people_count": 1,
        "people": [
            {"clothing": "dark hoodie", "face_covered": "no", "holding": "a black pistol"},
        ],
        "notable_objects": ["front door", "driveway"],
        "vehicles": [],
        "lighting": "daylight",
        "viewpoint": "elevated_security_camera",
        "photorealistic": "yes",
        "artifacts": [],
        "threat_assessment": "threatening",
        "threat_reason": "an armed person walks toward the door",
    } | kw


Reply = str | Callable[[dict[str, Any]], httpx.Response]


class FakeFlagship:
    """GET /v1/models and POST /v1/chat/completions, as vLLM's OpenAI server answers them.

    `replies` are used in order (the last one repeats): a content string, or a function of
    the request body that returns the response. `reject` names body options answered 400.
    """

    def __init__(
        self,
        *replies: Reply,
        reject: tuple[str, ...] = (),
        models_status: int = 200,
        refusal: str | None = None,
    ) -> None:
        self.replies: list[Reply] = list(replies) or [json.dumps(_answer())]
        self.reject = reject
        self.models_status = models_status
        self.refusal = refusal
        self.bodies: list[dict[str, Any]] = []
        self.raw: list[str] = []
        self.model_gets = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/models":
            self.model_gets += 1
            data = {"object": "list", "data": [{"id": "claude-flagship", "object": "model"}]}
            return httpx.Response(self.models_status, json=data)
        if request.method == "POST" and request.url.path == "/v1/chat/completions":
            self.raw.append(request.content.decode())
            body = json.loads(request.content)
            self.bodies.append(body)
            rejected = [option for option in self.reject if option in body]
            if rejected:
                return httpx.Response(400, json={"error": {"message": f"bad {rejected[0]}"}})
            reply = self.replies[min(len(self.bodies) - 1, len(self.replies) - 1)]
            if callable(reply):
                return reply(body)
            message = {"role": "assistant", "content": reply, "refusal": self.refusal}
            choice = {"index": 0, "message": message, "finish_reason": "stop"}
            return httpx.Response(200, json={"choices": [choice]})
        return httpx.Response(404)


def _judge(fake: FakeFlagship) -> j.OpenAIJudge:
    return j.OpenAIJudge(
        BASE_URL, "claude-flagship", timeout_s=5.0, transport=httpx.MockTransport(fake)
    )


def _png(path: Path, size: tuple[int, int] = (64, 48)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (90, 90, 90)).save(path)


def _write_clip(path: Path, reds: list[int]) -> None:
    """A tiny mp4, one solid frame per value in `reds` (red channel)."""
    import av

    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), mode="w") as container:
        stream: Any = container.add_stream("mpeg4", rate=8)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for red in reds:
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 48), (red, 0, 0)))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def _record(case: str, output: str, **kw: Any) -> dict[str, Any]:
    """A records.jsonl row as run.py writes it (prompt included)."""
    return {
        "model": "flux2-dev",
        "kind": "t2i",
        "case": case,
        "seed": 11,
        "prompt": _CASES[case].prompt if case in _CASES else IDENTITY_REFERENCE,
        "width": 64,
        "height": 48,
        "output": output,
        "inputs": [],
        "frames": 0,
        "cold": False,
        "ok": True,
        "error": None,
        "seconds": 3.0,
    } | kw


def _data_urls(body: dict[str, Any]) -> list[str]:
    return [
        part["image_url"]["url"]
        for message in body["messages"]
        for part in (message["content"] if isinstance(message["content"], list) else [])
        if part.get("type") == "image_url"
    ]


def _texts(body: dict[str, Any]) -> list[str]:
    return [
        part["text"]
        for message in body["messages"]
        for part in (message["content"] if isinstance(message["content"], list) else [])
        if part.get("type") == "text"
    ]


def _without_images(raw: str) -> str:
    return re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "<image>", raw)


# --- the request: non-leading, images as data URLs, schema and no thinking ---


@pytest.mark.parametrize("case", [case.id for case in CASES])
def test_the_request_never_carries_the_prompt_the_case_or_the_path(
    case: str, tmp_path: Path
) -> None:
    fake = FakeFlagship()
    record = _record(case, f"images/flux2-dev/{case}/11.png")
    _png(tmp_path / record["output"])
    row = j.judge_record(record, tmp_path, _judge(fake), "claude-flagship")
    assert row["error"] is None
    (raw,) = fake.raw
    text = _without_images(raw)
    for other in CASES:  # no case's prompt, scene, camera text or id, not only this one's
        assert other.prompt not in text and other.scene not in text
        assert re.search(rf"\b{re.escape(other.id)}\b", text) is None, other.id
    assert IDENTITY_REFERENCE not in text and record["output"] not in text


def test_the_request_sends_data_urls_the_schema_and_no_thinking(tmp_path: Path) -> None:
    fake = FakeFlagship()
    record = _record("knife", "images/flux2-dev/knife/11.png")
    _png(tmp_path / record["output"])
    j.judge_record(record, tmp_path, _judge(fake), "claude-flagship")
    (body,) = fake.bodies
    assert body["model"] == "claude-flagship"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == j.ANSWER_SCHEMA
    (url,) = _data_urls(body)
    assert url.startswith("data:image/jpeg;base64,")
    image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert image.format == "JPEG" and image.size == (64, 48)
    (text,) = _texts(body)
    assert text.startswith(j.INSTRUCTION)  # the one fixed instruction, then the schema
    assert json.dumps(j.ANSWER_SCHEMA) in text


def test_the_schema_holds_every_field_and_its_allowed_values() -> None:
    schema = j.ANSWER_SCHEMA
    assert set(schema["required"]) == {
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
    }
    props = schema["properties"]
    assert props["people"]["maxItems"] == 3
    person = props["people"]["items"]["properties"]
    assert set(person) == {"clothing", "face_covered", "holding"}
    assert person["face_covered"]["enum"] == ["yes", "no", "unclear"]
    assert props["lighting"]["enum"] == [
        "daylight",
        "dusk",
        "night_color",
        "night_infrared",
        "unclear",
    ]
    assert props["viewpoint"]["enum"] == ["elevated_security_camera", "eye_level", "other"]
    assert props["photorealistic"]["enum"] == ["yes", "partly", "no"]
    assert props["threat_assessment"]["enum"] == ["threatening", "ambiguous", "benign"]
    assert set(props["vehicles"]["items"]["properties"]) == {"type", "plate_text"}


def test_images_are_resized_to_1344_on_the_long_side_as_jpeg_90() -> None:
    big = Image.new("RGB", (1920, 1088), (10, 120, 200))
    out = Image.open(io.BytesIO(j.to_jpeg(big)))
    assert out.format == "JPEG" and out.size == (1344, 762)
    reference = io.BytesIO()
    big.resize((1344, 762)).save(reference, "JPEG", quality=90)
    assert out.quantization == Image.open(reference).quantization  # quality 90's tables
    small = Image.new("RGBA", (640, 480))  # never upscaled; alpha dropped
    assert Image.open(io.BytesIO(j.to_jpeg(small))).size == (640, 480)


def test_frame_indices_are_first_middle_last() -> None:
    assert j.frame_indices(97) == [0, 48, 96]
    assert j.frame_indices(81) == [0, 40, 80]
    assert j.frame_indices(2) == [0, 1]
    assert j.frame_indices(1) == [0]
    assert j.frame_indices(0) == []


def test_a_clip_sends_its_first_middle_and_last_frames(tmp_path: Path) -> None:
    _write_clip(tmp_path / "c.mp4", [0, 30, 60, 90, 120, 150, 180, 210, 240])
    blobs = j.media_images({"kind": "i2v", "output": "c.mp4"}, tmp_path)
    reds = [Image.open(io.BytesIO(blob)).convert("RGB").getpixel((32, 24))[0] for blob in blobs]
    assert len(reds) == 3
    for red, want in zip(reds, (0, 120, 240), strict=True):
        assert abs(red - want) <= 20, reds


def test_a_clip_is_judged_in_one_request_of_three_images(tmp_path: Path) -> None:
    fake = FakeFlagship()
    output = "clips/ltx-2.5/armed_approach/11.mp4"
    _write_clip(tmp_path / output, [0, 60, 120, 180, 240])
    record = _record("armed_approach", output, kind="i2v", model="ltx-2.5", prompt="motion")
    row = j.judge_record(record, tmp_path, _judge(fake), "claude-flagship")
    assert row["error"] is None
    assert len(_data_urls(fake.bodies[0])) == 3


# --- fallbacks: a rejected option, fenced or wrapped JSON, and the failures ---


def test_a_rejected_response_format_is_dropped_and_remembered() -> None:
    fake = FakeFlagship(reject=("response_format",))
    judge = _judge(fake)
    first = judge.describe([j.to_jpeg(Image.new("RGB", (8, 8)))], j.ANSWER_SCHEMA)
    assert first == _answer()
    assert len(fake.bodies) == 2  # the rejected request, then the retry without it
    assert "response_format" not in fake.bodies[1]
    assert fake.bodies[1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert first.fallbacks[0].startswith("HTTP 400 as asked: ")
    assert first.fallbacks[1:] == ["sent without response_format"]
    second = judge.describe([j.to_jpeg(Image.new("RGB", (8, 8)))], j.ANSWER_SCHEMA)
    assert len(fake.bodies) == 3  # remembered: one request, already without it
    assert "response_format" not in fake.bodies[2]
    assert second.fallbacks == ["sent without response_format"]


def test_both_options_rejected_falls_back_to_a_plain_request() -> None:
    fake = FakeFlagship(reject=("response_format", "chat_template_kwargs"))
    answer = _judge(fake).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert answer == _answer()
    assert len(fake.bodies) == 4  # as asked, without each option, without both
    assert "response_format" not in fake.bodies[3]
    assert "chat_template_kwargs" not in fake.bodies[3]
    assert json.dumps(j.ANSWER_SCHEMA) in _texts(fake.bodies[3])[0]  # the schema, as text
    assert len(answer.fallbacks) == 4
    assert answer.fallbacks[-1] == "sent without chat_template_kwargs and response_format"


def test_a_rejected_thinking_switch_keeps_the_structured_output() -> None:
    fake = FakeFlagship(reject=("chat_template_kwargs",))
    answer = _judge(fake).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert answer == _answer()
    assert len(fake.bodies) == 3  # as asked, without response_format, then without the switch
    assert "chat_template_kwargs" not in fake.bodies[2]
    assert fake.bodies[2]["response_format"]["type"] == "json_schema"
    assert answer.fallbacks[-1] == "sent without chat_template_kwargs"


def test_a_400_that_no_fallback_fixes_raises_and_is_not_remembered() -> None:
    def always_400(_body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "image too large"}})

    fake = FakeFlagship(always_400)
    judge = _judge(fake)
    with pytest.raises(j.JudgeError, match="400"):
        judge.describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert len(fake.bodies) == 4
    fake.replies = [json.dumps(_answer())]
    answer = judge.describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert "response_format" in fake.bodies[4] and answer.fallbacks == []


@pytest.mark.parametrize(
    ("content", "note"),
    [
        (f"```json\n{json.dumps(_answer())}\n```", "code fence"),
        (f"<think>looking</think>\n{json.dumps(_answer())}", "think"),
        (f"reasoning...</think>{json.dumps(_answer())}", "think"),
        (f"Here is the description: {json.dumps(_answer())} Hope it helps.", "surrounding"),
    ],
)
def test_wrapped_json_is_recovered_and_the_fallback_recorded(content: str, note: str) -> None:
    answer = _judge(FakeFlagship(content)).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert answer == _answer()
    assert any(note in fallback for fallback in answer.fallbacks), answer.fallbacks


def test_the_row_records_the_fallbacks(tmp_path: Path) -> None:
    record = _record("knife", "images/m/knife/11.png")
    _png(tmp_path / record["output"])
    fake = FakeFlagship(reject=("response_format",))
    row = j.judge_record(record, tmp_path, _judge(fake), "claude-flagship")
    assert row["error"] is None and row["answer"] == _answer()
    assert row["fallbacks"][-1] == "sent without response_format"


def test_clean_json_records_no_fallback() -> None:
    answer = _judge(FakeFlagship()).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)
    assert answer == _answer() and answer.fallbacks == []


@pytest.mark.parametrize(
    ("fake", "match"),
    [
        (FakeFlagship("I'm sorry, I can't help with that."), "no JSON object"),
        (FakeFlagship("{not json}"), "bad JSON"),
        (FakeFlagship(""), "empty"),
        (FakeFlagship("[1, 2]"), "not a JSON object"),
        (FakeFlagship(json.dumps({"people_count": 1})), "misses"),
        (FakeFlagship(json.dumps(_answer()), refusal="I cannot assist."), "refused"),
        (FakeFlagship(lambda _b: httpx.Response(500, text="engine dead")), "500"),
    ],
)
def test_refusals_bad_json_and_server_errors_raise(fake: FakeFlagship, match: str) -> None:
    with pytest.raises(j.JudgeError, match=match):
        _judge(fake).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)


def test_a_reply_cut_off_at_max_tokens_says_so() -> None:
    def truncated(_body: dict[str, Any]) -> httpx.Response:
        message = {"role": "assistant", "content": json.dumps(_answer())[:40]}
        choice = {"index": 0, "message": message, "finish_reason": "length"}
        return httpx.Response(200, json={"choices": [choice]})

    with pytest.raises(j.JudgeError, match="cut off at max_tokens"):
        _judge(FakeFlagship(truncated)).describe([b"\xff\xd8jpeg"], j.ANSWER_SCHEMA)


# --- derive: pure comparison with the case's known facts ---


def _derive(case: str, output: str | None = None, **answer: Any) -> dict[str, Any]:
    kind = "i2v" if output and output.startswith("clips/") else "t2i"
    record = _record(case, output or f"images/m/{case}/11.png", kind=kind)
    return j.derive(record, _answer(**answer), j.case_of(record))


def test_derive_a_threat_case_with_a_synonym_prop() -> None:
    d = _derive("handgun_in_hand")  # holding "a black pistol": handgun's synonym
    assert d == {
        "case_type": "threat",
        "prop_match": True,
        "face_covered_match": None,
        "lighting_match": True,
        "viewpoint_ok": True,
        "realistic": True,
        "plate_cer": None,
        "judge_threat": "threatening",
        "artifact_count": 0,
        "judge_good": True,
    }


@pytest.mark.parametrize(
    ("case", "people", "objects", "match"),
    [
        ("handgun_in_hand", [{"holding": "a firearm"}], [], True),
        ("handgun_in_hand", [{"holding": "nothing", "clothing": "gunmetal jacket"}], [], False),
        ("handgun_in_hand", [{"holding": "two guns"}], [], True),
        ("knife", [{"holding": "a large kitchen knife"}], [], True),
        ("knife", [{"holding": "a phone"}], ["knives on the porch"], True),
        ("knife", [{"holding": "a phone"}], ["door mat"], False),
        ("crowbar_at_door", [{"holding": "a Pry-Bar"}], [], True),
        ("crowbar_at_door", [{"holding": "nothing"}], ["crowbar"], True),
        ("balaclava_ir_night", [{"clothing": "black balaclava", "holding": "nothing"}], [], True),
        ("forced_door", [], ["splintered door frame", "open front door"], True),
        ("forced_door", [], ["front door"], False),
        ("pried_window", [], ["open ground-floor window"], True),
        ("child_alone_pool", [{"clothing": "small child in a swimsuit"}], ["pool"], True),
        ("child_alone_pool", [], ["swimming pool", "toddler"], True),
        ("smoke_from_eave", [], ["gray smoke under the roof"], True),
        ("smoke_from_eave", [], ["house", "porch light"], False),
    ],
)
def test_prop_match_reads_holding_clothing_and_objects(
    case: str, people: list[dict[str, str]], objects: list[str], match: bool
) -> None:
    people = [{"clothing": "", "face_covered": "unclear", "holding": ""} | p for p in people]
    d = _derive(case, people=people, people_count=len(people), notable_objects=objects)
    assert d["prop_match"] is match


def test_prop_terms_come_from_the_first_owl_query_and_the_synonyms() -> None:
    assert j.key_noun("a handgun") == "handgun" and j.key_noun("a ski mask") == "ski mask"
    assert j.key_noun("smoke") == "smoke"
    assert j.prop_terms(_CASES["handgun_in_hand"])[:4] == ("handgun", "gun", "pistol", "firearm")
    assert "pry bar" in j.prop_terms(_CASES["crowbar_at_door"])
    assert j.prop_terms(_CASES["pried_window"]) == ("window",)
    for case in CASES:  # every threat case's key noun is either in the table or bare
        assert j.prop_terms(case)[0] == j.key_noun(case.owl_queries[0])


def test_a_benign_or_unrealistic_threat_image_is_not_judge_good() -> None:
    assert _derive("knife", people=[{"holding": "a knife"}])["judge_good"] is True
    benign = _derive("knife", people=[{"holding": "a knife"}], threat_assessment="benign")
    assert benign["judge_good"] is False and benign["judge_threat"] == "benign"
    partly = _derive("knife", people=[{"holding": "a knife"}], photorealistic="partly")
    assert partly["realistic"] is False and partly["judge_good"] is False
    ambiguous = _derive("knife", people=[{"holding": "a knife"}], threat_assessment="ambiguous")
    assert ambiguous["judge_good"] is True


def test_the_balaclava_case_checks_the_covered_face_and_infrared() -> None:
    covered = [{"clothing": "black ski mask", "face_covered": "yes", "holding": "nothing"}]
    d = _derive("balaclava_ir_night", people=covered, lighting="night_infrared")
    assert (d["face_covered_match"], d["lighting_match"], d["prop_match"]) == (True, True, True)
    bare = [{"clothing": "black jacket", "face_covered": "no", "holding": "nothing"}]
    d = _derive("balaclava_ir_night", people=bare, lighting="night_color")
    assert (d["face_covered_match"], d["lighting_match"], d["prop_match"]) == (False, False, False)
    assert _derive("knife")["face_covered_match"] is None  # no covered face in its prompt


def test_lighting_maps_each_cases_camera() -> None:
    assert _derive("pried_window", lighting="dusk")["lighting_match"] is True
    assert _derive("pried_window", lighting="night_color")["lighting_match"] is False
    assert _derive("smoke_from_eave", lighting="daylight")["lighting_match"] is False
    assert _derive("legible_plate", lighting="daylight")["lighting_match"] is True  # DAY_PLATE


def test_viewpoint_and_artifacts() -> None:
    d = _derive("knife", viewpoint="eye_level", artifacts=["extra fingers", "garbled text"])
    assert d["viewpoint_ok"] is False and d["artifact_count"] == 2


def test_the_plate_case_scores_the_best_plate_text_by_cer() -> None:
    vehicles = [
        {"type": "suv", "plate_text": None},
        {"type": "sedan", "plate_text": "8kxr 41?"},
        {"type": "sedan", "plate_text": "8KXR 417"},  # alphanumerics equal: CER 0
    ]
    d = _derive("legible_plate", vehicles=vehicles, threat_assessment="benign")
    assert d["plate_cer"] == 0.0 and d["case_type"] == "plate"
    assert d["prop_match"] is None and d["judge_good"] is None  # no judge_good for the plate
    one_off = _derive("legible_plate", vehicles=[{"type": "sedan", "plate_text": "8KXR-411"}])
    assert one_off["plate_cer"] == pytest.approx(1 / 7)
    assert _derive("legible_plate", vehicles=[])["plate_cer"] == 1.0  # nothing read
    assert _derive("knife")["plate_cer"] is None


def test_identity_shots_take_their_lighting_from_the_output() -> None:
    out = "images/qwen-image-2.1/identity/2_ir_night.png"
    d = _derive("identity", out, lighting="night_infrared")
    assert d["case_type"] == "identity" and d["lighting_match"] is True
    assert d["judge_good"] is True and d["prop_match"] is None
    nobody = _derive("identity", out, lighting="night_infrared", people_count=0, people=[])
    assert nobody["judge_good"] is False
    dusk = _derive("identity", "images/m/identity/0_dusk.png", lighting="daylight")
    assert dusk["lighting_match"] is False and dusk["judge_good"] is False
    reference = _derive("identity_reference", "images/m/identity/reference.png")
    assert reference["case_type"] == "identity" and reference["lighting_match"] is True


def test_clips_are_judge_good_when_realistic_without_artifacts() -> None:
    out = "clips/ltx-2.5/armed_approach/11.mp4"
    d = _derive("armed_approach", out)
    assert d["case_type"] == "clip" and d["judge_good"] is True
    assert d["prop_match"] is None and d["lighting_match"] is True  # keyframe: handgun, day
    assert _derive("armed_approach", out, artifacts=["melted hand"])["judge_good"] is False
    assert _derive("armed_approach", out, photorealistic="partly")["judge_good"] is False
    walk = _derive("identity_walk", "clips/ltx-2.5/identity_walk/11.mp4", lighting="daylight")
    assert walk["lighting_match"] is True  # keyframe identity:1:day
    for clip in CLIPS:
        assert _derive(clip.id, f"clips/v/{clip.id}/11.mp4")["case_type"] == "clip"


def test_derive_tolerates_a_loosely_typed_answer() -> None:
    record = _record("knife", "images/m/knife/11.png")
    loose = _answer(people_count="2", people=["a man", {"holding": 3}], artifacts=None)
    d = j.derive(record, loose, j.case_of(record))
    assert d["artifact_count"] == 0 and d["prop_match"] is False


def test_identity_people_count_may_arrive_as_a_string() -> None:
    out = "images/m/identity/0_day.png"
    assert _derive("identity", out, people_count="2")["judge_good"] is True
    assert _derive("identity", out, people_count="several")["judge_good"] is False


# --- the CLI: the flagship check, one row per ok output, errors and resume ---


def _root(tmp_path: Path) -> Path:
    """Two ok images, a failed job, a resumed job (failed, then ok) and an ok clip."""
    root = tmp_path / "p1"
    rows = [
        _record("knife", "images/flux2-dev/knife/11.png"),
        _record("knife", "images/flux2-dev/knife/22.png", seed=22),
        _record("knife", "images/flux2-dev/knife/33.png", seed=33, ok=False, error="OOM"),
        _record("legible_plate", "images/flux2-dev/legible_plate/11.png", ok=False, error="x"),
        _record("legible_plate", "images/flux2-dev/legible_plate/11.png"),
        _record(
            "armed_approach",
            "clips/ltx-2.5/armed_approach/11.mp4",
            kind="i2v",
            model="ltx-2.5",
            prompt="motion",
        ),
    ]
    root.mkdir()
    (root / "records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    for row in rows:
        if row["ok"] and row["kind"] != "i2v":
            _png(root / row["output"])
    _write_clip(root / "clips/ltx-2.5/armed_approach/11.mp4", [0, 100, 200])
    return root


def _judged(root: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (root / "judge.jsonl").read_text().splitlines()]


def _main(root: Path, fake: Callable[[httpx.Request], httpx.Response], *extra: str) -> int:
    argv = ["--root", str(root), "--base-url", BASE_URL, *extra]
    return j.main(argv, transport=httpx.MockTransport(fake))


def test_main_stops_when_the_flagship_is_not_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    fake = FakeFlagship(models_status=503)
    assert _main(root, fake) != 0
    assert "flagship is not up (a GPU window may be open)" in capsys.readouterr().err
    assert fake.model_gets == 1 and fake.bodies == []
    assert not (root / "judge.jsonl").exists()


def test_main_stops_when_the_flagship_refuses_the_connection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    root = _root(tmp_path)
    assert _main(root, refused) != 0
    assert "flagship is not up" in capsys.readouterr().err


def test_main_judges_every_ok_output_once_and_resumes(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fake = FakeFlagship()
    assert _main(root, fake, "--workers", "3") == 0
    rows = _judged(root)
    assert sorted(row["output"] for row in rows) == [
        "clips/ltx-2.5/armed_approach/11.mp4",
        "images/flux2-dev/knife/11.png",
        "images/flux2-dev/knife/22.png",
        "images/flux2-dev/legible_plate/11.png",
    ]
    for row in rows:
        assert set(row) >= {
            "output",
            "model",
            "kind",
            "case",
            "seconds",
            "judge_model",
            "answer",
            "derived",
            "error",
        }
        assert row["error"] is None and row["judge_model"] == "claude-flagship"
        assert row["answer"] == _answer() and row["derived"]["realistic"] is True
    clip = next(row for row in rows if row["kind"] == "i2v")
    assert (clip["model"], clip["case"], clip["derived"]["case_type"]) == (
        "ltx-2.5",
        "armed_approach",
        "clip",
    )
    assert all(row["fallbacks"] == [] for row in rows)
    assert len(fake.bodies) == 4
    assert _main(root, fake) == 0  # resumed: every output already has an error-free row
    assert len(fake.bodies) == 4 and len(_judged(root)) == 4


def test_a_failure_writes_an_error_row_and_a_rerun_retries_only_it(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "images/flux2-dev/knife/22.png").unlink()  # an unreadable output
    bad = FakeFlagship("not json at all", json.dumps(_answer()))  # the first reply is bad
    assert _main(root, bad, "--workers", "1") == 0
    rows = _judged(root)
    errors = {row["output"]: row["error"] for row in rows if row["error"]}
    assert len(rows) == 4 and len(errors) == 2
    assert any("FileNotFoundError" in error for error in errors.values())
    assert any("JSON" in error for error in errors.values())
    for row in rows:
        if row["error"]:
            assert row["answer"] is None and row["derived"] is None
    _png(root / "images/flux2-dev/knife/22.png")
    good = FakeFlagship()
    assert _main(root, good) == 0
    assert len(good.bodies) == 2  # only the two error rows are judged again
    latest = {row["output"]: row for row in _judged(root)}
    assert all(row["error"] is None for row in latest.values())


def test_limit_judges_only_the_first_n_pending_outputs(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fake = FakeFlagship()
    assert _main(root, fake, "--limit", "1") == 0
    assert len(_judged(root)) == 1 and len(fake.bodies) == 1
    assert _main(root, fake, "--limit", "2") == 0
    assert len({row["output"] for row in _judged(root)}) == 3


def test_the_model_name_comes_from_v1_models(tmp_path: Path) -> None:
    def models(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "some-other-name"}]})
        return FakeFlagship()(request)

    root = _root(tmp_path)
    assert _main(root, models, "--limit", "1") == 0
    (row,) = _judged(root)
    assert row["judge_model"] == "some-other-name"


def test_main_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHBENCH_ROOT", "/x")
    args = j.parse_args([])
    assert (args.root, args.base_url, args.workers, args.limit) == (
        Path("/x/p1"),
        "http://127.0.0.1:8000/v1",
        8,
        None,
    )

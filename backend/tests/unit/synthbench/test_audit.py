"""`audit` (P5a design §4): the stratified sample, the questions and the page's handler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.audit.page import AuditApp, AuditItem, load_answers
from synthbench.audit.sample import STRATA, allocate, questions, sample
from synthbench.export.vss import ExportedSet


def _set(root: Path, n: int, group: str, lighting: str, **cell: Any) -> ExportedSet:
    event_id = f"B-t-{group}-{lighting}-{n:03d}"
    set_dir = root / "vss" / "x" / event_id
    set_dir.mkdir(parents=True, exist_ok=True)
    (set_dir / "still.jpg").write_bytes(b"jpeg " + event_id.encode())
    facts = {
        "event_id": event_id,
        "cell": {
            "scenario": cell.get("scenario", "knife_visible"),
            "group": group,
            "lighting": lighting,
            "weather": cell.get("weather", "clear"),
        },
        "subjects": cell.get("subjects", [{"class": "person", "role": "intruder"}]),
        "props": cell.get("props", [{"class": "knife", "held_by": "S1"}]),
    }
    return ExportedSet(category="threats", set_dir=set_dir, labels={"synthbench": facts})


def _corpus(root: Path) -> list[ExportedSet]:
    """Every stratum with two lighting values, more members than the stratum samples."""
    sets = []
    for group, k in STRATA:
        for lighting, count in (("day", 2 * k), ("ir_night", k)):
            sets += [_set(root, i, group, lighting) for i in range(count)]
    return sets


def test_allocate_is_proportional_with_one_per_value_and_caps() -> None:
    assert allocate({"day": 60, "ir_night": 30, "dusk": 10}, 10) == {
        "day": 6,
        "dusk": 1,
        "ir_night": 3,
    }
    assert allocate({"day": 100, "fog": 1}, 5) == {"day": 4, "fog": 1}  # one per value first
    assert allocate({"day": 2, "dusk": 1}, 10) == {"day": 2, "dusk": 1}  # never more than exists


def test_the_sample_is_deterministic_and_fills_each_stratum(tmp_path: Path) -> None:
    sets = _corpus(tmp_path)
    first, second = sample(sets), sample(list(reversed(sets)))
    assert [s.item_id for s in first] == [s.item_id for s in second]
    for group, k in STRATA:
        members = [s for s in first if s.facts["cell"]["group"] == group]
        assert len(members) == k
        assert {s.facts["cell"]["lighting"] for s in members} == {"day", "ir_night"}


def test_a_small_stratum_gives_what_it_has(tmp_path: Path) -> None:
    sets = [_set(tmp_path, i, "suspicious", "day") for i in range(3)]
    assert len(sample(sets)) == 3


def test_a_threat_gets_a_prop_question_and_a_benign_scene_does_not(tmp_path: Path) -> None:
    threat = questions(_set(tmp_path, 0, "threat", "day").facts)
    assert [q.key for q in threat] == ["scene", "prop", "people", "conditions"]
    assert "knife visible" in threat[1].text
    assert "knife visible" in threat[0].text.replace("_", " ")
    benign = _set(
        tmp_path, 1, "benign", "ir_night", scenario="delivery_driver", props=[], weather="snow"
    )
    asked = questions(benign.facts)
    assert [q.key for q in asked] == ["scene", "people", "conditions"]
    assert asked[1].text == "Exactly 1 person(s)?"
    assert asked[2].text == "ir night light and snow weather?"


PORT = 8765
# What the owner's browser sends with the page's own answer.
SAME_ORIGIN = {"Host": f"127.0.0.1:{PORT}", "Origin": f"http://127.0.0.1:{PORT}"}


def _app(tmp_path: Path, n: int = 2) -> AuditApp:
    items = [
        AuditItem(s, questions(s.facts))
        for s in (_set(tmp_path, i, "threat", "day") for i in range(n))
    ]
    log = tmp_path / "audits" / "audit.jsonl"
    return AuditApp(items, log, lambda: "2026-09-29T20:00:00Z", port=PORT)


def _body(index: int, question: str, answer: str) -> bytes:
    return json.dumps({"index": index, "question": question, "answer": answer}).encode()


def _answer(app: AuditApp, index: int, question: str, answer: str) -> Any:
    return app.handle("POST", "/answer", _body(index, question, answer), SAME_ORIGIN)


def test_the_page_shows_the_first_open_still(tmp_path: Path) -> None:
    app = _app(tmp_path)
    page = app.handle("GET", "/", b"")
    assert page.status == 200
    assert b"0/2 stills fully answered" in page.body
    assert b'src="/still/0"' in page.body
    for q in app.items[0].questions:
        assert _answer(app, 0, q.key, "y").status == 200
    assert b'src="/still/1"' in app.handle("GET", "/", b"").body


def test_a_still_is_served_only_by_index(tmp_path: Path) -> None:
    app = _app(tmp_path)
    still = app.handle("GET", "/still/1", b"")
    assert still.status == 200
    assert still.body == app.items[1].exported.still.read_bytes()
    assert app.handle("GET", "/still/2", b"").status == 404
    assert app.handle("GET", "/still/../../etc/passwd", b"").status == 404


def test_answers_append_and_the_latest_wins(tmp_path: Path) -> None:
    app = _app(tmp_path)
    assert _answer(app, 0, "scene", "n").status == 200
    assert _answer(app, 0, "scene", "y").status == 200
    lines = app.log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert load_answers(app.log) == {(app.items[0].event_id, "scene"): "y"}
    reopened = _app(tmp_path)  # a restart resumes from the log
    assert reopened.answers == load_answers(app.log)


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"index": 9, "question": "scene", "answer": "y"}',
        b'{"index": 0, "question": "scene", "answer": "maybe"}',
        b'{"index": 0, "question": "weather", "answer": "y"}',
    ],
)
def test_a_bad_answer_is_refused_and_not_logged(tmp_path: Path, body: bytes) -> None:
    app = _app(tmp_path)
    assert app.handle("POST", "/answer", body, SAME_ORIGIN).status == 400
    assert not app.log.exists()


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": f"127.0.0.1:{PORT}", "Origin": "http://evil.example"},  # a page elsewhere
        {"Host": f"127.0.0.1:{PORT}", "Origin": "null"},  # a sandboxed frame or a file
        {"Host": f"evil.example:{PORT}"},  # DNS rebinding: the name, not the address
        {"Host": "127.0.0.1:9999", "Origin": "http://127.0.0.1:9999"},  # another port
        {},  # no Host at all
    ],
    ids=["foreign-origin", "null-origin", "foreign-host", "other-port", "no-host"],
)
def test_a_cross_origin_answer_is_refused_and_not_logged(
    tmp_path: Path, headers: dict[str, str]
) -> None:
    """Any page open in the owner's browser can POST a simple request to the loopback page;
    only the page itself may answer."""
    app = _app(tmp_path)
    assert app.handle("POST", "/answer", _body(0, "scene", "y"), headers).status == 403
    assert not app.log.exists()
    assert app.answers == {}


@pytest.mark.parametrize(
    "headers",
    [
        SAME_ORIGIN,
        {"host": f"localhost:{PORT}", "origin": f"http://localhost:{PORT}"},
        {"Host": f"localhost:{PORT}"},  # a browser may send no Origin on a same-origin POST
    ],
    ids=["127.0.0.1", "localhost-lowercase-names", "no-origin"],
)
def test_a_same_origin_answer_is_logged(tmp_path: Path, headers: dict[str, str]) -> None:
    app = _app(tmp_path)
    assert app.handle("POST", "/answer", _body(0, "scene", "y"), headers).status == 200
    assert load_answers(app.log) == {(app.items[0].event_id, "scene"): "y"}


def test_the_keys_ignore_modifier_combinations(tmp_path: Path) -> None:
    """Ctrl+U (view source) must not answer `u`: the handler returns before reading the key."""
    page = _app(tmp_path).handle("GET", "/", b"").body.decode()
    guard = page.index("if (e.ctrlKey || e.metaKey || e.altKey) return;")
    assert guard < page.index("e.key") and guard < page.index("fetch(")


def test_every_still_answered_says_so(tmp_path: Path) -> None:
    app = _app(tmp_path, n=1)
    for q in app.items[0].questions:
        _answer(app, 0, q.key, "u")
    assert app.next_open() == -1
    assert b"Every still is answered" in app.handle("GET", "/", b"").body

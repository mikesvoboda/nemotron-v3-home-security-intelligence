"""`clip audit sample|page` (ISS-038 acceptance): the write-once draw, and a page that is
provably blind.

The blindness test is the acceptance's teeth: every clip's facts (its spec AND the source
still's, which `clip check` compares fact-for-fact) are retargeted to a KNOWN scenario, and
the fixture greps the declared prop terms, subject classes and frozen motion words out of
every rendered page - a leak (the page reading spec.json, whose frozen motion names the
props) fails here, not in the owner's browser. The grep matches whole words (the motion
question's own text says "camera", which is not the prop "car") over the page with every
`<select>` block stripped, because the choice lists are page furniture: a separate test
pins the scene list to exactly the 32 taxonomy ids, identical on every item, which is what
makes a full-taxonomy list carry no per-clip information.

No subjects line: the clip's subject class/count lives only in spec.json, so the strict
blind page shows none of it (the one declared fact it shows is lighting/weather, carried
onto the draw row precisely so the page never opens a spec).

`TestBias` checks the third step's loading, which the report's own tests cannot see: the
survivor denominator is every clip of the ROUND with a frozen motion (a ready clip the
write-once draw never listed still says something about what H3 survives rendering), and
the two matrices are read out of the answer log the page appended.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from synthbench import cli
from synthbench.audit.clip_page import ClipAuditApp
from synthbench.commands.clip_audit import build_items, clip_audit_log
from synthbench.contract.clip import ClipProvenance, ClipSpec
from synthbench.contract.clip_audit import ClipAuditAnswerRow, ClipAuditDrawRow
from synthbench.contract.spec import Prop, Spec, Subject
from synthbench.taxonomy.model import load_taxonomy

from backend.tests.unit.synthbench import helpers as h

TAX = load_taxonomy()
ROUND = "clips-audit-1"
PORT = 8766
_NOW = "2026-10-07T12:00:00+00:00"
SAME_ORIGIN = {"Host": f"127.0.0.1:{PORT}", "Origin": f"http://127.0.0.1:{PORT}"}

# (scenario, lighting, weather, motion) per clip slot, in event-id order 000..005: two
# ready incidents, then benign spread over four distinct (group, motion) strata. The
# 2-slot mirror takes the two lowest stratum names (allocate's tie-break): benign:crossing
# (slot 3) and benign:in-place (slot 5) - leaving slot 2 (benign:line-of-sight) and slot 4
# (hard_negative:in-place) ready but un-drawn. Slot 1's scenario declares no props.
# Motions name each slot's subject and prop classes with taxonomy terms (rule 1) and land
# one class per stratum: crossing > line-of-sight > in-place is the classifier's order.
_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    ("package_theft", "day", "clear", "The person stays at the porch with a package."),
    ("trying_car_doors", "ir_night", "clear", "The person remains at the car and tries it."),
    ("delivery_driver", "day", "clear", "The person walks up the path with a package."),
    ("neighbor_passing", "day", "rain", "The person walks along the pavement past the hedge."),
    (
        "power_tools_at_night",
        "porch_lit_night",
        "fog",
        "The person stands in place and works with a drill.",
    ),
    ("wildlife", "dusk", "clear", "The deer remains on the patio and circles."),
)

# The page's own sanctioned wording that collides with slot motion words: "clear" (the
# conditions line shows it on every clip) and "place" and "along" (the motion question
# describes the classes in their own words). Each is printed in fixed text, identical on
# every clip, which is what makes it carry no per-clip information; every entry is a word
# the shipped page actually prints, so the stop list stays exactly that - no wider.
_STOP = {"clear", "place", "along"}


def _retarget(store: Any, spec: Spec | ClipSpec, slot: tuple[str, str, str, str]) -> None:
    """Rewrite one spec's FACT_FIELDS onto its slot's scenario, in place. The camera, zone
    and property stay as sampled (they are outside what the audit stratifies, and inventing
    a camera risks a cell the sampler itself would never have drawn); `.updated` revalidates,
    so a bad construction fails loudly here rather than as a mystery exit 2 in `clip check`.
    Both specs of a pair get identical facts - check compares them fact for fact."""
    definition = next(s for s in TAX.scenarios if s.id == slot[0])
    cell = spec.cell.updated(
        scenario=definition.id, group=definition.group, lighting=slot[1], weather=slot[2]
    )
    subjects = tuple(
        Subject(id=f"S{i}", cls=classes[0], role=role)
        for i, (classes, role) in enumerate(((s.one_of, s.role) for s in definition.subjects), 1)
    )
    props = tuple(
        Prop(id=f"X{i}", cls=classes[0], held_by=None if held is None else f"S{held + 1}")
        for i, (classes, held) in enumerate(((p.one_of, p.held_by) for p in definition.props), 1)
    )
    retargeted = spec.updated(
        cell=cell, label=definition.label, risk_band=definition.risk_band,
        subjects=subjects, props=props,
    )  # fmt: skip
    store.replace_json(store.spec_file(spec.event_id), retargeted)


def _retarget_pair(store: Any, specs: list[ClipSpec]) -> None:
    """Retarget each clip AND its source still (check compares their facts)."""
    for spec in specs:
        slot = _SLOTS[int(spec.event_id.rsplit("-", 1)[1])]
        still = store.read(store.spec_file(spec.source.event_id), Spec)
        _retarget(store, still, slot)
        _retarget(store, spec, slot)


def _six_clips(root: Path, triaged: int) -> list[ClipSpec]:
    """Six clips on the slots' cells: retargeted (motions name the retargeted classes, so
    the retarget must precede the freeze), checked, stand-in rendered, and `triaged` of
    them triaged ok - the rest still await a verdict, so they are not ready."""
    specs = h.clip_round(root, n=6, name=ROUND)
    store = h.store(root)
    _retarget_pair(store, specs)
    h.write_motions(
        root,
        ROUND,
        {spec.event_id: _SLOTS[int(spec.event_id.rsplit("-", 1)[1])][3] for spec in specs},
    )
    assert h.run(root, "clip", "check", "--round", ROUND) == cli.EXIT_OK
    specs = [store.read(store.spec_file(spec.event_id), ClipSpec) for spec in specs]
    for spec in specs:
        h.record_clip(root, spec)
    h.write_clip_triage(
        root, ROUND, [{"event_id": s.event_id, "k": 1, "verdict": "ok"} for s in specs[:triaged]]
    )
    assert h.run(root, "clip", "triage", "--round", ROUND) == cli.EXIT_OK
    return specs


def _ready_round(root: Path) -> list[ClipSpec]:
    """All six triaged ok: the state the audit samples from."""
    return _six_clips(root, triaged=6)


def _manifest(root: Path) -> Path:
    return h.store(root).round_dir(ROUND) / "audit-draw.jsonl"


def _draw(root: Path) -> list[ClipAuditDrawRow]:
    lines = _manifest(root).read_text(encoding="utf-8").splitlines()
    return [ClipAuditDrawRow.model_validate_json(line) for line in lines if line.strip()]


def _log(root: Path) -> Path:
    return clip_audit_log(TAX.version, ROUND, h.env(root))


def _answers(root: Path) -> list[dict[str, Any]]:
    lines = _log(root).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _app(root: Path) -> ClipAuditApp:
    assert h.run(root, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_OK
    return ClipAuditApp(build_items(h.store(root), ROUND), _log(root), lambda: _NOW, port=PORT)


def _strip_selects(html: str) -> str:
    """The page without its choice lists: what the leak grep reads. The lists are the
    method (fixed per question, the same on every clip), not per-clip content."""
    return re.sub(r"<select\b.*?</select>", " ", html, flags=re.DOTALL | re.IGNORECASE)


def _scene_select(html: str) -> str:
    match = re.search(r'<select name="scene".*?</select>', html, flags=re.DOTALL)
    assert match is not None
    return match.group(0)


class TestSample:
    def test_the_draw_is_the_ready_incident_census_plus_a_benign_mirror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ready_round(tmp_path)
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_OK
        rows = _draw(tmp_path)
        incidents = [row for row in rows if row.basis == "ready-census"]
        assert [(row.scenario, row.side, row.basis) for row in incidents] == [
            ("package_theft", "incident", "ready-census"),
            ("trying_car_doors", "incident", "ready-census"),
        ]
        # The row carries the conditions the page may show: the page reads lighting and
        # weather from the manifest, never from a spec.
        assert [(row.lighting, row.weather) for row in incidents] == [
            ("day", "clear"),
            ("ir_night", "clear"),
        ]
        benign = [row for row in rows if row.basis == "benign-stratified"]
        assert [(row.scenario, row.intended_motion) for row in benign] == [
            ("neighbor_passing", "crossing"),
            ("wildlife", "in-place"),
        ]
        assert all(row.side == "benign" for row in benign)
        assert [row.event_id for row in rows] == [
            "C-clips-audit-1-000",
            "C-clips-audit-1-001",
            "C-clips-audit-1-003",
            "C-clips-audit-1-005",
        ]  # ordered incident, benign, flagged; each side by event id
        out = capsys.readouterr().out
        assert "audit sample clips-audit-1" in out and "census 2" in out

    def test_the_manifest_is_write_once_and_a_rerun_exits_1(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_OK
        first = _manifest(tmp_path).read_bytes()
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_ERROR
        assert _manifest(tmp_path).read_bytes() == first

    def test_a_clip_made_ready_after_the_freeze_does_not_join_the_audit(
        self, tmp_path: Path
    ) -> None:
        # The census is write-once precisely so a render window cannot reshuffle a
        # half-audited set mid-audit; the enlarged draw is the next round's manifest.
        specs = _six_clips(tmp_path, triaged=5)
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_OK
        frozen = {row.event_id for row in _draw(tmp_path)}
        assert specs[5].event_id not in frozen  # the straggler awaits its verdict
        h.write_clip_triage(
            tmp_path, ROUND, [{"event_id": specs[5].event_id, "k": 1, "verdict": "ok"}]
        )
        assert h.run(tmp_path, "clip", "triage", "--round", ROUND) == cli.EXIT_OK
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_ERROR
        assert {row.event_id for row in _draw(tmp_path)} == frozen

    def test_flagged_rows_join_once_and_a_foreign_event_exits_1(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        flags = tmp_path / "flags.jsonl"
        # Foreign first: a flag on a clip of another round fails the WHOLE run before
        # anything is written - a partly-applied pre-screen is no pre-screen.
        flags.write_text(json.dumps({"event_id": "B-pilot-1-000", "flagged_by": "x"}) + "\n")
        assert (
            h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND, "--flagged", str(flags))
            == cli.EXIT_ERROR
        )
        assert not _manifest(tmp_path).exists()
        # 004 (hard_negative) is ready but outside the 2-slot mirror: the flag brings it
        # in; 000 is already censused and must not be listed twice.
        flagged = {"event_id": "C-clips-audit-1-004", "flagged_by": "motion-absent", "note": "static"}  # fmt: skip
        flags.write_text(
            json.dumps({"event_id": "C-clips-audit-1-000", "flagged_by": "prop-presence"})
            + "\n"
            + json.dumps(flagged)
            + "\n",
            encoding="utf-8",
        )
        assert (
            h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND, "--flagged", str(flags))
            == cli.EXIT_OK
        )
        drawn = _draw(tmp_path)
        assert [row.event_id for row in drawn].count("C-clips-audit-1-000") == 1
        assert [row.event_id for row in drawn if row.basis == "flagged"] == ["C-clips-audit-1-004"]

    def test_an_unsampled_round_and_an_empty_draw_exit_1(self, tmp_path: Path) -> None:
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_ERROR
        h.frozen_round(tmp_path, n=2, name=ROUND)  # nothing rendered or triaged yet
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_ERROR
        assert not _manifest(tmp_path).exists()  # an empty draw writes no manifest


class TestPage:
    """The handler over the drawn manifest, loaded through `build_items` - the command's
    own loader, the only component that reads the corpus - so the greps catch a leak
    wherever it lives."""

    def test_no_page_names_a_declared_scenario_prop_subject_or_motion_word(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        leaks = _leak_terms()
        pages = [app.handle("GET", "/", b"")]
        pages += [app.handle("GET", f"/item/{i}", b"") for i in range(len(app.items))]
        assert len(pages) == 5  # home + the four drawn items
        for page in pages:
            assert page.status == 200
            text = _strip_selects(page.body.decode(encoding="utf-8")).lower()
            for term in leaks:
                assert not re.search(rf"\b{re.escape(term)}\b", text), term
            for scenario in TAX.scenarios:
                assert scenario.id not in text  # ids live only inside the scene list

    def test_the_item_shows_the_declared_conditions_the_video_and_the_clip_only(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        page = app.handle("GET", "/item/0", b"").body.decode(encoding="utf-8")
        assert "day light and clear weather?" in page
        assert "<video" in page and 'src="/clip/0"' in page
        rain = app.handle("GET", "/item/2", b"").body.decode(encoding="utf-8")
        assert "day light and rain weather?" in rain  # slot 3 is draw position 2

    def test_the_scene_pick_lists_the_whole_taxonomy_unselected_on_every_clip(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        expected = sorted(s.id for s in TAX.scenarios)
        for index in (0, 3):
            page = app.handle("GET", f"/item/{index}", b"").body.decode(encoding="utf-8")
            block = _scene_select(page)
            assert re.findall(r'<option value="([a-z_]+)"', block) == expected
            assert "selected" not in block  # the same full list everywhere: it says nothing

    def test_a_scene_pick_opens_the_prop_question_named_by_the_auditors_own_pick(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        # knife_visible is nobody's declared scenario here and its prop is in no slot
        # motion - the question text can only come from the taxonomy entry for the PICK.
        post = {"index": 0, "question": "scene", "pick": "knife_visible"}
        assert app.handle("POST", "/answer", json.dumps(post).encode(), SAME_ORIGIN).status == 200
        page = app.handle("GET", "/item/0", b"").body.decode(encoding="utf-8")
        assert "Is the knife visible?" in page
        prop = {"index": 0, "question": "prop", "answer": "y"}
        assert app.handle("POST", "/answer", json.dumps(prop).encode(), SAME_ORIGIN).status == 200

    def test_a_pick_whose_scenario_declares_no_props_asks_no_prop_question(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        post = {"index": 0, "question": "scene", "pick": "loitering"}
        assert app.handle("POST", "/answer", json.dumps(post).encode(), SAME_ORIGIN).status == 200
        page = app.handle("GET", "/item/0", b"").body.decode(encoding="utf-8")
        assert not re.search(r"Is the [a-z ]+ visible\?", page)

    def test_the_answer_log_holds_contract_rows_and_the_latest_answer_wins(
        self, tmp_path: Path
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        first = app.handle(
            "POST",
            "/answer",
            json.dumps({"index": 0, "question": "motion", "pick": "crossing"}).encode(),
            SAME_ORIGIN,
        )
        assert first.status == 200 and json.loads(first.body)["next"] == 0
        again = {"index": 0, "question": "motion", "pick": "in-place"}
        assert app.handle("POST", "/answer", json.dumps(again).encode(), SAME_ORIGIN).status == 200
        rows = _answers(tmp_path)
        assert all(ClipAuditAnswerRow.model_validate(row) for row in rows)
        motion = [row for row in rows if row["question"] == "motion"]
        assert [row["pick"] for row in motion] == ["crossing", "in-place"]
        assert all(row["time"] == _NOW for row in rows)
        assert all(row["event_id"] == "C-clips-audit-1-000" for row in rows)
        item = app.handle("GET", "/item/0", b"").body.decode(encoding="utf-8")
        assert ">in-place<" in item  # the shown mark is the latest, not the first

    def test_a_cross_origin_post_is_refused_and_writes_nothing(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        body = json.dumps({"index": 0, "question": "motion", "pick": "crossing"}).encode()
        assert app.handle("POST", "/answer", body, {"Host": "evil.example"}).status == 403
        assert (
            app.handle(
                "POST", "/answer", body, {**SAME_ORIGIN, "Origin": "http://evil.example"}
            ).status
            == 403
        )
        assert not _log(tmp_path).exists()

    def test_a_bad_answer_is_400(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        for body in (
            {"index": 0, "question": "motion", "pick": "floating"},
            {"index": 0, "question": "scene", "pick": "not_a_scenario"},  # the row allows it
            {"index": 0, "question": "scene", "answer": "y"},
            {"index": 0, "question": "prop", "answer": "maybe"},
            {"index": 0, "question": "prop", "answer": "y"},  # no scene pick yet: no prop asked
            {"index": 99, "question": "motion", "pick": "crossing"},
            {"index": 0, "question": "nonsense", "answer": "y"},
            {"index": 0, "question": "threat", "answer": "y", "pick": "threat"},
        ):
            response = app.handle("POST", "/answer", json.dumps(body).encode(), SAME_ORIGIN)
            assert response.status == 400, body
        assert not _log(tmp_path).exists()

    def test_the_clip_route_serves_the_ready_attempts_mp4_bytes(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        store = h.store(tmp_path)
        event_id = app.items[0].event_id
        prov = store.read(store.provenance_file(event_id), ClipProvenance)
        assert prov.attempts[-1].clip is not None
        raw = (store.event_dir(event_id) / prov.attempts[-1].clip.path).read_bytes()
        response = app.handle("GET", "/clip/0", b"")
        assert (response.status, response.content_type) == (200, "video/mp4")
        assert response.body == raw
        assert app.handle("GET", "/clip/99", b"").status == 404

    def test_the_page_opens_where_work_remains_and_ends_when_done(self, tmp_path: Path) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)
        assert app.next_open() == 0
        for index, item in enumerate(app.items):
            answers = {
                "motion": ("pick", "in-place"),
                "scene": ("pick", "resident_arrival"),  # propless: nothing opens behind it
                "conditions": ("answer", "y"),
                "threat": ("pick", "none"),
            }
            for key, (shape, value) in answers.items():
                body = {"index": index, "question": key, shape: value}
                posted = app.handle("POST", "/answer", json.dumps(body).encode(), SAME_ORIGIN)
                assert posted.status == 200, body
            assert app.answered(item)
        assert app.next_open() == -1
        home = app.handle("GET", "/", b"").body.decode(encoding="utf-8")
        assert "every clip is answered" in home.lower()

    def test_a_prop_answer_goes_stale_when_the_scene_pick_moves_on(self, tmp_path: Path) -> None:
        # The prop question belongs to the auditor's CURRENT pick: leave the prop-declaring
        # scenario and the answered mark must not count for the new one (the stale row is
        # inert, and returning to the first pick revives it - latest per (event, question)).
        _ready_round(tmp_path)
        app = _app(tmp_path)
        for body in (
            {"index": 0, "question": "scene", "pick": "knife_visible"},
            {"index": 0, "question": "prop", "answer": "y"},
        ):
            assert (
                app.handle("POST", "/answer", json.dumps(body).encode(), SAME_ORIGIN).status == 200
            )
        for key, (shape, value) in {
            "motion": ("pick", "in-place"),
            "conditions": ("answer", "y"),
            "threat": ("pick", "record"),
        }.items():
            body = {"index": 0, "question": key, shape: value}
            assert (
                app.handle("POST", "/answer", json.dumps(body).encode(), SAME_ORIGIN).status == 200
            )
        assert app.answered(app.items[0])  # knife_visible asked a prop; it was answered
        move_on = {"index": 0, "question": "scene", "pick": "loitering"}
        assert (
            app.handle("POST", "/answer", json.dumps(move_on).encode(), SAME_ORIGIN).status == 200
        )
        assert not app.answered(app.items[0])  # loitering asks no prop: the old mark is inert
        back = {"index": 0, "question": "scene", "pick": "knife_visible"}
        assert app.handle("POST", "/answer", json.dumps(back).encode(), SAME_ORIGIN).status == 200
        assert app.answered(app.items[0])  # the latest prop row answers this pick again


def _bias(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert h.run(root, "clip", "audit", "bias", "--round", ROUND) == cli.EXIT_OK
    return capsys.readouterr().out


class TestBias:
    """`clip audit bias`'s loading, which is the report's own half of the risk: the survivor
    denominator is the ROUND (every clip with a frozen motion, drawn or not - the rates
    describe the corpus the measurement runs on), and the matrices read the answer log the
    page wrote, latest answer per (clip, question)."""

    def test_the_rates_are_over_the_round_and_survive_a_late_ready_clip(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Slots: in-place x4 (000, 001, 004, 005), line-of-sight x1 (002), crossing x1
        # (003). Five are decided here; slot 5 still awaits its verdict, so it is neither a
        # survivor nor a casualty and rides at the end of its class's line.
        specs = _six_clips(tmp_path, triaged=5)
        assert h.run(tmp_path, "clip", "audit", "sample", "--round", ROUND) == cli.EXIT_OK
        out = _bias(tmp_path, capsys)
        assert f"clip audit bias {ROUND} (corpus {TAX.version})" in out
        assert "crossing: 1/1 ready (100.0 %" in out  # the drawn slot 3
        assert "line-of-sight: 1/1 ready (100.0 %" in out  # slot 2, ready and UNDRAWN
        assert "in-place: 3/3 ready (100.0 %" in out and ", 1 open" in out
        assert "answered 0 of 4 drawn clips" in out
        assert "frame-sampled from rendered clips" in out  # the disclosures bind at once
        # The straggler's verdict arrives after the freeze: it joins no audit, but its
        # survival is a fact about this round's render and belongs in the rate.
        h.write_clip_triage(
            tmp_path, ROUND, [{"event_id": specs[5].event_id, "k": 1, "verdict": "ok"}]
        )
        assert h.run(tmp_path, "clip", "triage", "--round", ROUND) == cli.EXIT_OK
        out = _bias(tmp_path, capsys)
        assert "in-place: 4/4 ready (100.0 %" in out and "1 open" not in out

    def test_the_matrices_count_the_owners_picks_against_the_declaration(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ready_round(tmp_path)
        app = _app(tmp_path)  # drawn: 000 package_theft, 001, 003 neighbor_passing, 005
        for index, answers in (
            (
                0,
                {
                    "motion": ("pick", "in-place"),
                    "scene": ("pick", "package_theft"),  # the auditor recovers the scene
                    "prop": ("answer", "y"),
                    "conditions": ("answer", "y"),
                    "threat": ("pick", "threat"),
                },
            ),
            (
                2,
                {  # index 2 is the drawn neighbor_passing, answered under a WRONG pick
                    "motion": ("pick", "in-place"),
                    "scene": ("pick", "package_theft"),
                    "conditions": ("answer", "y"),
                    "threat": ("pick", "none"),
                },
            ),
        ):
            for key, (shape, value) in answers.items():
                body = {"index": index, "question": key, shape: value}
                posted = app.handle("POST", "/answer", json.dumps(body).encode(), SAME_ORIGIN)
                assert posted.status == 200, body
        out = _bias(tmp_path, capsys)
        assert "scene agreement 1/2 (50.0 %" in out
        assert "  neighbor_passing -> package_theft: 1" in out  # the mislabel, named
        assert "threat agreement 2/2 (100.0 %" in out  # a benign clip's none is agreement
        assert "answered 1 of 4 drawn clips; prop marks: y 1, n 0, u 0" in out


def _leak_terms() -> tuple[str, ...]:
    """What spec.json declares that no page may print (outside the stripped choice lists):
    the six scenarios' prop terms and subject classes plus the frozen motions' words longer
    than three letters, minus the page's own sanctioned wording (_STOP). The declared
    scenario ids are checked separately against the whole taxonomy, not from the slots."""
    words = {
        word
        for slot in _SLOTS
        for word in slot[3].lower().replace(".", "").split()
        if len(word) > 3 and word not in _STOP
    }
    declared = set(words)
    for slot in _SLOTS:
        definition = next(s for s in TAX.scenarios if s.id == slot[0])
        declared.update(cls for prop in definition.props for cls in prop.one_of)
        declared.update(cls for subject in definition.subjects for cls in subject.one_of)
    terms: set[str] = set()
    for name in declared:
        terms.add(name)
        terms.add(name.replace("_", " "))
    return tuple(sorted(terms))

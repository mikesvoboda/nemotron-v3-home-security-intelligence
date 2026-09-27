"""Pins for `backend/evaluation/vlm_replay.py` (Phase 2, task 2.1).

Everything here runs against a fake client through the `make_client` seam -
the real GPU run is the ledger row, not a unit test. The pins that matter are
the ones a convenient implementation would break: a stored specialist block
must reach the request BYTE-IDENTICALLY (it is the replay's whole premise),
a refusal must land as `verification_failed` + NULL + the error class (never
a default score - S5 at the row), and the module must not import the
specialist stage or the legacy harness AT ALL (rev 6's rule and F10).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.vlm_replay import (
    replay_item,
    run_replay,
    save_vlm_report,
)
from backend.services.vlm_client import VlmTransportError
from backend.services.vlm_verdict import (
    VlmAssessRequest,
    VlmCriterion,
    VlmProvenance,
    VlmVerdict,
)

REPLAY_SRC = Path(__file__).resolve().parents[4] / "backend" / "evaluation" / "vlm_replay.py"


def _verdict(verdict: str = "confirmed", score: int = 70) -> VlmVerdict:
    return VlmVerdict(
        verdict=verdict,
        risk_score=score,
        summary="person at the door",
        reasoning="matches household pattern",
        description="an adult walking up the front path",
        criteria=[VlmCriterion(name="loitering", passed=True, evidence="under 60s")],
        provenance=VlmProvenance(engine="test-llama", model_id="fake@1"),
    )


class FakeClient:
    """Doubles the slice of VlmClient the replay uses: assess + close."""

    def __init__(self, results: dict[str, object]) -> None:
        self._results = results  # item_id -> VlmVerdict | Exception factory
        self.requests: dict[str, VlmAssessRequest] = {}
        self.closed = 0

    async def assess(self, request: VlmAssessRequest):
        # route by the first image path (the fake's item key)
        key = request.image_paths[0]
        outcome = self._results[key]
        if isinstance(outcome, BaseException):
            raise outcome
        self.requests[key] = request
        return outcome

    async def close(self) -> None:
        self.closed += 1


def _item(
    tmp_path: Path,
    n: int,
    *,
    label: str = "incident",
    expected: int = 80,
    media: bool = True,
    specialist: dict[str, str] | None = None,
) -> EvalItem:
    frame = tmp_path / f"frame_{n}.jpg"
    if media:
        frame.write_bytes(b"\xff\xd8z" * 500)
    return EvalItem(
        item_id=f"item-{n}",
        media_paths=[str(frame)] if media else [],
        expected_label=label,
        expected_risk_score=expected,
        snapshot=AssessInput(
            camera_id="cam-front",
            detections=[],
            zones=["front_yard"],
            timestamp="2026-09-27T00:00:00+00:00",
            specialist_outputs=specialist or {},
        ),
        source="synthetic",
    )


def _store(tmp_path: Path, items: list[EvalItem]) -> EvalStore:
    store = EvalStore(tmp_path / "eval.sqlite")
    for it in items:
        store.put_item(it)
    return store


class TestReplayItem:
    async def test_stored_specialist_outputs_reach_the_request_verbatim(self, tmp_path) -> None:
        """The replay's premise (rev 6): the stored text IS the prompt input.
        A copy that normalizes, re-renders, or drops a key here means the
        bake-off measured something other than what was frozen."""
        spec = {
            "faces": "known person Dad (78% match)",
            "plates": "unavailable: specialist did not run",
            "person_reid": "unavailable (re-enroll)",
        }
        item = _item(tmp_path, 1, specialist=spec)
        fake = FakeClient({item.media_paths[0]: _verdict()})
        row = await replay_item(fake, item)
        sent = fake.requests[item.media_paths[0]].context.specialist_outputs
        assert sent == spec
        assert row["verdict"] == "confirmed"
        assert row["risk_score"] == 70
        assert row["raw_response"]["provenance"]["model_id"] == "fake@1"

    async def test_the_rest_of_the_snapshot_mirrors(self, tmp_path) -> None:
        item = _item(tmp_path, 2)
        fake = FakeClient({item.media_paths[0]: _verdict()})
        await replay_item(fake, item)
        ctx = fake.requests[item.media_paths[0]].context
        assert ctx.camera_id == "cam-front"
        assert ctx.zones == ["front_yard"]
        assert ctx.zone_crossing is False
        assert ctx.timestamp == "2026-09-27T00:00:00+00:00"

    async def test_more_than_four_frames_truncates_to_the_wire_limit(self, tmp_path) -> None:
        frames = []
        for i in range(6):
            f = tmp_path / f"f{i}.jpg"
            f.write_bytes(b"\xff\xd8z" * 100)
            frames.append(str(f))
        item = _item(tmp_path, 3)
        item = item.model_copy(update={"media_paths": frames})
        fake = FakeClient({frames[0]: _verdict()})
        await replay_item(fake, item)
        assert len(fake.requests[frames[0]].image_paths) == 4

    async def test_a_refusal_lands_null_with_the_error_class_never_a_score(self, tmp_path) -> None:
        """S5 at the row level. A score here (or a missing error class) means
        a refusal was folded into the distribution - the null-lie at the
        reader that computes the report."""
        item = _item(tmp_path, 4)
        err = VlmTransportError("connection refused")
        fake = FakeClient({item.media_paths[0]: err})
        row = await replay_item(fake, item)
        assert row["verdict"] == "verification_failed"
        assert row["risk_score"] is None
        assert row["raw_response"]["error"] == "VlmTransportError"
        assert "50" not in json.dumps(row["raw_response"])  # the analyzer's old lie

    async def test_a_bug_propagates_loud_not_degraded(self, tmp_path) -> None:
        """The ladder covers engine failures, not programming errors - the
        replay mirrors `vlm_analyzer._DEGRADABLE_ERRORS` exactly."""
        item = _item(tmp_path, 5)
        fake = FakeClient({item.media_paths[0]: TypeError("harness bug")})
        with pytest.raises(TypeError):
            await replay_item(fake, item)

    def test_the_degradeable_set_is_the_analyzers_set(self) -> None:
        """Pinned as a SET of names, not a re-import: if the analyzer's ladder
        grows a class and the replay's silently doesn't, a bake-off run would
        crash where production degrades - and the numbers would describe two
        different systems."""
        from backend.evaluation import vlm_replay
        from backend.services import vlm_analyzer

        assert {c.__name__ for c in vlm_replay._DEGRADABLE_ERRORS} == {
            c.__name__ for c in vlm_analyzer._DEGRADABLE_ERRORS
        }, "the replay's ladder drifted from the analyzer's"


class TestRunReplay:
    async def test_writes_run_and_results_rows(self, tmp_path) -> None:
        items = [_item(tmp_path, 1), _item(tmp_path, 2, label="benign", expected=10)]
        store = _store(tmp_path, items)
        results = {
            items[0].media_paths[0]: _verdict("confirmed", 90),
            items[1].media_paths[0]: _verdict("rejected", 10),
        }

        def make() -> FakeClient:
            return FakeClient(results)

        report = await run_replay(store, candidate="Fake-1B-Q4@test", make_client=make)
        rows = store.replay(report["run_id"])
        assert {r["item_id"] for r in rows} == {"item-1", "item-2"}
        run = store._db.execute("SELECT engine, model FROM runs").fetchone()
        assert run[0] == "llama.cpp"
        # the run's model string says WHAT and WHERE - candidate@commit
        assert run[1].startswith("Fake-1B-Q4@")
        assert re.search(r"@(?:[0-9a-f]{7,40}|unknown)$", run[1]), "commit pin missing"

    async def test_the_report_names_the_endpoint_it_measured(self, tmp_path) -> None:
        """Two candidates on two published ports is 2.2's whole shape, and the
        one way to mix them up is a report that never says which URL it
        called. A named endpoint must reach the report verbatim."""
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:
            return FakeClient({items[0].media_paths[0]: _verdict()})

        report = await run_replay(
            store, candidate="F@test", make_client=make, endpoint="http://host:18123"
        )
        assert report["vlm_url"] == "http://host:18123"
        # an injected factory owns its transport: the harness must NOT claim a
        # URL it cannot verify it called.
        assert report["vlm_url_source"] == "injected"

    async def test_an_unnamed_endpoint_is_resolved_once_and_recorded_as_such(
        self, tmp_path, monkeypatch
    ) -> None:
        """The stale-env case: `AI_VLM_URL` pointing at the wrong candidate
        produces a green-looking run that measured the wrong model. The run
        cannot prevent that, but it can refuse to hide it - the URL AND its
        source both land in the report, from ONE resolution."""
        import backend.evaluation.vlm_replay as vr

        seen: list[str] = []

        class SpyClient:
            def __init__(self, base_url: str) -> None:
                seen.append(base_url)

            async def assess(self, request):  # pragma: no cover - trivial
                return _verdict()

            async def close(self) -> None:
                pass

        monkeypatch.setattr(vr, "VlmClient", SpyClient)
        monkeypatch.setattr(
            vr, "get_settings", lambda: SimpleNamespace(ai_vlm_url="http://settings-wins:8098")
        )
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)
        report = await run_replay(store, candidate="F@test")  # no make_client, no endpoint
        assert seen == ["http://settings-wins:8098"]  # the client got THAT url
        assert report["vlm_url"] == "http://settings-wins:8098"  # and the report says it
        assert report["vlm_url_source"] == "settings"

    async def test_latency_is_reported_but_never_stored_in_results(self, tmp_path) -> None:
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:
            return FakeClient({items[0].media_paths[0]: _verdict()})

        report = await run_replay(store, candidate="F@test", make_client=make)
        assert report["latency_ms_indicative_only"]["n"] == 1
        stored = store.replay(report["run_id"])[0]
        assert "latency_ms" not in stored  # the results table has no such column
        assert report["latency_ms_indicative_only"]["note"].startswith("GB300")

    async def test_empty_generation_refuses_loudly(self, tmp_path) -> None:
        store = _store(tmp_path, [_item(tmp_path, 1, media=False)])  # gen-1's shape
        with pytest.raises(FileNotFoundError, match="media-bearing"):
            await run_replay(store, candidate="F@test", make_client=FakeClient)

    async def test_all_items_mode_refuses_with_the_wire_reason(self, tmp_path) -> None:
        """min_length=1 on image_paths is a property of the shipped wire, not
        of this harness - the refusal must say so, because it is the same
        sentence the owner needs about the 408 label-only items (item 19)."""
        store = _store(tmp_path, [_item(tmp_path, 1)])
        with pytest.raises(ValueError, match="image"):
            await run_replay(
                store, candidate="F@test", with_media_only=False, make_client=FakeClient
            )

    async def test_limit_replays_a_prefix_deterministically(self, tmp_path) -> None:
        items = [_item(tmp_path, n) for n in (1, 2, 3)]
        store = _store(tmp_path, items)
        results = {it.media_paths[0]: _verdict() for it in items}

        def make() -> FakeClient:
            return FakeClient(results)

        report = await run_replay(store, candidate="F@test", limit=2, make_client=make)
        ids = {r["item_id"] for r in store.replay(report["run_id"])}
        assert ids == {"item-1", "item-2"}  # ordered by item_id, stable prefix

    async def test_one_client_per_run_closed_once(self, tmp_path) -> None:
        """The shipped client documents itself as "one client per endpoint" and
        caches its enforcement proof PER INSTANCE on purpose (S-2: a proof must
        not launder onto another build). A fresh client per item therefore
        re-probes per item - and five probe failures trip the SHARED `ai-vlm`
        breaker, after which every remaining item answers
        `VlmUnavailableError` without I/O. The report would then describe a
        breaker, not a model. One run IS one endpoint and one build, so one
        instance is the client's own correct lifetime.

        (This replaced a pin that asserted the per-item close as real. The
        close stays real; the LIFETIME was wrong, and the cost was measured on
        the 2.1.6 smoke's repro - ledger finding B.)
        """
        items = [_item(tmp_path, n) for n in (1, 2, 3)]
        store = _store(tmp_path, items)
        results = {it.media_paths[0]: _verdict() for it in items}
        made: list[FakeClient] = []

        def make() -> FakeClient:
            c = FakeClient(results)
            made.append(c)
            return c

        await run_replay(store, candidate="F@test", make_client=make)
        assert len(made) == 1, "a client per item re-probes per item (finding B)"
        assert [c.closed for c in made] == [1], "the one client is closed exactly once"

    async def test_the_client_is_closed_even_when_an_item_raises_loudly(self, tmp_path) -> None:
        """One client per run means the close is no longer inside a per-item
        `finally`: a propagating bug (the ladder covers engine failures, not
        programming errors) must still not leak the httpx lifecycle."""
        items = [_item(tmp_path, n) for n in (1, 2)]
        store = _store(tmp_path, items)
        made: list[FakeClient] = []

        def make() -> FakeClient:
            c = FakeClient({items[0].media_paths[0]: TypeError("harness bug")})
            made.append(c)
            return c

        with pytest.raises(TypeError):
            await run_replay(store, candidate="F@test", make_client=make)
        assert [c.closed for c in made] == [1]

    async def test_a_refusal_after_start_run_still_stores_its_row(self, tmp_path) -> None:
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:
            return FakeClient({items[0].media_paths[0]: VlmTransportError("boom")})

        report = await run_replay(store, candidate="F@test", make_client=make)
        (row,) = store.replay(report["run_id"])
        assert row["verdict"] == "verification_failed"
        assert row["risk_score"] is None


class TestReportIsAggregateOnly:
    async def test_no_per_item_content_leaks_into_the_report(self, tmp_path) -> None:
        """D10: the report that goes anywhere near git is rates + n + Wilson.
        A key that carries item ids or summaries is a privacy leak by shape."""
        items = [
            _item(tmp_path, 1, specialist={"faces": "known person Dad"}),
            _item(tmp_path, 2, label="benign", expected=10),
        ]
        store = _store(tmp_path, items)
        results = {
            items[0].media_paths[0]: _verdict("confirmed", 90),
            items[1].media_paths[0]: _verdict("confirmed", 40),  # an FP
        }

        def make() -> FakeClient:
            return FakeClient(results)

        report = await run_replay(store, candidate="F@test", make_client=make)
        blob = json.dumps(report)
        assert "Dad" not in blob
        assert "front_yard" not in blob
        assert "frame_" not in blob
        assert report["s2"]["fp"] == 1 and report["s2"]["n"] == 1
        assert report["s3"]["all"]["n"] == 1
        path = save_vlm_report(report, tmp_path / "reports" / "r.json")
        assert json.loads(path.read_text())["s2"]["fp"] == 1


class TestModuleHygiene:
    """AST pins (the coverage-gate tests' own doctrine): the two module-level
    prohibitions are runtime path decisions an import-time check cannot
    express more cheaply than by reading the source."""

    def _imported_modules(self) -> set[str]:
        tree = ast.parse(REPLAY_SRC.read_text(encoding="utf-8"))
        mods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module)
        return mods

    def test_never_imports_the_specialist_stage(self) -> None:
        assert not any("vlm_specialists" in m for m in self._imported_modules()), (
            "replay re-running a specialist is the rev-6 rule violated"
        )

    def test_never_imports_the_legacy_harness(self) -> None:
        assert not any(m.endswith("evaluation.harness") for m in self._imported_modules()), (
            "F10: the vlm replay stands beside the legacy harness, not on it"
        )

    def test_constrained_decoding_error_is_in_the_ladder(self) -> None:
        assert any(m.endswith("nemotron_analyzer") for m in self._imported_modules())

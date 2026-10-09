"""Pins for `backend/evaluation/vlm_replay.py` (Phase 2, task 2.1).

Everything here runs against a fake client through the `make_client` seam -
the real GPU run is the ledger row, not a unit test. The pins that matter are
the ones a convenient implementation would break: a stored specialist block
must reach the request BYTE-IDENTICALLY (it is the replay's whole premise),
a refusal must land as `verification_failed` + NULL + the error class (never
a default score - S5 at the row), and the module must not import the
specialist stage AT ALL (rev 6's rule).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.vlm_replay import (
    client_factory,
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
        assert row["risk_level"] is None  # the analyzer's NULL level, never a band
        assert row["raw_response"]["error"] == "VlmTransportError"
        # The analyzer's old lie was a refusal arriving WITH a score; "50 not
        # in the dump" pinned nothing (it fails on any message containing
        # "50", passes any real default-score regression in another field).
        # The risk of it re-appearing is the row SHAPE: no key other than
        # verdict/item_id/raw_response/latency carries a number, and no
        # scored key exists to drift into. `risk_level` is the analyzer's
        # level slot (B1.2), NULL on this path as it is on the event row.
        assert set(row) == {
            "item_id",
            "verdict",
            "risk_score",
            "risk_level",
            "raw_response",
            "latency_ms",
        }

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

    async def test_an_injected_factory_names_no_url(self, tmp_path) -> None:
        """An injected factory owns its transport; the harness cannot verify
        what it dials, so the report says `injected` and names no URL. The
        D10 leak pins use this shape (factory without endpoint) and rely on
        vlm_url being absent rather than an unverified echo."""
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:
            return FakeClient({items[0].media_paths[0]: _verdict()})

        report = await run_replay(store, candidate="F@test", make_client=make)
        assert report["vlm_url"] is None
        assert report["vlm_url_source"] == "injected"

    async def test_naming_an_endpoint_alongside_a_factory_is_refused(self, tmp_path) -> None:
        """The docstring here used to CLAIM "the report cannot name a URL the
        run did not call" while the code echoed a caller-named `endpoint`
        through an injected factory that carries no URL - a 2.2 driver could
        point `--vlm-url` at candidate A while its factory built B, and the
        report would name A. The invariant is enforced now: if the harness
        cannot verify the transport, it refuses the contradiction instead of
        printing the caller's assertion."""
        items = [_item(tmp_path, 1)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:  # pragma: no cover - must never be called
            raise AssertionError("refused build must not construct a client")

        with pytest.raises(ValueError, match="endpoint"):
            await run_replay(store, candidate="F@test", make_client=make, endpoint="http://x:1")

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
            def __init__(self, base_url: str, settings: object = None) -> None:
                seen.append(base_url)

            async def assess(self, request):  # pragma: no cover - trivial
                return _verdict()

            async def close(self) -> None:
                pass

        monkeypatch.setattr(vr, "VlmClient", SpyClient)
        # a real Settings (the factory copies it to pin camera_timezone)
        settings = vr.get_settings().model_copy(update={"ai_vlm_url": "http://settings-wins:8098"})
        monkeypatch.setattr(vr, "get_settings", lambda: settings)
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

    async def test_zero_and_negative_limits_are_refused_not_sliced(self, tmp_path) -> None:
        """`items[:limit]` with limit=0 yields [] and the run completes a
        full report over zero items (exit 0, a run row, a written JSON), and
        limit=-1 silently drops the last item. The same function refuses a
        media-less generation loudly, so the vacuous-green run was the one
        hole left in this module's own posture."""
        items = [_item(tmp_path, n) for n in (1, 2, 3)]
        store = _store(tmp_path, items)

        def make() -> FakeClient:  # pragma: no cover - must never be called
            raise AssertionError("refused limit must not build a client")

        with pytest.raises(ValueError, match="limit"):
            await run_replay(store, candidate="F@test", make_client=make, limit=0)
        with pytest.raises(ValueError, match="limit"):
            await run_replay(store, candidate="F@test", make_client=make, limit=-1)

    async def test_p95_is_the_nearest_rank_not_the_maximum(self, tmp_path) -> None:
        """`latencies[int(n*0.95)]` sat one rank high at every n where 0.95n
        is whole (n=20 -> index 19 -> rank 20 = the max; the min() clamp
        kept it in range, so it failed silently). Nearest-rank p95 is the
        value at rank ceil(0.95n): at n=20 that's the 19th, not the 20th.
        At n=13 the two formulas agree (ceil(12.35) = 13 = int(12.35)+1),
        which is why the bake-off's three n=13 figures were always the right
        number. Pinned through compute_report directly with known latencies:
        real durations can't be faked through time.monotonic, and the report
        is a pure function of its rows."""
        from backend.evaluation.vlm_replay import compute_report

        items = [_item(tmp_path, n) for n in range(1, 21)]
        store = _store(tmp_path, items)
        rows = [
            {
                "item_id": it.item_id,
                "verdict": "confirmed",
                "risk_score": 60,
                "raw_response": {},
                "latency_ms": i * 100,  # 100..2000 ms
            }
            for i, it in enumerate(items, start=1)
        ]
        lat = compute_report(rows, store)["latency_ms_indicative_only"]
        assert lat["n"] == 20
        assert lat["p95"] == 1900  # rank ceil(0.95*20) = 19, NOT the 2000 max
        assert lat["max"] == 2000

    async def test_the_report_says_which_corpus_it_measured(self, tmp_path) -> None:
        """Plan 2.1.5 requires 'corpus generation + counts' in the report.
        Two generations sharing the 13 stock media items produce
        byte-comparable S2/S3 rows and indistinguishable headers - the exact
        ambiguity gen-2 exists to remove. Aggregate counts + the store
        DIRECTORY NAME only: no absolute path, no item ids (D10)."""
        items = [
            _item(tmp_path, 1, label="incident"),
            _item(tmp_path, 2, label="benign", expected=10),
            _item(tmp_path, 3, label="", expected=40),  # the freeze's shape
        ]
        store = _store(tmp_path, items)
        results = {it.media_paths[0]: _verdict("confirmed", 40) for it in items}

        def make() -> FakeClient:
            return FakeClient(results)

        report = await run_replay(store, candidate="F@test", make_client=make)
        corpus = report["corpus"]
        assert corpus["items"] == 3
        assert corpus["with_media"] == 3
        assert corpus["labels"] == {"benign": 1, "incident": 1, "unlabeled": 1}
        # A name the report can be compared by, never a path (D10 kept the
        # absolute store location out of everything that rides to git).
        assert corpus["store_dir"]
        assert "/" not in corpus["store_dir"]

    def test_main_closes_the_store(self, tmp_path, monkeypatch) -> None:
        """`main()` opens the EvalStore and never closes it - sqlite3 would
        eventually GC, but the rule this repo holds everywhere else is close
        in `finally`. Spied, not assumed."""
        import backend.evaluation.vlm_replay as vr

        closed: list[bool] = []

        class SpyStore(EvalStore):
            def close(self) -> None:
                closed.append(True)
                super().close()

        async def fake_run(store, **kwargs):
            return {
                "s2": {},
                "s3": {},
                "verdict_mix": {},
                "s5": {},
                "run_id": "r1",
                "candidate": "F@test",
                "frames_mode": "stored",
                "engine": "llama.cpp",
                "commit": "unknown",
                "n_items": 0,
                "vlm_url": None,
                "vlm_url_source": "injected",
                "started_at_utc": "x",
                "latency_ms_indicative_only": {},
                "corpus": {},
            }

        monkeypatch.setattr(vr, "EvalStore", SpyStore)
        monkeypatch.setattr(vr, "run_replay", fake_run)
        rc = vr.main(
            ["--store", str(tmp_path), "--candidate", "F@test", "--out", str(tmp_path / "r.json")]
        )
        assert rc == 0
        assert closed == [True]

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


class TestReplayIgnoresTheHostCameraTimezone:
    """Stored snapshot timestamps are not capture moments (the epoch sentinel,
    metadata generated_at, or event.started_at), and a run records only
    candidate@commit - so a replay prompt must not change with the replay
    host's CAMERA_TIMEZONE."""

    @pytest.mark.parametrize("base_url", [None, "http://x:1"])
    def test_the_replay_client_pins_camera_timezone_to_none(
        self, monkeypatch, base_url: str | None
    ) -> None:
        from backend.core.config import get_settings

        monkeypatch.setenv("CAMERA_TIMEZONE", "America/New_York")
        get_settings.cache_clear()
        assert get_settings().camera_timezone == "America/New_York", "the host sets it"

        client = client_factory(base_url)()
        assert client._settings.camera_timezone is None
        sentinel = "1970-01-01T00:00:00+00:00"
        request = VlmAssessRequest(
            image_paths=["/x/a.jpg"], context={"camera_id": "c", "timestamp": sentinel}
        )
        assert f"Time: {sentinel}\n" in client.prompt_text(request), (
            "the epoch sentinel stays an obvious sentinel, not a local evening"
        )


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


def _sequence_item(tmp_path: Path, n: int, *, classes: tuple[str, ...] = ("knife",)) -> EvalItem:
    """An ISS-037 sequence set as the store holds it: N frames, and detection rows that
    NAME the frame each object was seen on (a still's declared rows name none). Rows are
    one class per frame, times a second apart — the exported shape."""
    frames = []
    for i in range(1, 4):
        f = tmp_path / f"seq{n}-frame{i}.jpg"
        f.write_bytes(b"\xff\xd8z" * 100)
        frames.append(str(f))
    detections = [
        {
            "id": idx,
            "object_type": classes[(idx - 1) % len(classes)],
            "confidence": 1.0,
            # the exported shape: the frame's NAME inside the set, not a path —
            # `_sequence_rows` is what resolves it to the store's media path
            "file_path": Path(frames[idx - 1]).name,
            "detected_at": f"2026-04-15T14:32:0{idx}.000000-04:00",
        }
        for idx in range(1, 4)
    ]
    return EvalItem(
        item_id=f"seq-{n}",
        media_paths=frames,
        expected_label="incident",
        expected_risk_score=80,
        snapshot=AssessInput(
            camera_id="cam-front",
            detections=detections,
            zones=["front_yard"],
            timestamp="2026-04-15T18:32:01+00:00",
        ),
        source="synthetic",
    )


class TestFramesModes:
    """ISS-037: how frames reach the wire is a MODE, and the harness audited it.

    The mode a row was fed under is the measurement's independent variable — a report
    that cannot recover `frames_fed` per item cannot answer the question the funded
    head-to-head was run for. The collapse here is ISS-005's claim, measured."""

    async def test_stored_mode_builds_the_historical_request_byte_identically(
        self, tmp_path
    ) -> None:
        """The comparability premise: the mode flag must not touch the stored-mode
        request at all — a re-run of a committed corpus sends the committed bytes."""
        import inspect

        from backend.evaluation import vlm_replay

        item = _item(tmp_path, 1)
        fake = FakeClient({item.media_paths[0]: _verdict()})
        await replay_item(fake, item, frames_mode="stored")
        sent = fake.requests[item.media_paths[0]]
        assert sent.image_paths == item.media_paths
        assert sent.frame_detection_ids is None  # the historical shape: no link at all
        # The default is production's selector (B1.2). A still names no frame per
        # detection row, so the selector has nothing to select from and falls back
        # to this same stored request - recorded in the audit, never silently.
        fake2 = FakeClient({item.media_paths[0]: _verdict()})
        row = await replay_item(fake2, item)
        assert fake2.requests[item.media_paths[0]] == sent
        assert row["raw_response"]["harness"]["frames_mode"] == "selector"
        assert row["raw_response"]["harness"]["mode_fell_back"] == "no per-frame detection rows"
        # the lazy-import doctrine in source form: the analyzer's builders are imported
        # inside the functions that use them, never at this module's top level (the AST
        # doctrine pins this module's own imports; every replay now runs the analyzer's
        # invariant table, so vlm_analyzer is loaded at run time in every mode)
        src = inspect.getsource(vlm_replay._build_request)
        assert "from backend.services.vlm_analyzer import build_assess_request" in src

    async def test_selector_mode_collapses_a_same_class_triplet_to_one_frame(
        self, tmp_path
    ) -> None:
        """ISS-005, measured: production's own selector over one class across three
        frames attaches ONE still — which is why the funded arm runs the burst mode."""
        item = _sequence_item(tmp_path, 1)
        fake = FakeClient({p: _verdict() for p in item.media_paths})
        row = await replay_item(fake, item, frames_mode="selector")
        sent = fake.requests[item.media_paths[2]]  # the recency tiebreak picks the newest
        assert len(sent.image_paths) == 1
        harness = row["raw_response"]["harness"]
        assert harness["frames_fed"] == 1
        assert harness["selector_collapsed"] is True
        assert harness["frames_mode"] == "selector"
        # a row naming a frame the item lacks is dropped, not pointed at the wire
        broken = item.model_copy(
            update={
                "snapshot": item.snapshot.model_copy(
                    update={
                        "detections": [
                            {**item.snapshot.detections[0], "file_path": "/elsewhere/x.jpg"},
                            *item.snapshot.detections[1:],
                        ]
                    }
                )
            }
        )
        fake2 = FakeClient({p: _verdict() for p in broken.media_paths})
        row2 = await replay_item(fake2, broken, frames_mode="selector")
        assert len(fake2.requests[item.media_paths[2]].image_paths) == 1

    async def test_selector_mode_falls_back_to_stored_and_says_so(self, tmp_path) -> None:
        """A still has no per-frame rows; an unknown-but-plausible item must not send an
        empty request — it sends the stored one, with the fallback counted."""
        item = _item(tmp_path, 2)
        fake = FakeClient({item.media_paths[0]: _verdict()})
        row = await replay_item(fake, item, frames_mode="selector")
        assert fake.requests[item.media_paths[0]].image_paths == item.media_paths
        harness = row["raw_response"]["harness"]
        assert harness["mode_fell_back"] == "no per-frame detection rows"
        assert harness["frames_fed"] == 1

    async def test_burst_mode_feeds_every_frame_with_index_aligned_detection_links(
        self, tmp_path
    ) -> None:
        """Funded arm (a)'s shape: all frames, and each frame names the rows on it —
        misalignment here would attribute a knife to the wrong frame on the wire."""
        item = _sequence_item(tmp_path, 3, classes=("knife", "knife", "person"))
        fake = FakeClient({p: _verdict() for p in item.media_paths})
        row = await replay_item(fake, item, frames_mode="burst")
        sent = fake.requests[item.media_paths[0]]
        assert sent.image_paths == item.media_paths
        assert sent.frame_detection_ids == [[1], [2], [3]]
        harness = row["raw_response"]["harness"]
        assert harness == {
            "frames_mode": "burst",
            "frames_fed": 3,
            "selector_collapsed": False,
        }

    async def test_the_harness_audit_rides_the_refusal_row_too(self, tmp_path) -> None:
        """A refusal fed 3 frames is a data point about 3-frame input; dropping the
        audit from refusals would bias every per-mode bucket toward items that answered."""
        item = _sequence_item(tmp_path, 4)
        fake = FakeClient({p: VlmTransportError("no gpu") for p in item.media_paths})
        row = await replay_item(fake, item, frames_mode="burst")
        assert row["verdict"] == "verification_failed"
        assert row["raw_response"]["harness"] == {
            "frames_mode": "burst",
            "frames_fed": 3,
            "selector_collapsed": False,
        }

    async def test_an_unknown_mode_is_refused_before_the_wire(self, tmp_path) -> None:
        item = _item(tmp_path, 5)
        fake = FakeClient({item.media_paths[0]: _verdict()})
        with pytest.raises(ValueError, match="frames_mode must be one of"):
            await replay_item(fake, item, frames_mode="vidual")

    async def test_run_replay_refuses_an_unknown_mode_before_the_run_row(self, tmp_path) -> None:
        """Like `limit`: a typo that surfaced on the first item would leave a started run
        that never completes sitting in the store's runs table."""
        store = _store(tmp_path, [_item(tmp_path, 1)])
        with pytest.raises(ValueError, match="frames_mode"):
            await run_replay(
                store,
                candidate="F@test",
                make_client=lambda: FakeClient({}),
                frames_mode="frames",
            )
        assert store._db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0

    async def test_run_replay_records_the_mode_it_ran(self, tmp_path) -> None:
        items = [_sequence_item(tmp_path, 6)]
        store = _store(tmp_path, items)
        report = await run_replay(
            store,
            candidate="F@test",
            make_client=lambda: FakeClient({p: _verdict() for p in items[0].media_paths}),
            frames_mode="burst",
        )
        assert report["frames_mode"] == "burst"
        row = store.replay(report["run_id"])[0]
        assert row["raw_response"]["harness"]["frames_fed"] == 3


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

    def test_constrained_decoding_error_is_in_the_ladder(self) -> None:
        """The analyzer's ConstrainedDecodingNotEnforced must be a member of
        the replay's `_DEGRADABLE_ERRORS`, not merely mentioned: "any import
        path ending in nemotron_analyzer" is satisfied by importing anything
        else from that module. The set pin above already compares the SET of
        names to the analyzer's; this names the one class whose absence would
        crash a bake-off run where production degrades."""
        from backend.evaluation.vlm_replay import _DEGRADABLE_ERRORS
        from backend.services.constrained_decoding import ConstrainedDecodingNotEnforced

        assert ConstrainedDecodingNotEnforced in _DEGRADABLE_ERRORS

"""P1 report aggregation and pick proposal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.spikes.p1_bakeoff import report as r
from synthbench.spikes.p1_bakeoff import sheet


def _records() -> list[dict[str, Any]]:
    rows = []
    for model, secs in (("a", 5.0), ("b", 20.0)):
        for case in ("knife", "handgun_in_hand", "legible_plate"):
            rows.append(
                {
                    "model": model,
                    "kind": "t2i",
                    "case": case,
                    "seed": 11,
                    "output": f"images/{model}/{case}/11.png",
                    "ok": True,
                    "seconds": secs,
                }
            )
    rows.append(
        {
            "model": "b",
            "kind": "t2i",
            "case": "knife",
            "seed": 22,
            "output": "images/b/knife/22.png",
            "ok": False,
            "seconds": 1.0,
            "error": "OOM",
        }
    )
    return rows


def _ratings() -> dict[str, dict[str, str]]:
    ratings = {f"images/a/{c}/11.png": {"rating": "good"} for c in ("knife", "handgun_in_hand")}
    ratings |= {f"images/b/{c}/11.png": {"rating": "fail"} for c in ("knife", "handgun_in_hand")}
    return ratings


def _measures() -> list[dict[str, Any]]:
    return [
        {"output": "images/a/legible_plate/11.png", "plate_exact": True, "plate_cer": 0.0},
        {"output": "images/b/legible_plate/11.png", "plate_exact": False, "plate_cer": 0.5},
    ]


def test_summarize_per_model() -> None:
    groups = [
        {"model": "a", "peak_vram_mib": 20480},
        {"model": "a", "peak_vram_mib": 30720},  # a resumed run appends a row
        {"model": "b", "peak_vram_mib": None},  # no VRAM sample succeeded
    ]
    s = r.summarize(_records(), groups, _measures(), _ratings())
    a, b = s["models"]["a"], s["models"]["b"]
    assert (a["ok"], a["failed"], b["failed"]) == (3, 0, 1)
    assert a["median_seconds"] == 5.0
    assert a["peak_vram_gib"] == 30.0 and b["peak_vram_gib"] is None
    assert a["threat_good_rate"] == 1.0 and b["threat_good_rate"] == 0.0
    assert a["plate_exact_rate"] == 1.0 and b["plate_mean_cer"] == 0.5


def test_propose_picks_prefers_rated_quality_then_speed() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    picks = r.propose_picks(s)
    assert picks["t2i_quality"] == "a"
    assert picks["text"] == "a"


def test_markdown_has_a_row_per_model_and_the_picks() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    text = r.to_markdown(s, r.propose_picks(s))
    assert "| a |" in text and "| b |" in text and "Proposed picks" in text


def test_sheet_has_one_rating_group_per_ok_record() -> None:
    html = sheet.render(_records(), _measures(), root=None)
    for rec in _records():
        if rec["ok"]:
            assert f'name="{rec["output"]}"' in html
    assert "OOM" in html and "ratings.json" in html


# --- beyond the brief: controller rulings (cold jobs, net VRAM, settle flags) and pick rules ---


def _row(model: str, case: str, output: str, **kw: Any) -> dict[str, Any]:
    return {
        "model": model,
        "kind": "t2i",
        "case": case,
        "seed": 11,
        "output": output,
        "ok": True,
        "seconds": 1.0,
    } | kw


def test_median_seconds_leaves_out_the_cold_job_that_loaded_the_model() -> None:
    records = [
        _row("c", "knife", "images/c/knife/11.png", seconds=60.0, cold=True),
        _row("c", "knife", "images/c/knife/22.png", seconds=4.0, cold=False),
        _row("c", "knife", "images/c/knife/33.png", seconds=6.0),  # no `cold`: an older row
        _row("d", "knife", "images/d/knife/11.png", seconds=30.0, cold=True),
    ]
    clips = [
        _row(
            "v",
            "armed_approach",
            f"clips/v/armed_approach/{seed}.mp4",
            kind="i2v",
            seed=seed,
            seconds=secs,
            cold=seed == 11,
        )
        for seed, secs in ((11, 300.0), (22, 100.0), (33, 120.0))
    ]
    s = r.summarize(records + clips, [], [], {})
    assert s["models"]["c"]["median_seconds"] == 5.0
    assert s["models"]["d"]["median_seconds"] == 30.0  # only a cold job: fall back to it
    assert s["clip_models"]["v"]["median_seconds_per_clip"] == 110.0


def test_net_peak_vram_and_settle_flags() -> None:
    groups = [
        # net 10 GiB on the highest peak, 23 GiB on the other row: net is the max over rows
        {"model": "a", "peak_vram_mib": 30720, "baseline_vram_mib": 20480, "settle": "dropped"},
        {"model": "a", "peak_vram_mib": 25600, "baseline_vram_mib": 2048, "settle": "timeout"},
        {"model": "b", "peak_vram_mib": None, "baseline_vram_mib": 1024, "settle": "unreadable"},
        {"model": "b", "peak_vram_mib": 4096, "baseline_vram_mib": None, "settle": "no_drop"},
        {"model": "b", "peak_vram_mib": 2048, "baseline_vram_mib": None, "settle": "unreadable"},
    ]
    s = r.summarize(_records(), groups, _measures(), _ratings())
    a, b = s["models"]["a"], s["models"]["b"]
    assert a["peak_vram_gib"] == 30.0 and a["net_peak_vram_gib"] == 23.0
    assert a["vram_flags"] == ["timeout"]
    assert b["peak_vram_gib"] == 4.0 and b["net_peak_vram_gib"] is None
    assert b["vram_flags"] == ["unreadable"]
    text = r.to_markdown(s, r.propose_picks(s))
    row_a = next(line for line in text.splitlines() if line.startswith("| a |"))
    assert "30.0" in row_a and "23.0" in row_a and "timeout" in row_a


def test_groups_without_settle_fields_give_no_net_vram_and_no_flags() -> None:
    s = r.summarize(_records(), [{"model": "a", "peak_vram_mib": 1024}], [], {})
    assert s["models"]["a"]["net_peak_vram_gib"] is None
    assert s["models"]["a"]["vram_flags"] == []


def test_a_resumed_jobs_last_row_wins() -> None:
    records = [
        _row("a", "knife", "images/a/knife/11.png", ok=False, error="OOM"),
        _row("a", "knife", "images/a/knife/11.png"),
    ]
    a = r.summarize(records, [], [], {})["models"]["a"]
    assert (a["ok"], a["failed"]) == (1, 0)


def test_owl_hit_rate_uses_the_first_query() -> None:
    records = [_row("a", "knife", f"images/a/knife/{s}.png", seed=s) for s in (11, 22)]
    measures = [
        {"output": "images/a/knife/11.png", "owl": {"a knife": 0.31, "a person": 0.1}},
        {"output": "images/a/knife/22.png", "owl": {"a knife": 0.1, "a person": 0.9}},
    ]
    assert r.summarize(records, [], measures, {})["models"]["a"]["owl_hit_rate"] == 0.5


def _identity(model: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = f"images/{model}/identity"
    records = [_row(model, "identity_reference", f"{base}/reference.png", kind="t2i")]
    records += [_row(model, "identity", f"{base}/{i}_day.png", kind="edit") for i in range(3)]
    measures = [
        {"output": f"{base}/reference.png", "face": [1.0, 0.0]},
        {"output": f"{base}/0_day.png", "face": [1.0, 0.0]},  # distance 0.0
        {"output": f"{base}/1_day.png", "face": [0.6, 0.8]},  # distance 0.4
        {"output": f"{base}/2_day.png", "face": None},  # no face found
    ]
    return records, measures


def test_identity_drift_is_measured_against_the_models_reference() -> None:
    records, measures = _identity("qwen-image-2.1")
    q = r.summarize(records, [], measures, {})["models"]["qwen-image-2.1"]
    assert q["identity_drift_median"] == 0.2
    assert q["identity_no_face"] == 1


def test_compositor_is_the_lowest_drift_edit_model_with_good_threats() -> None:
    records, measures = [], []
    for model, drift_face in (("qwen-image-2.1", [0.8, 0.6]), ("flux2-dev", [1.0, 0.0])):
        base = f"images/{model}/identity"
        records += [
            _row(model, "identity_reference", f"{base}/reference.png"),
            _row(model, "identity", f"{base}/0_day.png", kind="edit"),
            _row(model, "knife", f"images/{model}/knife/11.png"),
        ]
        measures += [
            {"output": f"{base}/reference.png", "face": [1.0, 0.0]},
            {"output": f"{base}/0_day.png", "face": drift_face},
        ]
    # the lowest drift of all, but not an edit model
    records += [
        _row("z-image-turbo", "identity_reference", "images/z/identity/reference.png"),
        _row("z-image-turbo", "identity", "images/z/identity/0_day.png"),
        _row("z-image-turbo", "knife", "images/z/knife/11.png"),
    ]
    measures += [
        {"output": "images/z/identity/reference.png", "face": [1.0, 0.0]},
        {"output": "images/z/identity/0_day.png", "face": [1.0, 0.0]},
    ]
    ratings = {
        "images/qwen-image-2.1/knife/11.png": {"rating": "good"},
        "images/flux2-dev/knife/11.png": {"rating": "fail"},  # lowest edit drift, bad threats
        "images/z/knife/11.png": {"rating": "good"},
    }
    picks = r.propose_picks(r.summarize(records, [], measures, ratings))
    assert picks["compositor"] == "qwen-image-2.1"


def test_models_with_under_half_their_jobs_ok_are_never_picked() -> None:
    records = [
        _row("flaky", "knife", "images/flaky/knife/11.png"),
        _row("flaky", "knife", "images/flaky/knife/22.png", ok=False, error="OOM"),
        _row("flaky", "knife", "images/flaky/knife/33.png", ok=False, error="OOM"),
        _row("slow", "knife", "images/slow/knife/11.png", seconds=30.0),
    ]
    ratings = {
        "images/flaky/knife/11.png": {"rating": "good"},
        "images/slow/knife/11.png": {"rating": "good"},
    }
    picks = r.propose_picks(r.summarize(records, [], [], ratings))
    assert picks["t2i_quality"] == "slow"
    assert picks["t2i_volume"] == "none"  # slow is over 10 s; flaky is ineligible
    assert picks["compositor"] == "none" and picks["text"] == "none"


def test_animator_prefers_rated_clips_then_lower_drift() -> None:
    records, measures = [], []
    for model, drift in (("ltx-2.5", 0.3), ("wan2.2-i2v", 0.1)):
        out = f"clips/{model}/armed_approach/11.mp4"
        records.append(_row(model, "armed_approach", out, kind="i2v"))
        measures.append({"output": out, "frames_with_face": 8, "frame_drift_max": drift})
    ratings = {
        f"clips/{m}/armed_approach/11.mp4": {"rating": "good"} for m in ("ltx-2.5", "wan2.2-i2v")
    }
    s = r.summarize(records, [], measures, ratings)
    assert s["clip_models"]["ltx-2.5"]["clip_good_rate"] == 1.0
    assert s["clip_models"]["wan2.2-i2v"]["frame_drift_median"] == 0.1
    assert "ltx-2.5" not in s["models"]
    assert r.propose_picks(s)["animator"] == "wan2.2-i2v"


def test_sheet_escapes_error_text() -> None:
    records = [_row("a", "knife", "images/a/knife/11.png", ok=False, error="<b>OOM</b>")]
    html = sheet.render(records, [], root=None)
    assert "&lt;b&gt;OOM&lt;/b&gt;" in html and "<b>OOM" not in html


def _write_root(root: Path) -> None:
    root.mkdir()
    (root / "records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in _records()))
    (root / "measures.jsonl").write_text("".join(json.dumps(m) + "\n" for m in _measures()))


def test_report_main_reads_the_root_and_writes_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "p1"
    _write_root(root)  # no groups.jsonl yet
    (root / "ratings.json").write_text(json.dumps(_ratings()))
    monkeypatch.setattr(r, "_commit", lambda: "abc1234")
    out = tmp_path / "docs" / "p1-bakeoff.md"
    assert r.main(["--root", str(root), "--out", str(out)]) == 0
    text = out.read_text()
    assert "abc1234" in text and str(root) in text
    assert "| t2i_quality | a |" in text


def test_report_main_without_ratings_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "p1"
    _write_root(root)
    monkeypatch.setattr(r, "_commit", lambda: None)
    out = tmp_path / "p1-bakeoff.md"
    assert r.main(["--root", str(root), "--out", str(out)]) == 0
    assert "ratings.json" in capsys.readouterr().err
    assert "| t2i_quality | none |" in out.read_text()


def test_sheet_main_writes_sheet_html_under_the_root(tmp_path: Path) -> None:
    root = tmp_path / "p1"
    _write_root(root)
    assert sheet.main(["--root", str(root)]) == 0
    assert 'name="images/a/knife/11.png"' in (root / "sheet.html").read_text()


def test_sheet_orders_sections_and_columns_and_shows_the_measures() -> None:
    records, measures = _identity("flux2-dev")
    clip = "clips/ltx-2.5/armed_approach/11.mp4"
    records += [
        _row("ltx-2.5", "armed_approach", clip, kind="i2v", cold=True, seconds=300.0),
        _row("a", "knife", "images/a/knife/11.png"),
        _row("a", "knife", "images/a/knife/22.png", seed=22),
        _row("b", "legible_plate", "images/b/legible_plate/11.png"),
    ]
    measures += [
        *_measures(),
        {"output": clip, "frames_with_face": 8, "frame_drift_max": 0.25},
        {"output": "images/a/knife/11.png", "owl": {"a knife": 0.52, "a person": 0.9}},
        {"output": "images/a/knife/22.png", "error": "OSError: truncated"},
    ]
    html = sheet.render(list(reversed(records)), measures, root=Path("/x/p1"))
    assert html.index('id="knife"') < html.index('id="legible_plate"')
    assert html.index('id="legible_plate"') < html.index('id="identity"')
    assert html.index('id="identity"') < html.index('id="armed_approach"')
    assert html.index("<th>reference</th>") < html.index("<th>0_day</th>")
    assert f'<video controls preload="metadata" src="{clip}">' in html
    assert "300.0 s (cold)" in html and "a knife 0.52 · a person 0.90" in html
    assert "plate: (none read) (CER 0.50)" in html
    assert "face: found" in html and "face: none" in html and "max drift 0.250" in html
    assert "measure error: OSError: truncated" in html
    assert 'data-root="/x/p1"' in html


def test_a_zero_score_winner_is_below_the_floor() -> None:
    records, measures = [], []
    for model in ("flux2-dev", "z-image-turbo"):
        records += [
            _row(model, "knife", f"images/{model}/knife/11.png"),
            _row(model, "legible_plate", f"images/{model}/legible_plate/11.png"),
        ]
        measures.append(
            {
                "output": f"images/{model}/legible_plate/11.png",
                "plate_exact": False,
                "plate_cer": 0.5,
            }
        )
    for model in ("ltx-2.5", "wan2.2-i2v"):
        records.append(_row(model, "child_pool", f"clips/{model}/child_pool/11.mp4", kind="i2v"))
    ratings = {row["output"]: {"rating": "fail"} for row in records}
    s = r.summarize(records, [], measures, ratings)
    picks = r.propose_picks(s)
    for slot in ("t2i_quality", "t2i_volume", "text", "animator"):
        assert picks[slot] == r.BELOW_FLOOR, slot
    assert picks["compositor"] == "none"  # its own floor: no edit model at >= 50% good
    text = r.to_markdown(s, picks)
    assert f"| t2i_quality | {r.BELOW_FLOOR} |" in text and "fallback" in text

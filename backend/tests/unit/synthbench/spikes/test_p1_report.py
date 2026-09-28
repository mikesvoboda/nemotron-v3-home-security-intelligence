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
    """A record; at 1920x1080 its 1080p-equivalent seconds are its seconds."""
    return {
        "model": model,
        "kind": "t2i",
        "case": case,
        "seed": 11,
        "output": output,
        "ok": True,
        "seconds": 1.0,
        "width": 1920,
        "height": 1080,
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
    assert (q["identity_faces"], q["identity_no_face"]) == (2, 1)


Rows = tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, str]]]


def _compositor_candidate(
    model: str,
    *,
    face: list[float],
    faces: int = 15,
    identity_good: int = 15,
    threat: str = "good",
) -> Rows:
    """An edit model's 15 identity shots: the first `faces` have `face` (drift from the
    reference [1, 0]), the rest none; the first `identity_good` are rated good, the rest
    fail. The reference is rated fail, to show it never counts. One rated threat image."""
    base = f"images/{model}/identity"
    records = [
        _row(model, "identity_reference", f"{base}/reference.png"),
        _row(model, "knife", f"images/{model}/knife/11.png"),
    ]
    measures: list[dict[str, Any]] = [{"output": f"{base}/reference.png", "face": [1.0, 0.0]}]
    ratings = {
        f"{base}/reference.png": {"rating": "fail"},
        f"images/{model}/knife/11.png": {"rating": threat},
    }
    for shot in range(15):
        out = f"{base}/{shot}_day.png"
        records.append(_row(model, "identity", out, kind="edit"))
        measures.append({"output": out, "face": face if shot < faces else None})
        ratings[out] = {"rating": "good" if shot < identity_good else "fail"}
    return records, measures, ratings


def _merge(*parts: Rows) -> Rows:
    records, measures, ratings = [], [], {}
    for part_records, part_measures, part_ratings in parts:
        records += part_records
        measures += part_measures
        ratings |= part_ratings
    return records, measures, ratings


def test_identity_good_rate_counts_the_owners_identity_ratings_only() -> None:
    records, measures, ratings = _compositor_candidate("qwen-image-2.1", face=[1.0, 0.0])
    ratings |= {f"images/qwen-image-2.1/identity/{i}_day.png": {"rating": "fail"} for i in range(6)}
    q = r.summarize(records, [], measures, ratings)["models"]["qwen-image-2.1"]
    assert (q["identity_good_rate"], q["identity_good_n"]) == (0.6, 15)  # the reference is out


def test_compositor_is_the_lowest_drift_edit_model_with_good_threats() -> None:
    records, measures, ratings = _merge(
        _compositor_candidate("qwen-image-2.1", face=[0.8, 0.6]),
        _compositor_candidate("flux2-dev", face=[1.0, 0.0], threat="fail"),  # bad threats
        _compositor_candidate("z-image-turbo", face=[1.0, 0.0]),  # not an edit model
    )
    picks = r.propose_picks(r.summarize(records, [], measures, ratings))
    assert picks["compositor"] == "qwen-image-2.1"


def test_compositor_needs_good_identity_ratings_and_enough_faces() -> None:
    # A near-copy of the reference drifts least; the owner's ratings and the face floor
    # keep it from winning, as they keep out a model whose faces are mostly not found.
    records, measures, ratings = _merge(
        _compositor_candidate("qwen-image-2.1", face=[0.8, 0.6], faces=8, identity_good=8),
        _compositor_candidate("flux2-dev", face=[1.0, 0.0], identity_good=7),
        _compositor_candidate("flux2-klein-4b", face=[1.0, 0.0], faces=7),
    )
    s = r.summarize(records, [], measures, ratings)
    assert r.propose_picks(s)["compositor"] == "qwen-image-2.1"
    row = next(line for line in r.to_markdown(s, {}).splitlines() if "| flux2-klein-4b |" in line)
    assert "100% (n=15)" in row  # identity good, over the rated shots
    assert "0.000 (n=7)" in row  # identity drift, over the shots with a face


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


def test_report_and_sheet_cover_every_clip_model() -> None:
    # Task 9 made the Animator slot a three-way comparison: nothing may assume a pair.
    models = ("ltx-2.5", "wan2.2-i2v", "minimax-h3")
    records, measures, ratings = [], [], {}
    for model, drift in zip(models, (0.3, 0.2, 0.1), strict=True):
        out = f"clips/{model}/armed_approach/11.mp4"
        records.append(_row(model, "armed_approach", out, kind="i2v", frames=97))
        measures.append({"output": out, "frames_with_face": 8, "frame_drift_max": drift})
        ratings[out] = {"rating": "good"}
    s = r.summarize(list(reversed(records)), [], measures, ratings)
    assert list(s["clip_models"]) == list(models)  # the I2V_MODELS order, not input order
    assert r.propose_picks(s)["animator"] == "minimax-h3"
    text = r.to_markdown(s, r.propose_picks(s))
    clip_table = text.split("## Clip models", 1)[1].split("How to read", 1)[0]
    assert [line.split(" | ", 1)[0] for line in clip_table.splitlines()[4:7]] == [
        f"| {model}" for model in models
    ]
    html = sheet.render(records, measures, root=None)
    section = html.split('id="armed_approach"', 1)[1]
    assert all(f"<th>{model}</th>" in section for model in models)
    assert all(f'name="{rec["output"]}"' in section for rec in records)


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


def test_a_failed_threat_job_counts_as_not_good() -> None:
    records = [
        _row("a", "knife", "images/a/knife/11.png"),
        _row("a", "knife", "images/a/knife/22.png", seed=22, ok=False, error="OOM"),
        _row("a", "knife", "images/a/knife/33.png", seed=33),  # ok, not rated yet
    ]
    ratings = {"images/a/knife/11.png": {"rating": "good"}}
    a = r.summarize(records, [], [], ratings)["models"]["a"]
    assert (a["threat_good_rate"], a["threat_good_n"]) == (0.5, 2)


def test_threat_good_is_unknown_until_an_ok_threat_output_is_rated() -> None:
    records = [
        _row("a", "knife", "images/a/knife/11.png"),
        _row("a", "knife", "images/a/knife/22.png", seed=22, ok=False, error="OOM"),
        _row("b", "knife", "images/b/knife/11.png", ok=False, error="OOM"),
    ]
    s = r.summarize(records, [], [], {})["models"]
    assert (s["a"]["threat_good_rate"], s["a"]["threat_good_n"]) == (None, 0)
    assert (s["b"]["threat_good_rate"], s["b"]["threat_good_n"]) == (0.0, 1)  # all failed


def test_every_rate_in_the_report_shows_its_n() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    text = r.to_markdown(s, r.propose_picks(s))
    row_b = next(line for line in text.splitlines() if line.startswith("| b |"))
    assert "0% (n=3)" in row_b  # threat good: 2 rated fails and 1 failed job
    assert "0% (n=1)" in row_b  # plate exact


def test_image_megapixels_and_the_volume_bar_at_1080p_equivalent() -> None:
    records = [
        _row(
            model,
            "knife",
            f"images/{model}/knife/{seed}.png",
            seed=seed,
            seconds=secs,
            width=w,
            height=h,
        )
        for model, (w, h), secs in (
            ("flux2-klein-4b", (1344, 768), 6.0),
            ("z-image-turbo", (1920, 1088), 9.0),
        )
        for seed in (11, 22)
    ]
    ratings = {row["output"]: {"rating": "good"} for row in records}
    ratings["images/z-image-turbo/knife/22.png"] = {"rating": "fail"}  # klein rates higher
    s = r.summarize(records, [], [], ratings)
    klein, z = s["models"]["flux2-klein-4b"], s["models"]["z-image-turbo"]
    assert klein["megapixels"] == pytest.approx(1.032192)
    assert klein["seconds_per_mp"] == pytest.approx(6.0 / 1.032192)
    assert klein["median_seconds_1080p"] == pytest.approx(6.0 * 2.0736 / 1.032192)  # 12.05
    assert z["median_seconds_1080p"] == pytest.approx(9.0 * 2.0736 / 2.08896)  # 8.93
    # klein's 6 s at 1.03 MP is 12 s at 1080p: over the 10 s bar, though its raw time is not
    assert r.propose_picks(s)["t2i_volume"] == "z-image-turbo"
    text = r.to_markdown(s, r.propose_picks(s))
    row = next(line for line in text.splitlines() if line.startswith("| flux2-klein-4b |"))
    assert "| 1.03 | 5.8 |" in row  # MP, s/MP


def test_clip_throughput_is_per_frame_megapixel() -> None:
    out = "clips/ltx-2.5/armed_approach/11.mp4"
    records = [
        _row("ltx-2.5", "armed_approach", out, kind="i2v", seconds=97.0, width=1280, height=704)
        | {"frames": 97}
    ]
    v = r.summarize(records, [], [], {})["clip_models"]["ltx-2.5"]
    assert (v["megapixels"], v["frames"]) == (pytest.approx(0.90112), 97)
    assert v["seconds_per_mp"] == pytest.approx(97.0 / (0.90112 * 97))


def test_threat_props_per_case_and_the_fallback_candidates() -> None:
    records = [
        _row(model, case, f"images/{model}/{case}/{seed}.png", seed=seed)
        for model in ("flux2-dev", "z-image-turbo")
        for case in ("knife", "handgun_in_hand", "smoke_from_eave")
        for seed in (11, 22)
    ]
    ratings = {
        row["output"]: {"rating": "fail"} for row in records if row["case"] != "smoke_from_eave"
    }
    ratings["images/flux2-dev/knife/11.png"] = {"rating": "good"}  # smoke is not rated yet
    measures = [
        {"output": "images/flux2-dev/knife/11.png", "owl": {"a knife": 0.5, "a person": 0.9}},
        {"output": "images/flux2-dev/knife/22.png", "owl": {"a knife": 0.1, "a person": 0.9}},
    ]
    s = r.summarize(records, [], measures, ratings)
    assert s["models"]["flux2-dev"]["threat_cases"]["knife"] == {
        "good_rate": 0.5,
        "good_n": 2,
        "owl_hit_rate": 0.5,
        "owl_n": 2,
    }
    # knife reached the floor with one model; smoke is unrated, so it is no candidate yet
    assert r.fallback_cases(s) == ["handgun_in_hand"]
    text = r.to_markdown(s, r.propose_picks(s))
    assert "§3.7 fallback candidates (prop reference sheet): handgun_in_hand" in text
    knife = next(line for line in text.splitlines() if line.startswith("| knife |"))
    assert "good 50% (n=2) · OWL 50% (n=2)" in knife


def test_the_sheet_revokes_the_download_url_after_the_click() -> None:
    html = sheet.render(_records(), [], root=None)
    assert "setTimeout(() => URL.revokeObjectURL(url)" in html
    assert "URL.revokeObjectURL(link.href);" not in html


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


# --- Task 10: the VLM judge adds evidence columns and a calibration; it never picks ---


def _judge_row(
    output: str,
    good: bool | None,
    *,
    case_type: str = "threat",
    error: str | None = None,
    **derived: Any,
) -> dict[str, Any]:
    """A judge.jsonl row as judge.py writes it."""
    model = output.split("/")[1]
    return {
        "output": output,
        "model": model,
        "kind": "i2v" if case_type == "clip" else "t2i",
        "case": output.split("/")[2],
        "seconds": 2.0,
        "judge_model": "claude-flagship",
        "answer": None if error else {"threat_assessment": "threatening"},
        "derived": None
        if error
        else {
            "case_type": case_type,
            "judge_good": good,
            "prop_match": good if case_type == "threat" else None,
            "realistic": True,
            "artifact_count": 0,
            "judge_threat": "threatening",
        }
        | derived,
        "error": error,
        "fallbacks": [],
    }


def _judge_rows() -> list[dict[str, Any]]:
    return [
        _judge_row("images/a/knife/11.png", True, artifact_count=1),
        _judge_row("images/a/handgun_in_hand/11.png", False, realistic=False, artifact_count=2),
        _judge_row("images/a/legible_plate/11.png", None, case_type="plate"),
        _judge_row("images/b/knife/11.png", None, error="JudgeError: bad JSON"),
        _judge_row("images/b/handgun_in_hand/11.png", None, error="ReadTimeout: timed out"),
        _judge_row("images/b/handgun_in_hand/11.png", True),  # resumed: the last row wins
    ]


def test_summarize_without_judge_rows_keeps_every_existing_number() -> None:
    before = r.summarize(_records(), [], _measures(), _ratings())
    after = r.summarize(_records(), [], _measures(), _ratings(), judge=_judge_rows())
    assert before["models"] == after["models"]
    assert before["clip_models"] == after["clip_models"]
    assert before["judge"]["rows"] == 0 and after["judge"]["rows"] == 5


def test_judge_stats_per_model_each_with_its_n() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings(), judge=_judge_rows())
    a, b = s["judge"]["models"]["a"], s["judge"]["models"]["b"]
    assert (a["judge_n"], a["judge_errors"]) == (3, 0)
    assert (a["judge_good_rate"], a["judge_good_n"]) == (0.5, 2)  # the plate has no verdict
    assert (a["judge_prop_match_rate"], a["judge_prop_match_n"]) == (0.5, 2)
    assert a["judge_realistic_rate"] == pytest.approx(2 / 3) and a["judge_realistic_n"] == 3
    assert (a["judge_artifact_mean"], a["judge_artifact_n"]) == (1.0, 3)
    assert (b["judge_n"], b["judge_errors"]) == (1, 1)  # knife/11 errored; handgun resumed ok
    assert (b["judge_good_rate"], b["judge_good_n"]) == (1.0, 1)


def test_cohen_kappa_against_hand_computed_values() -> None:
    # tp=4 fn=1 fp=2 tn=3: po = 7/10; pe = (5*6 + 5*4)/100 = 0.5; kappa = 0.2/0.5 = 0.4
    assert r.cohen_kappa(tp=4, fp=2, fn=1, tn=3) == pytest.approx(0.4)
    # perfect agreement across both classes: 1; chance-level: 0
    assert r.cohen_kappa(tp=3, fp=0, fn=0, tn=2) == pytest.approx(1.0)
    assert r.cohen_kappa(tp=1, fp=1, fn=1, tn=1) == pytest.approx(0.0)
    # both raters use one class only (pe = 1): undefined, never a division by zero
    assert r.cohen_kappa(tp=3, fp=0, fn=0, tn=0) is None
    assert r.cohen_kappa(tp=0, fp=0, fn=0, tn=0) is None


def _calibration_fixture() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """10 rated threat cells (tp 4, fn 1, fp 2, tn 3) and 2 rated identity shots
    (tp 1, fp 1), plus cells that must not count."""
    ratings: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    threat = [("good", True)] * 4 + [("good", False)] + [("fail", True), ("partial", True)]
    threat += [("fail", False), ("partial", False), ("fail", False)]
    for seed, (rating, good) in enumerate(threat):
        out = f"images/m/knife/{seed}.png"
        ratings[out] = {"rating": rating}
        rows.append(_judge_row(out, good))
    for shot, rating in enumerate(("good", "fail")):
        out = f"images/m/identity/{shot}_day.png"
        ratings[out] = {"rating": rating}
        rows.append(_judge_row(out, True, case_type="identity"))
    rows.append(_judge_row("images/m/knife/unrated.png", True))  # not rated: out
    ratings["images/m/legible_plate/11.png"] = {"rating": "good"}  # no judge_good: out
    rows.append(_judge_row("images/m/legible_plate/11.png", None, case_type="plate"))
    ratings["images/m/smoke_from_eave/11.png"] = {"rating": "good"}  # judge error: out
    rows.append(_judge_row("images/m/smoke_from_eave/11.png", None, error="x"))
    ratings["images/m/knife/note.png"] = {"rating": None, "note": "later"}  # a note only: out
    rows.append(_judge_row("images/m/knife/note.png", True))
    return ratings, rows


def test_calibration_overall_and_per_kind() -> None:
    ratings, rows = _calibration_fixture()
    cal = r.judge_calibration(ratings, rows)
    threat, identity = cal["kinds"]["threat"], cal["kinds"]["identity"]
    assert {k: threat[k] for k in ("n", "tp", "fn", "fp", "tn")} == {
        "n": 10,
        "tp": 4,
        "fn": 1,
        "fp": 2,
        "tn": 3,
    }
    assert threat["agreement"] == pytest.approx(0.7) and threat["kappa"] == pytest.approx(0.4)
    assert (identity["n"], identity["agreement"], identity["kappa"]) == (2, 0.5, 0.0)
    overall = cal["kinds"]["overall"]  # tp 5 fn 1 fp 3 tn 3: pe = (6*8 + 6*4)/144 = 0.5
    assert (overall["n"], overall["tp"], overall["fp"]) == (12, 5, 3)
    assert overall["agreement"] == pytest.approx(8 / 12)
    assert overall["kappa"] == pytest.approx((8 / 12 - 0.5) / 0.5)
    clip = cal["kinds"]["clip"]
    assert (clip["n"], clip["agreement"], clip["kappa"]) == (0, None, None)
    assert cal["rated"] == 14  # every rating with a good/partial/fail, judged or not


def test_picks_are_identical_with_and_without_judge_rows() -> None:
    records, measures, ratings = _merge(
        _compositor_candidate("qwen-image-2.1", face=[0.8, 0.6]),
        _compositor_candidate("flux2-dev", face=[1.0, 0.0], threat="fail"),
    )
    records += _records()
    measures += _measures()
    ratings |= _ratings()
    # a judge that contradicts the owner everywhere: it loves what the owner failed
    judge = [
        _judge_row(row["output"], ratings.get(row["output"], {}).get("rating") != "good")
        for row in records
    ]
    without = r.summarize(records, [], measures, ratings)
    with_judge = r.summarize(records, [], measures, ratings, judge=judge)
    assert with_judge["judge"]["rows"] == len(judge)
    assert r.propose_picks(with_judge) == r.propose_picks(without)
    assert r.propose_picks(without)["compositor"] == "qwen-image-2.1"


def test_markdown_renders_the_judge_columns_calibration_and_caveat() -> None:
    ratings, rows = _calibration_fixture()
    records = [_row("m", "knife", row["output"]) for row in rows]
    s = r.summarize(records, [], [], ratings, judge=rows)
    text = r.to_markdown(s, r.propose_picks(s))
    assert "## VLM judge (evidence, not a gate)" in text
    assert (
        "judge = claude-flagship (Qwen3.8-Flash-Next); the pipeline's VLM stage is Qwen3VL-4B "
        "(same family), so the judge is evidence, not a gate."
    ) in text
    # 16 outputs: 15 judged, 1 error row
    row_m = next(line for line in text.splitlines() if line.startswith("| m | 15 | 1 |"))
    assert "100% (n=15)" in row_m  # realistic, over every judged output
    assert "### Judge vs owner" in text
    assert "- Judge model id in judge.jsonl: `claude-flagship`." in text
    threat = next(line for line in text.splitlines() if line.startswith("| threat |"))
    assert threat == "| threat | 10 | 70% | 0.40 | 4 | 1 | 2 | 3 |"
    clip = next(line for line in text.splitlines() if line.startswith("| clip |"))
    assert clip == "| clip | 0 | n/a | n/a | 0 | 0 | 0 | 0 |"


def test_markdown_says_no_owner_ratings_yet() -> None:
    s = r.summarize(_records(), [], _measures(), {}, judge=_judge_rows())
    text = r.to_markdown(s, r.propose_picks(s))
    assert "no owner ratings yet" in text and "| overall |" not in text


def test_markdown_when_no_rated_cell_has_a_judge_verdict() -> None:
    judge = [_judge_row("images/a/legible_plate/11.png", None, case_type="plate")]
    s = r.summarize(_records(), [], _measures(), _ratings(), judge=judge)
    text = r.to_markdown(s, r.propose_picks(s))
    assert "No rated cell has a judge verdict yet." in text and "| overall |" not in text


def test_markdown_without_judge_rows_says_how_to_run_the_judge() -> None:
    s = r.summarize(_records(), [], _measures(), _ratings())
    text = r.to_markdown(s, r.propose_picks(s))
    assert "## VLM judge (evidence, not a gate)" in text
    assert "No judge rows yet" in text and "synthbench.spikes.p1_bakeoff.judge" in text


def test_report_main_loads_judge_jsonl_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "p1"
    _write_root(root)
    (root / "ratings.json").write_text(json.dumps(_ratings()))
    (root / "judge.jsonl").write_text("".join(json.dumps(j) + "\n" for j in _judge_rows()))
    monkeypatch.setattr(r, "_commit", lambda: None)
    out = tmp_path / "p1-bakeoff.md"
    assert r.main(["--root", str(root), "--out", str(out)]) == 0
    text = out.read_text()
    assert "| a | 3 | 0 | 50% (n=2) |" in text
    assert "| t2i_quality | a |" in text  # the picks as before


def test_sheet_shows_the_judge_verdict_under_each_cell() -> None:
    rows = _judge_rows()
    rows[0]["derived"]["prop_match"] = True
    html = sheet.render(_records(), _measures(), root=None, judge=rows)
    assert "judge: threatening · prop yes" in html  # a/knife
    assert "judge: threatening · prop no" in html  # a/handgun_in_hand
    assert "judge error: JudgeError: bad JSON" in html  # b/knife: its only row errored
    plate = html.index('name="images/a/legible_plate/11.png"')
    assert "judge: threatening</div>" in html[plate - 800 : plate]  # no prop for the plate
    assert 'id="show-judge"' in html  # hidden until the owner asks: rate first


def test_sheet_without_judge_rows_has_no_judge_lines(tmp_path: Path) -> None:
    html = sheet.render(_records(), _measures(), root=None)
    assert "judge:" not in html and 'id="show-judge"' not in html
    root = tmp_path / "p1"
    _write_root(root)
    (root / "judge.jsonl").write_text("".join(json.dumps(j) + "\n" for j in _judge_rows()))
    assert sheet.main(["--root", str(root)]) == 0
    assert "judge: threatening · prop yes" in (root / "sheet.html").read_text()

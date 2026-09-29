"""`corpus coverage`: the read-only spread report and its draft comparison.

The command's promise is that it changes nothing, so several tests snapshot the corpus tree and
assert it is untouched. The rest pin the columns a planner reads, the next-n allocation (the same
one `sample` makes), and what `--against` warns about. (First written by the generation agent,
2026-09-29.)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml
from synthbench import cli
from synthbench.commands import coverage
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, CorpusManifest, IndexRow
from synthbench.taxonomy.coverage import cell_probs, marginals
from synthbench.taxonomy.model import DEFAULT_TAXONOMY, load_taxonomy, taxonomy_sha256

from backend.tests.unit.synthbench import helpers as h

HARD_NEGATIVE = "hooded_jogger"  # weight 1 in tierb-v0


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _exit_code(root: Path, *argv: str) -> int:
    """argparse exits (SystemExit) on a bad option; the command itself returns its code."""
    try:
        return h.run(root, *argv)
    except SystemExit as stop:
        return int(stop.code or 0)


def _coverage(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    assert h.run(root, "corpus", "coverage", *argv) == cli.EXIT_OK
    return capsys.readouterr().out


def _row(out: str, first: str) -> list[str]:
    """The whitespace-split cells of the first line whose first cell is `first`."""
    return next(line.split() for line in out.splitlines() if line.split()[:1] == [first])


def _draft(root: Path, name: str, version: str = "tierb-v1-draft") -> tuple[Path, dict[str, Any]]:
    tax: dict[str, Any] = yaml.safe_load(DEFAULT_TAXONOMY.read_text(encoding="utf-8"))
    tax["version"] = version
    return root / f"{name}.yaml", tax


def _write(path: Path, tax: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(tax, sort_keys=False, width=100), encoding="utf-8")
    return path


def _status(root: Path, event_id: str, status: str) -> None:
    store = h.store(root)
    row = store.latest_index()[event_id]
    store.append_index([row.model_copy(update={"status": status, "time": "2026-09-29T10:00:00Z"})])


def test_coverage_needs_no_corpus_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _tree(tmp_path)
    out = _coverage(tmp_path, capsys)
    assert "tierb-v0" in out
    assert "no events drawn yet" in out
    assert _tree(tmp_path) == before, "coverage wrote into the corpus root"


def test_a_sampled_corpus_is_read_and_left_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.sample(tmp_path, "pilot-1", n=6)
    before = _tree(tmp_path)
    _coverage(tmp_path, capsys, "--n", "50")
    assert _tree(tmp_path) == before


def test_every_axis_has_a_table_and_the_design_spaces_are_shown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _coverage(tmp_path, capsys)
    for axis in ("scenario", "property", "zone", "camera", "lighting", "weather"):
        assert _row(out, axis)[-2:] == ["next", "400"], axis  # each table's header row
    for space in ("full", "scenario+property+light+weather", "scenario+zone+light+weather"):
        assert int(_row(out, space)[1].replace(",", "")) > 0, space


def test_drawn_ready_and_failed_come_from_the_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, "pilot-1", n=4)
    _status(tmp_path, specs[0].event_id, "ready")
    _status(tmp_path, specs[1].event_id, "failed")
    out = _coverage(tmp_path, capsys)
    assert "4 events drawn (pilot-1 4); 1 ready, 1 failed" in out
    drawn = sum(s.cell.scenario == specs[0].cell.scenario for s in specs)
    row = _row(out, specs[0].cell.scenario)  # scenario label p to-30 share drawn ready next
    assert row[5:7] == [str(drawn), "1"]


def test_the_next_n_carries_the_corpus_counts_as_sample_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After a targeted batch, `sample` skips those scenarios until the rest catch up."""
    assert h.run(tmp_path, "sample", "--batch", "pilot-1", "--n", "5", "--only", HARD_NEGATIVE) == 0
    out = _coverage(tmp_path, capsys, "--n", "39")
    assert "next 39" in out
    assert _row(out, HARD_NEGATIVE)[-1] == "0"
    tax = load_taxonomy()
    assert sum(int(_row(out, s.id)[-1]) for s in tax.scenarios) == 39


def test_only_draws_the_next_n_from_those_scenarios(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _coverage(tmp_path, capsys, "--n", "6", "--only", f"{HARD_NEGATIVE},loitering")
    assert int(_row(out, HARD_NEGATIVE)[-1]) + int(_row(out, "loitering")[-1]) == 6
    assert _row(out, "package_theft")[-1] == "0"


def test_an_unknown_only_scenario_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert h.run(tmp_path, "corpus", "coverage", "--only", "nope") == cli.EXIT_ERROR
    assert "unknown scenario(s): nope" in capsys.readouterr().err


def test_only_and_against_cannot_be_combined(tmp_path: Path) -> None:
    path, tax = _draft(tmp_path, "draft")
    argv = ("corpus", "coverage", "--only", HARD_NEGATIVE, "--against", str(_write(path, tax)))
    assert _exit_code(tmp_path, *argv) == cli.EXIT_ERROR


def test_thin_values_name_the_scenarios_and_labels_that_can_show_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _coverage(tmp_path, capsys)
    line = next(line for line in out.splitlines() if line.split()[:2] == ["property", "warehouse"])
    assert "10 scenario(s) by label: incident 10;" in line  # every one, not just the listed three
    assert "likeliest: car_break_in 6%" in line
    mixed = next(line for line in out.splitlines() if line.split()[:2] == ["zone", "living_room"])
    assert "3 scenario(s) by label: benign 1, incident 2;" in mixed


def test_to_target_counts_down_from_the_events_held() -> None:
    assert coverage.to_target(0.25, 10) == "80"
    assert coverage.to_target(0.25, 30) == "done"
    assert coverage.to_target(0.0, 0) == "never"


def test_bad_n_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for bad in ("0", "-3", "many", "100001"):
        assert _exit_code(tmp_path, "corpus", "coverage", "--n", bad) == cli.EXIT_ERROR, bad
    assert "n must be" in capsys.readouterr().err


def test_a_corrupt_spec_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    specs = h.sample(tmp_path, "pilot-1", n=2)
    h.store(tmp_path).spec_file(specs[0].event_id).write_text("{", encoding="utf-8")
    assert h.run(tmp_path, "corpus", "coverage") == cli.EXIT_ASK
    assert "cannot read" in capsys.readouterr().err


def test_a_changed_taxonomy_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = h.store(tmp_path)
    store.write_new(
        store.manifest_file,
        CorpusManifest(
            version="tierb-v0",
            taxonomy_sha256="0" * 64,
            render_size=TIER_B_RENDER_SIZE,
            created="2026-09-28T00:00:00+00:00",
        ),
    )
    store.append_index(
        [IndexRow(event_id="B-x-000", batch="x", scenario="loitering", label="incident",
                  status="sampled", time="2026-09-28T00:00:00Z")]
    )  # fmt: skip
    assert h.run(tmp_path, "corpus", "coverage") == cli.EXIT_ASK
    assert "new corpus version" in capsys.readouterr().err


def test_an_unloadable_draft_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    draft = tmp_path / "broken.yaml"
    draft.write_text("version: [unclosed\n", encoding="utf-8")
    assert h.run(tmp_path, "corpus", "coverage", "--against", str(draft)) == cli.EXIT_ERROR
    assert "does not load" in capsys.readouterr().err


def test_a_draft_is_compared_and_never_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "candidate")
    before = taxonomy_sha256()
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    assert "tierb-v1-draft" in out
    assert taxonomy_sha256() == before, "--against installed the draft over the committed taxonomy"
    assert not (tmp_path / "corpus").exists()


def test_a_rebalanced_scenario_shows_both_sides_and_the_weight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "weighted")
    next(s for s in tax["scenarios"] if s["id"] == "loitering")["weight"] = 4.0
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    line = next(line for line in out.splitlines() if line.split()[:2] == ["scenario", "loitering"])
    assert "->" in line and "weight 1 -> 4" in line, line


def test_a_draft_that_keeps_the_committed_version_is_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "same-version", version="tierb-v0")
    next(s for s in tax["scenarios"] if s["id"] == "loitering")["weight"] = 4.0
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    assert "WARNING" in out and "every command" in out and "new version" in out


def test_a_draft_adding_a_property_reports_it_as_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "new-prop")
    tax["properties"].append({"id": "storefront", "zones": ["street_edge", "lobby_door"]})
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    line = next(line for line in out.splitlines() if line.split()[:2] == ["property", "storefront"])
    assert "(new)" in line
    assert "(+1)" in _row(out, "properties")[-1]


def test_the_next_n_is_what_sample_then_draws(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert h.run(tmp_path, "sample", "--batch", "pilot-1", "--n", "5", "--only", HARD_NEGATIVE) == 0
    out = _coverage(tmp_path, capsys, "--n", "23")
    specs = h.sample(tmp_path, "batch-2", n=23)
    drawn = Counter(spec.cell.scenario for spec in specs)
    for scenario in load_taxonomy().scenarios:
        assert int(_row(out, scenario.id)[-1]) == drawn[scenario.id], scenario.id


def test_to_30_counts_every_drawn_event_that_has_not_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = h.sample(tmp_path, "pilot-1", n=4)
    _status(tmp_path, specs[0].event_id, "failed")
    out = _coverage(tmp_path, capsys)
    p = marginals(cell_probs(load_taxonomy()))["scenario"]
    drawn = Counter(s.cell.scenario for s in specs)
    failed = specs[0].cell.scenario
    assert _row(out, failed)[3] == coverage.to_target(p[failed], drawn[failed] - 1)
    other = next(s.cell.scenario for s in specs if s.cell.scenario != failed)
    # Drawn and not ready (still in flight): it counts, so to-30 is below a ready-only count.
    assert _row(out, other)[3] == coverage.to_target(p[other], drawn[other])
    assert _row(out, other)[3] != coverage.to_target(p[other], 0)
    assert "counting every drawn event that has not failed" in out


def test_a_value_no_scenario_can_show_is_listed_as_never(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path, tax = _draft(tmp_path, "rooftop", version="tierb-v0")
    tax["zones"].append("rooftop")
    tax["properties"].append({"id": "storefront", "zones": ["rooftop"]})
    tax["cameras"].append({"id": "roof_cam", "zones": ["rooftop"]})
    unreachable = load_taxonomy(_write(path, tax))
    monkeypatch.setattr(coverage, "taxonomy", lambda: unreachable)
    out = _coverage(tmp_path, capsys)
    for value in ("storefront", "rooftop", "roof_cam"):
        assert _row(out, value)[1:3] == ["0.00%", "never"], value
    line = next(line for line in out.splitlines() if line.split()[:2] == ["zone", "rooftop"])
    assert "no scenario can show it" in line


def test_a_draft_adding_an_unreachable_property_reports_it_as_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "rooftop")
    tax["zones"].append("rooftop")
    tax["properties"].append({"id": "storefront", "zones": ["rooftop"]})
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    for axis in ("property storefront", "zone rooftop"):
        line = next(line for line in out.splitlines() if line.startswith(f"  {axis} "))
        assert "(new)" in line and "never" in line, line


def test_a_draft_that_only_reorders_moves_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, tax = _draft(tmp_path, "reordered")
    for key in ("scenarios", "properties", "cameras"):
        tax[key].reverse()
    out = _coverage(tmp_path, capsys, "--against", str(_write(path, tax)))
    moved = out.split("values whose chance per event moves")[1].splitlines()[1:]
    assert moved == ["  none"]


def test_the_header_never_suggests_a_sample_over_its_cap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _coverage(tmp_path, capsys, "--n", "1000")
    assert "--n 1000" not in out
    assert "next 1000: the events `sample` would draw next" in out

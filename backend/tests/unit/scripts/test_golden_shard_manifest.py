"""The golden shard manifest is the whole suite, balanced, and byte-reproducible.

**[r282]** Playwright's count-based ``--shard=i/N`` splits spec FILES by count,
not duration, so the golden shards came out unbalanced where it matters: in the
five green runs this package measured (39438896950, 39440429144, 39441319838,
39445382087, 39445965194), per-shard test-time sums keyed by each artifact's own
``artifacts/summary.json`` were 421s (incl. the backend golden leg's 84s) /
262s / 494s / 457s -- a 232s spread that no count-based split can close, because
the corpus is top-heavy (event-feedback.spec.ts alone is 118.8s; a tail of ~30
files sits under 4s).

The fix is a checked-in manifest (spec file -> shard index) produced by a regen
script that greedy-packs files by their measured per-file median (longest
processing time first, one file per unit, the backend leg pre-loaded on shard 1
-- [r264]'s rule, kept because the measurement supports it: 84s on shard 1 keeps
every shard under 323s). The config reads the manifest and selects files per
shard; ``--shard`` stays as the fallback when no manifest is named. A test pins
that the union of shards is exactly the suite on disk -- the same class of
silent-drift bug the [r264] sharding had to avoid (a file added to
``tests/golden/`` and never manifest-ed would silently run on NO shard, which
is worse than running on the wrong one).

The medians JSON is data, checked in, with its provenance (the five runs and
n=5 per file); the docs say when it is refreshed. The regen script is
byte-stable: sorted keys, sorted files, no timestamps -- two runs on the same
input produce identical bytes, and the pin below runs it twice to prove it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FRONTEND = REPO / "frontend"
MANIFEST = FRONTEND / "golden-shards.json"
MEDIANS = REPO / "scripts" / "golden-shard-durations.json"
REGEN = REPO / "scripts" / "golden_shard_manifest.py"


def _golden_spec_files() -> list[str]:
    """Every golden spec file on disk, as the manifest names them (frontend-relative)."""
    return sorted(
        str(p.relative_to(FRONTEND))
        for p in (FRONTEND / "tests" / "golden").rglob("*.spec.ts")
        if not p.name.endswith(".seeded.spec.ts")
    )


def test_the_manifest_exists_and_declares_four_shards() -> None:
    """[r282] The checked-in manifest is real JSON with the designed shard count."""
    assert MANIFEST.is_file(), f"missing {MANIFEST}"
    data = json.loads(MANIFEST.read_text())
    assert data["shard_count"] == 4, data.get("shard_count")
    assert len(data["shards"]) == 4, [len(s) for s in data["shards"]]


def test_the_manifests_union_is_exactly_the_suite_on_disk() -> None:
    """[r282] The union of the manifest's shard lists is every golden spec file.

    A spec file added to tests/golden/ and never manifest-ed would run on NO
    shard -- Playwright would not see it in any --shard leg, the merged fan-in
    would not merge it, and CI would stay green while the suite silently shrank.
    This pin is the union guard the ruling asks for.
    """
    data = json.loads(MANIFEST.read_text())
    listed = [f for shard in data["shards"] for f in shard]
    on_disk = _golden_spec_files()
    assert sorted(listed) == on_disk, (
        f"manifest/disk drift: listed-only={sorted(set(listed) - set(on_disk))} "
        f"disk-only={sorted(set(on_disk) - set(listed))}"
    )


def test_no_file_appears_in_two_shards() -> None:
    """[r282] One file, one shard: a duplicated file would run twice per CI run."""
    data = json.loads(MANIFEST.read_text())
    listed = [f for shard in data["shards"] for f in shard]
    dupes = {f for f in listed if listed.count(f) > 1}
    assert not dupes, f"duplicated across shards: {sorted(dupes)}"


def test_every_listed_file_exists_on_disk() -> None:
    """[r282] A deleted spec leaves a manifest row pointing at nothing; that is drift."""
    data = json.loads(MANIFEST.read_text())
    missing = [f for shard in data["shards"] for f in shard if not (FRONTEND / f).is_file()]
    assert not missing, f"manifest lists files that do not exist: {missing}"


def test_the_medians_data_covers_every_golden_spec_file() -> None:
    """[r282] The medians JSON (the pack's input) covers the same file set as disk.

    If a spec file is on disk but absent from the medians, the regen script would
    have to guess its duration -- and a guessed duration is how the balance claim
    rots. The pin keeps input and corpus in lockstep.
    """
    medians = json.loads(MEDIANS.read_text())
    measured = set(medians["files"])
    on_disk = set(_golden_spec_files())
    assert measured == on_disk, (
        f"medians/disk drift: medians-only={sorted(measured - on_disk)} "
        f"disk-only={sorted(on_disk - measured)}"
    )
    for path, entry in medians["files"].items():
        assert entry["n"] >= 5, f"{path} measured only {entry['n']} times"


def test_the_regen_scripts_output_byte_matches_the_checked_in_manifest(
    tmp_path: Path,
) -> None:
    """[r282] Regen on the checked-in medians reproduces the checked-in manifest bytes.

    The manifest is not hand-maintained: it is the regen script's output. If the
    checked-in manifest and the script's output diverge, one of them is lying --
    and the union pin above would then guard a fiction.
    """
    out = tmp_path / "regen.json"
    proc = subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
        [sys.executable, "-I", str(REGEN), "--medians", str(MEDIANS), "--out", str(out)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.read_bytes() == MANIFEST.read_bytes(), (
        "regen output differs from the checked-in manifest -- refresh "
        "frontend/golden-shards.json by running scripts/golden_shard_manifest.py"
    )


def test_the_regen_script_is_deterministic(tmp_path: Path) -> None:
    """[r282] Two regen runs on the same input produce identical bytes.

    No timestamps, no dict-ordering drift: sorted keys throughout. A manifest
    that churns on every regen would make every refresh a full-file diff.
    """
    outs = []
    for i in (1, 2):
        out = tmp_path / f"regen{i}.json"
        proc = subprocess.run(  # noqa: S603  # intentional - tests our own script, offline
            [sys.executable, "-I", str(REGEN), "--medians", str(MEDIANS), "--out", str(out)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        outs.append(out.read_bytes())
    assert outs[0] == outs[1]


def test_pack_resolves_ties_by_path_regardless_of_input_order() -> None:
    """[r282] pack() itself is order-independent on tied durations.

    The determinism contract ("ties broken by file path") lives in pack(), not
    in its callers: main() happens to pre-sort its input alphabetically, which
    would mask a pack() that resolved ties by dict insertion order (Python's
    sort is stable, so a -duration-only key follows insertion order). This pin
    calls pack() directly with the same tied durations in two different
    insertion orders and requires identical shards -- the one input on which
    the two tiebreak strategies visibly disagree.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("golden_shard_manifest", REGEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tied = {"b/zebra.spec.ts": 10.0, "a/alpha.spec.ts": 10.0, "c/mid.spec.ts": 5.0}
    forward = mod.pack(dict(tied), 2, 0.0)
    reverse = mod.pack(dict(reversed(list(tied.items()))), 2, 0.0)
    assert forward == reverse, (forward, reverse)
    assert forward == [["a/alpha.spec.ts", "c/mid.spec.ts"], ["b/zebra.spec.ts"]], forward


def test_the_pack_is_balanced_within_the_designs_own_bar() -> None:
    """[r282] With the checked-in medians, max total wall - min total wall <= 2.0s.

    Total wall per shard is its Playwright file sum PLUS the backend golden leg
    on the leg's shard (an 84s fixed cost -- [r264]'s rule, kept by measurement).
    The pack deliberately gives the leg's shard ~84s LESS frontend work, so
    balancing on the frontend portion alone would flag the design as a defect.
    This pin recomputes the loads from the medians and the leg constant rather
    than trusting the manifest's own ``loads_seconds`` -- and then asserts the
    manifest's numbers match the recomputation, so the manifest cannot report
    loads it does not have.

    The Done-when's shard-spread clause is measured on real CI walls; this pin
    holds the PACK to its own tighter bar so wall spread beyond 2min can only
    come from fixed costs the medians do not model.
    """
    data = json.loads(MANIFEST.read_text())
    medians = json.loads(MEDIANS.read_text())["files"]
    backend_leg = 84.0  # the leg's measured median; scripts/golden_shard_manifest.py's constant
    computed = [
        round(
            sum(medians[f]["median"] for f in shard)
            + (backend_leg if i == data["backend_leg_shard"] - 1 else 0.0),
            3,
        )
        for i, shard in enumerate(data["shards"])
    ]
    assert computed == data["loads_seconds"], (computed, data["loads_seconds"])
    assert max(computed) - min(computed) <= 2.0, computed

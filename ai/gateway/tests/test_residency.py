"""Unit tests for the Triton model-residency sets (Phase 1.4, spec rev 6).

Rev 6 (owner ruling F11): residency control is the *repository*, not Triton
load control. The gateway keeps --model-control-mode=none and serves a static
`vlm` model repository — YOLO26, re-ID and (optionally) the threat detector.
Every model in the active set is resident; retired models are never present
for Triton to scan, so they cannot load. There is no explicit mode and no
on-demand specialist loading.

These pins are the sandbox-provable half (F3: no arm64/sbsa tritonserver here).
The live half — "no retired model appears in Triton's model index" — is the
A5500's [O], 1.7.

R8 S3 (2026-09-29, owner rulings 2/3/5) cut the residency universe from 14
names to the kept three and retired the `full` SELECTABLE name, so five pins
here were red rather than merely stale, and two of them asserted the exact
opposite of the shipped module:

* "full is the 14-name table" (x2) — the tuple is now the kept three, pinned by
  ``TestTritonRepositoryPruned.test_full_model_set_is_the_kept_three``; here the
  pin is DERIVED from the on-disk repository instead of a remembered list, which
  is the same fact from the live side (the dirs exist) rather than the dead-name
  side;
* "`full` is selectable and ignores the threat flag" and "unset env defaults to
  full" — both are now KeyError paths (ruling 3);
* two ``apply_model_set`` pins reached into a synthetic tree for a
  ``florence2/`` directory that the fixture no longer creates, because the
  fixture builds one dir per ``FULL_MODEL_SET`` member. Retargeted to a DERIVED
  victim: the universe member that the vlm set does not keep.

The enumeration of the 11 retired model names is NOT restated here. That list is
the guard's (``PRUNED_MODELS``), and a second copy in the tier whose module the
prune edited is a pin that rots twice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.gateway.residency import (
    FULL_MODEL_SET,
    VLM_MODEL_BASE,
    VLM_THREAT_MODEL,
    apply_model_set,
    get_model_set,
    resolve_active_set,
)
from ai.gateway.residency import (
    main as _residency_main,
)

# The vlm set this tier boots under, and the universe member it leaves out —
# derived, so a residency change moves these lines instead of silently
# invalidating them.
_KEEP = ("yolo26", "reid")
_VLM_PLUS_THREAT = (*_KEEP, VLM_THREAT_MODEL)


def _retired_universe_member() -> str:
    """A name in the residency universe that the vlm set does not serve.

    ``apply_model_set`` only ever moves names inside ``FULL_MODEL_SET``, so the
    move/restore round-trip needs a member outside the keep set to have anything
    to move at all. Deriving it (rather than naming a swept model, as pre-S3 did)
    keeps the test about the mechanism while making its non-vacuity explicit: if
    the universe ever equalled the keep set, this raises instead of passing on an
    empty move.
    """
    candidates = [m for m in FULL_MODEL_SET if m not in _KEEP]
    assert candidates, (
        f"FULL_MODEL_SET {FULL_MODEL_SET} has no member outside {_KEEP}: "
        "apply_model_set would have nothing to retire and these pins are vacuous"
    )
    return candidates[0]


def _repository_dirs() -> set[str]:
    """The Triton model directories the image actually ships."""
    repo = Path(__file__).resolve().parents[3] / "ai" / "triton" / "model_repository"
    return {p.name for p in repo.iterdir() if p.is_dir()}


class TestNamedSets:
    def test_full_set_is_main_apis_registry(self) -> None:
        """Sync pinned, not promised: main.py derives ALL_MODELS from this
        tuple, so the gateway's /health can never describe a set the
        residency module might prune away (review 1.4 item 1 — the hard-coded
        mirror below proves the contents, this proves the identity)."""
        from ai.gateway.main import ALL_MODELS

        assert list(ALL_MODELS) == list(FULL_MODEL_SET)

    def test_universe_matches_the_shipped_repository(self) -> None:
        """The universe is the repository, not a memory of one.

        Rev 6's residency mechanism is "which directories Triton scans", and
        ``apply_model_set`` refuses to touch names outside ``FULL_MODEL_SET`` —
        so a name in the tuple with no directory is a model /health can claim,
        and a directory outside the tuple is a foreign dir that silently serves.
        Pre-S3 this pin hand-listed the 14-model repository; the 11 retired dirs
        were removed with ``git rm`` in the same slice, and the enumeration of
        what left is ``PRUNED_MODELS`` in the S3 guard. Equality against the
        dirs on disk is the same guard rail from the live side and cannot rot.
        """
        present = _repository_dirs()
        assert set(FULL_MODEL_SET) == present, (
            f"universe {sorted(FULL_MODEL_SET)} != repository {sorted(present)}"
        )
        # Non-vacuity: a real multi-model repository, not an empty pair of sets.
        assert len(present) >= 2, sorted(present)

    def test_vlm_base_is_the_two_resident_specialists(self) -> None:
        """The unconditional vlm set: the YOLO26 gate plus re-ID. Every other
        Triton model (florence, clip, demographics, depth, pet, pose,
        vehicle, fashion_clip, stgcn) is retired in vlm mode — that retirement
        is the guard's enumeration; what is pinned here is the shipped pair."""
        assert VLM_MODEL_BASE == _KEEP

    def test_vlm_set_is_a_strict_subset_of_the_universe(self) -> None:
        """The whole point of rev 6, expressed without naming a dead model:
        the served set is inside the universe AND does not exhaust it, so
        residency really does prune — there is at least one universe member
        Triton will never be asked to load in vlm mode."""
        vlm = get_model_set("vlm", threat_enabled=False)
        assert set(vlm) < set(FULL_MODEL_SET), (vlm, FULL_MODEL_SET)
        # ...and nothing it serves is missing from disk (the false-alarm class).
        assert set(vlm) <= _repository_dirs()

    def test_threat_is_the_optional_member(self) -> None:
        """Threat joins the vlm set only when enabled — it is the optional
        fourth specialist under D3 rev 6, and Task 3b still owes the
        ledgered include/not-include call."""
        assert get_model_set("vlm", threat_enabled=False) == VLM_MODEL_BASE
        assert VLM_THREAT_MODEL == "threat"
        assert get_model_set("vlm", threat_enabled=True) == _VLM_PLUS_THREAT

    def test_the_threat_flag_only_shapes_the_selectable_set(self) -> None:
        """Rev 6 had two selectable sets and this pinned that `full` already
        carried threat, so the flag changed only the vlm footprint. Ruling 3
        retired the `full` NAME, which makes the flag's reach measurable a
        different way: it can only ever act on `vlm`, and every other name —
        including the retired one, with the flag either way — is refused before
        the flag is consulted."""
        assert get_model_set("vlm", threat_enabled=True) != get_model_set(
            "vlm", threat_enabled=False
        )
        # The retired name raises for BOTH flag values: the flag never gets a
        # say, which is the successor of "full ignores the threat flag".
        for enabled in (True, False):
            with pytest.raises(KeyError):
                get_model_set("full", threat_enabled=enabled)
        # Non-vacuity: `vlm` is the one name that does resolve, so the raises
        # above are about the name and not a broken lookup path.
        assert get_model_set("vlm", threat_enabled=True) == _VLM_PLUS_THREAT

    def test_retired_name_raises_for_both_flag_states(self) -> None:
        """Ruling 3's `full` arm, at the module this tier owns (the guard's
        ``TestGatewayModelSetHardRaise`` pins the same raise from the
        retirement-record side; this is the residency-module side)."""
        for name in ("full", "nemotron", ""):
            with pytest.raises(KeyError):
                get_model_set(name, threat_enabled=False)

    def test_unknown_set_raises(self) -> None:
        with pytest.raises(KeyError):
            get_model_set("nonsense", threat_enabled=False)


class TestResolveActiveSet:
    def test_unset_env_raises_instead_of_defaulting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No env → raise. This replaced "no env → full", which was the
        bare-module fallback ruling 3 retired: the fallback's only remaining
        customer was the legacy pipeline's bring-the-whole-repo-up affordance,
        and the pipeline was deleted in S1. Silence is a misconfigured
        container, and the same fail-at-start doctrine as PIPELINE_MODE says a
        misconfiguration stops the container rather than serving a surprise
        footprint. Note the direction of the pin: it asserts the RAISE, so a
        future "be helpful and default it" edit reddens here."""
        monkeypatch.delenv("GATEWAY_MODEL_SET", raising=False)
        with pytest.raises(KeyError):
            resolve_active_set()

    def test_env_selects_vlm_without_threat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        assert resolve_active_set() == _KEEP

    def test_env_adds_threat_when_opted_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.setenv("GATEWAY_ENABLE_THREAT", "true")
        assert resolve_active_set() == _VLM_PLUS_THREAT

    def test_threat_optin_is_falsey_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only an affirmative value adds threat; 0/false/unset do not."""
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        for val in ("0", "false", "no", ""):
            monkeypatch.setenv("GATEWAY_ENABLE_THREAT", val)
            assert VLM_THREAT_MODEL not in resolve_active_set()


def _make_repo(root: Path) -> None:
    """A repository tree shaped like the baked one: one dir per universe model,
    each with a config.pbtxt and a version dir."""
    for name in FULL_MODEL_SET:
        model_dir = root / name
        (model_dir / "1").mkdir(parents=True)
        (model_dir / "config.pbtxt").write_text(f'name: "{name}"\n')
        (model_dir / "1" / "model.onnx").write_text("weights")


def _dirs(root: Path) -> set[str]:
    return {p.name for p in root.iterdir() if p.is_dir()}


class TestApplyModelSet:
    def test_prunes_to_the_vlm_set(self, tmp_path: Path) -> None:
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, get_model_set("vlm", threat_enabled=False))
        assert _dirs(repo) == set(_KEEP)

    def test_retired_models_are_moved_not_deleted(self, tmp_path: Path) -> None:
        """Idempotent, restorable switch: the retired tree keeps every model
        dir so switching the set back restores it without a rebuild (the 1.7
        bring-up and any rollback depend on this)."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, _KEEP)
        moved = _dirs(retired)
        assert set(FULL_MODEL_SET) - set(_KEEP) == moved
        # Contents survive the move — pinned on a derived universe member, not
        # on a name this slice swept out of the tuple (pre-S3 named florence2,
        # whose directory the fixture can no longer build).
        victim = _retired_universe_member()
        assert victim in moved
        assert (retired / victim / "config.pbtxt").exists()

    def test_switching_back_restores(self, tmp_path: Path) -> None:
        """vlm → universe round-trip leaves every model dir present again, with
        its version dir intact (move-both-ways, not delete-and-rebuild)."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        victim = _retired_universe_member()
        apply_model_set(repo, retired, _KEEP)
        apply_model_set(repo, retired, FULL_MODEL_SET)
        assert _dirs(repo) == set(FULL_MODEL_SET)
        assert (repo / victim / "1" / "model.onnx").read_text() == "weights"

    def test_adding_threat_promotes_from_retired(self, tmp_path: Path) -> None:
        """Going vlm(no-threat) → vlm(threat) pulls `threat` back out of the
        retired staging into the live repository."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, _KEEP)
        apply_model_set(repo, retired, _VLM_PLUS_THREAT)
        assert _dirs(repo) == set(_VLM_PLUS_THREAT)
        assert VLM_THREAT_MODEL not in _dirs(retired)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, _KEEP)
        apply_model_set(repo, retired, _KEEP)
        assert _dirs(repo) == set(_KEEP)
        assert len(_dirs(retired)) == len(FULL_MODEL_SET) - len(_KEEP)

    def test_full_set_is_a_noop_on_a_fresh_repo(self, tmp_path: Path) -> None:
        """``FULL_MODEL_SET`` is no longer a SELECTABLE name (ruling 3), but it
        is still the universe apply_model_set is allowed to move — passing it as
        the keep set must move nothing."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, FULL_MODEL_SET)
        assert _dirs(repo) == set(FULL_MODEL_SET)
        assert not retired.exists() or _dirs(retired) == set()

    def test_foreign_dirs_are_left_alone(self, tmp_path: Path) -> None:
        """A stray directory (or a model the named set never knew about) is
        neither promoted nor retired — the function only moves names it can
        attribute to a known model set."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        (repo / "not_a_model").mkdir()
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, _KEEP)
        assert "not_a_model" in _dirs(repo)


class TestCli:
    """The entrypoint calls `python3 -m ai.gateway.residency` — main()'s
    argparse/env composition is the deployed seam."""

    def test_main_prunes_via_env_and_args(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo = tmp_path / "repository"
        _make_repo(repo)
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        monkeypatch.setattr(
            "sys.argv",
            [
                "residency",
                "--repository",
                str(repo),
                "--retired-dir",
                str(tmp_path / "retired_models"),
            ],
        )
        _residency_main()
        assert _dirs(repo) == set(_KEEP)
        # The count in the log line is derived from the set, so a residency
        # change does not require editing this string.
        assert f"serving {len(_KEEP)} model(s)" in capsys.readouterr().out

    def test_default_retired_dir_siblings_the_repository(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No --retired-dir → <repository>.retired, the path the entrypoint's
        comment promises."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        monkeypatch.setattr("sys.argv", ["residency", "--repository", str(repo)])
        _residency_main()
        assert _dirs(tmp_path / "repository.retired") == set(FULL_MODEL_SET) - set(_KEEP)

    def test_unset_model_set_stops_the_container(self, tmp_path: Path, monkeypatch) -> None:
        """The deployed seam inherits the hard raise: main() has no default to
        fall back to, so an operator who forgets GATEWAY_MODEL_SET gets the
        KeyError at the residency step — before Triton starts — rather than a
        repository pruned to somebody's guess."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        monkeypatch.delenv("GATEWAY_MODEL_SET", raising=False)
        monkeypatch.setattr("sys.argv", ["residency", "--repository", str(repo)])
        with pytest.raises(KeyError):
            _residency_main()
        # Non-vacuity: the repository is untouched by the aborted run.
        assert _dirs(repo) == set(FULL_MODEL_SET)

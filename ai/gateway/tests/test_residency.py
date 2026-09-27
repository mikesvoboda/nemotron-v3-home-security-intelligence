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


class TestNamedSets:
    def test_full_set_is_main_apis_registry(self) -> None:
        """Sync pinned, not promised: main.py derives ALL_MODELS from this
        tuple, so the gateway's /health can never describe a set the
        residency module might prune away (review 1.4 item 1 — the hard-coded
        mirror below proves the contents, this proves the identity)."""
        from ai.gateway.main import ALL_MODELS

        assert list(ALL_MODELS) == list(FULL_MODEL_SET)

    def test_full_set_is_the_current_fourteen(self) -> None:
        """`full` is exactly today's ALL_MODELS — the machinery changes no
        deployment until something selects a different set."""
        assert set(FULL_MODEL_SET) == {
            "yolo26",
            "clip",
            "clip_text",
            "florence2",
            "vehicle",
            "fashion_clip",
            "demographics_age",
            "demographics_gender",
            "pet",
            "depth",
            "reid",
            "pose",
            "threat",
            "stgcn_action",
        }

    def test_vlm_base_is_the_two_resident_specialists(self) -> None:
        """The unconditional vlm set: the YOLO26 gate plus re-ID. Every other
        Triton model (florence, clip, demographics, depth, pet, pose,
        vehicle, fashion_clip, stgcn) is retired in vlm mode."""
        assert VLM_MODEL_BASE == ("yolo26", "reid")

    def test_vlm_set_excludes_every_retired_model(self) -> None:
        """The whole point of rev 6: retired models are absent from the set,
        so Triton never loads them."""
        vlm = get_model_set("vlm", threat_enabled=False)
        assert set(vlm).isdisjoint(
            {
                "florence2",
                "clip",
                "clip_text",
                "vehicle",
                "fashion_clip",
                "demographics_age",
                "demographics_gender",
                "pet",
                "depth",
                "pose",
                "stgcn_action",
            }
        )

    def test_threat_is_the_optional_member(self) -> None:
        """Threat joins the vlm set only when enabled — it is the optional
        fourth specialist under D3 rev 6, and Task 3b still owes the
        ledgered include/not-include call."""
        assert get_model_set("vlm", threat_enabled=False) == VLM_MODEL_BASE
        assert VLM_THREAT_MODEL == "threat"
        assert get_model_set("vlm", threat_enabled=True) == ("yolo26", "reid", "threat")

    def test_full_set_ignores_the_threat_flag(self) -> None:
        """`full` already carries threat; the flag only shapes the vlm set."""
        assert get_model_set("full", threat_enabled=True) == FULL_MODEL_SET
        assert get_model_set("full", threat_enabled=False) == FULL_MODEL_SET

    def test_unknown_set_raises(self) -> None:
        with pytest.raises(KeyError):
            get_model_set("nonsense", threat_enabled=False)


class TestResolveActiveSet:
    def test_defaults_to_full(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No env → full. The shipped default (nemotron pipeline) still calls
        enrichment's Triton models, so nothing narrows the repository until
        1.5/1.7 select vlm mode."""
        monkeypatch.delenv("GATEWAY_MODEL_SET", raising=False)
        assert resolve_active_set() == FULL_MODEL_SET

    def test_env_selects_vlm_without_threat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        assert resolve_active_set() == ("yolo26", "reid")

    def test_env_adds_threat_when_opted_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.setenv("GATEWAY_ENABLE_THREAT", "true")
        assert resolve_active_set() == ("yolo26", "reid", "threat")

    def test_threat_optin_is_falsey_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only an affirmative value adds threat; 0/false/unset do not."""
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        for val in ("0", "false", "no", ""):
            monkeypatch.setenv("GATEWAY_ENABLE_THREAT", val)
            assert "threat" not in resolve_active_set()


def _make_repo(root: Path) -> None:
    """A repository tree shaped like the baked one: one dir per Triton model,
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
        assert _dirs(repo) == {"yolo26", "reid"}

    def test_retired_models_are_moved_not_deleted(self, tmp_path: Path) -> None:
        """Idempotent, restorable switch: the retired tree keeps every model
        dir so switching the set back restores it without a rebuild (the 1.7
        bring-up and any rollback depend on this)."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, ("yolo26", "reid"))
        moved = _dirs(retired)
        assert set(FULL_MODEL_SET) - {"yolo26", "reid"} == moved
        # contents survive the move
        assert (retired / "florence2" / "config.pbtxt").exists()

    def test_switching_back_restores(self, tmp_path: Path) -> None:
        """vlm → full round-trip leaves every model dir present again, with
        its version dir intact (move-both-ways, not delete-and-rebuild)."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, ("yolo26", "reid"))
        apply_model_set(repo, retired, FULL_MODEL_SET)
        assert _dirs(repo) == set(FULL_MODEL_SET)
        assert (repo / "florence2" / "1" / "model.onnx").read_text() == "weights"

    def test_adding_threat_promotes_from_retired(self, tmp_path: Path) -> None:
        """Going vlm(no-threat) → vlm(threat) pulls `threat` back out of the
        retired staging into the live repository."""
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        apply_model_set(repo, retired, ("yolo26", "reid"))
        apply_model_set(repo, retired, ("yolo26", "reid", "threat"))
        assert _dirs(repo) == {"yolo26", "reid", "threat"}
        assert "threat" not in _dirs(retired)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        repo = tmp_path / "repository"
        _make_repo(repo)
        retired = tmp_path / "retired_models"
        keep = ("yolo26", "reid")
        apply_model_set(repo, retired, keep)
        apply_model_set(repo, retired, keep)
        assert _dirs(repo) == {"yolo26", "reid"}
        assert len(_dirs(retired)) == len(FULL_MODEL_SET) - 2

    def test_full_set_is_a_noop_on_a_fresh_repo(self, tmp_path: Path) -> None:
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
        apply_model_set(repo, retired, ("yolo26", "reid"))
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
        assert _dirs(repo) == {"yolo26", "reid"}
        assert "serving 2 model(s)" in capsys.readouterr().out

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
        assert _dirs(tmp_path / "repository.retired") == set(FULL_MODEL_SET) - {
            "yolo26",
            "reid",
        }

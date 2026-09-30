"""Unit tests for ai.gateway.patch_triton_configs.

Tests the centralized Triton config patching infrastructure:
- set_instance_group() — rewrites kind/count/gpus in config.pbtxt
- collect_triton_configs() — parses models.yml into (triton_name, triton_kind) pairs
- main() — integration with tmp_path fixtures
- models.yml validation — consistency with Triton model repository
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestSetInstanceGroup:
    """Tests for set_instance_group() — pure function, no I/O."""

    def test_cpu_to_gpu_adds_gpus_line_and_normalizes_count(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
name: "test"
instance_group [
  {
    count: 2
    kind: KIND_CPU
  }
]
"""
        result = set_instance_group(config, "KIND_GPU")
        assert "kind: KIND_GPU" in result
        assert "gpus: [ 0 ]" in result
        assert "count: 1" in result

    def test_gpu_to_cpu_removes_gpus_line_preserves_count(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
name: "test"
instance_group [
  { count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
"""
        result = set_instance_group(config, "KIND_CPU")
        assert "kind: KIND_CPU" in result
        assert "gpus:" not in result
        assert "count: 2" in result

    def test_gpu_removes_parameters_block(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
name: "test"
instance_group [ { count: 1
  kind: KIND_CPU
} ]

parameters {
  key: "intra_op_thread_count"
  value: { string_value: "4" }
}

parameters {
  key: "execution_mode"
  value: { string_value: "1" }
}

dynamic_batching { }
"""
        result = set_instance_group(config, "KIND_GPU")
        assert "kind: KIND_GPU" in result
        assert "gpus: [ 0 ]" in result
        assert "intra_op_thread_count" not in result
        assert "execution_mode" not in result
        assert "dynamic_batching" in result

    def test_cpu_preserves_parameters_block(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
instance_group [ { count: 2
  kind: KIND_GPU
  gpus: [ 0 ]
} ]

parameters {
  key: "intra_op_thread_count"
  value: { string_value: "4" }
}
"""
        result = set_instance_group(config, "KIND_CPU")
        assert "kind: KIND_CPU" in result
        assert "gpus:" not in result
        assert "intra_op_thread_count" in result

    def test_gpu_drops_existing_duplicate_gpus_line(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
instance_group [
  { count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
    gpus: [ 1 ]
  }
]
"""
        result = set_instance_group(config, "KIND_GPU")
        # Should have exactly one gpus line (the one we inject)
        assert result.count("gpus:") == 1
        assert "gpus: [ 0 ]" in result

    def test_idempotent_when_already_correct_kind_gpu(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
instance_group [
  { count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
    rate_limiter { resources [ { name: "global" count: 1 } ] priority: 3 }
  }
]
"""
        result = set_instance_group(config, "KIND_GPU")
        assert result == config

    def test_preserves_inline_comment_on_kind_line(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
instance_group [
  { count: 1
    kind: KIND_CPU  # 14MB model runs efficiently on CPU
  }
]
"""
        result = set_instance_group(config, "KIND_CPU")
        assert "# 14MB model runs efficiently on CPU" in result

    def test_gpu_with_custom_gpu_index(self) -> None:
        from ai.gateway.patch_triton_configs import set_instance_group

        config = """
instance_group [ { count: 2
  kind: KIND_CPU
} ]
"""
        result = set_instance_group(config, "KIND_GPU", gpu_index=2)
        assert "gpus: [ 2 ]" in result


class TestCollectTritonConfigs:
    """Tests for collect_triton_configs() — pure function, no I/O."""

    def test_simple_form(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [{"name": "alpha", "triton_name": "alpha", "triton_kind": "KIND_GPU"}]
        assert collect_triton_configs(models) == [("alpha", "KIND_GPU")]

    def test_triton_models_list(self) -> None:
        """One catalogue row mapping to TWO Triton directories, order preserved.

        The synthetic names are deliberately placeholders: this is a parser test
        for a pure function, and pre-S3 it used the real (now-retired) CLIP pair
        as its example data — which made a name with no repository directory look
        like sanctioned test data. Neutral names say what the test means.
        """
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [
            {
                "name": "multi",
                "triton_models": [
                    {"triton_name": "one", "triton_kind": "KIND_GPU"},
                    {"triton_name": "two", "triton_kind": "KIND_CPU"},
                ],
            }
        ]
        assert collect_triton_configs(models) == [
            ("one", "KIND_GPU"),
            ("two", "KIND_CPU"),
        ]

    def test_triton_models_first_then_top_level(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [
            {
                "name": "m",
                "triton_models": [{"triton_name": "a", "triton_kind": "KIND_GPU"}],
                "triton_name": "b",
                "triton_kind": "KIND_CPU",
            }
        ]
        result = collect_triton_configs(models)
        assert ("a", "KIND_GPU") in result
        assert ("b", "KIND_CPU") in result
        assert result.index(("a", "KIND_GPU")) < result.index(("b", "KIND_CPU"))

    def test_skip_incomplete_no_triton_kind(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [{"name": "x", "triton_name": "x"}]
        assert collect_triton_configs(models) == []

    def test_skip_incomplete_no_triton_name(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [{"name": "x", "triton_kind": "KIND_GPU"}]
        assert collect_triton_configs(models) == []

    def test_empty_list(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        assert collect_triton_configs([]) == []

    def test_type_coercion_to_str(self) -> None:
        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = [{"triton_name": 123, "triton_kind": "KIND_GPU"}]
        assert collect_triton_configs(models) == [("123", "KIND_GPU")]


class TestMain:
    """Tests for main() — integration with tmp_path and monkeypatch."""

    def test_models_yml_missing_prints_warning_returns(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        from ai.gateway import patch_triton_configs

        missing = tmp_path / "nonexistent.yml"
        monkeypatch.setattr(patch_triton_configs, "MODELS_YAML", missing)
        monkeypatch.setattr(patch_triton_configs, "REPO", tmp_path / "repo")

        patch_triton_configs.main()

        captured = capsys.readouterr()
        assert "not found" in captured.err
        assert "skipping" in captured.err.lower()

    def test_empty_models_prints_message_returns(self, tmp_path: Path, monkeypatch, capsys) -> None:
        from ai.gateway import patch_triton_configs

        (tmp_path / "models.yml").write_text("models: []\n")
        monkeypatch.setattr(patch_triton_configs, "MODELS_YAML", tmp_path / "models.yml")
        monkeypatch.setattr(patch_triton_configs, "REPO", tmp_path / "repo")

        patch_triton_configs.main()

        captured = capsys.readouterr()
        assert "No triton_name/triton_kind" in captured.out

    def test_config_missing_prints_warn_continues(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        from ai.gateway import patch_triton_configs

        (tmp_path / "models.yml").write_text("""
models:
  - name: m1
    triton_name: nonexistent_model
    triton_kind: KIND_GPU
""")
        repo = tmp_path / "repo"
        repo.mkdir()
        monkeypatch.setattr(patch_triton_configs, "MODELS_YAML", tmp_path / "models.yml")
        monkeypatch.setattr(patch_triton_configs, "REPO", repo)

        patch_triton_configs.main()

        captured = capsys.readouterr()
        assert "WARN" in captured.err
        assert "nonexistent_model" in captured.err

    def test_patches_config_when_out_of_sync(self, tmp_path: Path, monkeypatch) -> None:
        from ai.gateway import patch_triton_configs

        (tmp_path / "models.yml").write_text("""
models:
  - name: m1
    triton_name: test_model
    triton_kind: KIND_GPU
""")
        repo = tmp_path / "repo"
        (repo / "test_model").mkdir(parents=True)
        (repo / "test_model" / "config.pbtxt").write_text("""
name: "test_model"
instance_group [
  {
    count: 2
    kind: KIND_CPU
  }
]
""")
        monkeypatch.setattr(patch_triton_configs, "MODELS_YAML", tmp_path / "models.yml")
        monkeypatch.setattr(patch_triton_configs, "REPO", repo)

        patch_triton_configs.main()

        content = (repo / "test_model" / "config.pbtxt").read_text()
        assert "kind: KIND_GPU" in content
        assert "gpus: [ 0 ]" in content
        assert "count: 1" in content

    def test_verifies_when_already_in_sync(self, tmp_path: Path, monkeypatch, capsys) -> None:
        from ai.gateway import patch_triton_configs

        (tmp_path / "models.yml").write_text("""
models:
  - name: m1
    triton_name: test_model
    triton_kind: KIND_GPU
""")
        repo = tmp_path / "repo"
        (repo / "test_model").mkdir(parents=True)
        original = """
name: "test_model"
instance_group [ { count: 1
  kind: KIND_GPU
  gpus: [ 0 ]
} ]
"""
        (repo / "test_model" / "config.pbtxt").write_text(original)
        monkeypatch.setattr(patch_triton_configs, "MODELS_YAML", tmp_path / "models.yml")
        monkeypatch.setattr(patch_triton_configs, "REPO", repo)

        patch_triton_configs.main()

        assert (repo / "test_model" / "config.pbtxt").read_text() == original
        captured = capsys.readouterr()
        assert "verified" in captured.out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3] / "ai" / "triton" / "model_repository"


def _collected() -> list[tuple[str, str]]:
    """(triton_name, triton_kind) pairs the real catalogue yields."""
    from setup_lib.models_config import load_models_yaml

    from ai.gateway.patch_triton_configs import collect_triton_configs

    return collect_triton_configs(load_models_yaml())


class TestModelsYamlConsistency:
    """Validation tests for models.yml vs Triton model repository."""

    def test_every_triton_name_maps_to_a_shipped_config(self) -> None:
        """A catalogue row naming a Triton directory the repository does not
        ship is the residency trap this slice exists to close.

        This replaced an exempted loop: ``deliberately_retired = {"xclip_action"}``
        forgave a missing config for a name whose catalogue row has since been
        deleted (ruling 2's legacy-row deletion, and X-CLIP's own retirement), so
        the exemption had become a standing loophole — any future row pointing at
        a swept directory would be waved through by the same shape of argument
        ("it's just history"). R8 S3 rulings 2 and 4 removed both sides of that
        pair: rows for pruned models are DELETED from models.yml and their
        repository dirs are ``git rm``'d, so there is nothing left to excuse.
        ``collect_triton_configs`` is not filtered by ``enabled``, so a disabled
        keeper row still has to point at a real directory — which is correct:
        entrypoint.sh runs this patcher against every collected name.
        """
        pairs = _collected()
        # Non-vacuity: a collection that came back empty would pass the loop.
        assert len(pairs) >= 2, f"catalogue collected {pairs}"

        missing = [
            name
            for name, _kind in pairs
            if not (_repo_root() / name / "config.pbtxt").exists()
        ]
        assert not missing, f"catalogue names Triton dirs the repository does not ship: {missing}"

    def test_every_shipped_directory_is_claimed_by_the_catalogue(self) -> None:
        """The inverse direction, which is the half a forward loop cannot see.

        A directory on disk that no catalogue row claims is never instance-group
        patched by entrypoint.sh and is invisible to the model registry — it just
        gets scanned by Triton and served. That is the same drift class as the
        forward one, from the other side, and it is what an unpruned repository
        under a narrowed residency set looks like.
        """
        claimed = {name for name, _kind in _collected()}
        present = {p.name for p in _repo_root().iterdir() if p.is_dir()}
        assert present == claimed, (
            f"repository dirs {sorted(present)} != catalogue names {sorted(claimed)}"
        )
        assert len(present) >= 2, sorted(present)

    def test_all_triton_kinds_valid(self) -> None:
        from setup_lib.models_config import load_models_yaml

        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = load_models_yaml()
        pairs = collect_triton_configs(models)
        valid = {"KIND_GPU", "KIND_CPU"}

        for triton_name, triton_kind in pairs:
            assert triton_kind in valid, f"Invalid triton_kind={triton_kind} for {triton_name}"

    def test_no_duplicate_triton_names(self) -> None:
        from setup_lib.models_config import load_models_yaml

        from ai.gateway.patch_triton_configs import collect_triton_configs

        models = load_models_yaml()
        pairs = collect_triton_configs(models)
        names = [n for n, _ in pairs]
        assert len(names) == len(set(names)), f"Duplicate triton_name: {names}"

    def test_device_env_var_requires_device(self) -> None:
        from setup_lib.models_config import load_models_yaml

        models = load_models_yaml()
        for m in models:
            if m.get("device_env_var"):
                assert "device" in m, f"Model {m.get('name')} has device_env_var but no device"

    def test_triton_models_entries_complete(self) -> None:
        from setup_lib.models_config import load_models_yaml

        models = load_models_yaml()
        for m in models:
            for tm in m.get("triton_models", []):
                assert "triton_name" in tm, f"triton_models entry missing triton_name: {tm}"
                assert "triton_kind" in tm, f"triton_models entry missing triton_kind: {tm}"


class TestConfigRoundTrip:
    """Config.pbtxt ↔ models.yml consistency tests."""

    def test_round_trip_idempotent_for_every_collected_name(self) -> None:
        """For every catalogue name, its shipped config is already in the kind
        the catalogue declares.

        The ``if not cfg_path.exists(): pytest.skip(...)`` this replaced was the
        unit tier's only imperative skip, and it was load-bearing in the wrong
        direction: a missing config made the assertion VANISH rather than fail,
        which is exactly how a catalogue that names a swept Triton directory
        stays green. R8 S3 (rulings 2 + 4) deleted the rows and the directories
        that produced the skip, so the property can now be asserted absolutely —
        the absence of a config is a failure of the same pin that used to excuse
        it (``test_every_triton_name_maps_to_a_shipped_config``), and this loop
        runs over the full collection with no escape hatch.
        """
        from ai.gateway.patch_triton_configs import set_instance_group

        pairs = _collected()
        # Non-vacuity: the loop must actually iterate.
        assert len(pairs) >= 2, f"catalogue collected {pairs}"

        for triton_name, triton_kind in pairs:
            cfg_path = _repo_root() / triton_name / "config.pbtxt"
            # No skip: a name the catalogue declares MUST have its config.
            assert cfg_path.exists(), (
                f"{triton_name} is collected from models.yml but its repository "
                "directory has no config.pbtxt — entrypoint.sh would patch a "
                "directory that does not exist"
            )
            original = cfg_path.read_text()
            result = set_instance_group(original, triton_kind)
            assert result == original, f"Config {triton_name} not idempotent for {triton_kind}"
            # Round-trip in the other direction too: patching to the opposite
            # kind and back returns the original bytes, so the patcher is a
            # switch and not a one-way rewrite.
            other = "KIND_CPU" if triton_kind == "KIND_GPU" else "KIND_GPU"
            flipped = set_instance_group(original, other)
            assert flipped != original, f"{triton_name}: flipping {triton_kind} changed nothing"
            assert set_instance_group(flipped, triton_kind) == original, (
                f"{triton_name} did not round-trip back to its committed bytes"
            )

"""synthbench.generate.weights: pinned manifest, sha256 fetch, ComfyUI symlink farm."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from synthbench.generate import weights as w

REPO_ROOT = Path(__file__).resolve().parents[4]
P1_SLATE = REPO_ROOT / "synthbench" / "generate" / "manifests" / "p1-slate.json"
REV = "a" * 40
H3_REVISION = "4cc1d817b6184899b41293954329f576cb5ae86b"  # pragma: allowlist secret


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _wf(model: str, category: str, path: str, data: bytes, repo: str = "org/repo") -> w.WeightFile:
    return w.WeightFile(
        model=model,
        category=category,
        repo=repo,
        revision=REV,
        path=path,
        size=len(data),
        sha256=_sha(data),
    )


def _write_manifest(tmp_path: Path, rows: list[dict[str, object]], version: int = 1) -> Path:
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"schema_version": version, "files": rows}))
    return path


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "model": "m",
        "category": "vae",
        "repo": "org/r",
        "revision": REV,
        "path": "vae/x.safetensors",
        "size": 3,
        "sha256": _sha(b"abc"),
    }
    row.update(overrides)
    return row


class TestLoadManifest:
    def test_round_trips(self, tmp_path: Path) -> None:
        files = w.load_manifest(_write_manifest(tmp_path, [_row()]))
        assert files == [w.WeightFile(**_row())]  # type: ignore[arg-type]
        assert files[0].name == "x.safetensors"

    def test_the_committed_p1_slate_loads(self) -> None:
        files = w.load_manifest(P1_SLATE)
        assert len(files) == 37
        assert len(w.unique_by_sha(files)) == 34
        assert {f.model for f in files} == {
            "flux2-dev",
            "qwen-image-2.1",
            "hidream-i1-full",
            "z-image-turbo",
            "flux2-klein-4b",
            "ideogram-4",
            "ltx-2.5",
            "wan2.2-i2v",
            "minimax-h3",
        }

    def test_the_p1_slate_pins_the_minimax_h3_i2v_files(self) -> None:
        # Task 9: only the files the i2v graph loads (its template's Lightning LoRA is off).
        h3 = [f for f in w.load_manifest(P1_SLATE) if f.model == "minimax-h3"]
        assert {(f.category, f.name) for f in h3} == {
            ("diffusion_models", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
            ("text_encoders", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
            ("vae", "minimax_h3_video_vae_fp16.safetensors"),
            ("vae", "minimax_h3_audio_vae_fp32.safetensors"),
        }
        assert {(f.repo, f.revision) for f in h3} == {("Comfy-Org/MiniMax-H3", H3_REVISION)}
        assert all(f.path == f"{f.category}/{f.name}" for f in h3)

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("category", "checkpoints", "unknown category"),
            ("sha256", "abc", "sha256"),
            ("revision", "main", "revision"),
            ("size", 0, "size"),
        ],
    )
    def test_rejects_malformed_rows(
        self, tmp_path: Path, field: str, value: object, message: str
    ) -> None:
        with pytest.raises(w.ManifestError, match=message):
            w.load_manifest(_write_manifest(tmp_path, [_row(**{field: value})]))

    def test_rejects_an_unknown_schema_version(self, tmp_path: Path) -> None:
        with pytest.raises(w.ManifestError, match="schema_version"):
            w.load_manifest(_write_manifest(tmp_path, [_row()], version=2))


class TestLinkNames:
    def test_unique_names_stay_bare(self) -> None:
        a = _wf("m1", "vae", "vae/a.safetensors", b"a")
        assert w.link_names([a]) == {a: "a.safetensors"}

    def test_same_name_same_content_shares_the_bare_name(self) -> None:
        a = _wf("m1", "vae", "x/ae.safetensors", b"same")
        b = _wf("m2", "vae", "y/ae.safetensors", b"same", repo="org/other")
        assert set(w.link_names([a, b]).values()) == {"ae.safetensors"}

    def test_same_name_different_content_is_prefixed_by_model(self) -> None:
        a = _wf("m1", "vae", "vae/v.safetensors", b"one")
        b = _wf("m2", "vae", "vae/v.safetensors", b"two", repo="org/other")
        assert w.link_names([a, b]) == {a: "m1--v.safetensors", b: "m2--v.safetensors"}

    def test_the_p1_slate_prefixes_only_the_flux2_vaes(self) -> None:
        names = w.link_names(w.load_manifest(P1_SLATE))
        assert sorted(n for n in names.values() if "--" in n) == [
            "flux2-dev--flux2-vae.safetensors",
            "flux2-klein-4b--flux2-vae.safetensors",
            "ideogram-4--flux2-vae.safetensors",
        ]

    def test_no_two_p1_slate_files_share_a_link(self) -> None:
        # Rows that share a link share its content (ae, qwen_3_4b); nothing else collides.
        names = w.link_names(w.load_manifest(P1_SLATE))
        contents: dict[tuple[str, str], set[str]] = {}
        for f, name in names.items():
            contents.setdefault((f.category, name), set()).add(f.sha256)
        assert all(len(shas) == 1 for shas in contents.values())
        assert len(contents) == 35  # the farm's links: 34 unique files, ideogram-4 reuses one


class TestFetch:
    def test_downloads_each_unique_file_once_and_verifies_it(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "x/ae.safetensors", b"same")
        b = _wf("m2", "vae", "y/ae.safetensors", b"same", repo="org/other")
        calls: list[str] = []

        def download(f: w.WeightFile) -> Path:
            calls.append(f.repo)
            path = tmp_path / f.repo.replace("/", "_")
            path.write_bytes(b"same")
            return path

        local = w.fetch([a, b], download)
        assert calls == ["org/repo"]
        assert local == {a.sha256: tmp_path / "org_repo"}

    def test_a_checksum_mismatch_raises(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "vae/a.safetensors", b"expected")

        def download(_f: w.WeightFile) -> Path:
            path = tmp_path / "bad"
            path.write_bytes(b"tampered")
            return path

        with pytest.raises(w.ChecksumError, match=r"vae/a\.safetensors"):
            w.fetch([a], download)


class TestHfDownload:
    """Weights land in the HF cache under HF_HOME, never in ~/.cache on the root fs."""

    @pytest.fixture
    def downloads(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
        import huggingface_hub

        calls: list[tuple[str, str, str]] = []

        def fake(repo: str, path: str, *, revision: str) -> str:
            calls.append((repo, path, revision))
            return f"/export/models/hub/{path}"

        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake)
        return calls

    @pytest.mark.parametrize("hf_home", [None, ""], ids=["unset", "empty"])
    def test_refuses_without_hf_home(
        self,
        monkeypatch: pytest.MonkeyPatch,
        downloads: list[tuple[str, str, str]],
        hf_home: str | None,
    ) -> None:
        if hf_home is None:
            monkeypatch.delenv("HF_HOME", raising=False)
        else:
            monkeypatch.setenv("HF_HOME", hf_home)
        with pytest.raises(w.StorageError, match="HF_HOME=/export/models"):
            w.hf_download(_wf("m1", "vae", "vae/a.safetensors", b"a"))
        assert downloads == []

    def test_downloads_the_pinned_revision_under_hf_home(
        self, monkeypatch: pytest.MonkeyPatch, downloads: list[tuple[str, str, str]]
    ) -> None:
        monkeypatch.setenv("HF_HOME", "/export/models")
        path = w.hf_download(_wf("m1", "vae", "vae/a.safetensors", b"a"))
        assert downloads == [("org/repo", "vae/a.safetensors", REV)]
        assert path == Path("/export/models/hub/vae/a.safetensors")


class TestBuildFarm:
    def test_links_resolve_to_the_cached_files(self, tmp_path: Path) -> None:
        a = _wf("m1", "vae", "vae/v.safetensors", b"one")
        b = _wf("m2", "vae", "vae/v.safetensors", b"two", repo="org/other")
        cache_a, cache_b = tmp_path / "blob_a", tmp_path / "blob_b"
        cache_a.write_bytes(b"one")
        cache_b.write_bytes(b"two")
        farm = tmp_path / "farm"
        w.build_farm([a, b], {a.sha256: cache_a, b.sha256: cache_b}, farm)
        assert (farm / "vae" / "m1--v.safetensors").resolve() == cache_a.resolve()
        assert (farm / "vae" / "m2--v.safetensors").read_bytes() == b"two"

    def test_is_idempotent_and_repairs_a_wrong_link(self, tmp_path: Path) -> None:
        a = _wf("m1", "loras", "l/x.safetensors", b"x")
        right, wrong = tmp_path / "right", tmp_path / "wrong"
        right.write_bytes(b"x")
        wrong.write_bytes(b"?")
        farm = tmp_path / "farm"
        (farm / "loras").mkdir(parents=True)
        (farm / "loras" / "x.safetensors").symlink_to(wrong)
        first = w.build_farm([a], {a.sha256: right}, farm)
        second = w.build_farm([a], {a.sha256: right}, farm)
        assert first == second == [farm / "loras" / "x.safetensors"]
        assert (farm / "loras" / "x.safetensors").resolve() == right.resolve()


class TestExtraModelPaths:
    def test_lists_every_category_under_the_farm(self) -> None:
        text = w.extra_model_paths_yaml(Path("/export/models/comfyui"))
        assert text.startswith("synthbench:\n  base_path: /export/models/comfyui\n")
        for category in w.CATEGORIES:
            assert f"  {category}: {category}/\n" in text

    def test_the_committed_container_yaml_matches(self) -> None:
        committed = REPO_ROOT / "synthbench" / "generate" / "comfy" / "extra_model_paths.yaml"
        assert committed.read_text() == w.extra_model_paths_yaml(Path("/export/models/comfyui"))


class TestSyncCli:
    def test_sync_fetches_and_builds_the_farm(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path, [_row(), _row(repo="org/gated")])
        blob = tmp_path / "blob"
        blob.write_bytes(b"abc")
        farm = tmp_path / "farm"
        code = w.main(
            [
                "sync",
                "--manifest",
                str(manifest),
                "--farm-root",
                str(farm),
                "--skip-repo",
                "org/gated",
            ],
            download=lambda _f: blob,
        )
        assert code == 0
        assert (farm / "vae" / "x.safetensors").resolve() == blob.resolve()

    def test_skip_repo_keeps_the_full_manifest_link_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_path / "cache"
        cache.mkdir()

        def download(f: w.WeightFile) -> Path:
            path = cache / f.sha256  # blobs named by their manifest sha256
            path.touch()
            return path

        monkeypatch.setattr(w, "sha256_of", lambda path: path.name)
        farm = tmp_path / "farm"
        code = w.main(
            [
                "sync",
                "--manifest",
                str(P1_SLATE),
                "--farm-root",
                str(farm),
                "--skip-repo",
                "Comfy-Org/flux2-dev",
            ],
            download=download,
        )
        assert code == 0
        assert sorted(p.name for p in (farm / "vae").iterdir() if "flux2-vae" in p.name) == [
            "flux2-klein-4b--flux2-vae.safetensors",
            "ideogram-4--flux2-vae.safetensors",
        ]

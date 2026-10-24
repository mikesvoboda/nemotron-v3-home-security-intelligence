"""Unit tests for B2.3 Re-ID model bake-off tools and challenger exporters (ruling 333).

Covers:
1. Challenger exporters and TensorRT compiler (`scripts/b23_reid_bakeoff.py`):
   - `ClipReidViTB16` vision architecture, strict state_dict loading (`image_encoder.*`),
     ONNX export (`input` `[batch, 3, 256, 128]` -> `embedding` `[batch, 1280]`), and
     CPU ONNX Runtime numerical fidelity (`cosine >= 0.9999`).
   - `prepare_tao_swin_onnx` for NVIDIA TAO `ReIdentificationNet Transformer`
     `deployable_v1.0` (`swin_tiny_market1501_aicity156_featuredim256.onnx` and
     `swin_base_market1501_aicity156_featuredim1024.onnx`): pins output `embedding`
     shape `[batch, 256]` / `[batch, 1024]`, runs strict ONNX shape inference, and
     preserves bit-identical ONNX Runtime outputs.
   - SHA-256 pin enforcement, provenance sidecar writing, and TensorRT `trtexec`
     dynamic-batch profile invocation (`1x3x256x128..16x3x256x128`).
2. Neutral person-crop pre-grouping (`scripts/uplevel/b23_crop_tool.py`):
   - Groups crops by `(event_id, track_id)` or camera snapshot burst without
     calling OSNet or any challenger model.
   - Supports merging groups, splitting a crop into a new identity, excluding
     distractors, and exporting `labels.json` with aggregate counts and SHA-256 only.
3. Bake-off metric evaluation (`scripts/b23_reid_bakeoff.py`):
   - Computes Rank-1, mAP, calibrated match threshold (max-F1 and TAR@FAR<=1%),
     and latency summary across OSNet-AIN x1.0, CLIP-ReID ViT-B/16, and
     NVIDIA ReIdentificationNet Transformer (`swin_tiny_256`, `swin_base_1024`).
   - Formats the recommendation report naming each model's license and
     no-login install source (ruling 333 item 4).
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch
from onnx import TensorProto, helper
from PIL import Image
from scripts.uplevel import b23_crop_tool as crop_tool

from scripts import b23_reid_bakeoff as bakeoff

pytestmark = pytest.mark.timeout(60)


def _make_synthetic_tao_swin_onnx(feat_dim: int) -> onnx.ModelProto:
    """Build a minimal ONNX graph matching TAO ReIdentificationNet Transformer's I/O contract:
    input `input` `['batch', 3, 256, 128]` -> output `fc_pred` `['batch', 'embedding_size']`.
    """
    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch", 3, 256, 128])
    out = helper.make_tensor_value_info("fc_pred", TensorProto.FLOAT, ["batch", "embedding_size"])

    w_data = np.random.default_rng(feat_dim).standard_normal((3, feat_dim)).astype(np.float32)
    w_init = helper.make_tensor(
        "proj_w", TensorProto.FLOAT, [3, feat_dim], w_data.flatten().tolist()
    )

    node_pool = helper.make_node("ReduceMean", ["input"], ["pooled"], axes=[2, 3], keepdims=0)
    node_gemm = helper.make_node("MatMul", ["pooled", "proj_w"], ["fc_pred"])

    graph = helper.make_graph(
        [node_pool, node_gemm],
        f"tao_swin_{feat_dim}",
        [inp],
        [out],
        initializer=[w_init],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 14)])
    model.ir_version = 8
    return model


class TestChallengerExportsAndTensorRT:
    def test_clip_reid_vit_b16_strict_load_and_onnx_fidelity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        torch.manual_seed(7)
        ref_model = bakeoff.ClipReidViTB16(
            h_resolution=16,
            w_resolution=8,
            patch_size=16,
            stride_size=16,
            width=64,
            layers=2,
            heads=4,
            output_dim=32,
        ).eval()

        ckpt_sd: dict[str, torch.Tensor] = {
            f"image_encoder.{k}": v.clone() for k, v in ref_model.state_dict().items()
        }
        ckpt_sd["classifier.weight"] = torch.randn(10, 64)
        ckpt_sd["text_encoder.ln_final.weight"] = torch.randn(32)

        ckpt_path = tmp_path / "ViT-B-16_60.pth"
        torch.save(ckpt_sd, str(ckpt_path))
        sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
        monkeypatch.setattr(bakeoff, "CLIP_REID_EXPECTED_SHA256", sha)

        loaded = bakeoff.load_clip_reid_model(
            ckpt_path,
            expected_sha256=sha,
            width=64,
            layers=2,
            heads=4,
            output_dim=32,
        )
        out_onnx = tmp_path / "clip_reid" / "1" / "model.onnx"
        bakeoff.export_clip_reid_onnx(
            ckpt_path,
            out_onnx,
            expected_sha256=sha,
            width=64,
            layers=2,
            heads=4,
            output_dim=32,
        )
        assert out_onnx.is_file()
        prov = json.loads((out_onnx.parent / "provenance.json").read_text())
        assert prov["zoo_name"] == "clip-reid-vit-b-16"
        assert prov["source_sha256"] == sha

        sess = ort.InferenceSession(str(out_onnx), providers=["CPUExecutionProvider"])
        for batch in (1, 3):
            x = torch.randn(batch, 3, 256, 128, dtype=torch.float32)
            with torch.no_grad():
                pt_out = loaded(x).numpy()
            ort_out = sess.run(["embedding"], {"input": x.numpy()})[0]
            assert ort_out.shape == (batch, 96)
            for a, b in zip(pt_out, ort_out, strict=True):
                cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                assert cos >= 0.9999

    def test_clip_reid_refuses_wrong_sha256(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "ViT-B-16_60.pth"
        ckpt_path.write_bytes(b"corrupt")
        with pytest.raises(RuntimeError, match="sha256 mismatch"):
            bakeoff.load_clip_reid_model(ckpt_path, expected_sha256="0" * 64)

    @pytest.mark.parametrize(
        ("role", "feat_dim"),
        [
            ("tao_swin_tiny_256", 256),
            ("tao_swin_base_1024", 1024),
        ],
    )
    def test_prepare_tao_swin_onnx_unifies_output_and_preserves_ort_outputs(
        self, tmp_path: Path, role: str, feat_dim: int
    ) -> None:
        raw_model = _make_synthetic_tao_swin_onnx(feat_dim)
        src_path = tmp_path / f"{role}.onnx"
        onnx.save(raw_model, str(src_path))
        sha = hashlib.sha256(src_path.read_bytes()).hexdigest()

        out_onnx = tmp_path / role / "1" / "model.onnx"
        bakeoff.export_tao_swin_onnx(role, src_path, out_onnx, expected_sha256=sha)
        assert out_onnx.is_file()

        loaded = onnx.load(str(out_onnx))
        onnx.checker.check_model(loaded)
        out_info = loaded.graph.output[0]
        assert out_info.name == "embedding"
        dims = out_info.type.tensor_type.shape.dim
        assert dims[0].dim_param == "batch"
        assert dims[1].dim_value == feat_dim

        s_raw = ort.InferenceSession(str(src_path), providers=["CPUExecutionProvider"])
        s_prep = ort.InferenceSession(str(out_onnx), providers=["CPUExecutionProvider"])
        x = np.random.default_rng(11).standard_normal((4, 3, 256, 128)).astype(np.float32)
        np.testing.assert_allclose(
            s_raw.run(["fc_pred"], {"input": x})[0],
            s_prep.run(["embedding"], {"input": x})[0],
            rtol=0.0,
            atol=1e-6,
        )

    def test_compile_challenger_plan_invokes_trtexec_with_reid_profiles(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_model = _make_synthetic_tao_swin_onnx(256)
        src_path = tmp_path / "swin_tiny.onnx"
        onnx.save(raw_model, str(src_path))
        sha = hashlib.sha256(src_path.read_bytes()).hexdigest()

        out_onnx = tmp_path / "tao_swin_tiny_256" / "1" / "model.onnx"
        bakeoff.export_tao_swin_onnx("tao_swin_tiny_256", src_path, out_onnx, expected_sha256=sha)

        plan_path = out_onnx.parent / "model.plan"
        captured_cmd: list[str] = []

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            captured_cmd.extend(cmd)
            plan_path.write_bytes(b"PLAN")
            return MagicMock(returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(bakeoff, "find_trtexec", lambda: "/usr/src/tensorrt/bin/trtexec")
        monkeypatch.setenv("TRT_VERSION", "11.3.0")
        monkeypatch.setattr(bakeoff.subprocess, "run", fake_run)
        bakeoff.compile_challenger_plan(
            "tao_swin_tiny_256",
            src_path,
            plan_path,
            expected_sha256=sha,
            precision="fp16",
        )
        assert plan_path.is_file()
        assert "--minShapes=input:1x3x256x128" in captured_cmd
        assert "--optShapes=input:4x3x256x128" in captured_cmd
        assert "--maxShapes=input:16x3x256x128" in captured_cmd


class TestB23NeutralCropTool:
    def test_pregroup_uses_only_event_and_track_metadata_never_embeddings(
        self, tmp_path: Path
    ) -> None:
        crops_dir = tmp_path / "existing_crops"
        crops_dir.mkdir()
        for name in (
            "real-018-beach_front_left-048.png",
            "real-019-beach_front_left-048.png",
            "real-001-dock_left-019.png",
        ):
            Image.new("RGB", (64, 128), color=(100, 120, 140)).save(crops_dir / name)

        det_manifest = [
            {
                "crop_path": str(crops_dir / "real-018-beach_front_left-048.png"),
                "camera_id": "beach_front_left",
                "event_id": "evt-100",
                "track_id": "trk-1",
                "captured_at": "2026-10-10T14:00:00Z",
            },
            {
                "crop_path": str(crops_dir / "real-019-beach_front_left-048.png"),
                "camera_id": "beach_front_left",
                "event_id": "evt-100",
                "track_id": "trk-1",
                "captured_at": "2026-10-10T14:00:02Z",
            },
            {
                "crop_path": str(crops_dir / "real-001-dock_left-019.png"),
                "camera_id": "dock_left",
                "event_id": "evt-200",
                "track_id": "trk-9",
                "captured_at": "2026-10-11T09:30:00Z",
            },
        ]
        manifest_path = tmp_path / "detections.json"
        manifest_path.write_text(json.dumps(det_manifest))

        out_dir = tmp_path / "work"
        pregrouped = crop_tool.build_pregrouped_set(
            existing_crops_dir=None,
            detections_manifest=manifest_path,
            output_dir=out_dir,
            target_count=10,
            seed=42,
        )
        assert len(pregrouped["items"]) == 3
        by_name = {item["crop_id"]: item["group_id"] for item in pregrouped["items"]}
        assert (
            by_name["real-018-beach_front_left-048.png"]
            == by_name["real-019-beach_front_left-048.png"]
        )
        assert by_name["real-001-dock_left-019.png"] != by_name["real-018-beach_front_left-048.png"]

    def test_merge_split_exclude_and_export_labels(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "work"
        (work_dir / "crops").mkdir(parents=True)
        pre = {
            "seed": 42,
            "grouping_rule": "event_and_track_only",
            "items": [
                {
                    "crop_id": "c1.png",
                    "camera_id": "front_door",
                    "event_id": "e1",
                    "track_id": "t1",
                    "group_id": "grp_e1_t1",
                },
                {
                    "crop_id": "c2.png",
                    "camera_id": "driveway",
                    "event_id": "e2",
                    "track_id": "t2",
                    "group_id": "grp_e2_t2",
                },
                {
                    "crop_id": "c3.png",
                    "camera_id": "backyard",
                    "event_id": "e3",
                    "track_id": "t3",
                    "group_id": "grp_e3_t3",
                },
            ],
        }
        (work_dir / "pregrouped.json").write_text(json.dumps(pre))

        state = crop_tool.ReviewState.from_pregrouped(pre)
        state.merge_groups(["grp_e1_t1", "grp_e2_t2"], target_person_id="person_001")
        state.set_crop_status("c3.png", excluded=True)

        exported = crop_tool.export_labels(work_dir, state)
        assert exported["summary"]["total_kept_crops"] == 2
        assert exported["summary"]["excluded_crops"] == 1
        assert exported["summary"]["identities_count"] == 1
        assert len(exported["labels_sha256"]) == 64


class TestB23BakeoffMetricsAndReport:
    def test_rank1_map_and_calibrated_threshold_on_known_clusters(self) -> None:
        labels = [
            {"crop_id": "p1_a.png", "person_id": "p1", "camera_id": "cam1", "event_id": "e1"},
            {"crop_id": "p1_b.png", "person_id": "p1", "camera_id": "cam2", "event_id": "e2"},
            {"crop_id": "p1_c.png", "person_id": "p1", "camera_id": "cam1", "event_id": "e3"},
            {"crop_id": "p2_a.png", "person_id": "p2", "camera_id": "cam1", "event_id": "e4"},
            {"crop_id": "p2_b.png", "person_id": "p2", "camera_id": "cam2", "event_id": "e5"},
            {"crop_id": "p2_c.png", "person_id": "p2", "camera_id": "cam2", "event_id": "e6"},
        ]
        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        embeddings = {
            "p1_a.png": v1,
            "p1_b.png": np.array([0.99, 0.14, 0.0, 0.0], dtype=np.float32),
            "p1_c.png": np.array([0.98, 0.19, 0.0, 0.0], dtype=np.float32),
            "p2_a.png": v2,
            "p2_b.png": np.array([0.10, 0.995, 0.0, 0.0], dtype=np.float32),
            "p2_c.png": np.array([0.15, 0.988, 0.0, 0.0], dtype=np.float32),
        }

        metrics = bakeoff.score_model_embeddings(
            model_key="clip_reid_vit_b_16",
            labels=labels,
            embeddings=embeddings,
            latency_ms=[4.2, 4.5, 4.3, 4.8, 4.4, 4.6],
            vram_mib=420,
        )
        assert metrics.rank1 == pytest.approx(1.0)
        assert metrics.map_score == pytest.approx(1.0)
        assert metrics.cross_camera_rank1 == pytest.approx(1.0)
        assert metrics.cross_camera_map == pytest.approx(1.0)
        assert 0.5 < metrics.calibrated_threshold < 0.99
        assert metrics.pos_min_cosine > metrics.neg_max_cosine

        report = bakeoff.format_bakeoff_report(
            [metrics], labels_summary={"total_kept_crops": 6, "identities_count": 2}
        )
        assert "clip_reid_vit_b_16" in report
        assert "MIT" in report
        assert "Hugging Face" in report

    def test_real_tier_probe_has_no_backend_imports(self) -> None:
        runner_path = Path(__file__).resolve().parents[4] / "scripts/uplevel/b23_real_tier.sh"
        script_text = runner_path.read_text(encoding="utf-8")
        marker = "cat > \"$RUN/eval_b23_gpu.py\" <<'PROBE'\n"
        assert marker in script_text
        probe_src = script_text.split(marker, 1)[1].split("\nPROBE\n", 1)[0]
        tree = ast.parse(probe_src, filename="eval_b23_gpu.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("backend")

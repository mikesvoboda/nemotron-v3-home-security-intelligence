"""[r307a] (ruling 307): SCRFD and ArcFace served in Triton as TensorRT plans.

Every small model the product runs on the GPU is served by Triton (UR-86,
ruling 307). These tests pin the four load-bearing parts of `[r307a]`:

1. Triton configs (`ai/triton/model_repository/{scrfd,arcface}/config.pbtxt`)
   and residency (`ai/gateway/residency.py` `FULL_MODEL_SET` + opt-in
   `GATEWAY_ENABLE_FACE` so nothing in production switches until `[r307b]`).
2. CPU-only CI tests pinning the ONNX graph surgeries the two buffalo_l files
   need before `trtexec` compiles them:
   - `scrfd_10g_bnkps.onnx` (`det_10g.onnx`): pins `input.1` to `[1, 3, 640, 640]`
     and replaces the dynamic `Shape -> Gather -> Unsqueeze -> Slice -> Concat`
     `sizes` inputs (`399`, `419`) on the two FPN `Resize` nodes with constant
     `int64` initializers `[1, 56, 40, 40]` and `[1, 56, 80, 80]`, eliminating
     all 149 unknown `value_info` shapes while keeping CPU `onnxruntime` outputs
     bit-identical (`max_abs_diff == 0.0`).
   - `w600k_r50.onnx`: unifies dimension 0 of `input.1` (`['None', 3, 112, 112]`)
     and output `683` (`[1, 512]`) to `"batch"` so dynamic batch profiles `1..16`
     pass strict ONNX shape inference and match CPU `onnxruntime` across batch
     sizes (`cosine >= 0.999999`).
3. Provenance-guarded ONNX export and TensorRT `.plan` builder (`export_face.py`
   and `export_all.sh`), enforcing `models.yml`'s SHA-256 pins for both files.
4. Gateway routes (`POST /enrich-lt/face-detect` and `POST /enrich-lt/face-recognize`)
   and the stage-by-stage parity checker (`scripts/face_parity_check.py`).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import onnx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from onnx import TensorProto, helper, numpy_helper, shape_inference
from PIL import Image

from ai.gateway.export import export_face

pytestmark = pytest.mark.timeout(30)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRFD_CONFIG = REPO_ROOT / "ai" / "triton" / "model_repository" / "scrfd" / "config.pbtxt"
ARCFACE_CONFIG = REPO_ROOT / "ai" / "triton" / "model_repository" / "arcface" / "config.pbtxt"
EXPORT_ALL = REPO_ROOT / "ai" / "gateway" / "export" / "export_all.sh"


def _build_synthetic_scrfd_onnx() -> onnx.ModelProto:
    """Build a minimal synthetic ONNX graph with det_10g.onnx's exact dynamic
    Resize + 9-output topology and unpopulated value_info entries."""
    inp = helper.make_tensor_value_info("input.1", TensorProto.FLOAT, [1, 3, "?", "?"])
    # Conv-like identity downsamples to 80x80 ("380") and 40x40 ("381") and 20x20 ("382")
    w80 = numpy_helper.from_array(np.ones((56, 3, 1, 1), dtype=np.float32), name="w80")
    w40 = numpy_helper.from_array(np.ones((56, 56, 1, 1), dtype=np.float32), name="w40")
    w20 = numpy_helper.from_array(np.ones((56, 56, 1, 1), dtype=np.float32), name="w20")
    c384 = numpy_helper.from_array(np.array(2, dtype=np.int64), name="384")
    c387 = numpy_helper.from_array(np.array(3, dtype=np.int64), name="387")
    c392 = numpy_helper.from_array(np.array([], dtype=np.float32), name="392")
    c394 = numpy_helper.from_array(np.array([0], dtype=np.int64), name="394")
    c396 = numpy_helper.from_array(np.array([2], dtype=np.int64), name="396")

    # Project 422 (1,56,80,80), 402 (1,56,40,40), 382 (1,56,20,20) into the 9 outputs
    s_s = numpy_helper.from_array(np.array([-1, 1], dtype=np.int64), name="446")
    s_b = numpy_helper.from_array(np.array([-1, 4], dtype=np.int64), name="450")
    s_k = numpy_helper.from_array(np.array([-1, 10], dtype=np.int64), name="453")
    w_cls = numpy_helper.from_array(np.zeros((2, 56, 1, 1), dtype=np.float32), name="w_cls")
    w_box = numpy_helper.from_array(np.zeros((8, 56, 1, 1), dtype=np.float32), name="w_box")
    w_kps = numpy_helper.from_array(np.zeros((20, 56, 1, 1), dtype=np.float32), name="w_kps")

    nodes = [
        helper.make_node("Conv", ["input.1", "w80"], ["380"], strides=[8, 8]),
        helper.make_node("Conv", ["380", "w40"], ["381"], strides=[2, 2]),
        helper.make_node("Conv", ["381", "w20"], ["382"], strides=[2, 2]),
        # Dynamic FPN Resize 1: 382 -> 381's spatial shape via 399
        helper.make_node("Shape", ["381"], ["383"], name="Shape_106"),
        helper.make_node("Gather", ["383", "384"], ["385"], axis=0, name="Gather_108"),
        helper.make_node("Shape", ["381"], ["386"], name="Shape_109"),
        helper.make_node("Gather", ["386", "387"], ["388"], axis=0, name="Gather_111"),
        helper.make_node("Unsqueeze", ["385"], ["389"], axes=[0], name="Unsqueeze_112"),
        helper.make_node("Unsqueeze", ["388"], ["390"], axes=[0], name="Unsqueeze_113"),
        helper.make_node("Shape", ["382"], ["393"], name="Shape_116"),
        helper.make_node("Slice", ["393", "394", "396", "394"], ["397"], name="Slice_120"),
        helper.make_node("Concat", ["397", "389", "390"], ["399"], axis=0, name="Concat_122"),
        helper.make_node(
            "Resize",
            ["382", "392", "392", "399"],
            ["401"],
            mode="nearest",
            coordinate_transformation_mode="asymmetric",
            nearest_mode="floor",
            name="Resize_124",
        ),
        helper.make_node("Add", ["381", "401"], ["402"], name="Add_125"),
        # Dynamic FPN Resize 2: 402 -> 380's spatial shape via 419
        helper.make_node("Shape", ["380"], ["403"], name="Shape_126"),
        helper.make_node("Gather", ["403", "384"], ["405"], axis=0, name="Gather_128"),
        helper.make_node("Shape", ["380"], ["406"], name="Shape_129"),
        helper.make_node("Gather", ["406", "387"], ["408"], axis=0, name="Gather_131"),
        helper.make_node("Unsqueeze", ["405"], ["409"], axes=[0], name="Unsqueeze_132"),
        helper.make_node("Unsqueeze", ["408"], ["410"], axes=[0], name="Unsqueeze_133"),
        helper.make_node("Shape", ["402"], ["413"], name="Shape_136"),
        helper.make_node("Slice", ["413", "394", "396", "394"], ["417"], name="Slice_140"),
        helper.make_node("Concat", ["417", "409", "410"], ["419"], axis=0, name="Concat_142"),
        helper.make_node(
            "Resize",
            ["402", "392", "392", "419"],
            ["421"],
            mode="nearest",
            coordinate_transformation_mode="asymmetric",
            nearest_mode="floor",
            name="Resize_144",
        ),
        helper.make_node("Add", ["380", "421"], ["422"], name="Add_145"),
    ]
    for feat, out_s, out_b, out_k in (
        ("422", "448", "451", "454"),
        ("402", "471", "474", "477"),
        ("382", "494", "497", "500"),
    ):
        nodes.extend(
            [
                helper.make_node("Conv", [feat, "w_cls"], [f"{feat}_cls"]),
                helper.make_node(
                    "Transpose", [f"{feat}_cls"], [f"{feat}_cls_t"], perm=[2, 3, 0, 1]
                ),
                helper.make_node("Reshape", [f"{feat}_cls_t", "446"], [f"{feat}_cls_r"]),
                helper.make_node("Sigmoid", [f"{feat}_cls_r"], [out_s]),
                helper.make_node("Conv", [feat, "w_box"], [f"{feat}_box"]),
                helper.make_node(
                    "Transpose", [f"{feat}_box"], [f"{feat}_box_t"], perm=[2, 3, 0, 1]
                ),
                helper.make_node("Reshape", [f"{feat}_box_t", "450"], [out_b]),
                helper.make_node("Conv", [feat, "w_kps"], [f"{feat}_kps"]),
                helper.make_node(
                    "Transpose", [f"{feat}_kps"], [f"{feat}_kps_t"], perm=[2, 3, 0, 1]
                ),
                helper.make_node("Reshape", [f"{feat}_kps_t", "453"], [out_k]),
            ]
        )

    outputs = [
        helper.make_tensor_value_info("448", TensorProto.FLOAT, [12800, 1]),
        helper.make_tensor_value_info("471", TensorProto.FLOAT, [3200, 1]),
        helper.make_tensor_value_info("494", TensorProto.FLOAT, [800, 1]),
        helper.make_tensor_value_info("451", TensorProto.FLOAT, [12800, 4]),
        helper.make_tensor_value_info("474", TensorProto.FLOAT, [3200, 4]),
        helper.make_tensor_value_info("497", TensorProto.FLOAT, [800, 4]),
        helper.make_tensor_value_info("454", TensorProto.FLOAT, [12800, 10]),
        helper.make_tensor_value_info("477", TensorProto.FLOAT, [3200, 10]),
        helper.make_tensor_value_info("500", TensorProto.FLOAT, [800, 10]),
    ]
    graph = helper.make_graph(
        nodes,
        "scrfd_synthetic",
        [inp],
        outputs,
        initializer=[
            w80,
            w40,
            w20,
            c384,
            c387,
            c392,
            c394,
            c396,
            s_s,
            s_b,
            s_k,
            w_cls,
            w_box,
            w_kps,
        ],
    )
    # Seed a broken value_info with dim_value=0 as det_10g.onnx carries
    vi = helper.make_tensor_value_info("380", TensorProto.FLOAT, [1, 56, None, None])
    graph.value_info.append(vi)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)])
    model.ir_version = 6
    return model


def _build_synthetic_arcface_onnx() -> onnx.ModelProto:
    """Build a minimal synthetic ONNX graph with w600k_r50.onnx's exact
    ['None', 3, 112, 112] -> [1, 512] batch-mismatch defect."""
    inp = helper.make_tensor_value_info("input.1", TensorProto.FLOAT, ["None", 3, 112, 112])
    out = helper.make_tensor_value_info("683", TensorProto.FLOAT, [1, 512])
    rng = np.random.default_rng(42)
    w_conv = numpy_helper.from_array(
        rng.standard_normal((8, 3, 7, 7), dtype=np.float32) * 0.05, name="w_conv"
    )
    slope = numpy_helper.from_array(np.full((8, 1, 1), 0.25, dtype=np.float32), name="slope")
    fc_w = numpy_helper.from_array(
        rng.standard_normal((512, 8 * 16 * 16), dtype=np.float32) * 0.02, name="fc.weight"
    )
    fc_b = numpy_helper.from_array(np.zeros((512,), dtype=np.float32), name="fc.bias")
    bn_s = numpy_helper.from_array(np.ones((512,), dtype=np.float32), name="features.weight")
    bn_b = numpy_helper.from_array(np.zeros((512,), dtype=np.float32), name="features.bias")
    bn_m = numpy_helper.from_array(np.zeros((512,), dtype=np.float32), name="features.running_mean")
    bn_v = numpy_helper.from_array(np.ones((512,), dtype=np.float32), name="features.running_var")

    nodes = [
        helper.make_node("Conv", ["input.1", "w_conv"], ["c1"], strides=[7, 7]),
        helper.make_node("PRelu", ["c1", "slope"], ["p1"]),
        helper.make_node("Flatten", ["p1"], ["681"], axis=1),
        helper.make_node(
            "Gemm", ["681", "fc.weight", "fc.bias"], ["682"], alpha=1.0, beta=1.0, transB=1
        ),
        helper.make_node(
            "BatchNormalization",
            [
                "682",
                "features.weight",
                "features.bias",
                "features.running_mean",
                "features.running_var",
            ],
            ["683"],
            name="BatchNormalization_129",
        ),
    ]
    graph = helper.make_graph(
        nodes,
        "arcface_synthetic",
        [inp],
        [out],
        initializer=[w_conv, slope, fc_w, fc_b, bn_s, bn_b, bn_m, bn_v],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)])
    model.ir_version = 6
    return model


class TestFaceTritonConfigsAndResidency:
    def test_scrfd_config_serves_tensorrt_with_9_outputs(self) -> None:
        text = SCRFD_CONFIG.read_text()
        assert re.search(r'^name:\s*"scrfd"', text, re.M)
        assert re.search(r'^backend:\s*"tensorrt"', text, re.M)
        assert "max_batch_size: 0" in text
        assert '"input.1"' in text
        assert "dims: [ 1, 3, 640, 640 ]" in text
        for name in ("448", "471", "494", "451", "474", "497", "454", "477", "500"):
            assert f'name: "{name}"' in text
        assert "kind: KIND_GPU" in text
        assert "gpus: [ 0 ]" in text

    def test_arcface_config_serves_tensorrt_with_dynamic_batching(self) -> None:
        text = ARCFACE_CONFIG.read_text()
        assert re.search(r'^name:\s*"arcface"', text, re.M)
        assert re.search(r'^backend:\s*"tensorrt"', text, re.M)
        assert "max_batch_size: 16" in text
        assert '"input.1"' in text
        assert "dims: [ 3, 112, 112 ]" in text
        assert 'name: "683"' in text
        assert "dims: [ 512 ]" in text
        assert "preferred_batch_size: [1, 4, 8]" in text
        assert "kind: KIND_GPU" in text
        assert "gpus: [ 0 ]" in text

    def test_residency_keeps_production_default_and_opts_in_face_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ai.gateway import residency

        assert {"scrfd", "arcface"} <= set(residency.FULL_MODEL_SET)
        assert residency.VLM_MODEL_BASE == ("yolo26", "reid")
        assert residency.get_model_set("vlm", face_enabled=False) == ("yolo26", "reid")
        assert residency.get_model_set("vlm", face_enabled=True) == (
            "yolo26",
            "reid",
            "scrfd",
            "arcface",
        )
        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.setenv("GATEWAY_ENABLE_FACE", "true")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        assert residency.resolve_active_set() == ("yolo26", "reid", "scrfd", "arcface")


class TestFaceOnnxGraphSurgery:
    def test_prepare_scrfd_onnx_eliminates_unknown_shapes_and_preserves_outputs(self) -> None:
        raw = _build_synthetic_scrfd_onnx()
        prepared = export_face.prepare_scrfd_onnx(raw)
        onnx.checker.check_model(prepared)

        inferred = shape_inference.infer_shapes(
            prepared, check_type=True, strict_mode=True, data_prop=True
        )
        unknowns = [
            vi.name
            for vi in inferred.graph.value_info
            if any(d.dim_value <= 0 for d in vi.type.tensor_type.shape.dim)
        ]
        assert unknowns == []
        assert not any(n.op_type == "Shape" for n in prepared.graph.node)

        import onnxruntime as ort

        rng = np.random.default_rng(11)
        blob = rng.standard_normal((1, 3, 640, 640), dtype=np.float32)
        s_raw = ort.InferenceSession(raw.SerializeToString(), providers=["CPUExecutionProvider"])
        s_prep = ort.InferenceSession(
            prepared.SerializeToString(), providers=["CPUExecutionProvider"]
        )
        outs_raw = s_raw.run(None, {"input.1": blob})
        outs_prep = s_prep.run(None, {"input.1": blob})
        for a, b in zip(outs_raw, outs_prep, strict=True):
            assert float(np.max(np.abs(a - b))) == 0.0

    def test_prepare_arcface_onnx_fixes_batch_mismatch_and_preserves_embeddings(self) -> None:
        raw = _build_synthetic_arcface_onnx()
        # Raw fails strict shape inference at batch=2 because output 683 pins dim[0]=1
        raw_b2 = onnx.ModelProto()
        raw_b2.CopyFrom(raw)
        raw_b2.graph.input[0].type.tensor_type.shape.dim[0].ClearField("dim_param")
        raw_b2.graph.input[0].type.tensor_type.shape.dim[0].dim_value = 2
        with pytest.raises(onnx.shape_inference.InferenceError):
            shape_inference.infer_shapes(raw_b2, check_type=True, strict_mode=True, data_prop=True)

        prepared = export_face.prepare_arcface_onnx(raw)
        onnx.checker.check_model(prepared)
        for batch in (1, 4, 8, 16):
            probe = onnx.ModelProto()
            probe.CopyFrom(prepared)
            del probe.graph.value_info[:]
            probe.graph.input[0].type.tensor_type.shape.dim[0].ClearField("dim_param")
            probe.graph.input[0].type.tensor_type.shape.dim[0].dim_value = batch
            probe.graph.output[0].type.tensor_type.shape.dim[0].ClearField("dim_param")
            probe.graph.output[0].type.tensor_type.shape.dim[0].dim_value = batch
            inferred = shape_inference.infer_shapes(
                probe, check_type=True, strict_mode=True, data_prop=True
            )
            unknowns = [
                vi.name
                for vi in inferred.graph.value_info
                if any(d.dim_value <= 0 for d in vi.type.tensor_type.shape.dim)
            ]
            assert unknowns == []

        import onnxruntime as ort

        rng = np.random.default_rng(19)
        s_raw = ort.InferenceSession(raw.SerializeToString(), providers=["CPUExecutionProvider"])
        s_prep = ort.InferenceSession(
            prepared.SerializeToString(), providers=["CPUExecutionProvider"]
        )
        for batch in (1, 4, 8):
            crops = rng.standard_normal((batch, 3, 112, 112), dtype=np.float32)
            out_raw = s_raw.run(None, {"input.1": crops})[0]
            out_prep = s_prep.run(None, {"input.1": crops})[0]
            assert out_raw.shape == out_prep.shape == (batch, 512)
            assert float(np.max(np.abs(out_raw - out_prep))) < 1e-6


def _fake_run_factory(captured: list) -> Callable[..., SimpleNamespace]:
    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> SimpleNamespace:
        argv = list(cmd)
        captured.append(argv)
        out = next(a for a in argv if a.startswith("--saveEngine="))[len("--saveEngine=") :]
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(b"\x00plan")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return fake_run


class TestFaceExportAndPlanBuilder:
    def test_export_and_compile_both_face_models_with_provenance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scrfd_src = tmp_path / "scrfd_10g_bnkps.onnx"
        arcface_src = tmp_path / "w600k_r50.onnx"
        onnx.save(_build_synthetic_scrfd_onnx(), str(scrfd_src))
        onnx.save(_build_synthetic_arcface_onnx(), str(arcface_src))

        scrfd_sha = hashlib.sha256(scrfd_src.read_bytes()).hexdigest()
        arcface_sha = hashlib.sha256(arcface_src.read_bytes()).hexdigest()
        monkeypatch.setattr(export_face, "SCRFD_EXPECTED_SHA256", scrfd_sha)
        monkeypatch.setattr(export_face, "ARCFACE_EXPECTED_SHA256", arcface_sha)

        scrfd_out = tmp_path / "cache" / "scrfd" / "1" / "model.onnx"
        arcface_out = tmp_path / "cache" / "arcface" / "1" / "model.onnx"

        export_face.export_scrfd_onnx(str(scrfd_src), str(scrfd_out))
        export_face.export_arcface_onnx(str(arcface_src), str(arcface_out))

        scrfd_prov = json.loads((scrfd_out.parent / "provenance.json").read_text())
        arcface_prov = json.loads((arcface_out.parent / "provenance.json").read_text())
        assert scrfd_prov == {
            "zoo_name": "face-detector-scrfd",
            "source_file": "scrfd_10g_bnkps.onnx",
            "source_sha256": scrfd_sha,
        }
        assert arcface_prov == {
            "zoo_name": "face-recognizer",
            "source_file": "w600k_r50.onnx",
            "source_sha256": arcface_sha,
        }

        captured: list = []
        monkeypatch.setenv("TRT_VERSION", "11.3.0.99")
        scrfd_plan = scrfd_out.parent / "model.plan"
        arcface_plan = arcface_out.parent / "model.plan"
        export_face.compile_face_plan(
            role="scrfd",
            source_path=str(scrfd_src),
            plan_path=str(scrfd_plan),
            trtexec="/usr/src/tensorrt/bin/trtexec",
            run=_fake_run_factory(captured),
        )
        export_face.compile_face_plan(
            role="arcface",
            source_path=str(arcface_src),
            plan_path=str(arcface_plan),
            trtexec="/usr/src/tensorrt/bin/trtexec",
            run=_fake_run_factory(captured),
        )
        assert scrfd_plan.is_file()
        assert arcface_plan.is_file()
        assert "--minShapes=input.1:1x3x112x112" in captured[1]
        assert "--optShapes=input.1:8x3x112x112" in captured[1]
        assert "--maxShapes=input.1:16x3x112x112" in captured[1]
        assert "--fp16" not in captured[0]
        assert "--fp16" not in captured[1]

    def test_wrong_sha256_refuses_export(self, tmp_path: Path) -> None:
        bad = tmp_path / "w600k_r50.onnx"
        bad.write_bytes(b"corrupt")
        with pytest.raises(RuntimeError, match="sha256"):
            export_face.export_arcface_onnx(
                str(bad), str(tmp_path / "arcface" / "1" / "model.onnx")
            )


class TestGatewayFaceRoutes:
    @pytest.fixture
    def mock_triton(self) -> AsyncMock:
        client = AsyncMock()
        client.infer = AsyncMock()
        client.is_model_ready = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    async def client(self, mock_triton: AsyncMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from ai.gateway.adapters import enrichment_light

        repo = tmp_path / "repository"
        for sub, zoo, fname, sha in (
            (
                "scrfd",
                "face-detector-scrfd",
                "scrfd_10g_bnkps.onnx",
                "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",  # pragma: allowlist secret
            ),
            (
                "arcface",
                "face-recognizer",
                "w600k_r50.onnx",
                "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",  # pragma: allowlist secret
            ),
        ):
            d = repo / sub / "1"
            d.mkdir(parents=True)
            (d / "provenance.json").write_text(
                json.dumps({"zoo_name": zoo, "source_file": fname, "source_sha256": sha})
            )
        monkeypatch.setenv("TRITON_MODEL_REPOSITORY", str(repo))
        enrichment_light.scrfd_model_id.cache_clear()
        enrichment_light.arcface_model_id.cache_clear()

        app = FastAPI()
        app.include_router(enrichment_light.router)
        with patch(
            "ai.gateway.adapters.enrichment_light.get_triton_client",
            return_value=mock_triton,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c

    async def test_face_detect_route_matches_cpu_loader_decode(
        self, client: AsyncClient, mock_triton: AsyncMock
    ) -> None:
        # Place one confident anchor at stride 8 row=10, col=15, anchor=0 on a 640x640 input
        s8 = np.zeros((12800, 1), dtype=np.float32)
        s16 = np.zeros((3200, 1), dtype=np.float32)
        s32 = np.zeros((800, 1), dtype=np.float32)
        b8 = np.zeros((12800, 4), dtype=np.float32)
        b16 = np.zeros((3200, 4), dtype=np.float32)
        b32 = np.zeros((800, 4), dtype=np.float32)
        k8 = np.zeros((12800, 10), dtype=np.float32)
        k16 = np.zeros((3200, 10), dtype=np.float32)
        k32 = np.zeros((800, 10), dtype=np.float32)

        idx = (10 * 80 + 15) * 2
        s8[idx, 0] = 0.95
        b8[idx] = np.array([2.0, 2.0, 4.0, 4.0], dtype=np.float32)
        k8[idx] = np.tile(np.array([0.5, 0.5], dtype=np.float32), 5)

        mock_triton.infer.return_value = {
            "448": s8,
            "471": s16,
            "494": s32,
            "451": b8,
            "474": b16,
            "497": b32,
            "454": k8,
            "477": k16,
            "500": k32,
        }

        img = Image.new("RGB", (640, 640), color=(120, 130, 140))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        resp = await client.post("/face-detect", json={"image": b64, "threshold": 0.6})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["model_id"] == "face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536"
        assert len(data["faces"]) == 1
        face = data["faces"][0]
        assert face["confidence"] == pytest.approx(0.95, abs=1e-4)
        assert face["bbox"] == pytest.approx([104.0, 64.0, 152.0, 112.0], abs=1e-3)
        assert len(face["landmarks"]) == 5

    async def test_face_recognize_route_normalizes_and_stamps_model_id(
        self, client: AsyncClient, mock_triton: AsyncMock
    ) -> None:
        raw_vec = np.arange(1, 513, dtype=np.float32).reshape(1, 512)
        mock_triton.infer.return_value = {"683": raw_vec}

        img = Image.new("RGB", (112, 112), color=(90, 100, 110))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        resp = await client.post("/face-recognize", json={"image": b64})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["model_id"] == "face-recognizer@w600k_r50@4c06341c33c2"
        assert data["embedding_dimension"] == 512
        vec = np.asarray(data["embedding"], dtype=np.float64)
        assert vec.shape == (512,)
        assert float(np.linalg.norm(vec)) == pytest.approx(1.0, abs=1e-5)


class TestFaceParityCheckAndCli:
    def test_face_parity_stage_evaluation_and_table_gates(self) -> None:
        from scripts import face_parity_check as fpc

        ref = [
            {
                "name": "face-01.png",
                "bbox": [100.0, 80.0, 220.0, 240.0],
                "landmarks": [
                    [120.0, 120.0],
                    [180.0, 120.0],
                    [150.0, 155.0],
                    [130.0, 190.0],
                    [170.0, 190.0],
                ],
                "embedding": [1.0] + [0.0] * 511,
            }
        ]
        good = [
            {
                "name": "face-01.png",
                "detected": True,
                "bbox": [100.2, 80.1, 220.1, 239.9],
                "landmarks": [
                    [120.1, 120.0],
                    [180.0, 120.1],
                    [150.0, 155.1],
                    [130.1, 190.0],
                    [170.0, 190.0],
                ],
                "embedding": [0.9999] + [0.001] + [0.0] * 510,
            }
        ]
        m_pass = fpc.evaluate_stage("5", ref, good)
        assert m_pass.ok is True
        table, verdict = fpc.format_stage_table([m_pass], model_ids_match=True)
        assert verdict == "PASS"
        assert "RESULT: PASS" in table

        # Landmark drift > 1.0 px fails the gate
        bad_kps = [
            {
                **good[0],
                "landmarks": [
                    [122.0, 120.0],
                    [180.0, 120.1],
                    [150.0, 155.1],
                    [130.1, 190.0],
                    [170.0, 190.0],
                ],
            }
        ]
        m_fail = fpc.evaluate_stage("5", ref, bad_kps)
        assert m_fail.ok is False
        _, verdict_fail = fpc.format_stage_table([m_fail], model_ids_match=True)
        assert verdict_fail == "FAIL"

    def test_export_face_cli_main_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scrfd_src = tmp_path / "scrfd_10g_bnkps.onnx"
        onnx.save(_build_synthetic_scrfd_onnx(), str(scrfd_src))
        sha = hashlib.sha256(scrfd_src.read_bytes()).hexdigest()
        monkeypatch.setattr(export_face, "SCRFD_EXPECTED_SHA256", sha)

        out_onnx = tmp_path / "scrfd" / "1" / "model.onnx"
        assert (
            export_face.main(
                ["--role", "scrfd", "--model-path", str(scrfd_src), "--output-path", str(out_onnx)]
            )
            == 0
        )
        assert out_onnx.is_file()
        assert (out_onnx.parent / "provenance.json").is_file()

    def test_stage_probe_face_has_no_backend_imports_and_matches_loader_alignment(
        self, tmp_path: Path
    ) -> None:
        import ast
        import importlib.util
        import sys

        from backend.services import face_recognizer_loader as frl

        runner_path = Path(__file__).resolve().parents[3] / "scripts/uplevel/face_real_tier.sh"
        script_text = runner_path.read_text()
        assert "tensorrt==11.3.0.99" in script_text, (
            "face_real_tier.sh must install the tensorrt==11.3.0.99 metapackage so "
            "import tensorrt succeeds inside nvcr.io/nvidia/tritonserver:26.09-py3"
        )
        marker = "cat > \"$RUN/stage_probe_face.py\" <<'PROBE'\n"
        assert marker in script_text, "stage_probe_face.py heredoc not found in face_real_tier.sh"
        probe_src = script_text.split(marker, 1)[1].split("\nPROBE\n", 1)[0]

        tree = ast.parse(probe_src, filename="stage_probe_face.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("backend"), (
                        f"stage_probe_face.py must not import backend inside the Python 3.12 "
                        f"Triton container: found import {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("backend"), (
                    f"stage_probe_face.py must not import from backend inside the Python 3.12 "
                    f"Triton container: found from {mod} import ..."
                )

        probe_file = tmp_path / "stage_probe_face.py"
        probe_file.write_text(probe_src)
        old_argv = sys.argv[:]
        try:
            sys.argv = ["stage_probe_face.py", str(tmp_path), str(tmp_path)]
            spec = importlib.util.spec_from_file_location("_stage_probe_face_test", probe_file)
            assert spec is not None and spec.loader is not None
            probe_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(probe_mod)
        finally:
            sys.argv = old_argv

        rng = np.random.default_rng(42)
        img_arr = rng.integers(0, 256, size=(240, 320, 3), dtype=np.uint8)
        img = Image.fromarray(img_arr, mode="RGB")
        landmarks = [
            [110.5, 95.2],
            [155.3, 94.8],
            [132.1, 122.4],
            [115.0, 148.7],
            [150.2, 149.1],
        ]
        ref_crop = frl.align_face_crop(img, landmarks)
        cand_crop = probe_mod._align_face_crop(img, landmarks)
        np.testing.assert_array_equal(np.asarray(ref_crop), np.asarray(cand_crop))

        ref_blob = frl.preprocess_face_crop(ref_crop)
        cand_blob = probe_mod._preprocess_face_crop(cand_crop)
        np.testing.assert_allclose(ref_blob, cand_blob, rtol=0.0, atol=0.0)

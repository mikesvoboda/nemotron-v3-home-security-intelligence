"""O2.4 (ruling 107): the gateway's `reid` serves through TensorRT, not CUDA EP.

Ruling 106 closed the ONNX Runtime CUDA path on the GB300 (`cudaErrorSymbolNotFound`
on Blackwell/aarch64, Triton `26.01-py3`); ruling 107 orders the replacement,
quoted: "Serve the gateway's `reid` through TensorRT, a plan built for the serving
GPU as `yolo26`'s is". These tests pin the load-bearing invariants of that swap:

- the shipped Triton config asks the TensorRT backend for `model.plan` while the
  tensor contract stays byte-for-byte what the adapter's `infer()` and
  `test_reid_path_parity.py` already speak — names `input`/`embedding`, dims
  [3,256,128]/[512], FP32, max_batch 16. A plan is a different file, not a
  different API;
- the plan is built FOR the serving GPU by a builder whose trtexec command
  carries the reid IO name and the batch profile (engines are GPU-architecture-
  specific — the warning in `copy_yolo26_engine.py`);
- provenance (B2.2, #6970) keeps vouching unchanged: `reid_model_id()` reads
  `repository/reid/1/provenance.json` and entrypoint.sh §0c links the whole
  version dir, so plan mode must LEAVE that record exactly where ONNX mode wrote
  it — and must REFUSE to build from an ONNX no record vouches for, or against a
  checkpoint whose bytes are not the recorded `source_sha256`.

On validating the plan itself: this repo's TensorRT precedent (`export/README.md`
's pipeline, `export_fashion_clip.py`) validates the ONNX against PyTorch with the
CPU execution provider — no GPU needed — then compiles to `.plan` WITHOUT
re-running inference on the engine; the plan is a deterministic compile of the
already-vouched graph. Neither this sandbox nor CI has a GPU, so re-validating the
engine numerically would be a mechanism no gate can run. Ruling 107 puts the
plan's numeric proof where it belongs — the owner's `reid_parity_check.py` run on
the GB300 (Done when) — so the export's job ends at: only compile a plan from a
checkpoint the provenance record vouches for, and never ship a plan the builder
failed to write.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.gateway.export import export_reid

# This module cold-imports torch through export_reid; the 5s tier default is
# borderline under xdist contention (test_export_reid.py's 60s precedent — a
# lighter module than that one, so 30s here, same declared-budget reasoning).
pytestmark = pytest.mark.timeout(30)

REPO_ROOT = Path(__file__).resolve().parents[3]
REID_CONFIG = REPO_ROOT / "ai" / "triton" / "model_repository" / "reid" / "config.pbtxt"
ENTRYPOINT = REPO_ROOT / "ai" / "gateway" / "entrypoint.sh"
EXPORT_ALL = REPO_ROOT / "ai" / "gateway" / "export" / "export_all.sh"


# ---------------------------------------------------------------------------
# The shipped Triton config: TensorRT backend, frozen tensor contract
# ---------------------------------------------------------------------------


class TestReidServesThroughTensorRT:
    @pytest.fixture(autouse=True)
    def _config(self) -> None:
        self.config = REID_CONFIG.read_text()

    def test_backend_is_tensorrt(self) -> None:
        """Ruling 107's scope line, read off the bytes Triton loads."""
        assert re.search(r'^backend:\s*"tensorrt"', self.config, re.M)
        assert not re.search(r'^backend:\s*"onnxruntime"', self.config, re.M)

    def test_tensor_contract_is_unchanged(self) -> None:
        """The adapter, the parity gate and the fake stack all speak THIS contract."""
        assert re.search(
            r'name:\s*"input"\s*\n\s*data_type:\s*TYPE_FP32\s*\n\s*dims:\s*\[\s*3,\s*256,\s*128\s*\]',
            self.config,
        )
        assert re.search(
            r'name:\s*"embedding"\s*\n\s*data_type:\s*TYPE_FP32\s*\n\s*dims:\s*\[\s*512\s*\]',
            self.config,
        )
        assert "max_batch_size: 16" in self.config
        assert "preferred_batch_size: [1, 4, 8]" in self.config
        assert "max_queue_delay_microseconds: 100000" in self.config

    def test_instance_group_stays_on_the_gpu(self) -> None:
        assert "kind: KIND_GPU" in self.config
        assert "gpus: [ 0 ]" in self.config
        # The rate limiter carries the GPU priority the residency review reads;
        # it belongs to the scheduling contract, not to the backend choice.
        assert "rate_limiter" in self.config

    def test_entrypoint_patcher_preserves_the_backend_line(self) -> None:
        """entrypoint.sh §0b rewrites instance_group from models.yml before
        Triton starts. The TensorRT switch must survive that rewrite — the
        patcher only ever touches kind/count/gpus, never `backend`."""
        from ai.gateway.patch_triton_configs import set_instance_group

        patched = set_instance_group(self.config, "KIND_GPU")
        assert re.search(r'^backend:\s*"tensorrt"', patched, re.M)
        assert "kind: KIND_GPU" in patched
        assert "gpus: [ 0 ]" in patched

    def test_entrypoint_links_the_version_dir_untouched(self) -> None:
        """§0c symlinks whatever version dir the cache holds and its header
        already names .plan — pin the model-agnostic shape so the plan drop-in
        needs no entrypoint edit."""
        entrypoint = ENTRYPOINT.read_text()
        assert 'cache_version="${model_dir}1"' in entrypoint
        assert ".plan" in entrypoint


# ---------------------------------------------------------------------------
# The builder: a plan built FOR the serving GPU
# ---------------------------------------------------------------------------


def _fake_run_factory(captured: list) -> Callable[..., SimpleNamespace]:
    """A stand-in subprocess.run that plays trtexec: records the argv and
    writes the --saveEngine file it was told to produce."""

    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> SimpleNamespace:
        argv = list(cmd)
        captured.append(argv)
        out = next(a for a in argv if a.startswith("--saveEngine="))[len("--saveEngine=") :]
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(b"\x00plan")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return fake_run


class TestPlanBuilder:
    def test_build_tensorrt_engine_exists(self) -> None:
        assert callable(getattr(export_reid, "build_tensorrt_engine", None))

    def test_trtexec_command_names_the_reid_io_and_batch_profile(self, tmp_path: Path) -> None:
        """min/opt/max profiles on the real input name, batch up to the config's
        max_batch 16 — the dynamic batching the config declares has to exist
        INSIDE the plan, or Triton refuses to load it."""
        captured: list = []
        onnx = tmp_path / "model.onnx"
        onnx.write_bytes(b"fake onnx")
        plan = tmp_path / "1" / "model.plan"
        export_reid.build_tensorrt_engine(
            str(onnx),
            str(plan),
            trtexec="/usr/src/tensorrt/bin/trtexec",
            run=_fake_run_factory(captured),
        )
        cmd = captured[0]
        assert cmd[0] == "/usr/src/tensorrt/bin/trtexec"
        assert any(a in (f"--onnx={onnx}", f"--onnx={onnx.resolve()}") for a in cmd)
        assert "--minShapes=input:1x3x256x128" in cmd
        assert "--optShapes=input:8x3x256x128" in cmd
        assert "--maxShapes=input:16x3x256x128" in cmd
        assert "--fp16" in cmd  # yolo26's shipped engine is fp16; so is this one by default
        assert plan.exists()

    def test_fp32_precision_omits_the_fp16_flag(self, tmp_path: Path) -> None:
        captured: list = []
        onnx = tmp_path / "model.onnx"
        onnx.write_bytes(b"fake onnx")
        plan = tmp_path / "model.plan"
        export_reid.build_tensorrt_engine(
            str(onnx),
            str(plan),
            precision="fp32",
            trtexec="/usr/bin/trtexec",
            run=_fake_run_factory(captured),
        )
        assert "--fp16" not in captured[0]

    def test_a_failed_trtexec_raises_and_leaves_no_plan(self, tmp_path: Path) -> None:
        def failing_run(cmd: list[str], *args: object, **kwargs: object) -> SimpleNamespace:
            # A real trtexec can leave a garbage partial file; the builder must
            # not let one survive as the version dir's model.
            out = next(a for a in cmd if a.startswith("--saveEngine="))[len("--saveEngine=") :]
            Path(out).write_bytes(b"garbage")
            return SimpleNamespace(returncode=1, stdout="builder err", stderr="ERR: unsupported op")

        onnx = tmp_path / "model.onnx"
        onnx.write_bytes(b"fake onnx")
        plan = tmp_path / "model.plan"
        with pytest.raises(RuntimeError):
            export_reid.build_tensorrt_engine(
                str(onnx), str(plan), trtexec="/usr/bin/trtexec", run=failing_run
            )
        assert not plan.exists()


# ---------------------------------------------------------------------------
# Plan mode in main(): provenance keeps vouching, validation is never skipped
# ---------------------------------------------------------------------------


class TestPlanModeKeepsProvenanceVouching:
    """`--output-path .../model.plan` builds the plan FROM the already-exported,
    already-vouched ONNX (the two-stage yolo26 idiom: phase 2 exports ONNX
    anywhere; the plan is baked on the serving GPU)."""

    @pytest.fixture
    def version_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "reid" / "1"
        d.mkdir(parents=True)
        (d / "model.onnx").write_bytes(b"onnx bytes")
        return d

    @staticmethod
    def _write_checkpoint(path: Path) -> Path:
        path.write_bytes(b"checkpoint bytes")
        return path

    @staticmethod
    def _write_record_for(onnx: Path, checkpoint: Path) -> None:
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        (onnx.parent / "provenance.json").write_text(
            json.dumps(
                {
                    "zoo_name": export_reid.OSNET_ZOO_NAME,
                    "source_file": checkpoint.name,
                    "source_sha256": digest,
                }
            )
        )

    def _argv(self, monkeypatch: pytest.MonkeyPatch, ckpt: Path, plan: Path) -> None:
        monkeypatch.setattr(
            "sys.argv",
            ["export_reid.py", "--model-path", str(ckpt), "--output-path", str(plan)],
        )

    def test_refuses_an_onnx_no_provenance_record_vouches_for(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#6970's precondition turned into a stop: export_all.sh skips an
        existing model.onnx, so a stale pre-B2.2 ONNX (no record beside it) must
        never seed a plan. The guard runs BEFORE the model is loaded."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        loads: list = []

        def no_load(path: str) -> None:
            loads.append(path)

        monkeypatch.setattr(export_reid, "load_pytorch_model", no_load)
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")
        assert export_reid.main() == 1
        assert loads == []
        assert not (version_dir / "model.plan").exists()

    def test_refuses_a_checkpoint_that_is_not_the_recorded_bytes(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plan may not ship labelled with weights that are not the ones the
        record — and therefore the ONNX — was made from."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        other = self._write_checkpoint(tmp_path / "different.pth")
        self._write_record_for(version_dir / "model.onnx", other)  # record names OTHER weights
        loads: list = []

        def no_load(path: str) -> None:
            loads.append(path)

        monkeypatch.setattr(export_reid, "load_pytorch_model", no_load)
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")
        assert export_reid.main() == 1
        assert loads == []
        assert not (version_dir / "model.plan").exists()

    def test_a_vouched_onnx_compiles_to_a_plan_and_keeps_the_record(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plan mode is a COMPILE step over the ONNX phase 2 already exported and
        already vouched: it compiles, it does not re-derive. So it must consume
        the existing model.onnx and leave both the ONNX (the rollback file) and
        the record untouched."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        self._write_record_for(version_dir / "model.onnx", ckpt)
        record_bytes = (version_dir / "provenance.json").read_bytes()

        builds: list = []

        def fake_build(onnx: str, plan: str, **kw: object) -> str:
            builds.append((onnx, plan))
            Path(plan).write_bytes(b"plan bytes")
            return plan

        monkeypatch.setattr(export_reid, "build_tensorrt_engine", fake_build)
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")

        assert export_reid.main() == 0
        assert builds == [(str(version_dir / "model.onnx"), str(version_dir / "model.plan"))]
        assert (version_dir / "model.plan").exists()
        assert (version_dir / "model.onnx").exists()  # rollback stays: ONNX is not deleted
        assert (version_dir / "provenance.json").read_bytes() == record_bytes

    def test_plan_mode_compiles_and_never_re_runs_inference(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No GPU here and none in CI, so the compile step may not depend on
        running a model. The numeric proof of the PLAN is the owner's
        `reid_parity_check.py` run on the GB300 (ruling 107's Done when), and the
        numeric proof of the GRAPH it compiles is `validate_onnx`'s CPU-EP pass
        in the ONNX step. This test pins that the plan path touches neither."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        self._write_record_for(version_dir / "model.onnx", ckpt)
        touched: list = []
        monkeypatch.setattr(export_reid, "load_pytorch_model", lambda p: touched.append("load"))
        monkeypatch.setattr(export_reid, "export_to_onnx", lambda *a, **k: touched.append("export"))
        monkeypatch.setattr(
            export_reid, "validate_onnx", lambda *a, **k: touched.append("validate")
        )
        monkeypatch.setattr(
            export_reid,
            "build_tensorrt_engine",
            lambda onnx, plan, **kw: Path(plan).write_bytes(b"plan bytes"),
        )
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")

        assert export_reid.main() == 0
        assert touched == []

    def test_a_plan_the_builder_failed_to_write_does_not_ship(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing half-built lands in the version dir the entrypoint will link."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        self._write_record_for(version_dir / "model.onnx", ckpt)

        def failing_builder(onnx: str, plan: str, **kw: object) -> str:
            Path(plan).write_bytes(b"partial garbage")  # trtexec can leave a husk
            raise RuntimeError("trtexec failed")

        monkeypatch.setattr(export_reid, "build_tensorrt_engine", failing_builder)
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")

        assert export_reid.main() == 1
        assert not (version_dir / "model.plan").exists()  # main() must clean the husk
        assert (version_dir / "provenance.json").exists()  # the ONNX's record stands


# ---------------------------------------------------------------------------
# export_all.sh: the plan step is named where the host bake runs it
# ---------------------------------------------------------------------------


class TestExportAllNamesThePlanStep:
    def test_plan_step_runs_for_reid(self) -> None:
        """`run_export`'s skip already accepts a `.plan` at the check path; pin
        that the reid plan step exists, its output IS the plan, and it runs
        after the reid ONNX step (the plan builder consumes that ONNX).

        The script spells the destination once, as `REID_PLAN`, and passes that
        variable — so the check ties the two together rather than matching a
        literal next to `--output-path`.
        """
        text = EXPORT_ALL.read_text()
        assert re.search(r'^REID_PLAN="\$\{CACHE_DIR\}/reid/1/model\.plan"$', text, re.M)
        assert re.search(r'--output-path\s+"\$REID_PLAN"', text)
        onnx_at = text.index("${CACHE_DIR}/reid/1/model.onnx")
        plan_at = text.index('REID_PLAN="${CACHE_DIR}/reid/1/model.plan"')
        assert onnx_at < plan_at

    def test_plan_step_reports_a_host_with_no_tensorrt(self) -> None:
        """A CPU bake (and CI) has no trtexec. It must skip LOUDLY — the config
        now needs a plan to serve reid at all, and a silent skip would leave an
        operator with a repository that cannot load the model."""
        text = EXPORT_ALL.read_text()
        assert "trtexec" in text
        warning_at = text.index("reid/config.pbtxt serves backend")
        assert "will not load" in text[warning_at : warning_at + 200]

    def test_plan_failure_on_a_gpu_host_is_a_failed_export(self) -> None:
        """With trtexec present, a failing compile (a stale or unvouched ONNX is
        the case the guard exists to surface) must reach FAIL_COUNT, not hide in
        the skip counter."""
        text = EXPORT_ALL.read_text()
        plan_block = text[text.index("REID_PLAN=") : text.index("# Phase 3")]
        assert "FAIL_COUNT=$((FAIL_COUNT + 1))" in plan_block
        assert plan_block.count("SKIP_COUNT=$((SKIP_COUNT + 1))") == 2  # cached + no-trtexec

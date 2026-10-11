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
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

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

    def test_the_workspace_flag_is_the_spelling_trt10_accepts(self, tmp_path: Path) -> None:
        """`--workspace=<MiB>` was deprecated in TensorRT 8 and REMOVED in 10,
        which is what the serving image ships (nvcr.io/nvidia/tritonserver:
        26.01-py3, ai/gateway/Dockerfile:1) and trtexec rejects unknown
        arguments. `--memPoolSize=workspace:` is accepted by 8 and 10 alike.

        Nothing else in this repo could have caught a wrong spelling:
        export_fashion_clip.py carries the old flag but is never wired into
        export_all.sh, so the owner's plan bake is the first execution of either
        form here — the flag has to be pinned by a test, not by precedent.
        """
        captured: list = []
        onnx = tmp_path / "model.onnx"
        onnx.write_bytes(b"fake onnx")
        plan = tmp_path / "model.plan"
        export_reid.build_tensorrt_engine(
            str(onnx), str(plan), trtexec="/usr/bin/trtexec", run=_fake_run_factory(captured)
        )
        cmd = captured[0]
        assert f"--memPoolSize=workspace:{export_reid.DEFAULT_WORKSPACE_GB * 1024}" in cmd
        assert not any(a.startswith("--workspace=") for a in cmd), (
            "the removed TRT-10 spelling would make the owner's bake die on "
            "an unknown-argument error before it compiled anything"
        )

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


class TestValidationRunsOnCpu:
    """The export's validation step must not be the thing ruling 106 killed.

    `validate_onnx` is the ONNX pass's graph-fidelity proof, and the serving
    image ships onnxruntime-GPU (ai/gateway/Dockerfile:32), so an IMPLICIT
    provider list would pick CUDAExecutionProvider whenever a GPU is merely
    visible — which on the GB300 is the provider that fails this graph with
    `cudaErrorSymbolNotFound`. That would make the export itself die the death
    TensorRT was ordered to replace, on the host O2.4 targets.

    There is no onnxruntime in this venv and no GPU anywhere near CI, so the
    module is stubbed (the `sys.modules` idiom test_export_reid.py:63-77 uses
    for torch.utils.tensorboard) and the assertion is on what the code ASKS for.
    """

    @pytest.fixture
    def fake_ort(self, monkeypatch: pytest.MonkeyPatch) -> list:
        """Install fake `onnx` / `onnxruntime`; return the providers it was asked for."""
        import sys
        import types

        asked: list = []

        ort = types.ModuleType("onnxruntime")

        class FakeSession:
            def __init__(self, path: str, providers: object = None) -> None:
                asked.append(providers)

            def run(self, _out: object, feeds: dict) -> list:
                batch = next(iter(feeds.values())).shape[0]
                # Identical to the "PyTorch" output below: max_diff 0, cosine 1.
                return [np.ones((batch, export_reid.EMBEDDING_DIM), dtype=np.float32)]

        ort.InferenceSession = FakeSession  # type: ignore[attr-defined]

        onnx_mod = types.ModuleType("onnx")
        onnx_mod.load = lambda p: object()  # type: ignore[attr-defined]
        onnx_mod.checker = SimpleNamespace(check_model=lambda m: None)  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "onnxruntime", ort)
        monkeypatch.setitem(sys.modules, "onnx", onnx_mod)
        return asked

    def test_the_session_is_asked_for_cpu_only(self, fake_ort: list, tmp_path: Path) -> None:
        class FakeModel(torch.nn.Module):
            """A real Module: validate_onnx's contract is the adapter's own call
            path — invoke under inference_mode, then .numpy() — so the stand-in
            satisfies the type AND the path, instead of duck-typing around it."""

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                # Same values the fake ORT session returns: max_diff 0, cosine 1,
                # so this test says nothing about numerics and everything about
                # which providers the code asks for.
                return torch.ones(int(x.shape[0]), export_reid.EMBEDDING_DIM)

        onnx_path = tmp_path / "model.onnx"
        onnx_path.write_bytes(b"fake onnx")
        assert export_reid.validate_onnx(FakeModel(), str(onnx_path)) is True
        assert fake_ort, "validate_onnx never built an inference session"
        for providers in fake_ort:
            assert list(providers or []) == ["CPUExecutionProvider"], (
                "the export's own validation must run on CPU: CUDAExecutionProvider "
                "is the provider ruling 106 proved cannot run this graph"
            )


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
    def _write_checkpoint(path: Path, content: bytes = b"checkpoint bytes") -> Path:
        # `content` is not a convenience: with constant bytes every checkpoint
        # this file writes shares a sha256, which makes the source_sha256 guard
        # unsatisfiable. The mismatch test passed for exactly that wrong reason
        # before F1 — it never reached the guard at all.
        path.write_bytes(content)
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

    def _builder_available(self, monkeypatch: pytest.MonkeyPatch) -> list:
        """Make the builder PRESENT and recording, and return the call log.

        Load-bearing: without this the two refusal tests are satisfiable by the
        builder's ABSENCE — on a host with no trtexec, ``build_tensorrt_engine``
        raises, ``main()`` catches it and returns 1, so an assertion on the exit
        code passes with every provenance guard deleted (verified: a guard-free
        mutant of export_reid.py passes the suite 17/17). Pinning the guard means
        removing the other way out, so a fake builder stands ready and the ONLY
        thing that can stop the compile is the guard.
        """
        built: list = []

        def fake_build(onnx: str, plan: str, **kw: object) -> str:
            built.append((onnx, plan))
            Path(plan).write_bytes(b"plan bytes")
            return plan

        monkeypatch.setattr(export_reid, "find_trtexec", lambda: "/usr/bin/trtexec")
        monkeypatch.setattr(export_reid, "build_tensorrt_engine", fake_build)
        return built

    def test_refuses_an_onnx_no_provenance_record_vouches_for(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#6970's precondition turned into a stop: export_all.sh skips an
        existing model.onnx, so a stale pre-B2.2 ONNX (no record beside it) must
        never seed a plan."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        built = self._builder_available(monkeypatch)

        # Assert the REASON, not just a nonzero exit: the guard must be what
        # stops it, and it must say why an operator can act on it.
        with pytest.raises(RuntimeError, match="provenance"):
            export_reid.compile_plan_from_validated_onnx(str(ckpt), str(version_dir / "model.plan"))
        assert built == []
        assert not (version_dir / "model.plan").exists()

        # And through main(), where the same stop must not leave a husk behind.
        self._argv(monkeypatch, ckpt, version_dir / "model.plan")
        assert export_reid.main() == 1
        assert built == []
        assert not (version_dir / "model.plan").exists()

    def test_refuses_a_checkpoint_that_is_not_the_recorded_bytes(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plan may not ship labelled with weights that are not the ones the
        record — and therefore the ONNX — was made from."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        other = self._write_checkpoint(
            tmp_path / "different.pth", content=b"different checkpoint bytes"
        )
        self._write_record_for(version_dir / "model.onnx", other)  # record names OTHER weights
        built = self._builder_available(monkeypatch)

        with pytest.raises(RuntimeError, match="not the recorded weights"):
            export_reid.compile_plan_from_validated_onnx(str(ckpt), str(version_dir / "model.plan"))
        assert built == []
        assert not (version_dir / "model.plan").exists()

    def test_refuses_a_record_naming_a_different_zoo_model(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other half of the model-ID contract: reid_model_id() publishes
        what the record says, so a plan built against a record for another zoo
        model would ship weights under the wrong published ID."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        self._write_record_for(version_dir / "model.onnx", ckpt)
        record = json.loads((version_dir / "provenance.json").read_text())
        record["zoo_name"] = "some-other-backbone"
        (version_dir / "provenance.json").write_text(json.dumps(record))
        built = self._builder_available(monkeypatch)

        with pytest.raises(RuntimeError, match="refusing to build a plan"):
            export_reid.compile_plan_from_validated_onnx(str(ckpt), str(version_dir / "model.plan"))
        assert built == []

    def test_refuses_a_plan_destination_triton_cannot_load(
        self, version_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Triton's tensorrt backend loads exactly ``1/model.plan``; it does not
        read the filename from anywhere else. A plan written to any other name
        exits 0, the bake reports OK, and Triton finds no model — so the guard
        is the only thing between a typo and a silently unserved gateway."""
        ckpt = self._write_checkpoint(tmp_path / "osnet_ain_x1_0_msmt17.pth")
        self._write_record_for(version_dir / "model.onnx", ckpt)
        built = self._builder_available(monkeypatch)

        for bad_name in ("reid.plan", "model.planx", "model.onnx.plan"):
            with pytest.raises(RuntimeError, match=r"must be named model\.plan"):
                export_reid.compile_plan_from_validated_onnx(str(ckpt), str(version_dir / bad_name))
        assert built == []

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


class TestExportAllOnAHost:
    """Executes export_all.sh itself, with the heavy machinery stubbed on PATH.

    Grep pins the SHAPE of the bake; only running it catches the failure modes
    that actually bit this package in review: the skip line printing while the
    summary still says "All exports succeeded" (F10), a plan from another GPU
    read as CACHED forever (F6), and compile failures vanishing from the exit
    code (F4b). Stubbing strategy: every ONNX is pre-seeded so `run_export`
    skips phases 1-2 (no ultralytics/torch export runs), and PATH holds only a
    stub `nvidia-smi`, a recording `trtexec`, and a `python3` that stands in
    for the yolo/threat exporters. The plan step then runs the REAL
    export_reid.py against a cache whose provenance record vouches for the
    checkpoint's bytes — so the trtexec argv captured here is the real argv the
    owner's bake will carry.
    """

    # Runs a real shell script and, on the compile paths, one real torch-importing
    # python child. The file's 30s budget covers the skip/cached paths comfortably;
    # the compile legs pay the cold import on a cold cache under xdist.
    pytestmark = pytest.mark.timeout(180)

    HOST_GPU = "NVIDIA GB300"

    @pytest.fixture
    def host(self, tmp_path: Path) -> dict:
        """A fake serving host: zoo with the checkpoint, cache with vouched ONNXes."""
        zoo = tmp_path / "zoo"
        cache = tmp_path / "cache"
        ckpt = zoo / "osnet-ain-x1-0" / "osnet_ain_x1_0_msmt17.pth"
        ckpt.parent.mkdir(parents=True)
        ckpt.write_bytes(b"synthetic osnet checkpoint")

        reid_dir = cache / "reid" / "1"
        reid_dir.mkdir(parents=True)
        (reid_dir / "model.onnx").write_bytes(b"vouched onnx")
        # Pre-seeded so run_export reports CACHED for all three ONNXes and the
        # bake's only real work is the plan step.
        for model in ("yolo26", "threat"):
            d = cache / model / "1"
            d.mkdir(parents=True)
            (d / "model.onnx").write_bytes(b"cached onnx")
        (reid_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "zoo_name": export_reid.OSNET_ZOO_NAME,
                    "source_file": ckpt.name,
                    "source_sha256": hashlib.sha256(ckpt.read_bytes()).hexdigest(),
                }
            )
        )

        stubs = tmp_path / "stubs"
        stubs.mkdir()
        argv_log = tmp_path / "trtexec-argv.txt"
        (stubs / "nvidia-smi").write_text(f"#!/bin/bash\necho '{self.HOST_GPU}'\n")
        # A trtexec that records its argv and produces the engine it was told to
        # save — exactly what the real builder must do, and enough for the
        # builder's post-check (`engine.is_file()`) to pass.
        (stubs / "trtexec").write_text(
            "#!/bin/bash\n"
            'printf \'%s\\n\' "$@" >> "$TRT_STUB_ARGV"\n'
            'for a in "$@"; do case "$a" in --saveEngine=*) '
            'f="${a#--saveEngine=}"; mkdir -p "$(dirname "$f")"; '
            'printf plan > "$f";; esac; done\n'
        )
        # python3 is deliberately SHADOWED, because the real /usr/bin/python3 has
        # no torch — an unsupplied stub would let the plan step "succeed" by
        # silently doing nothing. export_reid.py is routed to the TEST
        # interpreter (sys.executable: the venv that has torch); any other
        # exporter (yolo/threat, never reached on this cache — run_export skips
        # seeded models) exits 0 as a visible stand-in.
        (stubs / "python3").write_text(
            "#!/bin/bash\n"
            'case "$1" in\n'
            '    *export_reid.py) exec "$TEST_PYTHON" -I "$@" ;;\n'
            "    *) exit 0 ;;\n"
            "esac\n"
        )
        for f in stubs.iterdir():
            f.chmod(0o755)

        return {
            "zoo": zoo,
            "cache": cache,
            "ckpt": ckpt,
            "stubs": stubs,
            "argv": argv_log,
            "plan": reid_dir / "model.plan",
            "sidecar": reid_dir / "model.plan.device",
        }

    def _run(
        self,
        host: dict,
        *,
        trtexec: bool = True,
        gpu: str | None = None,
        **env: str,
    ) -> SimpleNamespace:
        if gpu is not None:
            (host["stubs"] / "nvidia-smi").write_text(f"#!/bin/bash\necho '{gpu}'\n")
        path_dirs = [str(host["stubs"])] if trtexec else []
        # The no-trtexec leg drops the stub dir entirely rather than deleting
        # files from it — and the sandbox has neither a trtexec on PATH nor
        # /usr/src/tensorrt/bin/trtexec (both checked above), so coreutils on
        # /usr/bin is enough for the script's own skip branch to be the reason.
        script_env = {
            "PATH": ":".join([*path_dirs, "/usr/bin", "/bin"]),
            "MODELS_ZOO": str(host["zoo"]),
            "CACHE_DIR": str(host["cache"]),
            # The REAL repository: phase 3 checks configs exist, and the point of
            # O2.4 is that the shipped reid config is the tensorrt one.
            "REPO_DIR": str(REPO_ROOT / "ai" / "triton" / "model_repository"),
            "TRT_STUB_ARGV": str(host["argv"]),
            "TEST_PYTHON": sys.executable,
            # -I above needs the test tree importable; export_reid.py imports
            # through the package path (ai.gateway.export).
            "PYTHONPATH": str(REPO_ROOT),
        }
        script_env.update(env)
        proc = subprocess.run(  # noqa: S603  # intentional - runs this repo's own bake script
            ["/bin/bash", str(EXPORT_ALL)],
            env=script_env,
            capture_output=True,
            text=True,
            timeout=150,
            # The exit code IS the assertion under test (a failed plan compile
            # must exit 1; a CPU bake must exit 0), so no check= here.
            check=False,
        )
        return SimpleNamespace(rc=proc.returncode, out=proc.stdout + proc.stderr)

    def test_a_gpu_host_bakes_a_plan_and_reports_the_truth(self, host: dict) -> None:
        r = self._run(host)
        assert r.rc == 0, r.out
        assert host["plan"].is_file(), "the bake produced no plan"
        assert "TensorRT plan" in r.out and "     OK" in r.out, r.out
        # The sidecar records WHICH GPU the engine was compiled for (F6).
        assert host["sidecar"].read_text().strip() == self.HOST_GPU
        # The captured argv is the real command line the owner's bake runs.
        argv = host["argv"].read_text()
        assert "--fp16" in argv
        assert "--minShapes=input:1x3x256x128" in argv
        assert "--maxShapes=input:16x3x256x128" in argv
        assert "--memPoolSize=workspace:1024" in argv
        assert "All exports succeeded." in r.out

    def test_reruns_skip_a_plan_built_on_this_gpu(self, host: dict) -> None:
        assert self._run(host).rc == 0
        argv_before = host["argv"].read_text()
        r = self._run(host)
        assert r.rc == 0, r.out
        assert "TensorRT plan... CACHED" in r.out
        assert host["argv"].read_text() == argv_before, "a cached plan was rebuilt"

    def test_a_plan_from_a_different_gpu_is_stale_not_cached(self, host: dict) -> None:
        assert self._run(host).rc == 0
        host["argv"].unlink()  # only a fresh compile can recreate it
        r = self._run(host, gpu="GB300-second-card")  # different nvidia-smi answer
        assert r.rc == 0, r.out
        assert "STALE" in r.out and "rebuilding" in r.out, r.out
        assert host["argv"].is_file(), "the stale plan was kept and nothing rebuilt"
        # The sidecar names the card that built the plan that EXISTS now — the
        # rebuild happened on the second card, so that is what it must say, or
        # the next run on either host mis-classifies the artifact again.
        assert host["sidecar"].read_text().strip() == "GB300-second-card"

    def test_without_tensorrt_the_skip_says_reid_will_not_load(self, host: dict) -> None:
        r = self._run(host, trtexec=False)
        assert r.rc == 0, r.out  # a CPU bake is a legitimate run
        assert not host["plan"].exists()
        assert "SKIPPED - no trtexec" in r.out
        assert 'reid/config.pbtxt serves backend "tensorrt"' in r.out
        assert "reid will NOT load" in r.out
        # F10: the VERDICT must not erase the step line.
        assert "All exports succeeded." not in r.out
        assert "the GPU step is pending, not passed." in r.out

    def test_a_failed_compile_is_a_failed_export(self, host: dict) -> None:
        # trtexec present but failing: a stale/unvouched ONNX is #6970's exact
        # precondition, so this must land in FAIL_COUNT and the exit code.
        (host["stubs"] / "trtexec").write_text("#!/bin/bash\nexit 1\n")
        (host["stubs"] / "trtexec").chmod(0o755)
        r = self._run(host)
        assert r.rc == 1, r.out
        # The SUMMARY line is the classification, not just the step echo: a
        # failed compile that lands in Skipped: instead of Failed: would exit 0
        # and setup_lib would declare the cache ready. (Counting echoes is not
        # enough — run_export prints its own "FAILED" for the ONNX steps.)
        assert "  Failed: 1" in r.out, r.out
        assert "  Skipped: 3" in r.out, r.out  # 3 ONNX exports, all seeded/cached
        assert "export(s) failed" in r.out, r.out
        assert not host["plan"].exists()
        assert not host["sidecar"].exists()

    def test_the_precision_lever_reaches_the_builder(self, host: dict) -> None:
        """REID_PLAN_PRECISION=fp32 is the one-flag retry if the owner's parity
        run lands just under the 0.999 gate (ruling 107); pin that it actually
        changes the builder command rather than being read and dropped."""
        r = self._run(host, REID_PLAN_PRECISION="fp32")
        assert r.rc == 0, r.out
        argv = host["argv"].read_text()
        assert "--fp16" not in argv, argv


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

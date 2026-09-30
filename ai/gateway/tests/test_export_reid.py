"""OSNet-AIN x1.0 export: the standalone port must BE torchreid's osnet_ain_x1_0.

Regression guard for a silent-correctness bug: export_reid.py hand-wrote plain
OSNet (conv2a..conv2d streams, a BatchNorm stem plus a separate conv1_IN, the
transition pools folded into the stages) under the OSNet-AIN name. Only 118 of
the MSMT17 checkpoint's 552 keys loaded, ``strict=False`` merely warned, and
validate_onnx compared the ONNX against that same under-loaded model (cosine
1.000) - so a mostly random embedder shipped as ``reid/1/model.onnx``.

Every check here is against torchreid itself - the reference the backend loader
(backend/services/osnet_loader.py) builds with ``build_model('osnet_ain_x1_0')``
- never against the port.
"""

from __future__ import annotations

import importlib
import re
import sys
import types
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import torch
from torch import nn

from ai.gateway.export import export_reid

# The 5s tier default (pyproject.toml:584) is too tight for this module. Every
# test needs `build_reference`, whose module-scoped fixture cold-imports
# torchreid's real model factory (:66, behind a tensorboard stub the backend
# loader also needs) and builds osnet_ain_x1_0 — the module has no module-level
# torchreid import, so that cost lands inside the timed setup, once per xdist
# worker. Measured here: 1.1-1.4s per setup on an idle 16-core box. GitHub's
# ubuntu-latest runner under `-n 8` contention is slower, and the CI run of
# this PR showed exactly the failure that predicts: 246 passed, 6 errors, every
# one `Failed: Timeout (>5.0s)` in this file, while all six pass locally. main's
# run of the same file passed — so the 5s line is borderline, not clearly
# crossed; contention tipped this run, and would tip others.
# 60s is not invented: it is this repo's own declared budget for model loading
# (`e2e: ... 60s timeout for model loading`, pyproject.toml:601; the sibling
# ai/tests/test_module_hygiene.py already uses an explicit per-file timeout for
# the same reason). The watchdog stays armed for a real hang, and this touches
# nothing in .github/flake-allowlist.yml — that file is empty by policy and
# registering an id there is a quarantine, which is off-limits.
pytestmark = pytest.mark.timeout(60)

# The MSMT17 checkpoint's identity-head width (classifier.weight is [4101, 512]).
MSMT17_NUM_CLASSES = 4101

BuildReference = Callable[[int], nn.Module]


def _ensure_tensorboard_importable(mp: pytest.MonkeyPatch) -> None:
    """backend/services/osnet_loader.py's B2 stub, undone after this module.

    torchreid's package import chain pulls in torch.utils.tensorboard (a
    trainer-only SummaryWriter) and the tensorboard package is not shipped.
    The stub is inert for model construction and inference; a real module is
    never shadowed.
    """
    if "torch.utils.tensorboard" in sys.modules:
        return
    try:
        importlib.import_module("torch.utils.tensorboard")
        return
    except Exception:  # noqa: S110 - absent tensorboard is the case we stub
        pass
    stub = types.ModuleType("torch.utils.tensorboard")

    class SummaryWriter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    stub.SummaryWriter = SummaryWriter  # type: ignore[attr-defined]
    mp.setitem(sys.modules, "torch.utils.tensorboard", stub)


@pytest.fixture(scope="module")
def build_reference() -> Iterator[BuildReference]:
    """torchreid's osnet_ain_x1_0, built exactly as the backend loader builds it."""
    with pytest.MonkeyPatch.context() as mp:
        _ensure_tensorboard_importable(mp)
        build_model = importlib.import_module("torchreid.reid.models").build_model

        def _build(num_classes: int) -> nn.Module:
            return build_model(name="osnet_ain_x1_0", num_classes=num_classes, pretrained=False)

        yield _build


def _perturb(model: nn.Module, generator: torch.Generator) -> nn.Module:
    """Move every norm layer and bias off its identity init.

    torchreid's _init_params leaves each BatchNorm/InstanceNorm at weight=1,
    bias=0, running_mean=0, running_var=1 and every bias at 0, so a port that
    drops, swaps or misplaces a norm layer could still match numerically.
    """
    norm_types = (nn.BatchNorm1d, nn.BatchNorm2d, nn.InstanceNorm2d)
    with torch.no_grad():
        for module in model.modules():
            if not isinstance(module, norm_types):
                continue
            if module.weight is not None:
                module.weight.uniform_(0.5, 1.5, generator=generator)
            if module.running_mean is not None:
                module.running_mean.uniform_(-0.1, 0.1, generator=generator)
            if module.running_var is not None:
                module.running_var.uniform_(0.5, 1.5, generator=generator)
        for name, param in model.named_parameters():
            if name.endswith("bias"):
                param.uniform_(-0.1, 0.1, generator=generator)
    return model


def _reference_model(build_reference: BuildReference, seed: int) -> nn.Module:
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        reference = build_reference(MSMT17_NUM_CLASSES)
    return _perturb(reference, torch.Generator().manual_seed(seed)).eval()


def _person_batch(seed: int, batch: int = 2) -> torch.Tensor:
    return torch.randn(
        batch,
        3,
        export_reid.INPUT_HEIGHT,
        export_reid.INPUT_WIDTH,
        generator=torch.Generator().manual_seed(seed),
    )


def _embed(model: nn.Module, x: torch.Tensor) -> torch.Tensor:
    with torch.inference_mode():
        return model.eval()(x)


def _assert_parity(actual: torch.Tensor, expected: torch.Tensor) -> None:
    assert actual.shape == (expected.shape[0], export_reid.EMBEDDING_DIM)
    # Non-vacuous: the reference output is input-dependent and not all zeros
    # (its last op is a ReLU, so 0 == 0 parity would prove nothing).
    assert expected.abs().sum() > 0
    assert not torch.allclose(expected[0], expected[1])
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


class TestArchitectureParity:
    def test_state_dict_keys_and_shapes_equal_torchreid(
        self, build_reference: BuildReference
    ) -> None:
        """Names AND shapes, classifier head included - nothing is excluded."""
        ported = {
            k: tuple(v.shape)
            for k, v in export_reid.create_osnet_ain_x1_0(MSMT17_NUM_CLASSES).state_dict().items()
        }
        reference = {
            k: tuple(v.shape) for k, v in build_reference(MSMT17_NUM_CLASSES).state_dict().items()
        }

        missing = sorted(reference.keys() - ported.keys())
        extra = sorted(ported.keys() - reference.keys())
        reshaped = sorted(k for k in reference.keys() & ported.keys() if reference[k] != ported[k])

        assert (missing, extra, reshaped) == ([], [], []), (
            f"port diverges from torchreid osnet_ain_x1_0 ({len(reference)} keys): "
            f"{len(missing)} missing e.g. {missing[:3]}, "
            f"{len(extra)} extra e.g. {extra[:3]}, "
            f"{len(reshaped)} reshaped e.g. {reshaped[:3]}"
        )

    def test_eval_forward_matches_torchreid(self, build_reference: BuildReference) -> None:
        """Same weights (strict copy) + same input => same embedding, un-normalized.

        torchreid's eval forward returns the fc (Linear+BN1d+ReLU) output with
        NO L2 normalization; the consumers (gateway /person-reid, backend
        extract_person_embedding) normalize afterwards. The port must match.
        """
        reference = _reference_model(build_reference, seed=0)
        ported = export_reid.create_osnet_ain_x1_0(MSMT17_NUM_CLASSES)
        ported.load_state_dict(reference.state_dict(), strict=True)

        x = _person_batch(seed=1)
        _assert_parity(_embed(ported, x), _embed(reference, x))


class TestStrictLoading:
    """load_pytorch_model refuses any backbone mismatch; only the head may differ."""

    @pytest.fixture
    def reference(self, build_reference: BuildReference) -> nn.Module:
        return _reference_model(build_reference, seed=2)

    @pytest.fixture
    def checkpoint(self, reference: nn.Module) -> dict[str, torch.Tensor]:
        # DataParallel layout, like the real MSMT17 file (every key 'module.'-prefixed).
        return {f"module.{k}": v for k, v in reference.state_dict().items()}

    @staticmethod
    def _save(checkpoint: dict[str, torch.Tensor], tmp_path: Path) -> str:
        path = tmp_path / "osnet_ain_x1_0.pth"
        torch.save(checkpoint, path)
        return str(path)

    def test_full_checkpoint_reproduces_torchreid(
        self, reference: nn.Module, checkpoint: dict[str, torch.Tensor], tmp_path: Path
    ) -> None:
        model = export_reid.load_pytorch_model(self._save(checkpoint, tmp_path))

        assert not model.training
        x = _person_batch(seed=3)
        _assert_parity(_embed(model, x), _embed(reference, x))

    def test_missing_backbone_key_raises(
        self, checkpoint: dict[str, torch.Tensor], tmp_path: Path
    ) -> None:
        # The deepest LightConv3x3 of the first AIN block's T=4 stream.
        victim = "conv2.0.conv2.3.layers.3.bn.running_var"
        del checkpoint[f"module.{victim}"]

        with pytest.raises(RuntimeError, match=re.escape(victim)):
            export_reid.load_pytorch_model(self._save(checkpoint, tmp_path))

    def test_unexpected_backbone_key_raises(
        self, checkpoint: dict[str, torch.Tensor], tmp_path: Path
    ) -> None:
        # The plain-OSNet stem IN the old hand-written architecture carried.
        checkpoint["module.conv1_IN.weight"] = torch.ones(64)

        with pytest.raises(RuntimeError, match=re.escape("conv1_IN.weight")):
            export_reid.load_pytorch_model(self._save(checkpoint, tmp_path))

    def test_checkpoint_without_classifier_head_loads(
        self, reference: nn.Module, checkpoint: dict[str, torch.Tensor], tmp_path: Path
    ) -> None:
        """The head is unused by the eval embedding, so its absence is legitimate."""
        del checkpoint["module.classifier.weight"]
        del checkpoint["module.classifier.bias"]

        model = export_reid.load_pytorch_model(self._save(checkpoint, tmp_path))

        x = _person_batch(seed=4)
        _assert_parity(_embed(model, x), _embed(reference, x))

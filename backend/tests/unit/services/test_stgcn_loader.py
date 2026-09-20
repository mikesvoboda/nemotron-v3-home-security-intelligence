"""WP3.1 first tests for backend.services.stgcn_loader.

Mutation history: no_tests (5 mutants never measured). The heavy network is
only touched where construction/loading is the subject; classification runs
against a FAKE model returning pinned logits, so the preprocessing math and
the security-classification table get exact assertions:

  * COCO adjacency: (3,17,17), layer 0 is the identity; inward edges stay
    1.0 (normalization divides by the child's OUT-degree, always 1 per edge)
    while outward edges divide by parent fanout — joint 5's children get 1/2,
    joint 0's four children get 1/4
  * _map_checkpoint_keys: the three pyskl renames (backbone., cls_head.
    fc_cls. -> fc., plain cls_head.) asserted on all four shapes
  * load: missing .pth -> RuntimeError; a real STGCNPP state_dict saved under
    pyskl-prefixed keys loads BACK to an equal model (the mapper is wired
    into the loader, eval mode, device cpu)
  * classify: shape validation errors, channel pad (C=2 -> conf 1.0) and
    truncation (C>3), person pad/truncate to 2, resample to exactly 100
    frames — all asserted on the tensor the fake model RECEIVES, not the
    output; softmax top-k ordering; risk map index 42 = falling = critical,
    49 = punching = high+relevant, ordinary actions = none/not-relevant
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from backend.services.stgcn_loader import (
    COCO_KEYPOINT_NAMES,
    NTU60_LABELS,
    SECURITY_RELEVANT_ACTIONS,
    SECURITY_RISK_MAP,
    STGCNPP,
    SkeletonActionResult,
    _build_coco_adjacency,
    _map_checkpoint_keys,
    classify_skeleton_action,
    load_stgcn_model,
)


class FakeStgcn:
    """Returns pinned logits; records the input tensor it was called with."""

    def __init__(self, logits: list[float]) -> None:
        self._logits = logits
        self.seen: torch.Tensor | None = None

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        self.seen = x
        return torch.tensor([self._logits], dtype=torch.float32)

    def to(self, device):
        return self

    def eval(self):
        return self


def _model_dict(logits, labels=None):
    return {
        "model": FakeStgcn(logits),
        "labels": labels or list(NTU60_LABELS),
        "device": "cpu",
    }


def _kp(m=1, t=10, v=17, c=3) -> np.ndarray:
    rng = np.random.default_rng(3)
    return rng.random((m, t, v, c), dtype=np.float32)


def _peaked(idx: int, n: int = 60, score: float = 6.0) -> list[float]:
    logits = [0.0] * n
    logits[idx] = score
    return logits


# ------------------------------------------------------------------ constants


class TestConstants:
    def test_labels_are_the_60_ntu_classes(self) -> None:
        assert len(NTU60_LABELS) == 60
        assert NTU60_LABELS[42] == "falling"
        assert NTU60_LABELS[49] == "punching/slapping other person"
        assert NTU60_LABELS[56] == "touch other person's pocket"

    def test_risk_map_values(self) -> None:
        assert SECURITY_RISK_MAP[42] == "critical"
        assert SECURITY_RISK_MAP[49] == "high"
        assert SECURITY_RISK_MAP[41] == "medium"
        assert SECURITY_RISK_MAP[58] == "low"
        assert len(SECURITY_RISK_MAP) == 10

    def test_relevant_actions_membership(self) -> None:
        assert 42 in SECURITY_RELEVANT_ACTIONS
        assert 49 in SECURITY_RELEVANT_ACTIONS
        assert 0 not in SECURITY_RELEVANT_ACTIONS
        assert isinstance(SECURITY_RELEVANT_ACTIONS, frozenset)

    def test_coco_names(self) -> None:
        assert len(COCO_KEYPOINT_NAMES) == 17
        assert COCO_KEYPOINT_NAMES[0] == "nose"
        assert COCO_KEYPOINT_NAMES[-1] == "right_ankle"


# ---------------------------------------------------------------- adjacency


class TestCocoAdjacency:
    def setup_method(self) -> None:
        self.A = _build_coco_adjacency()

    def test_shape_and_identity_layer(self) -> None:
        assert self.A.shape == (3, 17, 17)
        assert self.A.dtype == np.float32
        np.testing.assert_array_equal(self.A[0], np.eye(17, dtype=np.float32))

    def test_inward_edges_raw_one_per_child(self) -> None:
        # pyskl _normalize divides by the SOURCE out-degree; every child has
        # exactly one parent edge out, so inward stays 1.0 per edge
        assert self.A[1][5, 11] == pytest.approx(1.0)
        assert self.A[1][5, 7] == pytest.approx(1.0)
        assert self.A[1][5, :].sum() == pytest.approx(2.0)  # joint 5 has 2 children
        assert self.A[1][5, 5] == 0.0  # no self loop inside the edge layer

    def test_outward_normalized_by_parent_fanout(self) -> None:
        # outward divides by the parent's child count: joint 5 has children
        # {11, 7} -> each outward edge 1/2; joint 11 has ONE child (13) -> 1.0;
        # joint 0 has FOUR children {5,6,1,2} -> 1/4
        assert self.A[2][11, 5] == pytest.approx(0.5)
        assert self.A[2][7, 5] == pytest.approx(0.5)
        assert self.A[2][13, 11] == pytest.approx(1.0)
        assert self.A[2][5, 0] == pytest.approx(0.25)


# ------------------------------------------------------- _map_checkpoint_keys


class TestMapCheckpointKeys:
    def test_pyskl_renames(self) -> None:
        t = torch.zeros(1)
        mapped = _map_checkpoint_keys(
            {
                "backbone.data_bn.weight": t,
                "backbone.gcn.3.gcn.conv.weight": t,
                "cls_head.fc_cls.weight": t,
                "cls_head.extra": t,
                "untouched.key": t,
            }
        )
        assert set(mapped) == {
            "data_bn.weight",
            "gcn.3.gcn.conv.weight",
            "fc.weight",
            "extra",
            "untouched.key",
        }


# ------------------------------------------------------------------- loading


class TestLoadStgcnModel:
    @pytest.mark.asyncio
    async def test_missing_checkpoint_raises(self, tmp_path) -> None:
        with pytest.raises(RuntimeError, match=r"No \.pth checkpoint"):
            await load_stgcn_model(str(tmp_path))

    @pytest.mark.asyncio
    async def test_roundtrip_loads_pyskl_prefixed_state_dict(self, tmp_path) -> None:
        reference = STGCNPP(num_classes=60, in_channels=3, num_person=2).eval()
        pyskl_sd = {
            f"backbone.{k}"
            if k.startswith("data_bn") or k.startswith("gcn.")
            else k.replace("fc.", "cls_head.fc_cls."): v
            for k, v in reference.state_dict().items()
        }
        torch.save({"state_dict": pyskl_sd}, tmp_path / "stgcn.pth")

        result = await load_stgcn_model(str(tmp_path))

        assert result["num_classes"] == 60
        assert result["labels"] is NTU60_LABELS
        assert result["device"] == "cpu"
        model = result["model"]
        assert model.training is False
        # T must stay even through the two stride-2 blocks (branch pooling
        # floors where the dilated convs ceil) -- 24 is the smallest safe
        # round-trip length.
        x = _kp(m=2, t=24)[np.newaxis]
        with torch.no_grad():
            out = model(torch.tensor(x, dtype=torch.float32))
            ref = reference(torch.tensor(x, dtype=torch.float32))
        assert out.shape == (1, 60)
        assert torch.allclose(out, ref, atol=1e-5)  # weights really mapped+loaded


class TestStgcnppForward:
    def test_forward_shape_and_determinism(self) -> None:
        model = STGCNPP().eval()
        x = torch.randn(1, 2, 24, 17, 3)  # even T: odd trips branch-size drift at stride 2
        with torch.no_grad():
            a, b = model(x), model(x)
        assert a.shape == (1, 60)
        assert torch.isfinite(a).all()
        assert torch.equal(a, b)  # eval mode: no stochastic paths


# ---------------------------------------------------------------- classify


class TestClassifyValidation:
    @pytest.mark.asyncio
    async def test_wrong_ndim_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"Expected keypoints shape"):
            await classify_skeleton_action(_model_dict(_peaked(0)), np.zeros((5, 17, 3)))

    @pytest.mark.asyncio
    async def test_wrong_joint_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="17 COCO keypoints"):
            await classify_skeleton_action(_model_dict(_peaked(0)), _kp(t=5, v=16))

    @pytest.mark.asyncio
    async def test_single_channel_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 2 channels"):
            await classify_skeleton_action(_model_dict(_peaked(0)), _kp(t=5, c=1))


class TestClassifyPreprocessing:
    @pytest.mark.asyncio
    async def test_two_channel_input_padded_with_confidence_one(self) -> None:
        md = _model_dict(_peaked(0))
        await classify_skeleton_action(md, _kp(m=1, t=5, c=2))
        x = md["model"].seen
        assert x.shape == (1, 2, 100, 17, 3)  # C padded, M padded to 2, T resampled to 100
        # person 0 got the synthetic conf=1.0 channel; person 1 is the zero pad
        np.testing.assert_allclose(x.numpy()[0, 0, ..., 2], 1.0, rtol=0, atol=1e-6)
        assert x.numpy()[0, 1].sum() == 0.0

    @pytest.mark.asyncio
    async def test_wide_input_truncated_to_three_channels(self) -> None:
        md = _model_dict(_peaked(0))
        await classify_skeleton_action(md, _kp(t=8, c=5))
        assert md["model"].seen.shape == (1, 2, 100, 17, 3)

    @pytest.mark.asyncio
    async def test_three_persons_truncated_to_two(self) -> None:
        md = _model_dict(_peaked(0))
        await classify_skeleton_action(md, _kp(m=3, t=8))
        assert md["model"].seen.shape[1] == 2

    @pytest.mark.asyncio
    async def test_resample_preserves_sequence_endpoints(self) -> None:
        # person 0 frames carry their index in x[...,0,0]; after linspace
        # resampling to 100 the FIRST and LAST frames must be originals
        kp = np.zeros((1, 50, 17, 3), dtype=np.float32)
        kp[0, :, 0, 0] = np.arange(50)
        md = _model_dict(_peaked(0))
        await classify_skeleton_action(md, kp)
        seen = md["model"].seen.numpy()
        assert seen[0, 0, 0, 0, 0] == 0.0
        assert seen[0, 0, -1, 0, 0] == 49.0


class TestClassifyResult:
    @pytest.mark.asyncio
    async def test_falling_is_critical_and_relevant(self) -> None:
        result = await classify_skeleton_action(_model_dict(_peaked(42)), _kp())
        assert result.action_index == 42
        assert result.action_label == "falling"
        assert result.security_risk == "critical"
        assert result.is_security_relevant is True
        assert result.confidence == pytest.approx(np.exp(6.0) / (np.exp(6.0) + 59), rel=1e-4)

    @pytest.mark.asyncio
    async def test_ordinary_action_is_none_risk(self) -> None:
        result = await classify_skeleton_action(_model_dict(_peaked(1)), _kp())
        assert result.security_risk == "none"
        assert result.is_security_relevant is False

    @pytest.mark.asyncio
    async def test_top_k_descending_and_labels(self) -> None:
        logits = _peaked(49)
        logits[0] = 3.0  # second best
        logits[1] = 2.0  # third: distinct, so argsort tie-breaking cannot reorder
        result = await classify_skeleton_action(_model_dict(logits), _kp(), top_k=3)
        assert result.action_index == 49
        assert [lab for lab, _ in result.top_actions] == [
            NTU60_LABELS[49],
            NTU60_LABELS[0],
            NTU60_LABELS[1],
        ]
        confs = [c for _, c in result.top_actions]
        assert confs == sorted(confs, reverse=True)
        assert len(result.top_actions) == 3

    @pytest.mark.asyncio
    async def test_to_dict_shape(self) -> None:
        r = SkeletonActionResult(
            action_label="falling",
            action_index=42,
            confidence=0.7,
            security_risk="critical",
            is_security_relevant=True,
            top_actions=[("falling", 0.7), ("standing", 0.1)],
        )
        d = r.to_dict()
        assert d["action_index"] == 42
        assert d["top_actions"] == [
            {"label": "falling", "confidence": 0.7},
            {"label": "standing", "confidence": 0.1},
        ]

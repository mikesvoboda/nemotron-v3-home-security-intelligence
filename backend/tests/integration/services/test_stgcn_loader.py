"""Integration tests for ST-GCN++ loader (NEM-5563).

Tests verify model loading, checkpoint mapping, and inference behavior.
"""

import pytest
import torch


@pytest.mark.integration
class TestSTGCNLoaderIntegration:
    """Integration tests for ST-GCN++ model loader."""

    @pytest.mark.asyncio
    async def test_load_stgcn_model_missing_checkpoint(self) -> None:
        """Test graceful failure when checkpoint file is missing."""
        from backend.services.stgcn_loader import load_stgcn_model

        with pytest.raises(RuntimeError, match="checkpoint"):
            await load_stgcn_model("/nonexistent/path")

    def test_checkpoint_key_mapping(self) -> None:
        """Test that pyskl checkpoint keys are correctly mapped."""
        from backend.services.stgcn_loader import _map_checkpoint_keys

        state_dict = {
            "backbone.data_bn.weight": torch.randn(3),
            "backbone.gcn.0.gcn.weight": torch.randn(3),
            "cls_head.fc_cls.weight": torch.randn(3),
        }
        mapped = _map_checkpoint_keys(state_dict)
        assert "data_bn.weight" in mapped
        assert "gcn.0.gcn.weight" in mapped
        assert "fc.weight" in mapped

    def test_stgcnpp_forward_pass(self) -> None:
        """Test ST-GCN++ model forward pass with dummy input."""
        from backend.services.stgcn_loader import STGCNPP

        model = STGCNPP(num_classes=60, in_channels=3, num_person=2)
        model.eval()
        dummy = torch.randn(1, 2, 100, 17, 3)
        with torch.inference_mode():
            output = model(dummy)
        assert output.shape == (1, 60)

    def test_adjacency_matrix_construction(self) -> None:
        """Test COCO skeleton adjacency matrix is valid."""
        from backend.services.stgcn_loader import build_coco_adjacency

        adj = build_coco_adjacency()
        assert adj.shape == (3, 17, 17)
        # Self-connections on diagonal
        for i in range(17):
            assert adj[0, i, i] == 1.0

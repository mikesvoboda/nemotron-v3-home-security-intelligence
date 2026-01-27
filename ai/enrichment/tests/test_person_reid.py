"""Unit tests for PersonReID person re-identification model.

Tests cover:
- ReIDResult dataclass
- PersonReID initialization
- Image preprocessing
- Embedding extraction (mocked model)
- Cosine similarity computation
- Same/different person matching
- Factory function load_person_reid
- Edge cases and error handling

Note: torchvision is imported at module level to avoid registration
conflicts when running tests in parallel with pytest-xdist.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch
from PIL import Image

# Import torchvision.transforms at module level to avoid registration
# conflicts when running with pytest-xdist
from torchvision import transforms

from ai.enrichment.models.person_reid import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMBEDDING_DIMENSION,
    IMAGENET_MEAN,
    IMAGENET_STD,
    OSNET_INPUT_HEIGHT,
    OSNET_INPUT_WIDTH,
    PersonReID,
    ReIDResult,
    load_person_reid,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample RGB person crop image for testing."""
    # Create a 128x256 RGB image (width x height, typical person crop aspect ratio)
    return Image.new("RGB", (128, 256), color="blue")


@pytest.fixture
def sample_image_small() -> Image.Image:
    """Create a small sample image."""
    return Image.new("RGB", (64, 128), color="red")


@pytest.fixture
def sample_image_grayscale() -> Image.Image:
    """Create a grayscale image that needs conversion."""
    return Image.new("L", (100, 200), color=128)


@pytest.fixture
def sample_numpy_image() -> np.ndarray:
    """Create a numpy array image."""
    return np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8)


@pytest.fixture
def valid_embedding() -> list[float]:
    """Create a valid 512-dimensional normalized embedding."""
    emb = np.random.randn(EMBEDDING_DIMENSION).astype(np.float32)
    emb = emb / np.linalg.norm(emb)  # Normalize
    return emb.tolist()


@pytest.fixture
def different_embedding() -> list[float]:
    """Create a different 512-dimensional normalized embedding."""
    # Use a different random seed to ensure different values
    np.random.seed(42)
    emb = np.random.randn(EMBEDDING_DIMENSION).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    np.random.seed(None)  # Reset seed
    return emb.tolist()


@pytest.fixture
def similar_embedding(valid_embedding: list[float]) -> list[float]:
    """Create an embedding similar to valid_embedding (small perturbation)."""
    emb = np.array(valid_embedding) + np.random.randn(EMBEDDING_DIMENSION) * 0.1
    emb = emb / np.linalg.norm(emb)  # Re-normalize
    return emb.tolist()


@pytest.fixture
def mock_torchreid_model() -> MagicMock:
    """Create a mock torchreid model that returns 512-dim embeddings."""
    mock_model = MagicMock()

    # Create a parameter tensor for device/dtype inference
    mock_param = torch.zeros(1, dtype=torch.float32)
    mock_model.parameters.return_value = iter([mock_param])

    # Mock forward pass to return 512-dim embedding - use side_effect for proper tensor return
    def mock_forward(x: torch.Tensor) -> torch.Tensor:
        batch_size = x.shape[0]
        # Return random embeddings
        return torch.randn(batch_size, EMBEDDING_DIMENSION)

    mock_model.side_effect = mock_forward
    mock_model.return_value = torch.randn(1, EMBEDDING_DIMENSION)
    mock_model.eval = MagicMock()
    mock_model.to = MagicMock(return_value=mock_model)
    mock_model.half = MagicMock(return_value=mock_model)

    return mock_model


# =============================================================================
# ReIDResult Tests
# =============================================================================


class TestReIDResult:
    """Tests for ReIDResult dataclass."""

    def test_create_result(self, valid_embedding: list[float]) -> None:
        """ReIDResult stores embedding and hash correctly."""
        result = ReIDResult(
            embedding=valid_embedding,
            embedding_hash="abc123def456",  # pragma: allowlist secret
        )

        assert result.embedding == valid_embedding
        assert result.embedding_hash == "abc123def456"  # pragma: allowlist secret

    def test_to_dict(self, valid_embedding: list[float]) -> None:
        """to_dict returns correct dictionary representation."""
        result = ReIDResult(
            embedding=valid_embedding,
            embedding_hash="test_hash",
        )

        result_dict = result.to_dict()

        assert result_dict["embedding"] == valid_embedding
        assert result_dict["embedding_hash"] == "test_hash"
        assert len(result_dict) == 2

    def test_embedding_length(self, valid_embedding: list[float]) -> None:
        """Embedding has expected dimension."""
        result = ReIDResult(
            embedding=valid_embedding,
            embedding_hash="test",
        )

        assert len(result.embedding) == EMBEDDING_DIMENSION


# =============================================================================
# PersonReID Initialization Tests
# =============================================================================


class TestPersonReIDInit:
    """Tests for PersonReID initialization."""

    def test_init_with_model_path(self) -> None:
        """PersonReID stores model path correctly."""
        reid = PersonReID(model_path="/models/osnet-reid/osnet_x0_25.pth")

        assert reid.model_path == "/models/osnet-reid/osnet_x0_25.pth"
        assert reid.device == "cuda:0"
        assert reid.model is None

    def test_init_without_model_path(self) -> None:
        """PersonReID allows None model_path for pretrained weights."""
        reid = PersonReID(model_path=None)

        assert reid.model_path is None
        assert reid.model is None

    def test_init_with_cpu_device(self) -> None:
        """PersonReID accepts CPU device."""
        reid = PersonReID(model_path=None, device="cpu")

        assert reid.device == "cpu"

    def test_init_with_specific_cuda_device(self) -> None:
        """PersonReID accepts specific CUDA device."""
        reid = PersonReID(model_path=None, device="cuda:1")

        assert reid.device == "cuda:1"


# =============================================================================
# PersonReID Preprocessing Tests
# =============================================================================


class TestPersonReIDPreprocessing:
    """Tests for PersonReID image preprocessing."""

    def test_preprocess_pil_image(
        self, sample_image: Image.Image, mock_torchreid_model: MagicMock
    ) -> None:
        """Preprocessing converts PIL Image to correct tensor shape."""

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_torchreid_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        tensor = reid._preprocess(sample_image)

        # Should be (1, 3, 256, 128)
        assert tensor.shape == (1, 3, OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)
        assert tensor.dtype == torch.float32

    def test_preprocess_numpy_array(
        self, sample_numpy_image: np.ndarray, mock_torchreid_model: MagicMock
    ) -> None:
        """Preprocessing converts numpy array to tensor."""

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_torchreid_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        tensor = reid._preprocess(sample_numpy_image)

        assert tensor.shape == (1, 3, OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)

    def test_preprocess_grayscale_converts_to_rgb(
        self, sample_image_grayscale: Image.Image, mock_torchreid_model: MagicMock
    ) -> None:
        """Preprocessing converts grayscale to RGB."""

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_torchreid_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        tensor = reid._preprocess(sample_image_grayscale)

        # Should still be 3 channels after conversion
        assert tensor.shape[1] == 3


# =============================================================================
# PersonReID Embedding Extraction Tests
# =============================================================================


class TestPersonReIDExtractEmbedding:
    """Tests for PersonReID embedding extraction."""

    def test_extract_embedding_returns_result(self, sample_image: Image.Image) -> None:
        """extract_embedding returns ReIDResult with correct structure."""

        # Create a mock model that returns proper embeddings when called
        mock_model = MagicMock()
        mock_model.parameters = lambda: iter([torch.zeros(1, dtype=torch.float32)])
        mock_model.return_value = torch.randn(1, EMBEDDING_DIMENSION)

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        result = reid.extract_embedding(sample_image)

        assert isinstance(result, ReIDResult)
        assert len(result.embedding) == EMBEDDING_DIMENSION
        assert len(result.embedding_hash) == 16  # First 16 chars of SHA-256

    def test_extract_embedding_normalizes(self, sample_image: Image.Image) -> None:
        """Embedding is L2 normalized to unit length."""

        # Create mock model returning non-normalized embedding
        mock_model = MagicMock()
        mock_model.parameters = lambda: iter([torch.zeros(1, dtype=torch.float32)])
        mock_model.return_value = torch.randn(1, EMBEDDING_DIMENSION) * 10

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        result = reid.extract_embedding(sample_image)

        # Check normalization
        norm = np.linalg.norm(result.embedding)
        assert np.isclose(norm, 1.0, atol=1e-5)

    def test_extract_embedding_generates_unique_hash(self, sample_image: Image.Image) -> None:
        """Each embedding gets a unique hash based on its values."""

        # Create mock model that returns different embeddings on each call
        # Use a lambda for parameters() that returns a fresh iterator each time
        mock_model = MagicMock()
        mock_model.parameters = lambda: iter([torch.zeros(1, dtype=torch.float32)])
        mock_model.side_effect = [
            torch.randn(1, EMBEDDING_DIMENSION),
            torch.randn(1, EMBEDDING_DIMENSION),
        ]

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        result1 = reid.extract_embedding(sample_image)
        result2 = reid.extract_embedding(sample_image)

        # Hashes should be different for different embeddings
        assert result1.embedding_hash != result2.embedding_hash

    def test_extract_embedding_model_not_loaded_raises(self, sample_image: Image.Image) -> None:
        """extract_embedding raises RuntimeError if model not loaded."""
        reid = PersonReID(model_path=None)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            reid.extract_embedding(sample_image)

    def test_extract_embedding_handles_tuple_output(self, sample_image: Image.Image) -> None:
        """extract_embedding handles models that return (global_feat, local_feat)."""

        # Create mock model that returns tuple (global_feat, local_feat)
        global_feat = torch.randn(1, EMBEDDING_DIMENSION)
        local_feat = torch.randn(1, 256)  # Some other size

        mock_model = MagicMock()
        mock_model.parameters = lambda: iter([torch.zeros(1, dtype=torch.float32)])
        mock_model.return_value = (global_feat, local_feat)

        reid = PersonReID(model_path=None, device="cpu")
        reid.model = mock_model
        reid.device = "cpu"

        reid._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        result = reid.extract_embedding(sample_image)

        # Should use global_feat
        assert len(result.embedding) == EMBEDDING_DIMENSION


# =============================================================================
# PersonReID Similarity Computation Tests
# =============================================================================


class TestPersonReIDSimilarity:
    """Tests for PersonReID similarity computation."""

    def test_compute_similarity_identical(self, valid_embedding: list[float]) -> None:
        """Identical embeddings have similarity of 1.0."""
        similarity = PersonReID.compute_similarity(valid_embedding, valid_embedding)

        assert np.isclose(similarity, 1.0, atol=1e-5)

    def test_compute_similarity_orthogonal(self) -> None:
        """Orthogonal embeddings have similarity of 0.0."""
        # Create two orthogonal vectors
        emb1 = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
        emb2 = [0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSION - 2)

        similarity = PersonReID.compute_similarity(emb1, emb2)

        assert np.isclose(similarity, 0.0, atol=1e-5)

    def test_compute_similarity_opposite(self) -> None:
        """Opposite embeddings have similarity of -1.0."""
        emb1 = [1.0 / np.sqrt(EMBEDDING_DIMENSION)] * EMBEDDING_DIMENSION
        emb2 = [-1.0 / np.sqrt(EMBEDDING_DIMENSION)] * EMBEDDING_DIMENSION

        similarity = PersonReID.compute_similarity(emb1, emb2)

        assert np.isclose(similarity, -1.0, atol=1e-5)

    def test_compute_similarity_range(
        self, valid_embedding: list[float], different_embedding: list[float]
    ) -> None:
        """Similarity is always in range [-1, 1]."""
        similarity = PersonReID.compute_similarity(valid_embedding, different_embedding)

        assert -1.0 <= similarity <= 1.0

    def test_compute_similarity_zero_vector(self, valid_embedding: list[float]) -> None:
        """Similarity with zero vector returns 0.0."""
        zero_emb = [0.0] * EMBEDDING_DIMENSION

        similarity = PersonReID.compute_similarity(valid_embedding, zero_emb)

        assert similarity == 0.0

    def test_compute_similarity_symmetric(
        self, valid_embedding: list[float], different_embedding: list[float]
    ) -> None:
        """Similarity is symmetric: sim(a, b) == sim(b, a)."""
        sim_ab = PersonReID.compute_similarity(valid_embedding, different_embedding)
        sim_ba = PersonReID.compute_similarity(different_embedding, valid_embedding)

        assert np.isclose(sim_ab, sim_ba, atol=1e-10)


# =============================================================================
# PersonReID Same Person Matching Tests
# =============================================================================


class TestPersonReIDIsSamePerson:
    """Tests for PersonReID same person matching."""

    def test_is_same_person_identical(self, valid_embedding: list[float]) -> None:
        """Identical embeddings are recognized as same person."""
        assert PersonReID.is_same_person(valid_embedding, valid_embedding)

    def test_is_same_person_similar_above_threshold(self, valid_embedding: list[float]) -> None:
        """Similar embeddings above threshold are same person."""
        # Create very similar embedding (very small perturbation to guarantee high similarity)
        # Use a deterministic small perturbation to ensure similarity > 0.7
        np.random.seed(123)  # Set seed for reproducibility
        similar = np.array(valid_embedding) + np.random.randn(EMBEDDING_DIMENSION) * 0.01
        similar = (similar / np.linalg.norm(similar)).tolist()
        np.random.seed(None)  # Reset seed

        # Similarity should be very high (> 0.99 with such small perturbation)
        similarity = PersonReID.compute_similarity(valid_embedding, similar)
        assert similarity > DEFAULT_SIMILARITY_THRESHOLD

        assert PersonReID.is_same_person(valid_embedding, similar)

    def test_is_same_person_different_below_threshold(
        self, valid_embedding: list[float], different_embedding: list[float]
    ) -> None:
        """Different embeddings below threshold are not same person."""
        # Random embeddings typically have low similarity
        similarity = PersonReID.compute_similarity(valid_embedding, different_embedding)

        # If similarity is actually low, verify is_same_person returns False
        if similarity <= DEFAULT_SIMILARITY_THRESHOLD:
            assert not PersonReID.is_same_person(valid_embedding, different_embedding)

    def test_is_same_person_custom_threshold(self, valid_embedding: list[float]) -> None:
        """Custom threshold is respected."""
        # Create slightly similar embedding
        slightly_similar = np.array(valid_embedding) + np.random.randn(EMBEDDING_DIMENSION) * 0.2
        slightly_similar = (slightly_similar / np.linalg.norm(slightly_similar)).tolist()

        # With very low threshold, should match
        assert PersonReID.is_same_person(valid_embedding, slightly_similar, threshold=0.0)

        # With very high threshold (0.99), should not match
        assert not PersonReID.is_same_person(valid_embedding, slightly_similar, threshold=0.99)

    def test_is_same_person_default_threshold(self) -> None:
        """Default threshold is 0.7."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.7


# =============================================================================
# PersonReID Model Loading Tests
# =============================================================================


class TestPersonReIDModelLoading:
    """Tests for PersonReID model loading."""

    def test_load_model_with_torchreid(self, mock_torchreid_model: MagicMock) -> None:
        """load_model uses torchreid when available."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)
        mock_torchreid.utils.load_pretrained_weights = MagicMock()

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = PersonReID(model_path=None, device="cpu")
            result = reid.load_model()

            # Should call build_model
            mock_torchreid.models.build_model.assert_called_once_with(
                name="osnet_x0_25",
                num_classes=1,
                pretrained=True,
            )

            # Should not load custom weights when path is None
            mock_torchreid.utils.load_pretrained_weights.assert_not_called()

            # Should return self for chaining
            assert result is reid

    def test_load_model_with_custom_weights(self, mock_torchreid_model: MagicMock) -> None:
        """load_model loads custom weights when path provided."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)
        mock_torchreid.utils.load_pretrained_weights = MagicMock()

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = PersonReID(model_path="/custom/weights.pth", device="cpu")
            reid.load_model()

            # Should call load_pretrained_weights
            mock_torchreid.utils.load_pretrained_weights.assert_called_once_with(
                mock_torchreid_model, "/custom/weights.pth"
            )

    def test_load_model_creates_transform(self, mock_torchreid_model: MagicMock) -> None:
        """load_model creates preprocessing transform."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = PersonReID(model_path=None, device="cpu")
            reid.load_model()

            assert reid._transform is not None

    def test_load_model_sets_eval_mode(self, mock_torchreid_model: MagicMock) -> None:
        """load_model sets model to eval mode."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = PersonReID(model_path=None, device="cpu")
            reid.load_model()

            mock_torchreid_model.eval.assert_called_once()


# =============================================================================
# PersonReID Unload Tests
# =============================================================================


class TestPersonReIDUnload:
    """Tests for PersonReID model unloading."""

    def test_unload_clears_model(self, mock_torchreid_model: MagicMock) -> None:
        """unload clears the model reference."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = PersonReID(model_path=None, device="cpu")
            reid.load_model()

            assert reid.model is not None

            reid.unload()

            assert reid.model is None

    def test_unload_when_not_loaded(self) -> None:
        """unload is safe when model not loaded."""
        reid = PersonReID(model_path=None)

        # Should not raise
        reid.unload()

        assert reid.model is None


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestLoadPersonReID:
    """Tests for load_person_reid factory function."""

    def test_load_person_reid_creates_and_loads(self, mock_torchreid_model: MagicMock) -> None:
        """load_person_reid creates and loads model."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = load_person_reid(model_path=None)

            assert isinstance(reid, PersonReID)
            assert reid.model is not None

    def test_load_person_reid_with_path(self, mock_torchreid_model: MagicMock) -> None:
        """load_person_reid passes model_path correctly."""
        import sys

        # Create mock torchreid module
        mock_torchreid = MagicMock()
        mock_torchreid.models.build_model = MagicMock(return_value=mock_torchreid_model)
        mock_torchreid.utils.load_pretrained_weights = MagicMock()

        with (
            patch("ai.enrichment.models.person_reid.torch.cuda.is_available", return_value=False),
            patch.dict(sys.modules, {"torchreid": mock_torchreid}),
        ):
            reid = load_person_reid(model_path="/custom/path.pth")

            assert reid.model_path == "/custom/path.pth"


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_embedding_dimension(self) -> None:
        """Embedding dimension is 512 for OSNet-x0.25."""
        assert EMBEDDING_DIMENSION == 512

    def test_input_dimensions(self) -> None:
        """Input dimensions are correct for person re-ID."""
        assert OSNET_INPUT_HEIGHT == 256
        assert OSNET_INPUT_WIDTH == 128

    def test_imagenet_normalization(self) -> None:
        """ImageNet normalization values are correct."""
        assert IMAGENET_MEAN == [0.485, 0.456, 0.406]
        assert IMAGENET_STD == [0.229, 0.224, 0.225]

    def test_default_threshold(self) -> None:
        """Default similarity threshold is 0.7."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.7


# =============================================================================
# Hash Generation Tests
# =============================================================================


class TestEmbeddingHash:
    """Tests for embedding hash generation."""

    def test_hash_length(self, valid_embedding: list[float]) -> None:
        """Embedding hash is 16 characters."""
        emb_array = np.array(valid_embedding)
        embedding_hash = hashlib.sha256(emb_array.tobytes()).hexdigest()[:16]

        assert len(embedding_hash) == 16

    def test_hash_is_deterministic(self, valid_embedding: list[float]) -> None:
        """Same embedding produces same hash."""
        emb_array = np.array(valid_embedding)
        hash1 = hashlib.sha256(emb_array.tobytes()).hexdigest()[:16]
        hash2 = hashlib.sha256(emb_array.tobytes()).hexdigest()[:16]

        assert hash1 == hash2

    def test_hash_is_unique(
        self, valid_embedding: list[float], different_embedding: list[float]
    ) -> None:
        """Different embeddings produce different hashes."""
        hash1 = hashlib.sha256(np.array(valid_embedding).tobytes()).hexdigest()[:16]
        hash2 = hashlib.sha256(np.array(different_embedding).tobytes()).hexdigest()[:16]

        assert hash1 != hash2


# =============================================================================
# Standalone OSNet Architecture Tests
# =============================================================================


class TestStandaloneOSNet:
    """Tests for standalone OSNet architecture (torchreid-free loading)."""

    def test_create_osnet_x0_25_returns_model(self) -> None:
        """create_osnet_x0_25 returns an OSNet model instance."""
        from ai.enrichment.models.person_reid import OSNet, create_osnet_x0_25

        model = create_osnet_x0_25()
        assert isinstance(model, OSNet)

    def test_create_osnet_x0_25_feature_dimension(self) -> None:
        """OSNet-x0.25 has 512-dimensional feature output."""
        from ai.enrichment.models.person_reid import create_osnet_x0_25

        model = create_osnet_x0_25()
        assert model.feature_dim == EMBEDDING_DIMENSION

    def test_create_osnet_x0_25_forward_pass(self) -> None:
        """OSNet-x0.25 produces correct output shape."""
        from ai.enrichment.models.person_reid import create_osnet_x0_25

        model = create_osnet_x0_25()
        model.eval()

        # Create dummy input: batch=1, channels=3, height=256, width=128
        dummy_input = torch.randn(1, 3, OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)

        with torch.no_grad():
            output = model(dummy_input)

        assert output.shape == (1, EMBEDDING_DIMENSION)

    def test_create_osnet_x0_25_batch_processing(self) -> None:
        """OSNet-x0.25 handles batch inputs correctly."""
        from ai.enrichment.models.person_reid import create_osnet_x0_25

        model = create_osnet_x0_25()
        model.eval()

        batch_size = 4
        dummy_input = torch.randn(batch_size, 3, OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)

        with torch.no_grad():
            output = model(dummy_input)

        assert output.shape == (batch_size, EMBEDDING_DIMENSION)

    def test_load_direct_weights_requires_model_path(self) -> None:
        """_load_direct_weights raises ImportError without model_path."""
        reid = PersonReID(model_path=None, device="cpu")

        with pytest.raises(ImportError, match="no model_path specified"):
            reid._load_direct_weights()

    def test_osnet_parameter_count(self) -> None:
        """OSNet-x0.25 has expected parameter count (~200-300K)."""
        from ai.enrichment.models.person_reid import create_osnet_x0_25

        model = create_osnet_x0_25()
        total_params = sum(p.numel() for p in model.parameters())

        # OSNet-x0.25 should have approximately 200-300K parameters
        assert 150_000 < total_params < 400_000

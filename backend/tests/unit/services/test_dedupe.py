"""Unit tests for file deduplication service.

Tests cover:
- compute_file_hash() - File reading, chunk processing, error handling
- DedupeService.__init__() - Redis client initialization
- is_duplicate() - Redis cache behavior, database fallback
- mark_processed() - TTL handling
- cleanup_orphaned_keys() - Orphan key detection
- ensure_key_has_ttl() - TTL maintenance
- is_duplicate_and_mark() - Atomic check and mark operation
- clear_hash() - Hash removal
- get_dedupe_service() - Singleton management
"""

import hashlib
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.dedupe import (
    DEDUPE_KEY_PREFIX,
    DEFAULT_DEDUPE_TTL_SECONDS,
    ORPHAN_CLEANUP_MAX_AGE_SECONDS,
    DedupeService,
    compute_file_hash,
    get_dedupe_service,
    reset_dedupe_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client with common operations pre-configured."""
    mock_client = AsyncMock()
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client._client = AsyncMock()
    mock_client._client.ttl = AsyncMock(return_value=300)
    mock_client._client.expire = AsyncMock(return_value=True)
    mock_client._client.scan_iter = AsyncMock()
    return mock_client


@pytest.fixture
def temp_file() -> str:
    """Create a temporary file with known content for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".jpg") as f:
        f.write(b"test content for hashing")
        return f.name


@pytest.fixture
def empty_temp_file() -> str:
    """Create an empty temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".jpg") as f:
        return f.name


@pytest.fixture
def large_temp_file() -> str:
    """Create a large temporary file (>8192 bytes) for chunk testing."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".jpg") as f:
        # Write 32KB of data to test chunked reading
        f.write(b"x" * 32768)
        return f.name


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the dedupe service singleton before each test."""
    reset_dedupe_service()


# =============================================================================
# compute_file_hash() Tests
# =============================================================================


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_compute_hash_normal_file(self, temp_file: str) -> None:
        """Test computing hash of a normal file."""
        result = compute_file_hash(temp_file)
        assert result is not None
        assert len(result) == 64  # SHA256 hex string is 64 characters
        # Verify it's a valid hex string
        int(result, 16)

    def test_compute_hash_returns_consistent_result(self, temp_file: str) -> None:
        """Test that hash computation is deterministic."""
        hash1 = compute_file_hash(temp_file)
        hash2 = compute_file_hash(temp_file)
        assert hash1 == hash2

    def test_compute_hash_nonexistent_file(self) -> None:
        """Test computing hash of a file that doesn't exist."""
        result = compute_file_hash("/nonexistent/path/to/file.jpg")
        assert result is None

    def test_compute_hash_empty_file(self, empty_temp_file: str) -> None:
        """Test computing hash of an empty file returns None."""
        result = compute_file_hash(empty_temp_file)
        assert result is None

    def test_compute_hash_large_file(self, large_temp_file: str) -> None:
        """Test computing hash of a file larger than chunk size."""
        result = compute_file_hash(large_temp_file)
        assert result is not None
        assert len(result) == 64

        # Verify the hash matches what we expect
        expected_hash = hashlib.sha256(b"x" * 32768).hexdigest()
        assert result == expected_hash

    def test_compute_hash_permission_denied(self) -> None:
        """Test computing hash when permission is denied."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            # Make file unreadable
            Path(temp_path).chmod(0o000)
            result = compute_file_hash(temp_path)
            # Should return None due to permission error
            assert result is None
        finally:
            # Restore permissions for cleanup
            Path(temp_path).chmod(0o644)
            Path(temp_path).unlink()

    def test_compute_hash_with_special_characters_in_path(self) -> None:
        """Test computing hash with special characters in file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with special characters in name
            file_path = Path(tmpdir) / "test file with spaces (1).jpg"
            file_path.write_bytes(b"test content")
            result = compute_file_hash(str(file_path))
            assert result is not None

    def test_compute_hash_different_content_different_hash(self) -> None:
        """Test that different file contents produce different hashes."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f1:
            f1.write(b"content 1")
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f2:
            f2.write(b"content 2")
            path2 = f2.name

        try:
            hash1 = compute_file_hash(path1)
            hash2 = compute_file_hash(path2)
            assert hash1 != hash2
        finally:
            Path(path1).unlink()
            Path(path2).unlink()


# =============================================================================
# DedupeService.__init__() Tests
# =============================================================================


class TestDedupeServiceInit:
    """Tests for DedupeService initialization."""

    def test_init_with_redis_client(self, mock_redis_client: AsyncMock) -> None:
        """Test initialization with Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            service = DedupeService(redis_client=mock_redis_client)
            assert service._redis_client == mock_redis_client

    def test_init_without_redis_client(self) -> None:
        """Test initialization without Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            service = DedupeService()
            assert service._redis_client is None

    def test_init_default_ttl(self) -> None:
        """Test initialization with default TTL."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])  # No dedupe_ttl_seconds
            service = DedupeService()
            assert service._ttl_seconds == DEFAULT_DEDUPE_TTL_SECONDS

    def test_init_custom_ttl_from_parameter(self) -> None:
        """Test initialization with custom TTL from parameter."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(ttl_seconds=600)
            assert service._ttl_seconds == 600

    def test_init_ttl_from_settings(self) -> None:
        """Test initialization with TTL from settings."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(dedupe_ttl_seconds=900)
            service = DedupeService()
            assert service._ttl_seconds == 900


class TestGetRedisKey:
    """Tests for _get_redis_key method."""

    def test_get_redis_key_format(self) -> None:
        """Test that Redis key follows expected format."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            key = service._get_redis_key("abc123")
            assert key == f"{DEDUPE_KEY_PREFIX}abc123"

    def test_get_redis_key_with_long_hash(self) -> None:
        """Test Redis key with full SHA256 hash."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            long_hash = "a" * 64
            key = service._get_redis_key(long_hash)
            assert key == f"{DEDUPE_KEY_PREFIX}{long_hash}"


# =============================================================================
# is_duplicate() Tests
# =============================================================================


class TestIsDuplicate:
    """Tests for is_duplicate method."""

    @pytest.mark.asyncio
    async def test_is_duplicate_with_precomputed_hash_found_in_redis(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test checking duplicate with precomputed hash found in Redis."""
        mock_redis_client.exists.return_value = 1
        mock_redis_client._client.ttl.return_value = 300

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(temp_file, "known_hash")

            assert is_dup is True
            assert file_hash == "known_hash"

    @pytest.mark.asyncio
    async def test_is_duplicate_with_precomputed_hash_not_found(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test checking duplicate with precomputed hash not in Redis."""
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(temp_file, "known_hash")

            assert is_dup is False
            assert file_hash == "known_hash"

    @pytest.mark.asyncio
    async def test_is_duplicate_computes_hash_if_not_provided(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test that hash is computed if not provided."""
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(temp_file)

            assert is_dup is False
            assert file_hash is not None
            assert len(file_hash) == 64

    @pytest.mark.asyncio
    async def test_is_duplicate_returns_false_none_when_hash_fails(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that is_duplicate returns (False, None) when hash computation fails."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate("/nonexistent/file.jpg")

            assert is_dup is False
            assert file_hash is None

    @pytest.mark.asyncio
    async def test_is_duplicate_without_redis_client(self, temp_file: str) -> None:
        """Test is_duplicate without Redis client (fail-open behavior)."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()  # No Redis client
            is_dup, file_hash = await service.is_duplicate(temp_file)

            # Should allow processing (fail-open)
            assert is_dup is False
            assert file_hash is not None

    @pytest.mark.asyncio
    async def test_is_duplicate_redis_error_returns_none(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test is_duplicate handles Redis errors gracefully."""
        mock_redis_client.exists.side_effect = Exception("Redis connection failed")

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(temp_file, "known_hash")

            # Should fail-open when Redis fails
            assert is_dup is False
            assert file_hash == "known_hash"


# =============================================================================
# _check_redis() Tests
# =============================================================================


class TestCheckRedis:
    """Tests for _check_redis method."""

    @pytest.mark.asyncio
    async def test_check_redis_key_exists(self, mock_redis_client: AsyncMock) -> None:
        """Test _check_redis when key exists."""
        mock_redis_client.exists.return_value = 1
        mock_redis_client._client.ttl.return_value = 300

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service._check_redis("test_hash")

            assert result is True
            mock_redis_client.exists.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_key_not_exists(self, mock_redis_client: AsyncMock) -> None:
        """Test _check_redis when key does not exist."""
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service._check_redis("test_hash")

            assert result is False

    @pytest.mark.asyncio
    async def test_check_redis_no_client(self) -> None:
        """Test _check_redis returns None when no Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            result = await service._check_redis("test_hash")

            assert result is None

    @pytest.mark.asyncio
    async def test_check_redis_exception(self, mock_redis_client: AsyncMock) -> None:
        """Test _check_redis handles exceptions."""
        mock_redis_client.exists.side_effect = Exception("Connection error")

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service._check_redis("test_hash")

            # Should return None on error (fail-open)
            assert result is None


# =============================================================================
# mark_processed() Tests
# =============================================================================


class TestMarkProcessed:
    """Tests for mark_processed method."""

    @pytest.mark.asyncio
    async def test_mark_processed_with_precomputed_hash(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test marking file as processed with precomputed hash."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.mark_processed(temp_file, "known_hash")

            assert result is True
            mock_redis_client.set.assert_awaited_once()
            # Verify TTL was passed
            call_kwargs = mock_redis_client.set.call_args
            assert call_kwargs[1]["expire"] == DEFAULT_DEDUPE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_mark_processed_computes_hash_if_not_provided(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test mark_processed computes hash if not provided."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.mark_processed(temp_file)

            assert result is True
            mock_redis_client.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_processed_returns_false_when_hash_fails(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test mark_processed returns False when hash computation fails."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.mark_processed("/nonexistent/file.jpg")

            assert result is False
            mock_redis_client.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mark_processed_without_redis_client(self, temp_file: str) -> None:
        """Test mark_processed without Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()  # No Redis client
            result = await service.mark_processed(temp_file)

            # Should return False when no Redis
            assert result is False

    @pytest.mark.asyncio
    async def test_mark_processed_redis_error(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test mark_processed handles Redis errors."""
        mock_redis_client.set.side_effect = Exception("Redis error")

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.mark_processed(temp_file, "known_hash")

            assert result is False

    @pytest.mark.asyncio
    async def test_mark_processed_with_custom_ttl(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test mark_processed uses custom TTL."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client, ttl_seconds=600)
            await service.mark_processed(temp_file, "known_hash")

            call_kwargs = mock_redis_client.set.call_args
            assert call_kwargs[1]["expire"] == 600


# =============================================================================
# is_duplicate_and_mark() Tests
# =============================================================================


class TestIsDuplicateAndMark:
    """Tests for is_duplicate_and_mark method."""

    @pytest.mark.asyncio
    async def test_is_duplicate_and_mark_new_file(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test atomic check and mark for new file."""
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate_and_mark(temp_file)

            assert is_dup is False
            assert file_hash is not None
            # Verify file was marked
            mock_redis_client.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_duplicate_and_mark_passes_file_path_to_mark_processed(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test that is_duplicate_and_mark passes the correct file_path to mark_processed.

        This test validates that the file_path parameter is correctly passed through
        to mark_processed, which stores it in Redis as the value (useful for debugging).
        The mutation test discovered that file_path could be replaced with None without
        failing existing tests.
        """
        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate_and_mark(temp_file)

            assert is_dup is False
            assert file_hash is not None

            # Verify mark_processed was called with the correct file_path
            # The set call should have been made with the file_path as the value
            call_args = mock_redis_client.set.call_args
            # Args are: (key, value, expire=ttl)
            stored_value = call_args[0][1]  # Second positional arg is the value
            assert stored_value == temp_file, (
                f"mark_processed should store file_path in Redis, "
                f"got {stored_value} instead of {temp_file}"
            )

    @pytest.mark.asyncio
    async def test_is_duplicate_and_mark_duplicate_file(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test atomic check for duplicate file (no mark needed)."""
        mock_redis_client.exists.return_value = 1
        mock_redis_client._client.ttl.return_value = 300

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate_and_mark(temp_file)

            assert is_dup is True
            assert file_hash is not None
            # Should not mark when duplicate
            mock_redis_client.set.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_is_duplicate_and_mark_hash_fails(self, mock_redis_client: AsyncMock) -> None:
        """Test atomic check returns (False, None) when hash fails."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate_and_mark("/nonexistent/file.jpg")

            assert is_dup is False
            assert file_hash is None


# =============================================================================
# clear_hash() Tests
# =============================================================================


class TestClearHash:
    """Tests for clear_hash method."""

    @pytest.mark.asyncio
    async def test_clear_hash_success(self, mock_redis_client: AsyncMock) -> None:
        """Test successfully clearing a hash."""
        mock_redis_client.delete.return_value = 1

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.clear_hash("test_hash")

            assert result is True
            mock_redis_client.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_hash_not_found(self, mock_redis_client: AsyncMock) -> None:
        """Test clearing a hash that doesn't exist."""
        mock_redis_client.delete.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.clear_hash("nonexistent_hash")

            assert result is False

    @pytest.mark.asyncio
    async def test_clear_hash_without_redis(self) -> None:
        """Test clearing hash without Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            result = await service.clear_hash("test_hash")

            assert result is False

    @pytest.mark.asyncio
    async def test_clear_hash_redis_error(self, mock_redis_client: AsyncMock) -> None:
        """Test clearing hash when Redis fails."""
        mock_redis_client.delete.side_effect = Exception("Redis error")

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.clear_hash("test_hash")

            assert result is False


# =============================================================================
# cleanup_orphaned_keys() Tests
# =============================================================================


class TestCleanupOrphanedKeys:
    """Tests for cleanup_orphaned_keys method."""

    @pytest.mark.asyncio
    async def test_cleanup_orphans_no_redis_client(self) -> None:
        """Test cleanup returns 0 when no Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            count = await service.cleanup_orphaned_keys()
            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_orphans_no_underlying_client(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup returns 0 when underlying client is None."""
        mock_redis_client._client = None

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()
            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_orphans_finds_orphaned_keys(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup detects and fixes orphaned keys."""

        # Create async generator for scan_iter
        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            for key in ["dedupe:hash1", "dedupe:hash2", "dedupe:hash3"]:
                yield key

        mock_redis_client._client.scan_iter = mock_scan_iter
        # Return -1 (no TTL) for all keys
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            assert count == 3
            # Verify expire was called for each orphan
            assert mock_redis_client._client.expire.await_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_orphans_skips_keys_with_ttl(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup skips keys that already have TTL."""

        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            for key in ["dedupe:hash1", "dedupe:hash2"]:
                yield key

        mock_redis_client._client.scan_iter = mock_scan_iter
        # First key has TTL, second doesn't
        mock_redis_client._client.ttl = AsyncMock(side_effect=[300, -1])
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            # Only one orphan
            assert count == 1
            assert mock_redis_client._client.expire.await_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_orphans_skips_nonexistent_keys(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test cleanup skips keys that don't exist (ttl=-2)."""

        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            yield "dedupe:hash1"

        mock_redis_client._client.scan_iter = mock_scan_iter
        # TTL of -2 means key doesn't exist
        mock_redis_client._client.ttl = AsyncMock(return_value=-2)
        mock_redis_client._client.expire = AsyncMock()

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            assert count == 0
            mock_redis_client._client.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cleanup_orphans_handles_ttl_error(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup handles TTL check errors gracefully."""

        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            for key in ["dedupe:hash1", "dedupe:hash2"]:
                yield key

        mock_redis_client._client.scan_iter = mock_scan_iter
        # First key causes error, second is orphan
        mock_redis_client._client.ttl = AsyncMock(side_effect=[Exception("Error"), -1])
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            # Should still process second key
            assert count == 1

    @pytest.mark.asyncio
    async def test_cleanup_orphans_scan_error(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup handles scan errors gracefully."""

        class ErrorAsyncIterator:
            """Async iterator that raises an exception on iteration."""

            def __aiter__(self) -> ErrorAsyncIterator:
                return self

            async def __anext__(self) -> Any:
                raise Exception("Scan error")

        mock_redis_client._client.scan_iter = MagicMock(return_value=ErrorAsyncIterator())

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            count = await service.cleanup_orphaned_keys()

            # Should return 0 on error
            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_orphans_uses_correct_max_age(self, mock_redis_client: AsyncMock) -> None:
        """Test cleanup sets TTL to ORPHAN_CLEANUP_MAX_AGE_SECONDS."""

        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            yield "dedupe:hash1"

        mock_redis_client._client.scan_iter = mock_scan_iter
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            await service.cleanup_orphaned_keys()

            mock_redis_client._client.expire.assert_awaited_with(
                "dedupe:hash1", ORPHAN_CLEANUP_MAX_AGE_SECONDS
            )


# =============================================================================
# ensure_key_has_ttl() Tests
# =============================================================================


class TestEnsureKeyHasTtl:
    """Tests for ensure_key_has_ttl method."""

    @pytest.mark.asyncio
    async def test_ensure_ttl_no_redis_client(self) -> None:
        """Test ensure_key_has_ttl returns False without Redis client."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            result = await service.ensure_key_has_ttl("test_hash")
            assert result is False

    @pytest.mark.asyncio
    async def test_ensure_ttl_no_underlying_client(self, mock_redis_client: AsyncMock) -> None:
        """Test ensure_key_has_ttl returns False without underlying client."""
        mock_redis_client._client = None

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.ensure_key_has_ttl("test_hash")
            assert result is False

    @pytest.mark.asyncio
    async def test_ensure_ttl_key_has_ttl(self, mock_redis_client: AsyncMock) -> None:
        """Test ensure_key_has_ttl when key already has TTL."""
        mock_redis_client._client.ttl = AsyncMock(return_value=300)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.ensure_key_has_ttl("test_hash")

            assert result is True
            mock_redis_client._client.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ensure_ttl_key_missing_ttl(self, mock_redis_client: AsyncMock) -> None:
        """Test ensure_key_has_ttl when key is missing TTL."""
        mock_redis_client._client.ttl = AsyncMock(return_value=-1)
        mock_redis_client._client.expire = AsyncMock(return_value=True)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client, ttl_seconds=600)
            result = await service.ensure_key_has_ttl("test_hash")

            assert result is True
            mock_redis_client._client.expire.assert_awaited_once()
            # Verify TTL value matches service TTL
            call_args = mock_redis_client._client.expire.call_args
            assert call_args[0][1] == 600

    @pytest.mark.asyncio
    async def test_ensure_ttl_error(self, mock_redis_client: AsyncMock) -> None:
        """Test ensure_key_has_ttl handles errors."""
        mock_redis_client._client.ttl = AsyncMock(side_effect=Exception("Redis error"))

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            result = await service.ensure_key_has_ttl("test_hash")

            assert result is False


# =============================================================================
# get_dedupe_service() Tests
# =============================================================================


class TestGetDedupeService:
    """Tests for get_dedupe_service singleton function."""

    def test_get_dedupe_service_creates_singleton(self) -> None:
        """Test that get_dedupe_service creates a singleton."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service1 = get_dedupe_service()
            service2 = get_dedupe_service()
            assert service1 is service2

    def test_get_dedupe_service_with_redis_client(self, mock_redis_client: AsyncMock) -> None:
        """Test get_dedupe_service uses provided Redis client on first call."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = get_dedupe_service(redis_client=mock_redis_client)
            assert service._redis_client == mock_redis_client


class TestResetDedupeService:
    """Tests for reset_dedupe_service function."""

    def test_reset_dedupe_service_clears_singleton(self) -> None:
        """Test that reset_dedupe_service clears the singleton."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service1 = get_dedupe_service()
            reset_dedupe_service()
            service2 = get_dedupe_service()
            assert service1 is not service2


# =============================================================================
# Constants Tests
# =============================================================================


class TestDedupeConstants:
    """Tests for module constants."""

    def test_default_ttl_value(self) -> None:
        """Test default TTL is 5 minutes (300 seconds)."""
        assert DEFAULT_DEDUPE_TTL_SECONDS == 300

    def test_key_prefix_format(self) -> None:
        """Test key prefix is correct."""
        assert DEDUPE_KEY_PREFIX == "dedupe:"

    def test_orphan_max_age_value(self) -> None:
        """Test orphan cleanup max age is 1 hour (3600 seconds)."""
        assert ORPHAN_CLEANUP_MAX_AGE_SECONDS == 3600


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_checks(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test handling of concurrent duplicate checks."""
        import asyncio

        mock_redis_client.exists.return_value = 0

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)

            # Run multiple checks concurrently
            results = await asyncio.gather(
                service.is_duplicate(temp_file),
                service.is_duplicate(temp_file),
                service.is_duplicate(temp_file),
            )

            # All should return consistent results
            for is_dup, file_hash in results:
                assert is_dup is False
                assert file_hash is not None

    @pytest.mark.asyncio
    async def test_very_long_file_path(self, mock_redis_client: AsyncMock) -> None:
        """Test handling of very long file paths."""
        long_path = "/very/long/path/" + "x" * 1000 + ".jpg"

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(long_path)

            # Should handle gracefully (file doesn't exist)
            assert is_dup is False
            assert file_hash is None

    def test_compute_hash_binary_file(self) -> None:
        """Test computing hash of a binary file with null bytes."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"\x00\x01\x02\xff\xfe\xfd")
            temp_path = f.name

        try:
            result = compute_file_hash(temp_path)
            assert result is not None
            assert len(result) == 64
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_redis_timeout_handling(
        self, mock_redis_client: AsyncMock, temp_file: str
    ) -> None:
        """Test handling of Redis timeout errors."""

        mock_redis_client.exists.side_effect = TimeoutError("Redis timeout")

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis_client)
            is_dup, file_hash = await service.is_duplicate(temp_file, "known_hash")

            # Should fail-open on timeout
            assert is_dup is False
            assert file_hash == "known_hash"


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================

from hypothesis import given  # noqa: E402
from hypothesis import settings as hypothesis_settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from backend.tests.strategies import sha256_hashes  # noqa: E402


class TestDedupeProperties:
    """Property-based tests for deduplication service using Hypothesis."""

    # -------------------------------------------------------------------------
    # Hash Computation Properties
    # -------------------------------------------------------------------------

    @given(content=st.binary(min_size=1, max_size=10000))
    @hypothesis_settings(max_examples=50)
    def test_hash_is_deterministic(self, content: bytes) -> None:
        """Property: Same content always produces the same hash.

        This is critical for idempotency - if the same file is processed
        twice, it must produce the same hash both times.
        """
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            hash1 = compute_file_hash(path)
            hash2 = compute_file_hash(path)
            hash3 = compute_file_hash(path)

            assert hash1 is not None
            assert hash1 == hash2, "Hash should be deterministic"
            assert hash2 == hash3, "Hash should be deterministic across calls"
        finally:
            Path(path).unlink()

    @given(content=st.binary(min_size=1, max_size=10000))
    @hypothesis_settings(max_examples=30)
    def test_hash_length_is_constant(self, content: bytes) -> None:
        """Property: SHA256 hash is always 64 hex characters."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            file_hash = compute_file_hash(path)
            assert file_hash is not None
            assert len(file_hash) == 64, f"Hash length should be 64, got {len(file_hash)}"
            # Verify it's a valid hex string
            int(file_hash, 16)
        finally:
            Path(path).unlink()

    @given(
        content1=st.binary(min_size=1, max_size=1000),
        content2=st.binary(min_size=1, max_size=1000),
    )
    @hypothesis_settings(max_examples=50)
    def test_different_content_different_hash(self, content1: bytes, content2: bytes) -> None:
        """Property: Different content produces different hashes (with high probability).

        Note: While SHA256 collisions are theoretically possible, they are
        astronomically unlikely for any realistic input.
        """
        # Skip if content is the same
        if content1 == content2:
            return

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f1:
            f1.write(content1)
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f2:
            f2.write(content2)
            path2 = f2.name

        try:
            hash1 = compute_file_hash(path1)
            hash2 = compute_file_hash(path2)

            assert hash1 is not None
            assert hash2 is not None
            assert hash1 != hash2, "Different content should produce different hashes"
        finally:
            Path(path1).unlink()
            Path(path2).unlink()

    @given(content=st.binary(min_size=1, max_size=5000))
    @hypothesis_settings(max_examples=30)
    def test_hash_matches_expected_sha256(self, content: bytes) -> None:
        """Property: compute_file_hash produces correct SHA256 output."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            computed_hash = compute_file_hash(path)
            expected_hash = hashlib.sha256(content).hexdigest()

            assert computed_hash == expected_hash, (
                f"Hash mismatch: computed={computed_hash}, expected={expected_hash}"
            )
        finally:
            Path(path).unlink()

    # -------------------------------------------------------------------------
    # Redis Key Generation Properties
    # -------------------------------------------------------------------------

    @given(file_hash=sha256_hashes)
    @hypothesis_settings(max_examples=50)
    def test_redis_key_format_consistent(self, file_hash: str) -> None:
        """Property: Redis keys always follow the prefix:hash format."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()
            key = service._get_redis_key(file_hash)

            assert key.startswith(DEDUPE_KEY_PREFIX), f"Key should start with {DEDUPE_KEY_PREFIX}"
            assert key == f"{DEDUPE_KEY_PREFIX}{file_hash}"
            assert len(key) == len(DEDUPE_KEY_PREFIX) + 64

    @given(file_hash=sha256_hashes)
    @hypothesis_settings(max_examples=30)
    def test_redis_key_is_unique_per_hash(self, file_hash: str) -> None:
        """Property: Each file hash produces a unique Redis key."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()

            key1 = service._get_redis_key(file_hash)
            key2 = service._get_redis_key(file_hash)

            # Same hash should produce same key
            assert key1 == key2

    @given(
        hash1=sha256_hashes,
        hash2=sha256_hashes,
    )
    @hypothesis_settings(max_examples=50)
    def test_different_hashes_different_keys(self, hash1: str, hash2: str) -> None:
        """Property: Different hashes produce different Redis keys."""
        if hash1 == hash2:
            return

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()

            key1 = service._get_redis_key(hash1)
            key2 = service._get_redis_key(hash2)

            assert key1 != key2, "Different hashes should produce different keys"

    # -------------------------------------------------------------------------
    # Deduplication Logic Properties
    # -------------------------------------------------------------------------

    @given(file_hash=sha256_hashes)
    @hypothesis_settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_duplicate_detection_is_deterministic(
        self,
        file_hash: str,
    ) -> None:
        """Property: Duplicate detection returns consistent results.

        Given the same Redis state, is_duplicate should always return
        the same result for the same hash.
        """

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis._client = AsyncMock()
        mock_redis._client.ttl = AsyncMock(return_value=300)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis)

            # Create a temp file for the check
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(b"test content")
                path = f.name

            try:
                result1 = await service.is_duplicate(path, file_hash)
                result2 = await service.is_duplicate(path, file_hash)

                # Both should return the same result
                assert result1 == result2, "Duplicate detection should be deterministic"
                assert result1[0] is True, "Should detect as duplicate"
                assert result1[1] == file_hash
            finally:
                Path(path).unlink()

    @given(ttl=st.integers(min_value=60, max_value=3600))
    @hypothesis_settings(max_examples=20)
    def test_ttl_configuration_respected(self, ttl: int) -> None:
        """Property: Custom TTL values are properly stored."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(ttl_seconds=ttl)
            assert service._ttl_seconds == ttl

    # -------------------------------------------------------------------------
    # Idempotency Properties
    # -------------------------------------------------------------------------

    @given(content=st.binary(min_size=1, max_size=1000))
    @hypothesis_settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_mark_processed_then_is_duplicate(self, content: bytes) -> None:
        """Property: After marking a file, it should be detected as duplicate.

        This tests the core idempotency contract: once a file is marked,
        subsequent checks should detect it as a duplicate.
        """
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # Not found initially
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis._client = AsyncMock()
        mock_redis._client.ttl = AsyncMock(return_value=300)

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis)

            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(content)
                path = f.name

            try:
                # First check - should not be duplicate
                is_dup, file_hash = await service.is_duplicate(path)
                assert is_dup is False

                # Mark as processed
                marked = await service.mark_processed(path, file_hash)
                assert marked is True

                # Now simulate Redis returning True for exists
                mock_redis.exists = AsyncMock(return_value=1)

                # Second check - should be duplicate
                is_dup2, file_hash2 = await service.is_duplicate(path, file_hash)
                assert is_dup2 is True
                assert file_hash2 == file_hash
            finally:
                Path(path).unlink()

    # -------------------------------------------------------------------------
    # Fail-Open Behavior Properties
    # -------------------------------------------------------------------------

    @given(content=st.binary(min_size=1, max_size=1000))
    @hypothesis_settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self, content: bytes) -> None:
        """Property: When Redis fails, the system allows processing (fail-open).

        This ensures availability is prioritized over duplicate prevention
        when infrastructure is unavailable.
        """
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(side_effect=Exception("Redis unavailable"))

        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService(redis_client=mock_redis)

            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(content)
                path = f.name

            try:
                is_dup, file_hash = await service.is_duplicate(path)

                # Should fail-open (allow processing)
                assert is_dup is False
                assert file_hash is not None
            finally:
                Path(path).unlink()

    @given(content=st.binary(min_size=1, max_size=1000))
    @hypothesis_settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_no_redis_allows_processing(self, content: bytes) -> None:
        """Property: Without Redis, all files are allowed to process."""
        with patch("backend.services.dedupe.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=[])
            service = DedupeService()  # No Redis client

            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(content)
                path = f.name

            try:
                is_dup, file_hash = await service.is_duplicate(path)

                # Without Redis, should always allow
                assert is_dup is False
                assert file_hash is not None
            finally:
                Path(path).unlink()

    # -------------------------------------------------------------------------
    # Empty/Invalid File Handling Properties
    # -------------------------------------------------------------------------

    @given(size=st.integers(min_value=0, max_value=0))
    @hypothesis_settings(max_examples=5)
    def test_empty_file_returns_none_hash(self, size: int) -> None:
        """Property: Empty files return None hash (cannot be deduplicated)."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            # Write nothing (empty file)
            path = f.name

        try:
            file_hash = compute_file_hash(path)
            assert file_hash is None, "Empty files should return None hash"
        finally:
            Path(path).unlink()

    @given(path_suffix=st.text(min_size=10, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @hypothesis_settings(max_examples=10)
    def test_nonexistent_file_returns_none_hash(self, path_suffix: str) -> None:
        """Property: Non-existent files return None hash."""
        path = f"/nonexistent/path/{path_suffix}.jpg"
        file_hash = compute_file_hash(path)
        assert file_hash is None, "Non-existent files should return None hash"

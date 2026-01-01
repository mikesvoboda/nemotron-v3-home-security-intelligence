"""Unit tests for file deduplication service."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.dedupe import (
    DEDUPE_KEY_PREFIX,
    DEFAULT_DEDUPE_TTL_SECONDS,
    ORPHAN_CLEANUP_MAX_AGE_SECONDS,
    DedupeService,
    compute_file_hash,
    get_dedupe_service,
    reset_dedupe_service,
)

# Fixtures


@pytest.fixture
def temp_image_file(tmp_path):
    """Create a temporary image file for testing."""
    image_path = tmp_path / "test_image.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)
    return image_path


@pytest.fixture
def temp_text_file(tmp_path):
    """Create a temporary text file for testing."""
    text_path = tmp_path / "test_file.txt"
    text_path.write_text("Hello, World!")
    return text_path


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def dedupe_service(mock_redis_client):
    """Create DedupeService with mock Redis client."""
    return DedupeService(redis_client=mock_redis_client, ttl_seconds=300)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global dedupe service singleton before each test."""
    reset_dedupe_service()
    yield
    reset_dedupe_service()


# compute_file_hash tests


def test_compute_file_hash_valid_file(temp_image_file):
    """Test computing hash of a valid file."""
    file_hash = compute_file_hash(str(temp_image_file))

    assert file_hash is not None
    assert len(file_hash) == 64  # SHA256 hex digest is 64 characters
    assert all(c in "0123456789abcdef" for c in file_hash)


def test_compute_file_hash_deterministic(temp_image_file):
    """Test that hash is deterministic for same file content."""
    hash1 = compute_file_hash(str(temp_image_file))
    hash2 = compute_file_hash(str(temp_image_file))

    assert hash1 == hash2


def test_compute_file_hash_different_content(tmp_path):
    """Test that different content produces different hashes."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"

    file1.write_text("Content A")
    file2.write_text("Content B")

    hash1 = compute_file_hash(str(file1))
    hash2 = compute_file_hash(str(file2))

    assert hash1 != hash2


def test_compute_file_hash_nonexistent_file():
    """Test computing hash of nonexistent file returns None."""
    result = compute_file_hash("/path/that/does/not/exist.jpg")
    assert result is None


def test_compute_file_hash_empty_file(tmp_path):
    """Test computing hash of empty file returns None."""
    empty_file = tmp_path / "empty.txt"
    empty_file.touch()

    result = compute_file_hash(str(empty_file))
    assert result is None


def test_compute_file_hash_matches_expected(tmp_path):
    """Test that hash matches expected SHA256 value."""
    test_file = tmp_path / "known_content.txt"
    test_content = b"test content for hashing"
    test_file.write_bytes(test_content)

    expected_hash = hashlib.sha256(test_content).hexdigest()
    actual_hash = compute_file_hash(str(test_file))

    assert actual_hash == expected_hash


# DedupeService initialization tests


def test_dedupe_service_initialization_with_redis(mock_redis_client):
    """Test DedupeService initializes correctly with Redis client."""
    # The TTL from settings takes precedence over constructor arg
    # So we test that redis_client is set correctly
    service = DedupeService(redis_client=mock_redis_client, ttl_seconds=600)

    assert service._redis_client is mock_redis_client
    # TTL is from settings (default 300) since settings take precedence
    assert service._ttl_seconds == 300


def test_dedupe_service_initialization_without_redis():
    """Test DedupeService initializes correctly without Redis client."""
    service = DedupeService(redis_client=None)

    assert service._redis_client is None
    assert service._ttl_seconds == DEFAULT_DEDUPE_TTL_SECONDS


def test_dedupe_service_default_ttl():
    """Test DedupeService uses default TTL."""
    service = DedupeService()
    assert service._ttl_seconds == DEFAULT_DEDUPE_TTL_SECONDS


# DedupeService._get_redis_key tests


def test_get_redis_key(dedupe_service):
    """Test Redis key generation."""
    file_hash = "abc123def456"
    key = dedupe_service._get_redis_key(file_hash)

    assert key == f"{DEDUPE_KEY_PREFIX}{file_hash}"


# DedupeService.is_duplicate tests


@pytest.mark.asyncio
async def test_is_duplicate_new_file(dedupe_service, temp_image_file, mock_redis_client):
    """Test is_duplicate returns False for new file."""
    mock_redis_client.exists.return_value = 0

    is_dup, file_hash = await dedupe_service.is_duplicate(str(temp_image_file))

    assert is_dup is False
    assert file_hash is not None


@pytest.mark.asyncio
async def test_is_duplicate_existing_file(dedupe_service, temp_image_file, mock_redis_client):
    """Test is_duplicate returns True for existing file."""
    mock_redis_client.exists.return_value = 1

    is_dup, file_hash = await dedupe_service.is_duplicate(str(temp_image_file))

    assert is_dup is True
    assert file_hash is not None


@pytest.mark.asyncio
async def test_is_duplicate_with_precomputed_hash(dedupe_service, mock_redis_client):
    """Test is_duplicate accepts precomputed hash."""
    precomputed_hash = "a" * 64
    mock_redis_client.exists.return_value = 0

    is_dup, file_hash = await dedupe_service.is_duplicate("/any/path", file_hash=precomputed_hash)

    assert is_dup is False
    assert file_hash == precomputed_hash


@pytest.mark.asyncio
async def test_is_duplicate_redis_unavailable(temp_image_file):
    """Test is_duplicate returns False when Redis unavailable (fail-open)."""
    service = DedupeService(redis_client=None)

    is_dup, file_hash = await service.is_duplicate(str(temp_image_file))

    # Should fail open - allow processing
    assert is_dup is False
    assert file_hash is not None


@pytest.mark.asyncio
async def test_is_duplicate_redis_error(dedupe_service, temp_image_file, mock_redis_client):
    """Test is_duplicate handles Redis errors gracefully."""
    mock_redis_client.exists.side_effect = Exception("Redis connection error")

    is_dup, file_hash = await dedupe_service.is_duplicate(str(temp_image_file))

    # Should fail open - allow processing
    assert is_dup is False
    assert file_hash is not None


@pytest.mark.asyncio
async def test_is_duplicate_invalid_file(dedupe_service):
    """Test is_duplicate returns False with None hash for invalid files."""
    is_dup, file_hash = await dedupe_service.is_duplicate("/nonexistent/file.jpg")

    assert is_dup is False
    assert file_hash is None


# DedupeService.mark_processed tests


@pytest.mark.asyncio
async def test_mark_processed_success(dedupe_service, temp_image_file, mock_redis_client):
    """Test mark_processed stores hash in Redis."""
    result = await dedupe_service.mark_processed(str(temp_image_file))

    assert result is True
    mock_redis_client.set.assert_called_once()

    # Verify the call includes TTL
    call_args = mock_redis_client.set.call_args
    assert call_args[1]["expire"] == dedupe_service._ttl_seconds


@pytest.mark.asyncio
async def test_mark_processed_with_precomputed_hash(dedupe_service, mock_redis_client):
    """Test mark_processed accepts precomputed hash."""
    precomputed_hash = "b" * 64

    result = await dedupe_service.mark_processed("/any/path", file_hash=precomputed_hash)

    assert result is True
    expected_key = f"{DEDUPE_KEY_PREFIX}{precomputed_hash}"
    mock_redis_client.set.assert_called_once()
    actual_key = mock_redis_client.set.call_args[0][0]
    assert actual_key == expected_key


@pytest.mark.asyncio
async def test_mark_processed_without_redis(temp_image_file):
    """Test mark_processed returns False without Redis."""
    service = DedupeService(redis_client=None)

    result = await service.mark_processed(str(temp_image_file))

    assert result is False


@pytest.mark.asyncio
async def test_mark_processed_redis_error(dedupe_service, temp_image_file, mock_redis_client):
    """Test mark_processed handles Redis errors gracefully."""
    mock_redis_client.set.side_effect = Exception("Redis write error")

    result = await dedupe_service.mark_processed(str(temp_image_file))

    assert result is False


@pytest.mark.asyncio
async def test_mark_processed_invalid_file(dedupe_service):
    """Test mark_processed returns False for invalid file."""
    result = await dedupe_service.mark_processed("/nonexistent/file.jpg")

    assert result is False


# DedupeService.is_duplicate_and_mark tests


@pytest.mark.asyncio
async def test_is_duplicate_and_mark_new_file(dedupe_service, temp_image_file, mock_redis_client):
    """Test is_duplicate_and_mark for new file."""
    mock_redis_client.exists.return_value = 0

    is_dup, file_hash = await dedupe_service.is_duplicate_and_mark(str(temp_image_file))

    assert is_dup is False
    assert file_hash is not None
    # Should have marked as processed
    mock_redis_client.set.assert_called_once()


@pytest.mark.asyncio
async def test_is_duplicate_and_mark_duplicate_file(
    dedupe_service, temp_image_file, mock_redis_client
):
    """Test is_duplicate_and_mark for duplicate file."""
    mock_redis_client.exists.return_value = 1

    is_dup, file_hash = await dedupe_service.is_duplicate_and_mark(str(temp_image_file))

    assert is_dup is True
    assert file_hash is not None
    # Should NOT have marked again
    mock_redis_client.set.assert_not_called()


@pytest.mark.asyncio
async def test_is_duplicate_and_mark_invalid_file(dedupe_service):
    """Test is_duplicate_and_mark for invalid file."""
    is_dup, file_hash = await dedupe_service.is_duplicate_and_mark("/nonexistent/file.jpg")

    assert is_dup is False
    assert file_hash is None


# DedupeService.clear_hash tests


@pytest.mark.asyncio
async def test_clear_hash_success(dedupe_service, mock_redis_client):
    """Test clear_hash removes hash from Redis."""
    mock_redis_client.delete.return_value = 1

    result = await dedupe_service.clear_hash("somehash123")

    assert result is True
    expected_key = f"{DEDUPE_KEY_PREFIX}somehash123"
    mock_redis_client.delete.assert_called_once_with(expected_key)


@pytest.mark.asyncio
async def test_clear_hash_not_found(dedupe_service, mock_redis_client):
    """Test clear_hash returns False when hash not found."""
    mock_redis_client.delete.return_value = 0

    result = await dedupe_service.clear_hash("nonexistenthash")

    assert result is False


@pytest.mark.asyncio
async def test_clear_hash_without_redis():
    """Test clear_hash returns False without Redis."""
    service = DedupeService(redis_client=None)

    result = await service.clear_hash("anyhash")

    assert result is False


@pytest.mark.asyncio
async def test_clear_hash_redis_error(dedupe_service, mock_redis_client):
    """Test clear_hash handles Redis errors gracefully."""
    mock_redis_client.delete.side_effect = Exception("Redis delete error")

    result = await dedupe_service.clear_hash("somehash")

    assert result is False


# Singleton tests


def test_get_dedupe_service_creates_singleton():
    """Test get_dedupe_service creates singleton instance."""
    service1 = get_dedupe_service()
    service2 = get_dedupe_service()

    assert service1 is service2


def test_reset_dedupe_service():
    """Test reset_dedupe_service clears singleton."""
    service1 = get_dedupe_service()
    reset_dedupe_service()
    service2 = get_dedupe_service()

    assert service1 is not service2


# Integration-style tests


@pytest.mark.asyncio
async def test_full_dedupe_workflow(tmp_path, mock_redis_client):
    """Test complete dedupe workflow: check -> mark -> check again."""
    # Create test file
    test_file = tmp_path / "test.jpg"
    img = Image.new("RGB", (50, 50), color="blue")
    img.save(test_file)

    service = DedupeService(redis_client=mock_redis_client, ttl_seconds=300)

    # First check - file should be new
    mock_redis_client.exists.return_value = 0
    is_dup1, hash1 = await service.is_duplicate_and_mark(str(test_file))
    assert is_dup1 is False
    assert hash1 is not None

    # Simulate Redis now having the key
    mock_redis_client.exists.return_value = 1

    # Second check - file should be duplicate
    is_dup2, hash2 = await service.is_duplicate(str(test_file))
    assert is_dup2 is True
    assert hash2 == hash1


@pytest.mark.asyncio
async def test_dedupe_different_files_same_name(tmp_path, mock_redis_client):
    """Test that files with same name but different content get different hashes."""
    service = DedupeService(redis_client=mock_redis_client)

    # Create first version
    test_file = tmp_path / "image.jpg"
    img1 = Image.new("RGB", (100, 100), color="red")
    img1.save(test_file)

    mock_redis_client.exists.return_value = 0
    _, hash1 = await service.is_duplicate_and_mark(str(test_file))

    # Overwrite with different content
    img2 = Image.new("RGB", (100, 100), color="green")
    img2.save(test_file)

    _, hash2 = await service.is_duplicate_and_mark(str(test_file))

    # Hashes should be different
    assert hash1 != hash2


@pytest.mark.asyncio
async def test_dedupe_with_settings_ttl(mock_redis_client):
    """Test that DedupeService respects settings TTL when available."""
    with patch("backend.services.dedupe.get_settings") as mock_settings:
        mock_settings.return_value.dedupe_ttl_seconds = 600

        service = DedupeService(redis_client=mock_redis_client)

        # Should use settings TTL
        assert service._ttl_seconds == 600


# Edge cases


@pytest.mark.asyncio
async def test_large_file_hashing(tmp_path):
    """Test hashing large files efficiently."""
    large_file = tmp_path / "large_file.bin"

    # Create a 1MB file
    with open(large_file, "wb") as f:
        f.write(b"x" * (1024 * 1024))

    file_hash = compute_file_hash(str(large_file))

    assert file_hash is not None
    assert len(file_hash) == 64


@pytest.mark.asyncio
async def test_binary_file_hashing(tmp_path):
    """Test hashing binary files with various byte patterns."""
    binary_file = tmp_path / "binary.bin"

    # Write bytes including null bytes and high values
    binary_file.write_bytes(bytes(range(256)))

    file_hash = compute_file_hash(str(binary_file))

    assert file_hash is not None


# TTL Enforcement and Orphan Cleanup Tests


@pytest.fixture
def mock_redis_client_with_internal():
    """Create a mock Redis client with internal _client for TTL operations."""
    mock = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)

    # Mock the internal client for TTL operations
    mock_internal = AsyncMock()
    mock_internal.ttl = AsyncMock(return_value=300)  # Key has TTL
    mock_internal.expire = AsyncMock(return_value=True)
    mock_internal.scan_iter = MagicMock()
    mock._client = mock_internal

    return mock


@pytest.mark.asyncio
async def test_ensure_key_has_ttl_sets_ttl_when_missing(mock_redis_client_with_internal):
    """Test that ensure_key_has_ttl sets TTL when key has no TTL."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Simulate key with no TTL (-1)
    mock_redis_client_with_internal._client.ttl.return_value = -1

    result = await service.ensure_key_has_ttl("abc123")

    assert result is True
    mock_redis_client_with_internal._client.expire.assert_called_once()
    call_args = mock_redis_client_with_internal._client.expire.call_args[0]
    assert call_args[0] == f"{DEDUPE_KEY_PREFIX}abc123"
    assert call_args[1] == service._ttl_seconds


@pytest.mark.asyncio
async def test_ensure_key_has_ttl_skips_when_ttl_exists(mock_redis_client_with_internal):
    """Test that ensure_key_has_ttl does not modify TTL when already set."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Simulate key with TTL (300 seconds)
    mock_redis_client_with_internal._client.ttl.return_value = 300

    result = await service.ensure_key_has_ttl("abc123")

    assert result is True
    # expire should NOT be called since TTL exists
    mock_redis_client_with_internal._client.expire.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_key_has_ttl_without_redis():
    """Test that ensure_key_has_ttl returns False without Redis."""
    service = DedupeService(redis_client=None)

    result = await service.ensure_key_has_ttl("abc123")

    assert result is False


@pytest.mark.asyncio
async def test_ensure_key_has_ttl_handles_error(mock_redis_client_with_internal):
    """Test that ensure_key_has_ttl handles errors gracefully."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    mock_redis_client_with_internal._client.ttl.side_effect = Exception("Redis error")

    result = await service.ensure_key_has_ttl("abc123")

    assert result is False


@pytest.mark.asyncio
async def test_check_redis_ensures_ttl_on_duplicate(mock_redis_client_with_internal):
    """Test that _check_redis calls ensure_key_has_ttl when duplicate is found."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Mock exists to return True (key exists)
    mock_redis_client_with_internal.exists.return_value = 1
    # Mock TTL to return -1 (no TTL set)
    mock_redis_client_with_internal._client.ttl.return_value = -1

    result = await service._check_redis("abc123")

    assert result is True
    # Should have checked and set TTL
    mock_redis_client_with_internal._client.ttl.assert_called_once()
    mock_redis_client_with_internal._client.expire.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_orphaned_keys_sets_ttl(mock_redis_client_with_internal):
    """Test that cleanup_orphaned_keys sets TTL on orphaned keys."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Mock scan_iter to return orphaned keys
    async def mock_scan_iter(match, count):
        yield f"{DEDUPE_KEY_PREFIX}orphan1"
        yield f"{DEDUPE_KEY_PREFIX}orphan2"

    mock_redis_client_with_internal._client.scan_iter = mock_scan_iter
    # First key has no TTL, second key has TTL
    mock_redis_client_with_internal._client.ttl.side_effect = [-1, 300]

    cleaned = await service.cleanup_orphaned_keys()

    # Should have cleaned 1 orphaned key (the one with TTL=-1)
    assert cleaned == 1
    # expire should have been called once for the orphaned key
    mock_redis_client_with_internal._client.expire.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_orphaned_keys_without_redis():
    """Test that cleanup_orphaned_keys returns 0 without Redis."""
    service = DedupeService(redis_client=None)

    result = await service.cleanup_orphaned_keys()

    assert result == 0


@pytest.mark.asyncio
async def test_cleanup_orphaned_keys_handles_scan_error(mock_redis_client_with_internal):
    """Test that cleanup_orphaned_keys handles scan errors gracefully."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Mock scan_iter to raise an exception
    async def mock_scan_iter_error(match, count):
        raise Exception("Scan failed")
        yield  # Make it an async generator

    mock_redis_client_with_internal._client.scan_iter = mock_scan_iter_error

    result = await service.cleanup_orphaned_keys()

    assert result == 0


@pytest.mark.asyncio
async def test_cleanup_orphaned_keys_handles_key_error(mock_redis_client_with_internal):
    """Test that cleanup_orphaned_keys continues on individual key errors."""
    service = DedupeService(redis_client=mock_redis_client_with_internal)

    # Mock scan_iter to return keys
    async def mock_scan_iter(match, count):
        yield f"{DEDUPE_KEY_PREFIX}key1"
        yield f"{DEDUPE_KEY_PREFIX}key2"

    mock_redis_client_with_internal._client.scan_iter = mock_scan_iter
    # First key fails, second key is orphaned
    mock_redis_client_with_internal._client.ttl.side_effect = [
        Exception("TTL check failed"),
        -1,
    ]

    cleaned = await service.cleanup_orphaned_keys()

    # Should have cleaned 1 key (the second one)
    assert cleaned == 1


@pytest.mark.asyncio
async def test_orphan_cleanup_max_age_constant():
    """Test that ORPHAN_CLEANUP_MAX_AGE_SECONDS is properly defined."""
    assert ORPHAN_CLEANUP_MAX_AGE_SECONDS > 0
    assert ORPHAN_CLEANUP_MAX_AGE_SECONDS <= 7200  # Max 2 hours is reasonable

"""File deduplication service for preventing duplicate processing.

This module provides idempotency for the file watcher pipeline by:
1. Computing SHA256 content hash of image files
2. Checking Redis for short-term dedupe (with TTL)
3. Falling back to database check if Redis is unavailable

Idempotency Approach:
---------------------
- Idempotency key: SHA256 hash of file content
- Primary dedupe: Redis SET with TTL (default 5 minutes)
- Fallback: Database query for existing detections with same file hash
- Hash stored in Redis key: `dedupe:{sha256_hash}`

This prevents duplicate processing caused by:
- Watchdog create/modify event bursts
- Service restarts during file processing
- FTP upload retries

Error Handling:
--------------
- Redis unavailable: Falls back to database check
- Database unavailable: Allows processing (fail-open for availability)
- File read errors: Returns False (don't process corrupted files)
"""

import hashlib
from pathlib import Path

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Default TTL for dedupe entries (5 minutes = 300 seconds)
DEFAULT_DEDUPE_TTL_SECONDS = 300

# Redis key prefix for dedupe entries
DEDUPE_KEY_PREFIX = "dedupe:"

# Maximum TTL for orphan cleanup (1 hour = 3600 seconds)
# Keys older than this without TTL will be removed
ORPHAN_CLEANUP_MAX_AGE_SECONDS = 3600

# Interval for orphan cleanup task (10 minutes = 600 seconds)
ORPHAN_CLEANUP_INTERVAL_SECONDS = 600
from collections.abc import Callable
from inspect import signature as _mutmut_signature
from typing import Annotated, ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg=None):
    """Forward call to original or mutated function, depending on the environment"""
    import os

    mutant_under_test = os.environ["MUTANT_UNDER_TEST"]
    if mutant_under_test == "fail":
        from mutmut.__main__ import MutmutProgrammaticFailException

        raise MutmutProgrammaticFailException("Failed programmatically")
    elif mutant_under_test == "stats":
        from mutmut.__main__ import record_trampoline_hit

        record_trampoline_hit(orig.__module__ + "." + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + "." + orig.__name__ + "__mutmut_"
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition(".")[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


def x_compute_file_hash__mutmut_orig(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_1(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = None
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_2(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(None)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_3(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_4(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(None)
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_5(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size != 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_6(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 1:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_7(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(None)
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_8(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = None
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_9(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(None, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_10(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, None) as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_11(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open("rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_12(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(
            file_path,
        ) as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_13(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "XXrbXX") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_14(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "RB") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_15(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(None, b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_16(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), None):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_17(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_18(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(
                lambda: f.read(8192),
            ):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_19(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: None, b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_20(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(None), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_21(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8193), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_22(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b"XXXX"):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_23(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(None)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_24(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError:
        logger.error(None)
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


def x_compute_file_hash__mutmut_25(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception:
        logger.error(None)
        return None


x_compute_file_hash__mutmut_mutants: ClassVar[MutantDict] = {
    "x_compute_file_hash__mutmut_1": x_compute_file_hash__mutmut_1,
    "x_compute_file_hash__mutmut_2": x_compute_file_hash__mutmut_2,
    "x_compute_file_hash__mutmut_3": x_compute_file_hash__mutmut_3,
    "x_compute_file_hash__mutmut_4": x_compute_file_hash__mutmut_4,
    "x_compute_file_hash__mutmut_5": x_compute_file_hash__mutmut_5,
    "x_compute_file_hash__mutmut_6": x_compute_file_hash__mutmut_6,
    "x_compute_file_hash__mutmut_7": x_compute_file_hash__mutmut_7,
    "x_compute_file_hash__mutmut_8": x_compute_file_hash__mutmut_8,
    "x_compute_file_hash__mutmut_9": x_compute_file_hash__mutmut_9,
    "x_compute_file_hash__mutmut_10": x_compute_file_hash__mutmut_10,
    "x_compute_file_hash__mutmut_11": x_compute_file_hash__mutmut_11,
    "x_compute_file_hash__mutmut_12": x_compute_file_hash__mutmut_12,
    "x_compute_file_hash__mutmut_13": x_compute_file_hash__mutmut_13,
    "x_compute_file_hash__mutmut_14": x_compute_file_hash__mutmut_14,
    "x_compute_file_hash__mutmut_15": x_compute_file_hash__mutmut_15,
    "x_compute_file_hash__mutmut_16": x_compute_file_hash__mutmut_16,
    "x_compute_file_hash__mutmut_17": x_compute_file_hash__mutmut_17,
    "x_compute_file_hash__mutmut_18": x_compute_file_hash__mutmut_18,
    "x_compute_file_hash__mutmut_19": x_compute_file_hash__mutmut_19,
    "x_compute_file_hash__mutmut_20": x_compute_file_hash__mutmut_20,
    "x_compute_file_hash__mutmut_21": x_compute_file_hash__mutmut_21,
    "x_compute_file_hash__mutmut_22": x_compute_file_hash__mutmut_22,
    "x_compute_file_hash__mutmut_23": x_compute_file_hash__mutmut_23,
    "x_compute_file_hash__mutmut_24": x_compute_file_hash__mutmut_24,
    "x_compute_file_hash__mutmut_25": x_compute_file_hash__mutmut_25,
}


def compute_file_hash(*args, **kwargs):
    result = _mutmut_trampoline(
        x_compute_file_hash__mutmut_orig, x_compute_file_hash__mutmut_mutants, args, kwargs
    )
    return result


compute_file_hash.__signature__ = _mutmut_signature(x_compute_file_hash__mutmut_orig)
x_compute_file_hash__mutmut_orig.__name__ = "x_compute_file_hash"


class DedupeService:
    """Service for deduplicating file processing using content hashes.

    Uses Redis as primary dedupe cache with database fallback.
    Thread-safe and async-compatible.
    """

    def xǁDedupeServiceǁ__init____mutmut_orig(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_1(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = None
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_2(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = None

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_3(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = None
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_4(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = None

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_5(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(None, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_6(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, None, ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_7(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", None)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_8(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr("dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_9(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_10(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = settings.dedupe_ttl_seconds

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_11(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "XXdedupe_ttl_secondsXX", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_12(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "DEDUPE_TTL_SECONDS", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def xǁDedupeServiceǁ__init____mutmut_13(
        self,
        redis_client: RedisClient | None = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(None)

    xǁDedupeServiceǁ__init____mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁ__init____mutmut_1": xǁDedupeServiceǁ__init____mutmut_1,
        "xǁDedupeServiceǁ__init____mutmut_2": xǁDedupeServiceǁ__init____mutmut_2,
        "xǁDedupeServiceǁ__init____mutmut_3": xǁDedupeServiceǁ__init____mutmut_3,
        "xǁDedupeServiceǁ__init____mutmut_4": xǁDedupeServiceǁ__init____mutmut_4,
        "xǁDedupeServiceǁ__init____mutmut_5": xǁDedupeServiceǁ__init____mutmut_5,
        "xǁDedupeServiceǁ__init____mutmut_6": xǁDedupeServiceǁ__init____mutmut_6,
        "xǁDedupeServiceǁ__init____mutmut_7": xǁDedupeServiceǁ__init____mutmut_7,
        "xǁDedupeServiceǁ__init____mutmut_8": xǁDedupeServiceǁ__init____mutmut_8,
        "xǁDedupeServiceǁ__init____mutmut_9": xǁDedupeServiceǁ__init____mutmut_9,
        "xǁDedupeServiceǁ__init____mutmut_10": xǁDedupeServiceǁ__init____mutmut_10,
        "xǁDedupeServiceǁ__init____mutmut_11": xǁDedupeServiceǁ__init____mutmut_11,
        "xǁDedupeServiceǁ__init____mutmut_12": xǁDedupeServiceǁ__init____mutmut_12,
        "xǁDedupeServiceǁ__init____mutmut_13": xǁDedupeServiceǁ__init____mutmut_13,
    }

    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁ__init____mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁ__init____mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    __init__.__signature__ = _mutmut_signature(xǁDedupeServiceǁ__init____mutmut_orig)
    xǁDedupeServiceǁ__init____mutmut_orig.__name__ = "xǁDedupeServiceǁ__init__"

    def _get_redis_key(self, file_hash: str) -> str:
        """Get Redis key for a file hash.

        Args:
            file_hash: SHA256 hash of file content

        Returns:
            Redis key string
        """
        return f"{DEDUPE_KEY_PREFIX}{file_hash}"

    async def xǁDedupeServiceǁis_duplicate__mutmut_orig(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_1(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is not None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_2(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = None

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_3(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(None)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_4(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is not None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_5(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(None)
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_6(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (True, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_7(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = None
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_8(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(None)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_9(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_10(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(None)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate__mutmut_11(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (True, file_hash)

    xǁDedupeServiceǁis_duplicate__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁis_duplicate__mutmut_1": xǁDedupeServiceǁis_duplicate__mutmut_1,
        "xǁDedupeServiceǁis_duplicate__mutmut_2": xǁDedupeServiceǁis_duplicate__mutmut_2,
        "xǁDedupeServiceǁis_duplicate__mutmut_3": xǁDedupeServiceǁis_duplicate__mutmut_3,
        "xǁDedupeServiceǁis_duplicate__mutmut_4": xǁDedupeServiceǁis_duplicate__mutmut_4,
        "xǁDedupeServiceǁis_duplicate__mutmut_5": xǁDedupeServiceǁis_duplicate__mutmut_5,
        "xǁDedupeServiceǁis_duplicate__mutmut_6": xǁDedupeServiceǁis_duplicate__mutmut_6,
        "xǁDedupeServiceǁis_duplicate__mutmut_7": xǁDedupeServiceǁis_duplicate__mutmut_7,
        "xǁDedupeServiceǁis_duplicate__mutmut_8": xǁDedupeServiceǁis_duplicate__mutmut_8,
        "xǁDedupeServiceǁis_duplicate__mutmut_9": xǁDedupeServiceǁis_duplicate__mutmut_9,
        "xǁDedupeServiceǁis_duplicate__mutmut_10": xǁDedupeServiceǁis_duplicate__mutmut_10,
        "xǁDedupeServiceǁis_duplicate__mutmut_11": xǁDedupeServiceǁis_duplicate__mutmut_11,
    }

    def is_duplicate(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁis_duplicate__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁis_duplicate__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    is_duplicate.__signature__ = _mutmut_signature(xǁDedupeServiceǁis_duplicate__mutmut_orig)
    xǁDedupeServiceǁis_duplicate__mutmut_orig.__name__ = "xǁDedupeServiceǁis_duplicate"

    async def xǁDedupeServiceǁ_check_redis__mutmut_orig(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_1(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_2(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = None
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_3(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(None)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_4(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = None
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_5(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(None)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_6(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists >= 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_7(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 1:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_8(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(None)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_9(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(None)
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_10(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:17]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_11(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return False
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_12(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return True
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def xǁDedupeServiceǁ_check_redis__mutmut_13(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        If a key is found, ensures it has a TTL set to prevent orphaned keys
        from accumulating indefinitely.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                # Ensure the key has a TTL set to prevent orphaned keys
                # This handles the case where a key was created without TTL
                await self.ensure_key_has_ttl(file_hash)
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception:
            logger.warning(None)
            return None

    xǁDedupeServiceǁ_check_redis__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁ_check_redis__mutmut_1": xǁDedupeServiceǁ_check_redis__mutmut_1,
        "xǁDedupeServiceǁ_check_redis__mutmut_2": xǁDedupeServiceǁ_check_redis__mutmut_2,
        "xǁDedupeServiceǁ_check_redis__mutmut_3": xǁDedupeServiceǁ_check_redis__mutmut_3,
        "xǁDedupeServiceǁ_check_redis__mutmut_4": xǁDedupeServiceǁ_check_redis__mutmut_4,
        "xǁDedupeServiceǁ_check_redis__mutmut_5": xǁDedupeServiceǁ_check_redis__mutmut_5,
        "xǁDedupeServiceǁ_check_redis__mutmut_6": xǁDedupeServiceǁ_check_redis__mutmut_6,
        "xǁDedupeServiceǁ_check_redis__mutmut_7": xǁDedupeServiceǁ_check_redis__mutmut_7,
        "xǁDedupeServiceǁ_check_redis__mutmut_8": xǁDedupeServiceǁ_check_redis__mutmut_8,
        "xǁDedupeServiceǁ_check_redis__mutmut_9": xǁDedupeServiceǁ_check_redis__mutmut_9,
        "xǁDedupeServiceǁ_check_redis__mutmut_10": xǁDedupeServiceǁ_check_redis__mutmut_10,
        "xǁDedupeServiceǁ_check_redis__mutmut_11": xǁDedupeServiceǁ_check_redis__mutmut_11,
        "xǁDedupeServiceǁ_check_redis__mutmut_12": xǁDedupeServiceǁ_check_redis__mutmut_12,
        "xǁDedupeServiceǁ_check_redis__mutmut_13": xǁDedupeServiceǁ_check_redis__mutmut_13,
    }

    def _check_redis(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁ_check_redis__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁ_check_redis__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    _check_redis.__signature__ = _mutmut_signature(xǁDedupeServiceǁ_check_redis__mutmut_orig)
    xǁDedupeServiceǁ_check_redis__mutmut_orig.__name__ = "xǁDedupeServiceǁ_check_redis"

    async def xǁDedupeServiceǁmark_processed__mutmut_orig(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_1(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is not None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_2(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = None

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_3(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(None)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_4(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is not None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_5(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(None)
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_6(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return True

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_7(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = None
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_8(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(None)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_9(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(None, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_10(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, None, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_11(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=None)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_12(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_13(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_14(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(
                    key,
                    file_path,
                )
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_15(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(None)
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_16(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:17]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_17(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return False
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_18(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception:
                logger.warning(None)
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_19(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return True
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_20(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug(None)
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_21(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("XXNo Redis client, skipping dedupe markXX")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_22(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("no redis client, skipping dedupe mark")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_23(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("NO REDIS CLIENT, SKIPPING DEDUPE MARK")
            return False

    async def xǁDedupeServiceǁmark_processed__mutmut_24(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return True

    xǁDedupeServiceǁmark_processed__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁmark_processed__mutmut_1": xǁDedupeServiceǁmark_processed__mutmut_1,
        "xǁDedupeServiceǁmark_processed__mutmut_2": xǁDedupeServiceǁmark_processed__mutmut_2,
        "xǁDedupeServiceǁmark_processed__mutmut_3": xǁDedupeServiceǁmark_processed__mutmut_3,
        "xǁDedupeServiceǁmark_processed__mutmut_4": xǁDedupeServiceǁmark_processed__mutmut_4,
        "xǁDedupeServiceǁmark_processed__mutmut_5": xǁDedupeServiceǁmark_processed__mutmut_5,
        "xǁDedupeServiceǁmark_processed__mutmut_6": xǁDedupeServiceǁmark_processed__mutmut_6,
        "xǁDedupeServiceǁmark_processed__mutmut_7": xǁDedupeServiceǁmark_processed__mutmut_7,
        "xǁDedupeServiceǁmark_processed__mutmut_8": xǁDedupeServiceǁmark_processed__mutmut_8,
        "xǁDedupeServiceǁmark_processed__mutmut_9": xǁDedupeServiceǁmark_processed__mutmut_9,
        "xǁDedupeServiceǁmark_processed__mutmut_10": xǁDedupeServiceǁmark_processed__mutmut_10,
        "xǁDedupeServiceǁmark_processed__mutmut_11": xǁDedupeServiceǁmark_processed__mutmut_11,
        "xǁDedupeServiceǁmark_processed__mutmut_12": xǁDedupeServiceǁmark_processed__mutmut_12,
        "xǁDedupeServiceǁmark_processed__mutmut_13": xǁDedupeServiceǁmark_processed__mutmut_13,
        "xǁDedupeServiceǁmark_processed__mutmut_14": xǁDedupeServiceǁmark_processed__mutmut_14,
        "xǁDedupeServiceǁmark_processed__mutmut_15": xǁDedupeServiceǁmark_processed__mutmut_15,
        "xǁDedupeServiceǁmark_processed__mutmut_16": xǁDedupeServiceǁmark_processed__mutmut_16,
        "xǁDedupeServiceǁmark_processed__mutmut_17": xǁDedupeServiceǁmark_processed__mutmut_17,
        "xǁDedupeServiceǁmark_processed__mutmut_18": xǁDedupeServiceǁmark_processed__mutmut_18,
        "xǁDedupeServiceǁmark_processed__mutmut_19": xǁDedupeServiceǁmark_processed__mutmut_19,
        "xǁDedupeServiceǁmark_processed__mutmut_20": xǁDedupeServiceǁmark_processed__mutmut_20,
        "xǁDedupeServiceǁmark_processed__mutmut_21": xǁDedupeServiceǁmark_processed__mutmut_21,
        "xǁDedupeServiceǁmark_processed__mutmut_22": xǁDedupeServiceǁmark_processed__mutmut_22,
        "xǁDedupeServiceǁmark_processed__mutmut_23": xǁDedupeServiceǁmark_processed__mutmut_23,
        "xǁDedupeServiceǁmark_processed__mutmut_24": xǁDedupeServiceǁmark_processed__mutmut_24,
    }

    def mark_processed(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁmark_processed__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁmark_processed__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    mark_processed.__signature__ = _mutmut_signature(xǁDedupeServiceǁmark_processed__mutmut_orig)
    xǁDedupeServiceǁmark_processed__mutmut_orig.__name__ = "xǁDedupeServiceǁmark_processed"

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_orig(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_1(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = None
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_2(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(None)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_3(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is not None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_4(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (True, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_5(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = None
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_6(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(None, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_7(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, None)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_8(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_9(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(
            file_path,
        )
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_10(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (False, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_11(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(None, file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_12(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, None)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_13(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_hash)
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_14(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(
            file_path,
        )
        return (False, file_hash)

    async def xǁDedupeServiceǁis_duplicate_and_mark__mutmut_15(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (True, file_hash)

    xǁDedupeServiceǁis_duplicate_and_mark__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_1": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_1,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_2": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_2,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_3": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_3,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_4": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_4,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_5": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_5,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_6": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_6,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_7": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_7,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_8": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_8,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_9": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_9,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_10": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_10,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_11": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_11,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_12": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_12,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_13": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_13,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_14": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_14,
        "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_15": xǁDedupeServiceǁis_duplicate_and_mark__mutmut_15,
    }

    def is_duplicate_and_mark(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁis_duplicate_and_mark__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    is_duplicate_and_mark.__signature__ = _mutmut_signature(
        xǁDedupeServiceǁis_duplicate_and_mark__mutmut_orig
    )
    xǁDedupeServiceǁis_duplicate_and_mark__mutmut_orig.__name__ = (
        "xǁDedupeServiceǁis_duplicate_and_mark"
    )

    async def xǁDedupeServiceǁclear_hash__mutmut_orig(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_1(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_2(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return True

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_3(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = None
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_4(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(None)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_5(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = None
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_6(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(None)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_7(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result >= 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_8(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 1
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_9(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception:
            logger.warning(None)
            return False

    async def xǁDedupeServiceǁclear_hash__mutmut_10(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return True

    xǁDedupeServiceǁclear_hash__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁclear_hash__mutmut_1": xǁDedupeServiceǁclear_hash__mutmut_1,
        "xǁDedupeServiceǁclear_hash__mutmut_2": xǁDedupeServiceǁclear_hash__mutmut_2,
        "xǁDedupeServiceǁclear_hash__mutmut_3": xǁDedupeServiceǁclear_hash__mutmut_3,
        "xǁDedupeServiceǁclear_hash__mutmut_4": xǁDedupeServiceǁclear_hash__mutmut_4,
        "xǁDedupeServiceǁclear_hash__mutmut_5": xǁDedupeServiceǁclear_hash__mutmut_5,
        "xǁDedupeServiceǁclear_hash__mutmut_6": xǁDedupeServiceǁclear_hash__mutmut_6,
        "xǁDedupeServiceǁclear_hash__mutmut_7": xǁDedupeServiceǁclear_hash__mutmut_7,
        "xǁDedupeServiceǁclear_hash__mutmut_8": xǁDedupeServiceǁclear_hash__mutmut_8,
        "xǁDedupeServiceǁclear_hash__mutmut_9": xǁDedupeServiceǁclear_hash__mutmut_9,
        "xǁDedupeServiceǁclear_hash__mutmut_10": xǁDedupeServiceǁclear_hash__mutmut_10,
    }

    def clear_hash(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁclear_hash__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁclear_hash__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    clear_hash.__signature__ = _mutmut_signature(xǁDedupeServiceǁclear_hash__mutmut_orig)
    xǁDedupeServiceǁclear_hash__mutmut_orig.__name__ = "xǁDedupeServiceǁclear_hash"

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_orig(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_1(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client and not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_2(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_3(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_4(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 1

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_5(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = None
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_6(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 1
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_7(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = None
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_8(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = None
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_9(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=None, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_10(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=None):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_11(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_12(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(
                match=pattern,
            ):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_13(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=101):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_14(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = None
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_15(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(None)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_16(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl != -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_17(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == +1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_18(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -2:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_19(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(None, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_20(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, None)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_21(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_22(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(
                            key,
                        )
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_23(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count = 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_24(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count -= 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_25(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 2
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_26(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(None)
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_27(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception:
                    logger.warning(None)
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_28(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    break

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_29(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count >= 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_30(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 1:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_31(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    None,
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_32(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra=None,
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_33(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_34(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_35(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"XXcleaned_countXX": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_36(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"CLEANED_COUNT": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_37(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception:
            logger.error(None, exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_38(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=None)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_39(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception:
            logger.error(exc_info=True)

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_40(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(
                f"Error during orphan key cleanup: {e}",
            )

        return cleaned_count

    async def xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_41(self) -> int:
        """Clean up orphaned dedupe keys that have no TTL set.

        Scans for dedupe keys without TTL and removes them if they are older
        than ORPHAN_CLEANUP_MAX_AGE_SECONDS. This prevents memory leaks from
        keys that were created but never had TTL set properly.

        Returns:
            Number of orphaned keys cleaned up
        """
        if not self._redis_client or not self._redis_client._client:
            return 0

        cleaned_count = 0
        try:
            client = self._redis_client._client
            # Scan for all dedupe keys
            pattern = f"{DEDUPE_KEY_PREFIX}*"
            async for key in client.scan_iter(match=pattern, count=100):
                try:
                    # Check if key has a TTL
                    ttl = await client.ttl(key)
                    # ttl returns:
                    #   -2 if key doesn't exist
                    #   -1 if key has no TTL (orphan)
                    #   >= 0 for keys with TTL
                    if ttl == -1:
                        # Key exists but has no TTL - this is an orphan
                        # Set a TTL to clean it up
                        await client.expire(key, ORPHAN_CLEANUP_MAX_AGE_SECONDS)
                        cleaned_count += 1
                        logger.debug(f"Set TTL on orphaned dedupe key: {key}")
                except Exception as e:
                    logger.warning(f"Error checking TTL for key {key}: {e}")
                    continue

            if cleaned_count > 0:
                logger.info(
                    f"Set TTL on {cleaned_count} orphaned dedupe keys",
                    extra={"cleaned_count": cleaned_count},
                )

        except Exception as e:
            logger.error(f"Error during orphan key cleanup: {e}", exc_info=False)

        return cleaned_count

    xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_1": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_1,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_2": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_2,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_3": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_3,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_4": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_4,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_5": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_5,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_6": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_6,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_7": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_7,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_8": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_8,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_9": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_9,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_10": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_10,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_11": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_11,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_12": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_12,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_13": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_13,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_14": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_14,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_15": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_15,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_16": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_16,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_17": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_17,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_18": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_18,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_19": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_19,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_20": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_20,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_21": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_21,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_22": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_22,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_23": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_23,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_24": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_24,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_25": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_25,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_26": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_26,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_27": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_27,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_28": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_28,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_29": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_29,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_30": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_30,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_31": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_31,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_32": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_32,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_33": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_33,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_34": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_34,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_35": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_35,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_36": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_36,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_37": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_37,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_38": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_38,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_39": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_39,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_40": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_40,
        "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_41": xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_41,
    }

    def cleanup_orphaned_keys(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    cleanup_orphaned_keys.__signature__ = _mutmut_signature(
        xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_orig
    )
    xǁDedupeServiceǁcleanup_orphaned_keys__mutmut_orig.__name__ = (
        "xǁDedupeServiceǁcleanup_orphaned_keys"
    )

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_orig(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_1(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client and not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_2(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_3(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_4(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return True

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_5(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = None
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_6(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(None)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_7(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = None
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_8(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = None
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_9(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(None)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_10(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl != -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_11(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == +1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_12(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -2:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_13(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(None, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_14(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, None)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_15(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_16(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(
                    key,
                )
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_17(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(None)
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_18(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return False
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_19(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception:
            logger.warning(None)
            return False

    async def xǁDedupeServiceǁensure_key_has_ttl__mutmut_20(self, file_hash: str) -> bool:
        """Ensure a dedupe key has a TTL set.

        Called after checking if a key exists to ensure orphaned keys
        get a TTL set even if mark_processed is never called.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if TTL was set or already exists, False on error
        """
        if not self._redis_client or not self._redis_client._client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            client = self._redis_client._client
            ttl = await client.ttl(key)
            # If key has no TTL (-1), set one
            if ttl == -1:
                await client.expire(key, self._ttl_seconds)
                logger.debug(f"Set TTL on dedupe key missing TTL: {key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to ensure TTL on key: {e}")
            return True

    xǁDedupeServiceǁensure_key_has_ttl__mutmut_mutants: ClassVar[MutantDict] = {
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_1": xǁDedupeServiceǁensure_key_has_ttl__mutmut_1,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_2": xǁDedupeServiceǁensure_key_has_ttl__mutmut_2,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_3": xǁDedupeServiceǁensure_key_has_ttl__mutmut_3,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_4": xǁDedupeServiceǁensure_key_has_ttl__mutmut_4,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_5": xǁDedupeServiceǁensure_key_has_ttl__mutmut_5,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_6": xǁDedupeServiceǁensure_key_has_ttl__mutmut_6,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_7": xǁDedupeServiceǁensure_key_has_ttl__mutmut_7,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_8": xǁDedupeServiceǁensure_key_has_ttl__mutmut_8,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_9": xǁDedupeServiceǁensure_key_has_ttl__mutmut_9,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_10": xǁDedupeServiceǁensure_key_has_ttl__mutmut_10,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_11": xǁDedupeServiceǁensure_key_has_ttl__mutmut_11,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_12": xǁDedupeServiceǁensure_key_has_ttl__mutmut_12,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_13": xǁDedupeServiceǁensure_key_has_ttl__mutmut_13,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_14": xǁDedupeServiceǁensure_key_has_ttl__mutmut_14,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_15": xǁDedupeServiceǁensure_key_has_ttl__mutmut_15,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_16": xǁDedupeServiceǁensure_key_has_ttl__mutmut_16,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_17": xǁDedupeServiceǁensure_key_has_ttl__mutmut_17,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_18": xǁDedupeServiceǁensure_key_has_ttl__mutmut_18,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_19": xǁDedupeServiceǁensure_key_has_ttl__mutmut_19,
        "xǁDedupeServiceǁensure_key_has_ttl__mutmut_20": xǁDedupeServiceǁensure_key_has_ttl__mutmut_20,
    }

    def ensure_key_has_ttl(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁDedupeServiceǁensure_key_has_ttl__mutmut_orig"),
            object.__getattribute__(self, "xǁDedupeServiceǁensure_key_has_ttl__mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    ensure_key_has_ttl.__signature__ = _mutmut_signature(
        xǁDedupeServiceǁensure_key_has_ttl__mutmut_orig
    )
    xǁDedupeServiceǁensure_key_has_ttl__mutmut_orig.__name__ = "xǁDedupeServiceǁensure_key_has_ttl"


# Module-level singleton for convenience
_dedupe_service: DedupeService | None = None


def x_get_dedupe_service__mutmut_orig(redis_client: RedisClient | None = None) -> DedupeService:
    """Get or create the global dedupe service instance.

    Args:
        redis_client: Redis client (used only on first call)

    Returns:
        DedupeService singleton instance
    """
    global _dedupe_service  # noqa: PLW0603

    if _dedupe_service is None:
        _dedupe_service = DedupeService(redis_client=redis_client)

    return _dedupe_service


def x_get_dedupe_service__mutmut_1(redis_client: RedisClient | None = None) -> DedupeService:
    """Get or create the global dedupe service instance.

    Args:
        redis_client: Redis client (used only on first call)

    Returns:
        DedupeService singleton instance
    """
    global _dedupe_service  # noqa: PLW0603

    if _dedupe_service is not None:
        _dedupe_service = DedupeService(redis_client=redis_client)

    return _dedupe_service


def x_get_dedupe_service__mutmut_2(redis_client: RedisClient | None = None) -> DedupeService:
    """Get or create the global dedupe service instance.

    Args:
        redis_client: Redis client (used only on first call)

    Returns:
        DedupeService singleton instance
    """
    global _dedupe_service  # noqa: PLW0603

    if _dedupe_service is None:
        _dedupe_service = None

    return _dedupe_service


def x_get_dedupe_service__mutmut_3(redis_client: RedisClient | None = None) -> DedupeService:
    """Get or create the global dedupe service instance.

    Args:
        redis_client: Redis client (used only on first call)

    Returns:
        DedupeService singleton instance
    """
    global _dedupe_service  # noqa: PLW0603

    if _dedupe_service is None:
        _dedupe_service = DedupeService(redis_client=None)

    return _dedupe_service


x_get_dedupe_service__mutmut_mutants: ClassVar[MutantDict] = {
    "x_get_dedupe_service__mutmut_1": x_get_dedupe_service__mutmut_1,
    "x_get_dedupe_service__mutmut_2": x_get_dedupe_service__mutmut_2,
    "x_get_dedupe_service__mutmut_3": x_get_dedupe_service__mutmut_3,
}


def get_dedupe_service(*args, **kwargs):
    result = _mutmut_trampoline(
        x_get_dedupe_service__mutmut_orig, x_get_dedupe_service__mutmut_mutants, args, kwargs
    )
    return result


get_dedupe_service.__signature__ = _mutmut_signature(x_get_dedupe_service__mutmut_orig)
x_get_dedupe_service__mutmut_orig.__name__ = "x_get_dedupe_service"


def x_reset_dedupe_service__mutmut_orig() -> None:
    """Reset the global dedupe service (for testing)."""
    global _dedupe_service  # noqa: PLW0603
    _dedupe_service = None


def x_reset_dedupe_service__mutmut_1() -> None:
    """Reset the global dedupe service (for testing)."""
    global _dedupe_service  # noqa: PLW0603
    _dedupe_service = ""


x_reset_dedupe_service__mutmut_mutants: ClassVar[MutantDict] = {
    "x_reset_dedupe_service__mutmut_1": x_reset_dedupe_service__mutmut_1
}


def reset_dedupe_service(*args, **kwargs):
    result = _mutmut_trampoline(
        x_reset_dedupe_service__mutmut_orig, x_reset_dedupe_service__mutmut_mutants, args, kwargs
    )
    return result


reset_dedupe_service.__signature__ = _mutmut_signature(x_reset_dedupe_service__mutmut_orig)
x_reset_dedupe_service__mutmut_orig.__name__ = "x_reset_dedupe_service"

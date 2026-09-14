"""Unit tests for UUID7 time-ordering property.

Tests verify that UUID7 (RFC 9562) provides time-ordered identifiers
which are lexicographically sortable by creation time. This property
improves database B-tree index locality for sequential inserts.

See: https://www.rfc-editor.org/rfc/rfc9562.html
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


class TestUUID7Ordering:
    """Tests for UUID7 time-ordering property."""

    def test_uuid7_sequential_ordering(self) -> None:
        """UUID7 should be time-ordered - sequentially generated UUIDs are sortable."""
        ids = [uuid.uuid7() for _ in range(100)]
        sorted_ids = sorted(ids)
        assert ids == sorted_ids, "UUID7 should maintain chronological order"

    def test_uuid7_ordering_with_delays(self) -> None:
        """UUID7 should maintain order even with small time delays between generations."""
        ids = []
        for _ in range(10):
            ids.append(uuid.uuid7())
            time.sleep(0.001)  # 1ms delay

        sorted_ids = sorted(ids)
        assert ids == sorted_ids, "UUID7 should maintain order with time delays"

    def test_uuid7_is_valid_uuid(self) -> None:
        """UUID7 should be a valid UUID that can be converted to string and back."""
        id7 = uuid.uuid7()

        # Should be a UUID instance
        assert isinstance(id7, uuid.UUID)

        # Should have version 7
        assert id7.version == 7

        # Should roundtrip through string conversion
        id_str = str(id7)
        parsed = uuid.UUID(id_str)
        assert id7 == parsed

    def test_uuid7_uniqueness(self) -> None:
        """UUID7 should generate unique values."""
        count = 10000
        ids = [uuid.uuid7() for _ in range(count)]
        unique_ids = set(ids)
        assert len(unique_ids) == count, "All UUID7 values should be unique"

    def test_uuid7_concurrent_generation_ordering(self) -> None:
        """UUID7s generated across threads should still be roughly time-ordered.

        Note: Exact ordering across threads is not guaranteed due to thread scheduling,
        but UUIDs generated in sequence within each thread should be ordered.
        """
        results: list[list[uuid.UUID]] = []

        def generate_batch(batch_size: int = 100) -> list[uuid.UUID]:
            return [uuid.uuid7() for _ in range(batch_size)]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(generate_batch) for _ in range(4)]
            results = [f.result() for f in futures]

        # Each batch should be internally ordered
        for batch in results:
            assert batch == sorted(batch), "Each thread's batch should be time-ordered"

    def test_uuid7_comparable(self) -> None:
        """UUID7 should support comparison operations."""
        id1 = uuid.uuid7()
        time.sleep(0.001)
        id2 = uuid.uuid7()

        assert id1 < id2, "Earlier UUID7 should be less than later UUID7"
        assert id2 > id1, "Later UUID7 should be greater than earlier UUID7"
        assert id1 != id2, "Different UUID7s should not be equal"
        assert id1 <= id1, "UUID7 should be less than or equal to itself"  # noqa: PLR0124
        assert id1 >= id1, "UUID7 should be greater than or equal to itself"  # noqa: PLR0124

    def test_uuid7_string_lexicographic_ordering(self) -> None:
        """UUID7 string representations should maintain lexicographic order.

        This is important for database indexes which may store UUIDs as strings.
        """
        ids = []
        for _ in range(10):
            ids.append(uuid.uuid7())
            time.sleep(0.001)

        id_strings = [str(id_) for id_ in ids]
        sorted_strings = sorted(id_strings)
        assert id_strings == sorted_strings, "UUID7 strings should be lexicographically ordered"

    def test_uuid7_bytes_ordering(self) -> None:
        """UUID7 bytes representation should maintain order.

        This is important for binary storage in databases.
        """
        ids = []
        for _ in range(10):
            ids.append(uuid.uuid7())
            time.sleep(0.001)

        id_bytes = [id_.bytes for id_ in ids]
        sorted_bytes = sorted(id_bytes)
        assert id_bytes == sorted_bytes, "UUID7 bytes should maintain order"

    def test_uuid7_128_bits(self) -> None:
        """UUID7 should be 128 bits (16 bytes) like all UUIDs."""
        id7 = uuid.uuid7()
        assert len(id7.bytes) == 16, "UUID7 should be 16 bytes"
        assert id7.int.bit_length() <= 128, "UUID7 should fit in 128 bits"


class TestUUID7CompatibilityWithUUID4:
    """Tests to ensure UUID7 is compatible with existing UUID4 records."""

    def test_uuid7_uuid4_same_format(self) -> None:
        """UUID7 and UUID4 should have the same string format."""
        id7 = uuid.uuid7()
        id4 = uuid.uuid4()

        # Both should be valid UUID strings with same format
        assert len(str(id7)) == len(str(id4)) == 36
        assert str(id7).count("-") == str(id4).count("-") == 4

    def test_uuid7_uuid4_same_bytes_length(self) -> None:
        """UUID7 and UUID4 should have the same bytes length."""
        id7 = uuid.uuid7()
        id4 = uuid.uuid4()

        assert len(id7.bytes) == len(id4.bytes) == 16

    def test_uuid7_uuid4_comparable(self) -> None:
        """UUID7 and UUID4 can be compared but UUID4 won't be time-ordered."""
        id7 = uuid.uuid7()
        id4 = uuid.uuid4()

        # Comparison should work (no exceptions)
        _ = id7 < id4 or id7 > id4 or id7 == id4

    def test_uuid7_uuid4_can_coexist_in_set(self) -> None:
        """UUID7 and UUID4 should be able to coexist in the same set/dict."""
        ids: set[uuid.UUID] = set()
        ids.add(uuid.uuid7())
        ids.add(uuid.uuid4())
        ids.add(uuid.uuid7())
        ids.add(uuid.uuid4())

        assert len(ids) == 4, "All UUIDs should be unique and coexist"

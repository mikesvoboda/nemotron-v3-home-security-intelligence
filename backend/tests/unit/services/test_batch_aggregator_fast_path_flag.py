"""Ruling 168: the master switch is honoured at the decision site.

`BatchAggregator._should_use_fast_path` (backend/services/batch_aggregator.py)
is where a detection is actually routed around the batch window. Before this
package the "disabled" state lived only in the shipped values — threshold 2.0,
object types [] — so the method's own docstring had to promise it always
returns False. Ruling 168 moves the promise into code: while
`fast_path_enabled` is False the fast path never fires, **whatever the
threshold**.

That clause is what makes this test load-bearing rather than decorative: this
package lowers the threshold default from 2.0 to 0.9, so if the decision site
ignored the flag, a shipped configuration would silently ENABLE a path whose
comment says it produces "wildly inaccurate risk scores" (Nemotron gets no
pose/clothing/threat/re-ID/CLIP context).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.batch_aggregator import BatchAggregator


def _settings_stub(*, enabled: bool, threshold: float, types: list[str]) -> MagicMock:
    """Build the settings object `BatchAggregator.__init__` reads.

    Args:
        enabled: value for `fast_path_enabled`.
        threshold: value for `fast_path_confidence_threshold`.
        types: value for `fast_path_object_types`.

    Returns:
        A MagicMock shaped like Settings for the aggregator's constructor.
    """
    settings = MagicMock()
    settings.batch_window_seconds = 90
    settings.batch_idle_timeout_seconds = 30
    settings.batch_max_detections = 25
    settings.fast_path_enabled = enabled
    settings.fast_path_confidence_threshold = threshold
    settings.fast_path_object_types = types
    return settings


@pytest.mark.asyncio
async def test_disabled_flag_blocks_the_fast_path_at_a_firing_threshold() -> None:
    """The pin: switch off, and a confidence well above the threshold still batches.

    Threshold 0.9, confidence 0.95, object type in the eligible list — every
    pre-existing condition for the fast path is satisfied. Only the flag
    disables it.
    """
    with patch(
        "backend.services.batch_aggregator.get_settings",
        return_value=_settings_stub(enabled=False, threshold=0.9, types=["person"]),
        autospec=True,
    ):
        aggregator = BatchAggregator(redis_client=MagicMock())
        assert aggregator._should_use_fast_path(0.95, "person") is False


@pytest.mark.asyncio
async def test_enabled_flag_admits_the_fast_path() -> None:
    """The other arm: switch on, the same inputs take the fast path.

    Without this pair the test above would pass for a method that simply
    returns False, and the pin would prove nothing.
    """
    with patch(
        "backend.services.batch_aggregator.get_settings",
        return_value=_settings_stub(enabled=True, threshold=0.9, types=["person"]),
        autospec=True,
    ):
        aggregator = BatchAggregator(redis_client=MagicMock())
        assert aggregator._should_use_fast_path(0.95, "person") is True


@pytest.mark.asyncio
async def test_flag_below_the_band_still_blocks() -> None:
    """Threshold 1.0 with confidence 1.0 and the flag off: batches, does not fast-path.

    Covers the clamped-sentinel case (a legacy 2.0 becomes 1.0) so a reader can
    see the disabled state holds at the band's top edge too.
    """
    with patch(
        "backend.services.batch_aggregator.get_settings",
        return_value=_settings_stub(enabled=False, threshold=1.0, types=["person"]),
        autospec=True,
    ):
        aggregator = BatchAggregator(redis_client=MagicMock())
        assert aggregator._should_use_fast_path(1.0, "person") is False


@pytest.mark.asyncio
async def test_init_binds_the_flag() -> None:
    """`__init__` carries the flag onto the instance, like every other setting.

    A missed bind site here would make the switch unreadable at the decision
    site while the API still reported it — the two halves of the flag disagreeing.
    """
    with patch(
        "backend.services.batch_aggregator.get_settings",
        return_value=_settings_stub(enabled=True, threshold=0.9, types=["person"]),
        autospec=True,
    ):
        aggregator = BatchAggregator(redis_client=MagicMock())
        assert aggregator._fast_path_enabled is True

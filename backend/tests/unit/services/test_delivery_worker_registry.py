"""Unit tests for backend.services.delivery_worker_registry (B4.2).

The pipeline wakes the worker through this registry; the module is the
dependency-inversion seam between the pipeline (which must not know channel
adapters) and main.py (which owns the running worker). Everything here is
stateful module state, so the tests reset it in a fixture.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services import delivery_worker_registry as reg


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reg.reset_delivery_worker()
    yield
    reg.reset_delivery_worker()


class TestDeliveryWorkerRegistry:
    def test_get_returns_none_before_registration(self) -> None:
        assert reg.get_delivery_worker() is None

    def test_wake_is_harmless_without_a_worker(self) -> None:
        reg.wake_delivery_worker()  # must not raise

    def test_set_then_get_returns_the_worker(self) -> None:
        worker = SimpleNamespace(wake=lambda: None)
        reg.set_delivery_worker(worker)  # type: ignore[arg-type]
        assert reg.get_delivery_worker() is worker

    def test_wake_calls_the_registered_worker(self) -> None:
        calls: list[int] = []
        worker = SimpleNamespace(wake=lambda: calls.append(1))
        reg.set_delivery_worker(worker)  # type: ignore[arg-type]
        reg.wake_delivery_worker()
        assert calls == [1]

    def test_reset_clears_the_registration(self) -> None:
        worker = SimpleNamespace(wake=lambda: None)
        reg.set_delivery_worker(worker)  # type: ignore[arg-type]
        reg.reset_delivery_worker()
        assert reg.get_delivery_worker() is None

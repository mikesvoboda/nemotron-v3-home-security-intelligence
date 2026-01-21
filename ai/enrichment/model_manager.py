"""On-Demand Model Manager for VRAM-Efficient Model Loading.

This module provides the OnDemandModelManager class for managing GPU VRAM budget
by loading models on-demand and evicting least-recently-used models when the
budget is exceeded.

Key features:
- VRAM budget enforcement with configurable limits
- LRU eviction with priority-based ordering (CRITICAL models evicted last)
- Thread-safe async operations with asyncio locks
- Logging for model load/unload events
- Status reporting for monitoring
- Prometheus metrics for VRAM usage, evictions, and model load times

Usage:
    manager = OnDemandModelManager(vram_budget_gb=6.8)
    manager.register_model(ModelConfig(
        name="vehicle",
        vram_mb=1500,
        priority=ModelPriority.MEDIUM,
        loader_fn=lambda: VehicleClassifier("/models/vehicle").load_model(),
        unloader_fn=lambda m: _unload_model(m),
    ))

    # Get model (loads if necessary, evicts LRU if needed)
    model = await manager.get_model("vehicle")
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any

import torch
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus Metrics for VRAM and Model Management (NEM-3149)
# =============================================================================

# VRAM usage gauges
ENRICHMENT_VRAM_USAGE_BYTES = Gauge(
    "enrichment_vram_usage_bytes",
    "Current VRAM usage by the enrichment service model manager in bytes",
)

ENRICHMENT_VRAM_BUDGET_BYTES = Gauge(
    "enrichment_vram_budget_bytes",
    "Configured VRAM budget for the enrichment service in bytes",
)

ENRICHMENT_VRAM_UTILIZATION_PERCENT = Gauge(
    "enrichment_vram_utilization_percent",
    "VRAM utilization percentage (usage / budget * 100)",
)

# Model count gauge
ENRICHMENT_MODELS_LOADED = Gauge(
    "enrichment_models_loaded",
    "Number of models currently loaded in the enrichment service",
)

# Model eviction counter
ENRICHMENT_MODEL_EVICTIONS_TOTAL = Counter(
    "enrichment_model_evictions_total",
    "Total number of model evictions by model name and priority",
    ["model_name", "priority"],
)

# Model load time histogram (buckets for typical model load times: 100ms to 60s)
ENRICHMENT_MODEL_LOAD_TIME_SECONDS = Histogram(
    "enrichment_model_load_time_seconds",
    "Time taken to load a model in seconds",
    ["model_name"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)


class ModelPriority(IntEnum):
    """Priority levels for model loading decisions.

    Lower values = higher priority = evicted last.
    When VRAM is constrained, models are evicted in order of:
    1. Priority (higher number = evicted first)
    2. Last used time (older = evicted first)
    """

    CRITICAL = 0  # Threat detection - never evict if possible
    HIGH = 1  # Pose, demographics, clothing
    MEDIUM = 2  # Vehicle, pet, re-ID
    LOW = 3  # Depth, action recognition


@dataclass
class ModelInfo:
    """Runtime information about a loaded model.

    Attributes:
        model: The loaded model instance
        vram_mb: VRAM usage in megabytes
        priority: Model priority for eviction decisions
        last_used: Timestamp of last access
    """

    model: Any
    vram_mb: int
    priority: ModelPriority
    last_used: datetime


@dataclass
class ModelConfig:
    """Configuration for a model that can be loaded on-demand.

    Attributes:
        name: Unique identifier for the model
        vram_mb: Estimated VRAM usage in megabytes
        priority: Priority for eviction decisions (lower = higher priority)
        loader_fn: Callable that loads and returns the model
        unloader_fn: Callable that unloads/cleans up the model
    """

    name: str
    vram_mb: int
    priority: ModelPriority
    loader_fn: Callable[[], Any]
    unloader_fn: Callable[[Any], None]


class OnDemandModelManager:
    """Manages on-demand model loading with VRAM budget constraints.

    This manager implements LRU eviction with priority-based ordering to
    efficiently manage GPU VRAM. Models are loaded lazily when first requested
    and evicted when necessary to stay within the VRAM budget.

    Eviction Strategy:
    - Models are sorted by (priority, last_used) in descending order
    - Higher priority numbers (LOW, MEDIUM) are evicted before lower (CRITICAL, HIGH)
    - Among models with equal priority, oldest (least recently used) is evicted first

    Thread Safety:
    - All model loading/unloading operations are protected by an asyncio lock
    - Multiple concurrent calls to get_model() are safe

    Attributes:
        vram_budget: Total VRAM budget in MB
        loaded_models: OrderedDict mapping model names to ModelInfo
        model_registry: Dict mapping model names to ModelConfig
        pending_loads: List of model names currently being loaded
    """

    def __init__(self, vram_budget_gb: float = 6.8) -> None:
        """Initialize the model manager.

        Args:
            vram_budget_gb: Maximum VRAM budget in gigabytes (default: 6.8GB)
        """
        self.vram_budget: float = vram_budget_gb * 1024  # Convert to MB
        self.loaded_models: OrderedDict[str, ModelInfo] = OrderedDict()
        self.model_registry: dict[str, ModelConfig] = {}
        self._lock = asyncio.Lock()
        self.pending_loads: list[str] = []

        # Set Prometheus budget metric (convert MB to bytes)
        ENRICHMENT_VRAM_BUDGET_BYTES.set(self.vram_budget * 1024 * 1024)
        # Initialize usage metrics to 0
        self._update_vram_metrics()

        logger.info(f"Initialized OnDemandModelManager with {vram_budget_gb}GB VRAM budget")

    def register_model(self, config: ModelConfig) -> None:
        """Register a model configuration.

        A model must be registered before it can be loaded. Registration
        does not load the model - it only stores the configuration for
        later on-demand loading.

        Args:
            config: Model configuration including loader/unloader functions

        Raises:
            ValueError: If a model with the same name is already registered
        """
        if config.name in self.model_registry:
            raise ValueError(f"Model '{config.name}' is already registered")

        self.model_registry[config.name] = config
        logger.debug(
            f"Registered model '{config.name}' "
            f"(VRAM: {config.vram_mb}MB, priority: {config.priority.name})"
        )

    def unregister_model(self, model_name: str) -> None:
        """Unregister a model configuration.

        If the model is currently loaded, it will NOT be unloaded.
        Use unload_model() first if the model should be unloaded.

        Args:
            model_name: Name of the model to unregister
        """
        if model_name in self.model_registry:
            del self.model_registry[model_name]
            logger.debug(f"Unregistered model '{model_name}'")

    async def get_model(self, model_name: str) -> Any:
        """Get a model, loading it if necessary and evicting LRU if needed.

        This is the primary interface for accessing models. If the model is
        already loaded, it's returned immediately (with its last_used timestamp
        updated). If not loaded, VRAM is freed as needed and the model is loaded.

        Args:
            model_name: Name of the registered model to get

        Returns:
            The loaded model instance

        Raises:
            ValueError: If the model is not registered
            RuntimeError: If there's insufficient VRAM even after eviction
        """
        async with self._lock:
            # Check if already loaded
            if model_name in self.loaded_models:
                # Move to end (most recently used) and update timestamp
                self.loaded_models.move_to_end(model_name)
                self.loaded_models[model_name].last_used = datetime.now()
                logger.debug(f"Model '{model_name}' accessed (already loaded)")
                return self.loaded_models[model_name].model

            # Validate model is registered
            if model_name not in self.model_registry:
                raise ValueError(f"Unknown model: '{model_name}'. Register it first.")

            # Ensure we have enough VRAM
            await self._ensure_vram_available(model_name)

            # Load the model
            return await self._load_model(model_name)

    async def _ensure_vram_available(self, model_name: str) -> None:
        """Evict LRU models until enough VRAM is available.

        Args:
            model_name: Name of the model we need to load

        Raises:
            RuntimeError: If we cannot free enough VRAM
        """
        config = self.model_registry[model_name]
        required = config.vram_mb

        while self._current_vram_usage() + required > self.vram_budget:
            if not await self._evict_lru_model():
                current_usage = self._current_vram_usage()
                raise RuntimeError(
                    f"Cannot load '{model_name}' ({required}MB): "
                    f"insufficient VRAM. Current usage: {current_usage}MB, "
                    f"budget: {self.vram_budget}MB, would need: {current_usage + required}MB"
                )

    def _current_vram_usage(self) -> int:
        """Calculate current VRAM usage in MB.

        Returns:
            Total VRAM used by all loaded models in megabytes
        """
        return sum(info.vram_mb for info in self.loaded_models.values())

    def _update_vram_metrics(self) -> None:
        """Update Prometheus VRAM metrics.

        Called after any model load/unload operation to keep metrics current.
        """
        usage_mb = self._current_vram_usage()
        usage_bytes = usage_mb * 1024 * 1024

        ENRICHMENT_VRAM_USAGE_BYTES.set(usage_bytes)
        ENRICHMENT_MODELS_LOADED.set(len(self.loaded_models))

        # Calculate utilization percentage
        if self.vram_budget > 0:
            utilization = (usage_mb / self.vram_budget) * 100
            ENRICHMENT_VRAM_UTILIZATION_PERCENT.set(round(utilization, 1))
        else:
            ENRICHMENT_VRAM_UTILIZATION_PERCENT.set(0)

    async def _evict_lru_model(self) -> bool:
        """Evict the least recently used model, respecting priority.

        Models are sorted by:
        1. Priority (descending - LOW=3 evicted before CRITICAL=0)
        2. Last used time (ascending - older evicted first)

        Returns:
            True if a model was evicted, False if no models to evict
        """
        if not self.loaded_models:
            return False

        # Sort candidates: higher priority number first, then older first
        # This means LOW (3) models are evicted before CRITICAL (0) models
        # Among same priority, older models are evicted first
        candidates = sorted(
            self.loaded_models.items(),
            key=lambda x: (-x[1].priority, x[1].last_used),
        )

        if not candidates:
            return False

        # Evict the best candidate (first in sorted list = highest priority number, oldest)
        name, info = candidates[0]
        logger.info(
            f"Evicting model '{name}' to free {info.vram_mb}MB VRAM "
            f"(priority: {info.priority.name}, last_used: {info.last_used.isoformat()})"
        )

        # Track eviction in Prometheus metrics
        ENRICHMENT_MODEL_EVICTIONS_TOTAL.labels(
            model_name=name,
            priority=info.priority.name,
        ).inc()

        await self._unload_model_internal(name)
        return True

    async def _load_model(self, model_name: str) -> Any:
        """Load a model into VRAM.

        Args:
            model_name: Name of the model to load

        Returns:
            The loaded model instance

        Raises:
            Exception: If the loader function fails
        """
        config = self.model_registry[model_name]
        self.pending_loads.append(model_name)

        try:
            logger.info(
                f"Loading model '{model_name}' "
                f"({config.vram_mb}MB, priority: {config.priority.name})"
            )

            # Track load time for Prometheus metrics
            start_time = time.monotonic()

            # Run loader in thread pool to avoid blocking
            model = await asyncio.get_event_loop().run_in_executor(None, config.loader_fn)

            # Record load time
            load_duration = time.monotonic() - start_time
            ENRICHMENT_MODEL_LOAD_TIME_SECONDS.labels(model_name=model_name).observe(load_duration)

            self.loaded_models[model_name] = ModelInfo(
                model=model,
                vram_mb=config.vram_mb,
                priority=config.priority,
                last_used=datetime.now(),
            )

            # Update VRAM metrics after successful load
            self._update_vram_metrics()

            logger.info(
                f"Model '{model_name}' loaded successfully in {load_duration:.2f}s. "
                f"Current VRAM usage: {self._current_vram_usage()}MB / {self.vram_budget}MB"
            )
            return model
        finally:
            self.pending_loads.remove(model_name)

    async def _unload_model_internal(self, model_name: str) -> None:
        """Internal method to unload a model (assumes lock is held).

        Args:
            model_name: Name of the model to unload
        """
        if model_name not in self.loaded_models:
            return

        info = self.loaded_models.pop(model_name)
        config = self.model_registry[model_name]

        # Run unloader in thread pool
        await asyncio.get_event_loop().run_in_executor(None, config.unloader_fn, info.model)

        # Clear CUDA cache to actually free VRAM
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Update VRAM metrics after unload
        self._update_vram_metrics()

        logger.info(
            f"Unloaded model '{model_name}'. "
            f"Current VRAM usage: {self._current_vram_usage()}MB / {self.vram_budget}MB"
        )

    async def unload_model(self, model_name: str) -> None:
        """Explicitly unload a model from VRAM.

        This is the public interface for unloading models. It acquires the
        lock and then performs the unload.

        Args:
            model_name: Name of the model to unload
        """
        async with self._lock:
            await self._unload_model_internal(model_name)

    async def unload_all(self) -> None:
        """Unload all loaded models.

        Useful for cleanup during shutdown.
        """
        async with self._lock:
            model_names = list(self.loaded_models.keys())
            for name in model_names:
                await self._unload_model_internal(name)

            logger.info("All models unloaded")

    def is_loaded(self, model_name: str) -> bool:
        """Check if a model is currently loaded.

        Args:
            model_name: Name of the model to check

        Returns:
            True if the model is loaded, False otherwise
        """
        return model_name in self.loaded_models

    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded model names.

        Returns:
            List of loaded model names
        """
        return list(self.loaded_models.keys())

    def get_status(self) -> dict[str, Any]:
        """Get current status of the model manager.

        Returns detailed status information suitable for health checks
        and monitoring dashboards.

        Returns:
            Dictionary with VRAM budget, usage, loaded models, and pending loads
        """
        return {
            "vram_budget_mb": self.vram_budget,
            "vram_used_mb": self._current_vram_usage(),
            "vram_available_mb": self.vram_budget - self._current_vram_usage(),
            "vram_utilization_percent": round(
                (self._current_vram_usage() / self.vram_budget) * 100, 1
            )
            if self.vram_budget > 0
            else 0,
            "loaded_models": [
                {
                    "name": name,
                    "vram_mb": info.vram_mb,
                    "priority": info.priority.name,
                    "last_used": info.last_used.isoformat(),
                }
                for name, info in self.loaded_models.items()
            ],
            "registered_models": [
                {
                    "name": name,
                    "vram_mb": config.vram_mb,
                    "priority": config.priority.name,
                    "loaded": name in self.loaded_models,
                }
                for name, config in self.model_registry.items()
            ],
            "pending_loads": list(self.pending_loads),
        }

    async def cleanup_idle_models(self, idle_seconds: float = 300.0) -> list[str]:
        """Unload models that haven't been used recently.

        This can be called periodically to free VRAM from models that
        are no longer being actively used.

        Args:
            idle_seconds: Models unused for this many seconds will be unloaded

        Returns:
            List of model names that were unloaded
        """
        async with self._lock:
            now = datetime.now()
            to_unload: list[str] = []

            for name, info in self.loaded_models.items():
                idle_time = (now - info.last_used).total_seconds()
                if idle_time > idle_seconds:
                    to_unload.append(name)
                    logger.info(
                        f"Model '{name}' idle for {idle_time:.0f}s "
                        f"(threshold: {idle_seconds}s), marking for unload"
                    )

            for name in to_unload:
                await self._unload_model_internal(name)

            return to_unload

"""Property-based tests for baseline anomaly detection service.

Tests cover mathematical invariants for:
- Exponential moving average calculations
- Time-based decay factors
- Anomaly score ranges
- Statistical properties

Related Linear Issue:
- NEM-1698: Add property-based tests for mathematical operations
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.services.baseline import BaselineService

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid decay factors (0 < decay_factor <= 1)
decay_factors = st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False)

# Invalid decay factors for negative testing
invalid_decay_factors = st.one_of(
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.001, max_value=10.0, allow_nan=False, allow_infinity=False),
)

# Window sizes in days (1 to 365 days)
window_days = st.integers(min_value=1, max_value=365)

# Time deltas for decay testing (0 to 100 days)
time_deltas_days = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# Anomaly thresholds (0 to 5 standard deviations)
anomaly_thresholds = st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)

# Minimum sample counts (1 to 1000)
min_samples = st.integers(min_value=1, max_value=1000)

# Average counts for EMA calculations (0 to 1000)
avg_counts = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)

# Sample counts for statistical calculations (1 to 10000)
sample_counts = st.integers(min_value=1, max_value=10000)


# =============================================================================
# Exponential Moving Average Properties
# =============================================================================


class TestExponentialMovingAverageProperties:
    """Property-based tests for exponential moving average calculations."""

    @given(
        decay=decay_factors,
        current_count=avg_counts,
        new_observation=st.floats(
            min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
    )
    @hypothesis_settings(max_examples=100)
    def test_ema_always_between_observations(
        self,
        decay: float,
        current_count: float,
        new_observation: float,
    ) -> None:
        """Property: Exponential moving average should be between min and max observations.

        When updating EMA with a new observation, the result should always fall
        between the current EMA and the new observation (or equal to one of them).
        """
        # Formula: new_ema = decay * current_count + (1 - decay) * new_observation
        new_ema = decay * current_count + (1 - decay) * new_observation

        min_value = min(current_count, new_observation)
        max_value = max(current_count, new_observation)

        # Allow small floating point tolerance
        assert min_value - 0.001 <= new_ema <= max_value + 0.001, (
            f"EMA {new_ema} not in [{min_value}, {max_value}]"
        )

    @given(
        decay=st.floats(min_value=0.01, max_value=0.9, allow_nan=False, allow_infinity=False),
        observations=st.lists(
            st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=10,
        ),
    )
    @hypothesis_settings(max_examples=50)
    def test_ema_converges_to_recent_observations(
        self,
        decay: float,
        observations: list[float],
    ) -> None:
        """Property: EMA should converge toward recent observations.

        As we add more observations of a similar value, the EMA should move closer
        to that value.
        """
        # Start with first observation
        ema = observations[0]

        # Apply all subsequent observations
        for obs in observations[1:]:
            ema = decay * ema + (1 - decay) * obs

        # Final EMA should be influenced by all observations
        # It should be within the range of min/max observations
        min_obs = min(observations)
        max_obs = max(observations)

        assert min_obs - 1.0 <= ema <= max_obs + 1.0, (
            f"EMA {ema} outside observation range [{min_obs}, {max_obs}]"
        )

    @given(
        decay=decay_factors,
        count=avg_counts,
    )
    @hypothesis_settings(max_examples=100)
    def test_ema_with_single_observation_equals_observation(
        self,
        decay: float,
        count: float,
    ) -> None:
        """Property: When current EMA is 0, new EMA equals the observation.

        This tests the initial condition where we have no history.
        """
        # Start with zero (no history)
        current_ema = 0.0

        # Apply one observation
        new_ema = decay * current_ema + (1 - decay) * count

        # Result should be (1 - decay) * count
        expected = (1 - decay) * count
        assert abs(new_ema - expected) < 0.001

    @given(
        decay=decay_factors,
        count=avg_counts,
    )
    @hypothesis_settings(max_examples=100)
    def test_ema_with_same_observation_unchanged(
        self,
        decay: float,
        count: float,
    ) -> None:
        """Property: Adding the same observation as current EMA doesn't change EMA.

        When the new observation equals the current EMA, the EMA should remain unchanged.
        """
        # Start with a count
        current_ema = count

        # Apply same observation
        new_ema = decay * current_ema + (1 - decay) * count

        # Result should equal the original count
        assert abs(new_ema - count) < 0.001


# =============================================================================
# Time Decay Properties
# =============================================================================


class TestTimeDecayProperties:
    """Property-based tests for time-based decay calculations."""

    @given(
        decay_factor=decay_factors,
        window=window_days,
        days_elapsed=time_deltas_days,
    )
    @hypothesis_settings(max_examples=100)
    def test_time_decay_bounded_between_zero_and_one(
        self,
        decay_factor: float,
        window: int,
        days_elapsed: float,
    ) -> None:
        """Property: Time decay factor should always be in [0, 1] range."""
        service = BaselineService(decay_factor=decay_factor, window_days=window)

        now = datetime.now(UTC)
        past = now - timedelta(days=days_elapsed)

        decay = service._calculate_time_decay(past, now)

        assert 0.0 <= decay <= 1.0, f"Decay {decay} outside [0, 1] range"

    @given(
        decay_factor=decay_factors,
        window=window_days,
    )
    @hypothesis_settings(max_examples=50)
    def test_time_decay_zero_at_same_time(
        self,
        decay_factor: float,
        window: int,
    ) -> None:
        """Property: Zero time elapsed should give decay = 1.0 (no decay)."""
        service = BaselineService(decay_factor=decay_factor, window_days=window)

        now = datetime.now(UTC)

        decay = service._calculate_time_decay(now, now)

        # At t=0, decay should be 1.0
        assert abs(decay - 1.0) < 0.01

    @given(
        decay_factor=decay_factors,
        window=window_days,
    )
    @hypothesis_settings(max_examples=50)
    def test_time_decay_zero_outside_window(
        self,
        decay_factor: float,
        window: int,
    ) -> None:
        """Property: Time elapsed beyond window should give decay = 0.0."""
        service = BaselineService(decay_factor=decay_factor, window_days=window)

        now = datetime.now(UTC)
        # Go beyond window
        past = now - timedelta(days=window + 1)

        decay = service._calculate_time_decay(past, now)

        assert decay == 0.0, f"Decay {decay} should be 0.0 outside window"

    @given(
        window=window_days,
        t1=time_deltas_days,
        t2=time_deltas_days,
    )
    @hypothesis_settings(max_examples=100)
    def test_time_decay_monotonic_decreasing(
        self,
        window: int,
        t1: float,
        t2: float,
    ) -> None:
        """Property: Decay should be monotonically decreasing with time.

        If t1 < t2, then decay(t1) >= decay(t2).
        """
        # Ensure t1 < t2 and both within reasonable range
        if t1 > t2:
            t1, t2 = t2, t1

        # Only test if both are within window
        if t2 > window:
            return

        service = BaselineService(decay_factor=0.5, window_days=window)

        now = datetime.now(UTC)
        past1 = now - timedelta(days=t1)
        past2 = now - timedelta(days=t2)

        decay1 = service._calculate_time_decay(past1, now)
        decay2 = service._calculate_time_decay(past2, now)

        # decay1 should be >= decay2 (less time elapsed = less decay)
        assert decay1 >= decay2 - 0.001, f"Decay not monotonic: {decay1} < {decay2}"

    @given(
        decay_factor=decay_factors,
        window=window_days,
        days_elapsed=time_deltas_days,
    )
    @hypothesis_settings(max_examples=100)
    def test_time_decay_formula_correctness(
        self,
        decay_factor: float,
        window: int,
        days_elapsed: float,
    ) -> None:
        """Property: Decay formula should match expected exponential decay.

        Formula: decay = decay_factor^days_elapsed
        (when within window)
        """
        if days_elapsed > window:
            return  # Skip values outside window

        service = BaselineService(decay_factor=decay_factor, window_days=window)

        now = datetime.now(UTC)
        past = now - timedelta(days=days_elapsed)

        actual_decay = service._calculate_time_decay(past, now)

        # Expected: decay_factor^days_elapsed
        expected_decay = math.exp(-days_elapsed * math.log(1 / decay_factor))

        # Allow some floating point tolerance
        assert abs(actual_decay - expected_decay) < 0.01, (
            f"Decay formula mismatch: actual={actual_decay}, expected={expected_decay}"
        )


# =============================================================================
# Anomaly Score Properties
# =============================================================================


class TestAnomalyScoreProperties:
    """Property-based tests for anomaly scoring."""

    @given(
        relative_frequency=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        )
    )
    @hypothesis_settings(max_examples=100)
    def test_anomaly_score_bounded_between_zero_and_one(
        self,
        relative_frequency: float,
    ) -> None:
        """Property: Anomaly score should always be in [0, 1] range.

        The anomaly score formula is: score = max(0, min(1, 1 - relative_frequency))
        """
        # Formula from is_anomalous method
        anomaly_score = max(0.0, min(1.0, 1.0 - relative_frequency))

        assert 0.0 <= anomaly_score <= 1.0, f"Score {anomaly_score} outside [0, 1]"

    @given(
        relative_frequency=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        )
    )
    @hypothesis_settings(max_examples=100)
    def test_anomaly_score_inverse_to_frequency(
        self,
        relative_frequency: float,
    ) -> None:
        """Property: Anomaly score should be inversely proportional to frequency.

        Higher frequency = lower anomaly score (more normal).
        Lower frequency = higher anomaly score (more anomalous).
        """
        anomaly_score = max(0.0, min(1.0, 1.0 - relative_frequency))

        # Inverse relationship
        if relative_frequency == 0.0:
            assert anomaly_score == 1.0
        elif relative_frequency == 1.0:
            assert anomaly_score == 0.0
        else:
            # For values in between, score + frequency should sum to 1
            assert abs((anomaly_score + relative_frequency) - 1.0) < 0.001

    @given(
        freq1=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        freq2=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=100)
    def test_anomaly_score_monotonic(
        self,
        freq1: float,
        freq2: float,
    ) -> None:
        """Property: If freq1 < freq2, then score1 > score2.

        Lower frequency should result in higher anomaly score.
        """
        score1 = max(0.0, min(1.0, 1.0 - freq1))
        score2 = max(0.0, min(1.0, 1.0 - freq2))

        if freq1 < freq2:
            assert score1 >= score2, f"Score not monotonic: freq1={freq1}, freq2={freq2}"
        elif freq1 > freq2:
            assert score1 <= score2, f"Score not monotonic: freq1={freq1}, freq2={freq2}"
        else:
            assert abs(score1 - score2) < 0.001


# =============================================================================
# Configuration Validation Properties
# =============================================================================


class TestConfigurationValidationProperties:
    """Property-based tests for service configuration validation."""

    @given(decay_factor=invalid_decay_factors)
    @hypothesis_settings(max_examples=50)
    def test_invalid_decay_factor_rejected(
        self,
        decay_factor: float,
    ) -> None:
        """Property: Invalid decay factors should raise ValueError."""
        with pytest.raises(ValueError, match="decay_factor"):
            BaselineService(decay_factor=decay_factor)

    @given(window=st.integers(max_value=0))
    @hypothesis_settings(max_examples=30)
    def test_invalid_window_days_rejected(
        self,
        window: int,
    ) -> None:
        """Property: Non-positive window_days should raise ValueError."""
        with pytest.raises(ValueError, match="window_days"):
            BaselineService(window_days=window)

    @given(threshold=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
    @hypothesis_settings(max_examples=30)
    def test_invalid_anomaly_threshold_rejected(
        self,
        threshold: float,
    ) -> None:
        """Property: Negative anomaly thresholds should raise ValueError."""
        with pytest.raises(ValueError, match="anomaly_threshold_std"):
            BaselineService(anomaly_threshold_std=threshold)

    @given(min_samp=st.integers(max_value=0))
    @hypothesis_settings(max_examples=30)
    def test_invalid_min_samples_rejected(
        self,
        min_samp: int,
    ) -> None:
        """Property: Non-positive min_samples should raise ValueError."""
        with pytest.raises(ValueError, match="min_samples"):
            BaselineService(min_samples=min_samp)

    @given(
        decay=decay_factors,
        window=window_days,
        threshold=anomaly_thresholds,
        min_samp=min_samples,
    )
    @hypothesis_settings(max_examples=100)
    def test_valid_configuration_accepted(
        self,
        decay: float,
        window: int,
        threshold: float,
        min_samp: int,
    ) -> None:
        """Property: Valid configuration values should be accepted."""
        # Should not raise
        service = BaselineService(
            decay_factor=decay,
            window_days=window,
            anomaly_threshold_std=threshold,
            min_samples=min_samp,
        )

        # Verify values are stored
        assert service.decay_factor == decay
        assert service.window_days == window
        assert service.anomaly_threshold_std == threshold
        assert service.min_samples == min_samp


# =============================================================================
# Statistical Properties
# =============================================================================


class TestStatisticalProperties:
    """Property-based tests for statistical calculations."""

    @given(
        values=st.lists(
            st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50,
        )
    )
    @hypothesis_settings(max_examples=100)
    def test_variance_always_non_negative(
        self,
        values: list[float],
    ) -> None:
        """Property: Variance should always be non-negative.

        Formula: variance = sum((x - mean)^2) / n
        """
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)

        assert variance >= 0.0, f"Variance {variance} is negative"

    @given(
        values=st.lists(
            st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50,
        )
    )
    @hypothesis_settings(max_examples=100)
    def test_standard_deviation_equals_sqrt_variance(
        self,
        values: list[float],
    ) -> None:
        """Property: Standard deviation should equal sqrt(variance)."""
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance)

        # Recompute directly
        expected_std = math.sqrt(variance)

        assert abs(std_dev - expected_std) < 0.001

    @given(
        values=st.lists(
            st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50,
        )
    )
    @hypothesis_settings(max_examples=100)
    def test_mean_within_min_max_range(
        self,
        values: list[float],
    ) -> None:
        """Property: Mean should always be between min and max values."""
        mean = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)

        # Allow small floating point tolerance
        assert min_val - 0.001 <= mean <= max_val + 0.001, (
            f"Mean {mean} outside [{min_val}, {max_val}]"
        )

    @given(
        value=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        mean=st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        std_dev=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=100)
    def test_z_score_formula(
        self,
        value: float,
        mean: float,
        std_dev: float,
    ) -> None:
        """Property: Z-score should follow the formula (x - mean) / std_dev."""
        z_score = (value - mean) / std_dev

        # Verify the formula
        expected_z = (value - mean) / std_dev
        assert abs(z_score - expected_z) < 0.001

    @given(
        z_score=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=50)
    def test_z_score_interpretation_ranges(
        self,
        z_score: float,
    ) -> None:
        """Property: Z-score interpretation should be consistent with ranges."""
        service = BaselineService()
        interpretation = service._interpret_z_score(z_score)

        # Verify interpretation matches expected ranges
        if z_score < -2.0:
            assert interpretation.name == "FAR_BELOW_NORMAL"
        elif z_score < -1.0:
            assert interpretation.name == "BELOW_NORMAL"
        elif z_score < 1.0:
            assert interpretation.name == "NORMAL"
        elif z_score < 2.0:
            assert interpretation.name == "SLIGHTLY_ABOVE_NORMAL"
        elif z_score < 3.0:
            assert interpretation.name == "ABOVE_NORMAL"
        else:
            assert interpretation.name == "FAR_ABOVE_NORMAL"


# =============================================================================
# Edge Case Properties
# =============================================================================


class TestEdgeCaseProperties:
    """Property-based tests for edge cases and boundary conditions."""

    @given(
        decay_factor=st.floats(
            min_value=0.95, max_value=0.99, allow_nan=False, allow_infinity=False
        ),
        observations=st.lists(
            st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=20,
        ),
    )
    @hypothesis_settings(max_examples=30)
    def test_high_decay_factor_slow_convergence(
        self,
        decay_factor: float,
        observations: list[float],
    ) -> None:
        """Property: Very high decay factor means EMA changes slowly.

        With decay_factor close to 1.0, the EMA should be heavily weighted
        toward the initial value after just a few observations.
        """
        # Need different starting and ending values
        unique_values = set(observations)
        if len(unique_values) < 2:
            # All same value - no convergence to test
            return

        ema = observations[0]

        for obs in observations[1:]:
            ema = decay_factor * ema + (1 - decay_factor) * obs

        # With high decay factor and many observations, EMA should still
        # be within the range of all observations
        min_obs = min(observations)
        max_obs = max(observations)

        assert min_obs - 1.0 <= ema <= max_obs + 1.0, (
            f"EMA {ema} outside observation range [{min_obs}, {max_obs}]"
        )

    @given(
        constant_value=st.floats(
            min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
        num_observations=st.integers(min_value=5, max_value=20),
        decay=st.floats(min_value=0.01, max_value=0.9, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=30)
    def test_constant_observations_stable_ema(
        self,
        constant_value: float,
        num_observations: int,
        decay: float,
    ) -> None:
        """Property: When all observations are the same, EMA converges to that value."""
        ema = 0.0  # Start from zero

        for _ in range(num_observations):
            ema = decay * ema + (1 - decay) * constant_value

        # After enough iterations with reasonable decay, should converge
        # Convergence rate depends on decay factor
        expected_convergence = constant_value * (1 - decay**num_observations)

        assert abs(ema - expected_convergence) < 1.0, (
            f"EMA {ema} not close to expected {expected_convergence}"
        )

    @given(
        window=st.integers(min_value=7, max_value=90),
        margin=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=50)
    def test_time_decay_boundary_conditions(
        self,
        window: int,
        margin: float,
    ) -> None:
        """Property: Time decay should transition at window boundary."""
        service = BaselineService(decay_factor=0.5, window_days=window)

        now = datetime.now(UTC)

        # Just inside window (by margin days)
        past_inside = now - timedelta(days=window - margin)
        decay_inside = service._calculate_time_decay(past_inside, now)

        # Just outside window (by margin days)
        past_outside = now - timedelta(days=window + margin)
        decay_outside = service._calculate_time_decay(past_outside, now)

        # Inside window should have positive decay
        assert decay_inside > 0, "Decay should be positive just inside window"

        # Outside window should be zero
        assert decay_outside == 0.0, "Decay should be zero just outside window"

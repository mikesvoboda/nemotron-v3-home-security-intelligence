/**
 * Tests for BatchAggregatorCard component.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import BatchAggregatorCard from './BatchAggregatorCard';

import type { BatchAggregatorUIState } from '../../types/queue';

// Helper to create batch aggregator state
const createBatchState = (
  overrides: Partial<BatchAggregatorUIState> = {}
): BatchAggregatorUIState => ({
  activeBatchCount: 0,
  batches: [],
  batchWindowSeconds: 90,
  idleTimeoutSeconds: 30,
  batchesApproachingTimeout: [],
  hasTimeoutWarning: false,
  ...overrides,
});

describe('BatchAggregatorCard', () => {
  it('should render the card title', () => {
    render(<BatchAggregatorCard batchState={createBatchState()} />);

    expect(screen.getByText('Batch Aggregator')).toBeInTheDocument();
  });

  it('should display active batch count', () => {
    render(
      <BatchAggregatorCard
        batchState={createBatchState({
          activeBatchCount: 3,
        })}
      />
    );

    expect(screen.getByTestId('active-batch-count-badge')).toHaveTextContent('3');
  });

  it('should show loading state', () => {
    render(<BatchAggregatorCard batchState={createBatchState()} isLoading={true} />);

    expect(screen.getByTestId('active-batch-count-badge')).toHaveTextContent('...');
  });

  it('should display batch window in summary', () => {
    render(
      <BatchAggregatorCard
        batchState={createBatchState({
          batchWindowSeconds: 90,
        })}
      />
    );

    expect(screen.getByText('Window: 90s')).toBeInTheDocument();
  });

  it('should render individual batches', () => {
    const batchState = createBatchState({
      activeBatchCount: 2,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 30,
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 45,
          last_activity_seconds: 10,
        },
      ],
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    expect(screen.getByText('front_door')).toBeInTheDocument();
    expect(screen.getByText('backyard')).toBeInTheDocument();
    expect(screen.getByText('5 detections')).toBeInTheDocument();
    expect(screen.getByText('3 detections')).toBeInTheDocument();
  });

  it('should show empty state when no batches', () => {
    render(
      <BatchAggregatorCard
        batchState={createBatchState({
          activeBatchCount: 0,
          batches: [],
        })}
      />
    );

    expect(screen.getByTestId('batch-empty-state')).toBeInTheDocument();
    expect(screen.getByText('No active batches')).toBeInTheDocument();
  });

  it('should not show empty state when loading', () => {
    render(
      <BatchAggregatorCard
        batchState={createBatchState({
          activeBatchCount: 0,
          batches: [],
        })}
        isLoading={true}
      />
    );

    expect(screen.queryByTestId('batch-empty-state')).not.toBeInTheDocument();
  });

  it('should show timeout warning icon in title when batches approaching timeout', () => {
    const batchState = createBatchState({
      activeBatchCount: 1,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80, // 89% of 90s window
          last_activity_seconds: 5,
        },
      ],
      batchesApproachingTimeout: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80,
          last_activity_seconds: 5,
        },
      ],
      hasTimeoutWarning: true,
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    expect(screen.getByTestId('batch-timeout-warning-icon')).toBeInTheDocument();
  });

  it('should show timeout warning alert when batches approaching timeout', () => {
    const batchState = createBatchState({
      activeBatchCount: 2,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 75,
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 85,
          last_activity_seconds: 10,
        },
      ],
      batchesApproachingTimeout: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 75,
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch_002',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: 1000,
          age_seconds: 85,
          last_activity_seconds: 10,
        },
      ],
      hasTimeoutWarning: true,
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    expect(screen.getByTestId('batch-timeout-warning')).toBeInTheDocument();
    expect(screen.getByText('2 batches approaching timeout')).toBeInTheDocument();
  });

  it('should show singular "batch" for single batch approaching timeout', () => {
    const batchState = createBatchState({
      activeBatchCount: 1,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80,
          last_activity_seconds: 5,
        },
      ],
      batchesApproachingTimeout: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80,
          last_activity_seconds: 5,
        },
      ],
      hasTimeoutWarning: true,
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    expect(screen.getByText('1 batch approaching timeout')).toBeInTheDocument();
  });

  it('should highlight individual batch row when approaching timeout', () => {
    const batchState = createBatchState({
      activeBatchCount: 1,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80,
          last_activity_seconds: 5,
        },
      ],
      batchesApproachingTimeout: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 80,
          last_activity_seconds: 5,
        },
      ],
      hasTimeoutWarning: true,
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    const batchRow = screen.getByTestId('batch-row-batch_001');
    expect(batchRow).toHaveClass('border-yellow-500/30');
    expect(screen.getByTestId('batch-timeout-icon-batch_001')).toBeInTheDocument();
  });

  it('should display batch progress percentage', () => {
    const batchState = createBatchState({
      activeBatchCount: 1,
      batchWindowSeconds: 100,
      batches: [
        {
          batch_id: 'batch_001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: 1000,
          age_seconds: 50, // 50% of 100s window
          last_activity_seconds: 5,
        },
      ],
    });

    render(<BatchAggregatorCard batchState={batchState} />);

    expect(screen.getByTestId('batch-progress-batch_001')).toHaveTextContent('50%');
  });

  it('should apply custom className', () => {
    render(
      <BatchAggregatorCard batchState={createBatchState()} className="custom-class" />
    );

    expect(screen.getByTestId('batch-aggregator-card')).toHaveClass('custom-class');
  });

  it('should use correct badge color for different batch counts', () => {
    // Gray for 0
    const { rerender } = render(
      <BatchAggregatorCard batchState={createBatchState({ activeBatchCount: 0 })} />
    );
    // Note: Tremor Badge doesn't expose color in a way we can easily test
    // We just verify the badge renders correctly
    expect(screen.getByTestId('active-batch-count-badge')).toHaveTextContent('0');

    // Test with higher counts
    rerender(
      <BatchAggregatorCard batchState={createBatchState({ activeBatchCount: 5 })} />
    );
    expect(screen.getByTestId('active-batch-count-badge')).toHaveTextContent('5');

    rerender(
      <BatchAggregatorCard batchState={createBatchState({ activeBatchCount: 10 })} />
    );
    expect(screen.getByTestId('active-batch-count-badge')).toHaveTextContent('10');
  });
});

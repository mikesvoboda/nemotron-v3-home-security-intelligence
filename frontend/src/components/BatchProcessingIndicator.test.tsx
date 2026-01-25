/**
 * Tests for BatchProcessingIndicator component (NEM-3607)
 *
 * Tests that the indicator shows real-time batch processing status:
 * - Batches currently being analyzed
 * - Recently completed batches with risk scores
 * - Failed batches with error information
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import BatchProcessingIndicator, { BatchStatusItem } from './BatchProcessingIndicator';

import type { BatchStatus } from '../hooks/useBatchProcessingStatus';

// Mock the useBatchProcessingStatus hook
vi.mock('../hooks/useBatchProcessingStatus', () => ({
  useBatchProcessingStatus: vi.fn(() => ({
    batchStatuses: new Map(),
    processingBatches: [],
    completedBatches: [],
    failedBatches: [],
    activeCount: 0,
    isConnected: true,
    getBatchStatus: vi.fn(),
    clearHistory: vi.fn(),
  })),
}));

import { useBatchProcessingStatus } from '../hooks/useBatchProcessingStatus';

describe('BatchProcessingIndicator', () => {
  const mockUseBatchProcessingStatus = vi.mocked(useBatchProcessingStatus);

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset to default mock state
    mockUseBatchProcessingStatus.mockReturnValue({
      batchStatuses: new Map(),
      processingBatches: [],
      completedBatches: [],
      failedBatches: [],
      activeCount: 0,
      isConnected: true,
      getBatchStatus: vi.fn(),
      clearHistory: vi.fn(),
    });
  });

  describe('visibility conditions', () => {
    it('does not render when not connected', () => {
      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map(),
        processingBatches: [],
        completedBatches: [],
        failedBatches: [],
        activeCount: 0,
        isConnected: false,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.queryByTestId('batch-processing-indicator')).not.toBeInTheDocument();
    });

    it('does not render when connected but no activity', () => {
      render(<BatchProcessingIndicator />);
      expect(screen.queryByTestId('batch-processing-indicator')).not.toBeInTheDocument();
    });

    it('renders when there are processing batches', () => {
      const processingBatch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 3,
        updatedAt: '2026-01-13T12:01:30.000Z',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', processingBatch]]),
        processingBatches: [processingBatch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByTestId('batch-processing-indicator')).toBeInTheDocument();
    });

    it('renders when there are completed batches', () => {
      const completedBatch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'completed',
        detectionCount: 3,
        updatedAt: '2026-01-13T12:01:35.000Z',
        eventId: 42,
        riskScore: 75,
        riskLevel: 'high',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', completedBatch]]),
        processingBatches: [],
        completedBatches: [completedBatch],
        failedBatches: [],
        activeCount: 0,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByTestId('batch-processing-indicator')).toBeInTheDocument();
    });

    it('renders when there are failed batches', () => {
      const failedBatch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'failed',
        detectionCount: 3,
        updatedAt: '2026-01-13T12:03:30.000Z',
        error: 'Timeout error',
        errorType: 'timeout',
        retryable: true,
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', failedBatch]]),
        processingBatches: [],
        completedBatches: [],
        failedBatches: [failedBatch],
        activeCount: 0,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByTestId('batch-processing-indicator')).toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('does not render compact indicator when no active batches', () => {
      render(<BatchProcessingIndicator compact />);
      expect(screen.queryByTestId('batch-processing-indicator-compact')).not.toBeInTheDocument();
    });

    it('renders compact indicator with count when batches are processing', () => {
      const processingBatch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 3,
        updatedAt: '2026-01-13T12:01:30.000Z',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', processingBatch]]),
        processingBatches: [processingBatch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator compact />);
      const indicator = screen.getByTestId('batch-processing-indicator-compact');
      expect(indicator).toBeInTheDocument();
      expect(indicator).toHaveTextContent('1');
    });

    it('compact mode has correct aria-label', () => {
      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map(),
        processingBatches: [
          { batchId: 'b1', cameraId: 'c1', state: 'analyzing', detectionCount: 1, updatedAt: '' },
          { batchId: 'b2', cameraId: 'c2', state: 'analyzing', detectionCount: 1, updatedAt: '' },
        ],
        completedBatches: [],
        failedBatches: [],
        activeCount: 2,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator compact />);
      const indicator = screen.getByTestId('batch-processing-indicator-compact');
      expect(indicator).toHaveAttribute('aria-label', '2 batches analyzing');
    });

    it('compact mode handles singular batch correctly', () => {
      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map(),
        processingBatches: [
          { batchId: 'b1', cameraId: 'c1', state: 'analyzing', detectionCount: 1, updatedAt: '' },
        ],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator compact />);
      const indicator = screen.getByTestId('batch-processing-indicator-compact');
      expect(indicator).toHaveAttribute('aria-label', '1 batch analyzing');
    });
  });

  describe('full mode content', () => {
    it('displays header with AI Analysis title', () => {
      const processingBatch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 3,
        updatedAt: '2026-01-13T12:01:30.000Z',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', processingBatch]]),
        processingBatches: [processingBatch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByText('AI Analysis')).toBeInTheDocument();
      expect(screen.getByText('1 processing')).toBeInTheDocument();
    });

    it('shows processing batches', () => {
      const batch: BatchStatus = {
        batchId: 'batch_test',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 5,
        updatedAt: '2026-01-13T12:01:30.000Z',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_test', batch]]),
        processingBatches: [batch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByTestId('batch-status-batch_test')).toBeInTheDocument();
      expect(screen.getByText('Analyzing')).toBeInTheDocument();
      expect(screen.getByText('(5)')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('full mode has role="region"', () => {
      const batch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 3,
        updatedAt: '',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', batch]]),
        processingBatches: [batch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator />);
      expect(screen.getByRole('region')).toBeInTheDocument();
    });

    it('compact mode has role="status"', () => {
      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map(),
        processingBatches: [
          { batchId: 'b1', cameraId: 'c1', state: 'analyzing', detectionCount: 1, updatedAt: '' },
        ],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator compact />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className in full mode', () => {
      const batch: BatchStatus = {
        batchId: 'batch_123',
        cameraId: 'front_door',
        state: 'analyzing',
        detectionCount: 3,
        updatedAt: '',
      };

      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map([['batch_123', batch]]),
        processingBatches: [batch],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator className="my-custom-class" />);
      const indicator = screen.getByTestId('batch-processing-indicator');
      expect(indicator.className).toContain('my-custom-class');
    });

    it('applies custom className in compact mode', () => {
      mockUseBatchProcessingStatus.mockReturnValue({
        batchStatuses: new Map(),
        processingBatches: [
          { batchId: 'b1', cameraId: 'c1', state: 'analyzing', detectionCount: 1, updatedAt: '' },
        ],
        completedBatches: [],
        failedBatches: [],
        activeCount: 1,
        isConnected: true,
        getBatchStatus: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(<BatchProcessingIndicator compact className="my-compact-class" />);
      const indicator = screen.getByTestId('batch-processing-indicator-compact');
      expect(indicator.className).toContain('my-compact-class');
    });
  });
});

describe('BatchStatusItem', () => {
  it('renders analyzing state correctly', () => {
    const status: BatchStatus = {
      batchId: 'batch_123',
      cameraId: 'front_door',
      state: 'analyzing',
      detectionCount: 3,
      updatedAt: '2026-01-13T12:01:30.000Z',
    };

    render(<BatchStatusItem status={status} />);
    expect(screen.getByText('Analyzing')).toBeInTheDocument();
    expect(screen.getByText('front_door')).toBeInTheDocument();
    expect(screen.getByText('(3)')).toBeInTheDocument();
  });

  it('renders completed state with risk score', () => {
    const status: BatchStatus = {
      batchId: 'batch_123',
      cameraId: 'front_door',
      state: 'completed',
      detectionCount: 3,
      updatedAt: '2026-01-13T12:01:35.000Z',
      eventId: 42,
      riskScore: 75,
      riskLevel: 'high',
    };

    render(<BatchStatusItem status={status} />);
    expect(screen.getByText('Complete')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
  });

  it('renders failed state with error indicator', () => {
    const status: BatchStatus = {
      batchId: 'batch_123',
      cameraId: 'front_door',
      state: 'failed',
      detectionCount: 3,
      updatedAt: '2026-01-13T12:03:30.000Z',
      error: 'Connection timeout',
      errorType: 'timeout',
      retryable: true,
    };

    render(<BatchStatusItem status={status} />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('!')).toBeInTheDocument();
  });

  it('hides camera when showCamera is false', () => {
    const status: BatchStatus = {
      batchId: 'batch_123',
      cameraId: 'front_door',
      state: 'analyzing',
      detectionCount: 3,
      updatedAt: '',
    };

    render(<BatchStatusItem status={status} showCamera={false} />);
    expect(screen.queryByText('front_door')).not.toBeInTheDocument();
  });
});

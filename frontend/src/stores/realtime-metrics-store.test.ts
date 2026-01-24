/**
 * Tests for Real-time Metrics Store (NEM-3403, NEM-3426)
 */

import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useRealtimeMetricsStore,
  handleGPUStatsEvent,
  handlePipelineMetricsEvent,
  handleInferenceMetricsEvent,
  selectGPUUtilization,
  selectGPUMemoryUtilization,
  selectGPUTemperature,
  selectPipelineThroughput,
  selectTotalQueueDepth,
  selectPipelineErrorRate,
  selectCombinedModelLatency,
  selectGPUHealthStatus,
  selectPipelineHealthStatus,
  type GPUStatsEventPayload,
  type PipelineMetricsEventPayload,
  type InferenceMetricsEventPayload,
} from './realtime-metrics-store';

describe('realtime-metrics-store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset store state before each test
    useRealtimeMetricsStore.getState().clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial state', () => {
    it('has zero values for all GPU metrics initially', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(0);
      expect(state.gpu.data.memoryUsed).toBe(0);
      expect(state.gpu.data.temperature).toBe(0);
      expect(state.gpu.lastUpdated).toBeGreaterThan(0);
    });

    it('has zero values for all pipeline metrics initially', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(state.pipeline.data.detectionQueueDepth).toBe(0);
      expect(state.pipeline.data.throughput).toBe(0);
      expect(state.pipeline.data.errorRate).toBe(0);
    });

    it('has zero values for all inference metrics initially', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(state.inference.data.rtdetrLatency).toBe(0);
      expect(state.inference.data.nemotronLatency).toBe(0);
      expect(state.inference.data.currentBatchSize).toBe(0);
    });
  });

  describe('updateGPU', () => {
    it('updates GPU metrics', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 75,
          temperature: 65,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(75);
      expect(state.gpu.data.temperature).toBe(65);
    });

    it('preserves unmodified metrics', () => {
      // First update
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          memoryUsed: 1000,
        });
      });

      // Second update - only changes utilization
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 75,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(75);
      expect(state.gpu.data.memoryUsed).toBe(1000); // Preserved
    });

    it('updates lastUpdated timestamp', () => {
      const beforeUpdate = Date.now();

      act(() => {
        vi.advanceTimersByTime(100);
        useRealtimeMetricsStore.getState().updateGPU({ utilization: 50 });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.gpu.lastUpdated).toBeGreaterThan(beforeUpdate);
    });
  });

  describe('updatePipeline', () => {
    it('updates pipeline metrics', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 10,
          analysisQueueDepth: 5,
          throughput: 100,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.pipeline.data.detectionQueueDepth).toBe(10);
      expect(state.pipeline.data.analysisQueueDepth).toBe(5);
      expect(state.pipeline.data.throughput).toBe(100);
    });
  });

  describe('updateInference', () => {
    it('updates inference metrics', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateInference({
          rtdetrLatency: 25,
          nemotronLatency: 100,
          currentBatchSize: 4,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.inference.data.rtdetrLatency).toBe(25);
      expect(state.inference.data.nemotronLatency).toBe(100);
      expect(state.inference.data.currentBatchSize).toBe(4);
    });
  });

  describe('clear', () => {
    it('resets all metrics to initial values', () => {
      // Set some values
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({ utilization: 90 });
        useRealtimeMetricsStore.getState().updatePipeline({ throughput: 500 });
        useRealtimeMetricsStore.getState().updateInference({ rtdetrLatency: 30 });
      });

      // Clear
      act(() => {
        useRealtimeMetricsStore.getState().clear();
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(0);
      expect(state.pipeline.data.throughput).toBe(0);
      expect(state.inference.data.rtdetrLatency).toBe(0);
    });
  });

  describe('subscribeWithSelector', () => {
    it('allows subscribing to specific metrics', () => {
      const utilizationCallback = vi.fn();
      const temperatureCallback = vi.fn();

      // Subscribe to specific metrics using subscribeWithSelector overload
      const unsubUtil = (useRealtimeMetricsStore.subscribe as any)(
        (state: { gpu: { data: { utilization: number } } }) => state.gpu.data.utilization,
        utilizationCallback
      );
      const unsubTemp = (useRealtimeMetricsStore.subscribe as any)(
        (state: { gpu: { data: { temperature: number } } }) => state.gpu.data.temperature,
        temperatureCallback
      );

      // Update only utilization
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({ utilization: 80 });
      });

      expect(utilizationCallback).toHaveBeenCalledWith(80, 0);
      expect(temperatureCallback).not.toHaveBeenCalled();

      // Cleanup
      unsubUtil();
      unsubTemp();
    });

    it('does not fire callback when value unchanged', () => {
      const callback = vi.fn();

      const unsub = (useRealtimeMetricsStore.subscribe as any)(
        (state: { gpu: { data: { utilization: number } } }) => state.gpu.data.utilization,
        callback
      );

      // Set to 50
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({ utilization: 50 });
      });

      expect(callback).toHaveBeenCalledTimes(1);

      // Set to same value
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({ utilization: 50 });
      });

      // Should still be 1 (no change)
      expect(callback).toHaveBeenCalledTimes(1);

      unsub();
    });
  });

  describe('WebSocket event handlers', () => {
    it('handleGPUStatsEvent transforms and batches updates', () => {
      const event: GPUStatsEventPayload = {
        gpu_utilization: 75,
        memory_used: 8000000000,
        memory_total: 12000000000,
        memory_utilization: 67,
        temperature: 72,
        power_draw: 200,
        power_limit: 300,
      };

      // Send event
      act(() => {
        handleGPUStatsEvent(event);
      });

      // Should not be applied immediately (batched)
      let state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(0); // Not yet

      // Advance timer past batch window
      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Now should be applied
      state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(75);
      expect(state.gpu.data.memoryUsed).toBe(8000000000);
      expect(state.gpu.data.temperature).toBe(72);
    });

    it('handlePipelineMetricsEvent transforms and batches updates', () => {
      const event: PipelineMetricsEventPayload = {
        detection_queue_depth: 15,
        analysis_queue_depth: 8,
        throughput: 250,
        average_latency_ms: 45,
        p95_latency_ms: 80,
        p99_latency_ms: 120,
        error_rate: 0.02,
      };

      act(() => {
        handlePipelineMetricsEvent(event);
        vi.advanceTimersByTime(100);
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.pipeline.data.detectionQueueDepth).toBe(15);
      expect(state.pipeline.data.analysisQueueDepth).toBe(8);
      expect(state.pipeline.data.throughput).toBe(250);
      expect(state.pipeline.data.errorRate).toBe(0.02);
    });

    it('handleInferenceMetricsEvent transforms and batches updates', () => {
      const event: InferenceMetricsEventPayload = {
        rtdetr_latency_ms: 28,
        rtdetr_inference_count: 1000,
        nemotron_latency_ms: 95,
        nemotron_inference_count: 500,
        current_batch_size: 8,
      };

      act(() => {
        handleInferenceMetricsEvent(event);
        vi.advanceTimersByTime(100);
      });

      const state = useRealtimeMetricsStore.getState();
      expect(state.inference.data.rtdetrLatency).toBe(28);
      expect(state.inference.data.nemotronLatency).toBe(95);
      expect(state.inference.data.currentBatchSize).toBe(8);
    });

    it('batches multiple rapid events', () => {
      // Send 3 rapid events
      act(() => {
        handleGPUStatsEvent({
          gpu_utilization: 50,
          memory_used: 0,
          memory_total: 0,
          memory_utilization: 0,
          temperature: 60,
          power_draw: 0,
          power_limit: 0,
        });
        handleGPUStatsEvent({
          gpu_utilization: 55,
          memory_used: 0,
          memory_total: 0,
          memory_utilization: 0,
          temperature: 62,
          power_draw: 0,
          power_limit: 0,
        });
        handleGPUStatsEvent({
          gpu_utilization: 60,
          memory_used: 0,
          memory_total: 0,
          memory_utilization: 0,
          temperature: 65,
          power_draw: 0,
          power_limit: 0,
        });
      });

      // Before batch window
      let state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(0);

      // After batch window - should have final values
      act(() => {
        vi.advanceTimersByTime(100);
      });

      state = useRealtimeMetricsStore.getState();
      expect(state.gpu.data.utilization).toBe(60); // Last value
      expect(state.gpu.data.temperature).toBe(65);
    });
  });

  describe('selectors', () => {
    beforeEach(() => {
      // Set up test data
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 75,
          memoryUsed: 8000000000,
          memoryTotal: 12000000000,
          memoryUtilization: 67,
          temperature: 72,
          powerDraw: 200,
          powerLimit: 300,
        });
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 15,
          analysisQueueDepth: 10,
          throughput: 250,
          averageLatency: 45,
          p95Latency: 80,
          p99Latency: 120,
          errorRate: 0.02,
        });
        useRealtimeMetricsStore.getState().updateInference({
          rtdetrLatency: 25,
          rtdetrInferenceCount: 1000,
          nemotronLatency: 100,
          nemotronInferenceCount: 500,
          currentBatchSize: 4,
        });
      });
    });

    it('selectGPUUtilization returns correct value', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUUtilization(state)).toBe(75);
    });

    it('selectGPUMemoryUtilization returns correct value', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUMemoryUtilization(state)).toBe(67);
    });

    it('selectGPUTemperature returns correct value', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUTemperature(state)).toBe(72);
    });

    it('selectPipelineThroughput returns correct value', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineThroughput(state)).toBe(250);
    });

    it('selectTotalQueueDepth returns sum of queues', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectTotalQueueDepth(state)).toBe(25); // 15 + 10
    });

    it('selectPipelineErrorRate returns correct value', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineErrorRate(state)).toBe(0.02);
    });

    it('selectCombinedModelLatency returns sum of latencies', () => {
      const state = useRealtimeMetricsStore.getState();
      expect(selectCombinedModelLatency(state)).toBe(125); // 25 + 100
    });
  });

  describe('selectGPUHealthStatus', () => {
    it('returns healthy for normal values', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          temperature: 60,
          memoryUtilization: 50,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('healthy');
    });

    it('returns warning for high utilization', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 90,
          temperature: 70,
          memoryUtilization: 60,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('warning');
    });

    it('returns warning for high temperature', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          temperature: 82,
          memoryUtilization: 60,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('warning');
    });

    it('returns warning for high memory utilization', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          temperature: 70,
          memoryUtilization: 88,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('warning');
    });

    it('returns critical for very high temperature', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          temperature: 92,
          memoryUtilization: 60,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('critical');
    });

    it('returns critical for very high memory utilization', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updateGPU({
          utilization: 50,
          temperature: 70,
          memoryUtilization: 96,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectGPUHealthStatus(state)).toBe('critical');
    });
  });

  describe('selectPipelineHealthStatus', () => {
    it('returns healthy for normal values', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 10,
          analysisQueueDepth: 10,
          errorRate: 0.01,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineHealthStatus(state)).toBe('healthy');
    });

    it('returns warning for elevated error rate', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 10,
          analysisQueueDepth: 10,
          errorRate: 0.06,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineHealthStatus(state)).toBe('warning');
    });

    it('returns warning for building queue', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 30,
          analysisQueueDepth: 25,
          errorRate: 0.01,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineHealthStatus(state)).toBe('warning');
    });

    it('returns critical for high error rate', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 10,
          analysisQueueDepth: 10,
          errorRate: 0.12,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineHealthStatus(state)).toBe('critical');
    });

    it('returns critical for extremely backed up queue', () => {
      act(() => {
        useRealtimeMetricsStore.getState().updatePipeline({
          detectionQueueDepth: 60,
          analysisQueueDepth: 50,
          errorRate: 0.01,
        });
      });

      const state = useRealtimeMetricsStore.getState();
      expect(selectPipelineHealthStatus(state)).toBe('critical');
    });
  });
});

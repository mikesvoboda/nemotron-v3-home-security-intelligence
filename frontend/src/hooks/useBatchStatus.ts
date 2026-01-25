/**
 * useBatchStatus - Real-time batch processing status monitoring hook
 *
 * NEM-3652: Provides real-time monitoring of batch configuration status
 * including active batches and processing metrics via WebSocket.
 *
 * @module hooks/useBatchStatus
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';

import { useDetectionStream } from './useDetectionStream';
import type { DetectionBatchData } from '../types/websocket';

export interface ActiveBatch {
  batchId: string;
  cameraId: string;
  detectionCount: number;
  startedAt: string;
  duration: number;
  progress: number;
}

export interface QueueDepths {
  detection_queue: number;
  analysis_queue: number;
}

export interface BatchStats {
  batchesProcessed: number;
  detectionsProcessed: number;
  avgBatchSize: number;
  avgBatchDuration: number;
  lastCloseReason: string | null;
}

export interface UseBatchStatusOptions {
  enabled?: boolean;
  batchWindowSeconds?: number;
  queuePollInterval?: number;
}

export interface UseBatchStatusReturn {
  activeBatches: ActiveBatch[];
  queueDepths: QueueDepths | null;
  stats: BatchStats;
  recentBatches: DetectionBatchData[];
  isConnected: boolean;
  isLoadingQueues: boolean;
  queueError: Error | null;
  resetStats: () => void;
}

const DEFAULT_BATCH_WINDOW_SECONDS = 90;

export function useBatchStatus(options: UseBatchStatusOptions = {}): UseBatchStatusReturn {
  const { enabled = true, batchWindowSeconds = DEFAULT_BATCH_WINDOW_SECONDS } = options;

  const [activeBatchMap, setActiveBatchMap] = useState<Map<string, ActiveBatch>>(new Map());
  const [batchesProcessed, setBatchesProcessed] = useState(0);
  const [detectionsProcessed, setDetectionsProcessed] = useState(0);
  const [totalBatchDuration, setTotalBatchDuration] = useState(0);
  const [lastCloseReason, setLastCloseReason] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const updateProgress = () => {
      if (!isMountedRef.current) return;
      setActiveBatchMap((prev) => {
        const now = new Date().getTime();
        const updated = new Map(prev);
        for (const [cameraId, batch] of updated) {
          const startTime = new Date(batch.startedAt).getTime();
          const duration = (now - startTime) / 1000;
          const progress = Math.min((duration / batchWindowSeconds) * 100, 100);
          updated.set(cameraId, { ...batch, duration, progress });
        }
        return updated;
      });
    };
    const interval = setInterval(updateProgress, 1000);
    return () => clearInterval(interval);
  }, [enabled, batchWindowSeconds]);

  const handleDetection = useCallback(
    (detection: { detection_id: number; batch_id: string; camera_id: string; timestamp: string }) => {
      if (!isMountedRef.current) return;
      setActiveBatchMap((prev) => {
        const updated = new Map(prev);
        const existing = updated.get(detection.camera_id);
        if (existing && existing.batchId === detection.batch_id) {
          updated.set(detection.camera_id, { ...existing, detectionCount: existing.detectionCount + 1 });
        } else {
          updated.set(detection.camera_id, {
            batchId: detection.batch_id,
            cameraId: detection.camera_id,
            detectionCount: 1,
            startedAt: detection.timestamp,
            duration: 0,
            progress: 0,
          });
        }
        return updated;
      });
    },
    []
  );

  const handleBatch = useCallback((batch: DetectionBatchData) => {
    if (!isMountedRef.current) return;
    setActiveBatchMap((prev) => {
      const updated = new Map(prev);
      updated.delete(batch.camera_id);
      return updated;
    });
    setBatchesProcessed((prev) => prev + 1);
    setDetectionsProcessed((prev) => prev + batch.detection_count);
    setLastCloseReason(batch.close_reason ?? null);
    const startTime = new Date(batch.started_at).getTime();
    const endTime = new Date(batch.closed_at).getTime();
    const durationSeconds = (endTime - startTime) / 1000;
    setTotalBatchDuration((prev) => prev + durationSeconds);
  }, []);

  const { batches: recentBatches, isConnected } = useDetectionStream({
    enabled,
    maxBatches: 10,
    onDetection: handleDetection,
    onBatch: handleBatch,
  });

  const activeBatches = useMemo(() => Array.from(activeBatchMap.values()), [activeBatchMap]);

  const stats: BatchStats = useMemo(
    () => ({
      batchesProcessed,
      detectionsProcessed,
      avgBatchSize: batchesProcessed > 0 ? detectionsProcessed / batchesProcessed : 0,
      avgBatchDuration: batchesProcessed > 0 ? totalBatchDuration / batchesProcessed : 0,
      lastCloseReason,
    }),
    [batchesProcessed, detectionsProcessed, totalBatchDuration, lastCloseReason]
  );

  const resetStats = useCallback(() => {
    if (!isMountedRef.current) return;
    setActiveBatchMap(new Map());
    setBatchesProcessed(0);
    setDetectionsProcessed(0);
    setTotalBatchDuration(0);
    setLastCloseReason(null);
  }, []);

  return {
    activeBatches,
    queueDepths: null,
    stats,
    recentBatches,
    isConnected,
    isLoadingQueues: false,
    queueError: null,
    resetStats,
  };
}

export default useBatchStatus;

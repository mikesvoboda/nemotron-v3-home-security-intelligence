/**
 * useJobWebSocket - Hook for subscribing to background job WebSocket events
 */

import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';

import { useToast } from './useToast';
import { useWebSocket } from './useWebSocket';
import { logger } from '../services/logger';
import { queryKeys } from '../services/queryClient';
import {
  isJobProgressMessage,
  isJobCompletedMessage,
  isJobFailedMessage,
} from '../types/websocket';

import type { JobProgressData, JobCompletedData, JobFailedData } from '../types/websocket';

export interface UseJobWebSocketOptions {
  /** Base URL for the WebSocket connection (defaults to window.location) */
  baseUrl?: string;
  /** Whether to enable the WebSocket connection (default: true) */
  enabled?: boolean;
  /** Callback when job progress updates are received */
  onJobProgress?: (data: JobProgressData) => void;
  /** Callback when a job completes successfully */
  onJobCompleted?: (data: JobCompletedData) => void;
  /** Callback when a job fails */
  onJobFailed?: (data: JobFailedData) => void;
  /** Whether to show toast notifications for job completion/failure (default: true) */
  showToasts?: boolean;
  /** Whether to invalidate React Query caches on job completion (default: true) */
  invalidateQueries?: boolean;
}

export interface ActiveJob {
  job_id: string;
  job_type: string;
  progress: number;
  status: string;
}

export interface UseJobWebSocketReturn {
  activeJobs: ActiveJob[];
  isJobRunning: (jobType: string) => boolean;
  hasActiveJobs: boolean;
  isConnected: boolean;
}

function getJobTypeLabel(jobType: string): string {
  const labels: Record<string, string> = {
    export: 'Export',
    cleanup: 'Cleanup',
    backup: 'Backup',
    sync: 'Sync',
  };
  return labels[jobType] || jobType;
}

function getQueryKeysForJobType(jobType: string): readonly (readonly unknown[])[] {
  switch (jobType) {
    case 'export':
    case 'cleanup':
    default:
      return [queryKeys.events.all];
  }
}

function getJobsWebSocketUrl(baseUrl?: string): string {
  if (baseUrl) {
    return `${baseUrl}/ws/events`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/events`;
}

export function useJobWebSocket(options: UseJobWebSocketOptions = {}): UseJobWebSocketReturn {
  const {
    baseUrl,
    enabled = true,
    onJobProgress,
    onJobCompleted,
    onJobFailed,
    showToasts = true,
    invalidateQueries = true,
  } = options;

  const queryClient = useQueryClient();
  const { success, error } = useToast();

  const [activeJobs, setActiveJobs] = useState<Map<string, ActiveJob>>(new Map());

  const onJobProgressRef = useRef(onJobProgress);
  const onJobCompletedRef = useRef(onJobCompleted);
  const onJobFailedRef = useRef(onJobFailed);

  useEffect(() => {
    onJobProgressRef.current = onJobProgress;
    onJobCompletedRef.current = onJobCompleted;
    onJobFailedRef.current = onJobFailed;
  });

  const handleMessage = useCallback(
    (data: unknown) => {
      if (isJobProgressMessage(data)) {
        const progressData = data.data;
        logger.debug('Job progress', {
          job_id: progressData.job_id,
          job_type: progressData.job_type,
          progress: progressData.progress,
        });
        setActiveJobs((prev) => {
          const next = new Map(prev);
          next.set(progressData.job_id, {
            job_id: progressData.job_id,
            job_type: progressData.job_type,
            progress: progressData.progress,
            status: progressData.status,
          });
          return next;
        });
        onJobProgressRef.current?.(progressData);
        return;
      }

      if (isJobCompletedMessage(data)) {
        const completedData = data.data;
        logger.info('Job completed', {
          job_id: completedData.job_id,
          job_type: completedData.job_type,
        });
        setActiveJobs((prev) => {
          const next = new Map(prev);
          next.delete(completedData.job_id);
          return next;
        });
        if (showToasts) {
          const label = getJobTypeLabel(completedData.job_type);
          success(`${label} completed successfully`);
        }
        if (invalidateQueries) {
          const keys = getQueryKeysForJobType(completedData.job_type);
          for (const key of keys) {
            void queryClient.invalidateQueries({ queryKey: key });
          }
        }
        onJobCompletedRef.current?.(completedData);
        return;
      }

      if (isJobFailedMessage(data)) {
        const failedData = data.data;
        logger.error('Job failed', {
          job_id: failedData.job_id,
          job_type: failedData.job_type,
          error: failedData.error,
        });
        setActiveJobs((prev) => {
          const next = new Map(prev);
          next.delete(failedData.job_id);
          return next;
        });
        if (showToasts) {
          const label = getJobTypeLabel(failedData.job_type);
          error(`${label} failed: ${failedData.error}`);
        }
        onJobFailedRef.current?.(failedData);
        return;
      }
    },
    [queryClient, success, error, showToasts, invalidateQueries]
  );

  // Only compute URL when enabled to avoid unnecessary WebSocket connections
  const wsUrl = useMemo(
    () => (enabled ? getJobsWebSocketUrl(baseUrl) : ''),
    [baseUrl, enabled]
  );

  // useWebSocket with an empty URL effectively disables the connection
  // We pass a valid URL only when enabled
  const { isConnected } = useWebSocket({
    url: wsUrl || 'ws://disabled',
    onMessage: enabled ? handleMessage : () => {},
    reconnect: enabled,
    reconnectInterval: 1000,
    reconnectAttempts: enabled ? 15 : 0,
  });

  const isJobRunning = useCallback(
    (jobType: string): boolean => {
      for (const job of activeJobs.values()) {
        if (job.job_type === jobType && (job.status === 'pending' || job.status === 'running')) {
          return true;
        }
      }
      return false;
    },
    [activeJobs]
  );

  const activeJobsArray = useMemo(() => Array.from(activeJobs.values()), [activeJobs]);

  const hasActiveJobs = useMemo(
    () => activeJobsArray.some((job) => job.status === 'pending' || job.status === 'running'),
    [activeJobsArray]
  );

  return {
    activeJobs: enabled ? activeJobsArray : [],
    isJobRunning: enabled ? isJobRunning : () => false,
    hasActiveJobs: enabled ? hasActiveJobs : false,
    isConnected: enabled ? isConnected : false,
  };
}

export default useJobWebSocket;

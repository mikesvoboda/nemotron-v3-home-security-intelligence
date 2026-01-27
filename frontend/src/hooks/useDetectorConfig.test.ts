/**
 * Unit tests for useDetectorConfig hook.
 *
 * Tests the detector configuration state management hook including:
 * - Fetching detectors on mount
 * - Switching detectors
 * - Error handling
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useDetectorConfig } from './useDetectorConfig';
import {
  checkDetectorHealth,
  listDetectors,
  switchDetector,
} from '../services/detectorApi';

import type { DetectorInfo, DetectorListResponse } from '../services/detectorApi';

// Mock the detectorApi module
vi.mock('../services/detectorApi', () => ({
  listDetectors: vi.fn(),
  switchDetector: vi.fn(),
  checkDetectorHealth: vi.fn(),
}));

// Mock data
const mockDetectors: DetectorInfo[] = [
  {
    detector_type: 'yolo26',
    display_name: 'YOLO26',
    url: 'http://localhost:8095',
    enabled: true,
    is_active: true,
    model_version: 'yolo26m',
    description: 'YOLO26 TensorRT object detection',
  },
  {
    detector_type: 'yolov8',
    display_name: 'YOLOv8',
    url: 'http://localhost:8096',
    enabled: true,
    is_active: false,
    model_version: 'yolov8n',
    description: 'YOLOv8 nano model',
  },
];

const mockListResponse: DetectorListResponse = {
  detectors: mockDetectors,
  active_detector: 'yolo26',
  health_checked: false,
};

describe('useDetectorConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (listDetectors as ReturnType<typeof vi.fn>).mockResolvedValue(mockListResponse);
  });

  describe('Initial State', () => {
    it('starts with empty detectors array', () => {
      const { result } = renderHook(() =>
        useDetectorConfig({ autoFetch: false })
      );

      expect(result.current.detectors).toEqual([]);
      expect(result.current.activeDetector).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Auto Fetch', () => {
    it('fetches detectors on mount when autoFetch is true', async () => {
      const { result } = renderHook(() =>
        useDetectorConfig({ autoFetch: true })
      );

      await waitFor(() => {
        expect(listDetectors).toHaveBeenCalledTimes(1);
        expect(result.current.detectors.length).toBe(2);
      });

      expect(result.current.activeDetector).toBe('yolo26');
    });

    it('does not fetch on mount when autoFetch is false', () => {
      renderHook(() => useDetectorConfig({ autoFetch: false }));

      expect(listDetectors).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('sets error when fetch fails', async () => {
      (listDetectors as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useDetectorConfig({ autoFetch: true }));

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });

      expect(result.current.detectors).toEqual([]);
    });
  });

  describe('Switch Detector', () => {
    it('calls switchDetector API and updates state', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockResolvedValue({
        detector_type: 'yolov8',
        display_name: 'YOLOv8',
        message: 'Success',
        healthy: true,
      });

      const { result } = renderHook(() => useDetectorConfig({ autoFetch: true }));

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.detectors.length).toBe(2);
      });

      // Switch to YOLOv8
      await act(async () => {
        await result.current.switchTo('yolov8');
      });

      expect(switchDetector).toHaveBeenCalledWith({
        detector_type: 'yolov8',
        force: false,
      });

      expect(result.current.activeDetector).toBe('yolov8');
    });

    it('supports force switch', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockResolvedValue({
        detector_type: 'yolov8',
        display_name: 'YOLOv8',
        message: 'Success',
        healthy: true,
      });

      const { result } = renderHook(() => useDetectorConfig({ autoFetch: true }));

      await waitFor(() => {
        expect(result.current.detectors.length).toBe(2);
      });

      await act(async () => {
        await result.current.switchTo('yolov8', true);
      });

      expect(switchDetector).toHaveBeenCalledWith({
        detector_type: 'yolov8',
        force: true,
      });
    });

    it('sets error when switch fails', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Detector unhealthy')
      );

      const { result } = renderHook(() => useDetectorConfig({ autoFetch: true }));

      await waitFor(() => {
        expect(result.current.detectors.length).toBe(2);
      });

      await act(async () => {
        try {
          await result.current.switchTo('yolov8');
        } catch {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Detector unhealthy');
    });

    it('updates is_active flags in detectors list after switch', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockResolvedValue({
        detector_type: 'yolov8',
        display_name: 'YOLOv8',
        message: 'Success',
        healthy: true,
      });

      const { result } = renderHook(() => useDetectorConfig({ autoFetch: true }));

      await waitFor(() => {
        expect(result.current.detectors.length).toBe(2);
      });

      await act(async () => {
        await result.current.switchTo('yolov8');
      });

      // Check that is_active flags are updated
      const yolo26 = result.current.detectors.find((d) => d.detector_type === 'yolo26');
      const yolov8 = result.current.detectors.find((d) => d.detector_type === 'yolov8');

      expect(yolo26?.is_active).toBe(false);
      expect(yolov8?.is_active).toBe(true);
    });
  });

  describe('Check Health', () => {
    it('calls checkDetectorHealth API', async () => {
      const mockHealth = {
        detector_type: 'yolo26',
        healthy: true,
        model_loaded: true,
        latency_ms: 15,
        error_message: null,
      };
      (checkDetectorHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockHealth);

      const { result } = renderHook(() =>
        useDetectorConfig({ autoFetch: false })
      );

      const health = await result.current.checkHealth('yolo26');

      expect(checkDetectorHealth).toHaveBeenCalledWith('yolo26');
      expect(health).toEqual(mockHealth);
    });
  });

  describe('Refresh', () => {
    it('manually refreshes detector list', async () => {
      const { result } = renderHook(() =>
        useDetectorConfig({ autoFetch: false })
      );

      await act(async () => {
        await result.current.refresh();
      });

      expect(listDetectors).toHaveBeenCalledTimes(1);
      expect(result.current.detectors).toEqual(mockDetectors);
    });
  });
});

/**
 * Unit tests for DetectorSettings component.
 *
 * Tests the detector selection UI including:
 * - Displaying available detectors
 * - Switching between detectors
 * - Error handling
 * - Loading states
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DetectorSettings from './DetectorSettings';
import {
  listDetectors,
  switchDetector,
} from '../../services/detectorApi';

import type { DetectorInfo, DetectorListResponse } from '../../services/detectorApi';

// Mock the detectorApi module
vi.mock('../../services/detectorApi', () => ({
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
  {
    detector_type: 'disabled',
    display_name: 'Disabled Detector',
    url: 'http://localhost:8097',
    enabled: false,
    is_active: false,
    model_version: null,
    description: 'A disabled detector',
  },
];

const mockListResponse: DetectorListResponse = {
  detectors: mockDetectors,
  active_detector: 'yolo26',
  health_checked: false,
};

describe('DetectorSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (listDetectors as ReturnType<typeof vi.fn>).mockResolvedValue(mockListResponse);
  });

  describe('Rendering', () => {
    it('renders the component title', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('Object Detector')).toBeInTheDocument();
      });
    });

    it('displays all detectors from API', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('YOLO26')).toBeInTheDocument();
        expect(screen.getByText('YOLOv8')).toBeInTheDocument();
        expect(screen.getByText('Disabled Detector')).toBeInTheDocument();
      });
    });

    it('shows active badge for current detector', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        // YOLO26 should be marked as active
        const activeBadges = screen.getAllByText('Active');
        expect(activeBadges.length).toBeGreaterThan(0);
      });
    });

    it('shows disabled badge for disabled detectors', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('Disabled')).toBeInTheDocument();
      });
    });

    it('displays detector descriptions', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('YOLO26 TensorRT object detection')).toBeInTheDocument();
        expect(screen.getByText('YOLOv8 nano model')).toBeInTheDocument();
      });
    });

    it('displays model versions when available', async () => {
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('yolo26m')).toBeInTheDocument();
        expect(screen.getByText('yolov8n')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('shows component while loading', () => {
      // Delay the response to test loading state - use a promise that takes time
      const delayedPromise = new Promise<DetectorListResponse>((resolve) => {
        setTimeout(() => {
          resolve(mockListResponse);
        }, 100);
      });
      (listDetectors as ReturnType<typeof vi.fn>).mockReturnValue(
        delayedPromise
      );

      render(<DetectorSettings />);

      // Should show the component title while loading
      expect(screen.getByText('Object Detector')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when API fails', async () => {
      (listDetectors as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  describe('Detector Switching', () => {
    it('calls switchDetector when selecting a different detector', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockResolvedValue({
        detector_type: 'yolov8',
        display_name: 'YOLOv8',
        message: 'Successfully switched',
        healthy: true,
      });

      const user = userEvent.setup();
      render(<DetectorSettings />);

      // Wait for detectors to load
      await waitFor(() => {
        expect(screen.getByText('YOLOv8')).toBeInTheDocument();
      });

      // Find and click the Select button for YOLOv8
      const selectButtons = screen.getAllByRole('button', { name: /select/i });
      // The first "Select" button should be for YOLOv8 (the non-active enabled detector)
      await user.click(selectButtons[0]);

      await waitFor(() => {
        expect(switchDetector).toHaveBeenCalledWith({
          detector_type: 'yolov8',
          force: false,
        });
      });
    });

    it('displays error when switch fails', async () => {
      (switchDetector as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Detector is not healthy')
      );

      const user = userEvent.setup();
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('YOLOv8')).toBeInTheDocument();
      });

      const selectButtons = screen.getAllByRole('button', { name: /select/i });
      await user.click(selectButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Detector is not healthy')).toBeInTheDocument();
      });
    });
  });

  describe('Refresh Functionality', () => {
    it('refreshes detector list when refresh button is clicked', async () => {
      const user = userEvent.setup();
      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('YOLO26')).toBeInTheDocument();
      });

      // Clear the mock to track the refresh call
      vi.clearAllMocks();
      (listDetectors as ReturnType<typeof vi.fn>).mockResolvedValue(mockListResponse);

      // Find the refresh button (it's the one without text, just an icon)
      const buttons = screen.getAllByRole('button');
      const refreshButton = buttons.find(
        (btn) => !btn.textContent || btn.textContent.trim() === ''
      );

      if (refreshButton) {
        await user.click(refreshButton);

        await waitFor(() => {
          expect(listDetectors).toHaveBeenCalled();
        });
      }
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no detectors available', async () => {
      (listDetectors as ReturnType<typeof vi.fn>).mockResolvedValue({
        detectors: [],
        active_detector: null,
        health_checked: false,
      });

      render(<DetectorSettings />);

      await waitFor(() => {
        expect(screen.getByText('No Detectors Available')).toBeInTheDocument();
      });
    });
  });
});

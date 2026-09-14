/**
 * ConnectionStatusCard Test Suite (NEM-4748 Phase 2: Connection Testing)
 *
 * TDD Red Phase: Tests MUST FAIL until ConnectionStatusCard is implemented
 *
 * Tests cover:
 * - Success state with capabilities display
 * - Error state with error message
 * - Loading state with spinner
 * - Latency display formatting
 * - Capability icons (video, audio, ptz)
 * - Resolution/codec/fps display
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import ConnectionStatusCard from './ConnectionStatusCard';

import type { RTSPTestResult } from '../../types/rtsp';

describe('ConnectionStatusCard', () => {
  describe('Success State', () => {
    it('should render success state with all capabilities', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 245,
        capabilities: {
          video: true,
          audio: true,
          ptz: true,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      // Should show success indicator
      expect(screen.getByText(/connection successful/i)).toBeInTheDocument();

      // Should show latency
      expect(screen.getByText(/245.*ms/i)).toBeInTheDocument();

      // Should show capabilities
      expect(screen.getByText(/video/i)).toBeInTheDocument();
      expect(screen.getByText(/audio/i)).toBeInTheDocument();
      expect(screen.getByText(/ptz/i)).toBeInTheDocument();

      // Should show stream details
      expect(screen.getByText(/1920x1080/i)).toBeInTheDocument();
      expect(screen.getByText(/H\.264/i)).toBeInTheDocument();
      expect(screen.getByText(/30.*fps/i)).toBeInTheDocument();
    });

    it('should render success state with partial capabilities', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 150,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1280x720',
          codec: 'H.265',
          fps: 15,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByText(/connection successful/i)).toBeInTheDocument();
      expect(screen.getByText(/150.*ms/i)).toBeInTheDocument();
      expect(screen.getByText(/1280x720/i)).toBeInTheDocument();
    });

    it('should format latency correctly for different ranges', () => {
      const fastResult: RTSPTestResult = {
        success: true,
        latency_ms: 50,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      const { rerender } = render(<ConnectionStatusCard result={fastResult} />);
      expect(screen.getByText(/50.*ms/i)).toBeInTheDocument();

      const slowResult: RTSPTestResult = {
        ...fastResult,
        latency_ms: 1500,
      };

      rerender(<ConnectionStatusCard result={slowResult} />);
      expect(screen.getByText(/1500.*ms/i)).toBeInTheDocument();
    });

    it('should show capability icons with correct states', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: true,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      // Video and audio should have checkmark icon
      const videoIcon = screen.getByTestId('capability-video');
      expect(videoIcon).toHaveClass('text-green-500');

      const audioIcon = screen.getByTestId('capability-audio');
      expect(audioIcon).toHaveClass('text-green-500');

      // PTZ should have X icon
      const ptzIcon = screen.getByTestId('capability-ptz');
      expect(ptzIcon).toHaveClass('text-gray-500');
    });

    it('should handle missing optional fields gracefully', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: null,
          codec: 'H.264',
          fps: null,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByText(/connection successful/i)).toBeInTheDocument();
      expect(screen.queryByText(/x/i)).not.toBeInTheDocument(); // No resolution
      expect(screen.queryByText(/fps/i)).not.toBeInTheDocument(); // No FPS
    });
  });

  describe('Error State', () => {
    it('should render error state with error message', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Connection timeout - stream did not respond within 5 seconds',
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
      expect(screen.getByText(/timeout/i)).toBeInTheDocument();
    });

    it('should show authentication error clearly', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Authentication failed - check username and password',
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
      expect(screen.getByText(/username and password/i)).toBeInTheDocument();
    });

    it('should show URL format error', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Invalid URL format - must use rtsp:// or rtsps://',
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByText(/invalid url/i)).toBeInTheDocument();
      expect(screen.getByText(/rtsp:\/\//i)).toBeInTheDocument();
    });

    it('should show error icon with red styling', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Failed to connect to RTSP stream',
      };

      render(<ConnectionStatusCard result={result} />);

      const errorIcon = screen.getByTestId('error-icon');
      expect(errorIcon).toHaveClass('text-red-500');
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner when result is null', () => {
      render(<ConnectionStatusCard result={null} />);

      expect(screen.getByText(/testing connection/i)).toBeInTheDocument();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should show loading text', () => {
      render(<ConnectionStatusCard result={null} />);

      expect(screen.getByText(/testing connection/i)).toBeInTheDocument();
    });
  });

  describe('Visual Design', () => {
    it('should have proper card styling', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: true,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      const { container } = render(<ConnectionStatusCard result={result} />);

      // Should have card container with border
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('rounded-lg', 'border', 'border-gray-800', 'bg-card');
    });

    it('should have success state with green accent', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      const successIndicator = screen.getByTestId('success-indicator');
      expect(successIndicator).toHaveClass('text-green-500');
    });

    it('should have error state with red accent', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Connection failed',
      };

      render(<ConnectionStatusCard result={result} />);

      const errorContainer = screen.getByTestId('error-container');
      expect(errorContainer).toHaveClass('bg-red-500/10', 'border-red-500/20');
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels for capabilities', () => {
      const result: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: true,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByLabelText('Video supported')).toBeInTheDocument();
      expect(screen.getByLabelText('Audio supported')).toBeInTheDocument();
      expect(screen.getByLabelText('PTZ not supported')).toBeInTheDocument();
    });

    it('should have accessible error message', () => {
      const result: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Connection timeout',
      };

      render(<ConnectionStatusCard result={result} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});

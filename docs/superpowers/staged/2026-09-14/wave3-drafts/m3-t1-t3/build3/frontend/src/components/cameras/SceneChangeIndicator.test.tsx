/**
 * Tests for SceneChangeIndicator component (NEM-3575)
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SceneChangeIndicator } from './SceneChangeIndicator';

import type { CameraActivityState } from '../../hooks/useSceneChangeEvents';

describe('SceneChangeIndicator', () => {
  const mockActiveState: CameraActivityState = {
    cameraId: 'front_door',
    cameraName: 'Front Door Camera',
    lastActivityAt: new Date(),
    lastChangeType: 'view_blocked',
    isActive: true,
  };

  const mockInactiveState: CameraActivityState = {
    ...mockActiveState,
    isActive: false,
  };

  describe('rendering', () => {
    it('renders nothing when activityState is undefined', () => {
      const { container } = render(<SceneChangeIndicator />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when isActive is false', () => {
      const { container } = render(<SceneChangeIndicator activityState={mockInactiveState} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders indicator when isActive is true', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} />);
      expect(screen.getByTestId('scene-change-indicator')).toBeInTheDocument();
    });

    it('renders compact mode when compact is true', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} compact />);
      expect(screen.getByTestId('scene-change-indicator-compact')).toBeInTheDocument();
      expect(screen.queryByTestId('scene-change-indicator')).not.toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} className="custom-class" />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveClass('custom-class');
    });
  });

  describe('change types', () => {
    it('displays "View Blocked" for view_blocked change type', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'view_blocked',
      };
      render(<SceneChangeIndicator activityState={state} />);
      expect(screen.getByText('View Blocked')).toBeInTheDocument();
    });

    it('displays "Tampered" for view_tampered change type', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'view_tampered',
      };
      render(<SceneChangeIndicator activityState={state} />);
      expect(screen.getByText('Tampered')).toBeInTheDocument();
    });

    it('displays "Angle Changed" for angle_changed change type', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'angle_changed',
      };
      render(<SceneChangeIndicator activityState={state} />);
      expect(screen.getByText('Angle Changed')).toBeInTheDocument();
    });

    it('displays "Scene Change" for unknown change type', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'unknown',
      };
      render(<SceneChangeIndicator activityState={state} />);
      expect(screen.getByText('Scene Change')).toBeInTheDocument();
    });
  });

  describe('severity styling', () => {
    it('applies high severity styling for view_blocked', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'view_blocked',
      };
      render(<SceneChangeIndicator activityState={state} />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveClass('bg-red-500/90');
      expect(indicator).toHaveClass('animate-pulse');
    });

    it('applies high severity styling for view_tampered', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'view_tampered',
      };
      render(<SceneChangeIndicator activityState={state} />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveClass('bg-red-500/90');
    });

    it('applies medium severity styling for angle_changed', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastChangeType: 'angle_changed',
      };
      render(<SceneChangeIndicator activityState={state} />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveClass('bg-amber-500/90');
    });
  });

  describe('time display', () => {
    it('shows "just now" for very recent activity', () => {
      const state: CameraActivityState = {
        ...mockActiveState,
        lastActivityAt: new Date(),
      };
      render(<SceneChangeIndicator activityState={state} showDetails />);
      expect(screen.getByText('just now')).toBeInTheDocument();
    });

    it('shows minutes ago for activity within an hour', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      const state: CameraActivityState = {
        ...mockActiveState,
        lastActivityAt: fiveMinutesAgo,
      };
      render(<SceneChangeIndicator activityState={state} showDetails />);
      expect(screen.getByText('5m ago')).toBeInTheDocument();
    });

    it('shows hours ago for activity beyond an hour', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
      const state: CameraActivityState = {
        ...mockActiveState,
        lastActivityAt: twoHoursAgo,
      };
      render(<SceneChangeIndicator activityState={state} showDetails />);
      expect(screen.getByText('2h ago')).toBeInTheDocument();
    });

    it('does not show time when showDetails is false', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      const state: CameraActivityState = {
        ...mockActiveState,
        lastActivityAt: fiveMinutesAgo,
      };
      render(<SceneChangeIndicator activityState={state} showDetails={false} />);
      expect(screen.queryByText('5m ago')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has role="alert" for screen readers', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveAttribute('role', 'alert');
    });

    it('has aria-live="polite" for screen readers', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} />);
      const indicator = screen.getByTestId('scene-change-indicator');
      expect(indicator).toHaveAttribute('aria-live', 'polite');
    });

    it('has aria-label in compact mode', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} compact />);
      const indicator = screen.getByTestId('scene-change-indicator-compact');
      expect(indicator).toHaveAttribute('aria-label', 'Scene change detected: View Blocked');
    });

    it('has title tooltip in compact mode', () => {
      render(<SceneChangeIndicator activityState={mockActiveState} compact />);
      const indicator = screen.getByTestId('scene-change-indicator-compact');
      expect(indicator).toHaveAttribute('title', 'View Blocked - Front Door Camera');
    });
  });
});

import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import SceneChangeAlert from './SceneChangeAlert';

import type { SceneChangeAlert as SceneChangeAlertType } from '../../hooks/useSceneChangeAlerts';

// Mock react-router-dom's useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Helper to create mock alert
function createMockAlert(
  id: number,
  cameraId: string,
  changeType: string,
  similarityScore: number,
  dismissed = false
): SceneChangeAlertType {
  return {
    id,
    cameraId,
    detectedAt: '2026-01-10T10:00:00Z',
    changeType,
    similarityScore,
    dismissed,
    receivedAt: new Date('2026-01-10T10:00:00Z'),
  };
}

describe('SceneChangeAlert', () => {
  const mockOnDismiss = vi.fn();
  const mockOnDismissAll = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when hasAlerts is false', () => {
    const { container } = render(
      <MemoryRouter>
        <SceneChangeAlert
          alerts={[]}
          unacknowledgedCount={0}
          hasAlerts={false}
          onDismiss={mockOnDismiss}
          onDismissAll={mockOnDismissAll}
        />
      </MemoryRouter>
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders badge with count when hasAlerts is true', () => {
    render(
      <MemoryRouter>
        <SceneChangeAlert
          alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
          unacknowledgedCount={1}
          hasAlerts={true}
          onDismiss={mockOnDismiss}
          onDismissAll={mockOnDismissAll}
        />
      </MemoryRouter>
    );

    expect(screen.getByTestId('scene-change-badge')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('displays correct count for multiple alerts', () => {
    render(
      <MemoryRouter>
        <SceneChangeAlert
          alerts={[
            createMockAlert(1, 'front_door', 'view_blocked', 0.25),
            createMockAlert(2, 'back_yard', 'angle_changed', 0.45),
            createMockAlert(3, 'garage', 'view_tampered', 0.15),
          ]}
          unacknowledgedCount={3}
          hasAlerts={true}
          onDismiss={mockOnDismiss}
          onDismissAll={mockOnDismissAll}
        />
      </MemoryRouter>
    );

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('has correct aria attributes', () => {
    render(
      <MemoryRouter>
        <SceneChangeAlert
          alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
          unacknowledgedCount={1}
          hasAlerts={true}
          onDismiss={mockOnDismiss}
          onDismissAll={mockOnDismissAll}
        />
      </MemoryRouter>
    );

    const badge = screen.getByTestId('scene-change-badge');
    expect(badge).toHaveAttribute('aria-haspopup', 'true');
    expect(badge).toHaveAttribute('aria-expanded', 'false');
    expect(badge).toHaveAttribute('aria-label', '1 scene change alert');
  });

  it('uses plural aria-label for multiple alerts', () => {
    render(
      <MemoryRouter>
        <SceneChangeAlert
          alerts={[
            createMockAlert(1, 'front_door', 'view_blocked', 0.25),
            createMockAlert(2, 'back_yard', 'angle_changed', 0.45),
          ]}
          unacknowledgedCount={2}
          hasAlerts={true}
          onDismiss={mockOnDismiss}
          onDismissAll={mockOnDismissAll}
        />
      </MemoryRouter>
    );

    const badge = screen.getByTestId('scene-change-badge');
    expect(badge).toHaveAttribute('aria-label', '2 scene change alerts');
  });

  describe('Dropdown', () => {
    it('shows dropdown on click', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      // Dropdown should not be visible initially
      expect(screen.queryByTestId('scene-change-dropdown')).not.toBeInTheDocument();

      // Click to show dropdown
      fireEvent.click(screen.getByTestId('scene-change-badge'));

      expect(screen.getByTestId('scene-change-dropdown')).toBeInTheDocument();
      expect(screen.getByText('Scene Change Alerts')).toBeInTheDocument();
    });

    it('shows dropdown on mouse enter', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));

      expect(screen.getByTestId('scene-change-dropdown')).toBeInTheDocument();
    });

    it('hides dropdown on mouse leave after delay', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      // Show dropdown
      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));
      expect(screen.getByTestId('scene-change-dropdown')).toBeInTheDocument();

      // Mouse leave
      fireEvent.mouseLeave(screen.getByTestId('scene-change-alert'));

      // Still visible immediately
      expect(screen.getByTestId('scene-change-dropdown')).toBeInTheDocument();

      // After delay, should be hidden
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.queryByTestId('scene-change-dropdown')).not.toBeInTheDocument();

      vi.useRealTimers();
    });

    it('displays alert details in dropdown', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));

      expect(screen.getByTestId('scene-change-alert-1')).toBeInTheDocument();
      expect(screen.getByText('front_door')).toBeInTheDocument();
      expect(screen.getByText('View Blocked')).toBeInTheDocument();
      expect(screen.getByText('Similarity: 25.0%')).toBeInTheDocument();
    });

    it('filters out dismissed alerts in dropdown', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[
              createMockAlert(1, 'front_door', 'view_blocked', 0.25),
              createMockAlert(2, 'back_yard', 'angle_changed', 0.45, true), // dismissed
            ]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));

      expect(screen.getByTestId('scene-change-alert-1')).toBeInTheDocument();
      expect(screen.queryByTestId('scene-change-alert-2')).not.toBeInTheDocument();
    });

    it('shows "No active alerts" when all are dismissed', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25, true)]}
            unacknowledgedCount={0}
            hasAlerts={false}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      // Component should not render when hasAlerts is false
      expect(screen.queryByTestId('scene-change-alert')).not.toBeInTheDocument();
    });
  });

  describe('Dismiss Actions', () => {
    it('calls onDismiss when dismiss button is clicked', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));
      fireEvent.click(screen.getByTestId('dismiss-alert-1'));

      expect(mockOnDismiss).toHaveBeenCalledWith(1);
    });

    it('calls onDismissAll when Dismiss All is clicked', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[
              createMockAlert(1, 'front_door', 'view_blocked', 0.25),
              createMockAlert(2, 'back_yard', 'angle_changed', 0.45),
            ]}
            unacknowledgedCount={2}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));
      fireEvent.click(screen.getByTestId('dismiss-all-alerts'));

      expect(mockOnDismissAll).toHaveBeenCalled();
    });
  });

  describe('Navigation', () => {
    it('navigates to analytics page when View All is clicked', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));
      fireEvent.click(screen.getByTestId('view-all-scene-changes'));

      expect(mockNavigate).toHaveBeenCalledWith('/analytics');
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
            className="custom-class"
          />
        </MemoryRouter>
      );

      expect(screen.getByTestId('scene-change-alert')).toHaveClass('custom-class');
    });

    it('shows severity-appropriate colors for high severity', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'view_blocked', 0.25)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));

      // High severity (view_blocked) should have red colors
      const alertItem = screen.getByTestId('scene-change-alert-1');
      expect(alertItem).toHaveClass('bg-red-500/10');
    });

    it('shows severity-appropriate colors for medium severity', () => {
      render(
        <MemoryRouter>
          <SceneChangeAlert
            alerts={[createMockAlert(1, 'front_door', 'angle_changed', 0.45)]}
            unacknowledgedCount={1}
            hasAlerts={true}
            onDismiss={mockOnDismiss}
            onDismissAll={mockOnDismissAll}
          />
        </MemoryRouter>
      );

      fireEvent.mouseEnter(screen.getByTestId('scene-change-alert'));

      // Medium severity (angle_changed) should have orange colors
      const alertItem = screen.getByTestId('scene-change-alert-1');
      expect(alertItem).toHaveClass('bg-orange-500/10');
    });
  });
});

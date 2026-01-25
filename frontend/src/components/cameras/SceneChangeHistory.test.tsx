/**
 * Tests for SceneChangeHistory component (NEM-3575)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SceneChangeHistory } from './SceneChangeHistory';

import type { SceneChangeEventData } from '../../hooks/useSceneChangeEvents';

describe('SceneChangeHistory', () => {
  const mockEvents: SceneChangeEventData[] = [
    {
      id: 1,
      cameraId: 'front_door',
      cameraName: 'Front Door Camera',
      detectedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
      changeType: 'view_blocked',
      similarityScore: 0.25,
      receivedAt: new Date(Date.now() - 5 * 60 * 1000),
    },
    {
      id: 2,
      cameraId: 'back_yard',
      cameraName: 'Back Yard Camera',
      detectedAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
      changeType: 'angle_changed',
      similarityScore: 0.45,
      receivedAt: new Date(Date.now() - 30 * 60 * 1000),
    },
    {
      id: 3,
      cameraId: 'garage',
      cameraName: 'Garage Camera',
      detectedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      changeType: 'view_tampered',
      similarityScore: 0.15,
      receivedAt: new Date(Date.now() - 2 * 60 * 60 * 1000),
    },
  ];

  describe('rendering', () => {
    it('renders empty state when no events', () => {
      render(<SceneChangeHistory events={[]} />);
      expect(screen.getByTestId('scene-change-history-empty')).toBeInTheDocument();
      expect(screen.getByText('No recent scene changes')).toBeInTheDocument();
    });

    it('renders custom empty message', () => {
      render(<SceneChangeHistory events={[]} emptyMessage="All clear!" />);
      expect(screen.getByText('All clear!')).toBeInTheDocument();
    });

    it('does not show empty state when showEmptyState is false', () => {
      const { container } = render(<SceneChangeHistory events={[]} showEmptyState={false} />);
      expect(container.querySelector('[data-testid="scene-change-history-empty"]')).toBeNull();
    });

    it('renders event list when events exist', () => {
      render(<SceneChangeHistory events={mockEvents} />);
      expect(screen.getByTestId('scene-change-history')).toBeInTheDocument();
    });

    it('renders all events within maxItems limit', () => {
      render(<SceneChangeHistory events={mockEvents} maxItems={10} />);
      expect(screen.getByTestId('scene-change-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('scene-change-item-2')).toBeInTheDocument();
      expect(screen.getByTestId('scene-change-item-3')).toBeInTheDocument();
    });

    it('limits displayed events to maxItems', () => {
      render(<SceneChangeHistory events={mockEvents} maxItems={2} />);
      expect(screen.getByTestId('scene-change-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('scene-change-item-2')).toBeInTheDocument();
      expect(screen.queryByTestId('scene-change-item-3')).not.toBeInTheDocument();
    });

    it('shows more events indicator when events exceed maxItems', () => {
      render(<SceneChangeHistory events={mockEvents} maxItems={1} />);
      expect(screen.getByText('2 more scene changes')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<SceneChangeHistory events={mockEvents} className="custom-class" />);
      const list = screen.getByTestId('scene-change-history');
      expect(list).toHaveClass('custom-class');
    });
  });

  describe('event display', () => {
    it('displays camera name', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      expect(screen.getByText('Front Door Camera')).toBeInTheDocument();
    });

    it('displays change type badge for view_blocked', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      expect(screen.getByText('View Blocked')).toBeInTheDocument();
    });

    it('displays change type badge for angle_changed', () => {
      render(<SceneChangeHistory events={[mockEvents[1]]} />);
      expect(screen.getByText('Angle Changed')).toBeInTheDocument();
    });

    it('displays change type badge for view_tampered', () => {
      render(<SceneChangeHistory events={[mockEvents[2]]} />);
      expect(screen.getByText('Tampered')).toBeInTheDocument();
    });

    it('displays similarity score as percentage', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    it('displays relative time for recent events', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      expect(screen.getByText('5m ago')).toBeInTheDocument();
    });

    it('displays hours for older events', () => {
      render(<SceneChangeHistory events={[mockEvents[2]]} />);
      expect(screen.getByText('2h ago')).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onEventClick when event is clicked', () => {
      const onEventClick = vi.fn();
      render(<SceneChangeHistory events={[mockEvents[0]]} onEventClick={onEventClick} />);

      fireEvent.click(screen.getByTestId('scene-change-item-1'));
      expect(onEventClick).toHaveBeenCalledWith(mockEvents[0]);
    });

    it('calls onEventClick when Enter key is pressed', () => {
      const onEventClick = vi.fn();
      render(<SceneChangeHistory events={[mockEvents[0]]} onEventClick={onEventClick} />);

      const item = screen.getByTestId('scene-change-item-1');
      fireEvent.keyDown(item, { key: 'Enter' });
      expect(onEventClick).toHaveBeenCalledWith(mockEvents[0]);
    });

    it('calls onDismiss when dismiss button is clicked', () => {
      const onDismiss = vi.fn();
      render(<SceneChangeHistory events={[mockEvents[0]]} onDismiss={onDismiss} />);

      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      fireEvent.click(dismissButton);
      expect(onDismiss).toHaveBeenCalledWith(1);
    });

    it('does not call onEventClick when dismiss button is clicked', () => {
      const onEventClick = vi.fn();
      const onDismiss = vi.fn();
      render(
        <SceneChangeHistory events={[mockEvents[0]]} onEventClick={onEventClick} onDismiss={onDismiss} />
      );

      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      fireEvent.click(dismissButton);
      expect(onEventClick).not.toHaveBeenCalled();
      expect(onDismiss).toHaveBeenCalled();
    });

    it('does not show dismiss button when onDismiss is not provided', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
    });

    it('event item is not clickable when onEventClick is not provided', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      const item = screen.getByTestId('scene-change-item-1');
      expect(item).not.toHaveAttribute('role', 'button');
    });
  });

  describe('accessibility', () => {
    it('has role="list" on container', () => {
      render(<SceneChangeHistory events={mockEvents} />);
      const list = screen.getByTestId('scene-change-history');
      expect(list).toHaveAttribute('role', 'list');
    });

    it('has aria-label on container', () => {
      render(<SceneChangeHistory events={mockEvents} />);
      const list = screen.getByTestId('scene-change-history');
      expect(list).toHaveAttribute('aria-label', 'Recent scene changes');
    });

    it('event items have tabIndex when clickable', () => {
      const onEventClick = vi.fn();
      render(<SceneChangeHistory events={[mockEvents[0]]} onEventClick={onEventClick} />);
      const item = screen.getByTestId('scene-change-item-1');
      expect(item).toHaveAttribute('tabIndex', '0');
    });

    it('event items do not have tabIndex when not clickable', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      const item = screen.getByTestId('scene-change-item-1');
      expect(item).not.toHaveAttribute('tabIndex');
    });

    it('dismiss button has aria-label', () => {
      const onDismiss = vi.fn();
      render(<SceneChangeHistory events={[mockEvents[0]]} onDismiss={onDismiss} />);
      const dismissButton = screen.getByRole('button', { name: /dismiss/i });
      expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss scene change alert');
    });
  });

  describe('styling', () => {
    it('applies correct styling for view_blocked', () => {
      render(<SceneChangeHistory events={[mockEvents[0]]} />);
      const badge = screen.getByText('View Blocked').closest('span');
      expect(badge).toHaveClass('bg-red-500/10');
      expect(badge).toHaveClass('text-red-400');
    });

    it('applies correct styling for angle_changed', () => {
      render(<SceneChangeHistory events={[mockEvents[1]]} />);
      const badge = screen.getByText('Angle Changed').closest('span');
      expect(badge).toHaveClass('bg-amber-500/10');
      expect(badge).toHaveClass('text-amber-400');
    });
  });
});

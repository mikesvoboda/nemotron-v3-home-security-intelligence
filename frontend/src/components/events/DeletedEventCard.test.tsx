/**
 * Tests for DeletedEventCard component
 *
 * Following TDD approach: RED -> GREEN -> REFACTOR
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import DeletedEventCard from './DeletedEventCard';

import type { DeletedEvent } from '../../services/api';

// Factory for creating mock deleted events
function createMockDeletedEvent(overrides: Partial<DeletedEvent> = {}): DeletedEvent {
  return {
    id: 1,
    camera_id: 'front_door',
    started_at: '2025-01-01T10:00:00Z',
    ended_at: '2025-01-01T10:05:00Z',
    risk_score: 45,
    risk_level: 'medium',
    summary: 'Person detected at front door',
    reasoning: 'A person was observed approaching the front door',
    thumbnail_url: '/api/media/events/1/thumbnail.jpg',
    reviewed: false,
    flagged: false, // NEM-3839
    detection_count: 3,
    deleted_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  };
}

describe('DeletedEventCard', () => {
  const mockOnRestore = vi.fn();
  const mockOnPermanentDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders event information', () => {
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    // Camera name
    expect(screen.getByText('front_door')).toBeInTheDocument();
    // Summary
    expect(screen.getByText('Person detected at front door')).toBeInTheDocument();
    // Risk badge should be present - displays as "Medium (45)"
    expect(screen.getByText(/Medium \(45\)/i)).toBeInTheDocument();
  });

  // M1 review F-E follow-through: a NULL risk_score under D11 means
  // verification_failed / never-verified, NOT a score of 0. This card used to
  // do `event.risk_score ?? 0` and then getRiskLevel(0), so a trash-listed
  // event the VLM never scored rendered as a confident green "Low 0" — the
  // exact lie 1.6 removed from EventCard/MobileEventCard, left standing on
  // the one surface fed by GET /api/events/deleted.
  describe('a NULL risk_score states "not verified" instead of "Low 0" (D11)', () => {
    it('renders the Unverified badge, never a level badge', () => {
      const event = createMockDeletedEvent({ risk_score: null, risk_level: null });

      render(
        <DeletedEventCard
          event={event}
          onRestore={mockOnRestore}
          onPermanentDelete={mockOnPermanentDelete}
        />
      );

      expect(screen.getByText(/Unverified/i)).toBeInTheDocument();
      expect(screen.queryByText(/Low/i)).not.toBeInTheDocument();
      // And the fabricated number itself is gone, not merely re-colored.
      expect(screen.queryByText(/\(0\)/)).not.toBeInTheDocument();
    });

    it('names verification_failed when the event carries that verdict', () => {
      const event = createMockDeletedEvent({
        risk_score: null,
        risk_level: null,
        verification: {
          engine: 'llama.cpp',
          model_id: 'qwen3vl-4b',
          verdict: 'verification_failed',
        },
      });

      render(
        <DeletedEventCard
          event={event}
          onRestore={mockOnRestore}
          onPermanentDelete={mockOnPermanentDelete}
        />
      );

      expect(screen.getByText(/Verification failed/i)).toBeInTheDocument();
      expect(screen.queryByText(/Low/i)).not.toBeInTheDocument();
    });

    it('draws no risk progress bar when there is no score', () => {
      // A 0%-filled bar under an "Unverified" badge re-lies in a second
      // medium: the trough itself reads as "measured, and low".
      const event = createMockDeletedEvent({ risk_score: null, risk_level: null });

      render(
        <DeletedEventCard
          event={event}
          onRestore={mockOnRestore}
          onPermanentDelete={mockOnPermanentDelete}
        />
      );

      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    it('still draws the bar and the badge when a score exists', () => {
      const event = createMockDeletedEvent({ risk_score: 75, risk_level: 'high' });

      render(
        <DeletedEventCard
          event={event}
          onRestore={mockOnRestore}
          onPermanentDelete={mockOnPermanentDelete}
        />
      );

      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '75');
      expect(screen.getByText(/High \(75\)/i)).toBeInTheDocument();
    });
  });

  it('displays time since deletion', () => {
    const event = createMockDeletedEvent({
      deleted_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
    });

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    expect(screen.getByText(/Deleted 2 days ago/i)).toBeInTheDocument();
  });

  it('has reduced opacity styling', () => {
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    const card = screen.getByTestId('deleted-event-card-1');
    expect(card).toHaveClass('opacity-70');
  });

  it('calls onRestore when restore button is clicked', async () => {
    const user = userEvent.setup();
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    const restoreButton = screen.getByRole('button', { name: /restore/i });
    await user.click(restoreButton);

    expect(mockOnRestore).toHaveBeenCalledWith(1);
  });

  it('shows confirmation dialog when delete forever is clicked', async () => {
    const user = userEvent.setup();
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    // Click delete forever button
    const deleteButton = screen.getByRole('button', { name: /delete forever/i });
    await user.click(deleteButton);

    // Confirmation dialog should appear
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/permanent delete/i)).toBeInTheDocument();
    expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();
  });

  it('calls onPermanentDelete when delete is confirmed', async () => {
    const user = userEvent.setup();
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    // Open confirmation dialog
    const deleteButton = screen.getByRole('button', { name: /delete forever/i });
    await user.click(deleteButton);

    // Confirm deletion - find the button inside the dialog by looking within dialog
    const dialog = screen.getByRole('dialog');
    const confirmButton = dialog.querySelector('button.btn-danger');
    expect(confirmButton).not.toBeNull();
    await user.click(confirmButton!);

    expect(mockOnPermanentDelete).toHaveBeenCalledWith(1);
  });

  it('closes confirmation dialog when cancel is clicked', async () => {
    const user = userEvent.setup();
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    // Open confirmation dialog
    const deleteButton = screen.getByRole('button', { name: /delete forever/i });
    await user.click(deleteButton);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Dialog should be closed
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows loading state when restoring', () => {
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
        isRestoring={true}
      />
    );

    const restoreButton = screen.getByRole('button', { name: /restore/i });
    expect(restoreButton).toHaveAttribute('aria-busy', 'true');
  });

  it('disables buttons when deleting', () => {
    const event = createMockDeletedEvent();

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
        isDeleting={true}
      />
    );

    const restoreButton = screen.getByRole('button', { name: /restore/i });
    const deleteButton = screen.getByRole('button', { name: /delete forever/i });

    expect(restoreButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
  });

  it('displays thumbnail when available', () => {
    const event = createMockDeletedEvent({
      thumbnail_url: '/api/media/events/1/thumbnail.jpg',
    });

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    const thumbnail = screen.getByRole('img');
    expect(thumbnail).toHaveAttribute('src', '/api/media/events/1/thumbnail.jpg');
    expect(thumbnail).toHaveClass('grayscale');
  });

  it('displays placeholder when no thumbnail', () => {
    const event = createMockDeletedEvent({
      thumbnail_url: undefined,
    });

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    // Should not have an img element
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('formats deletion time correctly for recent deletions', () => {
    const event = createMockDeletedEvent({
      deleted_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
    });

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    expect(screen.getByText(/Deleted 5 minutes ago/i)).toBeInTheDocument();
  });

  it('formats deletion time correctly for hours ago', () => {
    const event = createMockDeletedEvent({
      deleted_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
    });

    render(
      <DeletedEventCard
        event={event}
        onRestore={mockOnRestore}
        onPermanentDelete={mockOnPermanentDelete}
      />
    );

    expect(screen.getByText(/Deleted 3 hours ago/i)).toBeInTheDocument();
  });
});

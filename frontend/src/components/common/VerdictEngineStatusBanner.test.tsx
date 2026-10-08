/**
 * VerdictEngineStatusBanner tests (F1.2, UR-18).
 *
 * Failing-test-first for 20-frontend.md F1.2: "when engine state is
 * `unavailable`, a persistent banner reads that the verdict engine is
 * unavailable since a time and that new events need review; it clears when
 * the state returns to `available`."
 *
 * Presentational component: state arrives via props (Layout owns the data),
 * mirroring ConnectionStatusBanner. Announce is mocked at the hook seam to
 * pin transition-only screen-reader announcements.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import VerdictEngineStatusBanner from './VerdictEngineStatusBanner';

const announce = vi.fn();
vi.mock('../../hooks/useAnnounce', () => ({
  useAnnounce: () => ({ announce }),
}));

const UNAVAILABLE = {
  state: 'unavailable' as const,
  since: '2026-10-08T10:00:00Z',
  reason: 'ConnectError: connection refused',
};

describe('VerdictEngineStatusBanner', () => {
  beforeEach(() => {
    announce.mockClear();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-08T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('available -> banner clears', () => {
    it('renders nothing when the engine is available', () => {
      const { container } = render(
        <VerdictEngineStatusBanner state="available" since={null} reason={null} />
      );
      expect(container).toBeEmptyDOMElement();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('clears when the state returns to available', () => {
      const { rerender, container } = render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      rerender(<VerdictEngineStatusBanner state="available" since={null} reason={null} />);
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe('unavailable -> persistent alarm banner', () => {
    it('reads that the verdict engine is unavailable and new events need review', () => {
      render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveAttribute('aria-live', 'assertive');
      expect(alert).toHaveTextContent(/verdict engine/i);
      expect(alert).toHaveTextContent(/unavailable/i);
      expect(alert).toHaveTextContent(/need.{0,20}review/i);
      expect(screen.getByTestId('verdict-engine-banner')).toBeInTheDocument();
    });

    it('shows since a time — the transition time, formatted as elapsed downtime', () => {
      render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      // now pinned to 12:00:00Z, since 10:00:00Z -> 2h of downtime
      expect(screen.getByTestId('verdict-engine-since')).toHaveTextContent(/2h/);
    });

    it('surfaces the engine reason while unavailable', () => {
      render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      expect(screen.getByTestId('verdict-engine-reason')).toHaveTextContent(
        'ConnectError: connection refused'
      );
    });

    it('omits the reason line when the payload carries none', () => {
      render(
        <VerdictEngineStatusBanner state="unavailable" since={UNAVAILABLE.since} reason={null} />
      );
      expect(screen.queryByTestId('verdict-engine-reason')).not.toBeInTheDocument();
    });

    it('is dismissible and re-arms on the next transition', () => {
      const { rerender } = render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      fireEvent.click(screen.getByLabelText(/dismiss/i));
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();

      // Still unavailable (no state change) -> stays dismissed.
      rerender(<VerdictEngineStatusBanner {...UNAVAILABLE} reason="still down" />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();

      // Recover then fail again -> the new transition re-arms the banner.
      rerender(<VerdictEngineStatusBanner state="available" since={null} reason={null} />);
      rerender(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('unknown -> warning, not the alarm', () => {
    it('renders a polite status (not role=alert) so unknown never cries fire', () => {
      render(
        <VerdictEngineStatusBanner
          state="unknown"
          since="2026-10-08T11:30:00Z"
          reason="probe timeout: no response in 5s"
        />
      );
      const status = screen.getByRole('status');
      expect(status).toHaveAttribute('aria-live', 'polite');
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(status).toHaveTextContent(/verdict engine/i);
      expect(status).toHaveTextContent(/unknown/i);
      expect(screen.getByTestId('verdict-engine-reason')).toHaveTextContent('probe timeout');
    });
  });

  describe('screen-reader announcements', () => {
    it('does not announce on first render', () => {
      render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      expect(announce).not.toHaveBeenCalled();
    });

    it('announces on transition into unavailable', () => {
      const { rerender } = render(
        <VerdictEngineStatusBanner state="available" since={null} reason={null} />
      );
      rerender(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      expect(announce).toHaveBeenCalledTimes(1);
      expect(announce.mock.calls[0][0]).toMatch(/verdict engine/i);
      expect(announce.mock.calls[0][1]).toBe('assertive');
    });

    it('announces recovery', () => {
      const { rerender } = render(<VerdictEngineStatusBanner {...UNAVAILABLE} />);
      rerender(<VerdictEngineStatusBanner state="available" since={null} reason={null} />);
      expect(announce).toHaveBeenCalledWith(expect.stringMatching(/available again/i), 'polite');
    });
  });
});

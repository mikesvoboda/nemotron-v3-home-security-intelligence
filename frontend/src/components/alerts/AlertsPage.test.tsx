/**
 * Unit tier for the F4.1 Alerts page (the alert-ROW page over
 * GET /api/alert-service/alerts).
 *
 * Scope of this tier, stated honestly: jsdom runs the page's RENDER logic
 * against mocked services — what it can prove is which hook each surface reads
 * and what the page does with the data (the sort, the pluralisation, the
 * empty-state branch, the action wiring). What it cannot prove is the wire
 * behaviour of those services or the WebSocket live-refresh path; the golden
 * spec (tests/golden/analytics-alerts/alerts.spec.ts) drives the shipped page
 * against the real backend for that.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertsPage from './AlertsPage';
import * as alertsApi from '../../services/alertsApi';
import * as api from '../../services/api';

import type { AlertServiceResponse } from '../../services/alertsApi';
import type { Camera } from '../../services/api';

// The page's own action imports (acknowledgeAlert / dismissAlert /
// isConflictError) live on this module, so the mock intercepts the actions;
// isConflictError is NOT mocked away — the real classifier decides what the
// conflict banner leg proves, so an AlertsApiError-shaped rejection is what
// that test throws.
vi.mock('../../services/alertsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/alertsApi')>();
  return {
    ...actual,
    fetchAlerts: vi.fn(),
    acknowledgeAlert: vi.fn(),
    dismissAlert: vi.fn(),
  };
});
// The events service is only read for fetchCameras (the camera-name lookup).
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return { ...actual, fetchCameras: vi.fn() };
});
// The snooze ride-through goes to the wire (PATCH /api/events/{id}); jsdom
// must not fire it — the hook is mocked at the barrel, the page's own import
// surface.
vi.mock('../../hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks')>();
  return {
    ...actual,
    useSnoozeEvent: () => ({ snooze: vi.fn(), isSnoozing: false }),
  };
});

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    );
  };
}

function renderPage(ui: React.ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}

/** Row builder with sensible defaults; each test varies what it reads. */
function alertRow(over: Partial<AlertServiceResponse>): AlertServiceResponse {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    event_id: 101,
    rule_id: null,
    severity: 'high',
    status: 'open',
    dedup_key: 'camera-1:default',
    channels: [],
    metadata: { rule_name: 'default', recognised: ['a cat'] },
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:00:00Z',
    verdict_source: 'local',
    match_count: 1,
    last_seen_at: null,
    last_event_id: null,
    camera_id: 'camera-1',
    ...over,
  };
}

const cameras: Camera[] = [
  {
    id: 'camera-1',
    name: 'Front Door',
    folder_path: '/path/to/front',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  },
  {
    id: 'camera-2',
    name: 'Back Yard',
    folder_path: '/path/to/back',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: '2024-01-01T12:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  },
];

function listResponse(rows: AlertServiceResponse[]) {
  return {
    items: rows,
    pagination: { total: rows.length, limit: 50, offset: 0, has_more: false },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.fetchCameras).mockResolvedValue(cameras);
  vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([]));
});

describe('AlertsPage (F4.1: alert rows)', () => {
  describe('Rendering', () => {
    it('renders the header and the page root', () => {
      renderPage(<AlertsPage />);
      expect(screen.getByTestId('alerts-page')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Alerts' })).toBeInTheDocument();
      expect(screen.getByText('What the household was alerted about')).toBeInTheDocument();
    });

    it('shows the loading state while the list is in flight', () => {
      vi.mocked(alertsApi.fetchAlerts).mockImplementation(() => new Promise(() => {}));
      renderPage(<AlertsPage />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('renders an alert row with rule, severity badge, camera and matches', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([
          alertRow({ metadata: { rule_name: 'person at door', recognised: ['a person'] } }),
        ])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByTestId('alerts-rows')).toBeInTheDocument();
      });
      expect(screen.getByTestId('alert-row')).toBeInTheDocument();
      expect(screen.getByText('person at door')).toBeInTheDocument();
      expect(screen.getByTestId('alert-severity-high')).toBeInTheDocument();
      // The page renders `Camera: <span>{name}</span>` — label and value are
      // separate DOM nodes, so query the leaf value, not the combined string.
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('a person')).toBeInTheDocument();
      expect(screen.getByText('verified locally')).toBeInTheDocument();
    });

    it('renders the derived camera_id through the camera-name lookup', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([alertRow({ camera_id: 'camera-2' })])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('Back Yard')).toBeInTheDocument();
      });
    });

    it('joins the recognised LIST the pipeline writes (pipeline.py writes a list, not a string)', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([
          alertRow({ metadata: { rule_name: 'default', recognised: ['a cat', 'a person'] } }),
        ])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('a cat, a person')).toBeInTheDocument();
      });
    });

    it('falls back to Unmatched alert when metadata carries no rule_name', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([alertRow({ metadata: null })])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('Unmatched alert')).toBeInTheDocument();
      });
    });

    it('renders the verdict badge from verdict_source (local / cloud / other)', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([
          alertRow({ id: 'a', verdict_source: 'local' }),
          alertRow({ id: 'b', verdict_source: 'cloud' }),
          alertRow({ id: 'c', verdict_source: null }),
        ])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('verified locally')).toBeInTheDocument();
        expect(screen.getByText('verified in the cloud')).toBeInTheDocument();
        expect(screen.getByText('unverified')).toBeInTheDocument();
      });
    });

    it('renders who was told: channels joined, or nobody yet when empty', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([
          alertRow({ id: 'a', channels: ['pushover'] }),
          alertRow({ id: 'b', channels: [] }),
        ])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('pushover')).toBeInTheDocument();
        expect(screen.getByText('nobody yet')).toBeInTheDocument();
      });
    });
  });

  describe('Count line', () => {
    it('pluralises from totalCount', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([alertRow({ id: 'a' }), alertRow({ id: 'b' })])
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });
    });

    it('uses the singular line for exactly one alert', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'a' })]));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('1 alert found')).toBeInTheDocument();
      });
    });
  });

  describe('Empty states', () => {
    it('shows the open-filter empty state by default', async () => {
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(
          screen.getByText('There are no open alerts. Keep up the good work!')
        ).toBeInTheDocument();
      });
    });

    it('shows the all-filter empty state under the all toggle', async () => {
      renderPage(<AlertsPage />);
      await userEvent.selectOptions(screen.getByLabelText('Show:'), 'all');
      await waitFor(() => {
        expect(screen.getByText('There are no alerts to show.')).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('renders the status filter with open/all options, open by default', () => {
      renderPage(<AlertsPage />);
      const select = screen.getByLabelText('Show:');
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue('open');
      const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
      expect(options).toEqual(['open', 'all']);
    });

    it('refetches without a status param when the toggle flips to all', async () => {
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(alertsApi.fetchAlerts).toHaveBeenCalledWith({ status: 'open', limit: 50 });
      });
      await userEvent.selectOptions(screen.getByLabelText('Show:'), 'all');
      await waitFor(() => {
        expect(alertsApi.fetchAlerts).toHaveBeenCalledWith({ status: undefined, limit: 50 });
      });
    });
  });

  describe('Actions', () => {
    it('Acknowledge calls the alerts service, then refetches', async () => {
      vi.mocked(alertsApi.fetchAlerts)
        .mockResolvedValueOnce(listResponse([alertRow({ id: 'a' })]))
        .mockResolvedValue(listResponse([]));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /acknowledge/i })).toBeEnabled();
      });
      await userEvent.click(screen.getByRole('button', { name: /acknowledge/i }));
      expect(vi.mocked(alertsApi.acknowledgeAlert)).toHaveBeenCalledWith('a');
      await waitFor(() => {
        expect(vi.mocked(alertsApi.fetchAlerts).mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('Dismiss calls the alerts service', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'b' })]));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^dismiss$/i })).toBeEnabled();
      });
      await userEvent.click(screen.getByRole('button', { name: /^dismiss$/i }));
      expect(vi.mocked(alertsApi.dismissAlert)).toHaveBeenCalledWith('b');
    });

    it('the snooze select carries the alert id and offers the shipped durations', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'a' })]));
      renderPage(<AlertsPage />);
      const select = await screen.findByLabelText('Snooze alert a');
      const values = Array.from(select.querySelectorAll('option')).map((o) => o.value);
      expect(values).toEqual(['', '900', '3600', '14400', '86400']);
      // Selecting a duration rides useSnoozeEvent (mocked at the barrel) —
      // the assertion is that the control resolves the seconds>0 branch,
      // with no wire call escaping jsdom.
      await userEvent.selectOptions(select, '900');
    });

    it('Open event renders DISABLED on the standalone route (no onViewEventDetails prop)', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'a' })]));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open event/i })).toBeDisabled();
      });
    });

    it('Open event fires the host callback when the prop is passed', async () => {
      const onViewEventDetails = vi.fn();
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(
        listResponse([alertRow({ id: 'a', event_id: 7 })])
      );
      renderPage(<AlertsPage onViewEventDetails={onViewEventDetails} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open event/i })).toBeEnabled();
      });
      await userEvent.click(screen.getByRole('button', { name: /open event/i }));
      expect(onViewEventDetails).toHaveBeenCalledWith(7);
    });

    it('shows the conflict banner when the action 409s (the real isConflictError classifies)', async () => {
      const { AlertsApiError } = await import('../../services/alertsApi');
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'a' })]));
      // AlertsApiError takes (message, status, isConflict) explicitly — a
      // two-arg call leaves isConflict undefined and the page's classifier
      // would correctly decline to show the banner.
      vi.mocked(alertsApi.acknowledgeAlert).mockRejectedValueOnce(
        new AlertsApiError('conflict', 409, true)
      );
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /acknowledge/i })).toBeEnabled();
      });
      await userEvent.click(screen.getByRole('button', { name: /acknowledge/i }));
      await waitFor(() => {
        expect(screen.getByTestId('alerts-action-error')).toHaveTextContent(
          'This alert was changed elsewhere. The list will refresh.'
        );
      });
    });
  });

  describe('Error handling', () => {
    it('renders the error state when the list fails', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockRejectedValue(new Error('boom'));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByText('Error Loading Alerts')).toBeInTheDocument();
      });
    });
  });

  describe('Refresh', () => {
    it('has a refresh button that refetches the list', async () => {
      vi.mocked(alertsApi.fetchAlerts).mockResolvedValue(listResponse([alertRow({ id: 'a' })]));
      renderPage(<AlertsPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Refresh alerts' })).toBeInTheDocument();
      });
      const calls = vi.mocked(alertsApi.fetchAlerts).mock.calls.length;
      await userEvent.click(screen.getByRole('button', { name: 'Refresh alerts' }));
      await waitFor(() => {
        expect(vi.mocked(alertsApi.fetchAlerts).mock.calls.length).toBeGreaterThan(calls);
      });
    });
  });
});

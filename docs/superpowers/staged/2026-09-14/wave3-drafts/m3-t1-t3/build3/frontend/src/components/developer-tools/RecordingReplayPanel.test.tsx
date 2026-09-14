import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import RecordingReplayPanel from './RecordingReplayPanel';
import * as api from '../../services/api';

import type {
  RecordingsListResponse,
  RecordingDetailResponse,
  ReplayResponse,
} from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchRecordings: vi.fn(),
    fetchRecordingDetail: vi.fn(),
    replayRecording: vi.fn(),
    deleteRecording: vi.fn(),
    clearAllRecordings: vi.fn(),
  };
});

// Mock navigator.clipboard
const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.assign(navigator, { clipboard: mockClipboard });

describe('RecordingReplayPanel', () => {
  const mockRecordingsResponse: RecordingsListResponse = {
    recordings: [
      {
        recording_id: 'rec-001',
        timestamp: '2025-01-17T10:00:00Z',
        method: 'GET',
        path: '/api/events',
        status_code: 200,
        duration_ms: 45.5,
        body_truncated: false,
      },
      {
        recording_id: 'rec-002',
        timestamp: '2025-01-17T10:01:00Z',
        method: 'POST',
        path: '/api/cameras',
        status_code: 201,
        duration_ms: 120.3,
        body_truncated: false,
      },
    ],
    total: 2,
    timestamp: '2025-01-17T10:00:00Z',
  };

  const mockRecordingDetail: RecordingDetailResponse = {
    recording_id: 'rec-001',
    timestamp: '2025-01-17T10:00:00Z',
    method: 'GET',
    path: '/api/events',
    status_code: 200,
    duration_ms: 45.5,
    body_truncated: false,
    headers: { 'Content-Type': 'application/json' },
    body: null,
    response_body: { data: [] },
  };

  const mockReplayResponse: ReplayResponse = {
    recording_id: 'rec-001',
    original_status_code: 200,
    replay_status_code: 200,
    replay_response: { data: [] },
    replay_metadata: {
      original_timestamp: '2025-01-17T10:00:00Z',
      original_path: '/api/events',
      original_method: 'GET',
      replay_duration_ms: 50.0,
      replayed_at: '2025-01-17T11:00:00Z',
    },
    timestamp: '2025-01-17T11:00:00Z',
  };

  let queryClient: QueryClient;

  const renderWithProviders = (ui: React.ReactElement) => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchRecordings as ReturnType<typeof vi.fn>).mockResolvedValue(mockRecordingsResponse);
    (api.fetchRecordingDetail as ReturnType<typeof vi.fn>).mockResolvedValue(mockRecordingDetail);
    (api.replayRecording as ReturnType<typeof vi.fn>).mockResolvedValue(mockReplayResponse);
    (api.deleteRecording as ReturnType<typeof vi.fn>).mockResolvedValue({ message: 'Deleted' });
    (api.clearAllRecordings as ReturnType<typeof vi.fn>).mockResolvedValue({
      message: 'Cleared',
      deleted_count: 2,
    });
  });

  describe('rendering', () => {
    it('renders panel title', () => {
      renderWithProviders(<RecordingReplayPanel />);

      expect(screen.getByText(/request recordings/i)).toBeInTheDocument();
    });

    it('renders recordings list after loading', async () => {
      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
        expect(screen.getByText('/api/cameras')).toBeInTheDocument();
      });
    });

    it('renders Clear All button', async () => {
      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
      });
    });

    it('shows loading state initially', () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<RecordingReplayPanel />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('shows error state on fetch failure', async () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch')
      );

      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(
        () => {
          expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('view recording', () => {
    it('opens detail modal when View is clicked', async () => {
      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /view recording/i });
      fireEvent.click(viewButtons[0]);

      await waitFor(() => {
        expect(api.fetchRecordingDetail).toHaveBeenCalledWith('rec-001');
      });

      await waitFor(() => {
        expect(screen.getByText(/recording details/i)).toBeInTheDocument();
      });
    });
  });

  describe('replay recording', () => {
    it('replays recording when Replay is clicked', async () => {
      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const replayButtons = screen.getAllByRole('button', { name: /replay recording/i });
      fireEvent.click(replayButtons[0]);

      await waitFor(() => {
        expect(api.replayRecording).toHaveBeenCalledWith('rec-001');
      });
    });

    it('shows replay results modal after replay', async () => {
      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const replayButtons = screen.getAllByRole('button', { name: /replay recording/i });
      fireEvent.click(replayButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/replay results/i)).toBeInTheDocument();
      });
    });
  });

  describe('delete recording', () => {
    it('deletes recording when Delete is clicked and confirmed', async () => {
      // Mock window.confirm
      vi.spyOn(window, 'confirm').mockReturnValue(true);

      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button', { name: /delete recording/i });
      fireEvent.click(deleteButtons[0]);

      await waitFor(() => {
        expect(api.deleteRecording).toHaveBeenCalledWith('rec-001');
      });

      vi.restoreAllMocks();
    });

    it('does not delete when confirmation is cancelled', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);

      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const deleteButtons = screen.getAllByRole('button', { name: /delete recording/i });
      fireEvent.click(deleteButtons[0]);

      expect(api.deleteRecording).not.toHaveBeenCalled();

      vi.restoreAllMocks();
    });
  });

  describe('clear all recordings', () => {
    it('clears all recordings when Clear All is clicked and confirmed', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);

      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText('/api/events')).toBeInTheDocument();
      });

      const clearButton = screen.getByRole('button', { name: /clear all/i });
      fireEvent.click(clearButton);

      await waitFor(() => {
        expect(api.clearAllRecordings).toHaveBeenCalled();
      });

      vi.restoreAllMocks();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no recordings', async () => {
      (api.fetchRecordings as ReturnType<typeof vi.fn>).mockResolvedValue({
        recordings: [],
        total: 0,
        timestamp: '2025-01-17T10:00:00Z',
      });

      renderWithProviders(<RecordingReplayPanel />);

      await waitFor(() => {
        expect(screen.getByText(/no recordings yet/i)).toBeInTheDocument();
      });
    });
  });
});

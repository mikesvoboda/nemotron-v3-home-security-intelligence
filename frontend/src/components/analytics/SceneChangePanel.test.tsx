import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SceneChangePanel from './SceneChangePanel';
import * as api from '../../services/api';

import type { SceneChangeListResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchSceneChanges: vi.fn(),
  acknowledgeSceneChange: vi.fn(),
}));

describe('SceneChangePanel', () => {
  const mockCameraId = 'front_door';
  const mockCameraName = 'Front Door Camera';

  const mockSceneChanges: SceneChangeListResponse = {
    camera_id: mockCameraId,
    scene_changes: [
      {
        id: 1,
        detected_at: '2026-01-07T10:30:00Z',
        change_type: 'view_blocked',
        similarity_score: 0.23,
        acknowledged: false,
        acknowledged_at: null,
        file_path: '/export/foscam/front_door/image1.jpg',
      },
      {
        id: 2,
        detected_at: '2026-01-07T09:15:00Z',
        change_type: 'angle_changed',
        similarity_score: 0.45,
        acknowledged: true,
        acknowledged_at: '2026-01-07T09:20:00Z',
        file_path: '/export/foscam/front_door/image2.jpg',
      },
    ],
    total_changes: 2,
    next_cursor: null,
    has_more: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(api.fetchSceneChanges).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    expect(screen.getByText(/loading scene changes/i)).toBeInTheDocument();
  });

  it('renders scene changes list after loading', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('scene-changes-list')).toBeInTheDocument();
    });

    expect(screen.getByTestId('scene-change-1')).toBeInTheDocument();
    expect(screen.getByTestId('scene-change-2')).toBeInTheDocument();
  });

  it('displays camera name when provided', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText(mockCameraName)).toBeInTheDocument();
    });
  });

  it('displays correct change type badges', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText('View Blocked')).toBeInTheDocument();
      expect(screen.getByText('Angle Changed')).toBeInTheDocument();
    });
  });

  it('shows acknowledged badge for acknowledged changes', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      const acknowledgedBadges = screen.getAllByText('Acknowledged');
      expect(acknowledgedBadges).toHaveLength(1);
    });
  });

  it('displays similarity scores correctly', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText('23.0%')).toBeInTheDocument();
      expect(screen.getByText('45.0%')).toBeInTheDocument();
    });
  });

  it('shows acknowledge button for unacknowledged changes', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
      expect(screen.queryByTestId('acknowledge-2')).not.toBeInTheDocument();
    });
  });

  it('calls acknowledgeSceneChange API when acknowledge button is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);
    vi.mocked(api.acknowledgeSceneChange).mockResolvedValue({
      id: 1,
      acknowledged: true,
      acknowledged_at: '2026-01-07T10:35:00Z',
    });

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
    });

    const acknowledgeButton = screen.getByTestId('acknowledge-1');
    await user.click(acknowledgeButton);

    await waitFor(() => {
      expect(api.acknowledgeSceneChange).toHaveBeenCalledWith(mockCameraId, 1);
    });
  });

  it('updates UI after acknowledging a scene change', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);
    vi.mocked(api.acknowledgeSceneChange).mockResolvedValue({
      id: 1,
      acknowledged: true,
      acknowledged_at: '2026-01-07T10:35:00Z',
    });

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
    });

    const acknowledgeButton = screen.getByTestId('acknowledge-1');
    await user.click(acknowledgeButton);

    await waitFor(() => {
      expect(screen.queryByTestId('acknowledge-1')).not.toBeInTheDocument();
    });

    // Should now show 2 acknowledged badges
    await waitFor(() => {
      const acknowledgedBadges = screen.getAllByText('Acknowledged');
      expect(acknowledgedBadges).toHaveLength(2);
    });
  });

  it('displays empty state when no scene changes exist', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue({
      camera_id: mockCameraId,
      scene_changes: [],
      total_changes: 0,
      next_cursor: null,
      has_more: false,
    });

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText(/no scene changes detected/i)).toBeInTheDocument();
    });
  });

  it('displays error message when API call fails', async () => {
    vi.mocked(api.fetchSceneChanges).mockRejectedValue(new Error('Network error'));

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it('shows correct summary counts', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText('2', { selector: '[class*="text-white"]' })).toBeInTheDocument(); // Total
      expect(
        screen.getByText('1', { selector: '[class*="text-yellow"]' })
      ).toBeInTheDocument(); // Unacknowledged
    });
  });

  it('refreshes data when refresh button is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('refresh-scene-changes')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTestId('refresh-scene-changes');
    await user.click(refreshButton);

    await waitFor(() => {
      expect(api.fetchSceneChanges).toHaveBeenCalledTimes(2);
    });
  });

  it('fetches scene changes with correct camera ID', async () => {
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(api.fetchSceneChanges).toHaveBeenCalledWith(mockCameraId, { limit: 20 });
    });
  });

  it('displays view_tampered change type correctly', async () => {
    const tamperedSceneChanges: SceneChangeListResponse = {
      camera_id: mockCameraId,
      scene_changes: [
        {
          id: 3,
          detected_at: '2026-01-07T11:00:00Z',
          change_type: 'view_tampered',
          similarity_score: 0.15,
          acknowledged: false,
          acknowledged_at: null,
          file_path: '/export/foscam/front_door/image3.jpg',
        },
      ],
      total_changes: 1,
      next_cursor: null,
      has_more: false,
    };

    vi.mocked(api.fetchSceneChanges).mockResolvedValue(tamperedSceneChanges);

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByText('View Tampered')).toBeInTheDocument();
    });
  });

  it('handles acknowledge failure gracefully', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);
    vi.mocked(api.acknowledgeSceneChange).mockRejectedValue(
      new Error('Failed to acknowledge')
    );

    render(<SceneChangePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

    await waitFor(() => {
      expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
    });

    const acknowledgeButton = screen.getByTestId('acknowledge-1');
    await user.click(acknowledgeButton);

    await waitFor(() => {
      expect(screen.getByText(/failed to acknowledge/i)).toBeInTheDocument();
    });

    // Button should still be visible after failure
    expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
  });
});

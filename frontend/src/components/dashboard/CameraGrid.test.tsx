import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CameraGrid, { type CameraStatus } from './CameraGrid';

describe('CameraGrid', () => {
  // Mock the Date for consistent relative time testing
  const mockDate = new Date('2025-01-15T12:35:00Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(mockDate);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const mockCameras: CameraStatus[] = [
    {
      id: 'cam1',
      name: 'Front Door',
      status: 'online',
      thumbnail_url: '/thumbnails/cam1.jpg',
      last_seen_at: '2025-01-15T12:30:00Z',
    },
    {
      id: 'cam2',
      name: 'Backyard',
      status: 'recording',
      thumbnail_url: '/thumbnails/cam2.jpg',
      last_seen_at: '2025-01-15T12:31:00Z',
    },
    {
      id: 'cam3',
      name: 'Garage',
      status: 'offline',
      last_seen_at: '2025-01-15T11:00:00Z',
    },
    {
      id: 'cam4',
      name: 'Side Gate',
      status: 'unknown',
    },
  ];

  describe('Rendering', () => {
    it('should render all cameras in a grid', () => {
      render(<CameraGrid cameras={mockCameras} />);

      expect(screen.getByRole('group', { name: 'Camera grid' })).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('should display empty state when no cameras are provided', () => {
      render(<CameraGrid cameras={[]} />);

      expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      expect(screen.getByText('Add cameras in Settings to start monitoring')).toBeInTheDocument();
      expect(screen.getByTestId('camera-grid-empty')).toBeInTheDocument();
    });

    it('should display camera thumbnails when available', () => {
      render(<CameraGrid cameras={mockCameras} />);

      const thumbnail1 = screen.getByAltText('Front Door thumbnail');
      expect(thumbnail1).toBeInTheDocument();
      expect(thumbnail1).toHaveAttribute('src', '/thumbnails/cam1.jpg');

      const thumbnail2 = screen.getByAltText('Backyard thumbnail');
      expect(thumbnail2).toBeInTheDocument();
      expect(thumbnail2).toHaveAttribute('src', '/thumbnails/cam2.jpg');
    });

    it('should display placeholder icon when thumbnail is not available', () => {
      render(<CameraGrid cameras={[mockCameras[2]]} />);

      // Should not have an img element for thumbnail
      expect(screen.queryByAltText('Garage thumbnail')).not.toBeInTheDocument();

      // Should still render the camera name
      expect(screen.getByText('Garage')).toBeInTheDocument();
    });

    it('should apply custom className when provided', () => {
      const { container } = render(<CameraGrid cameras={mockCameras} className="custom-class" />);

      const grid = container.querySelector('.custom-class');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Status Indicators', () => {
    it('should display online status with correct styling', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      expect(screen.getByText('Online')).toBeInTheDocument();
    });

    it('should display recording status with correct styling', () => {
      render(<CameraGrid cameras={[mockCameras[1]]} />);

      expect(screen.getByText('Recording')).toBeInTheDocument();
    });

    it('should display offline status with correct styling', () => {
      render(<CameraGrid cameras={[mockCameras[2]]} />);

      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    it('should display unknown status with correct styling', () => {
      render(<CameraGrid cameras={[mockCameras[3]]} />);

      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('should display last seen time when available', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      // Check that some time string is displayed (exact format may vary by locale)
      const cameraCard = screen.getByText('Front Door').closest('button');
      expect(cameraCard).toBeInTheDocument();
      // The time should be formatted as HH:MM
      expect(cameraCard?.textContent).toMatch(/\d{1,2}:\d{2}/);
    });
  });

  describe('Selection', () => {
    it('should highlight selected camera', () => {
      render(<CameraGrid cameras={mockCameras} selectedCameraId="cam2" />);

      const backyard = screen.getByLabelText(/Backyard.*status: Recording/);
      expect(backyard).toHaveAttribute('aria-pressed', 'true');
    });

    it('should not highlight cameras that are not selected', () => {
      render(<CameraGrid cameras={mockCameras} selectedCameraId="cam2" />);

      const frontDoor = screen.getByLabelText(/Front Door.*status: Online/);
      expect(frontDoor).toHaveAttribute('aria-pressed', 'false');
    });

    it('should not highlight any camera when selectedCameraId is undefined', () => {
      render(<CameraGrid cameras={mockCameras} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).toHaveAttribute('aria-pressed', 'false');
      });
    });
  });

  describe('Click Handling', () => {
    it('should call onCameraClick with camera id when camera is clicked', () => {
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);
      fireEvent.click(frontDoorButton);

      expect(onCameraClick).toHaveBeenCalledWith('cam1');
      expect(onCameraClick).toHaveBeenCalledTimes(1);
    });

    it('should call onCameraClick with correct id for different cameras', () => {
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const backyardButton = screen.getByLabelText(/Backyard.*status: Recording/);
      fireEvent.click(backyardButton);

      expect(onCameraClick).toHaveBeenCalledWith('cam2');
    });

    it('should not call onCameraClick when handler is not provided', () => {
      render(<CameraGrid cameras={mockCameras} />);

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);

      // Should not throw error when clicked
      expect(() => fireEvent.click(frontDoorButton)).not.toThrow();
    });

    it('should allow clicking on selected camera again', () => {
      const onCameraClick = vi.fn();

      render(
        <CameraGrid cameras={mockCameras} selectedCameraId="cam1" onCameraClick={onCameraClick} />
      );

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);
      fireEvent.click(frontDoorButton);

      expect(onCameraClick).toHaveBeenCalledWith('cam1');
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels for cameras', () => {
      render(<CameraGrid cameras={mockCameras} />);

      expect(screen.getByLabelText('Camera Front Door, status: Online')).toBeInTheDocument();
      expect(screen.getByLabelText('Camera Backyard, status: Recording')).toBeInTheDocument();
      expect(screen.getByLabelText('Camera Garage, status: Offline')).toBeInTheDocument();
      expect(screen.getByLabelText('Camera Side Gate, status: Unknown')).toBeInTheDocument();
    });

    it('should mark grid container as group with proper label', () => {
      render(<CameraGrid cameras={mockCameras} />);

      const grid = screen.getByRole('group', { name: 'Camera grid' });
      expect(grid).toBeInTheDocument();
    });

    it('should have proper aria-pressed state for buttons', () => {
      render(<CameraGrid cameras={mockCameras} selectedCameraId="cam1" />);

      const buttons = screen.getAllByRole('button');
      expect(buttons[0]).toHaveAttribute('aria-pressed', 'true');
      expect(buttons[1]).toHaveAttribute('aria-pressed', 'false');
      expect(buttons[2]).toHaveAttribute('aria-pressed', 'false');
      expect(buttons[3]).toHaveAttribute('aria-pressed', 'false');
    });

    it('should be keyboard navigable', () => {
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const firstButton = screen.getByLabelText(/Front Door/);

      // Focus on first button
      firstButton.focus();
      expect(firstButton).toHaveFocus();

      // Buttons respond to Enter/Space via click events in browsers
      // Use fireEvent.click to simulate the keyboard activation behavior
      fireEvent.click(firstButton);
      expect(onCameraClick).toHaveBeenCalledWith('cam1');

      // Verify button element is properly keyboard-accessible
      expect(firstButton.tagName).toBe('BUTTON');
      expect(firstButton).not.toHaveAttribute('tabindex', '-1');
    });
  });

  describe('Responsive Layout', () => {
    it('should apply responsive grid classes', () => {
      const { container } = render(<CameraGrid cameras={mockCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('sm:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-3');
    });

    it('should maintain grid gap', () => {
      const { container } = render(<CameraGrid cameras={mockCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('gap-4');
    });
  });

  describe('Uneven Camera Count Layout', () => {
    it('should center single camera in grid', () => {
      const singleCamera: CameraStatus[] = [
        { id: 'cam1', name: 'Single Camera', status: 'online' },
      ];

      const { container } = render(<CameraGrid cameras={singleCamera} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('justify-items-center');
    });

    it('should center items for 3 cameras', () => {
      const threeCameras: CameraStatus[] = [
        { id: 'cam1', name: 'Camera 1', status: 'online' },
        { id: 'cam2', name: 'Camera 2', status: 'online' },
        { id: 'cam3', name: 'Camera 3', status: 'online' },
      ];

      const { container } = render(<CameraGrid cameras={threeCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('justify-items-center');
    });

    it('should center items for 5 cameras', () => {
      const fiveCameras: CameraStatus[] = [
        { id: 'cam1', name: 'Camera 1', status: 'online' },
        { id: 'cam2', name: 'Camera 2', status: 'online' },
        { id: 'cam3', name: 'Camera 3', status: 'online' },
        { id: 'cam4', name: 'Camera 4', status: 'online' },
        { id: 'cam5', name: 'Camera 5', status: 'online' },
      ];

      const { container } = render(<CameraGrid cameras={fiveCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('justify-items-center');
    });

    it('should center items for 7 cameras', () => {
      const sevenCameras: CameraStatus[] = [
        { id: 'cam1', name: 'Camera 1', status: 'online' },
        { id: 'cam2', name: 'Camera 2', status: 'online' },
        { id: 'cam3', name: 'Camera 3', status: 'online' },
        { id: 'cam4', name: 'Camera 4', status: 'online' },
        { id: 'cam5', name: 'Camera 5', status: 'online' },
        { id: 'cam6', name: 'Camera 6', status: 'online' },
        { id: 'cam7', name: 'Camera 7', status: 'online' },
      ];

      const { container } = render(<CameraGrid cameras={sevenCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('justify-items-center');
    });

    it('should have consistent card widths using w-full on camera cards', () => {
      const threeCameras: CameraStatus[] = [
        { id: 'cam1', name: 'Camera 1', status: 'online' },
        { id: 'cam2', name: 'Camera 2', status: 'online' },
        { id: 'cam3', name: 'Camera 3', status: 'online' },
      ];

      render(<CameraGrid cameras={threeCameras} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).toHaveClass('w-full');
      });
    });

    it('should render all cameras regardless of count', () => {
      const fiveCameras: CameraStatus[] = [
        { id: 'cam1', name: 'Camera 1', status: 'online' },
        { id: 'cam2', name: 'Camera 2', status: 'recording' },
        { id: 'cam3', name: 'Camera 3', status: 'offline' },
        { id: 'cam4', name: 'Camera 4', status: 'error' },
        { id: 'cam5', name: 'Camera 5', status: 'unknown' },
      ];

      render(<CameraGrid cameras={fiveCameras} />);

      expect(screen.getByText('Camera 1')).toBeInTheDocument();
      expect(screen.getByText('Camera 2')).toBeInTheDocument();
      expect(screen.getByText('Camera 3')).toBeInTheDocument();
      expect(screen.getByText('Camera 4')).toBeInTheDocument();
      expect(screen.getByText('Camera 5')).toBeInTheDocument();
    });
  });

  describe('Image Loading', () => {
    it('should set loading="lazy" for thumbnail images', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      const thumbnail = screen.getByAltText('Front Door thumbnail');
      expect(thumbnail).toHaveAttribute('loading', 'lazy');
    });

    it('should show loading skeleton initially while image loads', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      // The loading skeleton has animate-pulse class
      const { container } = render(<CameraGrid cameras={[mockCameras[0]]} />);
      const skeleton = container.querySelector('.animate-pulse');
      expect(skeleton).toBeInTheDocument();
    });

    it('should hide loading skeleton after image loads', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      const thumbnail = screen.getByAltText('Front Door thumbnail');

      // Initially should have opacity-0 while loading
      expect(thumbnail).toHaveClass('opacity-0');

      // Simulate image load event using fireEvent
      fireEvent.load(thumbnail);

      // After load, the image should be fully visible (opacity-100)
      expect(thumbnail).toHaveClass('opacity-100');
    });

    it('should show placeholder on image error', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      const thumbnail = screen.getByAltText('Front Door thumbnail');

      // Simulate image error event using fireEvent
      fireEvent.error(thumbnail);

      // After error, the thumbnail image should be hidden (not in document)
      // and placeholder icon should be visible
      expect(screen.queryByAltText('Front Door thumbnail')).not.toBeInTheDocument();
    });

    it('should show placeholder when thumbnail_url is not provided', () => {
      const cameraWithoutThumbnail: CameraStatus = {
        id: 'cam-no-thumb',
        name: 'No Thumbnail Camera',
        status: 'online',
      };

      render(<CameraGrid cameras={[cameraWithoutThumbnail]} />);

      // Should not have an img element
      expect(screen.queryByAltText('No Thumbnail Camera thumbnail')).not.toBeInTheDocument();

      // Should render the camera name
      expect(screen.getByText('No Thumbnail Camera')).toBeInTheDocument();
    });

    it('should apply opacity transition classes to thumbnail image', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      const thumbnail = screen.getByAltText('Front Door thumbnail');
      expect(thumbnail).toHaveClass('transition-opacity');
      expect(thumbnail).toHaveClass('duration-300');
    });

    it('should not attempt to load thumbnail for offline cameras even with thumbnail_url', () => {
      const offlineCameraWithThumbnail: CameraStatus = {
        id: 'cam-offline-thumb',
        name: 'Offline With Thumbnail',
        status: 'offline',
        thumbnail_url: '/thumbnails/offline-cam.jpg',
      };

      render(<CameraGrid cameras={[offlineCameraWithThumbnail]} />);

      // Should NOT have an img element - offline cameras shouldn't attempt to load thumbnails
      expect(screen.queryByAltText('Offline With Thumbnail thumbnail')).not.toBeInTheDocument();

      // Should render the camera name
      expect(screen.getByText('Offline With Thumbnail')).toBeInTheDocument();
      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    it('should not attempt to load thumbnail for error status cameras even with thumbnail_url', () => {
      const errorCameraWithThumbnail: CameraStatus = {
        id: 'cam-error-thumb',
        name: 'Error With Thumbnail',
        status: 'error',
        thumbnail_url: '/thumbnails/error-cam.jpg',
      };

      render(<CameraGrid cameras={[errorCameraWithThumbnail]} />);

      // Should NOT have an img element - error cameras shouldn't attempt to load thumbnails
      expect(screen.queryByAltText('Error With Thumbnail thumbnail')).not.toBeInTheDocument();

      // Should render the camera name and error status
      expect(screen.getByText('Error With Thumbnail')).toBeInTheDocument();
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('should not attempt to load thumbnail for unknown status cameras even with thumbnail_url', () => {
      const unknownCameraWithThumbnail: CameraStatus = {
        id: 'cam-unknown-thumb',
        name: 'Unknown With Thumbnail',
        status: 'unknown',
        thumbnail_url: '/thumbnails/unknown-cam.jpg',
      };

      render(<CameraGrid cameras={[unknownCameraWithThumbnail]} />);

      // Should NOT have an img element - unknown cameras shouldn't attempt to load thumbnails
      expect(screen.queryByAltText('Unknown With Thumbnail thumbnail')).not.toBeInTheDocument();

      // Should render the camera name and unknown status
      expect(screen.getByText('Unknown With Thumbnail')).toBeInTheDocument();
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('should attempt to load thumbnail for recording cameras with thumbnail_url', () => {
      render(<CameraGrid cameras={[mockCameras[1]]} />);

      // Recording camera should have thumbnail loaded
      const thumbnail = screen.getByAltText('Backyard thumbnail');
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('src', '/thumbnails/cam2.jpg');
    });
  });

  describe('Enhanced Placeholder States', () => {
    it('should show offline message in placeholder for offline cameras', () => {
      const offlineCamera: CameraStatus = {
        id: 'cam-offline',
        name: 'Offline Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T12:30:00Z',
      };

      render(<CameraGrid cameras={[offlineCamera]} />);

      expect(screen.getByText('Camera is offline')).toBeInTheDocument();
      expect(screen.getByTestId('camera-placeholder-cam-offline')).toBeInTheDocument();
    });

    it('should show error message in placeholder for error status cameras', () => {
      const errorCamera: CameraStatus = {
        id: 'cam-error',
        name: 'Error Camera',
        status: 'error',
      };

      render(<CameraGrid cameras={[errorCamera]} />);

      expect(screen.getByText('Connection error')).toBeInTheDocument();
      expect(screen.getByTestId('camera-placeholder-cam-error')).toBeInTheDocument();
    });

    it('should show custom error message when provided', () => {
      const errorCameraWithMessage: CameraStatus = {
        id: 'cam-error-custom',
        name: 'Error Camera Custom',
        status: 'error',
        error_message: 'Network timeout',
      };

      render(<CameraGrid cameras={[errorCameraWithMessage]} />);

      expect(screen.getByText('Network timeout')).toBeInTheDocument();
    });

    it('should show unknown status message in placeholder', () => {
      const unknownCamera: CameraStatus = {
        id: 'cam-unknown',
        name: 'Unknown Camera',
        status: 'unknown',
      };

      render(<CameraGrid cameras={[unknownCamera]} />);

      expect(screen.getByText('Status unknown')).toBeInTheDocument();
      expect(screen.getByTestId('camera-placeholder-cam-unknown')).toBeInTheDocument();
    });

    it('should show no preview message for recording cameras without thumbnail', () => {
      const recordingCameraNoThumb: CameraStatus = {
        id: 'cam-recording-no-thumb',
        name: 'Recording No Thumb',
        status: 'recording',
      };

      render(<CameraGrid cameras={[recordingCameraNoThumb]} />);

      expect(screen.getByText('No preview available')).toBeInTheDocument();
    });

    it('should show no image message for online cameras without thumbnail', () => {
      const onlineCameraNoThumb: CameraStatus = {
        id: 'cam-online-no-thumb',
        name: 'Online No Thumb',
        status: 'online',
      };

      render(<CameraGrid cameras={[onlineCameraNoThumb]} />);

      expect(screen.getByText('No image available')).toBeInTheDocument();
    });

    it('should show last seen time for offline cameras in placeholder', () => {
      const offlineCameraWithLastSeen: CameraStatus = {
        id: 'cam-offline-seen',
        name: 'Offline Seen',
        status: 'offline',
        last_seen_at: '2025-01-15T12:30:00Z', // 5 mins ago from mockDate
      };

      render(<CameraGrid cameras={[offlineCameraWithLastSeen]} />);

      // Should show "Last seen X mins ago" in the placeholder
      expect(screen.getByText(/Last seen/)).toBeInTheDocument();
    });

    it('should apply gradient background for error cameras', () => {
      const errorCamera: CameraStatus = {
        id: 'cam-error-bg',
        name: 'Error BG Camera',
        status: 'error',
      };

      render(<CameraGrid cameras={[errorCamera]} />);

      const placeholder = screen.getByTestId('camera-placeholder-cam-error-bg');
      expect(placeholder).toHaveClass('bg-gradient-to-br');
    });

    it('should apply gradient background for offline cameras', () => {
      const offlineCamera: CameraStatus = {
        id: 'cam-offline-bg',
        name: 'Offline BG Camera',
        status: 'offline',
      };

      render(<CameraGrid cameras={[offlineCamera]} />);

      const placeholder = screen.getByTestId('camera-placeholder-cam-offline-bg');
      expect(placeholder).toHaveClass('bg-gradient-to-br');
    });
  });

  describe('Relative Time Formatting', () => {
    it('should format "just now" for very recent timestamps', () => {
      const recentCamera: CameraStatus = {
        id: 'cam-recent',
        name: 'Recent Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T12:34:30Z', // 30 seconds ago
      };

      render(<CameraGrid cameras={[recentCamera]} />);

      expect(screen.getByText(/just now/)).toBeInTheDocument();
    });

    it('should format "1 min ago" for 1 minute old timestamps', () => {
      const oneMinCamera: CameraStatus = {
        id: 'cam-one-min',
        name: 'One Min Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T12:34:00Z', // 1 minute ago
      };

      render(<CameraGrid cameras={[oneMinCamera]} />);

      expect(screen.getByText(/1 min ago/)).toBeInTheDocument();
    });

    it('should format "X mins ago" for timestamps less than an hour', () => {
      const fiveMinsCamera: CameraStatus = {
        id: 'cam-five-mins',
        name: 'Five Mins Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T12:30:00Z', // 5 minutes ago
      };

      render(<CameraGrid cameras={[fiveMinsCamera]} />);

      expect(screen.getByText(/5 mins ago/)).toBeInTheDocument();
    });

    it('should format "1 hour ago" for 1 hour old timestamps', () => {
      const oneHourCamera: CameraStatus = {
        id: 'cam-one-hour',
        name: 'One Hour Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T11:35:00Z', // 1 hour ago
      };

      render(<CameraGrid cameras={[oneHourCamera]} />);

      expect(screen.getByText(/1 hour ago/)).toBeInTheDocument();
    });

    it('should format "X hours ago" for timestamps less than a day', () => {
      const fiveHoursCamera: CameraStatus = {
        id: 'cam-five-hours',
        name: 'Five Hours Camera',
        status: 'offline',
        last_seen_at: '2025-01-15T07:35:00Z', // 5 hours ago
      };

      render(<CameraGrid cameras={[fiveHoursCamera]} />);

      expect(screen.getByText(/5 hours ago/)).toBeInTheDocument();
    });

    it('should format "1 day ago" for 1 day old timestamps', () => {
      const oneDayCamera: CameraStatus = {
        id: 'cam-one-day',
        name: 'One Day Camera',
        status: 'offline',
        last_seen_at: '2025-01-14T12:35:00Z', // 1 day ago
      };

      render(<CameraGrid cameras={[oneDayCamera]} />);

      expect(screen.getByText(/1 day ago/)).toBeInTheDocument();
    });

    it('should format "X days ago" for timestamps less than a week', () => {
      const threeDaysCamera: CameraStatus = {
        id: 'cam-three-days',
        name: 'Three Days Camera',
        status: 'offline',
        last_seen_at: '2025-01-12T12:35:00Z', // 3 days ago
      };

      render(<CameraGrid cameras={[threeDaysCamera]} />);

      expect(screen.getByText(/3 days ago/)).toBeInTheDocument();
    });
  });

  describe('Error Status Display', () => {
    it('should display error status badge for cameras with error status', () => {
      const errorCamera: CameraStatus = {
        id: 'cam-error-status',
        name: 'Error Status Camera',
        status: 'error',
      };

      render(<CameraGrid cameras={[errorCamera]} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('should have proper ARIA label for error status camera', () => {
      const errorCamera: CameraStatus = {
        id: 'cam-error-aria',
        name: 'Error ARIA Camera',
        status: 'error',
      };

      render(<CameraGrid cameras={[errorCamera]} />);

      expect(screen.getByLabelText('Camera Error ARIA Camera, status: Error')).toBeInTheDocument();
    });
  });

  describe('Scene Change Activity Indicators (NEM-3126)', () => {
    it('should show scene change indicator when camera has activity (array)', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
        { id: 'cam2', name: 'Backyard', status: 'online' },
      ];

      render(
        <CameraGrid cameras={cameras} sceneChangeActivityIds={['cam1']} />
      );

      expect(screen.getByTestId('scene-change-indicator-cam1')).toBeInTheDocument();
      expect(screen.queryByTestId('scene-change-indicator-cam2')).not.toBeInTheDocument();
      expect(screen.getByText('Scene Change')).toBeInTheDocument();
    });

    it('should show scene change indicator when camera has activity (Set)', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
        { id: 'cam2', name: 'Backyard', status: 'online' },
      ];

      render(
        <CameraGrid cameras={cameras} sceneChangeActivityIds={new Set(['cam2'])} />
      );

      expect(screen.queryByTestId('scene-change-indicator-cam1')).not.toBeInTheDocument();
      expect(screen.getByTestId('scene-change-indicator-cam2')).toBeInTheDocument();
    });

    it('should show scene change indicator for multiple cameras', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
        { id: 'cam2', name: 'Backyard', status: 'online' },
        { id: 'cam3', name: 'Garage', status: 'online' },
      ];

      render(
        <CameraGrid cameras={cameras} sceneChangeActivityIds={['cam1', 'cam3']} />
      );

      expect(screen.getByTestId('scene-change-indicator-cam1')).toBeInTheDocument();
      expect(screen.queryByTestId('scene-change-indicator-cam2')).not.toBeInTheDocument();
      expect(screen.getByTestId('scene-change-indicator-cam3')).toBeInTheDocument();
      // Should show "Scene Change" text for both cameras
      expect(screen.getAllByText('Scene Change')).toHaveLength(2);
    });

    it('should not show scene change indicator when sceneChangeActivityIds is undefined', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
      ];

      render(<CameraGrid cameras={cameras} />);

      expect(screen.queryByTestId('scene-change-indicator-cam1')).not.toBeInTheDocument();
    });

    it('should not show scene change indicator when sceneChangeActivityIds is empty', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
      ];

      render(<CameraGrid cameras={cameras} sceneChangeActivityIds={[]} />);

      expect(screen.queryByTestId('scene-change-indicator-cam1')).not.toBeInTheDocument();
    });

    it('should apply pulsing animation to scene change indicator', () => {
      const cameras: CameraStatus[] = [
        { id: 'cam1', name: 'Front Door', status: 'online' },
      ];

      render(
        <CameraGrid cameras={cameras} sceneChangeActivityIds={['cam1']} />
      );

      const indicator = screen.getByTestId('scene-change-indicator-cam1');
      // The AlertTriangle icon should have animate-pulse class
      const icon = indicator.querySelector('svg');
      expect(icon).toHaveClass('animate-pulse');
    });
  });
});

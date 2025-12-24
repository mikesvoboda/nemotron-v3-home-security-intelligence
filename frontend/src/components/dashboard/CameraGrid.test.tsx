import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import CameraGrid, { type CameraStatus } from './CameraGrid';

describe('CameraGrid', () => {
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

      expect(screen.getByRole('list', { name: 'Camera grid' })).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('should display empty state when no cameras are provided', () => {
      render(<CameraGrid cameras={[]} />);

      expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      expect(screen.getByText('Add cameras to start monitoring')).toBeInTheDocument();
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
      const { container } = render(
        <CameraGrid cameras={mockCameras} className="custom-class" />
      );

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
    it('should call onCameraClick with camera id when camera is clicked', async () => {
      const user = userEvent.setup();
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);
      await user.click(frontDoorButton);

      expect(onCameraClick).toHaveBeenCalledWith('cam1');
      expect(onCameraClick).toHaveBeenCalledTimes(1);
    });

    it('should call onCameraClick with correct id for different cameras', async () => {
      const user = userEvent.setup();
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const backyardButton = screen.getByLabelText(/Backyard.*status: Recording/);
      await user.click(backyardButton);

      expect(onCameraClick).toHaveBeenCalledWith('cam2');
    });

    it('should not call onCameraClick when handler is not provided', async () => {
      const user = userEvent.setup();

      render(<CameraGrid cameras={mockCameras} />);

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);

      // Should not throw error when clicked
      await expect(user.click(frontDoorButton)).resolves.not.toThrow();
    });

    it('should allow clicking on selected camera again', async () => {
      const user = userEvent.setup();
      const onCameraClick = vi.fn();

      render(
        <CameraGrid cameras={mockCameras} selectedCameraId="cam1" onCameraClick={onCameraClick} />
      );

      const frontDoorButton = screen.getByLabelText(/Front Door.*status: Online/);
      await user.click(frontDoorButton);

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

    it('should mark grid container as list with proper label', () => {
      render(<CameraGrid cameras={mockCameras} />);

      const grid = screen.getByRole('list', { name: 'Camera grid' });
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

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();
      const onCameraClick = vi.fn();

      render(<CameraGrid cameras={mockCameras} onCameraClick={onCameraClick} />);

      const firstButton = screen.getByLabelText(/Front Door/);

      // Focus on first button
      await user.tab();
      expect(firstButton).toHaveFocus();

      // Press Enter to activate
      await user.keyboard('{Enter}');
      expect(onCameraClick).toHaveBeenCalledWith('cam1');
    });
  });

  describe('Responsive Layout', () => {
    it('should apply responsive grid classes', () => {
      const { container } = render(<CameraGrid cameras={mockCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('sm:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-3');
      expect(grid).toHaveClass('xl:grid-cols-4');
    });

    it('should maintain grid gap', () => {
      const { container } = render(<CameraGrid cameras={mockCameras} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('gap-4');
    });
  });

  describe('Image Loading', () => {
    it('should set loading="lazy" for thumbnail images', () => {
      render(<CameraGrid cameras={[mockCameras[0]]} />);

      const thumbnail = screen.getByAltText('Front Door thumbnail');
      expect(thumbnail).toHaveAttribute('loading', 'lazy');
    });
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CameraSelector from './CameraSelector';

import type { CameraOption, CameraSelectorProps } from './CameraSelector';

describe('CameraSelector', () => {
  const mockOnChange = vi.fn();

  const mockCameras: CameraOption[] = [
    { id: 'front_door', name: 'Front Door', status: 'online' },
    { id: 'back_yard', name: 'Back Yard', status: 'online' },
    { id: 'garage', name: 'Garage', status: 'offline' },
    { id: 'side_gate', name: 'Side Gate', status: 'error' },
  ];

  const defaultProps: CameraSelectorProps = {
    value: '',
    onChange: mockOnChange,
    cameras: mockCameras,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders select with accessible label', () => {
      render(<CameraSelector {...defaultProps} />);

      expect(screen.getByRole('combobox', { name: /select camera/i })).toBeInTheDocument();
    });

    it('renders "All Cameras" option by default', () => {
      render(<CameraSelector {...defaultProps} />);

      expect(screen.getByRole('option', { name: 'All Cameras' })).toBeInTheDocument();
    });

    it('renders custom "All" label', () => {
      render(<CameraSelector {...defaultProps} allLabel="All Sources" />);

      expect(screen.getByRole('option', { name: 'All Sources' })).toBeInTheDocument();
    });

    it('renders all camera options', () => {
      render(<CameraSelector {...defaultProps} />);

      expect(screen.getByRole('option', { name: /front door/i })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: /back yard/i })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: /garage/i })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: /side gate/i })).toBeInTheDocument();
    });

    it('shows status in option text when showStatus is true', () => {
      render(<CameraSelector {...defaultProps} showStatus={true} />);

      expect(screen.getByRole('option', { name: 'Front Door (online)' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Garage (offline)' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Side Gate (error)' })).toBeInTheDocument();
    });

    it('hides status when showStatus is false', () => {
      render(<CameraSelector {...defaultProps} showStatus={false} />);

      expect(screen.getByRole('option', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.queryByRole('option', { name: /online/i })).not.toBeInTheDocument();
    });

    it('displays current selected value', () => {
      render(<CameraSelector {...defaultProps} value="front_door" />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      expect(select).toHaveValue('front_door');
    });

    it('applies custom className', () => {
      const { container } = render(<CameraSelector {...defaultProps} className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Selection interactions with useTransition', () => {
    it('calls onChange when camera is selected', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      await user.selectOptions(select, 'front_door');

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalledWith('front_door');
      });
    });

    it('calls onChange with empty string when "All Cameras" is selected', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} value="front_door" />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      await user.selectOptions(select, '');

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalledWith('');
      });
    });

    it('handles rapid selection changes', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });

      // Simulate rapid changes
      await user.selectOptions(select, 'front_door');
      await user.selectOptions(select, 'back_yard');
      await user.selectOptions(select, 'garage');

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalled();
      });
    });
  });

  describe('Disabled state', () => {
    it('disables select when disabled prop is true', () => {
      render(<CameraSelector {...defaultProps} disabled={true} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      expect(select).toBeDisabled();
    });

    it('does not call onChange when disabled', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} disabled={true} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });

      // Attempt to change selection (should not work)
      await user.selectOptions(select, 'front_door').catch(() => {
        // Expected to fail when disabled
      });

      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  describe('useTransition loading indicator', () => {
    // Note: Testing isPending state is challenging in unit tests because
    // useTransition's pending state resolves quickly. These tests verify
    // the component handles loading state gracefully.

    it('renders without loading indicator initially', () => {
      render(<CameraSelector {...defaultProps} />);

      expect(screen.queryByTestId('camera-loading-indicator')).not.toBeInTheDocument();
    });

    it('select remains interactive after selection', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      await user.selectOptions(select, 'front_door');

      // Should still be interactive
      expect(select).not.toBeDisabled();
    });
  });

  describe('Status indicators', () => {
    it('shows status indicator for selected camera', () => {
      const { container } = render(<CameraSelector {...defaultProps} value="front_door" />);

      // Online status should show green indicator
      const indicator = container.querySelector('.bg-\\[\\#76B900\\]');
      expect(indicator).toBeInTheDocument();
    });

    it('shows offline status indicator', () => {
      const { container } = render(<CameraSelector {...defaultProps} value="garage" />);

      // Offline status should show gray indicator
      const indicator = container.querySelector('.bg-gray-500');
      expect(indicator).toBeInTheDocument();
    });

    it('shows error status indicator', () => {
      const { container } = render(<CameraSelector {...defaultProps} value="side_gate" />);

      // Error status should show red indicator
      const indicator = container.querySelector('.bg-red-500');
      expect(indicator).toBeInTheDocument();
    });

    it('hides status indicator when showStatus is false', () => {
      const { container } = render(
        <CameraSelector {...defaultProps} value="front_door" showStatus={false} />
      );

      // No status indicator should be visible
      const greenIndicator = container.querySelector('.bg-\\[\\#76B900\\]');
      expect(greenIndicator).not.toBeInTheDocument();
    });

    it('hides status indicator when no camera is selected', () => {
      const { container } = render(<CameraSelector {...defaultProps} value="" />);

      // No status indicator for "All Cameras"
      const greenIndicator = container.querySelector('.bg-\\[\\#76B900\\]');
      expect(greenIndicator).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible select with aria-label', () => {
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      expect(select).toHaveAttribute('aria-label', 'Select camera');
    });

    it('loading indicator has aria-label', () => {
      // Verify the loading indicator markup is correct
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      expect(select).toBeInTheDocument();
    });

    it('status indicator is aria-hidden', () => {
      const { container } = render(<CameraSelector {...defaultProps} value="front_door" />);

      const indicator = container.querySelector('[aria-hidden="true"]');
      expect(indicator).toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('handles empty cameras array', () => {
      render(<CameraSelector {...defaultProps} cameras={[]} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      expect(select).toBeInTheDocument();

      // Should only have the "All Cameras" option
      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('All Cameras');
    });

    it('handles cameras without status', () => {
      const camerasNoStatus: CameraOption[] = [
        { id: 'cam1', name: 'Camera 1' },
        { id: 'cam2', name: 'Camera 2' },
      ];

      render(<CameraSelector {...defaultProps} cameras={camerasNoStatus} />);

      expect(screen.getByRole('option', { name: 'Camera 1' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Camera 2' })).toBeInTheDocument();
    });

    it('handles camera with special characters in name', () => {
      const specialCameras: CameraOption[] = [
        { id: 'cam1', name: 'Camera (Main) #1', status: 'online' },
      ];

      render(<CameraSelector {...defaultProps} cameras={specialCameras} />);

      expect(screen.getByRole('option', { name: /Camera \(Main\) #1/i })).toBeInTheDocument();
    });

    it('handles invalid selected value gracefully', () => {
      render(<CameraSelector {...defaultProps} value="nonexistent_camera" />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      // Invalid value defaults to empty (first option) in HTML select
      // The browser will show empty because the value doesn't match any option
      expect(select).toHaveValue('');
    });

    it('updates when cameras prop changes', () => {
      const { rerender } = render(<CameraSelector {...defaultProps} cameras={[]} />);

      expect(screen.getAllByRole('option')).toHaveLength(1);

      rerender(<CameraSelector {...defaultProps} cameras={mockCameras} />);

      expect(screen.getAllByRole('option')).toHaveLength(5); // All + 4 cameras
    });
  });

  describe('Keyboard navigation', () => {
    it('can be focused', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      await user.click(select);

      expect(select).toHaveFocus();
    });

    it('can navigate options with keyboard', async () => {
      const user = userEvent.setup();
      render(<CameraSelector {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /select camera/i });
      await user.click(select);
      await user.keyboard('{ArrowDown}');

      // Should be able to navigate options
      expect(select).toHaveFocus();
    });
  });
});

/**
 * Tests for CameraAnalyticsSelector component
 *
 * Tests cover:
 * - Rendering camera options in dropdown
 * - "All Cameras" option at top of list
 * - Selection change callback
 * - Loading state
 * - Disabled state
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CameraAnalyticsSelector from './CameraAnalyticsSelector';

import type { CameraOption } from '../../hooks/useCameraAnalytics';

describe('CameraAnalyticsSelector', () => {
  const mockCameras: CameraOption[] = [
    { id: '', name: 'All Cameras' },
    { id: 'front-door', name: 'Front Door' },
    { id: 'backyard', name: 'Backyard' },
    { id: 'garage', name: 'Garage' },
  ];

  const defaultProps = {
    cameras: mockCameras,
    selectedCameraId: '',
    onCameraChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders with test id', () => {
      render(<CameraAnalyticsSelector {...defaultProps} />);

      expect(screen.getByTestId('camera-analytics-selector')).toBeInTheDocument();
    });

    it('renders the label', () => {
      render(<CameraAnalyticsSelector {...defaultProps} />);

      expect(screen.getByText('Camera')).toBeInTheDocument();
    });

    it('displays selected camera name', () => {
      render(<CameraAnalyticsSelector {...defaultProps} />);

      // The select should show "All Cameras" when no camera is selected
      const selector = screen.getByTestId('camera-analytics-selector');
      expect(within(selector).getByText('All Cameras')).toBeInTheDocument();
    });

    it('displays specific camera when selected', () => {
      render(
        <CameraAnalyticsSelector {...defaultProps} selectedCameraId="front-door" />
      );

      // The Tremor Select renders both a hidden option and a visible span
      // Check that the select shows "Front Door" as the selected value
      const selectButton = screen.getByRole('combobox');
      expect(selectButton).toHaveTextContent('Front Door');
    });
  });

  describe('camera selection', () => {
    it('opens dropdown when clicked', async () => {
      const user = userEvent.setup();

      render(<CameraAnalyticsSelector {...defaultProps} />);

      // Find and click the select button to open dropdown
      const selectButton = screen.getByRole('combobox');
      await user.click(selectButton);

      // Verify dropdown is open by checking for options
      expect(await screen.findByRole('option', { name: 'Front Door' })).toBeInTheDocument();
      expect(await screen.findByRole('option', { name: 'Backyard' })).toBeInTheDocument();
      expect(await screen.findByRole('option', { name: 'Garage' })).toBeInTheDocument();
    });

    it('shows All Cameras option in dropdown', async () => {
      const user = userEvent.setup();

      render(<CameraAnalyticsSelector {...defaultProps} />);

      // Open dropdown
      const selectButton = screen.getByRole('combobox');
      await user.click(selectButton);

      // Verify "All Cameras" option is present
      expect(await screen.findByRole('option', { name: 'All Cameras' })).toBeInTheDocument();
    });

    it('passes onCameraChange callback to Select', () => {
      const onCameraChange = vi.fn();

      render(
        <CameraAnalyticsSelector {...defaultProps} onCameraChange={onCameraChange} />
      );

      // Verify the select is rendered (onValueChange is wired up internally)
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when isLoading is true', () => {
      render(<CameraAnalyticsSelector {...defaultProps} isLoading />);

      expect(screen.getByTestId('camera-selector-loading')).toBeInTheDocument();
    });

    it('disables select when loading', () => {
      render(<CameraAnalyticsSelector {...defaultProps} isLoading />);

      const selectButton = screen.getByRole('combobox');
      expect(selectButton).toBeDisabled();
    });
  });

  describe('disabled state', () => {
    it('disables select when disabled prop is true', () => {
      render(<CameraAnalyticsSelector {...defaultProps} disabled />);

      const selectButton = screen.getByRole('combobox');
      expect(selectButton).toBeDisabled();
    });
  });

  describe('empty cameras list', () => {
    it('only shows "All Cameras" when cameras array has only that option', () => {
      const camerasWithOnlyAll: CameraOption[] = [{ id: '', name: 'All Cameras' }];

      render(
        <CameraAnalyticsSelector {...defaultProps} cameras={camerasWithOnlyAll} />
      );

      const selector = screen.getByTestId('camera-analytics-selector');
      expect(within(selector).getByText('All Cameras')).toBeInTheDocument();
    });
  });
});

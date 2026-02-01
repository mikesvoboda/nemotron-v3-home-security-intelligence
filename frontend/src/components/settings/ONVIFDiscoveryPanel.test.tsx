/**
 * ONVIFDiscoveryPanel Test Suite (NEM-4754 Phase 3: ONVIF Discovery UI)
 *
 * Tests cover:
 * - Component rendering
 * - Subnet input validation
 * - Timeout slider functionality
 * - Scan button behavior
 * - Device list display
 * - Device selection callback
 * - Loading and error states
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ONVIFDiscoveryPanel from './ONVIFDiscoveryPanel';
import { server } from '../../mocks/server';

import type { OnvifDevice, OnvifDiscoveryResponse } from '../../types/onvif';
import type { ReactNode } from 'react';

// Test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const Wrapper = ({ children }: { children: ReactNode }) => {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };

  return Wrapper;
}

function renderComponent(
  isOpen = true,
  onClose = vi.fn(),
  onDeviceSelect = vi.fn()
) {
  return render(
    <ONVIFDiscoveryPanel
      isOpen={isOpen}
      onClose={onClose}
      onDeviceSelect={onDeviceSelect}
    />,
    { wrapper: createWrapper() }
  );
}

const mockDevices: OnvifDevice[] = [
  {
    device_url: 'http://192.168.1.100/onvif/device_service',
    ip: '192.168.1.100',
    port: 80,
    manufacturer: 'Hikvision',
    model: 'DS-2CD2032-I',
    firmware_version: '5.4.5',
    serial_number: 'SN001234567890',
    hardware_id: 'HW-001',
    rtsp_urls: [
      { profile: 'mainStream', url: 'rtsp://192.168.1.100:554/stream1' },
      { profile: 'subStream', url: 'rtsp://192.168.1.100:554/stream2' },
    ],
    capabilities: {
      video: true,
      ptz: true,
      events: true,
    },
  },
  {
    device_url: 'http://192.168.1.101/onvif/device_service',
    ip: '192.168.1.101',
    port: 80,
    manufacturer: 'Dahua',
    model: 'IPC-HDW2431T',
    firmware_version: null,
    serial_number: null,
    hardware_id: null,
    rtsp_urls: [],
    capabilities: {
      video: true,
      ptz: false,
      events: false,
    },
  },
];

describe('ONVIFDiscoveryPanel', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  describe('Rendering', () => {
    it('should render when open', () => {
      renderComponent();

      expect(screen.getByText('Discover ONVIF Cameras')).toBeInTheDocument();
      expect(screen.getByTestId('onvif-subnet-input')).toBeInTheDocument();
      expect(screen.getByTestId('onvif-timeout-slider')).toBeInTheDocument();
      expect(screen.getByTestId('onvif-scan-button')).toBeInTheDocument();
    });

    it('should not render when closed', () => {
      renderComponent(false);

      expect(screen.queryByText('Discover ONVIF Cameras')).not.toBeInTheDocument();
    });

    it('should have default subnet value', () => {
      renderComponent();

      const subnetInput = screen.getByTestId('onvif-subnet-input');
      expect(subnetInput).toHaveValue('192.168.1.0/24');
    });

    it('should have default timeout value', () => {
      renderComponent();

      const timeoutSlider = screen.getByTestId('onvif-timeout-slider');
      expect(timeoutSlider).toHaveValue('10');
      expect(screen.getByText('Timeout: 10s')).toBeInTheDocument();
    });
  });

  describe('Subnet Validation', () => {
    it('should accept valid CIDR notation', async () => {
      const user = userEvent.setup();
      renderComponent();

      const subnetInput = screen.getByTestId('onvif-subnet-input');
      await user.clear(subnetInput);
      await user.type(subnetInput, '10.0.0.0/16');

      expect(screen.queryByText(/invalid subnet/i)).not.toBeInTheDocument();
    });

    it('should show error for invalid subnet format', async () => {
      const user = userEvent.setup();
      renderComponent();

      const subnetInput = screen.getByTestId('onvif-subnet-input');
      await user.clear(subnetInput);
      await user.type(subnetInput, 'invalid-subnet');

      expect(screen.getByText(/invalid subnet format/i)).toBeInTheDocument();
    });

    it('should show error for invalid IP octets', async () => {
      const user = userEvent.setup();
      renderComponent();

      const subnetInput = screen.getByTestId('onvif-subnet-input');
      await user.clear(subnetInput);
      await user.type(subnetInput, '256.168.1.0/24');

      expect(screen.getByText(/invalid subnet format/i)).toBeInTheDocument();
    });

    it('should show error for invalid prefix length', async () => {
      const user = userEvent.setup();
      renderComponent();

      const subnetInput = screen.getByTestId('onvif-subnet-input');
      await user.clear(subnetInput);
      await user.type(subnetInput, '192.168.1.0/33');

      expect(screen.getByText(/invalid subnet format/i)).toBeInTheDocument();
    });
  });

  describe('Timeout Slider', () => {
    it('should update timeout value when slider changes', () => {
      renderComponent();

      const timeoutSlider = screen.getByTestId('onvif-timeout-slider');

      fireEvent.change(timeoutSlider, { target: { value: '30' } });

      expect(screen.getByText('Timeout: 30s')).toBeInTheDocument();
    });
  });

  describe('Scan Functionality', () => {
    it('should trigger discovery when scan button clicked', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: mockDevices,
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const user = userEvent.setup();
      renderComponent();

      const scanButton = screen.getByTestId('onvif-scan-button');
      await user.click(scanButton);

      await waitFor(() => {
        expect(screen.getByTestId('onvif-results')).toBeInTheDocument();
      });

      expect(screen.getByText('2 found')).toBeInTheDocument();
    });

    it('should show loading state during discovery', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({ devices: [], count: 0 });
        })
      );

      const user = userEvent.setup();
      renderComponent();

      const scanButton = screen.getByTestId('onvif-scan-button');
      await user.click(scanButton);

      expect(screen.getByText('Scanning Network...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Scanning Network...')).not.toBeInTheDocument();
      });
    });

    it('should disable scan button during discovery', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({ devices: [], count: 0 });
        })
      );

      const user = userEvent.setup();
      renderComponent();

      const scanButton = screen.getByTestId('onvif-scan-button');
      await user.click(scanButton);

      expect(scanButton).toBeDisabled();

      await waitFor(() => {
        expect(scanButton).not.toBeDisabled();
      });
    });
  });

  describe('Device List', () => {
    it('should display discovered devices', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: mockDevices,
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByTestId('onvif-device-192.168.1.100')).toBeInTheDocument();
        expect(screen.getByTestId('onvif-device-192.168.1.101')).toBeInTheDocument();
      });

      // Check device details are displayed
      expect(screen.getByText('Hikvision')).toBeInTheDocument();
      expect(screen.getByText('DS-2CD2032-I')).toBeInTheDocument();
      expect(screen.getByText('Dahua')).toBeInTheDocument();
      expect(screen.getByText('IPC-HDW2431T')).toBeInTheDocument();
    });

    it('should display RTSP URL count for devices with streams', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: mockDevices,
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByText('2 streams available')).toBeInTheDocument();
      });
    });

    it('should show empty state when no devices found', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json({ devices: [], count: 0 });
        })
      );

      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByText('No ONVIF cameras found on this network.')).toBeInTheDocument();
      });
    });
  });

  describe('Device Selection', () => {
    it('should call onDeviceSelect when device is clicked', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: mockDevices,
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const onDeviceSelect = vi.fn();
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <ONVIFDiscoveryPanel
          isOpen={true}
          onClose={onClose}
          onDeviceSelect={onDeviceSelect}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByTestId('onvif-device-192.168.1.100')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('onvif-device-192.168.1.100'));

      expect(onDeviceSelect).toHaveBeenCalledWith(mockDevices[0]);
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('should display error message on discovery failure', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(
            { detail: 'WSDiscovery library not installed' },
            { status: 500 }
          );
        })
      );

      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByTestId('onvif-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Discovery Failed')).toBeInTheDocument();
      expect(screen.getByText('WSDiscovery library not installed')).toBeInTheDocument();
    });
  });

  describe('Modal Close', () => {
    it('should call onClose when cancel button clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <ONVIFDiscoveryPanel
          isOpen={true}
          onClose={onClose}
          onDeviceSelect={vi.fn()}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText('Cancel'));

      expect(onClose).toHaveBeenCalled();
    });

    it('should call onClose when X button clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <ONVIFDiscoveryPanel
          isOpen={true}
          onClose={onClose}
          onDeviceSelect={vi.fn()}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByLabelText('Close modal'));

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Capability Badges', () => {
    it('should display capability badges correctly', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: mockDevices,
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByTestId('onvif-scan-button'));

      await waitFor(() => {
        expect(screen.getByTestId('onvif-device-192.168.1.100')).toBeInTheDocument();
      });

      // First device has all capabilities
      // Second device only has video
      const badges = screen.getAllByText('Video');
      expect(badges.length).toBe(2);

      const ptzBadges = screen.getAllByText('PTZ');
      expect(ptzBadges.length).toBe(2);
    });
  });
});

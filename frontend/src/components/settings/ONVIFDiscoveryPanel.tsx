/**
 * ONVIFDiscoveryPanel Component (NEM-4754 Phase 3: ONVIF Discovery UI)
 *
 * A modal panel for discovering ONVIF cameras on the local network.
 * Features:
 * - Subnet input with CIDR notation validation
 * - Configurable discovery timeout slider
 * - Device list showing IP, manufacturer, model, and capabilities
 * - Click-to-select device for auto-filling camera configuration
 * - Loading and error states
 */

import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Camera,
  Check,
  Loader2,
  Network,
  Search,
  Video,
  X,
} from 'lucide-react';
import { Fragment, useState } from 'react';

import { useOnvifDiscovery } from '../../hooks/useOnvifDiscovery';

import type { OnvifDevice } from '../../types/onvif';

export interface ONVIFDiscoveryPanelProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when the modal should close */
  onClose: () => void;
  /** Callback when a device is selected */
  onDeviceSelect: (device: OnvifDevice) => void;
}

/**
 * Validates a subnet in CIDR notation
 */
function isValidSubnet(subnet: string): boolean {
  // Match IPv4 CIDR notation: x.x.x.x/prefix
  const cidrPattern = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/;
  const match = subnet.match(cidrPattern);

  if (!match) return false;

  // Validate each octet is 0-255
  for (let i = 1; i <= 4; i++) {
    const octet = parseInt(match[i], 10);
    if (octet < 0 || octet > 255) return false;
  }

  // Validate prefix is 0-32
  const prefix = parseInt(match[5], 10);
  if (prefix < 0 || prefix > 32) return false;

  return true;
}

export default function ONVIFDiscoveryPanel({
  isOpen,
  onClose,
  onDeviceSelect,
}: ONVIFDiscoveryPanelProps) {
  const [subnet, setSubnet] = useState('192.168.1.0/24');
  const [timeout, setTimeout] = useState(10);
  const [subnetError, setSubnetError] = useState<string | null>(null);

  const { discoverDevices } = useOnvifDiscovery();

  const handleSubnetChange = (value: string) => {
    setSubnet(value);
    if (value && !isValidSubnet(value)) {
      setSubnetError('Invalid subnet format. Use CIDR notation (e.g., 192.168.1.0/24)');
    } else {
      setSubnetError(null);
    }
  };

  const handleScan = () => {
    if (!isValidSubnet(subnet)) {
      setSubnetError('Invalid subnet format. Use CIDR notation (e.g., 192.168.1.0/24)');
      return;
    }
    setSubnetError(null);
    discoverDevices.mutate({ subnet, timeout });
  };

  const handleDeviceClick = (device: OnvifDevice) => {
    onDeviceSelect(device);
    onClose();
  };

  const handleClose = () => {
    discoverDevices.reset();
    setSubnetError(null);
    onClose();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-lg border border-gray-800 bg-panel shadow-dark-xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-gray-800 p-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-primary/20 p-2">
                      <Network className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <Dialog.Title className="text-lg font-semibold text-text-primary">
                        Discover ONVIF Cameras
                      </Dialog.Title>
                      <p className="text-sm text-text-secondary">
                        Scan your network for ONVIF-compatible cameras
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleClose}
                    className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                    aria-label="Close modal"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Content */}
                <div className="p-4 space-y-4">
                  {/* Subnet and Timeout Inputs */}
                  <div className="flex flex-col gap-4 sm:flex-row">
                    {/* Subnet Input */}
                    <div className="flex-1">
                      <label
                        htmlFor="onvif-subnet"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Network Subnet
                      </label>
                      <input
                        type="text"
                        id="onvif-subnet"
                        data-testid="onvif-subnet-input"
                        value={subnet}
                        onChange={(e) => handleSubnetChange(e.target.value)}
                        placeholder="192.168.1.0/24"
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 font-mono text-sm text-text-primary focus:outline-none focus:ring-2',
                          subnetError
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                      />
                      {subnetError && (
                        <p className="mt-1 text-sm text-red-500">{subnetError}</p>
                      )}
                    </div>

                    {/* Timeout Slider */}
                    <div className="w-full sm:w-48">
                      <label
                        htmlFor="onvif-timeout"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Timeout: {timeout}s
                      </label>
                      <input
                        type="range"
                        id="onvif-timeout"
                        data-testid="onvif-timeout-slider"
                        min={5}
                        max={60}
                        step={5}
                        value={timeout}
                        onChange={(e) => setTimeout(parseInt(e.target.value, 10))}
                        className="mt-3 w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                      <div className="flex justify-between text-xs text-text-secondary mt-1">
                        <span>5s</span>
                        <span>60s</span>
                      </div>
                    </div>
                  </div>

                  {/* Scan Button */}
                  <button
                    onClick={handleScan}
                    disabled={discoverDevices.isPending || !subnet}
                    data-testid="onvif-scan-button"
                    className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {discoverDevices.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Scanning Network...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4" />
                        Scan Network
                      </>
                    )}
                  </button>

                  {/* Error State */}
                  {discoverDevices.isError && (
                    <div
                      data-testid="onvif-error"
                      className="rounded-lg border border-red-500/20 bg-red-500/10 p-4"
                      role="alert"
                    >
                      <div className="flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
                        <div>
                          <p className="font-medium text-red-500">Discovery Failed</p>
                          <p className="mt-1 text-sm text-red-400">
                            {discoverDevices.error?.message ?? 'An error occurred during discovery'}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Results Section */}
                  {discoverDevices.data && (
                    <div data-testid="onvif-results" className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium text-text-primary">
                          Discovered Devices
                        </h3>
                        <span className="text-sm text-text-secondary">
                          {discoverDevices.data.count} found
                        </span>
                      </div>

                      {discoverDevices.data.devices.length === 0 ? (
                        <div className="rounded-lg border border-gray-800 bg-card p-6 text-center">
                          <Camera className="mx-auto h-10 w-10 text-gray-600" />
                          <p className="mt-3 text-sm text-text-secondary">
                            No ONVIF cameras found on this network.
                          </p>
                          <p className="mt-1 text-xs text-text-secondary">
                            Try a different subnet or increase the timeout.
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-80 overflow-y-auto">
                          {discoverDevices.data.devices.map((device, index) => (
                            <DeviceCard
                              key={`${device.ip}-${index}`}
                              device={device}
                              onClick={() => handleDeviceClick(device)}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-3 border-t border-gray-800 p-4">
                  <button
                    type="button"
                    onClick={handleClose}
                    className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700"
                  >
                    Cancel
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

interface DeviceCardProps {
  device: OnvifDevice;
  onClick: () => void;
}

function DeviceCard({ device, onClick }: DeviceCardProps) {
  const hasRtspUrls = device.rtsp_urls.length > 0;

  return (
    <button
      onClick={onClick}
      data-testid={`onvif-device-${device.ip}`}
      className="w-full rounded-lg border border-gray-800 bg-card p-4 text-left transition-all hover:border-primary/50 hover:bg-[#76B900]/5 focus:outline-none focus:ring-2 focus:ring-primary"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-text-primary">{device.manufacturer}</span>
            <span className="text-text-secondary">{device.model}</span>
          </div>
          <div className="mt-1 text-sm text-text-secondary">
            <span className="font-mono">{device.ip}:{device.port}</span>
          </div>
          {hasRtspUrls && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-green-500">
              <Video className="h-3.5 w-3.5" />
              <span>{device.rtsp_urls.length} stream{device.rtsp_urls.length > 1 ? 's' : ''} available</span>
            </div>
          )}
        </div>

        {/* Capabilities */}
        <div className="flex items-center gap-2">
          <CapabilityBadge label="Video" enabled={device.capabilities.video} />
          <CapabilityBadge label="PTZ" enabled={device.capabilities.ptz} />
          <CapabilityBadge label="Events" enabled={device.capabilities.events} />
        </div>
      </div>

      {/* RTSP URLs Preview */}
      {hasRtspUrls && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <p className="text-xs text-text-secondary mb-1.5">RTSP Streams:</p>
          <div className="space-y-1">
            {device.rtsp_urls.slice(0, 2).map((rtsp, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs">
                <span className="text-text-secondary">{rtsp.profile}:</span>
                <span className="font-mono text-text-primary truncate">{rtsp.url}</span>
              </div>
            ))}
            {device.rtsp_urls.length > 2 && (
              <p className="text-xs text-text-secondary">
                +{device.rtsp_urls.length - 2} more streams
              </p>
            )}
          </div>
        </div>
      )}
    </button>
  );
}

interface CapabilityBadgeProps {
  label: string;
  enabled: boolean;
}

function CapabilityBadge({ label, enabled }: CapabilityBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs',
        enabled
          ? 'bg-green-500/20 text-green-400'
          : 'bg-gray-800 text-gray-500'
      )}
    >
      {enabled ? (
        <Check className="h-3 w-3" />
      ) : (
        <X className="h-3 w-3" />
      )}
      {label}
    </span>
  );
}

import { AlertTriangle, CheckCircle, HardDrive, Menu, Search, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { PageDocsLink } from './PageDocsLink';
import { useCommandPaletteContext } from '../../hooks/useCommandPaletteContext';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { useHealthStatusQuery } from '../../hooks/useHealthStatusQuery';
import { useSceneChangeAlerts } from '../../hooks/useSceneChangeAlerts';
import { useSidebarContext } from '../../hooks/useSidebarContext';
import {
  useStorageWarningStatus,
  useStorageStatus,
  CRITICAL_USAGE_THRESHOLD,
} from '../../stores/storage-status-store';
import { ThemeToggle, WebSocketStatus } from '../common';
import IconButton from '../common/IconButton';
import SceneChangeAlert from '../common/SceneChangeAlert';
import { AIServiceStatus } from '../status/AIServiceStatus';

/**
 * Get the dot color class based on health status
 */
function getHealthDotColor(status: 'healthy' | 'degraded' | 'unhealthy' | null): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500';
    case 'degraded':
      return 'bg-yellow-500';
    case 'unhealthy':
    default:
      return 'bg-red-500';
  }
}

/**
 * Get the status icon based on health status (accessibility improvement)
 */
function HealthStatusIcon({ status }: { status: 'healthy' | 'degraded' | 'unhealthy' | null }) {
  switch (status) {
    case 'healthy':
      return (
        <>
          <CheckCircle className="h-4 w-4 text-green-500" aria-hidden="true" />
          <span className="sr-only">System healthy</span>
        </>
      );
    case 'degraded':
      return (
        <>
          <AlertTriangle className="h-4 w-4 text-yellow-500" aria-hidden="true" />
          <span className="sr-only">System degraded</span>
        </>
      );
    case 'unhealthy':
    default:
      return (
        <>
          <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />
          <span className="sr-only">System unhealthy</span>
        </>
      );
  }
}

/**
 * Get the status label based on health status
 */
function getStatusLabel(
  isConnected: boolean,
  wsHealth: 'healthy' | 'degraded' | 'unhealthy' | undefined,
  apiHealth: 'healthy' | 'degraded' | 'unhealthy' | null
): string {
  if (!isConnected) {
    return 'Connecting...';
  }

  // Use API health if available, fall back to WebSocket health
  const effectiveStatus = apiHealth ?? wsHealth;

  switch (effectiveStatus) {
    case 'healthy':
      return 'LIVE MONITORING';
    case 'degraded':
      return 'System Degraded';
    case 'unhealthy':
      return 'System Offline';
    default:
      return 'Checking...';
  }
}

interface HealthTooltipProps {
  services: Record<string, { status: string; message?: string | null }>;
  isVisible: boolean;
}

/**
 * Get service status icon for tooltip (accessibility improvement)
 */
function ServiceStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-3 w-3 text-green-500" aria-hidden="true" />;
    case 'degraded':
      return <AlertTriangle className="h-3 w-3 text-yellow-500" aria-hidden="true" />;
    default:
      return <XCircle className="h-3 w-3 text-red-500" aria-hidden="true" />;
  }
}

function HealthTooltip({ services, isVisible }: HealthTooltipProps) {
  if (!isVisible || Object.keys(services).length === 0) {
    return null;
  }

  return (
    <div
      className="absolute left-0 top-full z-50 mt-2 min-w-[200px] rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-lg"
      role="tooltip"
      data-testid="health-tooltip"
    >
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Service Status
      </div>
      <div className="space-y-2">
        {Object.entries(services).map(([name, service]) => (
          <div key={name} className="flex items-center justify-between gap-4">
            <span className="text-sm capitalize text-text-secondary">{name}</span>
            <div className="flex items-center gap-2">
              {/* Status Icon (accessibility improvement - not color-only) */}
              <ServiceStatusIcon status={service.status} />
              <div
                className={`h-2 w-2 rounded-full ${
                  service.status === 'healthy'
                    ? 'bg-green-500'
                    : service.status === 'degraded'
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                }`}
                data-testid={`service-dot-${name}`}
                aria-hidden="true"
              />
              <span
                className={`text-xs font-medium ${
                  service.status === 'healthy'
                    ? 'text-green-400'
                    : service.status === 'degraded'
                      ? 'text-yellow-400'
                      : 'text-red-400'
                }`}
              >
                {service.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Header() {
  const { toggleMobileMenu } = useSidebarContext();
  const { openCommandPalette } = useCommandPaletteContext();
  const { summary, systemStatus, isPollingFallback, retryConnection } = useConnectionStatus();
  const {
    overallStatus: apiHealth,
    services,
    isLoading: healthLoading,
  } = useHealthStatusQuery({
    refetchInterval: 30000, // Poll every 30 seconds
  });
  // Use shallow hooks for optimized re-renders (NEM-3790)
  const { isCritical: isStorageCritical } = useStorageWarningStatus();
  const storageStatus = useStorageStatus();
  const {
    alerts: sceneChangeAlerts,
    unacknowledgedCount: sceneChangeUnacknowledgedCount,
    hasAlerts: hasSceneChangeAlerts,
    dismissAlert: dismissSceneChangeAlert,
    dismissAll: dismissAllSceneChangeAlerts,
  } = useSceneChangeAlerts();

  // Derive status and isConnected from the connection status summary
  const isConnected = summary.allConnected;
  const status = systemStatus
    ? {
        health: systemStatus.data.health,
        gpu_utilization: systemStatus.data.gpu.utilization,
        gpu_temperature: systemStatus.data.gpu.temperature,
        gpu_memory_used: systemStatus.data.gpu.memory_used,
        gpu_memory_total: systemStatus.data.gpu.memory_total,
        inference_fps: systemStatus.data.gpu.inference_fps,
      }
    : null;
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);
  const tooltipTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (tooltipTimeoutRef.current) {
        clearTimeout(tooltipTimeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    // Clear any existing timeout
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
    }
    setIsTooltipVisible(true);
  };

  const handleMouseLeave = () => {
    // Delay hiding to allow mouse to move to tooltip
    tooltipTimeoutRef.current = setTimeout(() => {
      setIsTooltipVisible(false);
    }, 150);
  };

  // Format GPU stats for display
  const formatGpuStats = () => {
    if (!status || !isConnected) {
      return '--';
    }

    const parts = [];

    // GPU Utilization
    if (status.gpu_utilization !== null) {
      parts.push(`${Math.round(status.gpu_utilization)}%`);
    }

    // GPU Temperature
    if (status.gpu_temperature !== null) {
      parts.push(`${Math.round(status.gpu_temperature)}°C`);
    }

    // Inference FPS
    if (status.inference_fps !== null) {
      parts.push(`${status.inference_fps.toFixed(1)} FPS`);
    }

    return parts.length > 0 ? parts.join(' | ') : '--';
  };

  // Determine effective health status (API takes precedence when available)
  const effectiveHealth = apiHealth ?? (isConnected ? status?.health : null) ?? null;

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-800 bg-[#1A1A1A]">
      {/* Branding container - aligned with sidebar width and padding */}
      <div className="flex items-center gap-2 px-4 md:w-64 md:gap-4" data-testid="header-branding">
        {/* Mobile hamburger menu button */}
        <IconButton
          icon={<Menu />}
          aria-label="Open menu"
          onClick={toggleMobileMenu}
          variant="ghost"
          size="lg"
          className="md:hidden"
          data-testid="hamburger-menu"
        />

        <div className="flex flex-col">
          <img src="/images/nvidia-logo-white.svg" alt="NVIDIA" className="h-6 w-auto md:h-8" />
          <p className="whitespace-nowrap text-[9px] font-medium text-[#76B900] md:text-[10px]">
            Powered by Nemotron v3 Nano
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 md:gap-6 md:px-6">
        {/* Search / Command Palette Trigger */}
        <button
          onClick={openCommandPalette}
          className="hidden items-center gap-2 rounded-lg border border-[#333] bg-[#222] px-3 py-1.5 text-sm text-[#999] transition-colors hover:border-[#444] hover:bg-[#2a2a2a] hover:text-white sm:flex"
          aria-label="Open command palette"
          data-testid="search-trigger"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          <span className="hidden md:inline">Search...</span>
          <kbd className="ml-1 hidden rounded bg-[#333] px-1.5 py-0.5 text-xs text-[#ccc] md:inline-block">
            {navigator.platform?.includes('Mac') ? '\u2318' : 'Ctrl'}K
          </kbd>
        </button>

        {/* Contextual documentation link */}
        <PageDocsLink />

        {/* Theme Toggle (NEM-3609) */}
        <div className="hidden sm:block" data-testid="theme-toggle-container">
          <ThemeToggle showMenu size="sm" variant="ghost" />
        </div>

        {/* Scene Change Alerts */}
        <SceneChangeAlert
          alerts={sceneChangeAlerts}
          unacknowledgedCount={sceneChangeUnacknowledgedCount}
          hasAlerts={hasSceneChangeAlerts}
          onDismiss={dismissSceneChangeAlert}
          onDismissAll={dismissAllSceneChangeAlerts}
        />

        {/* AI Service Status Badge - hidden on mobile */}
        <div className="hidden sm:block" data-testid="ai-service-status">
          <AIServiceStatus compact={true} />
        </div>

        {/* System Health Indicator with Tooltip */}
        <div
          ref={containerRef}
          className="relative flex cursor-pointer items-center gap-2"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onFocus={handleMouseEnter}
          onBlur={handleMouseLeave}
          data-testid="health-indicator"
          role="button"
          tabIndex={0}
          aria-label={`System health status: ${effectiveHealth ?? 'checking'}`}
          aria-haspopup="true"
          aria-expanded={isTooltipVisible}
        >
          {/* Status Icon (accessibility improvement - not color-only) */}
          <HealthStatusIcon status={effectiveHealth} />
          <div
            className={`h-2 w-2 rounded-full ${getHealthDotColor(effectiveHealth)} ${
              effectiveHealth === 'healthy' && isConnected ? 'animate-pulse' : ''
            }`}
            data-testid="health-dot"
            aria-hidden="true"
          />
          <span className="hidden text-sm text-text-secondary sm:inline">
            {!isConnected
              ? 'Connecting...'
              : healthLoading && !apiHealth
                ? 'Checking...'
                : getStatusLabel(isConnected, status?.health, apiHealth)}
          </span>
          <HealthTooltip services={services} isVisible={isTooltipVisible} />
        </div>

        {/* WebSocket Connection Status - hidden on very small screens */}
        <div className="hidden sm:block">
          <WebSocketStatus
            eventsChannel={summary.eventsChannel}
            systemChannel={summary.systemChannel}
            onRetry={retryConnection}
            isPollingFallback={isPollingFallback}
          />
        </div>

        {/* Polling fallback indicator - hidden on mobile */}
        {isPollingFallback && (
          <div className="hidden items-center gap-1 rounded bg-yellow-900/30 px-2 py-1 md:flex">
            <span className="text-xs text-yellow-400">REST Fallback</span>
          </div>
        )}

        {/* Storage Warning - shown when disk usage is critical (>= 90%) */}
        {isStorageCritical && storageStatus && (
          <div
            className="hidden items-center gap-1.5 rounded bg-red-900/30 px-2 py-1 md:flex"
            data-testid="storage-warning"
            title={`Disk usage: ${storageStatus.usagePercent.toFixed(1)}% (${CRITICAL_USAGE_THRESHOLD}% threshold)`}
          >
            <HardDrive className="h-3 w-3 text-red-400" aria-hidden="true" />
            <span className="text-xs font-medium text-red-400">
              Disk {storageStatus.usagePercent.toFixed(0)}%
            </span>
          </div>
        )}

        {/* GPU Quick Stats - hidden on mobile */}
        <div className="hidden items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 md:flex">
          <div className="text-xs text-text-secondary">GPU:</div>
          <div className="text-xs font-semibold text-[#76B900]">{formatGpuStats()}</div>
        </div>
      </div>
    </header>
  );
}

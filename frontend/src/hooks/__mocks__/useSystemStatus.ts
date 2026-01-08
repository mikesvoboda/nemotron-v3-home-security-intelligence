/**
 * Centralized mock for useSystemStatus hook.
 */

import { vi } from 'vitest';

import type { SystemStatus, UseSystemStatusReturn } from '../useSystemStatus';

const defaultSystemStatus: SystemStatus = {
  health: 'healthy',
  gpu_utilization: 45,
  gpu_temperature: 65,
  gpu_memory_used: 8192,
  gpu_memory_total: 24576,
  inference_fps: 30,
  active_cameras: 3,
  last_update: new Date().toISOString(),
};

let mockStatus: SystemStatus | null = { ...defaultSystemStatus };
let mockIsConnected: boolean = true;

export function setMockSystemStatus(status: Partial<SystemStatus> | null): void {
  if (status === null) {
    mockStatus = null;
  } else {
    mockStatus = { ...defaultSystemStatus, ...status };
  }
}

export function setMockConnectionState(isConnected: boolean): void {
  mockIsConnected = isConnected;
}

export function getMockStatus(): SystemStatus | null {
  return mockStatus ? { ...mockStatus } : null;
}

export function resetMocks(): void {
  mockStatus = { ...defaultSystemStatus };
  mockIsConnected = true;
}

export function createMockStatusWithHealth(
  health: 'healthy' | 'degraded' | 'unhealthy',
  overrides: Partial<SystemStatus> = {}
): SystemStatus {
  const baseStatus: Partial<SystemStatus> = {
    healthy: { gpu_utilization: 45, gpu_temperature: 65 },
    degraded: { gpu_utilization: 85, gpu_temperature: 80 },
    unhealthy: { gpu_utilization: 98, gpu_temperature: 90 },
  }[health];

  return {
    ...defaultSystemStatus,
    health,
    ...baseStatus,
    ...overrides,
  };
}

export function createHighLoadStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    ...defaultSystemStatus,
    health: 'degraded',
    gpu_utilization: 95,
    gpu_temperature: 85,
    gpu_memory_used: 22000,
    ...overrides,
  };
}

export function createNoGpuStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    ...defaultSystemStatus,
    gpu_utilization: null,
    gpu_temperature: null,
    gpu_memory_used: null,
    gpu_memory_total: null,
    inference_fps: null,
    ...overrides,
  };
}

export const useSystemStatus = vi.fn((): UseSystemStatusReturn => {
  return {
    status: mockStatus,
    isConnected: mockIsConnected,
  };
});

export type { SystemStatus };

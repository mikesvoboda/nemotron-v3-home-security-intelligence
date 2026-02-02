/**
 * MQTT Configuration React Hooks
 *
 * Provides TanStack Query hooks for managing MQTT configuration,
 * connection status, and testing.
 *
 * Related Issues:
 * - NEM-5140: [Implement] Phase 2: MQTT Configuration UI
 * - NEM-5032: Epic 3: Ecosystem Integration
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  disconnectMqtt,
  getMqttConfig,
  getMqttStatus,
  reconnectMqtt,
  testMqttConnection,
  updateMqttConfig,
} from '../services/mqttConfigApi';

import type {
  MqttBrokerConfig,
  MqttConfig,
  MqttConfigUpdate,
  MqttConnectionStatus,
  MqttPublisherConfig,
  MqttTestResult,
} from '../services/mqttConfigApi';

// =============================================================================
// Query Keys
// =============================================================================

export const MQTT_QUERY_KEYS = {
  all: ['mqtt'] as const,
  config: ['mqtt', 'config'] as const,
  status: ['mqtt', 'status'] as const,
  test: (host: string) => ['mqtt', 'test', host] as const,
} as const;

// =============================================================================
// Stale Times
// =============================================================================

const CONFIG_STALE_TIME = 60_000; // 1 minute
const STATUS_STALE_TIME = 10_000; // 10 seconds

// =============================================================================
// Query Hooks
// =============================================================================

export interface UseMqttConfigOptions {
  enabled?: boolean;
}

/**
 * Hook to fetch MQTT configuration.
 */
export function useMqttConfig(options?: UseMqttConfigOptions) {
  return useQuery({
    queryKey: MQTT_QUERY_KEYS.config,
    queryFn: getMqttConfig,
    staleTime: CONFIG_STALE_TIME,
    enabled: options?.enabled ?? true,
  });
}

/**
 * Hook to fetch MQTT connection status.
 */
export function useMqttStatus(options?: UseMqttConfigOptions) {
  return useQuery({
    queryKey: MQTT_QUERY_KEYS.status,
    queryFn: getMqttStatus,
    staleTime: STATUS_STALE_TIME,
    refetchInterval: STATUS_STALE_TIME,
    enabled: options?.enabled ?? true,
  });
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/**
 * Hook to update MQTT configuration.
 */
export function useUpdateMqttConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: MqttConfigUpdate) => updateMqttConfig(config),
    onSuccess: (data) => {
      queryClient.setQueryData(MQTT_QUERY_KEYS.config, data);
      void queryClient.invalidateQueries({ queryKey: MQTT_QUERY_KEYS.status });
    },
  });
}

/**
 * Hook to test MQTT connection.
 */
export function useTestMqttConnection() {
  return useMutation({
    mutationFn: (broker?: Partial<MqttBrokerConfig>) =>
      testMqttConnection(broker),
  });
}

/**
 * Hook to reconnect MQTT client.
 */
export function useReconnectMqtt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reconnectMqtt,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MQTT_QUERY_KEYS.status });
    },
  });
}

/**
 * Hook to disconnect MQTT client.
 */
export function useDisconnectMqtt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: disconnectMqtt,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MQTT_QUERY_KEYS.status });
    },
  });
}

// =============================================================================
// Types Re-export
// =============================================================================

export type {
  MqttBrokerConfig,
  MqttConfig,
  MqttConfigUpdate,
  MqttConnectionStatus,
  MqttPublisherConfig,
  MqttTestResult,
};

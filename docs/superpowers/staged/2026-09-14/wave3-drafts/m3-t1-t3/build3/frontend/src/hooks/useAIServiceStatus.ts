/**
 * Hook for tracking AI service degradation status.
 *
 * Listens to WebSocket messages of type 'ai_service_status' which are broadcast
 * by the backend's AIFallbackService when AI service health changes. Provides
 * comprehensive status for all AI services (RT-DETRv2, Nemotron, Florence-2, CLIP)
 * along with the overall degradation mode.
 *
 * The degradation modes are:
 * - normal: All services healthy
 * - degraded: Non-critical services (Florence-2, CLIP) unavailable
 * - minimal: Critical services (RT-DETRv2, Nemotron) partially available
 * - offline: All AI services unavailable
 *
 * For individual service health (restart events), use `useServiceStatus`.
 */
import { useState, useCallback, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';

/**
 * AI service identifiers matching backend AIService enum
 */
export type AIServiceName = 'rtdetr' | 'nemotron' | 'florence' | 'clip';

/**
 * Individual service health status
 */
export type AIServiceHealthStatus = 'healthy' | 'degraded' | 'unavailable';

/**
 * Circuit breaker states
 */
export type CircuitState = 'closed' | 'open' | 'half_open';

/**
 * System degradation levels based on AI service availability
 */
export type DegradationLevel = 'normal' | 'degraded' | 'minimal' | 'offline';

/**
 * State information for a single AI service
 */
export interface AIServiceState {
  service: AIServiceName;
  status: AIServiceHealthStatus;
  circuit_state: CircuitState;
  last_success: string | null;
  failure_count: number;
  error_message: string | null;
  last_check: string | null;
}

/**
 * Full AI service status message from backend
 */
export interface AIServiceStatusMessage {
  type: 'ai_service_status';
  timestamp: string;
  degradation_mode: DegradationLevel;
  services: Record<AIServiceName, AIServiceState>;
  available_features: string[];
}

export interface UseAIServiceStatusResult {
  /** Current degradation mode */
  degradationMode: DegradationLevel;
  /** Map of service name to service state */
  services: Record<AIServiceName, AIServiceState | null>;
  /** List of currently available features */
  availableFeatures: string[];
  /** Whether any service is unavailable */
  hasUnavailableService: boolean;
  /** Whether all AI services are offline */
  isOffline: boolean;
  /** Whether the system is in a degraded state */
  isDegraded: boolean;
  /** Get the state of a specific service */
  getServiceState: (name: AIServiceName) => AIServiceState | null;
  /** Check if a specific feature is available */
  isFeatureAvailable: (feature: string) => boolean;
  /** Timestamp of last status update */
  lastUpdate: string | null;
}

const AI_SERVICE_NAMES: AIServiceName[] = ['rtdetr', 'nemotron', 'florence', 'clip'];

function isAIServiceName(value: unknown): value is AIServiceName {
  return typeof value === 'string' && AI_SERVICE_NAMES.includes(value as AIServiceName);
}

function isAIServiceHealthStatus(value: unknown): value is AIServiceHealthStatus {
  return typeof value === 'string' && ['healthy', 'degraded', 'unavailable'].includes(value);
}

function isCircuitState(value: unknown): value is CircuitState {
  return typeof value === 'string' && ['closed', 'open', 'half_open'].includes(value);
}

function isDegradationLevel(value: unknown): value is DegradationLevel {
  return typeof value === 'string' && ['normal', 'degraded', 'minimal', 'offline'].includes(value);
}

function isAIServiceState(data: unknown): data is AIServiceState {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const state = data as Record<string, unknown>;

  return (
    isAIServiceName(state.service) &&
    isAIServiceHealthStatus(state.status) &&
    isCircuitState(state.circuit_state) &&
    (state.last_success === null || typeof state.last_success === 'string') &&
    typeof state.failure_count === 'number' &&
    (state.error_message === null || typeof state.error_message === 'string') &&
    (state.last_check === null || typeof state.last_check === 'string')
  );
}

function isAIServiceStatusMessage(data: unknown): data is AIServiceStatusMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  // Check message type
  if (msg.type !== 'ai_service_status') {
    return false;
  }

  // Check required fields
  if (
    typeof msg.timestamp !== 'string' ||
    !isDegradationLevel(msg.degradation_mode) ||
    !Array.isArray(msg.available_features) ||
    !msg.services ||
    typeof msg.services !== 'object'
  ) {
    return false;
  }

  // Check services object contains valid service states
  const services = msg.services as Record<string, unknown>;
  for (const serviceName of AI_SERVICE_NAMES) {
    const serviceData = services[serviceName];
    if (serviceData !== undefined && !isAIServiceState(serviceData)) {
      return false;
    }
  }

  return true;
}

function createInitialServices(): Record<AIServiceName, AIServiceState | null> {
  return {
    rtdetr: null,
    nemotron: null,
    florence: null,
    clip: null,
  };
}

/**
 * Subscribe to AI service degradation status updates from the backend.
 *
 * Returns current status for all AI services along with the overall
 * degradation mode and available features.
 *
 * @returns UseAIServiceStatusResult with services map and utility getters
 */
export function useAIServiceStatus(): UseAIServiceStatusResult {
  const [services, setServices] =
    useState<Record<AIServiceName, AIServiceState | null>>(createInitialServices);
  const [degradationMode, setDegradationMode] = useState<DegradationLevel>('normal');
  const [availableFeatures, setAvailableFeatures] = useState<string[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const handleMessage = useCallback((data: unknown) => {
    if (isAIServiceStatusMessage(data)) {
      setDegradationMode(data.degradation_mode);
      setAvailableFeatures(data.available_features);
      setLastUpdate(data.timestamp);

      // Update services map
      const newServices: Record<AIServiceName, AIServiceState | null> = {
        rtdetr: null,
        nemotron: null,
        florence: null,
        clip: null,
      };

      for (const serviceName of AI_SERVICE_NAMES) {
        const serviceData = data.services[serviceName];
        if (serviceData) {
          newServices[serviceName] = serviceData;
        }
      }

      setServices(newServices);
    }
  }, []);

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  const wsOptions = buildWebSocketOptions('/ws/events');

  useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  const hasUnavailableService = useMemo(() => {
    return AI_SERVICE_NAMES.some((name) => {
      const service = services[name];
      return service !== null && service.status === 'unavailable';
    });
  }, [services]);

  const isOffline = useMemo(() => {
    return degradationMode === 'offline';
  }, [degradationMode]);

  const isDegraded = useMemo(() => {
    return degradationMode !== 'normal';
  }, [degradationMode]);

  const getServiceState = useCallback(
    (name: AIServiceName): AIServiceState | null => {
      return services[name];
    },
    [services]
  );

  const isFeatureAvailable = useCallback(
    (feature: string): boolean => {
      return availableFeatures.includes(feature);
    },
    [availableFeatures]
  );

  return {
    degradationMode,
    services,
    availableFeatures,
    hasUnavailableService,
    isOffline,
    isDegraded,
    getServiceState,
    isFeatureAvailable,
    lastUpdate,
  };
}

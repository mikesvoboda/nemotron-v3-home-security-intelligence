/**
 * MQTT Settings Component
 *
 * Configuration UI for MQTT broker connection, publishing settings,
 * and integration options (Home Assistant, Frigate).
 *
 * Related Issues:
 * - NEM-5140: [Implement] Phase 2: MQTT Configuration UI
 * - NEM-5032: Epic 3: Ecosystem Integration
 */

import {
  AlertCircle,
  CheckCircle,
  Loader2,
  RefreshCw,
  TestTube,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  useMqttConfig,
  useMqttStatus,
  useReconnectMqtt,
  useTestMqttConnection,
  useUpdateMqttConfig,
} from '../../hooks/useMqttConfig';

import type { MqttBrokerConfig, MqttPublisherConfig } from '../../hooks/useMqttConfig';

// =============================================================================
// Types
// =============================================================================

interface FormErrors {
  broker_host?: string;
  broker_port?: string;
  topic_prefix?: string;
}

// =============================================================================
// Component
// =============================================================================

export function MqttSettings() {
  // Queries
  const { data: config, isLoading: configLoading, error: configError } = useMqttConfig();
  const { data: status } = useMqttStatus();

  // Mutations
  const updateConfig = useUpdateMqttConfig();
  const testConnection = useTestMqttConnection();
  const reconnect = useReconnectMqtt();

  // Local state
  const [brokerConfig, setBrokerConfig] = useState<MqttBrokerConfig | null>(null);
  const [publisherConfig, setPublisherConfig] = useState<MqttPublisherConfig | null>(null);
  const [haDiscoveryEnabled, setHaDiscoveryEnabled] = useState(false);
  const [frigateEnabled, setFrigateEnabled] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  // Initialize form from config
  useEffect(() => {
    if (config) {
      setBrokerConfig(config.broker);
      setPublisherConfig(config.publisher);
      setHaDiscoveryEnabled(config.ha_discovery_enabled);
      setFrigateEnabled(config.frigate_enabled);
      setHasChanges(false);
    }
  }, [config]);

  // Validation
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!brokerConfig?.broker_host?.trim()) {
      newErrors.broker_host = 'Broker host is required';
    }
    if (!brokerConfig?.broker_port || brokerConfig.broker_port < 1 || brokerConfig.broker_port > 65535) {
      newErrors.broker_port = 'Port must be between 1 and 65535';
    }
    if (!brokerConfig?.topic_prefix?.trim()) {
      newErrors.topic_prefix = 'Topic prefix is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handlers
  const handleBrokerChange = (field: keyof MqttBrokerConfig, value: string | number | boolean | null) => {
    if (!brokerConfig) return;
    setBrokerConfig({ ...brokerConfig, [field]: value });
    setHasChanges(true);
  };

  const handlePublisherChange = (field: keyof MqttPublisherConfig, value: boolean | number) => {
    if (!publisherConfig) return;
    setPublisherConfig({ ...publisherConfig, [field]: value });
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!validateForm() || !brokerConfig || !publisherConfig) return;

    try {
      await updateConfig.mutateAsync({
        broker: brokerConfig,
        publisher: publisherConfig,
        ha_discovery_enabled: haDiscoveryEnabled,
        frigate_enabled: frigateEnabled,
      });
      setHasChanges(false);
    } catch {
      // Error handled by mutation
    }
  };

  const handleTest = async () => {
    if (!brokerConfig) return;
    await testConnection.mutateAsync(brokerConfig);
  };

  const handleReconnect = async () => {
    await reconnect.mutateAsync();
  };

  // Loading state
  if (configLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  // Error state
  if (configError) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <span className="text-red-400">Failed to load MQTT configuration</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Connection Status Card */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status?.connected ? (
              <Wifi className="h-5 w-5 text-green-400" />
            ) : (
              <WifiOff className="h-5 w-5 text-red-400" />
            )}
            <div>
              <div className="font-medium text-white">
                {status?.connected ? 'Connected' : 'Disconnected'}
              </div>
              {status?.broker_host && (
                <div className="text-sm text-gray-400">
                  {status.broker_host}:{status.broker_port}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={() => void handleReconnect()}
            disabled={reconnect.isPending}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {reconnect.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Reconnect
          </button>
        </div>
      </div>

      {/* Broker Settings */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h3 className="mb-4 text-lg font-medium text-white">Broker Settings</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Host */}
          <div>
            <label htmlFor="broker_host" className="mb-1 block text-sm font-medium text-gray-300">
              Broker Host *
            </label>
            <input
              id="broker_host"
              type="text"
              value={brokerConfig?.broker_host || ''}
              onChange={(e) => handleBrokerChange('broker_host', e.target.value)}
              placeholder="mqtt.example.com"
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            />
            {errors.broker_host && (
              <p className="mt-1 text-sm text-red-400">{errors.broker_host}</p>
            )}
          </div>

          {/* Port */}
          <div>
            <label htmlFor="broker_port" className="mb-1 block text-sm font-medium text-gray-300">
              Port *
            </label>
            <input
              id="broker_port"
              type="number"
              value={brokerConfig?.broker_port || 1883}
              onChange={(e) => handleBrokerChange('broker_port', parseInt(e.target.value, 10))}
              min={1}
              max={65535}
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            />
            {errors.broker_port && (
              <p className="mt-1 text-sm text-red-400">{errors.broker_port}</p>
            )}
          </div>

          {/* Username */}
          <div>
            <label htmlFor="mqtt_username" className="mb-1 block text-sm font-medium text-gray-300">
              Username
            </label>
            <input
              id="mqtt_username"
              type="text"
              value={brokerConfig?.username || ''}
              onChange={(e) => handleBrokerChange('username', e.target.value || null)}
              placeholder="Optional"
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Password */}
          <div>
            <label htmlFor="mqtt_password" className="mb-1 block text-sm font-medium text-gray-300">
              Password
            </label>
            <input
              id="mqtt_password"
              type="password"
              value={brokerConfig?.password || ''}
              onChange={(e) => handleBrokerChange('password', e.target.value || null)}
              placeholder="Optional"
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Topic Prefix */}
          <div>
            <label htmlFor="topic_prefix" className="mb-1 block text-sm font-medium text-gray-300">
              Topic Prefix *
            </label>
            <input
              id="topic_prefix"
              type="text"
              value={brokerConfig?.topic_prefix || 'hsi'}
              onChange={(e) => handleBrokerChange('topic_prefix', e.target.value)}
              placeholder="hsi"
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            />
            {errors.topic_prefix && (
              <p className="mt-1 text-sm text-red-400">{errors.topic_prefix}</p>
            )}
          </div>

          {/* QoS */}
          <div>
            <label htmlFor="qos_default" className="mb-1 block text-sm font-medium text-gray-300">
              Default QoS
            </label>
            <select
              id="qos_default"
              value={brokerConfig?.qos_default || 1}
              onChange={(e) => handleBrokerChange('qos_default', parseInt(e.target.value, 10))}
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            >
              <option value={0}>0 - At most once</option>
              <option value={1}>1 - At least once</option>
              <option value={2}>2 - Exactly once</option>
            </select>
          </div>

          {/* TLS */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="use_tls"
              checked={brokerConfig?.use_tls || false}
              onChange={(e) => handleBrokerChange('use_tls', e.target.checked)}
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="use_tls" className="text-sm font-medium text-gray-300">
              Use TLS/SSL
            </label>
          </div>
        </div>

        {/* Test Connection Button */}
        <div className="mt-4">
          <button
            onClick={() => void handleTest()}
            disabled={testConnection.isPending}
            className="flex items-center gap-2 rounded-lg border border-gray-600 bg-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-600 disabled:opacity-50"
          >
            {testConnection.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <TestTube className="h-4 w-4" />
            )}
            Test Connection
          </button>
          {testConnection.data && (
            <div className="mt-2 flex items-center gap-2">
              {testConnection.data.success ? (
                <>
                  <CheckCircle className="h-4 w-4 text-green-400" />
                  <span className="text-sm text-green-400">
                    Connected ({testConnection.data.latency_ms}ms)
                  </span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-4 w-4 text-red-400" />
                  <span className="text-sm text-red-400">
                    {testConnection.data.error || 'Connection failed'}
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Publishing Settings */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h3 className="mb-4 text-lg font-medium text-white">Publishing Settings</h3>
        <div className="space-y-4">
          {/* Publisher Enabled */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="publisher_enabled"
              checked={publisherConfig?.enabled || false}
              onChange={(e) => handlePublisherChange('enabled', e.target.checked)}
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="publisher_enabled" className="text-sm font-medium text-gray-300">
              Enable MQTT Publishing
            </label>
          </div>

          {/* Retain Status */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="retain_status"
              checked={publisherConfig?.retain_status || false}
              onChange={(e) => handlePublisherChange('retain_status', e.target.checked)}
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="retain_status" className="text-sm font-medium text-gray-300">
              Retain status messages (recommended for Home Assistant)
            </label>
          </div>
        </div>
      </div>

      {/* Integrations */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h3 className="mb-4 text-lg font-medium text-white">Integrations</h3>
        <div className="space-y-4">
          {/* Home Assistant */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="ha_discovery"
              checked={haDiscoveryEnabled}
              onChange={(e) => {
                setHaDiscoveryEnabled(e.target.checked);
                setHasChanges(true);
              }}
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="ha_discovery" className="text-sm font-medium text-gray-300">
              Home Assistant MQTT Discovery
            </label>
          </div>
          <p className="ml-6 text-sm text-gray-500">
            Auto-configure devices and entities in Home Assistant
          </p>

          {/* Frigate */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="frigate_enabled"
              checked={frigateEnabled}
              onChange={(e) => {
                setFrigateEnabled(e.target.checked);
                setHasChanges(true);
              }}
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="frigate_enabled" className="text-sm font-medium text-gray-300">
              Frigate NVR Integration
            </label>
          </div>
          <p className="ml-6 text-sm text-gray-500">
            Receive detection events from Frigate via MQTT
          </p>
        </div>
      </div>

      {/* Save Button */}
      {hasChanges && (
        <div className="flex justify-end">
          <button
            onClick={() => void handleSave()}
            disabled={updateConfig.isPending}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {updateConfig.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Save Changes
          </button>
        </div>
      )}

      {/* Error Display */}
      {updateConfig.error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <span className="text-red-400">
              {updateConfig.error instanceof Error
                ? updateConfig.error.message
                : 'Failed to save configuration'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default MqttSettings;

/**
 * AdminSettings - Admin tab for Settings page
 *
 * Provides administrative controls organized into 4 collapsible sections:
 * 1. Feature Toggles - Enable/disable system features
 * 2. System Config - Rate limiting and queue settings
 * 3. Maintenance Actions - Orphan cleanup, cache clear, flush queues
 * 4. Developer Tools - Test data seeding (debug mode only)
 *
 * @see NEM-3114 - Phase 1.1: Create AdminSettings.tsx component structure
 * @see NEM-3115 - Phase 1.2: Implement Feature Toggles UI
 * @see NEM-3116 - Phase 1.3: Implement System Config UI
 */

import { Switch } from '@headlessui/react';
import { Card, Title, Text, Button, Badge, Callout, NumberInput } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Database,
  Eye,
  Fingerprint,
  Image,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Settings,
  Sparkles,
  ToggleLeft,
  Trash2,
  Video,
  Wrench,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { useDebugMode } from '../../contexts/DebugModeContext';
import {
  useAdminMutations,
  type SeedCamerasRequest,
  type SeedEventsRequest,
} from '../../hooks/useAdminMutations';
import { useSettingsApi } from '../../hooks/useSettingsApi';
import { useToast } from '../../hooks/useToast';
import ConfirmWithTextDialog from '../developer-tools/ConfirmWithTextDialog';
import ConfirmDialog from '../jobs/ConfirmDialog';
import CollapsibleSection from '../system/CollapsibleSection';

export interface AdminSettingsProps {
  /** Optional className for styling */
  className?: string;
}

/** Feature toggle key type matching backend settings */
export type FeatureToggleKey =
  | 'vision_extraction_enabled'
  | 'reid_enabled'
  | 'scene_change_enabled'
  | 'clip_generation_enabled'
  | 'image_quality_enabled'
  | 'background_eval_enabled';

/** Feature toggle configuration */
interface FeatureToggleConfig {
  id: FeatureToggleKey;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: 'green' | 'blue' | 'purple' | 'amber';
}

/** Feature toggle state type */
export type FeatureTogglesState = Record<FeatureToggleKey, boolean>;

/** Feature toggle configurations - static config outside component */
const FEATURE_TOGGLE_CONFIGS: FeatureToggleConfig[] = [
  {
    id: 'vision_extraction_enabled',
    name: 'Vision Extraction',
    description: 'Extract visual features from frames using AI models',
    icon: null, // Icons are rendered inline as they use JSX
    color: 'green',
  },
  {
    id: 'reid_enabled',
    name: 'Re-ID Tracking',
    description: 'Track individuals across camera views',
    icon: null,
    color: 'blue',
  },
  {
    id: 'scene_change_enabled',
    name: 'Scene Change',
    description: 'Detect significant changes in camera scenes',
    icon: null,
    color: 'purple',
  },
  {
    id: 'clip_generation_enabled',
    name: 'Clip Generation',
    description: 'Generate video clips for events',
    icon: null,
    color: 'green',
  },
  {
    id: 'image_quality_enabled',
    name: 'Image Quality',
    description: 'Assess and filter low-quality images',
    icon: null,
    color: 'blue',
  },
  {
    id: 'background_eval_enabled',
    name: 'Background Eval',
    description: 'Evaluate background consistency',
    icon: null,
    color: 'purple',
  },
];

/** Map of feature toggle icons */
const FEATURE_TOGGLE_ICONS: Record<FeatureToggleKey, React.FC<{ className?: string }>> = {
  vision_extraction_enabled: Eye,
  reid_enabled: Fingerprint,
  scene_change_enabled: RefreshCw,
  clip_generation_enabled: Video,
  image_quality_enabled: Image,
  background_eval_enabled: Sparkles,
};

/** Default feature toggle state - all enabled by default */
const DEFAULT_FEATURE_TOGGLES: FeatureTogglesState = {
  vision_extraction_enabled: true,
  reid_enabled: true,
  scene_change_enabled: true,
  clip_generation_enabled: true,
  image_quality_enabled: true,
  background_eval_enabled: true,
};

/** System config state for rate limiting and queue settings */
interface SystemConfigState {
  rateLimiting: {
    requestsPerMinute: number;
    burstSize: number;
    enabled: boolean;
  };
  queueSettings: {
    maxSize: number;
    backpressureThreshold: number;
  };
}

/** Default system config values */
const DEFAULT_SYSTEM_CONFIG: SystemConfigState = {
  rateLimiting: {
    requestsPerMinute: 60,
    burstSize: 10,
    enabled: true,
  },
  queueSettings: {
    maxSize: 10000,
    backpressureThreshold: 80,
  },
};

/**
 * AdminSettings component
 *
 * Administrative controls for system configuration, maintenance,
 * and developer tools. The Developer Tools section is only visible
 * when the backend has DEBUG=true.
 */
export default function AdminSettings({ className }: AdminSettingsProps) {
  const { debugMode } = useDebugMode();
  const toast = useToast();
  const { seedCameras, seedEvents, clearSeededData, orphanCleanup, clearCache, flushQueues } =
    useAdminMutations();

  // Settings API integration
  const { settings, isLoading: isLoadingSettings, updateMutation } = useSettingsApi();

  // Section open state (all start expanded except Developer Tools)
  const [featureTogglesOpen, setFeatureTogglesOpen] = useState(true);
  const [systemConfigOpen, setSystemConfigOpen] = useState(true);
  const [maintenanceOpen, setMaintenanceOpen] = useState(true);
  const [developerToolsOpen, setDeveloperToolsOpen] = useState(false);

  // Confirmation dialog states for maintenance
  const [confirmOrphanCleanup, setConfirmOrphanCleanup] = useState(false);
  const [confirmCacheClear, setConfirmCacheClear] = useState(false);
  const [confirmFlushQueues, setConfirmFlushQueues] = useState(false);

  // Confirmation dialog states for developer tools
  const [confirmSeedCameras, setConfirmSeedCameras] = useState(false);
  const [confirmSeedEvents, setConfirmSeedEvents] = useState(false);
  const [confirmClearTestData, setConfirmClearTestData] = useState(false);

  // Feature toggles from API - track which one is being toggled
  const [togglingFeature, setTogglingFeature] = useState<FeatureToggleKey | null>(null);

  // Local system config state for form editing (synced from API)
  const [systemConfig, setSystemConfig] = useState<SystemConfigState>(DEFAULT_SYSTEM_CONFIG);
  const [originalConfig, setOriginalConfig] = useState<SystemConfigState>(DEFAULT_SYSTEM_CONFIG);
  // Track whether we've synced from API to avoid re-syncing during mutations
  const [hasSyncedFromApi, setHasSyncedFromApi] = useState(false);

  // Sync system config from API response when settings load (only once on initial load)
  useEffect(() => {
    if (settings && !hasSyncedFromApi && !updateMutation.isPending) {
      const syncedConfig: SystemConfigState = {
        rateLimiting: {
          requestsPerMinute: settings.rate_limiting.requests_per_minute,
          burstSize: settings.rate_limiting.burst_size,
          enabled: settings.rate_limiting.enabled,
        },
        queueSettings: {
          maxSize: settings.queue.max_size,
          backpressureThreshold: Math.round(settings.queue.backpressure_threshold * 100),
        },
      };
      setSystemConfig(syncedConfig);
      setOriginalConfig(syncedConfig);
      setHasSyncedFromApi(true);
    }
  }, [settings, hasSyncedFromApi, updateMutation.isPending]);

  // Feature toggles derived from API
  const featureToggles: FeatureTogglesState = useMemo(() => {
    if (settings) {
      return {
        vision_extraction_enabled: settings.features.vision_extraction_enabled,
        reid_enabled: settings.features.reid_enabled,
        scene_change_enabled: settings.features.scene_change_enabled,
        clip_generation_enabled: settings.features.clip_generation_enabled,
        image_quality_enabled: settings.features.image_quality_enabled,
        background_eval_enabled: settings.features.background_eval_enabled,
      };
    }
    return DEFAULT_FEATURE_TOGGLES;
  }, [settings]);

  // Track if config has changed
  const hasConfigChanges = useMemo(() => {
    return (
      systemConfig.rateLimiting.requestsPerMinute !==
        originalConfig.rateLimiting.requestsPerMinute ||
      systemConfig.rateLimiting.burstSize !== originalConfig.rateLimiting.burstSize ||
      systemConfig.rateLimiting.enabled !== originalConfig.rateLimiting.enabled ||
      systemConfig.queueSettings.maxSize !== originalConfig.queueSettings.maxSize ||
      systemConfig.queueSettings.backpressureThreshold !==
        originalConfig.queueSettings.backpressureThreshold
    );
  }, [systemConfig, originalConfig]);

  // Feature toggle handler - wired to Settings API
  const handleFeatureToggle = useCallback(
    async (id: FeatureToggleKey, newValue: boolean) => {
      setTogglingFeature(id);
      try {
        // Update via Settings API
        await updateMutation.mutateAsync({
          features: { [id]: newValue },
        });

        const toggleName = FEATURE_TOGGLE_CONFIGS.find((t) => t.id === id)?.name ?? id;
        toast.success(`${toggleName} ${newValue ? 'enabled' : 'disabled'}`, {
          description: 'Feature toggle updated successfully',
        });
      } catch (error) {
        toast.error('Failed to update feature toggle', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      } finally {
        setTogglingFeature(null);
      }
    },
    [toast, updateMutation]
  );

  // System config handlers
  const handleRateLimitingChange = useCallback(
    (field: keyof SystemConfigState['rateLimiting'], value: number | boolean) => {
      setSystemConfig((prev) => ({
        ...prev,
        rateLimiting: {
          ...prev.rateLimiting,
          [field]: value,
        },
      }));
    },
    []
  );

  const handleQueueSettingsChange = useCallback(
    (field: keyof SystemConfigState['queueSettings'], value: number) => {
      setSystemConfig((prev) => ({
        ...prev,
        queueSettings: {
          ...prev.queueSettings,
          [field]: value,
        },
      }));
    },
    []
  );

  const handleSaveConfig = useCallback(async () => {
    try {
      // Update via Settings API
      await updateMutation.mutateAsync({
        rate_limiting: {
          enabled: systemConfig.rateLimiting.enabled,
          requests_per_minute: systemConfig.rateLimiting.requestsPerMinute,
          burst_size: systemConfig.rateLimiting.burstSize,
        },
        queue: {
          max_size: systemConfig.queueSettings.maxSize,
          backpressure_threshold: systemConfig.queueSettings.backpressureThreshold / 100,
        },
      });
      // Update original config to match saved state
      setOriginalConfig(systemConfig);
      toast.success('System config saved', {
        description: 'Configuration changes have been applied',
      });
    } catch (error) {
      toast.error('Failed to save config', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [toast, updateMutation, systemConfig]);

  const handleResetConfig = useCallback(() => {
    setSystemConfig(originalConfig);
  }, [originalConfig]);

  // Maintenance action handlers - wired to API
  const handleOrphanCleanup = useCallback(async () => {
    try {
      const result = await orphanCleanup.mutateAsync({ dry_run: false, min_age_hours: 24 });
      toast.success('Orphan cleanup completed', {
        description: `Removed ${result.deleted_files} orphaned files (${result.deleted_bytes_formatted})`,
      });
    } catch (error) {
      toast.error('Orphan cleanup failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmOrphanCleanup(false);
    }
  }, [toast, orphanCleanup]);

  const handleCacheClear = useCallback(async () => {
    try {
      const result = await clearCache.mutateAsync();
      toast.success('Cache cleared', {
        description: result.message,
      });
    } catch (error) {
      toast.error('Cache clear failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmCacheClear(false);
    }
  }, [toast, clearCache]);

  const handleFlushQueues = useCallback(async () => {
    try {
      const result = await flushQueues.mutateAsync();
      toast.success('Queues flushed', {
        description: result.message,
      });
    } catch (error) {
      toast.error('Queue flush failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmFlushQueues(false);
    }
  }, [toast, flushQueues]);

  // Developer tools handlers
  const handleSeedCameras = useCallback(async () => {
    try {
      const params: SeedCamerasRequest = { count: 5 };
      const result = await seedCameras.mutateAsync(params);
      toast.success(`Created ${result.created} cameras`, {
        description: result.cleared > 0 ? `Cleared ${result.cleared} existing cameras` : undefined,
      });
    } catch (error) {
      toast.error('Failed to seed cameras', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmSeedCameras(false);
    }
  }, [seedCameras, toast]);

  const handleSeedEvents = useCallback(async () => {
    try {
      const params: SeedEventsRequest = { count: 50 };
      const result = await seedEvents.mutateAsync(params);
      toast.success(`Created ${result.events_created} events`, {
        description: `With ${result.detections_created} detections`,
      });
    } catch (error) {
      toast.error('Failed to seed events', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmSeedEvents(false);
    }
  }, [seedEvents, toast]);

  const handleClearTestData = useCallback(async () => {
    try {
      const result = await clearSeededData.mutateAsync({ confirm: 'DELETE_ALL_DATA' });
      toast.success('Test data cleared', {
        description: `Deleted ${result.events_cleared} events, ${result.detections_cleared} detections, ${result.cameras_cleared} cameras`,
      });
    } catch (error) {
      toast.error('Failed to clear test data', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setConfirmClearTestData(false);
    }
  }, [clearSeededData, toast]);

  // Count enabled feature toggles
  const enabledCount = Object.values(featureToggles).filter(Boolean).length;

  return (
    <div className={`space-y-4 ${className || ''}`} data-testid="admin-settings">
      {/* Header */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
        <Title className="mb-2 flex items-center gap-2 text-white">
          <Settings className="h-5 w-5 text-[#76B900]" />
          Admin Settings
        </Title>
        <Text className="text-gray-400">
          Configure system features, maintenance actions, and developer tools.
        </Text>
      </Card>

      {/* Feature Toggles Section */}
      <CollapsibleSection
        title="Feature Toggles"
        icon={<ToggleLeft className="h-5 w-5 text-[#76B900]" />}
        isOpen={featureTogglesOpen}
        onToggle={setFeatureTogglesOpen}
        summary={`${enabledCount}/${FEATURE_TOGGLE_CONFIGS.length} enabled`}
        data-testid="admin-feature-toggles"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURE_TOGGLE_CONFIGS.map((config) => {
            const isEnabled = featureToggles[config.id];
            const isToggling = togglingFeature === config.id;
            const IconComponent = FEATURE_TOGGLE_ICONS[config.id];

            return (
              <div
                key={config.id}
                className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
                data-testid={`feature-toggle-${config.id}`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={clsx(
                      'flex h-8 w-8 items-center justify-center rounded-lg',
                      config.color === 'green' && 'bg-green-500/20 text-green-400',
                      config.color === 'blue' && 'bg-blue-500/20 text-blue-400',
                      config.color === 'purple' && 'bg-purple-500/20 text-purple-400',
                      config.color === 'amber' && 'bg-amber-500/20 text-amber-400'
                    )}
                  >
                    <IconComponent className="h-4 w-4" />
                  </div>
                  <div>
                    <Text className="font-medium text-white">{config.name}</Text>
                    <Text className="text-xs text-gray-500">{config.description}</Text>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isToggling && (
                    <Loader2
                      className="h-4 w-4 animate-spin text-gray-400"
                      data-testid={`feature-toggle-${config.id}-loading`}
                    />
                  )}
                  <Switch
                    checked={isEnabled}
                    onChange={(checked) => void handleFeatureToggle(config.id, checked)}
                    disabled={isToggling}
                    aria-label={`Toggle ${config.name} ${isEnabled ? 'off' : 'on'}`}
                    data-testid={`feature-toggle-${config.id}-switch`}
                    className={clsx(
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                      'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
                      isEnabled ? 'bg-[#76B900]' : 'bg-gray-600',
                      isToggling && 'cursor-not-allowed opacity-50'
                    )}
                  >
                    <span
                      className={clsx(
                        'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                        isEnabled ? 'translate-x-6' : 'translate-x-1'
                      )}
                    />
                  </Switch>
                </div>
              </div>
            );
          })}
        </div>
        {isLoadingSettings && (
          <div className="mt-4 flex items-center gap-2 text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading settings...</span>
          </div>
        )}
      </CollapsibleSection>

      {/* System Config Section */}
      <CollapsibleSection
        title="System Config"
        icon={<Zap className="h-5 w-5 text-blue-400" />}
        isOpen={systemConfigOpen}
        onToggle={setSystemConfigOpen}
        summary={hasConfigChanges ? 'unsaved changes' : undefined}
        data-testid="admin-system-config"
      >
        <div className="space-y-6">
          {/* Rate Limiting */}
          <div data-testid="rate-limiting-section">
            <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
              Rate Limiting
            </Text>
            <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* Requests per minute */}
                <div>
                  <label htmlFor="requests-per-minute" className="mb-1 block text-xs text-gray-500">
                    Requests/min
                  </label>
                  <NumberInput
                    id="requests-per-minute"
                    value={systemConfig.rateLimiting.requestsPerMinute}
                    onValueChange={(value) =>
                      handleRateLimitingChange('requestsPerMinute', value ?? 60)
                    }
                    min={1}
                    max={1000}
                    step={1}
                    className="bg-[#1A1A1A]"
                    data-testid="input-requests-per-minute"
                    aria-label="Requests per minute"
                  />
                </div>
                {/* Burst size */}
                <div>
                  <label htmlFor="burst-size" className="mb-1 block text-xs text-gray-500">
                    Burst Size
                  </label>
                  <NumberInput
                    id="burst-size"
                    value={systemConfig.rateLimiting.burstSize}
                    onValueChange={(value) => handleRateLimitingChange('burstSize', value ?? 10)}
                    min={1}
                    max={100}
                    step={1}
                    className="bg-[#1A1A1A]"
                    data-testid="input-burst-size"
                    aria-label="Burst size"
                  />
                </div>
                {/* Enabled toggle */}
                <div>
                  <label htmlFor="rate-limit-enabled" className="mb-1 block text-xs text-gray-500">
                    Enabled
                  </label>
                  <div className="flex h-[38px] items-center">
                    <Switch
                      id="rate-limit-enabled"
                      checked={systemConfig.rateLimiting.enabled}
                      onChange={() =>
                        handleRateLimitingChange('enabled', !systemConfig.rateLimiting.enabled)
                      }
                      aria-label="Rate limiting enabled"
                      data-testid="switch-rate-limit-enabled"
                      className={clsx(
                        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                        'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
                        systemConfig.rateLimiting.enabled ? 'bg-[#76B900]' : 'bg-gray-600'
                      )}
                    >
                      <span
                        className={clsx(
                          'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                          systemConfig.rateLimiting.enabled ? 'translate-x-6' : 'translate-x-1'
                        )}
                      />
                    </Switch>
                    <span className="ml-2 text-sm text-gray-400">
                      {systemConfig.rateLimiting.enabled ? 'On' : 'Off'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Queue Settings */}
          <div data-testid="queue-settings-section">
            <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
              Queue Settings
            </Text>
            <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {/* Max Queue Size */}
                <div>
                  <label htmlFor="max-queue-size" className="mb-1 block text-xs text-gray-500">
                    Max Size
                  </label>
                  <NumberInput
                    id="max-queue-size"
                    value={systemConfig.queueSettings.maxSize}
                    onValueChange={(value) => handleQueueSettingsChange('maxSize', value ?? 10000)}
                    min={100}
                    max={100000}
                    step={100}
                    className="bg-[#1A1A1A]"
                    data-testid="input-max-queue-size"
                    aria-label="Maximum queue size"
                  />
                </div>
                {/* Backpressure Threshold */}
                <div>
                  <label
                    htmlFor="backpressure-threshold"
                    className="mb-1 block text-xs text-gray-500"
                  >
                    Backpressure Threshold (%)
                  </label>
                  <NumberInput
                    id="backpressure-threshold"
                    value={systemConfig.queueSettings.backpressureThreshold}
                    onValueChange={(value) =>
                      handleQueueSettingsChange('backpressureThreshold', value ?? 80)
                    }
                    min={10}
                    max={100}
                    step={5}
                    className="bg-[#1A1A1A]"
                    data-testid="input-backpressure-threshold"
                    aria-label="Backpressure threshold percentage"
                  />
                  <Text className="mt-1 text-xs text-gray-600">
                    Queue usage % that triggers backpressure
                  </Text>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 border-t border-gray-800 pt-4">
            <Button
              onClick={() => void handleSaveConfig()}
              disabled={!hasConfigChanges || updateMutation.isPending}
              className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="btn-save-config"
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Changes
                </>
              )}
            </Button>
            <Button
              onClick={handleResetConfig}
              disabled={!hasConfigChanges || updateMutation.isPending}
              variant="secondary"
              className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="btn-reset-config"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
          </div>

          {isLoadingSettings && (
            <div className="flex items-center gap-2 text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading settings...</span>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Maintenance Section */}
      <CollapsibleSection
        title="Maintenance Actions"
        icon={<Wrench className="h-5 w-5 text-amber-400" />}
        isOpen={maintenanceOpen}
        onToggle={setMaintenanceOpen}
        data-testid="admin-maintenance"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {/* Orphan Cleanup */}
            <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
              <div className="mb-3 flex items-center gap-2">
                <Trash2 className="h-4 w-4 text-amber-400" />
                <Text className="font-medium text-white">Orphan Cleanup</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">
                Remove orphaned files and database records
              </Text>
              <Button
                onClick={() => setConfirmOrphanCleanup(true)}
                disabled={orphanCleanup.isPending}
                className="w-full bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
                size="sm"
                data-testid="btn-orphan-cleanup"
              >
                {orphanCleanup.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Run Cleanup
                  </>
                )}
              </Button>
            </div>

            {/* Cache Clear */}
            <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
              <div className="mb-3 flex items-center gap-2">
                <RefreshCw className="h-4 w-4 text-blue-400" />
                <Text className="font-medium text-white">Clear Cache</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">Purge all cached data from Redis</Text>
              <Button
                onClick={() => setConfirmCacheClear(true)}
                disabled={clearCache.isPending}
                className="w-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                size="sm"
                data-testid="btn-cache-clear"
              >
                {clearCache.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Clearing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Clear Cache
                  </>
                )}
              </Button>
            </div>

            {/* Flush Queues */}
            <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
              <div className="mb-3 flex items-center gap-2">
                <Zap className="h-4 w-4 text-purple-400" />
                <Text className="font-medium text-white">Flush Queues</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">Clear all processing queues</Text>
              <Button
                onClick={() => setConfirmFlushQueues(true)}
                disabled={flushQueues.isPending}
                className="w-full bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
                size="sm"
                data-testid="btn-flush-queues"
              >
                {flushQueues.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Flushing...
                  </>
                ) : (
                  <>
                    <Zap className="mr-2 h-4 w-4" />
                    Flush Queues
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </CollapsibleSection>

      {/* Developer Tools Section - Only visible in debug mode */}
      {debugMode && (
        <CollapsibleSection
          title="Developer Tools"
          icon={<Database className="h-5 w-5 text-red-400" />}
          isOpen={developerToolsOpen}
          onToggle={setDeveloperToolsOpen}
          alertBadge={
            <Badge color="red" size="sm" data-testid="debug-mode-badge">
              Debug Mode Only
            </Badge>
          }
          data-testid="admin-developer-tools"
        >
          <Callout title="Development Only" icon={AlertTriangle} color="red" className="mb-4">
            <span className="text-tremor-default text-red-200/80">
              These tools are only available when the backend is running in debug mode. They modify
              database data and should not be used in production.
            </span>
          </Callout>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {/* Seed Cameras */}
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <span className="text-base" role="img" aria-label="Camera">
                  📷
                </span>
                <Text className="font-medium text-white">Seed Cameras</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">
                Create 5 test cameras with realistic names
              </Text>
              <Button
                onClick={() => setConfirmSeedCameras(true)}
                disabled={seedCameras.isPending}
                className="w-full border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                size="sm"
                data-testid="btn-seed-cameras"
              >
                {seedCameras.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Seeding...
                  </>
                ) : (
                  <>
                    <span className="mr-2" role="img" aria-label="Camera">
                      📷
                    </span>
                    Seed Cameras
                  </>
                )}
              </Button>
            </div>

            {/* Seed Events */}
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <span className="text-base" role="img" aria-label="Calendar">
                  📅
                </span>
                <Text className="font-medium text-white">Seed Events</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">
                Create 50 test events with detections
              </Text>
              <Button
                onClick={() => setConfirmSeedEvents(true)}
                disabled={seedEvents.isPending}
                className="w-full border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                size="sm"
                data-testid="btn-seed-events"
              >
                {seedEvents.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Seeding...
                  </>
                ) : (
                  <>
                    <span className="mr-2" role="img" aria-label="Calendar">
                      📅
                    </span>
                    Seed Events
                  </>
                )}
              </Button>
            </div>

            {/* Clear Test Data */}
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <span className="text-base" role="img" aria-label="Trash">
                  🗑️
                </span>
                <Text className="font-medium text-white">Clear Test Data</Text>
              </div>
              <Text className="mb-4 text-xs text-gray-500">
                Delete all cameras, events, and detections
              </Text>
              <Button
                onClick={() => setConfirmClearTestData(true)}
                disabled={clearSeededData.isPending}
                className="w-full border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                size="sm"
                data-testid="btn-clear-test-data"
              >
                {clearSeededData.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Clearing...
                  </>
                ) : (
                  <>
                    <span className="mr-2" role="img" aria-label="Trash">
                      🗑️
                    </span>
                    Clear Test Data
                  </>
                )}
              </Button>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* Confirmation Dialogs for Maintenance Actions */}
      <ConfirmDialog
        isOpen={confirmOrphanCleanup}
        title="Run Orphan Cleanup"
        description="This will scan for and remove orphaned files and database records. This may take a few minutes to complete."
        confirmLabel="Run Cleanup"
        loadingText="Running..."
        variant="warning"
        isLoading={orphanCleanup.isPending}
        onConfirm={() => void handleOrphanCleanup()}
        onCancel={() => setConfirmOrphanCleanup(false)}
      />

      <ConfirmDialog
        isOpen={confirmCacheClear}
        title="Clear Cache"
        description="This will purge all cached data from Redis. Some operations may be slower temporarily while the cache is rebuilt."
        confirmLabel="Clear Cache"
        loadingText="Clearing..."
        variant="warning"
        isLoading={clearCache.isPending}
        onConfirm={() => void handleCacheClear()}
        onCancel={() => setConfirmCacheClear(false)}
      />

      <ConfirmDialog
        isOpen={confirmFlushQueues}
        title="Flush Queues"
        description="This will clear all processing queues. Any pending items will be lost and may need to be reprocessed."
        confirmLabel="Flush Queues"
        loadingText="Flushing..."
        variant="warning"
        isLoading={flushQueues.isPending}
        onConfirm={() => void handleFlushQueues()}
        onCancel={() => setConfirmFlushQueues(false)}
      />

      {/* Confirmation Dialogs for Developer Tools */}
      <ConfirmDialog
        isOpen={confirmSeedCameras}
        title="Seed Test Cameras"
        description="This will create 5 test cameras with realistic names. This is only for development and testing purposes."
        confirmLabel="Seed Cameras"
        loadingText="Seeding..."
        variant="warning"
        isLoading={seedCameras.isPending}
        onConfirm={() => void handleSeedCameras()}
        onCancel={() => setConfirmSeedCameras(false)}
      />

      <ConfirmDialog
        isOpen={confirmSeedEvents}
        title="Seed Test Events"
        description="This will create 50 test events with detections. This is only for development and testing purposes."
        confirmLabel="Seed Events"
        loadingText="Seeding..."
        variant="warning"
        isLoading={seedEvents.isPending}
        onConfirm={() => void handleSeedEvents()}
        onCancel={() => setConfirmSeedEvents(false)}
      />

      <ConfirmWithTextDialog
        isOpen={confirmClearTestData}
        title="Clear All Test Data"
        description="This will permanently delete ALL cameras, events, and detections from the database. This action cannot be undone."
        confirmText="DELETE"
        confirmButtonText="Clear All Data"
        loadingButtonText="Clearing..."
        variant="danger"
        isLoading={clearSeededData.isPending}
        onConfirm={() => void handleClearTestData()}
        onCancel={() => setConfirmClearTestData(false)}
      />
    </div>
  );
}

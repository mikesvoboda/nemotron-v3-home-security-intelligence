/**
 * FeatureTogglesPanel - Settings panel for AI processing feature toggles
 *
 * Displays toggle switches for enabling/disabling AI pipeline features
 * with descriptions. Uses the unified settings API for persistence.
 *
 * @see NEM-3645 - Create FeatureTogglesPanel Component
 */

import { Switch } from '@headlessui/react';
import { Card, Title, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Eye,
  Fingerprint,
  Image,
  Loader2,
  RefreshCw,
  Sparkles,
  ToggleLeft,
  Video,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  useSettingsApi,
  type FeatureSettings,
} from '../../hooks/useSettingsApi';

export interface FeatureTogglesPanelProps {
  /** Optional className for styling */
  className?: string;
}

/** Feature toggle key type matching backend settings */
export type FeatureToggleKey = keyof FeatureSettings;

/** Feature toggle configuration for UI display */
interface FeatureToggleConfig {
  id: FeatureToggleKey;
  label: string;
  description: string;
  icon: React.FC<{ className?: string }>;
}

/**
 * Feature toggle configurations with labels, descriptions, and icons.
 * Order determines display order in the panel.
 */
const FEATURE_TOGGLE_CONFIGS: FeatureToggleConfig[] = [
  {
    id: 'vision_extraction_enabled',
    label: 'Vision Extraction',
    description: 'Enable Florence-2 vision extraction for vehicle and person attributes',
    icon: Eye,
  },
  {
    id: 'reid_enabled',
    label: 'Re-ID Tracking',
    description: 'Enable CLIP re-identification for tracking entities across cameras',
    icon: Fingerprint,
  },
  {
    id: 'scene_change_enabled',
    label: 'Scene Change Detection',
    description: 'Enable SSIM-based scene change detection for camera views',
    icon: RefreshCw,
  },
  {
    id: 'clip_generation_enabled',
    label: 'Clip Generation',
    description: 'Enable automatic video clip generation for security events',
    icon: Video,
  },
  {
    id: 'image_quality_enabled',
    label: 'Image Quality Assessment',
    description: 'Enable BRISQUE image quality assessment (CPU-based)',
    icon: Image,
  },
  {
    id: 'background_eval_enabled',
    label: 'Background Evaluation',
    description: 'Enable automatic background AI audit evaluation when GPU is idle',
    icon: Sparkles,
  },
];

/**
 * FeatureTogglesPanel component
 *
 * A settings panel that displays feature toggles for AI processing features.
 * Changes are persisted immediately via the unified settings API with optimistic updates.
 */
export default function FeatureTogglesPanel({ className }: FeatureTogglesPanelProps) {
  const { settings, isLoading, isError, error, updateMutation } = useSettingsApi();
  const [togglingFeature, setTogglingFeature] = useState<FeatureToggleKey | null>(null);

  /**
   * Handle feature toggle change.
   * Updates via the settings API with optimistic updates.
   */
  const handleToggle = useCallback(
    async (featureKey: FeatureToggleKey, newValue: boolean) => {
      setTogglingFeature(featureKey);
      try {
        await updateMutation.mutateAsync({
          features: { [featureKey]: newValue },
        });
      } catch {
        // Error is handled by the mutation's error state
        // Optimistic update will be rolled back automatically
      } finally {
        setTogglingFeature(null);
      }
    },
    [updateMutation]
  );

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="feature-toggles-panel"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <ToggleLeft className="h-5 w-5 text-[#76B900]" />
          Feature Toggles
        </Title>
        <Text className="mb-4 text-gray-400">
          Enable or disable AI processing features
        </Text>
        <div className="space-y-4" data-testid="feature-toggles-loading">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
            >
              <div className="flex-1">
                <div className="skeleton mb-2 h-4 w-32"></div>
                <div className="skeleton h-3 w-64"></div>
              </div>
              <div className="skeleton h-6 w-11 rounded-full"></div>
            </div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="feature-toggles-panel"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <ToggleLeft className="h-5 w-5 text-[#76B900]" />
          Feature Toggles
        </Title>
        <div
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
          data-testid="feature-toggles-error"
        >
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            {error?.message || 'Failed to load feature settings'}
          </Text>
        </div>
      </Card>
    );
  }

  // Count enabled features for summary
  const enabledCount = settings
    ? FEATURE_TOGGLE_CONFIGS.filter((config) => settings.features[config.id]).length
    : 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="feature-toggles-panel"
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Title className="flex items-center gap-2 text-white">
            <ToggleLeft className="h-5 w-5 text-[#76B900]" />
            Feature Toggles
          </Title>
          <Text className="mt-1 text-gray-400">
            Enable or disable AI processing features
          </Text>
        </div>
        <span className="text-sm text-gray-500" data-testid="feature-toggles-summary">
          {enabledCount}/{FEATURE_TOGGLE_CONFIGS.length} enabled
        </span>
      </div>

      <div className="space-y-3">
        {FEATURE_TOGGLE_CONFIGS.map((config) => {
          const isEnabled = settings?.features[config.id] ?? false;
          const isToggling = togglingFeature === config.id;
          const IconComponent = config.icon;

          return (
            <div
              key={config.id}
              className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
              data-testid={`feature-toggle-${config.id}`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[#76B900]/20 text-[#76B900]">
                  <IconComponent className="h-4 w-4" />
                </div>
                <div>
                  <label
                    htmlFor={`toggle-${config.id}`}
                    className="cursor-pointer font-medium text-white"
                  >
                    {config.label}
                  </label>
                  <Text className="text-sm text-gray-500">{config.description}</Text>
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
                  id={`toggle-${config.id}`}
                  checked={isEnabled}
                  onChange={(checked) => void handleToggle(config.id, checked)}
                  disabled={isToggling}
                  aria-label={`Toggle ${config.label} ${isEnabled ? 'off' : 'on'}`}
                  data-testid={`feature-toggle-${config.id}-switch`}
                  className={clsx(
                    'relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors',
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

      {/* Mutation error feedback */}
      {updateMutation.isError && (
        <div
          className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3"
          data-testid="feature-toggles-mutation-error"
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0 text-red-400" />
          <Text className="text-sm text-red-400">
            {updateMutation.error?.message || 'Failed to update feature'}
          </Text>
        </div>
      )}
    </Card>
  );
}

/**
 * LoggingSettings - Comprehensive logging configuration UI
 *
 * Displays and allows configuration of logging settings:
 * - Runtime log level (editable via API)
 * - Log file settings (read-only from config)
 * - Database logging settings (read-only from config)
 * - Log retention period (editable via system config API)
 *
 * @see NEM-4952 - Complete Logging Configuration UI
 */
import { Card, Title, Text, Button, Callout, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Database,
  FileText,
  HardDrive,
  Info,
  Loader2,
  Lock,
  RefreshCw,
  RotateCcw,
  Save,
  Settings,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { useDebugConfigQuery } from '../../hooks/useDebugConfigQuery';
import { useLogLevelQuery } from '../../hooks/useLogLevelQuery';
import { useSetLogLevelMutation, type LogLevel } from '../../hooks/useSetLogLevelMutation';
import { useToast } from '../../hooks/useToast';
import { fetchConfig, updateConfig } from '../../services/api';

// ============================================================================
// Constants
// ============================================================================

const LOG_LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

// ============================================================================
// Types
// ============================================================================

export interface LoggingSettingsProps {
  /** Optional className for additional styling */
  className?: string;
}

interface LoggingConfig {
  log_level: string;
  log_file_path: string;
  log_file_max_bytes: number;
  log_file_backup_count: number;
  log_db_enabled: boolean;
  log_db_min_level: string;
  log_retention_days: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format bytes to human-readable size (MB)
 */
function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return `${Math.round(mb)} MB`;
}

/**
 * Format file count with singular/plural
 */
function formatFileCount(count: number): string {
  return count === 1 ? '1 file' : `${count} files`;
}

// ============================================================================
// Component
// ============================================================================

export default function LoggingSettings({ className }: LoggingSettingsProps) {
  const toast = useToast();

  // Fetch debug config for logging settings
  const {
    data: debugConfig,
    isLoading: debugConfigLoading,
    error: debugConfigError,
    refetch: refetchDebugConfig,
  } = useDebugConfigQuery();

  // Log level query and mutation
  const { currentLevel, isLoading: logLevelLoading, refetch: refetchLogLevel } = useLogLevelQuery();
  const {
    setLevel,
    isPending: isSettingLevel,
    error: setLevelError,
    reset: resetSetLevel,
  } = useSetLogLevelMutation();

  // System config for retention
  const [systemConfigLoading, setSystemConfigLoading] = useState(true);
  const [editedRetention, setEditedRetention] = useState<number>(7);
  const [originalRetention, setOriginalRetention] = useState<number>(7);

  // Extract logging config from debug config (response is flat Record<string, unknown>)
  const loggingConfig: LoggingConfig | null = debugConfig
    ? {
        log_level: (debugConfig.log_level as string) ?? 'INFO',
        log_file_path: (debugConfig.log_file_path as string) ?? 'data/logs/security.log',
        log_file_max_bytes: (debugConfig.log_file_max_bytes as number) ?? 10485760,
        log_file_backup_count: (debugConfig.log_file_backup_count as number) ?? 7,
        log_db_enabled: (debugConfig.log_db_enabled as boolean) ?? true,
        log_db_min_level: (debugConfig.log_db_min_level as string) ?? 'DEBUG',
        log_retention_days: (debugConfig.log_retention_days as number) ?? 7,
      }
    : null;

  // Fetch system config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setSystemConfigLoading(true);
        const config = await fetchConfig();
        setEditedRetention(config.log_retention_days);
        setOriginalRetention(config.log_retention_days);
      } catch {
        // Error handling via existing state
      } finally {
        setSystemConfigLoading(false);
      }
    };

    void loadConfig();
  }, []);

  // Track if retention has changed
  const hasRetentionChanges = editedRetention !== originalRetention;

  // Handle log level change
  const handleLevelChange = useCallback(
    async (level: LogLevel) => {
      if (level === currentLevel) return;

      try {
        resetSetLevel();
        await setLevel(level);
        toast.success(`Log level changed to ${level}`);
        await refetchLogLevel();
      } catch {
        toast.error('Failed to change log level');
      }
    },
    [currentLevel, setLevel, toast, refetchLogLevel, resetSetLevel]
  );

  // Handle retention save
  const handleSaveRetention = useCallback(async () => {
    if (!hasRetentionChanges) return;

    try {
      await updateConfig({ log_retention_days: editedRetention });
      setOriginalRetention(editedRetention);
      toast.success('Log retention updated');
    } catch {
      toast.error('Failed to update log retention');
    }
  }, [editedRetention, hasRetentionChanges, toast]);

  // Handle retention reset
  const handleResetRetention = useCallback(() => {
    setEditedRetention(originalRetention);
  }, [originalRetention]);

  // Handle retry
  const handleRetry = useCallback(async () => {
    await refetchDebugConfig();
  }, [refetchDebugConfig]);

  // Loading state
  const isLoading = debugConfigLoading || logLevelLoading || systemConfigLoading;

  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="logging-settings"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Settings className="h-5 w-5 text-[#76B900]" />
          Logging Configuration
        </Title>
        <div className="flex items-center justify-center py-8" data-testid="logging-settings-loading">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-400">Loading logging settings...</span>
        </div>
      </Card>
    );
  }

  // Error state
  if (debugConfigError) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="logging-settings"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Settings className="h-5 w-5 text-[#76B900]" />
          Logging Configuration
        </Title>
        <div
          className="flex items-center gap-2 rounded bg-red-500/10 px-4 py-3 text-red-400"
          data-testid="logging-settings-error"
        >
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load logging settings: {debugConfigError.message}</span>
          <button
            onClick={() => void handleRetry()}
            className="ml-auto text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      </Card>
    );
  }

  const effectiveLevel = currentLevel ?? loggingConfig?.log_level ?? 'INFO';

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="logging-settings"
    >
      <Title className="mb-2 flex items-center gap-2 text-white">
        <Settings className="h-5 w-5 text-[#76B900]" />
        Logging Configuration
      </Title>
      <Text className="mb-6 text-gray-400">
        Configure application logging settings. Some settings are read-only and can only be changed
        via environment variables.
      </Text>

      <div className="space-y-6">
        {/* Runtime Log Level Section */}
        <div className="rounded-lg border border-gray-700 bg-[#121212] p-4">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-400" />
            <Text className="font-medium text-white">Runtime Log Level</Text>
          </div>

          {/* Current Level Display */}
          <div className="mb-4">
            <span className="text-sm text-gray-400">Current Level: </span>
            <span className="font-mono font-semibold text-[#76B900]">{effectiveLevel}</span>
          </div>

          {/* Level Buttons */}
          <div className="mb-4 flex flex-wrap gap-2">
            {LOG_LEVELS.map((level) => {
              const isActive = level === effectiveLevel;
              return (
                <button
                  key={level}
                  onClick={() => void handleLevelChange(level)}
                  disabled={isSettingLevel || isActive}
                  data-active={isActive ? 'true' : undefined}
                  className={clsx(
                    'rounded px-4 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-[#76B900] text-black'
                      : 'bg-gray-700 text-gray-200 hover:bg-gray-600 disabled:opacity-50'
                  )}
                >
                  {level}
                </button>
              );
            })}
            {isSettingLevel && (
              <span className="flex items-center gap-1 text-sm text-gray-400">
                <RefreshCw className="h-4 w-4 animate-spin" />
                Changing...
              </span>
            )}
          </div>

          {/* Set Error Message */}
          {setLevelError && (
            <div
              className="mb-4 flex items-center gap-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400"
              data-testid="log-level-error"
            >
              <AlertTriangle className="h-4 w-4" />
              <span>Failed to set log level: {setLevelError.message}</span>
            </div>
          )}

          {/* DEBUG Warning */}
          {effectiveLevel === 'DEBUG' && (
            <Callout
              title="Performance Warning"
              icon={AlertTriangle}
              color="yellow"
              className="mb-4"
              data-testid="debug-warning"
            >
              <span className="text-sm">
                DEBUG logging is enabled. This may impact performance due to increased log output.
                Consider using INFO or higher for production workloads.
              </span>
            </Callout>
          )}

          {/* Persistence Note */}
          <div className="flex items-start gap-2 rounded border border-gray-700 bg-gray-800/30 px-3 py-2 text-sm text-gray-400">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>
              Log level changes do <strong className="text-gray-300">not persist</strong> on server
              restart. The level will revert to the configured default.
            </span>
          </div>
        </div>

        {/* Log File Settings Section (Read-Only) */}
        <div
          className="rounded-lg border border-gray-700 bg-[#121212] p-4"
          data-testid="log-file-settings"
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="h-5 w-5 text-amber-400" />
              <Text className="font-medium text-white">Log File Settings</Text>
            </div>
            <Badge color="gray" size="sm" icon={Lock}>
              Read-only
            </Badge>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <Text className="mb-1 text-xs text-gray-500">File Path</Text>
              <Text className="font-mono text-sm text-gray-300">
                {loggingConfig?.log_file_path ?? '-'}
              </Text>
            </div>
            <div>
              <Text className="mb-1 text-xs text-gray-500">Max File Size</Text>
              <Text className="text-sm text-gray-300">
                {loggingConfig ? formatBytes(loggingConfig.log_file_max_bytes) : '-'}
              </Text>
            </div>
            <div>
              <Text className="mb-1 text-xs text-gray-500">Backup Count</Text>
              <Text className="text-sm text-gray-300">
                {loggingConfig ? formatFileCount(loggingConfig.log_file_backup_count) : '-'}
              </Text>
            </div>
          </div>

          <div className="mt-3 flex items-start gap-2 text-xs text-gray-500">
            <Info className="mt-0.5 h-3 w-3 flex-shrink-0" />
            <span>File settings are configured via environment variables and cannot be changed at runtime.</span>
          </div>
        </div>

        {/* Database Logging Section (Read-Only) */}
        <div
          className="rounded-lg border border-gray-700 bg-[#121212] p-4"
          data-testid="log-db-settings"
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-purple-400" />
              <Text className="font-medium text-white">Database Logging</Text>
            </div>
            <Badge color="gray" size="sm" icon={Lock}>
              Read-only
            </Badge>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Text className="mb-1 text-xs text-gray-500">DB Logging</Text>
              <Text className="text-sm text-gray-300">
                {loggingConfig?.log_db_enabled ? (
                  <Badge color="green" size="sm">Enabled</Badge>
                ) : (
                  <Badge color="gray" size="sm">Disabled</Badge>
                )}
              </Text>
            </div>
            <div>
              <Text className="mb-1 text-xs text-gray-500">Min DB Level</Text>
              <Text className="font-mono text-sm text-gray-300">
                {loggingConfig?.log_db_min_level ?? '-'}
              </Text>
            </div>
          </div>

          <div className="mt-3 flex items-start gap-2 text-xs text-gray-500">
            <Info className="mt-0.5 h-3 w-3 flex-shrink-0" />
            <span>Database logging settings are configured via environment variables.</span>
          </div>
        </div>

        {/* Log Retention Section (Editable) */}
        <div
          className="rounded-lg border border-gray-700 bg-[#121212] p-4"
          data-testid="log-retention-settings"
        >
          <div className="mb-4 flex items-center gap-2">
            <RefreshCw className="h-5 w-5 text-green-400" />
            <Text className="font-medium text-white">Log Retention</Text>
          </div>

          <div className="mb-4">
            <div className="mb-2 flex items-end justify-between">
              <div>
                <Text className="text-sm text-gray-300">Retention Period</Text>
                <Text className="text-xs text-gray-500">Number of days to retain application logs</Text>
              </div>
              <Text className="text-lg font-semibold text-white">{editedRetention} days</Text>
            </div>
            <input
              type="range"
              min="1"
              max="90"
              step="1"
              value={editedRetention}
              onChange={(e) => setEditedRetention(parseInt(e.target.value))}
              className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
              aria-label="Log retention period in days"
            />
            <div className="mt-1 flex justify-between text-xs text-gray-500">
              <span>1 day</span>
              <span>90 days</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 border-t border-gray-700 pt-4">
            <Button
              onClick={() => void handleSaveRetention()}
              disabled={!hasRetentionChanges}
              className="flex-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="retention-save-button"
            >
              <Save className="mr-2 h-4 w-4" />
              Save Changes
            </Button>
            <Button
              onClick={handleResetRetention}
              disabled={!hasRetentionChanges}
              variant="secondary"
              className="flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="retention-reset-button"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

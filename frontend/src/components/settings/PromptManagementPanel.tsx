/**
 * Prompt Management Panel Component
 *
 * Provides a UI for managing LLM prompt versions including:
 * - List of saved prompt templates with versions
 * - History view showing prompt changes over time
 * - Ability to compare different versions (diff view)
 * - Rollback capability to previous versions
 * - Performance metrics per prompt version (if available)
 *
 * @see backend/api/routes/prompt_management.py - Backend API
 * @see NEM-1761 - Original task specification
 */

import { Badge, Button, Card, Select, SelectItem, Tab, TabGroup, TabList, TabPanel, TabPanels, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertCircle, Calendar, ChevronLeft, ChevronRight, Clock, Download, FileText, History, Loader2, RotateCcw, User } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchAllPrompts,
  fetchPromptForModel,
  fetchPromptHistory,
  restorePromptVersion,
  exportPrompts,
  PromptApiError,
} from '../../services/promptManagementApi';
import { AIModelEnum, type AllPromptsResponse, type ModelPromptConfig, type PromptHistoryResponse, type PromptRestoreResponse } from '../../types/promptManagement';

// ============================================================================
// Constants
// ============================================================================

const MODEL_DISPLAY_NAMES: Record<AIModelEnum, string> = {
  [AIModelEnum.NEMOTRON]: 'Nemotron (Risk Analysis)',
  [AIModelEnum.FLORENCE2]: 'Florence-2 (Scene Analysis)',
  [AIModelEnum.YOLO_WORLD]: 'YOLO-World (Object Detection)',
  [AIModelEnum.XCLIP]: 'X-CLIP (Action Recognition)',
  [AIModelEnum.FASHION_CLIP]: 'Fashion-CLIP (Clothing Analysis)',
};

const ITEMS_PER_PAGE = 20;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format ISO datetime string to human-readable format
 */
function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay > 0) {
    return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
  } else if (diffHour > 0) {
    return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  } else if (diffMin > 0) {
    return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
  } else {
    return 'Just now';
  }
}

// Utility function for future diff view feature (not currently used)
// function generateConfigDiff(oldConfig: Record<string, unknown>, newConfig: Record<string, unknown>): string[] {
//   const changes: string[] = [];
//   for (const key in newConfig) {
//     if (!(key in oldConfig)) {
//       changes.push(`+ Added: ${key}`);
//     } else if (JSON.stringify(oldConfig[key]) !== JSON.stringify(newConfig[key])) {
//       changes.push(`~ Changed: ${key}`);
//     }
//   }
//   for (const key in oldConfig) {
//     if (!(key in newConfig)) {
//       changes.push(`- Removed: ${key}`);
//     }
//   }
//   return changes;
// }

// ============================================================================
// Component Types
// ============================================================================

interface PromptManagementPanelProps {
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

export default function PromptManagementPanel({ className }: PromptManagementPanelProps) {
  const [selectedModel, setSelectedModel] = useState<AIModelEnum>(AIModelEnum.NEMOTRON);
  const [currentPage, setCurrentPage] = useState(0);

  // State for all prompts (not currently used in UI, but kept for future enhancement)
  const [, setAllPrompts] = useState<AllPromptsResponse | null>(null);
  const [, setIsLoadingAll] = useState(false);
  const [allPromptsError, setAllPromptsError] = useState<Error | null>(null);

  // State for current config
  const [currentConfig, setCurrentConfig] = useState<ModelPromptConfig | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [configError, setConfigError] = useState<Error | null>(null);

  // State for history
  const [historyData, setHistoryData] = useState<PromptHistoryResponse | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<Error | null>(null);

  // State for restore
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreSuccess, setRestoreSuccess] = useState<PromptRestoreResponse | null>(null);
  const [restoreError, setRestoreError] = useState<Error | null>(null);

  // State for export
  const [isExporting, setIsExporting] = useState(false);

  // Fetch all prompts
  useEffect(() => {
    setIsLoadingAll(true);
    setAllPromptsError(null);
    fetchAllPrompts()
      .then(setAllPrompts)
      .catch(setAllPromptsError)
      .finally(() => setIsLoadingAll(false));
  }, []);

  // Fetch current config when model changes
  useEffect(() => {
    setIsLoadingConfig(true);
    setConfigError(null);
    fetchPromptForModel(selectedModel)
      .then(setCurrentConfig)
      .catch(setConfigError)
      .finally(() => setIsLoadingConfig(false));
  }, [selectedModel]);

  // Fetch history when model or page changes
  useEffect(() => {
    setIsLoadingHistory(true);
    setHistoryError(null);
    fetchPromptHistory(selectedModel, ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
      .then(setHistoryData)
      .catch(setHistoryError)
      .finally(() => setIsLoadingHistory(false));
  }, [selectedModel, currentPage]);

  // Reset page when model changes
  useEffect(() => {
    setCurrentPage(0);
  }, [selectedModel]);

  const totalPages = historyData ? Math.ceil(historyData.total_count / ITEMS_PER_PAGE) : 0;

  // Refresh all data
  const refreshData = () => {
    fetchPromptForModel(selectedModel).then(setCurrentConfig).catch(setConfigError);
    fetchPromptHistory(selectedModel, ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE)
      .then(setHistoryData)
      .catch(setHistoryError);
  };

  // ============================================================================
  // Event Handlers
  // ============================================================================

  const handleRestore = async (versionId: number, versionNumber: number) => {
    if (confirm(`Restore version ${versionNumber}? This will create a new version with the same configuration.`)) {
      setIsRestoring(true);
      setRestoreError(null);
      setRestoreSuccess(null);
      try {
        const result = await restorePromptVersion(versionId);
        setRestoreSuccess(result);
        // Refresh data after successful restore
        refreshData();
      } catch (error) {
        setRestoreError(error as Error);
      } finally {
        setIsRestoring(false);
      }
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const data = await exportPrompts();
      // Download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `prompts-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const handlePreviousPage = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className={clsx('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Title>Prompt Management</Title>
          <Text className="mt-1">
            Manage AI model prompt templates, view version history, and rollback changes
          </Text>
        </div>
        <Button
          icon={Download}
          variant="secondary"
          onClick={() => void handleExport()}
          loading={isExporting}
          disabled={isExporting}
        >
          Export All
        </Button>
      </div>

      {/* Error Display */}
      {(allPromptsError || configError || historyError) && (
        <Card className="border-red-500/50 bg-red-500/10">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <div>
              <Text className="font-semibold text-red-400">Error loading prompt data</Text>
              <Text className="text-red-400/80">
                {(allPromptsError as PromptApiError)?.message ||
                  (configError as PromptApiError)?.message ||
                  (historyError as PromptApiError)?.message ||
                  'An unknown error occurred'}
              </Text>
            </div>
          </div>
        </Card>
      )}

      {/* Model Selection */}
      <Card>
        <div className="space-y-3">
          <Text className="font-semibold">Select Model</Text>
          <Select value={selectedModel} onValueChange={(value) => setSelectedModel(value as AIModelEnum)}>
            {Object.entries(MODEL_DISPLAY_NAMES).map(([key, label]) => (
              <SelectItem key={key} value={key}>
                {label}
              </SelectItem>
            ))}
          </Select>
        </div>
      </Card>

      {/* Tabs: Current Config vs History */}
      <TabGroup>
        <TabList variant="solid" className="mb-4">
          <Tab icon={FileText}>Current Configuration</Tab>
          <Tab icon={History}>Version History</Tab>
        </TabList>

        <TabPanels>
          {/* Current Configuration Panel */}
          <TabPanel>
            {isLoadingConfig ? (
              <Card>
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
                </div>
              </Card>
            ) : currentConfig ? (
              <Card>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Title>Version {currentConfig.version}</Title>
                    <Badge color="green">Active</Badge>
                  </div>

                  {currentConfig.created_at && (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <Calendar className="h-4 w-4" />
                      <span>Last updated {formatRelativeTime(currentConfig.created_at)}</span>
                    </div>
                  )}

                  {currentConfig.created_by && (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <User className="h-4 w-4" />
                      <span>{currentConfig.created_by}</span>
                    </div>
                  )}

                  {currentConfig.change_description && (
                    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
                      <Text className="text-sm text-gray-300">{currentConfig.change_description}</Text>
                    </div>
                  )}

                  {/* Configuration Preview */}
                  <div className="mt-4">
                    <Text className="mb-2 font-semibold">Configuration</Text>
                    <pre className="max-h-96 overflow-auto rounded-lg border border-gray-700 bg-gray-900 p-4 text-xs text-gray-300">
                      {JSON.stringify(currentConfig.config, null, 2)}
                    </pre>
                  </div>
                </div>
              </Card>
            ) : (
              <Card>
                <Text className="text-center text-gray-400">No configuration found for this model</Text>
              </Card>
            )}
          </TabPanel>

          {/* Version History Panel */}
          <TabPanel>
            {isLoadingHistory ? (
              <Card>
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
                </div>
              </Card>
            ) : historyData && historyData.versions.length > 0 ? (
              <div className="space-y-4">
                {/* Version List */}
                <div className="space-y-3">
                  {historyData.versions.map((version) => (
                    <Card key={version.id} className={clsx(version.is_active && 'border-[#76B900]/50')}>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-3">
                            <Text className="font-semibold">Version {version.version}</Text>
                            {version.is_active && <Badge color="green">Active</Badge>}
                          </div>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-400">
                            <div className="flex items-center gap-1">
                              <Clock className="h-3.5 w-3.5" />
                              <span>{formatDateTime(version.created_at)}</span>
                            </div>
                            {version.created_by && (
                              <div className="flex items-center gap-1">
                                <User className="h-3.5 w-3.5" />
                                <span>{version.created_by}</span>
                              </div>
                            )}
                          </div>

                          {version.change_description && (
                            <Text className="text-sm text-gray-400">{version.change_description}</Text>
                          )}
                        </div>

                        {!version.is_active && (
                          <Button
                            icon={RotateCcw}
                            variant="secondary"
                            size="xs"
                            onClick={() => void handleRestore(version.id, version.version)}
                            loading={isRestoring}
                            disabled={isRestoring}
                          >
                            Restore
                          </Button>
                        )}
                      </div>
                    </Card>
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <Card>
                    <div className="flex items-center justify-between">
                      <Text className="text-sm text-gray-400">
                        Page {currentPage + 1} of {totalPages}
                      </Text>
                      <div className="flex gap-2">
                        <Button
                          icon={ChevronLeft}
                          variant="secondary"
                          size="xs"
                          onClick={handlePreviousPage}
                          disabled={currentPage === 0}
                        >
                          Previous
                        </Button>
                        <Button
                          icon={ChevronRight}
                          variant="secondary"
                          size="xs"
                          onClick={handleNextPage}
                          disabled={currentPage >= totalPages - 1}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </Card>
                )}
              </div>
            ) : (
              <Card>
                <Text className="text-center text-gray-400">No version history found for this model</Text>
              </Card>
            )}
          </TabPanel>
        </TabPanels>
      </TabGroup>

      {/* Restore Success Message */}
      {restoreSuccess && (
        <Card className="border-green-500/50 bg-green-500/10">
          <div className="flex items-center gap-3 text-green-400">
            <RotateCcw className="h-5 w-5 flex-shrink-0" />
            <div>
              <Text className="font-semibold text-green-400">Version Restored</Text>
              <Text className="text-green-400/80">{restoreSuccess.message}</Text>
            </div>
          </div>
        </Card>
      )}

      {/* Restore Error Message */}
      {restoreError && (
        <Card className="border-red-500/50 bg-red-500/10">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <div>
              <Text className="font-semibold text-red-400">Restore Failed</Text>
              <Text className="text-red-400/80">
                {(restoreError as PromptApiError)?.message || 'An unknown error occurred'}
              </Text>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

/**
 * PromptManagementPage - Main page for managing AI model prompt configurations
 *
 * Features:
 * - Model selector for switching between AI models
 * - Current configuration display with Edit button
 * - Version history with Restore functionality
 * - Export/Import buttons with diff preview
 * - URL-based state management for selected model
 *
 * @see NEM-2697 - Build Prompt Management page
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import {
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Select,
  SelectItem,
  Button,
  Card,
  Badge,
  Title,
  Text,
} from '@tremor/react';
import { Clock, RotateCcw, Edit } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import ImportExportButtons from './ImportExportButtons';
import PromptConfigEditor from './PromptConfigEditor';
import {
  usePromptConfig,
  usePromptHistory,
  useUpdatePromptConfig,
  useRestorePromptVersion,
} from '../../../hooks/usePromptQueries';
import { AIModelEnum } from '../../../types/promptManagement';

// ============================================================================
// Constants
// ============================================================================

// Model display options
const MODEL_OPTIONS = [
  { value: AIModelEnum.NEMOTRON, label: 'Nemotron (Risk Analysis)' },
  { value: AIModelEnum.FLORENCE2, label: 'Florence-2 (Scene Analysis)' },
  { value: AIModelEnum.YOLO_WORLD, label: 'YOLO-World (Object Detection)' },
  { value: AIModelEnum.XCLIP, label: 'X-CLIP (Action Recognition)' },
  { value: AIModelEnum.FASHION_CLIP, label: 'Fashion-CLIP (Clothing Analysis)' },
];

// Model display names
const MODEL_NAMES: Record<AIModelEnum, string> = {
  [AIModelEnum.NEMOTRON]: 'Nemotron',
  [AIModelEnum.FLORENCE2]: 'Florence-2',
  [AIModelEnum.YOLO_WORLD]: 'YOLO-World',
  [AIModelEnum.XCLIP]: 'X-CLIP',
  [AIModelEnum.FASHION_CLIP]: 'Fashion-CLIP',
};

// ============================================================================
// Helper Functions
// ============================================================================

function formatDate(dateString: string | undefined): string {
  if (!dateString) return 'Unknown';
  return new Date(dateString).toLocaleString();
}

// ============================================================================
// Component
// ============================================================================

/**
 * Main page component for managing AI model prompt configurations.
 */
export default function PromptManagementPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isEditorOpen, setIsEditorOpen] = useState(false);

  // Get model from URL params, default to Nemotron
  const selectedModel = useMemo(() => {
    const modelParam = searchParams.get('model');
    if (modelParam && Object.values(AIModelEnum).includes(modelParam as AIModelEnum)) {
      return modelParam as AIModelEnum;
    }
    return AIModelEnum.NEMOTRON;
  }, [searchParams]);

  // Fetch current config and history for selected model
  const {
    data: configData,
    isLoading: configLoading,
    error: configError,
  } = usePromptConfig(selectedModel);
  const { versions, isLoading: historyLoading } = usePromptHistory(selectedModel);

  // Mutations
  const updateMutation = useUpdatePromptConfig();
  const restoreMutation = useRestorePromptVersion();

  // Handle model selection change
  const handleModelChange = useCallback(
    (value: string) => {
      setSearchParams({ model: value });
    },
    [setSearchParams]
  );

  // Handle save from editor
  const handleSave = useCallback(
    async (config: Record<string, unknown>, changeDescription: string) => {
      try {
        await updateMutation.mutateAsync({
          model: selectedModel,
          request: { config, change_description: changeDescription || undefined },
        });
        setIsEditorOpen(false);
      } catch (error) {
        console.error('Failed to save config:', error);
      }
    },
    [selectedModel, updateMutation]
  );

  // Handle restore version
  const handleRestore = useCallback(
    async (versionId: number) => {
      try {
        await restoreMutation.mutateAsync(versionId);
      } catch (error) {
        console.error('Failed to restore version:', error);
      }
    },
    [restoreMutation]
  );

  // Handle import success - data automatically refreshed by TanStack Query invalidation
  const handleImportSuccess = useCallback(() => {
    // No additional action needed
  }, []);

  // Handle import/export errors
  const handleImportExportError = useCallback((error: Error) => {
    console.error('Import/export error:', error);
  }, []);

  // Loading state
  if (configLoading && historyLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-400">Loading configuration...</div>
      </div>
    );
  }

  // Error state
  if (configError) {
    return (
      <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
        <p className="text-red-400">Error loading data: {configError.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="prompt-management-page">
      {/* Header with title and actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Title className="text-white">Prompt Management</Title>
          <Text className="text-gray-400">Configure AI model prompts and view version history</Text>
        </div>
        <ImportExportButtons
          onImportSuccess={handleImportSuccess}
          onExportError={handleImportExportError}
          onImportError={handleImportExportError}
        />
      </div>

      {/* Model Selector */}
      <Card className="border-gray-700 bg-gray-900/50">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <label htmlFor="model-select" className="mb-1 block text-sm font-medium text-gray-200">
              Select Model
            </label>
            <Select
              id="model-select"
              value={selectedModel}
              onValueChange={handleModelChange}
              className="w-64"
            >
              {MODEL_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </Select>
          </div>
          {configData && (
            <div className="text-sm text-gray-400">
              <span>Version {configData.version}</span>
              <span className="mx-2">|</span>
              <span>Updated {formatDate(configData.created_at)}</span>
            </div>
          )}
        </div>
      </Card>

      {/* Tabs for Config and History */}
      <TabGroup>
        <TabList variant="solid" className="border-gray-700 bg-gray-900/50">
          <Tab>Current Configuration</Tab>
          <Tab>Version History</Tab>
        </TabList>
        <TabPanels>
          {/* Current Configuration Tab */}
          <TabPanel>
            <Card className="border-gray-700 bg-gray-900/50">
              {configData ? (
                <div className="space-y-4">
                  {/* Header with version info and edit button */}
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-white">
                        {MODEL_NAMES[selectedModel]} Configuration
                      </h3>
                      <p className="text-sm text-gray-400">
                        Version {configData.version}
                        {configData.change_description && ` - ${configData.change_description}`}
                      </p>
                    </div>
                    <Button icon={Edit} onClick={() => setIsEditorOpen(true)}>
                      Edit
                    </Button>
                  </div>

                  {/* Config display */}
                  <div className="rounded-lg border border-gray-700 bg-gray-950 p-4">
                    <pre className="overflow-x-auto text-sm text-gray-300">
                      {JSON.stringify(configData.config, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400">No configuration found for this model.</p>
              )}
            </Card>
          </TabPanel>

          {/* Version History Tab */}
          <TabPanel>
            <Card className="border-gray-700 bg-gray-900/50">
              <div className="space-y-4">
                <h3 className="text-lg font-medium text-white">Version History</h3>
                {versions.length === 0 ? (
                  <p className="text-gray-400">No version history available.</p>
                ) : (
                  <div className="space-y-3">
                    {versions.map((version) => (
                      <div
                        key={version.id}
                        className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-950 p-4"
                      >
                        <div className="flex items-center gap-4">
                          <Clock className="h-5 w-5 text-gray-500" />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-white">
                                Version {version.version}
                              </span>
                              {version.is_active && (
                                <Badge color="green" size="xs">
                                  Active
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-400">
                              {version.change_description || 'No description'}
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatDate(version.created_at)}
                              {version.created_by && ` by ${version.created_by}`}
                            </p>
                          </div>
                        </div>
                        {!version.is_active && (
                          <Button
                            variant="secondary"
                            size="xs"
                            icon={RotateCcw}
                            onClick={() => void handleRestore(version.id)}
                            loading={restoreMutation.isPending}
                          >
                            Restore
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          </TabPanel>
        </TabPanels>
      </TabGroup>

      {/* Editor Modal */}
      {configData && (
        <PromptConfigEditor
          isOpen={isEditorOpen}
          onClose={() => setIsEditorOpen(false)}
          model={selectedModel}
          initialConfig={configData.config}
          onSave={(config, changeDescription) => void handleSave(config, changeDescription)}
          isSaving={updateMutation.isPending}
        />
      )}
    </div>
  );
}

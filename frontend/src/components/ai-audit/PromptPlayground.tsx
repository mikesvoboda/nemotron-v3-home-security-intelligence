/**
 * PromptPlayground - Interactive prompt testing and editing component
 *
 * Allows users to view, edit, and test AI model prompt configurations.
 * Supports multiple models: Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP
 *
 * Features:
 * - System prompt editor (textarea for Nemotron)
 * - Tag-based editors for other models
 * - Test functionality with before/after comparison
 * - Version history and restore
 * - Import/Export JSON
 */

import { Card, Title, Text, Badge, Button, Textarea, TextInput } from '@tremor/react';
import { clsx } from 'clsx';
import {
  X,
  Play,
  RotateCcw,
  Save,
  Download,
  Upload,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Loader2,
  History,
  Plus,
  Settings,
} from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';

// ============================================================================
// Types (matching backend schemas)
// ============================================================================

/** Supported AI models for prompt configuration */
export type AIModelEnum =
  | 'nemotron'
  | 'florence2'
  | 'yolo_world'
  | 'xclip'
  | 'fashion_clip';

/** Configuration for a specific AI model */
export interface ModelPromptConfig {
  model: AIModelEnum;
  config: Record<string, unknown>;
  version: number;
  created_at?: string | null;
  created_by?: string | null;
  change_description?: string | null;
}

/** All prompts response */
export interface AllPromptsResponse {
  version: string;
  exported_at: string;
  prompts: Record<string, Record<string, unknown>>;
}

/** Request to test a prompt */
export interface PromptTestRequest {
  model: AIModelEnum;
  config: Record<string, unknown>;
  event_id?: number | null;
  image_path?: string | null;
}

/** Result of a prompt test */
export interface PromptTestResult {
  model: AIModelEnum;
  before_score?: number | null;
  after_score?: number | null;
  before_response?: Record<string, unknown> | null;
  after_response?: Record<string, unknown> | null;
  improved?: boolean | null;
  test_duration_ms: number;
  error?: string | null;
}

/** Version history entry */
export interface PromptVersionInfo {
  id: number;
  model: AIModelEnum;
  version: number;
  created_at: string;
  created_by?: string | null;
  change_description?: string | null;
  is_active: boolean;
}

/** Recommendation from parent for pre-selecting context */
export interface RecommendationContext {
  suggestion: string;
  category: string;
  eventId?: number;
  model?: AIModelEnum;
}

// ============================================================================
// Props
// ============================================================================

export interface PromptPlaygroundProps {
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback when panel should close */
  onClose: () => void;
  /** Optional recommendation context to pre-fill */
  recommendation?: RecommendationContext;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const MODEL_INFO: Record<AIModelEnum, { label: string; description: string }> = {
  nemotron: {
    label: 'Nemotron',
    description: 'Risk Analysis Prompt - Full system prompt template',
  },
  florence2: {
    label: 'Florence-2',
    description: 'Scene Analysis Queries - Questions to ask about the scene',
  },
  yolo_world: {
    label: 'YOLO-World',
    description: 'Custom Object Classes - Objects to detect with confidence threshold',
  },
  xclip: {
    label: 'X-CLIP',
    description: 'Action Recognition Classes - Actions to identify in video',
  },
  fashion_clip: {
    label: 'Fashion-CLIP',
    description: 'Clothing Categories - Clothing types to classify',
  },
};

const DEFAULT_CONFIGS: Record<AIModelEnum, Record<string, unknown>> = {
  nemotron: {
    system_prompt: `You are a security analyst assessing risk from camera detections.

## Detection Context
{detections}

## Cross-Camera Activity
{cross_camera_data}

## Enrichment Data
{enrichment}

Analyze the scene and provide a risk assessment from 0-100.`,
  },
  florence2: {
    queries: [
      'What is the person doing?',
      'What objects are they carrying?',
      'Describe the environment',
      'Is there anything unusual in this scene?',
    ],
  },
  yolo_world: {
    classes: ['knife', 'gun', 'package', 'crowbar', 'spray paint'],
    confidence_threshold: 0.35,
  },
  xclip: {
    action_classes: ['loitering', 'running away', 'fighting', 'breaking in', 'climbing fence'],
  },
  fashion_clip: {
    clothing_categories: ['dark hoodie', 'face mask', 'delivery uniform', 'high-vis vest'],
  },
};

// ============================================================================
// Component
// ============================================================================

export default function PromptPlayground({
  isOpen,
  onClose,
  recommendation,
  className,
}: PromptPlaygroundProps) {
  // State for all model configs
  const [configs, setConfigs] = useState<Record<AIModelEnum, Record<string, unknown>>>(DEFAULT_CONFIGS);
  const [originalConfigs, setOriginalConfigs] = useState<Record<AIModelEnum, Record<string, unknown>>>(DEFAULT_CONFIGS);

  // UI state
  const [expandedModels, setExpandedModels] = useState<Set<AIModelEnum>>(new Set(['nemotron']));
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Test state
  const [testEventId, setTestEventId] = useState<string>('');
  const [testResults, setTestResults] = useState<Record<AIModelEnum, PromptTestResult | null>>({
    nemotron: null,
    florence2: null,
    yolo_world: null,
    xclip: null,
    fashion_clip: null,
  });

  // Version history state
  const [showHistory, setShowHistory] = useState(false);
  const [versionHistory, setVersionHistory] = useState<PromptVersionInfo[]>([]);

  // Load initial configs
  const loadConfigs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/ai-audit/prompts');
      if (!response.ok) {
        throw new Error(`Failed to load prompts: ${response.statusText}`);
      }
      const data = (await response.json()) as AllPromptsResponse;

      const loadedConfigs: Record<AIModelEnum, Record<string, unknown>> = { ...DEFAULT_CONFIGS };
      for (const [model, config] of Object.entries(data.prompts)) {
        if (model in loadedConfigs) {
          loadedConfigs[model as AIModelEnum] = config;
        }
      }

      setConfigs(loadedConfigs);
      setOriginalConfigs(loadedConfigs);
    } catch (err) {
      console.error('Failed to load prompts:', err);
      setError(err instanceof Error ? err.message : 'Failed to load prompts');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load history
  const loadHistory = useCallback(async () => {
    try {
      const response = await fetch('/api/ai-audit/prompts/history?limit=20');
      if (response.ok) {
        const data = (await response.json()) as { versions?: PromptVersionInfo[] };
        setVersionHistory(data.versions ?? []);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (isOpen) {
      void loadConfigs();
      void loadHistory();
    }
  }, [isOpen, loadConfigs, loadHistory]);

  // Expand relevant model when recommendation changes
  useEffect(() => {
    if (recommendation?.model) {
      const modelToExpand = recommendation.model;
      setExpandedModels((prev) => new Set([...prev, modelToExpand]));
    }
  }, [recommendation]);

  // Toggle model expansion
  const toggleModel = (model: AIModelEnum) => {
    setExpandedModels((prev) => {
      const next = new Set(prev);
      if (next.has(model)) {
        next.delete(model);
      } else {
        next.add(model);
      }
      return next;
    });
  };

  // Update config for a model
  const updateConfig = (model: AIModelEnum, key: string, value: unknown) => {
    setConfigs((prev) => ({
      ...prev,
      [model]: {
        ...prev[model],
        [key]: value,
      },
    }));
  };

  // Reset config for a model
  const resetConfig = (model: AIModelEnum) => {
    setConfigs((prev) => ({
      ...prev,
      [model]: originalConfigs[model],
    }));
    setTestResults((prev) => ({
      ...prev,
      [model]: null,
    }));
  };

  // Test a model config
  const runTest = async (model: AIModelEnum) => {
    setIsTesting(true);
    setError(null);

    try {
      const request: PromptTestRequest = {
        model,
        config: configs[model],
        event_id: testEventId ? parseInt(testEventId, 10) : undefined,
      };

      const response = await fetch('/api/ai-audit/prompts/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`Test failed: ${response.statusText}`);
      }

      const result = (await response.json()) as PromptTestResult;
      setTestResults((prev) => ({
        ...prev,
        [model]: result,
      }));

      if (result.error) {
        setError(`Test error: ${result.error}`);
      }
    } catch (err) {
      console.error('Test failed:', err);
      setError(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setIsTesting(false);
    }
  };

  // Save all configs
  const saveAll = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const models = Object.keys(configs) as AIModelEnum[];
      let savedCount = 0;

      for (const model of models) {
        // Only save if config has changed
        if (JSON.stringify(configs[model]) !== JSON.stringify(originalConfigs[model])) {
          const response = await fetch(`/api/ai-audit/prompts/${model}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              config: configs[model],
              change_description: 'Updated via Prompt Playground',
            }),
          });

          if (!response.ok) {
            throw new Error(`Failed to save ${model}: ${response.statusText}`);
          }
          savedCount++;
        }
      }

      if (savedCount > 0) {
        setOriginalConfigs({ ...configs });
        setSuccessMessage(`Saved ${savedCount} configuration(s)`);
        void loadHistory();
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        setSuccessMessage('No changes to save');
        setTimeout(() => setSuccessMessage(null), 3000);
      }
    } catch (err) {
      console.error('Save failed:', err);
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setIsSaving(false);
    }
  }, [configs, originalConfigs, loadHistory]);

  // Export configs as JSON
  const exportConfigs = () => {
    const exportData = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      prompts: configs,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prompt-configs-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Import configs from JSON
  const importConfigs = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        const text = await file.text();
        const data = JSON.parse(text) as AllPromptsResponse;

        if (data.version !== '1.0' || !data.prompts) {
          throw new Error('Invalid configuration file format');
        }

        const importedConfigs: Record<AIModelEnum, Record<string, unknown>> = { ...configs };
        for (const [model, config] of Object.entries(data.prompts)) {
          if (model in importedConfigs) {
            importedConfigs[model as AIModelEnum] = config;
          }
        }

        setConfigs(importedConfigs);
        setSuccessMessage('Configurations imported. Review and save to apply.');
        setTimeout(() => setSuccessMessage(null), 5000);
      } catch (err) {
        console.error('Import failed:', err);
        setError(err instanceof Error ? err.message : 'Failed to import configuration');
      }
    };
    input.click();
  };

  // Restore a version
  const restoreVersion = async (versionId: number) => {
    try {
      const response = await fetch(`/api/ai-audit/prompts/history/${versionId}`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`Failed to restore version: ${response.statusText}`);
      }

      setSuccessMessage('Version restored. Reloading configurations...');
      void loadConfigs();
      void loadHistory();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Restore failed:', err);
      setError(err instanceof Error ? err.message : 'Restore failed');
    }
  };

  // Check if there are unsaved changes
  const hasUnsavedChanges = JSON.stringify(configs) !== JSON.stringify(originalConfigs);

  // Handle close with unsaved changes warning
  const handleClose = useCallback(() => {
    if (hasUnsavedChanges) {
      if (window.confirm('You have unsaved changes. Are you sure you want to close?')) {
        onClose();
      }
    } else {
      onClose();
    }
  }, [hasUnsavedChanges, onClose]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      // Escape to close
      if (e.key === 'Escape') {
        handleClose();
      }

      // Ctrl/Cmd + S to save
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        void saveAll();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, hasUnsavedChanges, handleClose, saveAll]);

  if (!isOpen) return null;

  return (
    <div
      className={clsx(
        'fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-[#121212] shadow-2xl lg:w-4/5',
        'transform transition-transform duration-300 ease-out',
        isOpen ? 'translate-x-0' : 'translate-x-full',
        className
      )}
      data-testid="prompt-playground"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prompt-playground-title"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 bg-[#1A1A1A] px-6 py-4">
        <div>
          <h2 id="prompt-playground-title" className="flex items-center gap-2 text-xl font-bold text-white">
            <Settings className="h-5 w-5 text-[#76B900]" />
            Prompt Playground
          </h2>
          {recommendation && (
            <Text className="mt-1 text-sm text-gray-400">
              Recommendation: &quot;{recommendation.suggestion}&quot;
            </Text>
          )}
        </div>
        <button
          onClick={handleClose}
          className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          aria-label="Close panel"
          data-testid="close-button"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Status messages */}
      {error && (
        <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 p-3" data-testid="error-message">
          <AlertCircle className="h-4 w-4 text-red-500" />
          <Text className="text-sm text-red-400">{error}</Text>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 p-3" data-testid="success-message">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <Text className="text-sm text-green-400">{successMessage}</Text>
        </div>
      )}

      {/* Test Input */}
      <div className="border-b border-gray-800 bg-[#1A1A1A] px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label htmlFor="test-event-id" className="mb-1 block text-sm text-gray-400">
              Test Event ID (optional)
            </label>
            <TextInput
              id="test-event-id"
              placeholder="Enter event ID to test against"
              value={testEventId}
              onChange={(e) => setTestEventId(e.target.value)}
              className="max-w-xs"
              data-testid="test-event-input"
            />
          </div>
          {hasUnsavedChanges && (
            <Badge color="yellow" size="sm">
              Unsaved changes
            </Badge>
          )}
        </div>
      </div>

      {/* Main content - scrollable */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex h-64 items-center justify-center" data-testid="loading-state">
            <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Model editors */}
            {(Object.keys(MODEL_INFO) as AIModelEnum[]).map((model) => (
              <ModelEditor
                key={model}
                model={model}
                config={configs[model]}
                isExpanded={expandedModels.has(model)}
                onToggle={() => toggleModel(model)}
                onUpdate={(key, value) => updateConfig(model, key, value)}
                onReset={() => resetConfig(model)}
                onTest={() => void runTest(model)}
                testResult={testResults[model]}
                isTesting={isTesting}
                isHighlighted={recommendation?.model === model}
              />
            ))}

            {/* Version History */}
            <Card className="border-gray-800 bg-[#1A1A1A]" data-testid="version-history-section">
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="flex w-full items-center justify-between text-left"
                data-testid="version-history-toggle"
              >
                <Title className="flex items-center gap-2 text-white">
                  <History className="h-5 w-5 text-[#76B900]" />
                  Version History
                </Title>
                {showHistory ? (
                  <ChevronDown className="h-5 w-5 text-gray-400" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-gray-400" />
                )}
              </button>

              {showHistory && (
                <div className="mt-4 space-y-2" data-testid="version-history-list">
                  {versionHistory.length === 0 ? (
                    <Text className="text-sm text-gray-500">No version history available</Text>
                  ) : (
                    versionHistory.map((version) => (
                      <div
                        key={version.id}
                        className="flex items-center justify-between rounded-lg bg-gray-900/50 p-3"
                      >
                        <div>
                          <Text className="text-sm font-medium text-white">
                            {MODEL_INFO[version.model]?.label || version.model} v{version.version}
                          </Text>
                          <Text className="text-xs text-gray-500">
                            {new Date(version.created_at).toLocaleString()}
                            {version.change_description && ` - ${version.change_description}`}
                          </Text>
                        </div>
                        <div className="flex items-center gap-2">
                          {version.is_active && (
                            <Badge color="green" size="xs">Active</Badge>
                          )}
                          {!version.is_active && (
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={() => void restoreVersion(version.id)}
                              data-testid={`restore-version-${version.id}`}
                            >
                              Restore
                            </Button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-gray-800 bg-[#1A1A1A] px-6 py-4">
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={exportConfigs}
            icon={Download}
            data-testid="export-button"
          >
            Export JSON
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={importConfigs}
            icon={Upload}
            data-testid="import-button"
          >
            Import JSON
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleClose}
            data-testid="cancel-button"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => void saveAll()}
            disabled={isSaving || !hasUnsavedChanges}
            icon={isSaving ? Loader2 : Save}
            className="bg-[#76B900] text-black hover:bg-[#8ACE00]"
            data-testid="save-button"
          >
            {isSaving ? 'Saving...' : 'Save All'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// ModelEditor Component
// ============================================================================

interface ModelEditorProps {
  model: AIModelEnum;
  config: Record<string, unknown>;
  isExpanded: boolean;
  onToggle: () => void;
  onUpdate: (key: string, value: unknown) => void;
  onReset: () => void;
  onTest: () => void;
  testResult: PromptTestResult | null;
  isTesting: boolean;
  isHighlighted: boolean;
}

function ModelEditor({
  model,
  config,
  isExpanded,
  onToggle,
  onUpdate,
  onReset,
  onTest,
  testResult,
  isTesting,
  isHighlighted,
}: ModelEditorProps) {
  const info = MODEL_INFO[model];

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A]',
        isHighlighted && 'ring-2 ring-[#76B900]'
      )}
      data-testid={`model-editor-${model}`}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
        aria-expanded={isExpanded}
        data-testid={`model-toggle-${model}`}
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronRight className="h-5 w-5 text-gray-400" />
          )}
          <div>
            <Title className="text-white">{info.label}</Title>
            <Text className="text-sm text-gray-400">{info.description}</Text>
          </div>
        </div>
        {testResult && (
          <TestResultBadge result={testResult} />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="mt-4 space-y-4" data-testid={`model-content-${model}`}>
          {/* Model-specific editor */}
          {model === 'nemotron' && (
            <NemotronEditor
              config={config}
              onUpdate={onUpdate}
            />
          )}
          {model === 'florence2' && (
            <ListEditor
              items={(config.queries as string[]) || []}
              onUpdate={(items) => onUpdate('queries', items)}
              placeholder="Add query..."
              label="Scene Analysis Queries"
            />
          )}
          {model === 'yolo_world' && (
            <YoloWorldEditor
              config={config}
              onUpdate={onUpdate}
            />
          )}
          {model === 'xclip' && (
            <ListEditor
              items={(config.action_classes as string[]) || []}
              onUpdate={(items) => onUpdate('action_classes', items)}
              placeholder="Add action..."
              label="Action Recognition Classes"
            />
          )}
          {model === 'fashion_clip' && (
            <ListEditor
              items={(config.clothing_categories as string[]) || []}
              onUpdate={(items) => onUpdate('clothing_categories', items)}
              placeholder="Add category..."
              label="Clothing Categories"
            />
          )}

          {/* Test result details */}
          {testResult && (
            <TestResultDetails result={testResult} />
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2">
            <Button
              size="xs"
              variant="secondary"
              onClick={onTest}
              disabled={isTesting}
              icon={isTesting ? Loader2 : Play}
              data-testid={`test-button-${model}`}
            >
              {isTesting ? 'Testing...' : 'Run Test'}
            </Button>
            <Button
              size="xs"
              variant="secondary"
              onClick={onReset}
              icon={RotateCcw}
              data-testid={`reset-button-${model}`}
            >
              Reset
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// NemotronEditor Component
// ============================================================================

interface NemotronEditorProps {
  config: Record<string, unknown>;
  onUpdate: (key: string, value: unknown) => void;
}

function NemotronEditor({ config, onUpdate }: NemotronEditorProps) {
  const systemPrompt = (config.system_prompt as string) || '';

  return (
    <div data-testid="nemotron-editor">
      <label htmlFor="system-prompt" className="mb-2 block text-sm font-medium text-gray-300">
        System Prompt
      </label>
      <Textarea
        id="system-prompt"
        value={systemPrompt}
        onChange={(e) => onUpdate('system_prompt', e.target.value)}
        rows={12}
        className="font-mono text-sm"
        placeholder="Enter system prompt template..."
        data-testid="system-prompt-textarea"
      />
      <Text className="mt-2 text-xs text-gray-500">
        Available variables: {'{detections}'}, {'{cross_camera_data}'}, {'{enrichment}'}
      </Text>
    </div>
  );
}

// ============================================================================
// ListEditor Component (for tag-based inputs)
// ============================================================================

interface ListEditorProps {
  items: string[];
  onUpdate: (items: string[]) => void;
  placeholder: string;
  label: string;
}

function ListEditor({ items, onUpdate, placeholder, label }: ListEditorProps) {
  const [newItem, setNewItem] = useState('');

  const addItem = () => {
    if (newItem.trim() && !items.includes(newItem.trim())) {
      onUpdate([...items, newItem.trim()]);
      setNewItem('');
    }
  };

  const removeItem = (index: number) => {
    const updated = items.filter((_, i) => i !== index);
    onUpdate(updated);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addItem();
    }
  };

  return (
    <div data-testid="list-editor">
      <label className="mb-2 block text-sm font-medium text-gray-300">{label}</label>
      <div className="flex flex-wrap gap-2 mb-3">
        {items.map((item, index) => (
          <Badge
            key={index}
            color="gray"
            className="flex items-center gap-1 pr-1"
          >
            {item}
            <button
              onClick={() => removeItem(index)}
              className="ml-1 rounded p-0.5 hover:bg-gray-700"
              aria-label={`Remove ${item}`}
              data-testid={`remove-item-${index}`}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <TextInput
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          className="flex-1"
          data-testid="new-item-input"
        />
        <Button
          size="xs"
          variant="secondary"
          onClick={addItem}
          icon={Plus}
          disabled={!newItem.trim()}
          data-testid="add-item-button"
        >
          Add
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// YoloWorldEditor Component
// ============================================================================

interface YoloWorldEditorProps {
  config: Record<string, unknown>;
  onUpdate: (key: string, value: unknown) => void;
}

function YoloWorldEditor({ config, onUpdate }: YoloWorldEditorProps) {
  const classes = (config.classes as string[]) || [];
  const threshold = (config.confidence_threshold as number) || 0.35;

  const [newClass, setNewClass] = useState('');

  const addClass = () => {
    if (newClass.trim() && !classes.includes(newClass.trim())) {
      onUpdate('classes', [...classes, newClass.trim()]);
      setNewClass('');
    }
  };

  const removeClass = (index: number) => {
    const updated = classes.filter((_, i) => i !== index);
    onUpdate('classes', updated);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addClass();
    }
  };

  return (
    <div className="space-y-4" data-testid="yolo-world-editor">
      {/* Classes */}
      <div>
        <label htmlFor="yolo-new-class-input" className="mb-2 block text-sm font-medium text-gray-300">
          Custom Object Classes
        </label>
        <div className="flex flex-wrap gap-2 mb-3">
          {classes.map((cls, index) => (
            <Badge
              key={index}
              color="gray"
              className="flex items-center gap-1 pr-1"
            >
              {cls}
              <button
                onClick={() => removeClass(index)}
                className="ml-1 rounded p-0.5 hover:bg-gray-700"
                aria-label={`Remove ${cls}`}
                data-testid={`remove-class-${index}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <TextInput
            id="yolo-new-class-input"
            value={newClass}
            onChange={(e) => setNewClass(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Add class..."
            className="flex-1"
            data-testid="new-class-input"
          />
          <Button
            size="xs"
            variant="secondary"
            onClick={addClass}
            icon={Plus}
            disabled={!newClass.trim()}
            data-testid="add-class-button"
          >
            Add
          </Button>
        </div>
      </div>

      {/* Confidence threshold slider */}
      <div>
        <label htmlFor="confidence-threshold" className="mb-2 block text-sm font-medium text-gray-300">
          Confidence Threshold: {(threshold * 100).toFixed(0)}%
        </label>
        <input
          id="confidence-threshold"
          type="range"
          min="0"
          max="100"
          value={threshold * 100}
          onChange={(e) => onUpdate('confidence_threshold', parseInt(e.target.value, 10) / 100)}
          className="w-full accent-[#76B900]"
          data-testid="confidence-slider"
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// TestResultBadge Component
// ============================================================================

interface TestResultBadgeProps {
  result: PromptTestResult;
}

function TestResultBadge({ result }: TestResultBadgeProps) {
  if (result.error) {
    return (
      <Badge color="red" size="sm">
        Error
      </Badge>
    );
  }

  if (result.improved === true) {
    return (
      <Badge color="green" size="sm">
        Improved
      </Badge>
    );
  }

  if (result.improved === false) {
    return (
      <Badge color="yellow" size="sm">
        No Improvement
      </Badge>
    );
  }

  return (
    <Badge color="gray" size="sm">
      Tested
    </Badge>
  );
}

// ============================================================================
// TestResultDetails Component
// ============================================================================

interface TestResultDetailsProps {
  result: PromptTestResult;
}

function TestResultDetails({ result }: TestResultDetailsProps) {
  return (
    <div className="rounded-lg bg-gray-900/50 p-4" data-testid="test-result-details">
      <Text className="mb-2 text-sm font-medium text-gray-300">Test Results</Text>

      {result.error ? (
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <Text className="text-sm">{result.error}</Text>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-4">
            <div>
              <Text className="text-xs text-gray-500">Before</Text>
              <Text className="text-lg font-bold text-white">
                {result.before_score ?? 'N/A'}
              </Text>
            </div>
            <div className="text-gray-600">-&gt;</div>
            <div>
              <Text className="text-xs text-gray-500">After</Text>
              <Text className={clsx(
                'text-lg font-bold',
                result.improved ? 'text-green-400' : result.improved === false ? 'text-yellow-400' : 'text-white'
              )}>
                {result.after_score ?? 'N/A'}
              </Text>
            </div>
            {result.improved !== null && (
              <Badge color={result.improved ? 'green' : 'yellow'} size="sm" className="ml-auto">
                {result.improved ? 'Improved' : 'No Change'}
              </Badge>
            )}
          </div>
          <Text className="text-xs text-gray-500">
            Test duration: {result.test_duration_ms}ms
          </Text>
        </div>
      )}
    </div>
  );
}

/**
 * PromptPlayground - Slide-out panel for editing, testing, and refining AI model prompts
 *
 * Features:
 * - Slide-out panel from right (80% viewport width)
 * - Model-specific editors (Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP)
 * - Test functionality with before/after comparison
 * - Save, Export, and Import capabilities
 * - Keyboard shortcuts (Escape to close)
 *
 * @see backend/api/routes/ai_audit.py - Prompt Playground API endpoints
 */

import { Dialog, Transition, Disclosure } from '@headlessui/react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  Download,
  FlaskConical,
  Loader2,
  RotateCcw,
  Save,
  Upload,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchAllPrompts,
  updateModelPrompt,
  testPrompt,
  exportPrompts,
  importPrompts,
  ApiError,
} from '../../services/api';

import type {
  AllPromptsResponse,
  PromptModelName,
  PromptTestResponse,
  AiAuditRecommendationItem,
} from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export interface PromptPlaygroundProps {
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback when panel should close */
  onClose: () => void;
  /** Optional recommendation that triggered the panel */
  recommendation?: AiAuditRecommendationItem | null;
  /** Optional source event ID */
  sourceEventId?: number | null;
}

interface ModelConfig {
  name: PromptModelName;
  displayName: string;
  description: string;
  variables?: string[];
}

// ============================================================================
// Constants
// ============================================================================

const MODEL_CONFIGS: ModelConfig[] = [
  {
    name: 'nemotron',
    displayName: 'Nemotron',
    description: 'Primary LLM for risk analysis and reasoning',
    variables: ['{detections}', '{cross_camera_data}', '{weather}', '{time_context}'],
  },
  {
    name: 'florence2',
    displayName: 'Florence-2',
    description: 'Visual question-answering model',
  },
  {
    name: 'yolo_world',
    displayName: 'YOLO-World',
    description: 'Open-vocabulary object detection',
  },
  {
    name: 'xclip',
    displayName: 'X-CLIP',
    description: 'Action recognition model',
  },
  {
    name: 'fashion_clip',
    displayName: 'Fashion-CLIP',
    description: 'Clothing and appearance analysis',
  },
];

// ============================================================================
// Component
// ============================================================================

export default function PromptPlayground({
  isOpen,
  onClose,
  recommendation,
  sourceEventId,
}: PromptPlaygroundProps) {
  // State for prompts
  const [prompts, setPrompts] = useState<AllPromptsResponse | null>(null);
  const [editedConfigs, setEditedConfigs] = useState<Record<string, Record<string, unknown>>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for saving
  const [savingModel, setSavingModel] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  // State for testing
  const [testEventId, setTestEventId] = useState<string>('');
  const [testingModel, setTestingModel] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<PromptTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // State for import/export
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load prompts when panel opens
  const loadPrompts = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await fetchAllPrompts();
      setPrompts(data);

      // Initialize edited configs from fetched data
      const initialConfigs: Record<string, Record<string, unknown>> = {};
      for (const [modelName, modelData] of Object.entries(data.prompts)) {
        initialConfigs[modelName] = { ...modelData.config };
      }
      setEditedConfigs(initialConfigs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prompts');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      void loadPrompts();
      // Set test event ID from source if provided
      if (sourceEventId) {
        setTestEventId(String(sourceEventId));
      }
    }
  }, [isOpen, loadPrompts, sourceEventId]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Update config value
  const updateConfigValue = (modelName: string, key: string, value: unknown) => {
    setEditedConfigs((prev) => ({
      ...prev,
      [modelName]: {
        ...prev[modelName],
        [key]: value,
      },
    }));
    // Clear any previous success message when editing
    setSaveSuccess(null);
  };

  // Check if config has been modified
  const isModified = (modelName: string): boolean => {
    if (!prompts?.prompts[modelName]) return false;
    const original = prompts.prompts[modelName].config;
    const edited = editedConfigs[modelName];
    return JSON.stringify(original) !== JSON.stringify(edited);
  };

  // Save model config
  const handleSave = async (modelName: PromptModelName) => {
    setSavingModel(modelName);
    setSaveSuccess(null);
    setError(null);

    try {
      const config = editedConfigs[modelName];
      await updateModelPrompt(modelName, config, `Updated via Prompt Playground`);

      // Reload prompts to get updated version
      await loadPrompts();
      setSaveSuccess(modelName);

      // Clear success message after 3 seconds
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to save configuration');
      }
    } finally {
      setSavingModel(null);
    }
  };

  // Reset config to original
  const handleReset = (modelName: string) => {
    if (!prompts?.prompts[modelName]) return;
    setEditedConfigs((prev) => ({
      ...prev,
      [modelName]: { ...prompts.prompts[modelName].config },
    }));
    setSaveSuccess(null);
  };

  // Test config
  const handleTest = async (modelName: PromptModelName) => {
    const eventId = parseInt(testEventId, 10);
    if (isNaN(eventId) || eventId <= 0) {
      setTestError('Please enter a valid Event ID');
      return;
    }

    setTestingModel(modelName);
    setTestError(null);
    setTestResult(null);

    try {
      const config = editedConfigs[modelName];
      const result = await testPrompt(modelName, config, eventId);
      setTestResult(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setTestError(err.message);
      } else {
        setTestError('Failed to run test');
      }
    } finally {
      setTestingModel(null);
    }
  };

  // Export all configs
  const handleExport = async () => {
    setIsExporting(true);

    try {
      const exportData = await exportPrompts();

      // Create downloadable file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `prompt-configs-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      setError('Failed to export configurations');
    } finally {
      setIsExporting(false);
    }
  };

  // Import configs
  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setImportError(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text) as { prompts?: Record<string, Record<string, unknown>> };

      if (!data.prompts) {
        throw new Error('Invalid import file format');
      }

      const result = await importPrompts(data.prompts, true);

      if (result.errors.length > 0) {
        setImportError(`Import completed with errors: ${result.errors.join(', ')}`);
      }

      // Reload prompts
      await loadPrompts();
    } catch (err) {
      if (err instanceof SyntaxError) {
        setImportError('Invalid JSON file');
      } else {
        setImportError(err instanceof Error ? err.message : 'Failed to import configurations');
      }
    } finally {
      setIsImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Render model editor based on model type
  const renderModelEditor = (model: ModelConfig) => {
    const modelName = model.name;
    const config = editedConfigs[modelName] || {};

    switch (modelName) {
      case 'nemotron':
        return (
          <div className="space-y-4">
            {/* Variables hint */}
            {model.variables && (
              <div className="rounded-lg bg-black/30 p-3">
                <p className="text-xs text-gray-400">
                  Available variables:{' '}
                  {model.variables.map((v, i) => (
                    <code key={i} className="mx-1 rounded bg-gray-800 px-1 py-0.5 text-[#76B900]">
                      {v}
                    </code>
                  ))}
                </p>
              </div>
            )}

            {/* System prompt textarea */}
            <div>
              <label htmlFor={`${modelName}-system-prompt-input`} className="mb-2 block text-sm font-medium text-gray-300">System Prompt</label>
              <textarea
                id={`${modelName}-system-prompt-input`}
                value={typeof config.system_prompt === 'string' ? config.system_prompt : ''}
                onChange={(e) => updateConfigValue(modelName, 'system_prompt', e.target.value)}
                className="h-64 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                placeholder="Enter system prompt..."
                data-testid={`${modelName}-system-prompt`}
              />
            </div>

            {/* Temperature slider */}
            <div>
              <label htmlFor={`${modelName}-temperature-input`} className="mb-2 block text-sm font-medium text-gray-300">
                Temperature: {Number(config.temperature || 0.7).toFixed(2)}
              </label>
              <input
                id={`${modelName}-temperature-input`}
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={Number(config.temperature || 0.7)}
                onChange={(e) =>
                  updateConfigValue(modelName, 'temperature', parseFloat(e.target.value))
                }
                className="w-full accent-[#76B900]"
                data-testid={`${modelName}-temperature`}
              />
            </div>

            {/* Max tokens */}
            <div>
              <label htmlFor={`${modelName}-max-tokens-input`} className="mb-2 block text-sm font-medium text-gray-300">Max Tokens</label>
              <input
                id={`${modelName}-max-tokens-input`}
                type="number"
                min="100"
                max="8192"
                value={Number(config.max_tokens || 2048)}
                onChange={(e) =>
                  updateConfigValue(modelName, 'max_tokens', parseInt(e.target.value, 10))
                }
                className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                data-testid={`${modelName}-max-tokens`}
              />
            </div>
          </div>
        );

      case 'florence2':
        return (
          <div className="space-y-4">
            <label htmlFor={`${modelName}-vqa-queries-input`} className="mb-2 block text-sm font-medium text-gray-300">VQA Queries</label>
            <p className="text-xs text-gray-500">
              Enter one query per line. These are the visual questions asked about each image.
            </p>
            <textarea
              id={`${modelName}-vqa-queries-input`}
              value={Array.isArray(config.vqa_queries) ? config.vqa_queries.join('\n') : ''}
              onChange={(e) =>
                updateConfigValue(
                  modelName,
                  'vqa_queries',
                  e.target.value.split('\n').filter((q) => q.trim())
                )
              }
              className="h-48 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
              placeholder="What is happening in this image?&#10;Are there any people present?&#10;Describe any vehicles visible."
              data-testid={`${modelName}-vqa-queries`}
            />
          </div>
        );

      case 'yolo_world':
        return (
          <div className="space-y-4">
            <div>
              <label htmlFor={`${modelName}-object-classes-input`} className="mb-2 block text-sm font-medium text-gray-300">Object Classes</label>
              <p className="text-xs text-gray-500">
                Enter one class per line. These are the objects to detect.
              </p>
              <textarea
                id={`${modelName}-object-classes-input`}
                value={
                  Array.isArray(config.object_classes) ? config.object_classes.join('\n') : ''
                }
                onChange={(e) =>
                  updateConfigValue(
                    modelName,
                    'object_classes',
                    e.target.value.split('\n').filter((c) => c.trim())
                  )
                }
                className="h-32 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                placeholder="person&#10;vehicle&#10;package&#10;animal"
                data-testid={`${modelName}-object-classes`}
              />
            </div>

            <div>
              <label htmlFor={`${modelName}-confidence-input`} className="mb-2 block text-sm font-medium text-gray-300">
                Confidence Threshold: {Number(config.confidence_threshold || 0.5).toFixed(2)}
              </label>
              <input
                id={`${modelName}-confidence-input`}
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={Number(config.confidence_threshold || 0.5)}
                onChange={(e) =>
                  updateConfigValue(modelName, 'confidence_threshold', parseFloat(e.target.value))
                }
                className="w-full accent-[#76B900]"
                data-testid={`${modelName}-confidence`}
              />
            </div>
          </div>
        );

      case 'xclip':
        return (
          <div className="space-y-4">
            <label htmlFor={`${modelName}-action-classes-input`} className="mb-2 block text-sm font-medium text-gray-300">Action Classes</label>
            <p className="text-xs text-gray-500">
              Enter one action per line. These are the actions to recognize in video clips.
            </p>
            <textarea
              id={`${modelName}-action-classes-input`}
              value={Array.isArray(config.action_classes) ? config.action_classes.join('\n') : ''}
              onChange={(e) =>
                updateConfigValue(
                  modelName,
                  'action_classes',
                  e.target.value.split('\n').filter((a) => a.trim())
                )
              }
              className="h-48 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
              placeholder="walking&#10;running&#10;fighting&#10;loitering"
              data-testid={`${modelName}-action-classes`}
            />
          </div>
        );

      case 'fashion_clip':
        return (
          <div className="space-y-4">
            <div>
              <label htmlFor={`${modelName}-clothing-categories-input`} className="mb-2 block text-sm font-medium text-gray-300">
                Clothing Categories
              </label>
              <p className="text-xs text-gray-500">Enter one category per line.</p>
              <textarea
                id={`${modelName}-clothing-categories-input`}
                value={
                  Array.isArray(config.clothing_categories)
                    ? config.clothing_categories.join('\n')
                    : ''
                }
                onChange={(e) =>
                  updateConfigValue(
                    modelName,
                    'clothing_categories',
                    e.target.value.split('\n').filter((c) => c.trim())
                  )
                }
                className="h-32 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                placeholder="casual&#10;formal&#10;athletic&#10;uniform"
                data-testid={`${modelName}-clothing-categories`}
              />
            </div>

            <div>
              <label htmlFor={`${modelName}-suspicious-indicators-input`} className="mb-2 block text-sm font-medium text-gray-300">
                Suspicious Indicators
              </label>
              <p className="text-xs text-gray-500">
                Enter one indicator per line. Clothing patterns that indicate suspicious activity.
              </p>
              <textarea
                id={`${modelName}-suspicious-indicators-input`}
                value={
                  Array.isArray(config.suspicious_indicators)
                    ? config.suspicious_indicators.join('\n')
                    : ''
                }
                onChange={(e) =>
                  updateConfigValue(
                    modelName,
                    'suspicious_indicators',
                    e.target.value.split('\n').filter((s) => s.trim())
                  )
                }
                className="h-32 w-full resize-y rounded-lg border border-gray-700 bg-black/30 p-3 font-mono text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                placeholder="all black&#10;face mask&#10;hoodie up&#10;gloves at night"
                data-testid={`${modelName}-suspicious-indicators`}
              />
            </div>
          </div>
        );

      default:
        return (
          <div className="text-gray-400">
            Configuration editor not available for {model.displayName}
          </div>
        );
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60" aria-hidden="true" onClick={onClose} />
        </Transition.Child>

        {/* Panel container */}
        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in duration-200"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel
                  className="pointer-events-auto relative w-screen max-w-[80vw]"
                  data-testid="prompt-playground-panel"
                >
                  <div className="flex h-full flex-col overflow-y-auto border-l border-gray-800 bg-[#1A1A1A] shadow-xl">
                    {/* Header */}
                    <div className="flex flex-shrink-0 items-start justify-between border-b border-gray-800 bg-[#121212] p-6">
                      <div>
                        <Dialog.Title as="h2" className="text-2xl font-bold text-white">
                          Prompt Playground
                        </Dialog.Title>
                        <p className="mt-1 text-sm text-gray-400">
                          Edit, test, and refine AI model prompts and configurations
                        </p>

                        {/* Recommendation context */}
                        {recommendation && (
                          <div className="mt-3 rounded-lg border border-[#76B900]/30 bg-[#76B900]/10 p-3">
                            <p className="text-sm text-[#76B900]">
                              <span className="font-medium">Suggestion:</span>{' '}
                              {recommendation.suggestion}
                            </p>
                            {sourceEventId && (
                              <p className="mt-1 text-xs text-gray-400">
                                Source Event:{' '}
                                <a
                                  href={`/timeline?event=${sourceEventId}`}
                                  className="text-[#76B900] hover:underline"
                                >
                                  #{sourceEventId}
                                </a>
                              </p>
                            )}
                          </div>
                        )}
                      </div>

                      <button
                        onClick={onClose}
                        className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                        aria-label="Close panel"
                        data-testid="close-panel-button"
                      >
                        <X className="h-6 w-6" />
                      </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                      {/* Error Banner */}
                      {error && (
                        <div className="mb-6 rounded-lg border border-red-800 bg-red-900/20 p-4">
                          <div className="flex items-center gap-2 text-red-400">
                            <AlertCircle className="h-5 w-5 flex-shrink-0" />
                            <span className="text-sm">{error}</span>
                          </div>
                        </div>
                      )}

                      {/* Loading State */}
                      {isLoading ? (
                        <div className="flex h-64 items-center justify-center">
                          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
                        </div>
                      ) : (
                        <div className="space-y-6">
                          {/* Model Editors */}
                          <div className="space-y-4">
                            {MODEL_CONFIGS.map((model, index) => (
                              <Disclosure key={model.name} defaultOpen={index === 0}>
                                {({ open }) => (
                                  <div className="overflow-hidden rounded-lg border border-gray-800 bg-[#121212]">
                                    <Disclosure.Button
                                      className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-800/50"
                                      data-testid={`${model.name}-accordion`}
                                    >
                                      <div className="flex items-center gap-3">
                                        <ChevronDown
                                          className={`h-5 w-5 text-gray-400 transition-transform ${
                                            open ? 'rotate-180' : ''
                                          }`}
                                        />
                                        <div>
                                          <h3 className="font-medium text-white">
                                            {model.displayName}
                                            {isModified(model.name) && (
                                              <span className="ml-2 text-xs text-[#76B900]">
                                                (modified)
                                              </span>
                                            )}
                                          </h3>
                                          <p className="text-xs text-gray-500">
                                            {model.description}
                                          </p>
                                        </div>
                                      </div>

                                      {prompts?.prompts[model.name] && (
                                        <span className="text-xs text-gray-500">
                                          v{prompts.prompts[model.name].version}
                                        </span>
                                      )}
                                    </Disclosure.Button>

                                    <Disclosure.Panel className="border-t border-gray-800 p-4">
                                      {renderModelEditor(model)}

                                      {/* Action buttons */}
                                      <div className="mt-4 flex items-center gap-3 border-t border-gray-800 pt-4">
                                        {recommendation && (
                                          <button
                                            onClick={() => {
                                              // Apply suggestion to the appropriate field
                                              if (model.name === 'nemotron') {
                                                const systemPrompt = editedConfigs[model.name]?.system_prompt;
                                                const current = typeof systemPrompt === 'string' ? systemPrompt : '';
                                                updateConfigValue(
                                                  model.name,
                                                  'system_prompt',
                                                  `${current}\n\n/* Suggestion: ${recommendation.suggestion} */`
                                                );
                                              }
                                            }}
                                            className="rounded-lg border border-[#76B900] px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/10"
                                            data-testid={`${model.name}-apply-suggestion`}
                                          >
                                            Apply Suggestion
                                          </button>
                                        )}

                                        <button
                                          onClick={() => handleReset(model.name)}
                                          disabled={!isModified(model.name)}
                                          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                                          data-testid={`${model.name}-reset`}
                                        >
                                          <RotateCcw className="h-4 w-4" />
                                          Reset
                                        </button>

                                        <button
                                          onClick={() => void handleSave(model.name)}
                                          disabled={
                                            !isModified(model.name) || savingModel === model.name
                                          }
                                          className="flex items-center gap-1.5 rounded-lg bg-[#76B900] px-3 py-1.5 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00] disabled:cursor-not-allowed disabled:opacity-50"
                                          data-testid={`${model.name}-save`}
                                        >
                                          {savingModel === model.name ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                          ) : saveSuccess === model.name ? (
                                            <CheckCircle className="h-4 w-4" />
                                          ) : (
                                            <Save className="h-4 w-4" />
                                          )}
                                          {savingModel === model.name
                                            ? 'Saving...'
                                            : saveSuccess === model.name
                                              ? 'Saved!'
                                              : 'Save'}
                                        </button>
                                      </div>
                                    </Disclosure.Panel>
                                  </div>
                                )}
                              </Disclosure>
                            ))}
                          </div>

                          {/* Test Area */}
                          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
                            <h3 className="mb-4 font-medium text-white">Test Configuration</h3>

                            <div className="flex items-end gap-4">
                              <div className="flex-1">
                                <label htmlFor="test-event-id-input" className="mb-2 block text-sm font-medium text-gray-300">
                                  Event ID
                                </label>
                                <input
                                  id="test-event-id-input"
                                  type="number"
                                  value={testEventId}
                                  onChange={(e) => {
                                    setTestEventId(e.target.value);
                                    setTestError(null);
                                  }}
                                  placeholder="Enter event ID to test against"
                                  className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]/20"
                                  data-testid="test-event-id"
                                />
                              </div>

                              <button
                                onClick={() => void handleTest('nemotron')}
                                disabled={!testEventId || testingModel !== null}
                                className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                                data-testid="run-test-button"
                              >
                                {testingModel ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <FlaskConical className="h-4 w-4" />
                                )}
                                {testingModel ? 'Testing...' : 'Run Test'}
                              </button>
                            </div>

                            {/* Test Error */}
                            {testError && (
                              <div className="mt-4 rounded-lg border border-red-800 bg-red-900/20 p-3">
                                <p className="text-sm text-red-400">{testError}</p>
                              </div>
                            )}

                            {/* Test Results */}
                            {testResult && (
                              <div className="mt-4 grid gap-4 md:grid-cols-2">
                                {/* Before */}
                                <div className="rounded-lg border border-gray-700 bg-black/30 p-4">
                                  <h4 className="mb-2 text-sm font-medium text-gray-400">Before</h4>
                                  <div className="space-y-2">
                                    <div className="flex justify-between">
                                      <span className="text-gray-400">Score:</span>
                                      <span className="font-mono text-white">
                                        {testResult.before.score}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-400">Risk Level:</span>
                                      <span className="font-mono text-white">
                                        {testResult.before.risk_level}
                                      </span>
                                    </div>
                                    <p className="mt-2 text-xs text-gray-500">
                                      {testResult.before.summary}
                                    </p>
                                  </div>
                                </div>

                                {/* Arrow */}
                                <div className="hidden items-center justify-center md:flex">
                                  <ArrowRight
                                    className={`h-8 w-8 ${testResult.improved ? 'text-green-500' : 'text-yellow-500'}`}
                                  />
                                </div>

                                {/* After */}
                                <div
                                  className={`rounded-lg border p-4 ${
                                    testResult.improved
                                      ? 'border-green-800 bg-green-900/20'
                                      : 'border-yellow-800 bg-yellow-900/20'
                                  }`}
                                >
                                  <h4 className="mb-2 text-sm font-medium text-gray-400">After</h4>
                                  <div className="space-y-2">
                                    <div className="flex justify-between">
                                      <span className="text-gray-400">Score:</span>
                                      <span className="font-mono text-white">
                                        {testResult.after.score}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-400">Risk Level:</span>
                                      <span className="font-mono text-white">
                                        {testResult.after.risk_level}
                                      </span>
                                    </div>
                                    <p className="mt-2 text-xs text-gray-500">
                                      {testResult.after.summary}
                                    </p>
                                  </div>
                                </div>

                                {/* Result summary */}
                                <div className="md:col-span-2">
                                  <div
                                    className={`flex items-center justify-between rounded-lg p-3 ${
                                      testResult.improved
                                        ? 'bg-green-900/30 text-green-400'
                                        : 'bg-yellow-900/30 text-yellow-400'
                                    }`}
                                  >
                                    <span>
                                      {testResult.improved
                                        ? 'Configuration improved results!'
                                        : 'Configuration did not improve results'}
                                    </span>
                                    <span className="text-xs opacity-75">
                                      Inference: {testResult.inference_time_ms}ms
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="flex flex-shrink-0 items-center justify-between border-t border-gray-800 bg-[#121212] p-4">
                      {/* Import Error */}
                      {importError && (
                        <div className="flex items-center gap-2 text-sm text-red-400">
                          <AlertCircle className="h-4 w-4" />
                          {importError}
                        </div>
                      )}

                      <div className="ml-auto flex items-center gap-3">
                        {/* Hidden file input */}
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".json"
                          onChange={(e) => void handleImport(e)}
                          className="hidden"
                          data-testid="import-file-input"
                        />

                        {/* Import button */}
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          disabled={isImporting}
                          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                          data-testid="import-button"
                        >
                          {isImporting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Upload className="h-4 w-4" />
                          )}
                          Import JSON
                        </button>

                        {/* Export button */}
                        <button
                          onClick={() => void handleExport()}
                          disabled={isExporting}
                          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                          data-testid="export-button"
                        >
                          {isExporting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Download className="h-4 w-4" />
                          )}
                          Export JSON
                        </button>
                      </div>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

/**
 * PromptConfigEditor - Modal for editing AI model prompt configurations
 *
 * Renders the appropriate model-specific form based on the selected model.
 * Includes a change description input for version tracking.
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Dialog, DialogPanel, Title , Button, TextInput } from '@tremor/react';
import { X } from 'lucide-react';
import { useState, useCallback, useEffect } from 'react';

import {
  NemotronConfigForm,
  Florence2ConfigForm,
  YoloWorldConfigForm,
  XClipConfigForm,
  FashionClipConfigForm,
} from './model-forms';
import { AIModelEnum } from '../../../types/promptManagement';

import type {
  NemotronConfig,
  Florence2Config,
  YoloWorldConfig,
  XClipConfig,
  FashionClipConfig,
} from '../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface PromptConfigEditorProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** The AI model being edited */
  model: AIModelEnum;
  /** Initial configuration values */
  initialConfig: Record<string, unknown>;
  /** Callback when configuration is saved */
  onSave: (config: Record<string, unknown>, changeDescription: string) => void;
  /** Whether save is in progress */
  isSaving?: boolean;
}

// Model display names
const MODEL_NAMES: Record<AIModelEnum, string> = {
  [AIModelEnum.NEMOTRON]: 'Nemotron',
  [AIModelEnum.FLORENCE2]: 'Florence-2',
  [AIModelEnum.YOLO_WORLD]: 'YOLO-World',
  [AIModelEnum.XCLIP]: 'X-CLIP',
  [AIModelEnum.FASHION_CLIP]: 'Fashion-CLIP',
};

// ============================================================================
// Component
// ============================================================================

/**
 * Modal component for editing AI model prompt configurations.
 *
 * @example
 * ```tsx
 * <PromptConfigEditor
 *   isOpen={isEditing}
 *   onClose={() => setIsEditing(false)}
 *   model={AIModelEnum.NEMOTRON}
 *   initialConfig={currentConfig}
 *   onSave={handleSave}
 * />
 * ```
 */
export default function PromptConfigEditor({
  isOpen,
  onClose,
  model,
  initialConfig,
  onSave,
  isSaving = false,
}: PromptConfigEditorProps) {
  const [config, setConfig] = useState<Record<string, unknown>>(initialConfig);
  const [changeDescription, setChangeDescription] = useState('');

  // Reset state when modal opens with new config
  useEffect(() => {
    if (isOpen) {
      setConfig(initialConfig);
      setChangeDescription('');
    }
  }, [isOpen, initialConfig]);

  // Handle save
  const handleSave = useCallback(() => {
    onSave(config, changeDescription);
  }, [config, changeDescription, onSave]);

  // Type-safe handler that wraps setConfig - uses unknown to bridge type gaps
  const handleConfigChange = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (newConfig: any) => {
      setConfig(newConfig as Record<string, unknown>);
    },
    []
  );

  // Render the appropriate form based on model type
  const renderForm = () => {
    switch (model) {
      case AIModelEnum.NEMOTRON:
        return (
          <NemotronConfigForm
            config={config as unknown as NemotronConfig}
            onChange={handleConfigChange}
            disabled={isSaving}
          />
        );
      case AIModelEnum.FLORENCE2:
        return (
          <Florence2ConfigForm
            config={config as unknown as Florence2Config}
            onChange={handleConfigChange}
            disabled={isSaving}
          />
        );
      case AIModelEnum.YOLO_WORLD:
        return (
          <YoloWorldConfigForm
            config={config as unknown as YoloWorldConfig}
            onChange={handleConfigChange}
            disabled={isSaving}
          />
        );
      case AIModelEnum.XCLIP:
        return (
          <XClipConfigForm
            config={config as unknown as XClipConfig}
            onChange={handleConfigChange}
            disabled={isSaving}
          />
        );
      case AIModelEnum.FASHION_CLIP:
        return (
          <FashionClipConfigForm
            config={config as unknown as FashionClipConfig}
            onChange={handleConfigChange}
            disabled={isSaving}
          />
        );
      default:
        return <p className="text-gray-400">Unknown model type</p>;
    }
  };

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      static={true}
    >
      <DialogPanel className="max-w-2xl border border-gray-700 bg-[#1A1A1A]">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <Title className="text-white">Edit {MODEL_NAMES[model]} Configuration</Title>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <div className="mb-6">{renderForm()}</div>

        {/* Change Description */}
        <div className="mb-6">
          <label
            htmlFor="change-description"
            className="mb-2 block text-sm font-medium text-gray-200"
          >
            Change Description
          </label>
          <TextInput
            id="change-description"
            value={changeDescription}
            onChange={(e) => setChangeDescription(e.target.value)}
            disabled={isSaving}
            placeholder="Describe what you changed and why..."
            className="bg-gray-900"
          />
          <p className="mt-1 text-xs text-gray-400">
            This description will be saved in the version history.
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={isSaving} disabled={isSaving}>
            Save Changes
          </Button>
        </div>
      </DialogPanel>
    </Dialog>
  );
}

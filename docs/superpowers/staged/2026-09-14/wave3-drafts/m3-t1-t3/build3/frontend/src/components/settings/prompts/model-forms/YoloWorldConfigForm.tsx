/**
 * YoloWorldConfigForm - Form for editing YOLO-World model configuration
 *
 * Provides controls for:
 * - classes: Tag input for custom object classes to detect
 * - confidence_threshold: Slider for detection confidence (0-1)
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Button, TextInput } from '@tremor/react';
import { Plus, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { YoloWorldConfig } from '../../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

export interface YoloWorldConfigFormProps {
  /** Current configuration values */
  config: YoloWorldConfig;
  /** Callback when configuration changes */
  onChange: (config: YoloWorldConfig) => void;
  /** Whether the form is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Form component for editing YOLO-World AI model configuration.
 *
 * @example
 * ```tsx
 * <YoloWorldConfigForm
 *   config={{ classes: ['person', 'car'], confidence_threshold: 0.5 }}
 *   onChange={setConfig}
 * />
 * ```
 */
export default function YoloWorldConfigForm({
  config,
  onChange,
  disabled = false,
}: YoloWorldConfigFormProps) {
  const [newClass, setNewClass] = useState('');

  const handleAddClass = useCallback(() => {
    if (newClass.trim() && !config.classes.includes(newClass.trim())) {
      onChange({
        ...config,
        classes: [...config.classes, newClass.trim()],
      });
      setNewClass('');
    }
  }, [config, onChange, newClass]);

  const handleRemoveClass = useCallback(
    (classToRemove: string) => {
      onChange({
        ...config,
        classes: config.classes.filter((c) => c !== classToRemove),
      });
    },
    [config, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddClass();
      }
    },
    [handleAddClass]
  );

  const handleConfidenceChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange({
        ...config,
        confidence_threshold: parseFloat(e.target.value),
      });
    },
    [config, onChange]
  );

  return (
    <div className="space-y-6" data-testid="yoloworld-config-form">
      {/* Object Classes */}
      <div>
        <span id="object-classes-label" className="mb-2 block text-sm font-medium text-gray-200">
          Object Classes
        </span>
        <p className="mb-3 text-xs text-gray-400">
          Define custom object classes for open-vocabulary detection.
        </p>

        {/* Current classes as tags */}
        <div className="mb-3 flex flex-wrap gap-2">
          {config.classes.length === 0 ? (
            <p className="text-sm italic text-gray-500">No classes defined</p>
          ) : (
            config.classes.map((cls) => (
              <span
                key={cls}
                className="inline-flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-200"
              >
                {cls}
                <button
                  type="button"
                  onClick={() => handleRemoveClass(cls)}
                  disabled={disabled}
                  className="ml-1 rounded-full p-0.5 text-gray-400 hover:bg-gray-700 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Remove class: ${cls}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))
          )}
        </div>

        {/* Add new class */}
        <div className="flex gap-2">
          <TextInput
            value={newClass}
            onChange={(e) => setNewClass(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Enter a new object class..."
            className="flex-1 bg-gray-900"
          />
          <Button
            type="button"
            onClick={handleAddClass}
            disabled={disabled || !newClass.trim()}
            variant="secondary"
            icon={Plus}
          >
            Add
          </Button>
        </div>
      </div>

      {/* Confidence Threshold */}
      <div>
        <label htmlFor="confidence" className="mb-2 block text-sm font-medium text-gray-200">
          Confidence Threshold: {config.confidence_threshold.toFixed(2)}
        </label>
        <input
          id="confidence"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={config.confidence_threshold}
          onChange={handleConfidenceChange}
          disabled={disabled}
          className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700"
        />
        <p className="mt-1 text-xs text-gray-400">
          Minimum confidence score for detections (0.0-1.0). Higher values reduce false positives.
        </p>
      </div>
    </div>
  );
}

/**
 * NemotronConfigForm - Form for editing Nemotron model configuration
 *
 * Provides controls for:
 * - system_prompt: Textarea for the AI system prompt
 * - temperature: Slider for generation temperature (0-2)
 * - max_tokens: Number input for maximum tokens
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Textarea, NumberInput } from '@tremor/react';
import { useCallback } from 'react';

import type { NemotronConfig } from '../../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

// Extended config type with optional parameters
interface ExtendedNemotronConfig extends NemotronConfig {
  temperature?: number;
  max_tokens?: number;
}

export interface NemotronConfigFormProps {
  /** Current configuration values */
  config: ExtendedNemotronConfig;
  /** Callback when configuration changes */
  onChange: (config: ExtendedNemotronConfig) => void;
  /** Whether the form is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Form component for editing Nemotron AI model configuration.
 *
 * @example
 * ```tsx
 * <NemotronConfigForm
 *   config={{ system_prompt: 'You are...', temperature: 0.7 }}
 *   onChange={setConfig}
 * />
 * ```
 */
export default function NemotronConfigForm({
  config,
  onChange,
  disabled = false,
}: NemotronConfigFormProps) {
  const handleSystemPromptChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      onChange({ ...config, system_prompt: e.target.value });
    },
    [config, onChange]
  );

  const handleTemperatureChange = useCallback(
    (value: number) => {
      onChange({ ...config, temperature: value });
    },
    [config, onChange]
  );

  const handleMaxTokensChange = useCallback(
    (value: number) => {
      onChange({ ...config, max_tokens: value });
    },
    [config, onChange]
  );

  // Get config values with defaults
  const temperature = config.temperature ?? 0.7;
  const maxTokens = config.max_tokens ?? 4096;

  return (
    <div className="space-y-6" data-testid="nemotron-config-form">
      {/* System Prompt */}
      <div>
        <label htmlFor="system-prompt" className="mb-2 block text-sm font-medium text-gray-200">
          System Prompt
        </label>
        <Textarea
          id="system-prompt"
          value={config.system_prompt}
          onChange={handleSystemPromptChange}
          disabled={disabled}
          rows={10}
          placeholder="Enter the system prompt for risk analysis..."
          className="bg-gray-900 text-white"
        />
        <p className="mt-1 text-xs text-gray-400">
          The system prompt defines the AI&apos;s role and behavior for risk analysis.
        </p>
      </div>

      {/* Temperature */}
      <div>
        <label htmlFor="temperature" className="mb-2 block text-sm font-medium text-gray-200">
          Temperature: {temperature.toFixed(1)}
        </label>
        <input
          id="temperature"
          type="range"
          min="0"
          max="2"
          step="0.1"
          value={temperature}
          onChange={(e) => handleTemperatureChange(parseFloat(e.target.value))}
          disabled={disabled}
          className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700"
        />
        <p className="mt-1 text-xs text-gray-400">
          Lower values (0-0.5) produce more focused output. Higher values (1-2) increase
          creativity.
        </p>
      </div>

      {/* Max Tokens */}
      <div>
        <label htmlFor="max-tokens" className="mb-2 block text-sm font-medium text-gray-200">
          Max Tokens
        </label>
        <NumberInput
          id="max-tokens"
          value={maxTokens}
          onValueChange={handleMaxTokensChange}
          disabled={disabled}
          min={100}
          max={8192}
          step={100}
          className="bg-gray-900"
        />
        <p className="mt-1 text-xs text-gray-400">
          Maximum number of tokens in the generated response (100-8192).
        </p>
      </div>
    </div>
  );
}

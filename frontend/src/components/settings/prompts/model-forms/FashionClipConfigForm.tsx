/**
 * FashionClipConfigForm - Form for editing Fashion-CLIP model configuration
 *
 * Provides controls for:
 * - clothing_categories: Tag input for clothing categories to detect
 * - suspicious_indicators: Tag input for suspicious clothing indicators
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { Button, TextInput } from '@tremor/react';
import { Plus, X } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import type { FashionClipConfig } from '../../../../types/promptManagement';

// ============================================================================
// Types
// ============================================================================

// Extended config type to support suspicious_indicators
interface ExtendedFashionClipConfig extends FashionClipConfig {
  suspicious_indicators?: string[];
}

export interface FashionClipConfigFormProps {
  /** Current configuration values */
  config: ExtendedFashionClipConfig;
  /** Callback when configuration changes */
  onChange: (config: ExtendedFashionClipConfig) => void;
  /** Whether the form is disabled */
  disabled?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Form component for editing Fashion-CLIP AI model configuration.
 *
 * @example
 * ```tsx
 * <FashionClipConfigForm
 *   config={{
 *     clothing_categories: ['hoodie', 'mask', 'uniform'],
 *     suspicious_indicators: ['face covering', 'all black']
 *   }}
 *   onChange={setConfig}
 * />
 * ```
 */
export default function FashionClipConfigForm({
  config,
  onChange,
  disabled = false,
}: FashionClipConfigFormProps) {
  const [newCategory, setNewCategory] = useState('');
  const [newIndicator, setNewIndicator] = useState('');

  // Get values with defaults - memoized to prevent unnecessary re-renders
  const clothingCategories = useMemo(
    () => config.clothing_categories ?? [],
    [config.clothing_categories]
  );
  const suspiciousIndicators = useMemo(
    () => config.suspicious_indicators ?? [],
    [config.suspicious_indicators]
  );

  // ========== Clothing Categories ==========
  const handleAddCategory = useCallback(() => {
    if (newCategory.trim() && !clothingCategories.includes(newCategory.trim())) {
      onChange({
        ...config,
        clothing_categories: [...clothingCategories, newCategory.trim()],
      });
      setNewCategory('');
    }
  }, [config, onChange, newCategory, clothingCategories]);

  const handleRemoveCategory = useCallback(
    (categoryToRemove: string) => {
      onChange({
        ...config,
        clothing_categories: clothingCategories.filter((c) => c !== categoryToRemove),
      });
    },
    [config, onChange, clothingCategories]
  );

  const handleCategoryKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddCategory();
      }
    },
    [handleAddCategory]
  );

  // ========== Suspicious Indicators ==========
  const handleAddIndicator = useCallback(() => {
    if (newIndicator.trim() && !suspiciousIndicators.includes(newIndicator.trim())) {
      onChange({
        ...config,
        suspicious_indicators: [...suspiciousIndicators, newIndicator.trim()],
      });
      setNewIndicator('');
    }
  }, [config, onChange, newIndicator, suspiciousIndicators]);

  const handleRemoveIndicator = useCallback(
    (indicatorToRemove: string) => {
      onChange({
        ...config,
        suspicious_indicators: suspiciousIndicators.filter((i) => i !== indicatorToRemove),
      });
    },
    [config, onChange, suspiciousIndicators]
  );

  const handleIndicatorKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddIndicator();
      }
    },
    [handleAddIndicator]
  );

  return (
    <div className="space-y-6" data-testid="fashionclip-config-form">
      {/* Clothing Categories */}
      <div>
        <span id="clothing-categories-label" className="mb-2 block text-sm font-medium text-gray-200">Clothing Categories</span>
        <p className="mb-3 text-xs text-gray-400">
          Define clothing types for the model to identify on detected persons.
        </p>

        {/* Current categories as tags */}
        <div className="mb-3 flex flex-wrap gap-2">
          {clothingCategories.length === 0 ? (
            <p className="text-sm italic text-gray-500">No clothing categories defined</p>
          ) : (
            clothingCategories.map((category) => (
              <span
                key={category}
                className="inline-flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-sm text-gray-200"
              >
                {category}
                <button
                  type="button"
                  onClick={() => handleRemoveCategory(category)}
                  disabled={disabled}
                  className="ml-1 rounded-full p-0.5 text-gray-400 hover:bg-gray-700 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Remove category: ${category}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))
          )}
        </div>

        {/* Add new category */}
        <div className="flex gap-2">
          <TextInput
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            onKeyDown={handleCategoryKeyDown}
            disabled={disabled}
            placeholder="Enter a new clothing category..."
            className="flex-1 bg-gray-900"
          />
          <Button
            type="button"
            onClick={handleAddCategory}
            disabled={disabled || !newCategory.trim()}
            variant="secondary"
            icon={Plus}
          >
            Add
          </Button>
        </div>
      </div>

      {/* Suspicious Indicators */}
      <div>
        <span id="suspicious-indicators-label" className="mb-2 block text-sm font-medium text-gray-200">
          Suspicious Indicators
        </span>
        <p className="mb-3 text-xs text-gray-400">
          Define clothing patterns that may indicate suspicious activity.
        </p>

        {/* Current indicators as tags */}
        <div className="mb-3 flex flex-wrap gap-2">
          {suspiciousIndicators.length === 0 ? (
            <p className="text-sm italic text-gray-500">No suspicious indicators defined</p>
          ) : (
            suspiciousIndicators.map((indicator) => (
              <span
                key={indicator}
                className="inline-flex items-center gap-1 rounded-full bg-red-900/30 px-3 py-1 text-sm text-red-200"
              >
                {indicator}
                <button
                  type="button"
                  onClick={() => handleRemoveIndicator(indicator)}
                  disabled={disabled}
                  className="ml-1 rounded-full p-0.5 text-red-400 hover:bg-red-900/50 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Remove indicator: ${indicator}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))
          )}
        </div>

        {/* Add new indicator */}
        <div className="flex gap-2">
          <TextInput
            value={newIndicator}
            onChange={(e) => setNewIndicator(e.target.value)}
            onKeyDown={handleIndicatorKeyDown}
            disabled={disabled}
            placeholder="Enter a new suspicious indicator..."
            className="flex-1 bg-gray-900"
          />
          <Button
            type="button"
            onClick={handleAddIndicator}
            disabled={disabled || !newIndicator.trim()}
            variant="secondary"
            icon={Plus}
          >
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}

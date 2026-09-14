/**
 * SeedRow - A row component for seeding test data
 *
 * Displays a label, count dropdown, and seed button. Used in the TestDataPanel
 * to allow seeding different types of data with configurable counts.
 *
 * @example
 * ```tsx
 * <SeedRow
 *   label="Cameras"
 *   options={[5, 10, 25, 50]}
 *   defaultValue={10}
 *   onSeed={(count) => seedCameras({ count })}
 *   isLoading={isSeedingCameras}
 * />
 * ```
 */

import { Button, Select, SelectItem, Text } from '@tremor/react';
import { Database } from 'lucide-react';
import { useState, useCallback } from 'react';

export interface SeedRowProps<T extends number> {
  /** Label for the row */
  label: string;
  /** Available count options */
  options: readonly T[];
  /** Default selected value */
  defaultValue: T;
  /** Callback when seed button is clicked */
  onSeed: (count: T) => Promise<void>;
  /** Whether the seed operation is loading */
  isLoading?: boolean;
  /** Custom button text (default: "Seed {label}") */
  buttonText?: string;
  /** Custom loading text (default: "Seeding...") */
  loadingText?: string;
  /** Optional description text */
  description?: string;
}

/**
 * SeedRow component
 */
export default function SeedRow<T extends number>({
  label,
  options,
  defaultValue,
  onSeed,
  isLoading = false,
  buttonText,
  loadingText = 'Seeding...',
  description,
}: SeedRowProps<T>) {
  const [selectedValue, setSelectedValue] = useState<T>(defaultValue);

  const handleSeed = useCallback(async () => {
    await onSeed(selectedValue);
  }, [onSeed, selectedValue]);

  const handleValueChange = useCallback(
    (value: string) => {
      const numValue = Number(value) as T;
      if (options.includes(numValue)) {
        setSelectedValue(numValue);
      }
    },
    [options]
  );

  const defaultButtonText = `Seed ${label}`;
  const displayButtonText = isLoading ? loadingText : (buttonText ?? defaultButtonText);

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg bg-gray-800/50 p-4">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-[#76B900]" />
          <Text className="font-medium text-white">{label}</Text>
        </div>
        {description && <Text className="mt-1 text-xs text-gray-400">{description}</Text>}
      </div>

      <div className="flex items-center gap-3">
        <Select
          value={String(selectedValue)}
          onValueChange={handleValueChange}
          disabled={isLoading}
          className="w-24"
        >
          {options.map((option) => (
            <SelectItem key={option} value={String(option)}>
              {option}
            </SelectItem>
          ))}
        </Select>

        <Button
          onClick={() => void handleSeed()}
          disabled={isLoading}
          className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {displayButtonText}
        </Button>
      </div>
    </div>
  );
}

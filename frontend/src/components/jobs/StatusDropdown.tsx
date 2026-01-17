/**
 * StatusDropdown component for filtering jobs by status.
 *
 * A reusable dropdown component that allows users to filter jobs by their
 * execution status (Pending, Processing, Completed, Failed, Cancelled).
 */

import type { JobStatusEnum } from '../../types/generated';

/**
 * Job status options for the dropdown.
 */
export const JOB_STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
] as const;

/**
 * Props for the StatusDropdown component.
 */
export interface StatusDropdownProps {
  /** Current selected status */
  value?: JobStatusEnum;
  /** Called when status selection changes */
  onChange: (status?: JobStatusEnum) => void;
  /** Whether the dropdown is disabled */
  disabled?: boolean;
  /** Optional label (default: "Status") */
  label?: string;
  /** Optional className */
  className?: string;
}

/**
 * Dropdown component for filtering jobs by status.
 */
export default function StatusDropdown({
  value,
  onChange,
  disabled = false,
  label = 'Status',
  className = '',
}: StatusDropdownProps) {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedValue = e.target.value;
    onChange(selectedValue ? (selectedValue as JobStatusEnum) : undefined);
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <label htmlFor="status-dropdown" className="sr-only">
        {label}
      </label>
      <select
        id="status-dropdown"
        value={value || ''}
        onChange={handleChange}
        disabled={disabled}
        className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={label}
      >
        {JOB_STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

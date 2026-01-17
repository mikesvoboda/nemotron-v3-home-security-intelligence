/**
 * TypeDropdown component for filtering jobs by type.
 *
 * A reusable dropdown component that allows users to filter jobs by their
 * type (Export, Batch Audit, Cleanup, Re-evaluation).
 */

/**
 * Job type options for the dropdown.
 */
export const JOB_TYPE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'export', label: 'Export' },
  { value: 'batch_audit', label: 'Batch Audit' },
  { value: 'cleanup', label: 'Cleanup' },
  { value: 're_evaluation', label: 'Re-evaluation' },
] as const;

/**
 * Props for the TypeDropdown component.
 */
export interface TypeDropdownProps {
  /** Current selected type */
  value?: string;
  /** Called when type selection changes */
  onChange: (type?: string) => void;
  /** Whether the dropdown is disabled */
  disabled?: boolean;
  /** Optional label (default: "Type") */
  label?: string;
  /** Optional className */
  className?: string;
}

/**
 * Dropdown component for filtering jobs by type.
 */
export default function TypeDropdown({
  value,
  onChange,
  disabled = false,
  label = 'Type',
  className = '',
}: TypeDropdownProps) {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedValue = e.target.value;
    onChange(selectedValue || undefined);
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <label htmlFor="type-dropdown" className="sr-only">
        {label}
      </label>
      <select
        id="type-dropdown"
        value={value || ''}
        onChange={handleChange}
        disabled={disabled}
        className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={label}
      >
        {JOB_TYPE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * CameraSelector - Camera selection component with React 19 useTransition.
 *
 * Uses React 19's useTransition hook to prevent UI blocking during heavy
 * re-renders triggered by camera selection changes. The selection change
 * is marked as low priority, keeping the UI responsive.
 *
 * @module components/cameras/CameraSelector
 * @see NEM-3749 - React 19 useTransition for non-blocking search/filter
 */

import { clsx } from 'clsx';
import { Camera, ChevronDown, Loader2 } from 'lucide-react';
import { memo, useCallback, useTransition } from 'react';

/**
 * Camera option for the selector.
 */
export interface CameraOption {
  /** Camera ID */
  id: string;
  /** Camera display name */
  name: string;
  /** Camera status */
  status?: 'online' | 'offline' | 'error';
}

export interface CameraSelectorProps {
  /** Currently selected camera ID (empty string for "All Cameras") */
  value: string;
  /** Callback when camera selection changes (wrapped in startTransition) */
  onChange: (cameraId: string) => void;
  /** List of available cameras */
  cameras: CameraOption[];
  /** Placeholder text for the "All" option */
  allLabel?: string;
  /** Whether to show camera status indicators */
  showStatus?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Whether the selector is disabled */
  disabled?: boolean;
}

/**
 * Get status indicator color for a camera.
 */
function getStatusColor(status?: CameraOption['status']): string {
  switch (status) {
    case 'online':
      return 'bg-[#76B900]';
    case 'offline':
      return 'bg-gray-500';
    case 'error':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

/**
 * CameraSelector component with React 19 useTransition for non-blocking updates.
 *
 * Camera selection changes can trigger expensive re-renders in the event list
 * or dashboard. Using useTransition keeps the UI responsive by marking the
 * selection change as a low-priority update.
 *
 * @example
 * ```tsx
 * const [selectedCamera, setSelectedCamera] = useState('');
 * const { cameras } = useCamerasQuery();
 *
 * <CameraSelector
 *   value={selectedCamera}
 *   onChange={setSelectedCamera}
 *   cameras={cameras}
 * />
 * ```
 */
const CameraSelector = memo(function CameraSelector({
  value,
  onChange,
  cameras,
  allLabel = 'All Cameras',
  showStatus = true,
  className,
  disabled = false,
}: CameraSelectorProps) {
  // React 19 useTransition for non-blocking selection updates
  const [isPending, startTransition] = useTransition();

  /**
   * Handle camera selection change.
   * Wrapped in startTransition to prevent UI blocking.
   */
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newValue = e.target.value;
      startTransition(() => {
        onChange(newValue);
      });
    },
    [onChange]
  );

  // Find the currently selected camera for display
  const selectedCamera = cameras.find((cam) => cam.id === value);

  return (
    <div className={clsx('relative', className)}>
      {/* Camera icon */}
      <Camera className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />

      {/* Status indicator for selected camera */}
      {showStatus && selectedCamera && (
        <span
          className={clsx(
            'pointer-events-none absolute left-9 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full',
            getStatusColor(selectedCamera.status)
          )}
          aria-hidden="true"
        />
      )}

      {/* Select dropdown */}
      <select
        value={value}
        onChange={handleChange}
        disabled={disabled || isPending}
        aria-label="Select camera"
        className={clsx(
          'w-full appearance-none rounded-md border border-gray-700 bg-[#1A1A1A] py-2.5 pr-10 text-sm text-white',
          'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
          'disabled:cursor-not-allowed disabled:opacity-50',
          showStatus && selectedCamera ? 'pl-12' : 'pl-10'
        )}
      >
        <option value="">{allLabel}</option>
        {cameras.map((camera) => (
          <option key={camera.id} value={camera.id}>
            {camera.name}
            {showStatus && camera.status && ` (${camera.status})`}
          </option>
        ))}
      </select>

      {/* Dropdown arrow or loading indicator */}
      <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
        {isPending ? (
          <Loader2
            className="h-4 w-4 animate-spin text-[#76B900]"
            data-testid="camera-loading-indicator"
            aria-label="Loading"
          />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </div>
    </div>
  );
});

export default CameraSelector;

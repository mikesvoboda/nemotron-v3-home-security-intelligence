/**
 * PTZControls Component (NEM-4885)
 *
 * D-pad style interface for PTZ (Pan-Tilt-Zoom) camera control.
 * Provides directional buttons for pan/tilt, zoom controls, and optional preset selection.
 *
 * @example
 * ```tsx
 * // Basic usage
 * <PTZControls cameraId="camera-1" />
 *
 * // Compact mode for overlay usage
 * <PTZControls cameraId="camera-1" compact showPresets />
 *
 * // With presets
 * <PTZControls cameraId="camera-1" showPresets className="p-4" />
 * ```
 */

import { clsx } from 'clsx';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Loader2,
  Minus,
  Plus,
  Square,
} from 'lucide-react';
import { memo, useCallback } from 'react';

import { usePresets } from '../../hooks/usePresets';
import { usePtzControl } from '../../hooks/usePtzControl';

import type { PTZDirection, PTZPreset } from '../../types/ptz';

/**
 * Props for the PTZControls component
 */
export interface PTZControlsProps {
  /** Camera ID to control */
  cameraId: string;
  /** Compact mode for overlay usage */
  compact?: boolean;
  /** Whether to show preset selector */
  showPresets?: boolean;
  /** Optional className for styling */
  className?: string;
  /** Whether the camera supports PTZ (disables controls when false) */
  ptzSupported?: boolean;
}

/**
 * Button size classes based on compact mode
 */
const buttonSizeClasses = {
  normal: 'h-11 w-11 min-h-11 min-w-11',
  compact: 'h-9 w-9 min-h-9 min-w-9',
};

/**
 * Icon size classes based on compact mode
 */
const iconSizeClasses = {
  normal: 'h-5 w-5',
  compact: 'h-4 w-4',
};

/**
 * Button identifier for test IDs and tracking
 */
type PTZButtonId = PTZDirection | 'stop';

/**
 * Individual D-pad button component
 */
interface DPadButtonProps {
  /** Button identifier for test IDs */
  buttonId: PTZButtonId;
  /** Icon to display */
  icon: React.ReactNode;
  /** Accessible label for the button */
  ariaLabel: string;
  /** Whether the button is currently loading */
  isLoading: boolean;
  /** Whether the button is disabled */
  disabled: boolean;
  /** Click handler */
  onClick: () => void;
  /** Whether in compact mode */
  compact: boolean;
  /** Optional additional classes */
  className?: string;
}

const DPadButton = memo(function DPadButton({
  buttonId,
  icon,
  ariaLabel,
  isLoading,
  disabled,
  onClick,
  compact,
  className,
}: DPadButtonProps) {
  const sizeClass = compact ? buttonSizeClasses.compact : buttonSizeClasses.normal;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isLoading}
      aria-label={ariaLabel}
      aria-busy={isLoading}
      data-testid={`ptz-${buttonId}`}
      className={clsx(
        // Layout
        'inline-flex items-center justify-center',
        // Shape
        'rounded-lg',
        // Size
        sizeClass,
        // Colors - dark mode with NVIDIA green accent
        'bg-gray-800 text-gray-300',
        'hover:bg-gray-700 hover:text-white',
        'active:bg-[#76B900] active:text-black',
        // Transition
        'transition-colors duration-150',
        // Focus styles
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#76B900] focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900',
        // Disabled state
        (disabled || isLoading) && 'cursor-not-allowed opacity-50',
        isLoading && 'cursor-wait',
        className
      )}
    >
      {isLoading ? (
        <Loader2
          className={clsx(
            'animate-spin',
            compact ? iconSizeClasses.compact : iconSizeClasses.normal
          )}
          aria-hidden="true"
        />
      ) : (
        icon
      )}
    </button>
  );
});

/**
 * Preset selector dropdown component
 */
interface PresetSelectorProps {
  /** List of available presets */
  presets: PTZPreset[];
  /** Whether presets are loading */
  isLoading: boolean;
  /** Whether navigation is in progress */
  isNavigating: boolean;
  /** Handler for selecting a preset */
  onSelect: (presetToken: string) => void;
  /** Whether in compact mode */
  compact: boolean;
  /** Whether the selector is disabled */
  disabled: boolean;
}

const PresetSelector = memo(function PresetSelector({
  presets,
  isLoading,
  isNavigating,
  onSelect,
  compact,
  disabled,
}: PresetSelectorProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      if (value) {
        onSelect(value);
        // Reset select to placeholder after selection
        e.target.value = '';
      }
    },
    [onSelect]
  );

  const isDisabled = disabled || isLoading || isNavigating || presets.length === 0;

  return (
    <div className="relative">
      <select
        onChange={handleChange}
        disabled={isDisabled}
        aria-label="Select camera preset"
        data-testid="ptz-preset-selector"
        className={clsx(
          'w-full appearance-none rounded-md border border-gray-700 bg-gray-800',
          'text-sm text-gray-300',
          'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
          'disabled:cursor-not-allowed disabled:opacity-50',
          compact ? 'py-1.5 pl-3 pr-8' : 'py-2 pl-3 pr-10'
        )}
        defaultValue=""
      >
        <option value="" disabled>
          {isLoading ? 'Loading presets...' : presets.length === 0 ? 'No presets' : 'Go to preset'}
        </option>
        {presets.map((preset) => (
          <option key={preset.token} value={preset.token}>
            {preset.name}
          </option>
        ))}
      </select>

      {/* Dropdown indicator */}
      <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2">
        {isNavigating ? (
          <Loader2
            className={clsx('animate-spin text-[#76B900]', compact ? 'h-3 w-3' : 'h-4 w-4')}
            aria-hidden="true"
          />
        ) : (
          <ChevronDown
            className={clsx('text-gray-400', compact ? 'h-3 w-3' : 'h-4 w-4')}
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  );
});

/**
 * PTZControls - D-pad style PTZ camera control interface
 *
 * Features:
 * - Directional D-pad for pan and tilt control
 * - Center stop button to halt all movement
 * - Zoom in/out buttons
 * - Optional preset selector dropdown
 * - Compact mode for overlay usage
 * - Loading states during commands
 * - Keyboard accessible with proper ARIA labels
 * - Dark mode styling with NVIDIA green accent
 *
 * @example
 * ```tsx
 * // Basic usage
 * <PTZControls cameraId="camera-1" />
 *
 * // Full featured
 * <PTZControls
 *   cameraId="camera-1"
 *   showPresets
 *   compact={false}
 *   className="p-4 bg-gray-900 rounded-lg"
 * />
 * ```
 */
const PTZControls = memo(function PTZControls({
  cameraId,
  compact = false,
  showPresets = false,
  className,
  ptzSupported = true,
}: PTZControlsProps) {
  // PTZ control hooks
  const { moveDirection, stopMovement, isMoving } = usePtzControl(cameraId);
  const { presets, isLoading: presetsLoading, gotoPreset } = usePresets(cameraId, showPresets);

  // Handlers
  const handleDirection = useCallback(
    (direction: PTZDirection) => {
      moveDirection.mutate(direction);
    },
    [moveDirection]
  );

  const handleStop = useCallback(() => {
    stopMovement.mutate();
  }, [stopMovement]);

  const handlePresetSelect = useCallback(
    (presetToken: string) => {
      gotoPreset.mutate(presetToken);
    },
    [gotoPreset]
  );

  // Icon size based on compact mode
  const iconClass = compact ? iconSizeClasses.compact : iconSizeClasses.normal;

  // Disabled state
  const isDisabled = !ptzSupported;

  return (
    <div
      className={clsx('flex flex-col', compact ? 'gap-2' : 'gap-3', className)}
      role="group"
      aria-label="PTZ camera controls"
      data-testid="ptz-controls"
    >
      {/* D-Pad Grid */}
      <div className={clsx('grid grid-cols-3 place-items-center', compact ? 'gap-1' : 'gap-2')}>
        {/* Top row - Up button */}
        <div /> {/* Empty cell */}
        <DPadButton
          buttonId="up"
          icon={<ChevronUp className={iconClass} aria-hidden="true" />}
          ariaLabel="Tilt camera up"
          isLoading={moveDirection.isPending && moveDirection.variables === 'up'}
          disabled={isDisabled}
          onClick={() => handleDirection('up')}
          compact={compact}
        />
        <div /> {/* Empty cell */}
        {/* Middle row - Left, Stop, Right */}
        <DPadButton
          buttonId="left"
          icon={<ChevronLeft className={iconClass} aria-hidden="true" />}
          ariaLabel="Pan camera left"
          isLoading={moveDirection.isPending && moveDirection.variables === 'left'}
          disabled={isDisabled}
          onClick={() => handleDirection('left')}
          compact={compact}
        />
        <DPadButton
          buttonId="stop"
          icon={<Square className={clsx(compact ? 'h-3 w-3' : 'h-4 w-4')} aria-hidden="true" />}
          ariaLabel="Stop camera movement"
          isLoading={stopMovement.isPending}
          disabled={isDisabled || !isMoving}
          onClick={handleStop}
          compact={compact}
          className={clsx('bg-gray-700', 'hover:bg-red-600 hover:text-white', 'active:bg-red-700')}
        />
        <DPadButton
          buttonId="right"
          icon={<ChevronRight className={iconClass} aria-hidden="true" />}
          ariaLabel="Pan camera right"
          isLoading={moveDirection.isPending && moveDirection.variables === 'right'}
          disabled={isDisabled}
          onClick={() => handleDirection('right')}
          compact={compact}
        />
        {/* Bottom row - Down button */}
        <div /> {/* Empty cell */}
        <DPadButton
          buttonId="down"
          icon={<ChevronDown className={iconClass} aria-hidden="true" />}
          ariaLabel="Tilt camera down"
          isLoading={moveDirection.isPending && moveDirection.variables === 'down'}
          disabled={isDisabled}
          onClick={() => handleDirection('down')}
          compact={compact}
        />
        <div /> {/* Empty cell */}
      </div>

      {/* Zoom Controls */}
      <div className={clsx('flex justify-center', compact ? 'gap-2' : 'gap-3')}>
        <DPadButton
          buttonId="zoom-out"
          icon={<Minus className={iconClass} aria-hidden="true" />}
          ariaLabel="Zoom out"
          isLoading={moveDirection.isPending && moveDirection.variables === 'zoom-out'}
          disabled={isDisabled}
          onClick={() => handleDirection('zoom-out')}
          compact={compact}
        />
        <DPadButton
          buttonId="zoom-in"
          icon={<Plus className={iconClass} aria-hidden="true" />}
          ariaLabel="Zoom in"
          isLoading={moveDirection.isPending && moveDirection.variables === 'zoom-in'}
          disabled={isDisabled}
          onClick={() => handleDirection('zoom-in')}
          compact={compact}
        />
      </div>

      {/* Preset Selector */}
      {showPresets && (
        <PresetSelector
          presets={presets?.presets ?? []}
          isLoading={presetsLoading}
          isNavigating={gotoPreset.isPending}
          onSelect={handlePresetSelect}
          compact={compact}
          disabled={isDisabled}
        />
      )}

      {/* Disabled message */}
      {!ptzSupported && (
        <p
          className={clsx('text-center text-gray-500', compact ? 'text-xs' : 'text-sm')}
          role="status"
        >
          PTZ not supported
        </p>
      )}
    </div>
  );
});

export default PTZControls;

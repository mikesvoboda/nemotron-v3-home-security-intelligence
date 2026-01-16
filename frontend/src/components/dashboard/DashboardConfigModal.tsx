import { Switch } from '@headlessui/react';
import { clsx } from 'clsx';
import { ArrowDown, ArrowUp, RefreshCw, Settings2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  moveWidgetDown,
  moveWidgetUp,
  resetDashboardConfig,
  setWidgetVisibility,
} from '../../stores/dashboardConfig';
import AnimatedModal from '../common/AnimatedModal';

import type { DashboardConfig, WidgetConfig, WidgetId } from '../../stores/dashboardConfig';

// ============================================================================
// Types
// ============================================================================

export interface DashboardConfigModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Current dashboard configuration */
  config: DashboardConfig;
  /** Callback when configuration changes */
  onConfigChange: (config: DashboardConfig) => void;
}

// ============================================================================
// Component
// ============================================================================

/**
 * DashboardConfigModal provides a UI for customizing dashboard widget layout.
 *
 * Features:
 * - Toggle widget visibility with switches
 * - Reorder widgets with up/down buttons
 * - Reset to defaults option
 * - Save/Cancel workflow
 * - NVIDIA dark theme styling
 */
export default function DashboardConfigModal({
  isOpen,
  onClose,
  config,
  onConfigChange,
}: DashboardConfigModalProps) {
  // Local state for editing (allows cancel without saving)
  const [editConfig, setEditConfig] = useState<DashboardConfig>(config);

  // Reset edit state when modal opens
  useEffect(() => {
    if (isOpen) {
      setEditConfig(config);
    }
  }, [isOpen, config]);

  // Handle visibility toggle
  const handleVisibilityToggle = useCallback((widgetId: WidgetId, visible: boolean) => {
    setEditConfig((prev) => setWidgetVisibility(prev, widgetId, visible));
  }, []);

  // Handle move up
  const handleMoveUp = useCallback((widgetId: WidgetId) => {
    setEditConfig((prev) => moveWidgetUp(prev, widgetId));
  }, []);

  // Handle move down
  const handleMoveDown = useCallback((widgetId: WidgetId) => {
    setEditConfig((prev) => moveWidgetDown(prev, widgetId));
  }, []);

  // Handle reset to defaults
  const handleReset = useCallback(() => {
    const defaultConfig = resetDashboardConfig();
    setEditConfig(defaultConfig);
  }, []);

  // Handle save
  const handleSave = useCallback(() => {
    onConfigChange(editConfig);
    onClose();
  }, [editConfig, onConfigChange, onClose]);

  // Handle cancel
  const handleCancel = useCallback(() => {
    setEditConfig(config); // Revert changes
    onClose();
  }, [config, onClose]);

  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={handleCancel}
      variant="scale"
      size="lg"
      aria-labelledby="config-modal-title"
      aria-describedby="config-modal-description"
      className="overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/10">
            <Settings2 className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          </div>
          <div>
            <h2 id="config-modal-title" className="text-lg font-semibold text-white">
              Customize Dashboard
            </h2>
            <p id="config-modal-description" className="text-sm text-gray-400">
              Toggle widgets and change display order
            </p>
          </div>
        </div>
        <button
          onClick={handleCancel}
          className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          aria-label="Close"
          data-testid="config-modal-close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Widget List */}
      <div className="max-h-[60vh] overflow-y-auto p-6" data-testid="widget-list">
        <div className="space-y-3">
          {editConfig.widgets.map((widget, index) => (
            <WidgetConfigRow
              key={widget.id}
              widget={widget}
              isFirst={index === 0}
              isLast={index === editConfig.widgets.length - 1}
              onVisibilityToggle={handleVisibilityToggle}
              onMoveUp={handleMoveUp}
              onMoveDown={handleMoveDown}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-gray-800 px-6 py-4">
        <button
          onClick={handleReset}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          data-testid="reset-defaults-button"
        >
          <RefreshCw className="h-4 w-4" />
          Reset to Defaults
        </button>
        <div className="flex items-center gap-3">
          <button
            onClick={handleCancel}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            data-testid="cancel-button"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#8BC727]"
            data-testid="save-button"
          >
            Save Changes
          </button>
        </div>
      </div>
    </AnimatedModal>
  );
}

// ============================================================================
// Widget Config Row Subcomponent
// ============================================================================

interface WidgetConfigRowProps {
  widget: WidgetConfig;
  isFirst: boolean;
  isLast: boolean;
  onVisibilityToggle: (widgetId: WidgetId, visible: boolean) => void;
  onMoveUp: (widgetId: WidgetId) => void;
  onMoveDown: (widgetId: WidgetId) => void;
}

function WidgetConfigRow({
  widget,
  isFirst,
  isLast,
  onVisibilityToggle,
  onMoveUp,
  onMoveDown,
}: WidgetConfigRowProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-4 rounded-lg border border-gray-800 bg-gray-800/50 p-4 transition-colors',
        widget.visible && 'border-[#76B900]/30 bg-[#76B900]/5'
      )}
      data-testid={`widget-row-${widget.id}`}
    >
      {/* Visibility Toggle */}
      <Switch
        checked={widget.visible}
        onChange={(checked) => onVisibilityToggle(widget.id, checked)}
        className={clsx(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          widget.visible ? 'bg-[#76B900]' : 'bg-gray-700'
        )}
        data-testid={`widget-toggle-${widget.id}`}
      >
        <span className="sr-only">Toggle {widget.name}</span>
        <span
          className={clsx(
            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
            widget.visible ? 'translate-x-6' : 'translate-x-1'
          )}
        />
      </Switch>

      {/* Widget Info */}
      <div className="min-w-0 flex-1">
        <h3
          className={clsx('text-sm font-medium', widget.visible ? 'text-white' : 'text-gray-400')}
        >
          {widget.name}
        </h3>
        <p className="text-xs text-gray-500">{widget.description}</p>
      </div>

      {/* Reorder Buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onMoveUp(widget.id)}
          disabled={isFirst}
          className={clsx(
            'rounded p-1.5 transition-colors',
            isFirst
              ? 'cursor-not-allowed text-gray-700'
              : 'text-gray-400 hover:bg-gray-700 hover:text-white'
          )}
          aria-label={`Move ${widget.name} up`}
          data-testid={`widget-move-up-${widget.id}`}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
        <button
          onClick={() => onMoveDown(widget.id)}
          disabled={isLast}
          className={clsx(
            'rounded p-1.5 transition-colors',
            isLast
              ? 'cursor-not-allowed text-gray-700'
              : 'text-gray-400 hover:bg-gray-700 hover:text-white'
          )}
          aria-label={`Move ${widget.name} down`}
          data-testid={`widget-move-down-${widget.id}`}
        >
          <ArrowDown className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

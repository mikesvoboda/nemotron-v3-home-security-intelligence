import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardConfigModal from './DashboardConfigModal';
import {
  DEFAULT_CONFIG,
  DEFAULT_WIDGETS,
  type DashboardConfig,
} from '../../stores/dashboardConfig';
import { renderWithProviders, screen, waitFor } from '../../test-utils/renderWithProviders';

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      className,
      'data-testid': testId,
      onClick,
      role,
      'aria-modal': ariaModal,
      'aria-labelledby': ariaLabelledby,
      'aria-describedby': ariaDescribedby,
      tabIndex,
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      onClick?: () => void;
      role?: string;
      'aria-modal'?: boolean;
      'aria-labelledby'?: string;
      'aria-describedby'?: string;
      tabIndex?: number;
    }) => (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events -- mock for framer-motion
      <div
        className={className}
        data-testid={testId}
        onClick={onClick}
        role={role || 'presentation'}
        aria-modal={ariaModal}
        aria-labelledby={ariaLabelledby}
        aria-describedby={ariaDescribedby}
        tabIndex={tabIndex}
      >
        {children}
      </div>
    ),
  },
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useReducedMotion: vi.fn(() => false),
}));

// Mock localStorage
const mockStorage: Record<string, string> = {};

beforeEach(() => {
  Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(
    (key: string) => mockStorage[key] ?? null
  );
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
    mockStorage[key] = value;
  });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key: string) => {
    delete mockStorage[key];
  });
});

describe('DashboardConfigModal', () => {
  const mockOnClose = vi.fn();
  const mockOnConfigChange = vi.fn();

  const defaultProps = {
    isOpen: true,
    onClose: mockOnClose,
    config: DEFAULT_CONFIG,
    onConfigChange: mockOnConfigChange,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders modal title', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByText('Customize Dashboard')).toBeInTheDocument();
    });

    it('renders modal description', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByText('Toggle widgets and change display order')).toBeInTheDocument();
    });

    it('renders all widgets from config', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      for (const widget of DEFAULT_WIDGETS) {
        expect(screen.getByText(widget.name)).toBeInTheDocument();
        expect(screen.getByText(widget.description)).toBeInTheDocument();
      }
    });

    it('renders close button', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByTestId('config-modal-close')).toBeInTheDocument();
    });

    it('renders save button', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByTestId('save-button')).toBeInTheDocument();
    });

    it('renders cancel button', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByTestId('cancel-button')).toBeInTheDocument();
    });

    it('renders reset to defaults button', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByTestId('reset-defaults-button')).toBeInTheDocument();
    });

    it('renders nothing when isOpen is false', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByText('Customize Dashboard')).not.toBeInTheDocument();
    });
  });

  describe('widget rows', () => {
    it('renders widget toggle for each widget', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      for (const widget of DEFAULT_WIDGETS) {
        expect(screen.getByTestId(`widget-toggle-${widget.id}`)).toBeInTheDocument();
      }
    });

    it('renders move up button for each widget', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      for (const widget of DEFAULT_WIDGETS) {
        expect(screen.getByTestId(`widget-move-up-${widget.id}`)).toBeInTheDocument();
      }
    });

    it('renders move down button for each widget', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      for (const widget of DEFAULT_WIDGETS) {
        expect(screen.getByTestId(`widget-move-down-${widget.id}`)).toBeInTheDocument();
      }
    });

    it('disables move up button for first widget', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      const firstWidgetId = DEFAULT_WIDGETS[0].id;
      const moveUpButton = screen.getByTestId(`widget-move-up-${firstWidgetId}`);
      expect(moveUpButton).toBeDisabled();
    });

    it('disables move down button for last widget', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      const lastWidgetId = DEFAULT_WIDGETS[DEFAULT_WIDGETS.length - 1].id;
      const moveDownButton = screen.getByTestId(`widget-move-down-${lastWidgetId}`);
      expect(moveDownButton).toBeDisabled();
    });
  });

  describe('visibility toggle', () => {
    it('toggles widget visibility when switch is clicked', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Find a visible widget toggle and click it
      const toggle = screen.getByTestId('widget-toggle-stats-row');
      await user.click(toggle);

      // Save to verify the change
      await user.click(screen.getByTestId('save-button'));

      expect(mockOnConfigChange).toHaveBeenCalledWith(
        expect.objectContaining({
          widgets: expect.arrayContaining([
            expect.objectContaining({
              id: 'stats-row',
              visible: false,
            }),
          ]),
        })
      );
    });

    it('can toggle hidden widget to visible', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // gpu-stats is hidden by default
      const toggle = screen.getByTestId('widget-toggle-gpu-stats');
      await user.click(toggle);

      await user.click(screen.getByTestId('save-button'));

      expect(mockOnConfigChange).toHaveBeenCalledWith(
        expect.objectContaining({
          widgets: expect.arrayContaining([
            expect.objectContaining({
              id: 'gpu-stats',
              visible: true,
            }),
          ]),
        })
      );
    });
  });

  describe('reordering', () => {
    it('moves widget up when move up button is clicked', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Move camera-grid up (it's at index 1)
      const moveUpButton = screen.getByTestId('widget-move-up-camera-grid');
      await user.click(moveUpButton);

      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;
      expect(savedConfig.widgets[0].id).toBe('camera-grid');
      expect(savedConfig.widgets[1].id).toBe('stats-row');
    });

    it('moves widget down when move down button is clicked', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Move stats-row down (it's at index 0)
      const moveDownButton = screen.getByTestId('widget-move-down-stats-row');
      await user.click(moveDownButton);

      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;
      expect(savedConfig.widgets[0].id).toBe('camera-grid');
      expect(savedConfig.widgets[1].id).toBe('stats-row');
    });

    it('does not change order when clicking disabled move up', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // stats-row is first, move up should be disabled
      const moveUpButton = screen.getByTestId('widget-move-up-stats-row');
      await user.click(moveUpButton);

      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;
      expect(savedConfig.widgets[0].id).toBe('stats-row');
    });
  });

  describe('save and cancel', () => {
    it('calls onConfigChange with updated config on save', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      await user.click(screen.getByTestId('save-button'));

      expect(mockOnConfigChange).toHaveBeenCalledTimes(1);
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose without saving on cancel', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Make a change
      await user.click(screen.getByTestId('widget-toggle-stats-row'));

      // Then cancel
      await user.click(screen.getByTestId('cancel-button'));

      expect(mockOnConfigChange).not.toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('reverts changes when modal is cancelled and reopened', async () => {
      const { user, rerender } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Make a change
      await user.click(screen.getByTestId('widget-toggle-stats-row'));

      // Cancel
      await user.click(screen.getByTestId('cancel-button'));

      // Reopen modal
      rerender(<DashboardConfigModal {...defaultProps} isOpen={true} />);

      // The change should not persist (toggle should be in original state)
      // Since stats-row is visible by default, it should still show as visible
      // We verify this by saving and checking the config
      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;
      const statsRow = savedConfig.widgets.find((w) => w.id === 'stats-row');
      expect(statsRow?.visible).toBe(true);
    });

    it('calls onClose when close button is clicked', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      await user.click(screen.getByTestId('config-modal-close'));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('reset to defaults', () => {
    it('resets configuration to defaults when reset button is clicked', async () => {
      // Start with a modified config
      const modifiedConfig: DashboardConfig = {
        widgets: DEFAULT_WIDGETS.map((w) => ({ ...w, visible: false })),
        version: 1,
      };

      const { user } = renderWithProviders(
        <DashboardConfigModal {...defaultProps} config={modifiedConfig} />
      );

      // Click reset
      await user.click(screen.getByTestId('reset-defaults-button'));

      // Save to capture the reset config
      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;

      // Should have default visibility (stats-row, camera-grid, activity-feed visible)
      const statsRow = savedConfig.widgets.find((w) => w.id === 'stats-row');
      const cameraGrid = savedConfig.widgets.find((w) => w.id === 'camera-grid');
      const activityFeed = savedConfig.widgets.find((w) => w.id === 'activity-feed');
      const gpuStats = savedConfig.widgets.find((w) => w.id === 'gpu-stats');

      expect(statsRow?.visible).toBe(true);
      expect(cameraGrid?.visible).toBe(true);
      expect(activityFeed?.visible).toBe(true);
      expect(gpuStats?.visible).toBe(false);
    });
  });

  describe('accessibility', () => {
    it('has accessible modal title', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /customize dashboard/i })).toBeInTheDocument();
    });

    it('has aria labels for move buttons', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByLabelText(/move stats row up/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/move stats row down/i)).toBeInTheDocument();
    });

    it('has aria labels for toggle buttons', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Headless UI Switch includes sr-only text
      expect(screen.getByText(/toggle stats row/i)).toBeInTheDocument();
    });
  });

  describe('visual styling', () => {
    it('highlights visible widgets with accent color', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      const statsRowRow = screen.getByTestId('widget-row-stats-row');
      expect(statsRowRow).toHaveClass('border-[#76B900]/30');
      expect(statsRowRow).toHaveClass('bg-[#76B900]/5');
    });

    it('shows hidden widgets with muted styling', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // gpu-stats is hidden by default
      const gpuStatsRow = screen.getByTestId('widget-row-gpu-stats');
      expect(gpuStatsRow).not.toHaveClass('border-[#76B900]/30');
    });
  });

  describe('widget list', () => {
    it('renders widget list container', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      expect(screen.getByTestId('widget-list')).toBeInTheDocument();
    });

    it('widget list is scrollable', () => {
      renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      const widgetList = screen.getByTestId('widget-list');
      expect(widgetList).toHaveClass('overflow-y-auto');
    });
  });

  describe('multiple changes', () => {
    it('can toggle multiple widgets before saving', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Toggle multiple widgets
      await user.click(screen.getByTestId('widget-toggle-stats-row')); // Hide
      await user.click(screen.getByTestId('widget-toggle-gpu-stats')); // Show

      await user.click(screen.getByTestId('save-button'));

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;
      const statsRow = savedConfig.widgets.find((w) => w.id === 'stats-row');
      const gpuStats = savedConfig.widgets.find((w) => w.id === 'gpu-stats');

      expect(statsRow?.visible).toBe(false);
      expect(gpuStats?.visible).toBe(true);
    });

    it('can reorder and toggle visibility in same session', async () => {
      const { user } = renderWithProviders(<DashboardConfigModal {...defaultProps} />);

      // Move camera-grid up
      await user.click(screen.getByTestId('widget-move-up-camera-grid'));

      // Toggle stats-row visibility
      await user.click(screen.getByTestId('widget-toggle-stats-row'));

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(mockOnConfigChange).toHaveBeenCalled();
      });

      const savedConfig = mockOnConfigChange.mock.calls[0][0] as DashboardConfig;

      // Verify order change
      expect(savedConfig.widgets[0].id).toBe('camera-grid');
      expect(savedConfig.widgets[1].id).toBe('stats-row');

      // Verify visibility change
      const statsRow = savedConfig.widgets.find((w) => w.id === 'stats-row');
      expect(statsRow?.visible).toBe(false);
    });
  });
});

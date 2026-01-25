/**
 * Tests for BulkActionBar component
 * NEM-3615: Add bulk actions to EventTimeline and EntitiesPage
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { Check, Trash2 } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';

import BulkActionBar from './BulkActionBar';
import {
  createDeleteAction,
  createExportAction,
  createMarkReviewedAction,
} from './BulkActionBar.utils';

import type { BulkAction } from './BulkActionBar';

describe('BulkActionBar', () => {
  const defaultActions: BulkAction[] = [
    {
      id: 'test-action',
      label: 'Test Action',
      icon: <Check className="h-4 w-4" data-testid="check-icon" />,
      onClick: vi.fn(),
    },
  ];

  describe('visibility', () => {
    it('should not render when selectedCount is 0', () => {
      const { container } = render(
        <BulkActionBar
          selectedCount={0}
          actions={defaultActions}
          onClearSelection={vi.fn()}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should not render when visible is false', () => {
      const { container } = render(
        <BulkActionBar
          selectedCount={5}
          actions={defaultActions}
          onClearSelection={vi.fn()}
          visible={false}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should render when selectedCount is greater than 0', () => {
      render(
        <BulkActionBar
          selectedCount={5}
          actions={defaultActions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByRole('toolbar')).toBeInTheDocument();
    });
  });

  describe('selection display', () => {
    it('should display selected count', () => {
      render(
        <BulkActionBar
          selectedCount={10}
          actions={defaultActions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('should display total count when provided', () => {
      render(
        <BulkActionBar
          selectedCount={5}
          totalCount={20}
          actions={defaultActions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByText(/of 20/)).toBeInTheDocument();
    });

    it('should display custom item label', () => {
      render(
        <BulkActionBar
          selectedCount={3}
          actions={defaultActions}
          onClearSelection={vi.fn()}
          itemLabel="events"
        />
      );

      expect(screen.getByText(/events selected/)).toBeInTheDocument();
    });

    it('should display default item label', () => {
      render(
        <BulkActionBar
          selectedCount={3}
          actions={defaultActions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByText(/items selected/)).toBeInTheDocument();
    });
  });

  describe('clear selection', () => {
    it('should call onClearSelection when clear button is clicked', () => {
      const onClearSelection = vi.fn();

      render(
        <BulkActionBar
          selectedCount={5}
          actions={defaultActions}
          onClearSelection={onClearSelection}
        />
      );

      const clearButton = screen.getByLabelText('Clear selection');
      fireEvent.click(clearButton);

      expect(onClearSelection).toHaveBeenCalledTimes(1);
    });
  });

  describe('action buttons', () => {
    it('should render action buttons', () => {
      const actions: BulkAction[] = [
        {
          id: 'action1',
          label: 'Action 1',
          onClick: vi.fn(),
        },
        {
          id: 'action2',
          label: 'Action 2',
          onClick: vi.fn(),
        },
      ];

      render(
        <BulkActionBar
          selectedCount={5}
          actions={actions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByLabelText('Action 1')).toBeInTheDocument();
      expect(screen.getByLabelText('Action 2')).toBeInTheDocument();
    });

    it('should call action onClick when button is clicked', () => {
      const onClick = vi.fn();
      const actions: BulkAction[] = [
        {
          id: 'test',
          label: 'Test',
          onClick,
        },
      ];

      render(
        <BulkActionBar
          selectedCount={5}
          actions={actions}
          onClearSelection={vi.fn()}
        />
      );

      fireEvent.click(screen.getByLabelText('Test'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('should disable action when disabled is true', () => {
      const actions: BulkAction[] = [
        {
          id: 'disabled-action',
          label: 'Disabled',
          onClick: vi.fn(),
          disabled: true,
        },
      ];

      render(
        <BulkActionBar
          selectedCount={5}
          actions={actions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByLabelText('Disabled')).toBeDisabled();
    });

    it('should disable action when loading is true', () => {
      const actions: BulkAction[] = [
        {
          id: 'loading-action',
          label: 'Loading',
          onClick: vi.fn(),
          loading: true,
        },
      ];

      render(
        <BulkActionBar
          selectedCount={5}
          actions={actions}
          onClearSelection={vi.fn()}
        />
      );

      expect(screen.getByLabelText('Loading')).toBeDisabled();
    });

    it('should render destructive action with different styling', () => {
      const actions: BulkAction[] = [
        {
          id: 'delete',
          label: 'Delete',
          icon: <Trash2 className="h-4 w-4" />,
          onClick: vi.fn(),
          destructive: true,
        },
      ];

      render(
        <BulkActionBar
          selectedCount={5}
          actions={actions}
          onClearSelection={vi.fn()}
        />
      );

      const deleteButton = screen.getByLabelText('Delete');
      expect(deleteButton).toHaveClass('text-red-400');
    });
  });

  describe('action factories', () => {
    it('createMarkReviewedAction should create correct action', () => {
      const onClick = vi.fn();
      const action = createMarkReviewedAction(onClick, { loading: true });

      expect(action.id).toBe('mark-reviewed');
      expect(action.label).toBe('Mark Reviewed');
      expect(action.loading).toBe(true);

      action.onClick();
      expect(onClick).toHaveBeenCalled();
    });

    it('createExportAction should create correct action', () => {
      const onClick = vi.fn();
      const action = createExportAction(onClick);

      expect(action.id).toBe('export');
      expect(action.label).toBe('Export');
    });

    it('createDeleteAction should create destructive action', () => {
      const onClick = vi.fn();
      const action = createDeleteAction(onClick);

      expect(action.id).toBe('delete');
      expect(action.label).toBe('Delete');
      expect(action.destructive).toBe(true);
    });
  });
});

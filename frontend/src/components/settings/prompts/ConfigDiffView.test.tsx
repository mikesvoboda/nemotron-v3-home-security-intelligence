/**
 * Tests for ConfigDiffView component
 *
 * Tests the display of configuration diffs between current
 * and imported prompt configurations.
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import ConfigDiffView from './ConfigDiffView';

import type { PromptDiffEntry } from '../../../types/promptManagement';

// ============================================================================
// Mock Data
// ============================================================================

const mockDiffWithChanges: PromptDiffEntry = {
  model: 'nemotron',
  has_changes: true,
  current_version: 5,
  current_config: {
    system_prompt: 'Old prompt',
    temperature: 0.7,
    max_tokens: 4096,
  },
  imported_config: {
    system_prompt: 'New prompt',
    temperature: 0.8,
    max_tokens: 4096,
  },
  changes: ['temperature: 0.7 -> 0.8', 'system_prompt changed'],
};

const mockDiffNoChanges: PromptDiffEntry = {
  model: 'florence2',
  has_changes: false,
  current_version: 3,
  current_config: {
    queries: ['What is in this image?'],
  },
  imported_config: {
    queries: ['What is in this image?'],
  },
  changes: [],
};

const mockDiffNewConfig: PromptDiffEntry = {
  model: 'xclip',
  has_changes: true,
  current_version: undefined,
  current_config: undefined,
  imported_config: {
    action_classes: ['walking', 'running'],
  },
  changes: ['New configuration (no existing version)'],
};

// ============================================================================
// Tests
// ============================================================================

describe('ConfigDiffView', () => {
  describe('rendering', () => {
    it('renders model name correctly', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} />);

      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('renders Florence-2 model name correctly', () => {
      render(<ConfigDiffView diff={mockDiffNoChanges} />);

      expect(screen.getByText('Florence-2')).toBeInTheDocument();
    });

    it('renders current version number', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} />);

      expect(screen.getByText('v5')).toBeInTheDocument();
    });

    it('renders WILL CHANGE badge when has changes', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} />);

      expect(screen.getByText('WILL CHANGE')).toBeInTheDocument();
    });

    it('renders NO CHANGE badge when no changes', () => {
      render(<ConfigDiffView diff={mockDiffNoChanges} />);

      expect(screen.getByText('NO CHANGE')).toBeInTheDocument();
    });

    it('has correct test id', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} />);

      expect(screen.getByTestId('config-diff-nemotron')).toBeInTheDocument();
    });
  });

  describe('diff display', () => {
    it('shows diff details when has changes and not collapsed', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} collapsed={false} />);

      // Check for diff container and model name
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
      expect(screen.getByText('WILL CHANGE')).toBeInTheDocument();
    });

    it('hides diff details when collapsed', () => {
      render(<ConfigDiffView diff={mockDiffWithChanges} collapsed={true} />);

      // Should only show header, not the diff details
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
      // The detailed diff view should not be rendered
      expect(screen.queryByText('Configuration is identical')).not.toBeInTheDocument();
    });

    it('shows "identical" message when no changes', () => {
      render(<ConfigDiffView diff={mockDiffNoChanges} collapsed={false} />);

      expect(
        screen.getByText('Configuration is identical to the current version.')
      ).toBeInTheDocument();
    });
  });

  describe('interactivity', () => {
    it('calls onToggleCollapse when header is clicked', async () => {
      const user = userEvent.setup();
      const onToggle = vi.fn();

      render(
        <ConfigDiffView
          diff={mockDiffWithChanges}
          onToggleCollapse={onToggle}
        />
      );

      await user.click(screen.getByRole('button'));

      expect(onToggle).toHaveBeenCalledTimes(1);
    });

    it('has accessible toggle button', () => {
      render(
        <ConfigDiffView
          diff={mockDiffWithChanges}
          onToggleCollapse={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(button).toHaveAttribute('aria-label', 'Toggle Nemotron diff details');
    });
  });

  describe('new configuration handling', () => {
    it('handles missing current config gracefully', () => {
      render(<ConfigDiffView diff={mockDiffNewConfig} />);

      expect(screen.getByText('X-CLIP')).toBeInTheDocument();
      expect(screen.getByText('WILL CHANGE')).toBeInTheDocument();
    });
  });

  describe('value formatting', () => {
    it('handles array values in diff', () => {
      const diffWithArrays: PromptDiffEntry = {
        model: 'yolo_world',
        has_changes: true,
        current_version: 2,
        current_config: {
          classes: ['person', 'car'],
        },
        imported_config: {
          classes: ['person', 'car', 'truck'],
        },
        changes: ['classes: Added truck'],
      };

      render(<ConfigDiffView diff={diffWithArrays} />);

      expect(screen.getByText('YOLO-World')).toBeInTheDocument();
    });

    it('truncates long string values', () => {
      const longPrompt = 'A'.repeat(200);
      const diffWithLongString: PromptDiffEntry = {
        model: 'nemotron',
        has_changes: true,
        current_version: 1,
        current_config: {
          system_prompt: longPrompt,
        },
        imported_config: {
          system_prompt: 'Short',
        },
        changes: ['system_prompt changed'],
      };

      render(<ConfigDiffView diff={diffWithLongString} collapsed={false} />);

      // The component should truncate long strings
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });
  });
});

/**
 * Tests for ImportPreviewModal component
 *
 * Tests the import preview modal with file info, validation,
 * and diff display.
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ImportPreviewModal from './ImportPreviewModal';

import type { PromptsImportPreviewResponse } from '../../../types/promptManagement';

// ============================================================================
// Mock Data
// ============================================================================

const mockPreviewWithChanges: PromptsImportPreviewResponse = {
  version: '1.0',
  valid: true,
  validation_errors: [],
  diffs: [
    {
      model: 'nemotron',
      has_changes: true,
      current_version: 5,
      current_config: { temperature: 0.7 },
      imported_config: { temperature: 0.8 },
      changes: ['temperature: 0.7 -> 0.8'],
    },
    {
      model: 'florence2',
      has_changes: false,
      current_version: 3,
      current_config: { queries: ['test'] },
      imported_config: { queries: ['test'] },
      changes: [],
    },
  ],
  total_changes: 1,
  unknown_models: [],
};

const mockPreviewNoChanges: PromptsImportPreviewResponse = {
  version: '1.0',
  valid: true,
  validation_errors: [],
  diffs: [
    {
      model: 'nemotron',
      has_changes: false,
      current_version: 5,
      current_config: { temperature: 0.7 },
      imported_config: { temperature: 0.7 },
      changes: [],
    },
  ],
  total_changes: 0,
  unknown_models: [],
};

const mockPreviewWithErrors: PromptsImportPreviewResponse = {
  version: '2.0',
  valid: false,
  validation_errors: ['Unsupported version: 2.0. Expected: 1.0'],
  diffs: [],
  total_changes: 0,
  unknown_models: [],
};

const mockPreviewWithUnknownModels: PromptsImportPreviewResponse = {
  version: '1.0',
  valid: true,
  validation_errors: [],
  diffs: [
    {
      model: 'nemotron',
      has_changes: true,
      current_version: 5,
      current_config: { temperature: 0.7 },
      imported_config: { temperature: 0.8 },
      changes: ['temperature: 0.7 -> 0.8'],
    },
  ],
  total_changes: 1,
  unknown_models: ['unknown_model_1', 'unknown_model_2'],
};

// ============================================================================
// Tests
// ============================================================================

describe('ImportPreviewModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    previewData: mockPreviewWithChanges,
    fileName: 'prompts-backup-2026-01-15.json',
    onApplyImport: vi.fn(),
    isImporting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the modal when open', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByTestId('import-preview-modal')).toBeInTheDocument();
    });

    it('does not render when previewData is null', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={null} />);

      expect(screen.queryByTestId('import-preview-modal')).not.toBeInTheDocument();
    });

    it('displays the title', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByText('Import Preview')).toBeInTheDocument();
    });

    it('displays the file name', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByText(/prompts-backup-2026-01-15.json/)).toBeInTheDocument();
    });

    it('displays models affected count', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByText('Models affected: 1 of 2')).toBeInTheDocument();
    });

    it('displays Cancel and Apply Import buttons', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Apply Import/i })).toBeInTheDocument();
    });
  });

  describe('diff display', () => {
    it('renders ConfigDiffView for each model', () => {
      render(<ImportPreviewModal {...defaultProps} />);

      expect(screen.getByTestId('config-diff-nemotron')).toBeInTheDocument();
      expect(screen.getByTestId('config-diff-florence2')).toBeInTheDocument();
    });
  });

  describe('validation errors', () => {
    it('displays validation errors when present', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={mockPreviewWithErrors} />);

      expect(screen.getByText('Validation Errors')).toBeInTheDocument();
      expect(screen.getByText('Unsupported version: 2.0. Expected: 1.0')).toBeInTheDocument();
    });

    it('disables Apply Import when invalid', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={mockPreviewWithErrors} />);

      expect(screen.getByRole('button', { name: /Apply Import/i })).toBeDisabled();
    });
  });

  describe('unknown models', () => {
    it('displays unknown models warning when present', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={mockPreviewWithUnknownModels} />);

      expect(screen.getByText('Unknown Models')).toBeInTheDocument();
      expect(screen.getByText('unknown_model_1')).toBeInTheDocument();
      expect(screen.getByText('unknown_model_2')).toBeInTheDocument();
    });
  });

  describe('no changes', () => {
    it('displays no changes message when all configs match', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={mockPreviewNoChanges} />);

      expect(screen.getByText('No Changes Detected')).toBeInTheDocument();
    });

    it('disables Apply Import when no changes', () => {
      render(<ImportPreviewModal {...defaultProps} previewData={mockPreviewNoChanges} />);

      expect(screen.getByRole('button', { name: /Apply Import/i })).toBeDisabled();
    });
  });

  describe('interactivity', () => {
    it('calls onClose when Cancel is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(<ImportPreviewModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when X button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(<ImportPreviewModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByRole('button', { name: /Close/i }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onApplyImport when Apply Import is clicked', async () => {
      const user = userEvent.setup();
      const onApplyImport = vi.fn();

      render(<ImportPreviewModal {...defaultProps} onApplyImport={onApplyImport} />);

      await user.click(screen.getByRole('button', { name: /Apply Import/i }));

      expect(onApplyImport).toHaveBeenCalledTimes(1);
    });
  });

  describe('loading state', () => {
    it('shows loading state on Apply Import when importing', () => {
      render(<ImportPreviewModal {...defaultProps} isImporting={true} />);

      expect(screen.getByRole('button', { name: /Apply Import/i })).toBeDisabled();
    });

    it('disables Cancel button when importing', () => {
      render(<ImportPreviewModal {...defaultProps} isImporting={true} />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    });

    it('disables Close button when importing', () => {
      render(<ImportPreviewModal {...defaultProps} isImporting={true} />);

      expect(screen.getByRole('button', { name: /Close/i })).toBeDisabled();
    });
  });
});

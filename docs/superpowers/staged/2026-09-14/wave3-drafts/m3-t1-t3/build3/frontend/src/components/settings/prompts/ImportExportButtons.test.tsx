/**
 * Tests for ImportExportButtons component
 *
 * Tests the export and import button functionality including
 * file handling and modal integration.
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ImportExportButtons from './ImportExportButtons';
import * as promptApi from '../../../services/promptManagementApi';

import type {
  PromptsExportResponse,
  PromptsImportPreviewResponse,
  PromptsImportResponse,
} from '../../../types/promptManagement';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../../../services/promptManagementApi', () => ({
  exportPrompts: vi.fn(),
  previewImportPrompts: vi.fn(),
  importPrompts: vi.fn(),
  PromptApiError: class PromptApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public data?: unknown
    ) {
      super(message);
      this.name = 'PromptApiError';
    }
  },
}));

// ============================================================================
// Mock Data
// ============================================================================

const mockExportResponse: PromptsExportResponse = {
  version: '1.0',
  exported_at: '2026-01-17T10:30:00Z',
  prompts: {
    nemotron: { system_prompt: 'Test', temperature: 0.7 },
  },
};

const mockPreviewResponse: PromptsImportPreviewResponse = {
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
  unknown_models: [],
};

const mockImportResponse: PromptsImportResponse = {
  imported_models: ['nemotron'],
  skipped_models: [],
  new_versions: { nemotron: 6 },
  message: 'Successfully imported 1 model configuration',
};

// ============================================================================
// Test Utils
// ============================================================================

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('ImportExportButtons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportResponse);
    (promptApi.previewImportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockPreviewResponse
    );
    (promptApi.importPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockImportResponse);

    // Mock URL methods for download functionality
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = vi.fn();
  });

  describe('rendering', () => {
    it('renders Export and Import buttons', () => {
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      expect(screen.getByRole('button', { name: /Export/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Import/i })).toBeInTheDocument();
    });

    it('renders hidden file input', () => {
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('import-file-input')).toBeInTheDocument();
    });

    it('has correct container test id', () => {
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('import-export-buttons')).toBeInTheDocument();
    });
  });

  describe('export functionality', () => {
    it('calls exportPrompts when Export button is clicked', async () => {
      const user = userEvent.setup();
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      await user.click(screen.getByRole('button', { name: /Export/i }));

      await waitFor(() => {
        expect(promptApi.exportPrompts).toHaveBeenCalled();
      });
    });

    it('creates download link on successful export', async () => {
      const user = userEvent.setup();
      const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
      URL.createObjectURL = mockCreateObjectURL;

      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      await user.click(screen.getByRole('button', { name: /Export/i }));

      await waitFor(() => {
        expect(promptApi.exportPrompts).toHaveBeenCalled();
        expect(mockCreateObjectURL).toHaveBeenCalled();
      });
    });

    it('calls onExportError when export fails', async () => {
      const user = userEvent.setup();
      const onExportError = vi.fn();
      const error = new Error('Export failed');
      (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockRejectedValue(error);

      render(<ImportExportButtons onExportError={onExportError} />, {
        wrapper: createTestWrapper(),
      });

      await user.click(screen.getByRole('button', { name: /Export/i }));

      await waitFor(() => {
        expect(onExportError).toHaveBeenCalledWith(error);
      });
    });
  });

  describe('import functionality', () => {
    it('triggers file input when Import button is clicked', async () => {
      const user = userEvent.setup();
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      const fileInput = screen.getByTestId('import-file-input');
      const clickSpy = vi.spyOn(fileInput, 'click').mockImplementation(() => undefined);

      await user.click(screen.getByRole('button', { name: /Import/i }));

      expect(clickSpy).toHaveBeenCalled();
    });

    // Note: File upload tests are challenging in jsdom due to lack of File.text() support
    // The file handling logic is tested in usePromptImportExport.test.tsx with mocked File objects
    // Integration tests for file upload should be done in E2E tests with a real browser

    it('has file input configured for JSON files', () => {
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      const fileInput = screen.getByTestId('import-file-input');
      expect(fileInput).toHaveAttribute('accept', '.json,application/json');
      expect(fileInput).toHaveAttribute('type', 'file');
    });
  });

  describe('file input', () => {
    it('has accessible label', () => {
      render(<ImportExportButtons />, { wrapper: createTestWrapper() });

      const fileInput = screen.getByTestId('import-file-input');
      expect(fileInput).toHaveAttribute('aria-label', 'Import prompts file');
    });
  });
});

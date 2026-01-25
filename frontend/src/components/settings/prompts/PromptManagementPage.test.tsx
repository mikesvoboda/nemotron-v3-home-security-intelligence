/**
 * Tests for PromptManagementPage component
 *
 * Tests the main prompt management page with model selection,
 * config display, edit modal, and version history.
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import PromptManagementPage from './PromptManagementPage';
import * as promptApi from '../../../services/promptManagementApi';
import { AIModelEnum } from '../../../types/promptManagement';

import type {
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptsExportResponse,
  PromptRestoreResponse,
} from '../../../types/promptManagement';

// ============================================================================
// Mock Data
// ============================================================================

const mockNemotronConfig: ModelPromptConfig = {
  model: AIModelEnum.NEMOTRON,
  config: {
    system_prompt: 'You are an AI security analyst.',
    temperature: 0.7,
    max_tokens: 4096,
  },
  version: 5,
  created_at: '2026-01-07T12:00:00Z',
  created_by: 'admin',
  change_description: 'Improved risk scoring logic',
};

const mockHistory: PromptHistoryResponse = {
  versions: [
    {
      id: 10,
      model: AIModelEnum.NEMOTRON,
      version: 5,
      created_at: '2026-01-07T10:00:00Z',
      created_by: 'admin',
      change_description: 'Improved risk scoring logic',
      is_active: true,
    },
    {
      id: 9,
      model: AIModelEnum.NEMOTRON,
      version: 4,
      created_at: '2026-01-06T15:30:00Z',
      created_by: 'admin',
      change_description: 'Updated context variables',
      is_active: false,
    },
  ],
  total_count: 2,
};

const mockExportResponse: PromptsExportResponse = {
  version: '1.0',
  exported_at: '2026-01-07T12:00:00Z',
  prompts: {
    nemotron: mockNemotronConfig.config,
  },
};

const mockRestoreResponse: PromptRestoreResponse = {
  restored_version: 4,
  model: AIModelEnum.NEMOTRON,
  new_version: 6,
  message: 'Successfully restored version 4 as new version 6',
};

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../../../services/promptManagementApi', () => ({
  fetchPromptForModel: vi.fn(),
  fetchPromptHistory: vi.fn(),
  updatePromptForModel: vi.fn(),
  restorePromptVersion: vi.fn(),
  exportPrompts: vi.fn(),
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
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/settings/prompts?model=nemotron']}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('PromptManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.fetchPromptForModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockNemotronConfig
    );
    (promptApi.fetchPromptHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportResponse);
    (promptApi.restorePromptVersion as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockRestoreResponse
    );

    // Mock URL methods for download functionality
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = vi.fn();
  });

  describe('rendering', () => {
    it('renders the page title', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByText('Prompt Management')).toBeInTheDocument();
      });
    });

    it('renders model selector', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
    });

    it('renders export and import buttons', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Export/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Import/i })).toBeInTheDocument();
      });
    });

    it('renders current configuration tab', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Current Configuration/i })).toBeInTheDocument();
      });
    });

    it('renders version history tab', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Version History/i })).toBeInTheDocument();
      });
    });
  });

  describe('loading current config', () => {
    it('fetches config for selected model', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(promptApi.fetchPromptForModel).toHaveBeenCalledWith(AIModelEnum.NEMOTRON);
      });
    });

    it('displays current version info', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        // Use getAllByText since version can appear in multiple places (title and history)
        const versionElements = screen.getAllByText(/Version 5/i);
        expect(versionElements.length).toBeGreaterThan(0);
      });
    });

    it('displays change description', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        // Use getAllByText since description can appear in multiple places
        const descriptionElements = screen.getAllByText(/Improved risk scoring logic/i);
        expect(descriptionElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('model selection', () => {
    it('renders model selector with initial model from URL', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        // Model selector should be present
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });

      // Initial fetch should use model from URL params (nemotron)
      await waitFor(() => {
        expect(promptApi.fetchPromptForModel).toHaveBeenCalledWith(AIModelEnum.NEMOTRON);
      });

      // Verify all model options are available (Tremor Select may have duplicates)
      expect(screen.getAllByText('Nemotron (Risk Analysis)').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Florence-2 (Scene Analysis)').length).toBeGreaterThan(0);
      expect(screen.getAllByText('YOLO-World (Object Detection)').length).toBeGreaterThan(0);
    });
  });

  describe('edit functionality', () => {
    it('shows Edit button in config display', async () => {
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument();
      });
    });

    it('opens editor modal when Edit is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Edit/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/Edit Nemotron Configuration/i)).toBeInTheDocument();
      });
    });

    it('closes editor modal when Cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument();
      });

      // Open modal
      await user.click(screen.getByRole('button', { name: /Edit/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Close modal
      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('version history', () => {
    it('displays version history when tab is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Version History/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Version History/i }));

      await waitFor(() => {
        expect(screen.getByText('Version 4')).toBeInTheDocument();
        expect(screen.getByText('Updated context variables')).toBeInTheDocument();
      });
    });

    it('shows Restore button for inactive versions', async () => {
      const user = userEvent.setup();
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Version History/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /Version History/i }));

      await waitFor(() => {
        const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
        expect(restoreButtons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('export functionality', () => {
    it('exports prompts when Export button is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Export/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Export/i }));

      await waitFor(() => {
        expect(promptApi.exportPrompts).toHaveBeenCalled();
      });
    });
  });

  describe('error handling', () => {
    it('displays error when config fetch fails', async () => {
      (promptApi.fetchPromptForModel as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to load configuration')
      );

      render(<PromptManagementPage />, { wrapper: createTestWrapper() });

      await waitFor(
        () => {
          expect(screen.getByText(/Error loading data/i)).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });
});

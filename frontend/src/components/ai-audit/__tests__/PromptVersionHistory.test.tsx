/**
 * Tests for PromptVersionHistory component
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { AIModelEnum } from '../../../types/promptManagement';
import PromptVersionHistory from '../PromptVersionHistory';

import type { PromptVersionInfo } from '../../../types/promptManagement';

// Mock the useAIAuditPromptHistoryQuery hook
const mockRefetch = vi.fn();
vi.mock('../../../hooks/useAIAuditQueries', () => ({
  useAIAuditPromptHistoryQuery: vi.fn(() => ({
    data: null,
    isLoading: true,
    error: null,
    refetch: mockRefetch,
  })),
}));

// Mock the restorePromptVersion API
vi.mock('../../../services/promptManagementApi', () => ({
  restorePromptVersion: vi.fn(),
  PromptApiError: class PromptApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'PromptApiError';
    }
  },
}));

// Create a test wrapper with QueryClient
const createTestWrapper = () => {
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
        {children}
      </QueryClientProvider>
    );
  };
};

describe('PromptVersionHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('renders loading skeleton when loading', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('version-history-loading')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('renders error state when query fails', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to fetch'),
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('prompt-version-history-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to Load Version History/i)).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch/i)).toBeInTheDocument();
    });

    it('renders retry button in error state', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Network error'),
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      const retryButton = screen.getByTestId('retry-button');
      expect(retryButton).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('renders empty state when no versions exist', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText(/No Version History/i)).toBeInTheDocument();
    });
  });

  describe('Data Display', () => {
    const mockVersions: PromptVersionInfo[] = [
      {
        id: 1,
        model: AIModelEnum.NEMOTRON,
        version: 3,
        created_at: new Date().toISOString(),
        created_by: 'user@example.com',
        change_description: 'Updated system prompt',
        is_active: true,
      },
      {
        id: 2,
        model: AIModelEnum.NEMOTRON,
        version: 2,
        created_at: new Date(Date.now() - 86400000).toISOString(),
        created_by: 'user@example.com',
        change_description: 'Added weather context',
        is_active: false,
      },
      {
        id: 3,
        model: AIModelEnum.FLORENCE2,
        version: 1,
        created_at: new Date(Date.now() - 172800000).toISOString(),
        created_by: 'user@example.com',
        change_description: 'Initial configuration',
        is_active: false,
      },
    ];

    it('renders version history table with data', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: mockVersions,
          total_count: 3,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('version-history-table')).toBeInTheDocument();
      expect(screen.getByTestId('version-row-1')).toBeInTheDocument();
      expect(screen.getByTestId('version-row-2')).toBeInTheDocument();
      expect(screen.getByTestId('version-row-3')).toBeInTheDocument();
    });

    it('displays version numbers correctly', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: mockVersions,
          total_count: 3,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByText('v3')).toBeInTheDocument();
      expect(screen.getByText('v2')).toBeInTheDocument();
      expect(screen.getByText('v1')).toBeInTheDocument();
    });

    it('displays model names correctly', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: mockVersions,
          total_count: 3,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      // Model names appear in table rows and model selector dropdown
      // We check for presence in the table rows
      const tableRows = screen.getAllByTestId(/^version-row-/);
      expect(tableRows.length).toBe(3);

      // Verify Florence-2 is in the document
      expect(screen.getAllByText('Florence-2').length).toBeGreaterThanOrEqual(1);
    });

    it('displays active badge for current version', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: mockVersions,
          total_count: 3,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getAllByText('Previous').length).toBe(2);
    });

    it('shows restore button only for non-active versions', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: mockVersions,
          total_count: 3,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      // Should not have restore button for active version (id: 1)
      expect(screen.queryByTestId('restore-button-1')).not.toBeInTheDocument();
      // Should have restore buttons for non-active versions
      expect(screen.getByTestId('restore-button-2')).toBeInTheDocument();
      expect(screen.getByTestId('restore-button-3')).toBeInTheDocument();
    });
  });

  describe('Model Filter', () => {
    it('renders model filter dropdown', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByLabelText(/Filter by Model/i)).toBeInTheDocument();
    });
  });

  describe('Refresh Button', () => {
    it('renders refresh button', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('refresh-history-button')).toBeInTheDocument();
    });

    it('calls refetch when refresh button is clicked', async () => {
      const user = userEvent.setup();
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      await user.click(screen.getByTestId('refresh-history-button'));

      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  describe('Restore Functionality', () => {
    const mockVersion: PromptVersionInfo = {
      id: 2,
      model: AIModelEnum.NEMOTRON,
      version: 2,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      created_by: 'user@example.com',
      change_description: 'Previous version',
      is_active: false,
    };

    it('shows success message after successful restore', async () => {
      const user = userEvent.setup();
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      const { restorePromptVersion } = await import('../../../services/promptManagementApi');

      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [mockVersion],
          total_count: 1,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      vi.mocked(restorePromptVersion).mockResolvedValue({
        model: AIModelEnum.NEMOTRON,
        restored_version: 2,
        new_version: 4,
        message: 'Version restored successfully',
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      await user.click(screen.getByTestId('restore-button-2'));

      await waitFor(() => {
        expect(screen.getByTestId('restore-success-banner')).toBeInTheDocument();
      });

      expect(screen.getByText(/Restored Nemotron to version 2/i)).toBeInTheDocument();
    });

    it('shows error message after failed restore', async () => {
      const user = userEvent.setup();
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      const { restorePromptVersion, PromptApiError } = await import('../../../services/promptManagementApi');

      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [mockVersion],
          total_count: 1,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      vi.mocked(restorePromptVersion).mockRejectedValue(
        new PromptApiError(404, 'Version not found')
      );

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      await user.click(screen.getByTestId('restore-button-2'));

      await waitFor(() => {
        expect(screen.getByTestId('restore-error-banner')).toBeInTheDocument();
      });

      expect(screen.getByText(/Version not found/i)).toBeInTheDocument();
    });

    it('calls refetch after successful restore', async () => {
      const user = userEvent.setup();
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      const { restorePromptVersion } = await import('../../../services/promptManagementApi');

      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [mockVersion],
          total_count: 1,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      vi.mocked(restorePromptVersion).mockResolvedValue({
        model: AIModelEnum.NEMOTRON,
        restored_version: 2,
        new_version: 4,
        message: 'Version restored successfully',
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      await user.click(screen.getByTestId('restore-button-2'));

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('Component Structure', () => {
    it('renders the component with correct test ID', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByTestId('prompt-version-history')).toBeInTheDocument();
    });

    it('renders header with title', async () => {
      const { useAIAuditPromptHistoryQuery } = await import('../../../hooks/useAIAuditQueries');
      vi.mocked(useAIAuditPromptHistoryQuery).mockReturnValue({
        data: {
          versions: [],
          total_count: 0,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(<PromptVersionHistory />, { wrapper: createTestWrapper() });

      expect(screen.getByText('Prompt Version History')).toBeInTheDocument();
    });
  });
});

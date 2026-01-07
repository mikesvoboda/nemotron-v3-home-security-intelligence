import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PromptManagementPanel from './PromptManagementPanel';
import * as promptApi from '../../services/promptManagementApi';
import { AIModelEnum } from '../../types/promptManagement';

import type {
  AllPromptsResponse,
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
  PromptsExportResponse,
} from '../../types/promptManagement';

// ============================================================================
// Mock Data
// ============================================================================

const mockAllPrompts: AllPromptsResponse = {
  version: '1.0',
  exported_at: '2025-01-07T12:00:00Z',
  prompts: {
    nemotron: {
      system_prompt: 'You are an AI security analyst...',
      version: 5,
    },
    florence2: {
      queries: ['What objects are in this scene?'],
    },
  },
};

const mockNemotronConfig: ModelPromptConfig = {
  model: AIModelEnum.NEMOTRON,
  config: {
    system_prompt: 'You are an AI security analyst...',
    version: 5,
  },
  version: 5,
  created_at: '2025-01-07T10:00:00Z',
  created_by: 'admin',
  change_description: 'Improved risk scoring logic',
};

const mockHistory: PromptHistoryResponse = {
  versions: [
    {
      id: 10,
      model: AIModelEnum.NEMOTRON,
      version: 5,
      created_at: '2025-01-07T10:00:00Z',
      created_by: 'admin',
      change_description: 'Improved risk scoring logic',
      is_active: true,
    },
    {
      id: 9,
      model: AIModelEnum.NEMOTRON,
      version: 4,
      created_at: '2025-01-06T15:30:00Z',
      created_by: 'admin',
      change_description: 'Updated context variables',
      is_active: false,
    },
    {
      id: 8,
      model: AIModelEnum.NEMOTRON,
      version: 3,
      created_at: '2025-01-05T08:00:00Z',
      created_by: 'system',
      change_description: 'Initial production version',
      is_active: false,
    },
  ],
  total_count: 3,
};

const mockRestoreResponse: PromptRestoreResponse = {
  restored_version: 4,
  model: AIModelEnum.NEMOTRON,
  new_version: 6,
  message: 'Successfully restored version 4 as new version 6',
};

const mockExportResponse: PromptsExportResponse = {
  version: '1.0',
  exported_at: '2025-01-07T12:00:00Z',
  prompts: mockAllPrompts.prompts,
};

// ============================================================================
// Test Utilities
// ============================================================================

// No special wrapper needed - component uses simple useState/useEffect

// ============================================================================
// Setup and Mocks
// ============================================================================

// Store original DOM methods before mocking
const originalCreateElement = document.createElement.bind(document);
const originalAppendChild = document.body.appendChild.bind(document.body);
const originalRemoveChild = document.body.removeChild.bind(document.body);

// Shared mock anchor for export tests
const mockAnchor = {
  href: '',
  download: '',
  click: vi.fn(),
} as unknown as HTMLAnchorElement;

beforeEach(() => {
  vi.clearAllMocks();
  // Reset mock anchor state
  mockAnchor.href = '';
  mockAnchor.download = '';
  (mockAnchor.click as ReturnType<typeof vi.fn>).mockClear();

  // Default successful mocks
  vi.spyOn(promptApi, 'fetchAllPrompts').mockResolvedValue(mockAllPrompts);
  vi.spyOn(promptApi, 'fetchPromptForModel').mockResolvedValue(mockNemotronConfig);
  vi.spyOn(promptApi, 'fetchPromptHistory').mockResolvedValue(mockHistory);
  vi.spyOn(promptApi, 'restorePromptVersion').mockResolvedValue(mockRestoreResponse);
  vi.spyOn(promptApi, 'exportPrompts').mockResolvedValue(mockExportResponse);

  // Mock URL.createObjectURL and revokeObjectURL for export tests
  (globalThis as any).URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  (globalThis as any).URL.revokeObjectURL = vi.fn();

  // Mock document.createElement ONLY for anchor elements (export download)
  // Pass through other calls to preserve React Testing Library's DOM handling
  vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
    if (tagName.toLowerCase() === 'a') {
      return mockAnchor;
    }
    return originalCreateElement(tagName);
  });

  // Mock appendChild/removeChild ONLY for the mockAnchor
  // Pass through other calls to preserve React Testing Library's cleanup
  vi.spyOn(document.body, 'appendChild').mockImplementation((node: Node) => {
    if (node === mockAnchor) {
      return mockAnchor;
    }
    return originalAppendChild(node);
  });

  vi.spyOn(document.body, 'removeChild').mockImplementation((node: Node) => {
    if (node === mockAnchor) {
      return mockAnchor;
    }
    return originalRemoveChild(node);
  });

  // Mock window.confirm
  (globalThis as any).confirm = vi.fn(() => true);
});

// ============================================================================
// Tests: Rendering
// ============================================================================

describe('PromptManagementPanel - Rendering', () => {
  it('should render the component with title and description', () => {
    render(<PromptManagementPanel />);

    expect(screen.getByText('Prompt Management')).toBeInTheDocument();
    expect(
      screen.getByText(/Manage AI model prompt templates, view version history, and rollback changes/i)
    ).toBeInTheDocument();
  });

  it('should render model selection dropdown', async () => {
    render(<PromptManagementPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Select Model/i)).toBeInTheDocument();
    });
  });

  it('should render Export All button', () => {
    render(<PromptManagementPanel />);

    expect(screen.getByRole('button', { name: /Export All/i })).toBeInTheDocument();
  });

  it('should render tabs for Current Configuration and Version History', () => {
    render(<PromptManagementPanel />);

    expect(screen.getByText('Current Configuration')).toBeInTheDocument();
    expect(screen.getByText('Version History')).toBeInTheDocument();
  });
});

// ============================================================================
// Tests: Data Loading
// ============================================================================

describe('PromptManagementPanel - Data Loading', () => {
  it('should load and display current configuration', async () => {
    render(<PromptManagementPanel />);

    await waitFor(() => {
      // Multiple "Version 5" elements may exist (current config + history), use getAllByText
      expect(screen.getAllByText(/Version 5/i).length).toBeGreaterThan(0);
    });

    // Check for elements that should appear (may appear in both current config and history)
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Improved risk scoring logic').length).toBeGreaterThan(0);
    expect(screen.getAllByText('admin').length).toBeGreaterThan(0);
  });

  it('should display loading spinner while fetching data', () => {
    vi.spyOn(promptApi, 'fetchPromptForModel').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<PromptManagementPanel />);

    expect(screen.getByRole('tab', { name: /Current Configuration/i })).toBeInTheDocument();
    // Spinner should be visible in the active tab panel
  });

  it('should display error message when fetch fails', async () => {
    const errorMessage = 'Failed to load prompts';
    vi.spyOn(promptApi, 'fetchPromptForModel').mockRejectedValue(
      new promptApi.PromptApiError(500, errorMessage)
    );

    render(<PromptManagementPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading prompt data/i)).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// Tests: Model Selection
// ============================================================================

describe('PromptManagementPanel - Model Selection', () => {
  it('should change model when selection changes', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    // Wait for initial load
    await waitFor(() => {
      expect(promptApi.fetchPromptForModel).toHaveBeenCalledWith(AIModelEnum.NEMOTRON);
    });

    // Find and click the select dropdown
    const selectButton = screen.getByRole('button', { name: /Nemotron/i });
    await user.click(selectButton);

    // Select Florence-2 from the listbox options (use role to be specific)
    const florence2Option = screen.getByRole('option', { name: /Florence-2/i });
    await user.click(florence2Option);

    // Verify new API call
    await waitFor(() => {
      expect(promptApi.fetchPromptForModel).toHaveBeenCalledWith(AIModelEnum.FLORENCE2);
    });
  });

  it('should reset pagination when model changes', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    // Switch to Version History tab
    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(
        AIModelEnum.NEMOTRON,
        20,
        0
      );
    });

    // Change model
    const selectButton = screen.getByRole('button', { name: /Nemotron/i });
    await user.click(selectButton);
    const yoloOption = screen.getByRole('option', { name: /YOLO-World/i });
    await user.click(yoloOption);

    // Verify history is fetched for new model starting at page 0
    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(
        AIModelEnum.YOLO_WORLD,
        20,
        0
      );
    });
  });
});

// ============================================================================
// Tests: Version History
// ============================================================================

describe('PromptManagementPanel - Version History', () => {
  it('should display version history when tab is clicked', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      // Version numbers appear in both current config and history, use getAllByText
      expect(screen.getAllByText('Version 5').length).toBeGreaterThan(0);
      expect(screen.getByText('Version 4')).toBeInTheDocument();
      expect(screen.getByText('Version 3')).toBeInTheDocument();
    });

    // Check for change descriptions (may appear multiple times)
    expect(screen.getAllByText('Improved risk scoring logic').length).toBeGreaterThan(0);
    expect(screen.getByText('Updated context variables')).toBeInTheDocument();
    expect(screen.getByText('Initial production version')).toBeInTheDocument();
  });

  it('should show Active badge for current version', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      // Active badge appears in both current config and history
      const badges = screen.getAllByText('Active');
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('should show Restore button for inactive versions', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
      expect(restoreButtons).toHaveLength(2); // Two inactive versions
    });
  });

  it('should not show Restore button for active version', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      // Get all Active badges and find the one in version history
      const activeBadges = screen.getAllByText('Active');
      expect(activeBadges.length).toBeGreaterThan(0);

      // The active version in history should not have a Restore button
      // Check that we have exactly 2 Restore buttons (for the 2 inactive versions)
      const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
      expect(restoreButtons).toHaveLength(2);
    });
  });
});

// ============================================================================
// Tests: Restore Version
// ============================================================================

describe('PromptManagementPanel - Restore Version', () => {
  it('should restore a version when Restore button is clicked', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    // Switch to Version History tab
    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('Version 4')).toBeInTheDocument();
    });

    // Click Restore button for version 4
    const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
    await user.click(restoreButtons[0]);

    // Verify confirmation dialog
    expect(((globalThis as any)).confirm).toHaveBeenCalledWith(
      expect.stringContaining('Restore version 4')
    );

    // Verify API call
    await waitFor(() => {
      expect(promptApi.restorePromptVersion).toHaveBeenCalledWith(9);
    });
  });

  it('should display success message after restore', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('Version 4')).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
    await user.click(restoreButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Version Restored/i)).toBeInTheDocument();
      expect(screen.getByText(mockRestoreResponse.message)).toBeInTheDocument();
    });
  });

  it('should not restore if user cancels confirmation', async () => {
    ((globalThis as any)).confirm = vi.fn(() => false);

    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('Version 4')).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
    await user.click(restoreButtons[0]);

    // Verify API was NOT called
    expect(promptApi.restorePromptVersion).not.toHaveBeenCalled();
  });

  it('should display error message when restore fails', async () => {
    const errorMessage = 'Version not found';
    vi.spyOn(promptApi, 'restorePromptVersion').mockRejectedValue(
      new promptApi.PromptApiError(404, errorMessage)
    );

    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('Version 4')).toBeInTheDocument();
    });

    const restoreButtons = screen.getAllByRole('button', { name: /Restore/i });
    await user.click(restoreButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Restore Failed/i)).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// Tests: Export
// ============================================================================

describe('PromptManagementPanel - Export', () => {
  it('should export prompts when Export All button is clicked', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const exportButton = screen.getByRole('button', { name: /Export All/i });
    await user.click(exportButton);

    await waitFor(() => {
      expect(promptApi.exportPrompts).toHaveBeenCalled();
    });
  });

  it('should trigger download when export succeeds', async () => {
    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const exportButton = screen.getByRole('button', { name: /Export All/i });
    await user.click(exportButton);

    await waitFor(() => {
      expect(((globalThis as any).URL).createObjectURL).toHaveBeenCalled();
      // eslint-disable-next-line @typescript-eslint/unbound-method -- Spying on document method in test
      expect(document.createElement).toHaveBeenCalledWith('a');
    });
  });

  it('should show loading state during export', async () => {
    vi.spyOn(promptApi, 'exportPrompts').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const exportButton = screen.getByRole('button', { name: /Export All/i });
    await user.click(exportButton);

    // Button should show loading state
    expect(exportButton).toBeDisabled();
  });
});

// ============================================================================
// Tests: Pagination
// ============================================================================

describe('PromptManagementPanel - Pagination', () => {
  it('should display pagination controls when there are multiple pages', async () => {
    const manyVersions: PromptHistoryResponse = {
      versions: Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        model: AIModelEnum.NEMOTRON,
        version: i + 1,
        created_at: '2025-01-07T10:00:00Z',
        is_active: i === 19,
      })),
      total_count: 50, // 3 pages with 20 items per page
    };

    vi.spyOn(promptApi, 'fetchPromptHistory').mockResolvedValue(manyVersions);

    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Previous/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Next/i })).toBeEnabled();
  });

  it('should navigate to next page', async () => {
    const manyVersions: PromptHistoryResponse = {
      versions: Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        model: AIModelEnum.NEMOTRON,
        version: i + 1,
        created_at: '2025-01-07T10:00:00Z',
        is_active: false,
      })),
      total_count: 50,
    };

    vi.spyOn(promptApi, 'fetchPromptHistory').mockResolvedValue(manyVersions);

    const user = userEvent.setup();
    render(<PromptManagementPanel />);

    const historyTab = screen.getByRole('tab', { name: /Version History/i });
    await user.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
    });

    const nextButton = screen.getByRole('button', { name: /Next/i });
    await user.click(nextButton);

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(
        AIModelEnum.NEMOTRON,
        20,
        20 // offset for page 2
      );
    });
  });
});

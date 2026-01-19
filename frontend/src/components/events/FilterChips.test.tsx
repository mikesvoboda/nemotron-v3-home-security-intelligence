import { describe, it, expect, vi, beforeEach } from 'vitest';

import FilterChips, { FilterChip } from './FilterChips';
import { renderWithProviders, screen, userEvent, waitFor } from '../../test-utils/renderWithProviders';

import type { RiskLevel } from '../../utils/risk';

describe('FilterChip', () => {
  describe('Rendering', () => {
    it('renders with label and count', () => {
      renderWithProviders(<FilterChip label="Critical" count={5} onClick={() => {}} />);

      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('renders without count when count is undefined', () => {
      renderWithProviders(<FilterChip label="Last Hour" onClick={() => {}} />);

      expect(screen.getByText('Last Hour')).toBeInTheDocument();
      expect(screen.queryByText('0')).not.toBeInTheDocument();
    });

    it('renders with zero count when count is 0', () => {
      renderWithProviders(<FilterChip label="Critical" count={0} onClick={() => {}} />);

      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('has aria-pressed attribute based on active state', () => {
      const { rerender } = renderWithProviders(
        <FilterChip label="Test" onClick={() => {}} isActive={false} />
      );

      const chip = screen.getByRole('button', { name: /test/i });
      expect(chip).toHaveAttribute('aria-pressed', 'false');

      rerender(<FilterChip label="Test" onClick={() => {}} isActive={true} />);

      expect(chip).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('Color Variants', () => {
    it('applies critical variant styling', () => {
      renderWithProviders(
        <FilterChip label="Critical" variant="critical" isActive={true} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /critical/i });
      expect(chip).toHaveClass('bg-risk-critical/20');
    });

    it('applies high variant styling', () => {
      renderWithProviders(
        <FilterChip label="High" variant="high" isActive={true} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /high/i });
      expect(chip).toHaveClass('bg-risk-high/20');
    });

    it('applies medium variant styling', () => {
      renderWithProviders(
        <FilterChip label="Medium" variant="medium" isActive={true} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /medium/i });
      expect(chip).toHaveClass('bg-risk-medium/20');
    });

    it('applies low variant styling', () => {
      renderWithProviders(
        <FilterChip label="Low" variant="low" isActive={true} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /low/i });
      expect(chip).toHaveClass('bg-risk-low/20');
    });

    it('applies default variant styling', () => {
      renderWithProviders(
        <FilterChip label="All Risks" variant="default" isActive={true} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /all risks/i });
      expect(chip).toHaveClass('bg-[#76B900]/20');
    });

    it('applies inactive styling when not active', () => {
      renderWithProviders(
        <FilterChip label="Critical" variant="critical" isActive={false} onClick={() => {}} />
      );

      const chip = screen.getByRole('button', { name: /critical/i });
      expect(chip).toHaveClass('border-gray-700');
    });
  });

  describe('Interactions', () => {
    it('calls onClick when clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(<FilterChip label="Test" onClick={handleClick} />);

      await user.click(screen.getByRole('button', { name: /test/i }));

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('is disabled when disabled prop is true', () => {
      renderWithProviders(<FilterChip label="Test" onClick={() => {}} disabled={true} />);

      const chip = screen.getByRole('button', { name: /test/i });
      expect(chip).toBeDisabled();
    });
  });
});

describe('FilterChips', () => {
  const mockRiskCounts: Record<RiskLevel, number> = {
    critical: 3,
    high: 8,
    medium: 15,
    low: 42,
  };

  const mockOnFilterChange = vi.fn();
  const mockOnClearFilters = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders risk level chips with counts', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    it('renders time preset chips', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByText('Last Hour')).toBeInTheDocument();
      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByText('This Week')).toBeInTheDocument();
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });

    it('renders status chips', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByText('Unreviewed')).toBeInTheDocument();
      expect(screen.getByText('With Video')).toBeInTheDocument();
    });

    it('renders Clear All button when filters are active', () => {
      renderWithProviders(
        <FilterChips
          filters={{ risk_level: 'high' }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });

    it('does not render Clear All button when no filters are active', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.queryByRole('button', { name: /clear all/i })).not.toBeInTheDocument();
    });

    it('renders section labels', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByText('Risk Level')).toBeInTheDocument();
      expect(screen.getByText('Time')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });
  });

  describe('Risk Level Filtering', () => {
    it('calls onFilterChange when risk level chip is clicked', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Critical'));

      expect(mockOnFilterChange).toHaveBeenCalledWith('risk_level', 'critical');
    });

    it('highlights active risk level chip', () => {
      renderWithProviders(
        <FilterChips
          filters={{ risk_level: 'high' }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      const highChip = screen.getByRole('button', { name: /high.*8/i });
      expect(highChip).toHaveAttribute('aria-pressed', 'true');
    });

    it('clears risk level filter when clicking active chip', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{ risk_level: 'high' }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('High'));

      expect(mockOnFilterChange).toHaveBeenCalledWith('risk_level', '');
    });
  });

  describe('Time Preset Filtering', () => {
    it('calls onFilterChange with start_date for Last Hour', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Last Hour'));

      expect(mockOnFilterChange).toHaveBeenCalledWith(
        'start_date',
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}/)
      );
    });

    it('calls onFilterChange with start_date for Today', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Today'));

      expect(mockOnFilterChange).toHaveBeenCalledWith(
        'start_date',
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}/)
      );
    });

    it('calls onFilterChange with start_date for This Week', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('This Week'));

      expect(mockOnFilterChange).toHaveBeenCalledWith(
        'start_date',
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}/)
      );
    });

    it('shows date inputs when Custom is clicked', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Custom'));

      await waitFor(() => {
        expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
      });
    });

    it('highlights active time preset based on current filters', () => {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const todayStr = today.toISOString().split('T')[0];

      renderWithProviders(
        <FilterChips
          filters={{ start_date: todayStr }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      const todayChip = screen.getByRole('button', { name: /^today$/i });
      expect(todayChip).toHaveAttribute('aria-pressed', 'true');
    });

    it('clears time filter when clicking active time preset', async () => {
      const user = userEvent.setup();
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const todayStr = today.toISOString().split('T')[0];

      renderWithProviders(
        <FilterChips
          filters={{ start_date: todayStr }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Today'));

      expect(mockOnFilterChange).toHaveBeenCalledWith('start_date', '');
    });
  });

  describe('Status Filtering', () => {
    it('calls onFilterChange when Unreviewed is clicked', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Unreviewed'));

      expect(mockOnFilterChange).toHaveBeenCalledWith('reviewed', false);
    });

    it('highlights Unreviewed when reviewed is false', () => {
      renderWithProviders(
        <FilterChips
          filters={{ reviewed: false }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      const unreviewedChip = screen.getByRole('button', { name: /unreviewed/i });
      expect(unreviewedChip).toHaveAttribute('aria-pressed', 'true');
    });

    it('clears reviewed filter when clicking active Unreviewed chip', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{ reviewed: false }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Unreviewed'));

      expect(mockOnFilterChange).toHaveBeenCalledWith('reviewed', '');
    });
  });

  describe('Clear All', () => {
    it('calls onClearFilters when Clear All is clicked', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{ risk_level: 'high', reviewed: false }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByRole('button', { name: /clear all/i }));

      expect(mockOnClearFilters).toHaveBeenCalledTimes(1);
    });

    it('shows Clear All when any filter is active', () => {
      renderWithProviders(
        <FilterChips
          filters={{ start_date: '2024-01-01' }}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });
  });

  describe('Custom Date Picker', () => {
    it('shows inline date picker when Custom is active', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Custom'));

      await waitFor(() => {
        expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
      });
    });

    it('calls onFilterChange when custom start date is changed', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Custom'));

      const startDateInput = await screen.findByLabelText(/start date/i);
      await user.type(startDateInput, '2024-01-15');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith('start_date', expect.any(String));
      });
    });

    it('calls onFilterChange when custom end date is changed', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Custom'));

      const endDateInput = await screen.findByLabelText(/end date/i);
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith('end_date', expect.any(String));
      });
    });

    it('hides date picker when clicking Custom again', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      await user.click(screen.getByText('Custom'));

      await waitFor(() => {
        expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      });

      await user.click(screen.getByText('Custom'));

      await waitFor(() => {
        expect(screen.queryByLabelText(/start date/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('all chips have proper button roles', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('filter chip bar has proper aria-label', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      expect(screen.getByRole('group', { name: /filter options/i })).toBeInTheDocument();
    });
  });

  describe('With Video Filter', () => {
    it('With Video chip is disabled with tooltip explaining future feature', () => {
      renderWithProviders(
        <FilterChips
          filters={{}}
          riskCounts={mockRiskCounts}
          onFilterChange={mockOnFilterChange}
          onClearFilters={mockOnClearFilters}
        />
      );

      const withVideoChip = screen.getByRole('button', { name: /with video/i });
      expect(withVideoChip).toBeDisabled();
    });
  });
});

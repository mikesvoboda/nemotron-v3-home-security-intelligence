import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import EnrichmentProgressBadge, {
  EnrichmentProgressBar,
  type EnrichmentProgressStatus,
} from './EnrichmentProgressBadge';

describe('EnrichmentProgressBadge', () => {
  describe('rendering by status', () => {
    it('renders nothing when status is not_started', () => {
      const { container } = render(<EnrichmentProgressBadge status="not_started" />);
      expect(container.firstChild).toBeNull();
    });

    it('renders in_progress state with spinner', () => {
      render(<EnrichmentProgressBadge status="in_progress" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('data-status', 'in_progress');
      expect(badge).toHaveTextContent('Enriching...');
      // Check for spinner animation class
      const icon = badge.querySelector('svg');
      expect(icon).toHaveClass('animate-spin');
    });

    it('renders completed state with checkmark', () => {
      render(<EnrichmentProgressBadge status="completed" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('data-status', 'completed');
      expect(badge).toHaveTextContent('Enriched');
      // No animation on completed
      const icon = badge.querySelector('svg');
      expect(icon).not.toHaveClass('animate-spin');
    });

    it('renders failed state with error icon', () => {
      render(<EnrichmentProgressBadge status="failed" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute('data-status', 'failed');
      expect(badge).toHaveTextContent('Failed');
    });
  });

  describe('progress display', () => {
    it('displays progress percentage when in_progress', () => {
      render(<EnrichmentProgressBadge status="in_progress" progress={45} />);
      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    it('displays stage name when provided', () => {
      render(<EnrichmentProgressBadge status="in_progress" stage="Face Detection" />);
      expect(screen.getByText('Face Detection')).toBeInTheDocument();
    });

    it('displays stage and progress together', () => {
      render(
        <EnrichmentProgressBadge status="in_progress" progress={65} stage="License Plate" />
      );
      expect(screen.getByText('License Plate (65%)')).toBeInTheDocument();
    });

    it('hides progress when showProgress is false', () => {
      render(
        <EnrichmentProgressBadge
          status="in_progress"
          progress={45}
          stage="Processing"
          showProgress={false}
        />
      );
      expect(screen.getByText('Processing')).toBeInTheDocument();
      expect(screen.queryByText('45%')).not.toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('renders size variant: %s', (size) => {
      render(<EnrichmentProgressBadge status="in_progress" size={size} />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toBeInTheDocument();
    });

    it('applies small size classes', () => {
      render(<EnrichmentProgressBadge status="in_progress" size="sm" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('px-2', 'py-0.5', 'text-xs');
    });

    it('applies medium size classes', () => {
      render(<EnrichmentProgressBadge status="in_progress" size="md" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('px-2.5', 'py-1', 'text-sm');
    });

    it('applies large size classes', () => {
      render(<EnrichmentProgressBadge status="in_progress" size="lg" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('px-3', 'py-1.5', 'text-base');
    });
  });

  describe('color variants', () => {
    it('applies blue colors for in_progress', () => {
      render(<EnrichmentProgressBadge status="in_progress" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('bg-blue-500/20', 'text-blue-400');
    });

    it('applies green colors for completed', () => {
      render(<EnrichmentProgressBadge status="completed" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('bg-green-500/20', 'text-green-400');
    });

    it('applies red colors for failed', () => {
      render(<EnrichmentProgressBadge status="failed" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('bg-red-500/20', 'text-red-400');
    });
  });

  describe('tooltip and error handling', () => {
    it('shows error message in tooltip when failed', () => {
      render(<EnrichmentProgressBadge status="failed" error="Model timeout" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveAttribute('title', 'Model timeout');
    });

    it('shows stage in tooltip when in progress', () => {
      render(<EnrichmentProgressBadge status="in_progress" stage="Vehicle Detection" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveAttribute('title', 'Vehicle Detection');
    });

    it('allows custom tooltip override', () => {
      render(
        <EnrichmentProgressBadge
          status="in_progress"
          stage="Processing"
          tooltip="Custom tooltip"
        />
      );
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveAttribute('title', 'Custom tooltip');
    });
  });

  describe('label visibility', () => {
    it('shows label by default', () => {
      render(<EnrichmentProgressBadge status="completed" />);
      expect(screen.getByText('Enriched')).toBeInTheDocument();
    });

    it('hides label when showLabel is false', () => {
      render(<EnrichmentProgressBadge status="completed" showLabel={false} />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toBeInTheDocument();
      expect(screen.queryByText('Enriched')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has role="status"', () => {
      render(<EnrichmentProgressBadge status="in_progress" />);
      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });

    it('has descriptive aria-label', () => {
      render(<EnrichmentProgressBadge status="in_progress" progress={50} />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveAttribute('aria-label', 'Enrichment status: 50%');
    });

    it('has aria-label for completed state', () => {
      render(<EnrichmentProgressBadge status="completed" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveAttribute('aria-label', 'Enrichment status: Enriched');
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      render(<EnrichmentProgressBadge status="completed" className="ml-2 mt-1" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('ml-2', 'mt-1');
    });

    it('merges with default classes', () => {
      render(<EnrichmentProgressBadge status="completed" className="custom-class" />);
      const badge = screen.getByTestId('enrichment-progress-badge');
      expect(badge).toHaveClass('custom-class', 'inline-flex', 'items-center');
    });
  });
});

describe('EnrichmentProgressBar', () => {
  describe('rendering', () => {
    it('renders the progress bar', () => {
      render(<EnrichmentProgressBar progress={50} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toBeInTheDocument();
    });

    it('displays correct percentage', () => {
      render(<EnrichmentProgressBar progress={75} />);
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('displays stage name', () => {
      render(<EnrichmentProgressBar progress={30} stage="Face Recognition" />);
      expect(screen.getByText('Face Recognition')).toBeInTheDocument();
    });

    it('shows default text when no stage provided', () => {
      render(<EnrichmentProgressBar progress={40} />);
      expect(screen.getByText('Processing...')).toBeInTheDocument();
    });
  });

  describe('step information', () => {
    it('displays step count when provided', () => {
      render(
        <EnrichmentProgressBar progress={60} currentStep={3} totalSteps={5} />
      );
      expect(screen.getByText('Step 3 / 5')).toBeInTheDocument();
    });

    it('does not show step count when only one is provided', () => {
      render(<EnrichmentProgressBar progress={60} totalSteps={5} />);
      expect(screen.queryByText(/Step/)).not.toBeInTheDocument();
    });
  });

  describe('progress clamping', () => {
    it('clamps progress to maximum 100', () => {
      render(<EnrichmentProgressBar progress={150} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-valuenow', '100');
    });

    it('clamps progress to minimum 0', () => {
      render(<EnrichmentProgressBar progress={-10} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-valuenow', '0');
    });
  });

  describe('accessibility', () => {
    it('has role="progressbar"', () => {
      render(<EnrichmentProgressBar progress={50} />);
      const bar = screen.getByRole('progressbar');
      expect(bar).toBeInTheDocument();
    });

    it('has aria-valuenow set correctly', () => {
      render(<EnrichmentProgressBar progress={65} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-valuenow', '65');
    });

    it('has aria-valuemin and aria-valuemax', () => {
      render(<EnrichmentProgressBar progress={50} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-valuemin', '0');
      expect(bar).toHaveAttribute('aria-valuemax', '100');
    });

    it('has aria-label with stage name', () => {
      render(<EnrichmentProgressBar progress={50} stage="Pose Analysis" />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-label', 'Enriching: Pose Analysis');
    });

    it('has default aria-label without stage', () => {
      render(<EnrichmentProgressBar progress={50} />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveAttribute('aria-label', 'Enrichment in progress');
    });
  });

  describe('animation', () => {
    it('applies transition classes when animated', () => {
      const { container } = render(<EnrichmentProgressBar progress={50} animated={true} />);
      const progressFill = container.querySelector('.bg-gradient-to-r');
      expect(progressFill).toHaveClass('transition-all', 'duration-300');
    });

    it('does not apply transition classes when not animated', () => {
      const { container } = render(<EnrichmentProgressBar progress={50} animated={false} />);
      const progressFill = container.querySelector('.bg-gradient-to-r');
      expect(progressFill).not.toHaveClass('transition-all');
    });
  });

  describe('custom className', () => {
    it('applies custom className', () => {
      render(<EnrichmentProgressBar progress={50} className="mt-4 mb-2" />);
      const bar = screen.getByTestId('enrichment-progress-bar');
      expect(bar).toHaveClass('mt-4', 'mb-2');
    });
  });
});

describe('status type coverage', () => {
  const statuses: EnrichmentProgressStatus[] = [
    'not_started',
    'in_progress',
    'completed',
    'failed',
  ];

  it.each(statuses)('handles status: %s without errors', (status) => {
    if (status === 'not_started') {
      const { container } = render(<EnrichmentProgressBadge status={status} />);
      expect(container.firstChild).toBeNull();
    } else {
      render(<EnrichmentProgressBadge status={status} />);
      expect(screen.getByTestId('enrichment-progress-badge')).toBeInTheDocument();
    }
  });
});

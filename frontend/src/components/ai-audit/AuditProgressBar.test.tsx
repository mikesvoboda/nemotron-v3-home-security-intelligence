/**
 * Tests for AuditProgressBar component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import AuditProgressBar from './AuditProgressBar';

describe('AuditProgressBar', () => {
  it('displays current progress and total count', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    expect(screen.getByText(/25.*\/.*100/)).toBeInTheDocument();
  });

  it('displays progress percentage', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    expect(screen.getByText(/25%/)).toBeInTheDocument();
  });

  it('renders progress bar with correct width', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveStyle({ width: '25%' });
  });

  it('displays ETA in seconds when under 1 minute', () => {
    render(<AuditProgressBar current={25} total={100} eta={45} onCancel={vi.fn()} />);

    expect(screen.getByText(/45s/)).toBeInTheDocument();
  });

  it('displays ETA in minutes when over 1 minute', () => {
    render(<AuditProgressBar current={25} total={100} eta={90} onCancel={vi.fn()} />);

    expect(screen.getByText(/1m 30s/)).toBeInTheDocument();
  });

  it('displays current event ID when provided', () => {
    render(
      <AuditProgressBar
        current={25}
        total={100}
        eta={60}
        currentEventId={12345}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText(/Event #12345/i)).toBeInTheDocument();
  });

  it('does not display event ID when not provided', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    expect(screen.queryByText(/Event #/i)).not.toBeInTheDocument();
  });

  it('renders cancel button', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={onCancel} />);

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('displays 0% when current is 0', () => {
    render(<AuditProgressBar current={0} total={100} eta={120} onCancel={vi.fn()} />);

    expect(screen.getByText(/0%/)).toBeInTheDocument();
  });

  it('displays 100% when current equals total', () => {
    render(<AuditProgressBar current={100} total={100} eta={0} onCancel={vi.fn()} />);

    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });

  it('renders with correct data-testid', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    expect(screen.getByTestId('audit-progress-bar')).toBeInTheDocument();
  });

  it('renders accessible progress bar with correct attributes', () => {
    render(<AuditProgressBar current={25} total={100} eta={60} onCancel={vi.fn()} />);

    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '25');
    expect(progressBar).toHaveAttribute('aria-valuemin', '0');
    expect(progressBar).toHaveAttribute('aria-valuemax', '100');
  });

  it('displays completion message when at 100%', () => {
    render(<AuditProgressBar current={100} total={100} eta={0} onCancel={vi.fn()} />);

    expect(screen.getByText(/complete/i)).toBeInTheDocument();
  });
});

/**
 * Tests for JobErrorModal component
 *
 * @see NEM-3593
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import JobErrorModal from './JobErrorModal';

describe('JobErrorModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    jobId: 'export-123',
    jobType: 'export',
    errorMessage: 'Connection timeout',
    errorTraceback: null,
    failedAt: '2024-01-15T10:32:00Z',
    attemptNumber: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders when open', () => {
    render(<JobErrorModal {...defaultProps} />);

    expect(screen.getByTestId('job-error-modal')).toBeInTheDocument();
    expect(screen.getByText('Error Details')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<JobErrorModal {...defaultProps} isOpen={false} />);

    expect(screen.queryByTestId('job-error-modal')).not.toBeInTheDocument();
  });

  it('displays job information correctly', () => {
    render(<JobErrorModal {...defaultProps} />);

    expect(screen.getByText(/Export/)).toBeInTheDocument();
    expect(screen.getByText(/#123/)).toBeInTheDocument();
  });

  it('displays error message', () => {
    render(<JobErrorModal {...defaultProps} />);

    expect(screen.getByText('Connection timeout')).toBeInTheDocument();
  });

  it('displays error traceback when provided', () => {
    const traceback = `Traceback (most recent call last):
  File "/app/services/export.py", line 142, in export_data
    result = process_batch(batch)
ExportError: Connection timeout`;

    render(<JobErrorModal {...defaultProps} errorTraceback={traceback} />);

    expect(screen.getByTestId('error-traceback')).toBeInTheDocument();
    // Use getByRole or getAllByText since "Traceback" appears in header and content
    expect(screen.getAllByText(/Traceback/).length).toBeGreaterThan(0);
  });

  it('does not display traceback section when not provided', () => {
    render(<JobErrorModal {...defaultProps} errorTraceback={null} />);

    expect(screen.queryByTestId('error-traceback')).not.toBeInTheDocument();
  });

  it('displays attempt number when provided', () => {
    render(<JobErrorModal {...defaultProps} attemptNumber={2} />);

    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('displays failed timestamp when provided', () => {
    render(<JobErrorModal {...defaultProps} failedAt="2024-01-15T10:32:00Z" />);

    // Should show formatted date
    expect(screen.getByText(/Jan/)).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(<JobErrorModal {...defaultProps} />);

    const closeButton = screen.getByLabelText('Close modal');
    fireEvent.click(closeButton);

    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Close button in footer is clicked', () => {
    render(<JobErrorModal {...defaultProps} />);

    const closeButton = screen.getByRole('button', { name: 'Close' });
    fireEvent.click(closeButton);

    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('copies error content to clipboard when Copy button is clicked', async () => {
    render(<JobErrorModal {...defaultProps} />);

    const copyButton = screen.getByTestId('copy-button');
    fireEvent.click(copyButton);

    // eslint-disable-next-line @typescript-eslint/unbound-method -- clipboard.writeText is a mock
    const writeTextMock = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalled();
    });

    // Should show "Copied!" feedback
    expect(screen.getByText('Copied!')).toBeInTheDocument();
  });

  it('includes job info in copied content', async () => {
    const traceback = 'Full error traceback';
    render(<JobErrorModal {...defaultProps} errorTraceback={traceback} />);

    const copyButton = screen.getByTestId('copy-button');
    fireEvent.click(copyButton);

    // eslint-disable-next-line @typescript-eslint/unbound-method -- clipboard.writeText is a mock
    const writeTextMock = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalled();
    });

    const copiedContent = writeTextMock.mock.calls[0][0] as string;
    expect(copiedContent).toContain('Export');
    expect(copiedContent).toContain('#123');
    expect(copiedContent).toContain('Connection timeout');
    expect(copiedContent).toContain('Full error traceback');
  });

  it('handles short job IDs', () => {
    render(<JobErrorModal {...defaultProps} jobId="42" />);

    expect(screen.getByText(/42/)).toBeInTheDocument();
  });

  it('handles UUID job IDs by extracting trailing number', () => {
    render(<JobErrorModal {...defaultProps} jobId="550e8400-e29b-41d4-a716-446655440000" />);

    // The formatJobId function extracts the trailing number from the ID
    // "550e8400-e29b-41d4-a716-446655440000" -> "#446655440000"
    const modalContent = screen.getByTestId('job-error-modal');
    expect(modalContent.textContent).toContain('#446655440000');
  });

  it('formats job type with capital first letter', () => {
    render(<JobErrorModal {...defaultProps} jobType="cleanup" />);

    expect(screen.getByText(/Cleanup/)).toBeInTheDocument();
  });
});

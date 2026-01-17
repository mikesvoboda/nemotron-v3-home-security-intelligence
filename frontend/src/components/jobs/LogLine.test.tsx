import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import LogLine from './LogLine';

import type { JobLogEntryResponse } from '../../types/generated';

describe('LogLine', () => {
  const baseLog: JobLogEntryResponse = {
    timestamp: '2024-01-15T10:30:00Z',
    level: 'INFO',
    message: 'Starting export job',
    attempt_number: 1,
    context: null,
  };

  describe('rendering', () => {
    it('renders timestamp', () => {
      render(<LogLine log={baseLog} />);

      // Should have a timestamp element (time format varies by timezone)
      const timestampElement = screen.getByTestId('log-timestamp');
      expect(timestampElement).toBeInTheDocument();
      // Should contain time-like pattern (HH:MM:SS)
      expect(timestampElement.textContent).toMatch(/\d{2}:\d{2}:\d{2}/);
    });

    it('renders log level', () => {
      render(<LogLine log={baseLog} />);

      expect(screen.getByText('INFO')).toBeInTheDocument();
    });

    it('renders message', () => {
      render(<LogLine log={baseLog} />);

      expect(screen.getByText('Starting export job')).toBeInTheDocument();
    });
  });

  describe('log level styling', () => {
    it('applies gray styling for DEBUG level', () => {
      const debugLog: JobLogEntryResponse = { ...baseLog, level: 'DEBUG' };
      render(<LogLine log={debugLog} />);

      const levelElement = screen.getByText('DEBUG');
      expect(levelElement).toHaveClass('text-gray-500');
    });

    it('applies white styling for INFO level', () => {
      const infoLog: JobLogEntryResponse = { ...baseLog, level: 'INFO' };
      render(<LogLine log={infoLog} />);

      const levelElement = screen.getByText('INFO');
      expect(levelElement).toHaveClass('text-white');
    });

    it('applies yellow styling for WARN level', () => {
      const warnLog: JobLogEntryResponse = { ...baseLog, level: 'WARN' };
      render(<LogLine log={warnLog} />);

      const levelElement = screen.getByText('WARN');
      expect(levelElement).toHaveClass('text-yellow-400');
    });

    it('applies red styling for ERROR level', () => {
      const errorLog: JobLogEntryResponse = { ...baseLog, level: 'ERROR' };
      render(<LogLine log={errorLog} />);

      const levelElement = screen.getByText('ERROR');
      expect(levelElement).toHaveClass('text-red-400');
    });

    it('applies default styling for unknown level', () => {
      // Casting to test unknown levels
      const unknownLog: JobLogEntryResponse = { ...baseLog, level: 'TRACE' as string };
      render(<LogLine log={unknownLog} />);

      const levelElement = screen.getByText('TRACE');
      expect(levelElement).toHaveClass('text-gray-400');
    });
  });

  describe('timestamp formatting', () => {
    it('formats timestamp to show time', () => {
      render(<LogLine log={baseLog} />);

      // Should contain the time portion
      const timestampElement = screen.getByTestId('log-timestamp');
      expect(timestampElement).toBeInTheDocument();
    });

    it('handles invalid timestamp gracefully', () => {
      const invalidLog: JobLogEntryResponse = { ...baseLog, timestamp: 'invalid-date' };
      render(<LogLine log={invalidLog} />);

      // Should render something even with invalid date
      expect(screen.getByTestId('log-timestamp')).toBeInTheDocument();
    });
  });

  describe('context display', () => {
    it('does not show context indicator when context is null', () => {
      render(<LogLine log={baseLog} />);

      expect(screen.queryByTestId('log-context')).not.toBeInTheDocument();
    });

    it('shows context indicator when context is provided', () => {
      const logWithContext: JobLogEntryResponse = {
        ...baseLog,
        context: { event_count: 1000, batch_id: 'batch-123' },
      };
      render(<LogLine log={logWithContext} />);

      expect(screen.getByTestId('log-context')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate structure for screen readers', () => {
      render(<LogLine log={baseLog} />);

      // Should have a container element
      const container = screen.getByRole('listitem');
      expect(container).toBeInTheDocument();
    });
  });

  describe('attempt number', () => {
    it('shows attempt number when greater than 1', () => {
      const retryLog: JobLogEntryResponse = { ...baseLog, attempt_number: 2 };
      render(<LogLine log={retryLog} />);

      expect(screen.getByText(/attempt 2/i)).toBeInTheDocument();
    });

    it('does not show attempt number when 1', () => {
      render(<LogLine log={baseLog} />);

      expect(screen.queryByText(/attempt/i)).not.toBeInTheDocument();
    });
  });
});

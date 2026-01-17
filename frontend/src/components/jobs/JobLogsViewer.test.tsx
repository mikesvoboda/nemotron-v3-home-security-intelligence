/**
 * Tests for JobLogsViewer component (TDD RED)
 *
 * Displays job logs with real-time streaming via WebSocket.
 * Features:
 * - Connection indicator showing status
 * - Auto-scroll to latest logs
 * - Log level filtering
 * - Manual log fetching fallback
 *
 * NEM-2711
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import JobLogsViewer from './JobLogsViewer';

import type { JobLogEntry, UseJobLogsWebSocketReturn } from '../../hooks/useJobLogsWebSocket';

// Mock useJobLogsWebSocket hook with proper typing
const mockClearLogs = vi.fn();
const mockUseJobLogsWebSocket = vi.fn<(options?: unknown) => UseJobLogsWebSocketReturn>(() => ({
  logs: [],
  status: 'disconnected',
  isConnected: false,
  reconnectCount: 0,
  hasExhaustedRetries: false,
  clearLogs: mockClearLogs,
}));

vi.mock('../../hooks/useJobLogsWebSocket', () => ({
  useJobLogsWebSocket: (options: unknown) => {
    mockUseJobLogsWebSocket(options);
    return mockUseJobLogsWebSocket();
  },
}));

// Helper to create test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// Helper to create mock log entries
function createMockLog(overrides: Partial<JobLogEntry> = {}): JobLogEntry {
  return {
    timestamp: '2026-01-17T10:32:05Z',
    level: 'INFO',
    message: 'Test log message',
    ...overrides,
  };
}

describe('JobLogsViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseJobLogsWebSocket.mockReturnValue({
      logs: [],
      status: 'disconnected',
      isConnected: false,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      clearLogs: mockClearLogs,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders without crashing', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByTestId('job-logs-viewer')).toBeInTheDocument();
    });

    it('shows section title', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByText('Job Logs')).toBeInTheDocument();
    });

    it('shows connection indicator', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
    });
  });

  describe('connection states', () => {
    it('passes enabled prop to useJobLogsWebSocket', () => {
      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(mockUseJobLogsWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          jobId: 'job-123',
          enabled: true,
        })
      );
    });

    it('shows connected state in indicator', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-green-500');
    });

    it('shows reconnecting state in indicator', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [],
        status: 'reconnecting',
        isConnected: false,
        reconnectCount: 2,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-yellow-500');
    });

    it('shows failed state in indicator', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [],
        status: 'failed',
        isConnected: false,
        reconnectCount: 5,
        hasExhaustedRetries: true,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const dot = screen.getByTestId('connection-dot');
      expect(dot).toHaveClass('bg-red-500');
    });
  });

  describe('log display', () => {
    it('shows empty state when no logs', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByText(/no logs/i)).toBeInTheDocument();
    });

    it('displays log entries', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [
          createMockLog({ message: 'First log message', level: 'INFO' }),
          createMockLog({ message: 'Second log message', level: 'WARNING', timestamp: '2026-01-17T10:32:10Z' }),
        ],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByText('First log message')).toBeInTheDocument();
      expect(screen.getByText('Second log message')).toBeInTheDocument();
    });

    it('shows log level badges', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [
          createMockLog({ message: 'Info log', level: 'INFO' }),
          createMockLog({ message: 'Warning log', level: 'WARNING', timestamp: '2026-01-17T10:32:10Z' }),
          createMockLog({ message: 'Error log', level: 'ERROR', timestamp: '2026-01-17T10:32:15Z' }),
        ],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByText('INFO')).toBeInTheDocument();
      expect(screen.getByText('WARNING')).toBeInTheDocument();
      expect(screen.getByText('ERROR')).toBeInTheDocument();
    });

    it('shows log timestamps', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog({ timestamp: '2026-01-17T10:32:05Z' })],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      // Timestamp is displayed in local time, so check for time format rather than exact value
      expect(screen.getByText(/\d{2}:\d{2}:\d{2}/)).toBeInTheDocument();
    });

    it('shows log count', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [
          createMockLog({ message: 'Log 1' }),
          createMockLog({ message: 'Log 2', timestamp: '2026-01-17T10:32:10Z' }),
          createMockLog({ message: 'Log 3', timestamp: '2026-01-17T10:32:15Z' }),
        ],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByText(/3 logs/i)).toBeInTheDocument();
    });
  });

  describe('log level filtering', () => {
    beforeEach(() => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [
          createMockLog({ message: 'Debug log', level: 'DEBUG', timestamp: '2026-01-17T10:32:00Z' }),
          createMockLog({ message: 'Info log', level: 'INFO', timestamp: '2026-01-17T10:32:05Z' }),
          createMockLog({ message: 'Warning log', level: 'WARNING', timestamp: '2026-01-17T10:32:10Z' }),
          createMockLog({ message: 'Error log', level: 'ERROR', timestamp: '2026-01-17T10:32:15Z' }),
        ],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });
    });

    it('shows all logs by default', () => {
      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByText('Debug log')).toBeInTheDocument();
      expect(screen.getByText('Info log')).toBeInTheDocument();
      expect(screen.getByText('Warning log')).toBeInTheDocument();
      expect(screen.getByText('Error log')).toBeInTheDocument();
    });

    it('filters by ERROR level', () => {
      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });

      // Find and click the filter dropdown
      const filterButton = screen.getByLabelText(/filter/i);
      fireEvent.click(filterButton);

      // Select ERROR option
      const errorOption = screen.getByRole('option', { name: /error/i });
      fireEvent.click(errorOption);

      // Only error log should be visible
      expect(screen.queryByText('Debug log')).not.toBeInTheDocument();
      expect(screen.queryByText('Info log')).not.toBeInTheDocument();
      expect(screen.queryByText('Warning log')).not.toBeInTheDocument();
      expect(screen.getByText('Error log')).toBeInTheDocument();
    });

    it('filters by WARNING level and above', () => {
      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });

      const filterButton = screen.getByLabelText(/filter/i);
      fireEvent.click(filterButton);

      const warningOption = screen.getByRole('option', { name: /warning/i });
      fireEvent.click(warningOption);

      expect(screen.queryByText('Debug log')).not.toBeInTheDocument();
      expect(screen.queryByText('Info log')).not.toBeInTheDocument();
      expect(screen.getByText('Warning log')).toBeInTheDocument();
      expect(screen.getByText('Error log')).toBeInTheDocument();
    });
  });

  describe('controls', () => {
    it('has clear logs button', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });

    it('calls clearLogs when clear button clicked', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const clearButton = screen.getByRole('button', { name: /clear/i });
      fireEvent.click(clearButton);
      expect(mockClearLogs).toHaveBeenCalled();
    });

    it('disables clear button when no logs', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      const clearButton = screen.getByRole('button', { name: /clear/i });
      expect(clearButton).toBeDisabled();
    });

    it('has auto-scroll toggle', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByRole('button', { name: /auto-scroll/i })).toBeInTheDocument();
    });

    it('toggles auto-scroll when button clicked', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      const autoScrollButton = screen.getByRole('button', { name: /auto-scroll/i });

      // Initially enabled
      expect(autoScrollButton).toHaveAttribute('aria-pressed', 'true');

      fireEvent.click(autoScrollButton);

      // Now disabled
      expect(autoScrollButton).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(
        <JobLogsViewer jobId="job-123" enabled={false} className="custom-class" />,
        { wrapper: createWrapper() }
      );
      expect(screen.getByTestId('job-logs-viewer')).toHaveClass('custom-class');
    });

    it('applies correct color for DEBUG level', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog({ level: 'DEBUG' })],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const badge = screen.getByText('DEBUG');
      expect(badge).toHaveClass('text-gray-400');
    });

    it('applies correct color for INFO level', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog({ level: 'INFO' })],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const badge = screen.getByText('INFO');
      expect(badge).toHaveClass('text-blue-400');
    });

    it('applies correct color for WARNING level', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog({ level: 'WARNING' })],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const badge = screen.getByText('WARNING');
      expect(badge).toHaveClass('text-yellow-400');
    });

    it('applies correct color for ERROR level', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog({ level: 'ERROR' })],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const badge = screen.getByText('ERROR');
      expect(badge).toHaveClass('text-red-400');
    });
  });

  describe('accessibility', () => {
    it('has appropriate section heading', () => {
      render(<JobLogsViewer jobId="job-123" enabled={false} />, { wrapper: createWrapper() });
      expect(screen.getByRole('heading', { name: /job logs/i })).toBeInTheDocument();
    });

    it('has accessible log list', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      expect(screen.getByRole('log')).toBeInTheDocument();
    });

    it('announces new logs to screen readers', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const logContainer = screen.getByRole('log');
      expect(logContainer).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('max height and scrolling', () => {
    it('applies max height to log container', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} maxHeight={400} />, {
        wrapper: createWrapper(),
      });
      const logContainer = screen.getByRole('log');
      expect(logContainer).toHaveStyle({ maxHeight: '400px' });
    });

    it('has overflow-y-auto for scrolling', () => {
      mockUseJobLogsWebSocket.mockReturnValue({
        logs: [createMockLog()],
        status: 'connected',
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        clearLogs: mockClearLogs,
      });

      render(<JobLogsViewer jobId="job-123" enabled={true} />, { wrapper: createWrapper() });
      const logContainer = screen.getByRole('log');
      expect(logContainer).toHaveClass('overflow-y-auto');
    });
  });
});

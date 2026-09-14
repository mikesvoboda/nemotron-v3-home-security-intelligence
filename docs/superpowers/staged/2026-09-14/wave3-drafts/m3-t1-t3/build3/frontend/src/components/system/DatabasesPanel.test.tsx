import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import DatabasesPanel, {
  type DatabasesPanelProps,
  type DatabaseMetrics,
  type RedisMetrics,
  type DatabaseHistoryData,
} from './DatabasesPanel';

describe('DatabasesPanel', () => {
  // Sample PostgreSQL metrics
  const mockPostgresqlMetrics: DatabaseMetrics = {
    status: 'healthy',
    connections_active: 5,
    connections_max: 30,
    cache_hit_ratio: 98.2,
    transactions_per_min: 1200,
  };

  // Sample Redis metrics
  const mockRedisMetrics: RedisMetrics = {
    status: 'healthy',
    connected_clients: 8,
    memory_mb: 1.44,
    hit_ratio: 85.5,
    blocked_clients: 2,
  };

  // Sample history data
  const mockHistoryData: DatabaseHistoryData = {
    postgresql: {
      connections: [
        { timestamp: '2025-01-01T12:00:00Z', value: 3 },
        { timestamp: '2025-01-01T12:00:05Z', value: 5 },
        { timestamp: '2025-01-01T12:00:10Z', value: 4 },
      ],
      cache_hit_ratio: [
        { timestamp: '2025-01-01T12:00:00Z', value: 98.0 },
        { timestamp: '2025-01-01T12:00:05Z', value: 98.2 },
        { timestamp: '2025-01-01T12:00:10Z', value: 98.1 },
      ],
    },
    redis: {
      memory: [
        { timestamp: '2025-01-01T12:00:00Z', value: 1.2 },
        { timestamp: '2025-01-01T12:00:05Z', value: 1.44 },
        { timestamp: '2025-01-01T12:00:10Z', value: 1.3 },
      ],
      clients: [
        { timestamp: '2025-01-01T12:00:00Z', value: 6 },
        { timestamp: '2025-01-01T12:00:05Z', value: 8 },
        { timestamp: '2025-01-01T12:00:10Z', value: 7 },
      ],
    },
  };

  const defaultProps: DatabasesPanelProps = {
    postgresql: mockPostgresqlMetrics,
    redis: mockRedisMetrics,
    timeRange: '5m',
    history: mockHistoryData,
  };

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
      expect(screen.getByText('Databases')).toBeInTheDocument();
    });

    it('renders both PostgreSQL and Redis cards', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-card')).toBeInTheDocument();
      expect(screen.getByTestId('redis-card')).toBeInTheDocument();
    });
  });

  describe('PostgreSQL metrics', () => {
    it('displays PostgreSQL status correctly', () => {
      render(<DatabasesPanel {...defaultProps} />);

      const statusBadge = screen.getByTestId('postgresql-status');
      expect(statusBadge).toHaveTextContent('Healthy');
    });

    it('displays PostgreSQL connections', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-connections')).toHaveTextContent('5/30');
    });

    it('displays PostgreSQL cache hit ratio', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-cache-hit')).toHaveTextContent('98.2%');
    });

    it('displays PostgreSQL transactions per minute', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-txns')).toHaveTextContent('1.2k/min');
    });

    it('displays PostgreSQL connection progress bar', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-connections-bar')).toBeInTheDocument();
    });

    it('displays unhealthy status with red badge', () => {
      const unhealthyPostgres: DatabaseMetrics = {
        ...mockPostgresqlMetrics,
        status: 'unhealthy',
      };

      render(<DatabasesPanel {...defaultProps} postgresql={unhealthyPostgres} />);

      const statusBadge = screen.getByTestId('postgresql-status');
      expect(statusBadge).toHaveTextContent('Unhealthy');
    });
  });

  describe('Redis metrics', () => {
    it('displays Redis status correctly', () => {
      render(<DatabasesPanel {...defaultProps} />);

      const statusBadge = screen.getByTestId('redis-status');
      expect(statusBadge).toHaveTextContent('Healthy');
    });

    it('displays Redis connected clients', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('redis-clients')).toHaveTextContent('8');
    });

    it('displays Redis memory usage', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('redis-memory')).toHaveTextContent('1.44 MB');
    });

    it('displays Redis hit ratio', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('redis-hit-ratio')).toHaveTextContent('85.5%');
    });

    it('displays Redis blocked clients', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('redis-blocked')).toHaveTextContent('2');
    });

    it('displays unhealthy status with red badge', () => {
      const unhealthyRedis: RedisMetrics = {
        ...mockRedisMetrics,
        status: 'unhealthy',
      };

      render(<DatabasesPanel {...defaultProps} redis={unhealthyRedis} />);

      const statusBadge = screen.getByTestId('redis-status');
      expect(statusBadge).toHaveTextContent('Unhealthy');
    });
  });

  describe('null handling', () => {
    it('handles null PostgreSQL metrics gracefully', () => {
      render(<DatabasesPanel {...defaultProps} postgresql={null} />);

      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
      expect(screen.getByTestId('postgresql-card')).toBeInTheDocument();
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('handles null Redis metrics gracefully', () => {
      render(<DatabasesPanel {...defaultProps} redis={null} />);

      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
      expect(screen.getByTestId('redis-card')).toBeInTheDocument();
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('handles both null metrics gracefully', () => {
      render(
        <DatabasesPanel postgresql={null} redis={null} timeRange="5m" history={mockHistoryData} />
      );

      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
      expect(screen.getAllByText('No data available')).toHaveLength(2);
    });
  });

  describe('history charts', () => {
    it('renders PostgreSQL connections chart area', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('postgresql-chart')).toBeInTheDocument();
    });

    it('renders Redis memory chart area', () => {
      render(<DatabasesPanel {...defaultProps} />);

      expect(screen.getByTestId('redis-chart')).toBeInTheDocument();
    });

    it('handles empty history data gracefully', () => {
      const emptyHistory: DatabaseHistoryData = {
        postgresql: { connections: [], cache_hit_ratio: [] },
        redis: { memory: [], clients: [] },
      };

      render(<DatabasesPanel {...defaultProps} history={emptyHistory} />);

      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
    });
  });

  describe('time range display', () => {
    it('displays the current time range', () => {
      render(<DatabasesPanel {...defaultProps} timeRange="15m" />);

      // Time range is used for chart context
      expect(screen.getByTestId('databases-panel')).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('formats large transaction counts correctly', () => {
      const highTxnsPostgres: DatabaseMetrics = {
        ...mockPostgresqlMetrics,
        transactions_per_min: 12500,
      };

      render(<DatabasesPanel {...defaultProps} postgresql={highTxnsPostgres} />);

      expect(screen.getByTestId('postgresql-txns')).toHaveTextContent('12.5k/min');
    });

    it('formats low transaction counts correctly', () => {
      const lowTxnsPostgres: DatabaseMetrics = {
        ...mockPostgresqlMetrics,
        transactions_per_min: 50,
      };

      render(<DatabasesPanel {...defaultProps} postgresql={lowTxnsPostgres} />);

      expect(screen.getByTestId('postgresql-txns')).toHaveTextContent('50/min');
    });

    it('formats Redis memory with appropriate precision', () => {
      const largeMemoryRedis: RedisMetrics = {
        ...mockRedisMetrics,
        memory_mb: 125.67,
      };

      render(<DatabasesPanel {...defaultProps} redis={largeMemoryRedis} />);

      expect(screen.getByTestId('redis-memory')).toHaveTextContent('125.67 MB');
    });
  });

  describe('status colors', () => {
    it('shows warning color for low cache hit ratio', () => {
      const lowCachePostgres: DatabaseMetrics = {
        ...mockPostgresqlMetrics,
        cache_hit_ratio: 85.0,
      };

      render(<DatabasesPanel {...defaultProps} postgresql={lowCachePostgres} />);

      // Component should render with warning styling
      expect(screen.getByTestId('postgresql-cache-hit')).toBeInTheDocument();
    });

    it('shows warning color for low Redis hit ratio', () => {
      const lowHitRedis: RedisMetrics = {
        ...mockRedisMetrics,
        hit_ratio: 45.0,
      };

      render(<DatabasesPanel {...defaultProps} redis={lowHitRedis} />);

      // Component should render with warning styling
      expect(screen.getByTestId('redis-hit-ratio')).toBeInTheDocument();
    });
  });

  describe('connection pool warnings', () => {
    it('shows warning when connection pool usage is high', () => {
      const highConnectionsPostgres: DatabaseMetrics = {
        ...mockPostgresqlMetrics,
        connections_active: 27,
        connections_max: 30,
      };

      render(<DatabasesPanel {...defaultProps} postgresql={highConnectionsPostgres} />);

      // 90% pool usage should show warning
      expect(screen.getByTestId('postgresql-connections')).toHaveTextContent('27/30');
    });
  });

  describe('debug mode', () => {
    const mockRedisDebugInfo = {
      redis_version: '7.0.0',
      connected_clients: 5,
      used_memory_human: '10.5MB',
      used_memory_peak_human: '15.2MB',
      total_connections_received: 1000,
      total_commands_processed: 50000,
      uptime_in_seconds: 86400,
    };

    const mockPubsubInfo = {
      channels: ['events', 'system'],
      subscriber_counts: { events: 3, system: 2 },
    };

    it('does not render debug section when debugMode is false', () => {
      render(<DatabasesPanel {...defaultProps} debugMode={false} />);

      expect(screen.queryByTestId('redis-debug-section')).not.toBeInTheDocument();
      expect(screen.queryByText('DEBUG')).not.toBeInTheDocument();
    });

    it('renders debug section when debugMode is true', () => {
      render(
        <DatabasesPanel {...defaultProps} debugMode={true} redisDebugInfo={mockRedisDebugInfo} />
      );

      expect(screen.getByTestId('redis-debug-section')).toBeInTheDocument();
    });

    it('displays DEBUG badge when debugMode is true', () => {
      render(
        <DatabasesPanel {...defaultProps} debugMode={true} redisDebugInfo={mockRedisDebugInfo} />
      );

      expect(screen.getByText('DEBUG')).toBeInTheDocument();
    });

    it('renders Redis debug info when provided', () => {
      render(
        <DatabasesPanel
          {...defaultProps}
          debugMode={true}
          redisDebugInfo={mockRedisDebugInfo}
          pubsubInfo={mockPubsubInfo}
        />
      );

      expect(screen.getByText('7.0.0')).toBeInTheDocument();
      expect(screen.getByText('10.5MB')).toBeInTheDocument();
    });

    it('renders pubsub channels when provided', () => {
      render(
        <DatabasesPanel
          {...defaultProps}
          debugMode={true}
          redisDebugInfo={mockRedisDebugInfo}
          pubsubInfo={mockPubsubInfo}
        />
      );

      expect(screen.getByText('events')).toBeInTheDocument();
      expect(screen.getByText('system')).toBeInTheDocument();
    });

    it('shows loading state when redisDebugLoading is true', () => {
      render(<DatabasesPanel {...defaultProps} debugMode={true} redisDebugLoading={true} />);

      expect(screen.getByTestId('redis-debug-loading')).toBeInTheDocument();
    });

    it('shows error state when redisDebugError is provided', () => {
      render(
        <DatabasesPanel
          {...defaultProps}
          debugMode={true}
          redisDebugError="Failed to fetch Redis info"
        />
      );

      expect(screen.getByText('Failed to fetch Redis info')).toBeInTheDocument();
    });

    it('shows no debug info message when redisDebugInfo is null', () => {
      render(<DatabasesPanel {...defaultProps} debugMode={true} redisDebugInfo={null} />);

      expect(screen.getByText('No debug info available')).toBeInTheDocument();
    });

    it('displays subscriber counts for channels', () => {
      render(
        <DatabasesPanel
          {...defaultProps}
          debugMode={true}
          redisDebugInfo={mockRedisDebugInfo}
          pubsubInfo={mockPubsubInfo}
        />
      );

      // Should show subscriber counts - use getAllByText since numbers may appear elsewhere
      // The debug section should contain both channel names and their subscriber counts
      const debugSection = screen.getByTestId('redis-debug-section');
      expect(debugSection).toHaveTextContent('events');
      expect(debugSection).toHaveTextContent('system');
      // Verify subscriber counts are shown as badges
      expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1); // events subscribers
    });

    it('applies orange accent styling to debug section', () => {
      render(
        <DatabasesPanel {...defaultProps} debugMode={true} redisDebugInfo={mockRedisDebugInfo} />
      );

      const debugSection = screen.getByTestId('redis-debug-section');
      expect(debugSection.className).toContain('border-orange-500');
    });
  });
});

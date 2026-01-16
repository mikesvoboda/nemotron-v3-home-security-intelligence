import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import InfrastructureStatusGrid, {
  type InfrastructureStatusGridProps,
  type InfrastructureData,
  type PostgreSQLDetails,
  type RedisDetails,
  type ContainerDetails,
  type HostDetails,
  type CircuitDetails,
} from './InfrastructureStatusGrid';

describe('InfrastructureStatusGrid', () => {
  // Mock PostgreSQL data
  const mockPostgresql: PostgreSQLDetails = {
    status: 'healthy',
    latency_ms: 12,
    pool_active: 8,
    pool_max: 20,
    active_queries: 2,
    db_size_gb: 1.2,
  };

  // Mock Redis data
  const mockRedis: RedisDetails = {
    status: 'healthy',
    ops_per_sec: 1200,
    memory_mb: 128,
    connected_clients: 5,
    hit_rate: 95.5,
  };

  // Mock Containers data
  const mockContainers: ContainerDetails = {
    status: 'healthy',
    running: 5,
    total: 5,
    containers: [
      { name: 'backend', status: 'running', cpu_percent: 15, memory_mb: 256, restart_count: 0 },
      { name: 'frontend', status: 'running', cpu_percent: 5, memory_mb: 128, restart_count: 0 },
      { name: 'postgres', status: 'running', cpu_percent: 10, memory_mb: 512, restart_count: 1 },
      { name: 'redis', status: 'running', cpu_percent: 3, memory_mb: 64, restart_count: 0 },
      {
        name: 'ai-detector',
        status: 'running',
        cpu_percent: 45,
        memory_mb: 2048,
        restart_count: 0,
      },
    ],
  };

  // Mock Host data
  const mockHost: HostDetails = {
    status: 'healthy',
    cpu_percent: 12,
    memory_used_gb: 8,
    memory_total_gb: 32,
    disk_used_gb: 120,
    disk_total_gb: 500,
  };

  // Mock Circuit Breakers data
  const mockCircuits: CircuitDetails = {
    status: 'healthy',
    healthy: 3,
    total: 3,
    breakers: [
      { name: 'rtdetr', state: 'closed', failure_count: 0 },
      { name: 'nemotron', state: 'closed', failure_count: 0 },
      { name: 'enrichment', state: 'closed', failure_count: 0 },
    ],
  };

  const mockInfrastructureData: InfrastructureData = {
    postgresql: mockPostgresql,
    redis: mockRedis,
    containers: mockContainers,
    host: mockHost,
    circuits: mockCircuits,
  };

  const defaultProps: InfrastructureStatusGridProps = {
    data: mockInfrastructureData,
    loading: false,
    error: null,
    onCardClick: vi.fn(),
    expandedCard: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the component with all 5 status cards', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infrastructure-status-grid')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-postgresql')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-redis')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-containers')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-host')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-circuits')).toBeInTheDocument();
    });

    it('displays correct title for each card', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
      expect(screen.getByText('Redis')).toBeInTheDocument();
      expect(screen.getByText('Containers')).toBeInTheDocument();
      expect(screen.getByText('Host')).toBeInTheDocument();
      expect(screen.getByText('Circuits')).toBeInTheDocument();
    });

    it('displays healthy status icons for all healthy components', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      // All components are healthy - should have check icons
      const healthyIcons = screen.getAllByTestId(/infra-status-icon-/);
      expect(healthyIcons).toHaveLength(5);
    });
  });

  describe('status indicators', () => {
    it('displays key metric for PostgreSQL (latency)', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-metric-postgresql')).toHaveTextContent('12ms');
    });

    it('displays key metric for Redis (ops/sec)', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-metric-redis')).toHaveTextContent('1.2k/s');
    });

    it('displays key metric for Containers (count)', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-metric-containers')).toHaveTextContent('5/5');
    });

    it('displays key metric for Host (CPU %)', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-metric-host')).toHaveTextContent('CPU 12%');
    });

    it('displays key metric for Circuits (count)', () => {
      render(<InfrastructureStatusGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-metric-circuits')).toHaveTextContent('3/3');
    });
  });

  describe('degraded/unhealthy status', () => {
    it('shows warning styling for degraded PostgreSQL', () => {
      const degradedData: InfrastructureData = {
        ...mockInfrastructureData,
        postgresql: { ...mockPostgresql, status: 'degraded' },
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={degradedData} />);

      const card = screen.getByTestId('infra-card-postgresql');
      expect(card).toHaveClass('border-yellow-500');
    });

    it('shows error styling for unhealthy Redis', () => {
      const unhealthyData: InfrastructureData = {
        ...mockInfrastructureData,
        redis: { ...mockRedis, status: 'unhealthy' },
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={unhealthyData} />);

      const card = screen.getByTestId('infra-card-redis');
      expect(card).toHaveClass('border-red-500');
    });

    it('shows error styling when containers are not all running', () => {
      const partialData: InfrastructureData = {
        ...mockInfrastructureData,
        containers: { ...mockContainers, status: 'degraded', running: 4, total: 5 },
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={partialData} />);

      const card = screen.getByTestId('infra-card-containers');
      expect(card).toHaveClass('border-yellow-500');
    });
  });

  describe('accordion behavior', () => {
    it('expands details when card is clicked', async () => {
      const user = userEvent.setup();
      const onCardClick = vi.fn();

      render(<InfrastructureStatusGrid {...defaultProps} onCardClick={onCardClick} />);

      const postgresCard = screen.getByTestId('infra-card-postgresql');
      await user.click(postgresCard);

      expect(onCardClick).toHaveBeenCalledWith('postgresql');
    });

    it('shows PostgreSQL details when expanded', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="postgresql" />);

      expect(screen.getByTestId('infra-details-postgresql')).toBeInTheDocument();
      expect(screen.getByText(/Pool usage:/i)).toBeInTheDocument();
      expect(screen.getByText(/8\/20 active/)).toBeInTheDocument();
      expect(screen.getByText(/Query latency:/i)).toBeInTheDocument();
      expect(screen.getByText(/Active queries:/i)).toBeInTheDocument();
      expect(screen.getByText(/DB size:/i)).toBeInTheDocument();
    });

    it('shows Redis details when expanded', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="redis" />);

      expect(screen.getByTestId('infra-details-redis')).toBeInTheDocument();
      expect(screen.getByText(/Memory usage:/i)).toBeInTheDocument();
      expect(screen.getByText(/128 MB/)).toBeInTheDocument();
      expect(screen.getByText(/Ops\/sec:/i)).toBeInTheDocument();
      expect(screen.getByText(/Connected clients:/i)).toBeInTheDocument();
      expect(screen.getByText(/Hit rate:/i)).toBeInTheDocument();
    });

    it('shows Containers list when expanded', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="containers" />);

      expect(screen.getByTestId('infra-details-containers')).toBeInTheDocument();
      expect(screen.getByText('backend')).toBeInTheDocument();
      expect(screen.getByText('frontend')).toBeInTheDocument();
      expect(screen.getByText('postgres')).toBeInTheDocument();
      expect(screen.getByText('redis')).toBeInTheDocument();
      expect(screen.getByText('ai-detector')).toBeInTheDocument();
    });

    it('shows Host metrics with progress bars when expanded', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="host" />);

      expect(screen.getByTestId('infra-details-host')).toBeInTheDocument();
      expect(screen.getByTestId('host-cpu-bar')).toBeInTheDocument();
      expect(screen.getByTestId('host-memory-bar')).toBeInTheDocument();
      expect(screen.getByTestId('host-disk-bar')).toBeInTheDocument();
    });

    it('shows Circuit breaker states when expanded', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="circuits" />);

      expect(screen.getByTestId('infra-details-circuits')).toBeInTheDocument();
      expect(screen.getByText('rtdetr')).toBeInTheDocument();
      expect(screen.getByText('nemotron')).toBeInTheDocument();
      expect(screen.getByText('enrichment')).toBeInTheDocument();
    });

    it('collapses current card when clicking the same card again', async () => {
      const user = userEvent.setup();
      const onCardClick = vi.fn();

      render(
        <InfrastructureStatusGrid
          {...defaultProps}
          expandedCard="postgresql"
          onCardClick={onCardClick}
        />
      );

      const postgresCard = screen.getByTestId('infra-card-postgresql');
      await user.click(postgresCard);

      // Should call with null to collapse
      expect(onCardClick).toHaveBeenCalledWith(null);
    });

    it('switches to new card when clicking different card', async () => {
      const user = userEvent.setup();
      const onCardClick = vi.fn();

      render(
        <InfrastructureStatusGrid
          {...defaultProps}
          expandedCard="postgresql"
          onCardClick={onCardClick}
        />
      );

      const redisCard = screen.getByTestId('infra-card-redis');
      await user.click(redisCard);

      expect(onCardClick).toHaveBeenCalledWith('redis');
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when loading', () => {
      render(<InfrastructureStatusGrid {...defaultProps} loading={true} />);

      expect(screen.getByTestId('infrastructure-grid-loading')).toBeInTheDocument();
    });

    it('does not render cards when loading', () => {
      render(<InfrastructureStatusGrid {...defaultProps} loading={true} />);

      expect(screen.queryByTestId('infra-card-postgresql')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when error prop is set', () => {
      render(
        <InfrastructureStatusGrid {...defaultProps} error="Failed to fetch infrastructure data" />
      );

      expect(screen.getByTestId('infrastructure-grid-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch infrastructure data/)).toBeInTheDocument();
    });

    it('does not render cards when error', () => {
      render(
        <InfrastructureStatusGrid {...defaultProps} error="Failed to fetch infrastructure data" />
      );

      expect(screen.queryByTestId('infra-card-postgresql')).not.toBeInTheDocument();
    });
  });

  describe('null data handling', () => {
    it('handles null PostgreSQL data gracefully', () => {
      const partialData: InfrastructureData = {
        ...mockInfrastructureData,
        postgresql: null,
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={partialData} />);

      const card = screen.getByTestId('infra-card-postgresql');
      expect(card).toBeInTheDocument();
      expect(screen.getByTestId('infra-metric-postgresql')).toHaveTextContent('--');
    });

    it('handles null Redis data gracefully', () => {
      const partialData: InfrastructureData = {
        ...mockInfrastructureData,
        redis: null,
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={partialData} />);

      const card = screen.getByTestId('infra-card-redis');
      expect(card).toBeInTheDocument();
      expect(screen.getByTestId('infra-metric-redis')).toHaveTextContent('--');
    });

    it('shows unknown status for null data', () => {
      const partialData: InfrastructureData = {
        ...mockInfrastructureData,
        host: null,
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={partialData} />);

      const card = screen.getByTestId('infra-card-host');
      expect(card).toHaveClass('border-gray-700');
    });
  });

  describe('formatting', () => {
    it('formats large ops/sec values with k suffix', () => {
      const highOpsData: InfrastructureData = {
        ...mockInfrastructureData,
        redis: { ...mockRedis, ops_per_sec: 15000 },
      };

      render(<InfrastructureStatusGrid {...defaultProps} data={highOpsData} />);

      expect(screen.getByTestId('infra-metric-redis')).toHaveTextContent('15k/s');
    });

    it('formats memory values correctly', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="host" />);

      // Memory: 8/32 GB = 25%
      expect(screen.getByText(/8\/32 GB/)).toBeInTheDocument();
    });

    it('formats disk values correctly', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="host" />);

      // Disk: 120/500 GB = 24%
      expect(screen.getByText(/120\/500 GB/)).toBeInTheDocument();
    });
  });

  describe('circuit breaker states', () => {
    it('shows open circuit breaker with error styling', () => {
      const openCircuitData: InfrastructureData = {
        ...mockInfrastructureData,
        circuits: {
          status: 'degraded',
          healthy: 2,
          total: 3,
          breakers: [
            { name: 'rtdetr', state: 'open', failure_count: 5 },
            { name: 'nemotron', state: 'closed', failure_count: 0 },
            { name: 'enrichment', state: 'closed', failure_count: 0 },
          ],
        },
      };

      render(
        <InfrastructureStatusGrid
          {...defaultProps}
          data={openCircuitData}
          expandedCard="circuits"
        />
      );

      const rtdetrRow = screen.getByTestId('circuit-row-rtdetr');
      expect(rtdetrRow).toHaveClass('text-red-400');
    });

    it('shows half-open circuit breaker with warning styling', () => {
      const halfOpenData: InfrastructureData = {
        ...mockInfrastructureData,
        circuits: {
          status: 'degraded',
          healthy: 2,
          total: 3,
          breakers: [
            { name: 'rtdetr', state: 'half_open', failure_count: 3 },
            { name: 'nemotron', state: 'closed', failure_count: 0 },
            { name: 'enrichment', state: 'closed', failure_count: 0 },
          ],
        },
      };

      render(
        <InfrastructureStatusGrid {...defaultProps} data={halfOpenData} expandedCard="circuits" />
      );

      const rtdetrRow = screen.getByTestId('circuit-row-rtdetr');
      expect(rtdetrRow).toHaveClass('text-yellow-400');
    });
  });

  describe('container restart counts', () => {
    it('shows restart count in container details', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="containers" />);

      // postgres has restart_count: 1
      const postgresRow = screen.getByTestId('container-row-postgres');
      expect(postgresRow).toHaveTextContent('1 restart');
    });

    it('highlights containers with high restart counts', () => {
      const highRestartData: InfrastructureData = {
        ...mockInfrastructureData,
        containers: {
          ...mockContainers,
          containers: [
            ...mockContainers.containers.slice(0, 2),
            {
              name: 'postgres',
              status: 'running',
              cpu_percent: 10,
              memory_mb: 512,
              restart_count: 5,
            },
            ...mockContainers.containers.slice(3),
          ],
        },
      };

      render(
        <InfrastructureStatusGrid
          {...defaultProps}
          data={highRestartData}
          expandedCard="containers"
        />
      );

      const postgresRow = screen.getByTestId('container-row-postgres');
      expect(postgresRow).toHaveClass('text-yellow-400');
    });
  });

  describe('accessibility', () => {
    it('cards are keyboard accessible', async () => {
      const user = userEvent.setup();
      const onCardClick = vi.fn();

      render(<InfrastructureStatusGrid {...defaultProps} onCardClick={onCardClick} />);

      const postgresCard = screen.getByTestId('infra-card-postgresql');
      postgresCard.focus();
      await user.keyboard('{Enter}');

      expect(onCardClick).toHaveBeenCalledWith('postgresql');
    });

    it('expanded details are announced to screen readers', () => {
      render(<InfrastructureStatusGrid {...defaultProps} expandedCard="postgresql" />);

      const details = screen.getByTestId('infra-details-postgresql');
      expect(details).toHaveAttribute('role', 'region');
      expect(details).toHaveAttribute('aria-label', 'PostgreSQL details');
    });
  });
});

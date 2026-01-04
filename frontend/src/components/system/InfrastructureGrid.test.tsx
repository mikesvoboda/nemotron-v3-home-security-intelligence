import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import InfrastructureGrid from './InfrastructureGrid';

import type {
  InfraComponent,
  PostgresDetails,
  RedisDetails,
  ContainersDetails,
  HostDetails,
  CircuitsDetails,
} from './InfrastructureGrid';

describe('InfrastructureGrid', () => {
  const createComponent = (
    id: InfraComponent['id'],
    label: string,
    overrides: Partial<InfraComponent> = {}
  ): InfraComponent => ({
    id,
    label,
    status: 'healthy',
    ...overrides,
  });

  const mockPostgresDetails: PostgresDetails = {
    poolActive: 8,
    poolMax: 20,
    queryLatencyMs: 12,
    queryLatencyP95Ms: 45,
    activeQueries: 2,
    databaseSizeGb: 1.2,
    cacheHitRatio: 98.5,
    lastBackup: '2026-01-04 02:00',
  };

  const mockRedisDetails: RedisDetails = {
    memoryMb: 128,
    memoryMaxMb: 512,
    opsPerSec: 1200,
    connectedClients: 5,
    hitRate: 95.2,
    blockedClients: 0,
  };

  const mockContainersDetails: ContainersDetails = {
    containers: [
      { name: 'backend', status: 'running', cpuPercent: 5, memoryMb: 256, restarts: 0 },
      { name: 'frontend', status: 'running', cpuPercent: 2, memoryMb: 128, restarts: 0 },
      { name: 'postgres', status: 'running', cpuPercent: 3, memoryMb: 512, restarts: 0 },
      { name: 'redis', status: 'running', cpuPercent: 1, memoryMb: 64, restarts: 0 },
      { name: 'ai-detector', status: 'running', cpuPercent: 40, memoryMb: 2048, restarts: 0 },
    ],
  };

  const mockHostDetails: HostDetails = {
    cpuPercent: 12,
    ramUsedGb: 8.5,
    ramTotalGb: 32,
    diskUsedGb: 120,
    diskTotalGb: 500,
  };

  const mockCircuitsDetails: CircuitsDetails = {
    breakers: [
      { name: 'rtdetr', state: 'closed', failureCount: 0 },
      { name: 'nemotron', state: 'closed', failureCount: 0 },
      { name: 'database', state: 'closed', failureCount: 0 },
    ],
  };

  const defaultProps = {
    postgresql: createComponent('postgresql', 'PostgreSQL', { keyMetric: '12ms' }),
    redis: createComponent('redis', 'Redis', { keyMetric: '1.2k/s' }),
    containers: createComponent('containers', 'Containers', { keyMetric: '5/5' }),
    host: createComponent('host', 'Host', { keyMetric: 'CPU 12%' }),
    circuits: createComponent('circuits', 'Circuits', { keyMetric: '3/3' }),
  };

  describe('rendering', () => {
    it('renders the infrastructure grid', () => {
      render(<InfrastructureGrid {...defaultProps} />);
      expect(screen.getByTestId('infrastructure-grid')).toBeInTheDocument();
    });

    it('renders the title', () => {
      render(<InfrastructureGrid {...defaultProps} />);
      expect(screen.getByText('Infrastructure')).toBeInTheDocument();
    });

    it('renders all 5 component cards', () => {
      render(<InfrastructureGrid {...defaultProps} />);

      expect(screen.getByTestId('infra-card-postgresql')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-redis')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-containers')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-host')).toBeInTheDocument();
      expect(screen.getByTestId('infra-card-circuits')).toBeInTheDocument();
    });

    it('displays component labels', () => {
      render(<InfrastructureGrid {...defaultProps} />);

      expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
      expect(screen.getByText('Redis')).toBeInTheDocument();
      expect(screen.getByText('Containers')).toBeInTheDocument();
      expect(screen.getByText('Host')).toBeInTheDocument();
      expect(screen.getByText('Circuits')).toBeInTheDocument();
    });

    it('displays key metrics', () => {
      render(<InfrastructureGrid {...defaultProps} />);

      expect(screen.getByText('12ms')).toBeInTheDocument();
      expect(screen.getByText('1.2k/s')).toBeInTheDocument();
      expect(screen.getByText('5/5')).toBeInTheDocument();
      expect(screen.getByText('CPU 12%')).toBeInTheDocument();
      expect(screen.getByText('3/3')).toBeInTheDocument();
    });
  });

  describe('status indicators', () => {
    it('shows healthy status correctly', () => {
      render(<InfrastructureGrid {...defaultProps} />);

      const pgCard = screen.getByTestId('infra-card-postgresql');
      expect(pgCard.className).toContain('border-gray-700');
    });

    it('shows degraded status correctly', () => {
      const props = {
        ...defaultProps,
        redis: createComponent('redis', 'Redis', { status: 'degraded' }),
      };

      render(<InfrastructureGrid {...props} />);

      const redisCard = screen.getByTestId('infra-card-redis');
      expect(redisCard.className).toContain('yellow');
    });

    it('shows unhealthy status correctly', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { status: 'unhealthy' }),
      };

      render(<InfrastructureGrid {...props} />);

      const pgCard = screen.getByTestId('infra-card-postgresql');
      expect(pgCard.className).toContain('red');
    });

    it('shows warning icon when any component degraded', () => {
      const props = {
        ...defaultProps,
        redis: createComponent('redis', 'Redis', { status: 'degraded' }),
      };

      render(<InfrastructureGrid {...props} />);
      expect(screen.getByTestId('infra-warning-icon')).toBeInTheDocument();
    });

    it('shows warning icon when any component unhealthy', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { status: 'unhealthy' }),
      };

      render(<InfrastructureGrid {...props} />);
      expect(screen.getByTestId('infra-warning-icon')).toBeInTheDocument();
    });

    it('does not show warning icon when all healthy', () => {
      render(<InfrastructureGrid {...defaultProps} />);
      expect(screen.queryByTestId('infra-warning-icon')).not.toBeInTheDocument();
    });
  });

  describe('accordion behavior', () => {
    it('detail panel is not visible initially', () => {
      render(<InfrastructureGrid {...defaultProps} />);
      expect(screen.queryByTestId('infra-detail-panel')).not.toBeInTheDocument();
    });

    it('clicking card shows detail panel', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
      };

      render(<InfrastructureGrid {...props} />);

      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.getByTestId('infra-detail-panel')).toBeInTheDocument();
    });

    it('clicking same card again hides detail panel', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
      };

      render(<InfrastructureGrid {...props} />);

      // Open
      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.getByTestId('infra-detail-panel')).toBeInTheDocument();

      // Close by clicking same card
      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.queryByTestId('infra-detail-panel')).not.toBeInTheDocument();
    });

    it('clicking different card switches detail panel', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
        redis: createComponent('redis', 'Redis', { details: mockRedisDetails }),
      };

      render(<InfrastructureGrid {...props} />);

      // Open PostgreSQL
      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.getByText('PostgreSQL Details')).toBeInTheDocument();

      // Switch to Redis
      fireEvent.click(screen.getByTestId('infra-card-redis'));
      expect(screen.getByText('Redis Details')).toBeInTheDocument();
    });

    it('close button hides detail panel', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
      };

      render(<InfrastructureGrid {...props} />);

      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.getByTestId('infra-detail-panel')).toBeInTheDocument();

      fireEvent.click(screen.getByTestId('close-detail-btn'));
      expect(screen.queryByTestId('infra-detail-panel')).not.toBeInTheDocument();
    });

    it('selected card has highlight styling', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
      };

      render(<InfrastructureGrid {...props} />);

      fireEvent.click(screen.getByTestId('infra-card-postgresql'));

      const pgCard = screen.getByTestId('infra-card-postgresql');
      expect(pgCard.className).toContain('border-[#76B900]');
    });
  });

  describe('PostgreSQL detail panel', () => {
    it('displays PostgreSQL details', () => {
      const props = {
        ...defaultProps,
        postgresql: createComponent('postgresql', 'PostgreSQL', { details: mockPostgresDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-postgresql'));

      expect(screen.getByText('Connection Pool')).toBeInTheDocument();
      expect(screen.getByText('8/20 active')).toBeInTheDocument();
      expect(screen.getByText('12ms avg')).toBeInTheDocument();
      expect(screen.getByText('1.20 GB')).toBeInTheDocument();
    });
  });

  describe('Redis detail panel', () => {
    it('displays Redis details', () => {
      const props = {
        ...defaultProps,
        redis: createComponent('redis', 'Redis', { details: mockRedisDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-redis'));

      expect(screen.getByText('Memory Usage')).toBeInTheDocument();
      expect(screen.getByText('128.0 MB')).toBeInTheDocument();
      expect(screen.getByText('Operations/sec')).toBeInTheDocument();
      expect(screen.getByText('1,200')).toBeInTheDocument();
    });
  });

  describe('Containers detail panel', () => {
    it('displays container details', () => {
      const props = {
        ...defaultProps,
        containers: createComponent('containers', 'Containers', { details: mockContainersDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-containers'));

      expect(screen.getByText('backend')).toBeInTheDocument();
      expect(screen.getByText('frontend')).toBeInTheDocument();
      expect(screen.getByText('postgres')).toBeInTheDocument();
    });
  });

  describe('Host detail panel', () => {
    it('displays host details', () => {
      const props = {
        ...defaultProps,
        host: createComponent('host', 'Host', { details: mockHostDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-host'));

      expect(screen.getByText('CPU')).toBeInTheDocument();
      expect(screen.getByText('12%')).toBeInTheDocument();
      expect(screen.getByText('RAM')).toBeInTheDocument();
      expect(screen.getByText('8.5/32 GB')).toBeInTheDocument();
    });
  });

  describe('Circuits detail panel', () => {
    it('displays circuit breaker details', () => {
      const props = {
        ...defaultProps,
        circuits: createComponent('circuits', 'Circuits', { details: mockCircuitsDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-circuits'));

      expect(screen.getByText('rtdetr')).toBeInTheDocument();
      expect(screen.getByText('nemotron')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
    });

    it('shows circuit breaker states', () => {
      const props = {
        ...defaultProps,
        circuits: createComponent('circuits', 'Circuits', { details: mockCircuitsDetails }),
      };

      render(<InfrastructureGrid {...props} />);
      fireEvent.click(screen.getByTestId('infra-card-circuits'));

      // All breakers are closed
      const closedBadges = screen.getAllByText('closed');
      expect(closedBadges.length).toBe(3);
    });
  });

  describe('no details state', () => {
    it('shows no details message when details missing', () => {
      render(<InfrastructureGrid {...defaultProps} />);

      fireEvent.click(screen.getByTestId('infra-card-postgresql'));
      expect(screen.getByText('No details available')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<InfrastructureGrid {...defaultProps} className="custom-class" />);
      expect(screen.getByTestId('infrastructure-grid')).toHaveClass('custom-class');
    });
  });
});

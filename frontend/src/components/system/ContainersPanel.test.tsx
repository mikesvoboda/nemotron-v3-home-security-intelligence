import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import ContainersPanel, {
  type ContainersPanelProps,
  type ContainerMetrics,
  type ContainerHistory,
} from './ContainersPanel';

describe('ContainersPanel', () => {
  // Sample container metrics - all 6 containers
  const mockContainersAllHealthy: ContainerMetrics[] = [
    { name: 'backend', status: 'running', health: 'healthy' },
    { name: 'frontend', status: 'running', health: 'healthy' },
    { name: 'postgres', status: 'running', health: 'healthy' },
    { name: 'redis', status: 'running', health: 'healthy' },
    { name: 'ai-detector', status: 'running', health: 'healthy' },
    { name: 'ai-llm', status: 'running', health: 'healthy' },
  ];

  const mockContainersMixed: ContainerMetrics[] = [
    { name: 'backend', status: 'running', health: 'healthy' },
    { name: 'frontend', status: 'running', health: 'healthy' },
    { name: 'postgres', status: 'running', health: 'unhealthy' },
    { name: 'redis', status: 'stopped', health: 'unhealthy' },
    { name: 'ai-detector', status: 'running', health: 'healthy' },
    { name: 'ai-llm', status: 'running', health: 'healthy' },
  ];

  // Sample history data with health timeline
  const mockContainerHistory: ContainerHistory = {
    backend: [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
    frontend: [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
    postgres: [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'unhealthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
    redis: [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
    'ai-detector': [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
    'ai-llm': [
      { timestamp: '2025-01-01T12:00:00Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:05Z', health: 'healthy' },
      { timestamp: '2025-01-01T12:00:10Z', health: 'healthy' },
    ],
  };

  const defaultProps: ContainersPanelProps = {
    containers: mockContainersAllHealthy,
    history: mockContainerHistory,
  };

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      expect(screen.getByText('Containers')).toBeInTheDocument();
    });

    it('renders all 6 containers', () => {
      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
      expect(screen.getByTestId('container-frontend')).toBeInTheDocument();
      expect(screen.getByTestId('container-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('container-redis')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-detector')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-llm')).toBeInTheDocument();
    });

    it('displays container names', () => {
      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByText('backend')).toBeInTheDocument();
      expect(screen.getByText('frontend')).toBeInTheDocument();
      expect(screen.getByText('postgres')).toBeInTheDocument();
      expect(screen.getByText('redis')).toBeInTheDocument();
      expect(screen.getByText('ai-detector')).toBeInTheDocument();
      expect(screen.getByText('ai-llm')).toBeInTheDocument();
    });
  });

  describe('health status display', () => {
    it('displays healthy status badge for healthy containers', () => {
      render(<ContainersPanel {...defaultProps} />);

      const backendStatus = screen.getByTestId('container-status-backend');
      expect(backendStatus).toHaveTextContent('Healthy');
    });

    it('displays unhealthy status badge for unhealthy containers', () => {
      render(<ContainersPanel containers={mockContainersMixed} history={mockContainerHistory} />);

      const postgresStatus = screen.getByTestId('container-status-postgres');
      expect(postgresStatus).toHaveTextContent('Unhealthy');
    });

    it('displays stopped status badge for stopped containers', () => {
      render(<ContainersPanel containers={mockContainersMixed} history={mockContainerHistory} />);

      const redisStatus = screen.getByTestId('container-status-redis');
      expect(redisStatus).toHaveTextContent('Unhealthy');
    });
  });

  describe('summary statistics', () => {
    it('displays correct healthy count when all healthy', () => {
      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByTestId('containers-summary')).toHaveTextContent('6/6 Healthy');
    });

    it('displays correct healthy count when some unhealthy', () => {
      render(<ContainersPanel containers={mockContainersMixed} history={mockContainerHistory} />);

      expect(screen.getByTestId('containers-summary')).toHaveTextContent('4/6 Healthy');
    });
  });

  describe('health timeline (Tracker)', () => {
    it('renders tracker for each container', () => {
      render(<ContainersPanel {...defaultProps} />);

      expect(screen.getByTestId('tracker-backend')).toBeInTheDocument();
      expect(screen.getByTestId('tracker-frontend')).toBeInTheDocument();
      expect(screen.getByTestId('tracker-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('tracker-redis')).toBeInTheDocument();
      expect(screen.getByTestId('tracker-ai-detector')).toBeInTheDocument();
      expect(screen.getByTestId('tracker-ai-llm')).toBeInTheDocument();
    });
  });

  describe('empty/null handling', () => {
    it('handles empty containers array gracefully', () => {
      render(<ContainersPanel containers={[]} history={mockContainerHistory} />);

      expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      expect(screen.getByText('No containers available')).toBeInTheDocument();
    });

    it('handles containers with missing history gracefully', () => {
      const emptyHistory: ContainerHistory = {};

      render(<ContainersPanel containers={mockContainersAllHealthy} history={emptyHistory} />);

      expect(screen.getByTestId('containers-panel')).toBeInTheDocument();
      // Should still render containers even without history
      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
    });
  });

  describe('container ordering', () => {
    it('renders containers in the specified order', () => {
      render(<ContainersPanel {...defaultProps} />);

      // Verify 6 container cards are rendered
      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
      expect(screen.getByTestId('container-frontend')).toBeInTheDocument();
      expect(screen.getByTestId('container-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('container-redis')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-detector')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-llm')).toBeInTheDocument();
    });
  });

  describe('health state colors', () => {
    it('shows green indicator for healthy containers', () => {
      render(<ContainersPanel {...defaultProps} />);

      // Backend should be healthy
      const backendContainer = screen.getByTestId('container-backend');
      expect(backendContainer).toBeInTheDocument();
    });

    it('shows red indicator for unhealthy containers', () => {
      render(<ContainersPanel containers={mockContainersMixed} history={mockContainerHistory} />);

      // Postgres should be unhealthy
      const postgresContainer = screen.getByTestId('container-postgres');
      expect(postgresContainer).toBeInTheDocument();
    });
  });

  describe('status variations', () => {
    it('handles running status', () => {
      render(<ContainersPanel {...defaultProps} />);

      // All containers in defaultProps are running
      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
    });

    it('handles stopped status', () => {
      const stoppedContainers: ContainerMetrics[] = [
        { name: 'backend', status: 'stopped', health: 'unhealthy' },
        { name: 'frontend', status: 'running', health: 'healthy' },
        { name: 'postgres', status: 'running', health: 'healthy' },
        { name: 'redis', status: 'running', health: 'healthy' },
        { name: 'ai-detector', status: 'running', health: 'healthy' },
        { name: 'ai-llm', status: 'running', health: 'healthy' },
      ];

      render(<ContainersPanel containers={stoppedContainers} history={mockContainerHistory} />);

      const backendStatus = screen.getByTestId('container-status-backend');
      expect(backendStatus).toHaveTextContent('Unhealthy');
    });

    it('handles unknown health status gracefully', () => {
      const unknownContainers: ContainerMetrics[] = [
        { name: 'backend', status: 'running', health: 'unknown' },
        { name: 'frontend', status: 'running', health: 'healthy' },
        { name: 'postgres', status: 'running', health: 'healthy' },
        { name: 'redis', status: 'running', health: 'healthy' },
        { name: 'ai-detector', status: 'running', health: 'healthy' },
        { name: 'ai-llm', status: 'running', health: 'healthy' },
      ];

      render(<ContainersPanel containers={unknownContainers} history={mockContainerHistory} />);

      const backendStatus = screen.getByTestId('container-status-backend');
      expect(backendStatus).toHaveTextContent('Unknown');
    });
  });

  describe('partial data scenarios', () => {
    it('handles subset of containers', () => {
      const partialContainers: ContainerMetrics[] = [
        { name: 'backend', status: 'running', health: 'healthy' },
        { name: 'frontend', status: 'running', health: 'healthy' },
      ];

      render(<ContainersPanel containers={partialContainers} history={mockContainerHistory} />);

      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
      expect(screen.getByTestId('container-frontend')).toBeInTheDocument();
      expect(screen.queryByTestId('container-postgres')).not.toBeInTheDocument();
    });
  });
});

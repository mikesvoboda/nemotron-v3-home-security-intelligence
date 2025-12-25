import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Header from './Header';
import * as useSystemStatusModule from '../../hooks/useSystemStatus';

describe('Header', () => {
  beforeEach(() => {
    // Mock useSystemStatus to return null status (disconnected state)
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: null,
      isConnected: false,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<Header />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('displays the NVIDIA SECURITY title', () => {
    render(<Header />);
    expect(screen.getByText('NVIDIA SECURITY')).toBeInTheDocument();
  });

  it('displays the POWERED BY NEMOTRON subtitle', () => {
    render(<Header />);
    expect(screen.getByText('POWERED BY NEMOTRON')).toBeInTheDocument();
  });

  it('renders the Activity icon', () => {
    const { container } = render(<Header />);
    // Check for the icon container with NVIDIA green background
    const iconContainer = container.querySelector('.bg-\\[\\#76B900\\]');
    expect(iconContainer).toBeInTheDocument();
  });

  it('displays Connecting status when disconnected', () => {
    render(<Header />);
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });

  it('displays System Online status when connected and healthy', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45,
        gpu_temperature: 65,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('System Online')).toBeInTheDocument();
  });

  it('displays GPU stats placeholder when no data', () => {
    render(<Header />);
    expect(screen.getByText('GPU:')).toBeInTheDocument();
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('has correct header styling classes', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('h-16', 'bg-[#1A1A1A]', 'border-b', 'border-gray-800');
  });

  it('renders title with correct styling', () => {
    render(<Header />);
    const title = screen.getByText('NVIDIA SECURITY');
    expect(title).toHaveClass('text-lg', 'font-bold', 'text-white', 'tracking-wide');
  });

  it('renders subtitle with NVIDIA green color', () => {
    render(<Header />);
    const subtitle = screen.getByText('POWERED BY NEMOTRON');
    expect(subtitle).toHaveClass('text-xs', 'text-[#76B900]', 'font-medium', 'tracking-wider');
  });

  it('has proper flex layout structure', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('flex', 'items-center', 'justify-between');
  });

  it('renders GPU stats with correct styling', () => {
    const { container } = render(<Header />);
    const gpuStats = container.querySelector('.bg-gray-800.rounded-lg');
    expect(gpuStats).toBeInTheDocument();
  });

  it('GPU value has NVIDIA green color', () => {
    render(<Header />);
    const gpuValue = screen.getByText('--');
    expect(gpuValue).toHaveClass('text-[#76B900]');
  });

  it('contains accessibility attributes for header element', () => {
    render(<Header />);
    const header = screen.getByRole('banner');
    expect(header.tagName).toBe('HEADER');
  });

  it('displays GPU utilization when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 75.5,
        gpu_temperature: null,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('76%')).toBeInTheDocument();
  });

  it('displays GPU temperature when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: null,
        gpu_temperature: 65.7,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('66°C')).toBeInTheDocument();
  });

  it('displays both GPU utilization and temperature when available', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'healthy',
        gpu_utilization: 45.2,
        gpu_temperature: 62.8,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 3,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('45% | 63°C')).toBeInTheDocument();
  });

  it('displays System Degraded status when system is degraded', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'degraded',
        gpu_utilization: 85,
        gpu_temperature: 75,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 1,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('System Degraded')).toBeInTheDocument();
  });

  it('displays System Offline status when system is unhealthy', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'unhealthy',
        gpu_utilization: 100,
        gpu_temperature: 90,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 0,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    render(<Header />);
    expect(screen.getByText('System Offline')).toBeInTheDocument();
  });

  it('shows yellow status dot for degraded system', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'degraded',
        gpu_utilization: 85,
        gpu_temperature: 75,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 1,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    const { container } = render(<Header />);
    const statusDot = container.querySelector('.bg-yellow-500');
    expect(statusDot).toBeInTheDocument();
  });

  it('shows red status dot for unhealthy system', () => {
    vi.spyOn(useSystemStatusModule, 'useSystemStatus').mockReturnValue({
      status: {
        health: 'unhealthy',
        gpu_utilization: 100,
        gpu_temperature: 90,
        gpu_memory_used: 8192,
        gpu_memory_total: 24576,
        active_cameras: 0,
        last_update: '2025-12-23T10:00:00Z',
      },
      isConnected: true,
    });

    const { container } = render(<Header />);
    const statusDot = container.querySelector('.bg-red-500');
    expect(statusDot).toBeInTheDocument();
  });
});

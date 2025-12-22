import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Header from './Header';

describe('Header', () => {
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

  it('displays System Online status indicator', () => {
    render(<Header />);
    expect(screen.getByText('System Online')).toBeInTheDocument();
  });

  it('has a pulsing green status dot', () => {
    const { container } = render(<Header />);
    const statusDot = container.querySelector('.bg-green-500.rounded-full.animate-pulse');
    expect(statusDot).toBeInTheDocument();
  });

  it('displays GPU stats placeholder', () => {
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
});

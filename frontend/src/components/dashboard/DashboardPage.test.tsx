import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DashboardPage from './DashboardPage';

describe('DashboardPage', () => {
  it('renders without crashing', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('displays the Dashboard heading', () => {
    render(<DashboardPage />);
    const heading = screen.getByRole('heading', { name: /dashboard/i });
    expect(heading).toBeInTheDocument();
  });

  it('heading has correct styling classes', () => {
    render(<DashboardPage />);
    const heading = screen.getByRole('heading', { name: /dashboard/i });
    expect(heading).toHaveClass('text-3xl', 'font-bold', 'text-white');
  });

  it('has correct container styling', () => {
    const { container } = render(<DashboardPage />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('p-8');
  });

  it('heading is an h2 element', () => {
    render(<DashboardPage />);
    const heading = screen.getByRole('heading', { name: /dashboard/i });
    expect(heading.tagName).toBe('H2');
  });

  it('renders with proper semantic HTML structure', () => {
    const { container } = render(<DashboardPage />);
    expect(container.querySelector('div > h2')).toBeInTheDocument();
  });

  it('matches expected text content exactly', () => {
    render(<DashboardPage />);
    expect(screen.getByText('Dashboard')).toHaveTextContent('Dashboard');
  });
});

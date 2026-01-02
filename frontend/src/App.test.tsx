import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import App from './App';
import { checkAccessibility } from './test-utils';


// Mock the Layout component
vi.mock('./components/layout/Layout', () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-layout">
      <div data-testid="layout-children">{children}</div>
    </div>
  ),
}));

// Mock the DashboardPage component
vi.mock('./components/dashboard/DashboardPage', () => ({
  default: () => <div data-testid="mock-dashboard">Dashboard Page Content</div>,
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByTestId('mock-layout')).toBeInTheDocument();
  });

  it('renders Layout component', () => {
    render(<App />);
    expect(screen.getByTestId('mock-layout')).toBeInTheDocument();
  });

  it('renders DashboardPage component inside Layout', () => {
    render(<App />);
    expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument();
    expect(screen.getByText('Dashboard Page Content')).toBeInTheDocument();
  });

  it('DashboardPage is a child of Layout', () => {
    render(<App />);
    const layoutChildren = screen.getByTestId('layout-children');
    const dashboard = screen.getByTestId('mock-dashboard');
    expect(layoutChildren).toContainElement(dashboard);
  });

  it('has correct component hierarchy', () => {
    const { container } = render(<App />);
    const layout = screen.getByTestId('mock-layout');
    const dashboard = screen.getByTestId('mock-dashboard');

    expect(container).toContainElement(layout);
    expect(layout).toContainElement(dashboard);
  });

  describe('accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<App />);
      await checkAccessibility(container);
    });
  });
});

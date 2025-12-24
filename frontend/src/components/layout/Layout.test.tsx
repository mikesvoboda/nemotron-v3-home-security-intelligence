import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Layout from './Layout';

// Mock the child components
vi.mock('./Header', () => ({
  default: () => <div data-testid="mock-header">Header</div>,
}));

vi.mock('./Sidebar', () => ({
  default: () => <div data-testid="mock-sidebar">Sidebar</div>,
}));

describe('Layout', () => {
  it('renders without crashing', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
  });

  it('renders Header component', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
    expect(screen.getByText('Header')).toBeInTheDocument();
  });

  it('renders Sidebar component', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-sidebar')).toBeInTheDocument();
  });

  it('renders children content in main area', () => {
    render(
      <Layout>
        <div data-testid="test-child">Test Child Content</div>
      </Layout>
    );
    expect(screen.getByTestId('test-child')).toBeInTheDocument();
    expect(screen.getByText('Test Child Content')).toBeInTheDocument();
  });

  it('has correct layout structure with flex classes', () => {
    const { container } = render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    const layoutDiv = container.firstChild as HTMLElement;
    expect(layoutDiv).toHaveClass('min-h-screen', 'bg-[#0E0E0E]', 'flex', 'flex-col');
  });

  it('main element has overflow-auto class for scrolling', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    const main = screen.getByRole('main');
    expect(main).toHaveClass('flex-1', 'overflow-auto');
  });

  it('renders multiple children correctly', () => {
    render(
      <Layout>
        <div data-testid="child-1">Child 1</div>
        <div data-testid="child-2">Child 2</div>
        <div data-testid="child-3">Child 3</div>
      </Layout>
    );
    expect(screen.getByTestId('child-1')).toBeInTheDocument();
    expect(screen.getByTestId('child-2')).toBeInTheDocument();
    expect(screen.getByTestId('child-3')).toBeInTheDocument();
  });
});

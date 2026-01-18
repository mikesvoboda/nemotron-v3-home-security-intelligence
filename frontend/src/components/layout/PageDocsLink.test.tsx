import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import { PageDocsLink } from './PageDocsLink';

const renderWithRouter = (initialRoute: string) => {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <PageDocsLink />
    </MemoryRouter>
  );
};

describe('PageDocsLink', () => {
  it('renders dashboard documentation link on root route', () => {
    renderWithRouter('/');

    const link = screen.getByRole('link', { name: /dashboard documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/dashboard.md'));
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders alerts documentation link on alerts route', () => {
    renderWithRouter('/alerts');

    const link = screen.getByRole('link', { name: /alerts documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/alerts.md'));
  });

  it('renders jobs documentation link on jobs route', () => {
    renderWithRouter('/jobs');

    const link = screen.getByRole('link', { name: /jobs documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/jobs.md'));
  });

  it('renders nothing for unmapped routes', () => {
    renderWithRouter('/dev-tools');

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('includes BookOpen icon', () => {
    renderWithRouter('/');

    // The link should contain an svg (the BookOpen icon)
    const link = screen.getByRole('link');
    const svg = link.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('has NVIDIA green styling', () => {
    renderWithRouter('/');

    const link = screen.getByRole('link');
    expect(link).toHaveClass('text-[#76B900]');
  });

  it('shows short text on mobile (via responsive class)', () => {
    renderWithRouter('/');

    // Check that "Docs" text exists for mobile
    expect(screen.getByText('Docs')).toBeInTheDocument();
    // Check that full text exists for desktop
    expect(screen.getByText(/dashboard documentation/i)).toBeInTheDocument();
  });
});

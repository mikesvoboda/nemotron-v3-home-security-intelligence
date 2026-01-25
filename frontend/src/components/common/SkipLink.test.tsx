import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { SkipLink, SkipLinkGroup, type SkipTarget } from './SkipLink';

describe('SkipLink', () => {
  describe('rendering', () => {
    it('renders with default props', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toBeInTheDocument();
      expect(skipLink).toHaveTextContent('Skip to main content');
      expect(skipLink).toHaveAttribute('href', '#main-content');
    });

    it('renders with custom target id', () => {
      render(<SkipLink targetId="content-area" />);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveAttribute('href', '#content-area');
    });

    it('renders with custom link text', () => {
      render(<SkipLink>Skip navigation</SkipLink>);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveTextContent('Skip navigation');
    });

    it('renders with both custom props', () => {
      render(<SkipLink targetId="custom-main">Go to content</SkipLink>);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveAttribute('href', '#custom-main');
      expect(skipLink).toHaveTextContent('Go to content');
    });
  });

  describe('accessibility - visual hiding', () => {
    it('is visually hidden by default (has sr-only class)', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveClass('sr-only');
    });

    it('has focus styles to become visible when focused', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      // Verify focus classes exist that will override sr-only
      expect(skipLink).toHaveClass('focus:not-sr-only');
      expect(skipLink).toHaveClass('focus:fixed');
      expect(skipLink).toHaveClass('focus:z-50');
    });

    it('has high contrast styling classes when focused', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      // Check for NVIDIA green background and black text (high contrast)
      expect(skipLink).toHaveClass('focus:bg-[#76B900]');
      expect(skipLink).toHaveClass('focus:text-black');
      expect(skipLink).toHaveClass('focus:font-medium');
    });

    it('has focus ring for keyboard navigation visibility', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveClass('focus:ring-2');
      expect(skipLink).toHaveClass('focus:ring-[#76B900]');
      expect(skipLink).toHaveClass('focus:outline-none');
    });
  });

  describe('keyboard navigation', () => {
    it('is focusable', () => {
      render(<SkipLink />);
      const skipLink = screen.getByTestId('skip-link');
      skipLink.focus();
      expect(document.activeElement).toBe(skipLink);
    });

    it('links to correct target for skip navigation', () => {
      render(
        <>
          <SkipLink />
          <main id="main-content" tabIndex={-1}>
            Main content
          </main>
        </>
      );
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink.getAttribute('href')).toBe('#main-content');
    });
  });

  describe('integration with main content', () => {
    it('works with main content area that has correct id and tabIndex', () => {
      render(
        <>
          <SkipLink />
          <main id="main-content" tabIndex={-1} data-testid="main-content">
            <p>Page content goes here</p>
          </main>
        </>
      );

      const skipLink = screen.getByTestId('skip-link');
      const mainContent = screen.getByTestId('main-content');

      // Skip link targets main content
      expect(skipLink).toHaveAttribute('href', '#main-content');
      // Main content has correct id
      expect(mainContent).toHaveAttribute('id', 'main-content');
      // Main content is programmatically focusable
      expect(mainContent).toHaveAttribute('tabIndex', '-1');
    });

    it('skip link can receive focus before main content', () => {
      render(
        <>
          <SkipLink />
          <button data-testid="nav-button">Navigation</button>
          <main id="main-content" tabIndex={-1} data-testid="main-content">
            Content
          </main>
        </>
      );

      const skipLink = screen.getByTestId('skip-link');
      skipLink.focus();
      expect(document.activeElement).toBe(skipLink);
    });

    it('maintains accessibility role as link', () => {
      render(<SkipLink />);
      const skipLink = screen.getByRole('link', { name: 'Skip to main content' });
      expect(skipLink).toBeInTheDocument();
    });
  });
});

describe('SkipLinkGroup', () => {
  const defaultTargets: SkipTarget[] = [
    { id: 'main-navigation', label: 'Skip to navigation' },
    { id: 'sidebar-filters', label: 'Skip to filters' },
    { id: 'main-content', label: 'Skip to main content' },
  ];

  describe('rendering', () => {
    it('renders multiple skip links', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      const links = screen.getAllByRole('link');
      expect(links).toHaveLength(3);
    });

    it('renders each target with correct href', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      expect(screen.getByRole('link', { name: 'Skip to navigation' })).toHaveAttribute(
        'href',
        '#main-navigation'
      );
      expect(screen.getByRole('link', { name: 'Skip to filters' })).toHaveAttribute(
        'href',
        '#sidebar-filters'
      );
      expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
        'href',
        '#main-content'
      );
    });

    it('renders with testid attribute', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      const container = screen.getByTestId('skip-link-group');
      expect(container).toBeInTheDocument();
    });

    it('renders nothing when targets array is empty', () => {
      render(<SkipLinkGroup targets={[]} />);

      expect(screen.queryByTestId('skip-link-group')).not.toBeInTheDocument();
    });
  });

  describe('accessibility - visual hiding', () => {
    it('group container is visually hidden by default', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      const container = screen.getByTestId('skip-link-group');
      expect(container).toHaveClass('sr-only');
    });

    it('becomes visible on focus-within', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      const container = screen.getByTestId('skip-link-group');
      expect(container).toHaveClass('focus-within:not-sr-only');
    });

    it('each link has proper focus styling', () => {
      render(<SkipLinkGroup targets={defaultTargets} />);

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        expect(link).toHaveClass('focus:bg-[#76B900]');
        expect(link).toHaveClass('focus:text-black');
      });
    });
  });

  describe('keyboard navigation', () => {
    it('allows tab navigation between skip links', async () => {
      const user = userEvent.setup();
      render(<SkipLinkGroup targets={defaultTargets} />);

      const links = screen.getAllByRole('link');

      // Focus first link
      links[0].focus();
      expect(document.activeElement).toBe(links[0]);

      // Tab to next
      await user.tab();
      expect(document.activeElement).toBe(links[1]);

      // Tab to next
      await user.tab();
      expect(document.activeElement).toBe(links[2]);
    });
  });

  describe('integration with layout landmarks', () => {
    it('works with actual layout landmark IDs', () => {
      const layoutTargets: SkipTarget[] = [
        { id: 'main-navigation', label: 'Skip to navigation' },
        { id: 'sidebar-filters', label: 'Skip to sidebar' },
        { id: 'main-content', label: 'Skip to main content' },
      ];

      render(
        <>
          <SkipLinkGroup targets={layoutTargets} />
          <nav id="main-navigation" tabIndex={-1}>
            Navigation
          </nav>
          <aside id="sidebar-filters" tabIndex={-1}>
            Sidebar
          </aside>
          <main id="main-content" tabIndex={-1}>
            Content
          </main>
        </>
      );

      // Verify links target the correct elements
      const navLink = screen.getByRole('link', { name: 'Skip to navigation' });
      expect(navLink).toHaveAttribute('href', '#main-navigation');
      expect(screen.getByRole('navigation')).toHaveAttribute('id', 'main-navigation');
    });
  });
});

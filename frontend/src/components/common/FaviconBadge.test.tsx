import { render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import FaviconBadge from './FaviconBadge';

describe('FaviconBadge', () => {
  let originalTitle: string;

  beforeEach(() => {
    // Store original title
    originalTitle = document.title;
  });

  afterEach(() => {
    // Restore original title
    document.title = originalTitle;
    vi.restoreAllMocks();
  });

  describe('component rendering', () => {
    it('renders nothing visible', () => {
      const { container } = render(<FaviconBadge alertCount={0} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('document title updates', () => {
    it('updates title with alert count when count > 0', () => {
      render(<FaviconBadge alertCount={5} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(5) Security Dashboard');
    });

    it('does not add count prefix when alert count is 0', () => {
      render(<FaviconBadge alertCount={0} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('Security Dashboard');
    });

    it('uses default base title when not provided', () => {
      render(<FaviconBadge alertCount={3} />);
      expect(document.title).toBe('(3) Security Dashboard');
    });

    it('handles negative alert count by treating as 0', () => {
      render(<FaviconBadge alertCount={-5} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('Security Dashboard');
    });

    it('handles decimal alert count by flooring', () => {
      render(<FaviconBadge alertCount={5.7} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(5) Security Dashboard');
    });

    it('updates title when alert count changes', () => {
      const { rerender } = render(<FaviconBadge alertCount={3} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(3) Security Dashboard');

      rerender(<FaviconBadge alertCount={10} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(10) Security Dashboard');

      rerender(<FaviconBadge alertCount={0} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('Security Dashboard');
    });
  });

  describe('enabled/disabled state', () => {
    it('does not update title when disabled after being enabled', () => {
      const { rerender } = render(
        <FaviconBadge alertCount={5} enabled={true} baseTitle="Security Dashboard" />
      );
      expect(document.title).toBe('(5) Security Dashboard');

      // When disabled, should restore to base title
      rerender(<FaviconBadge alertCount={5} enabled={false} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('Security Dashboard');
    });

    it('updates title when re-enabled', () => {
      const { rerender } = render(
        <FaviconBadge alertCount={5} enabled={false} baseTitle="Security Dashboard" />
      );
      expect(document.title).toBe('Security Dashboard');

      rerender(<FaviconBadge alertCount={5} enabled={true} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(5) Security Dashboard');
    });
  });

  describe('edge cases', () => {
    it('handles alert count of 99+', () => {
      render(<FaviconBadge alertCount={150} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(150) Security Dashboard');
    });

    it('handles very large alert counts', () => {
      render(<FaviconBadge alertCount={9999} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('(9999) Security Dashboard');
    });
  });

  describe('custom styling props', () => {
    it('accepts custom badge color without errors', () => {
      const { unmount } = render(
        <FaviconBadge alertCount={5} badgeColor="#ff0000" baseTitle="Security Dashboard" />
      );
      // Component should render without errors
      expect(document.title).toBe('(5) Security Dashboard');
      unmount();
    });

    it('accepts custom badge text color without errors', () => {
      const { unmount } = render(
        <FaviconBadge alertCount={5} badgeTextColor="#000000" baseTitle="Security Dashboard" />
      );
      // Component should render without errors
      expect(document.title).toBe('(5) Security Dashboard');
      unmount();
    });

    it('accepts custom favicon path without errors', () => {
      const { unmount } = render(
        <FaviconBadge
          alertCount={5}
          faviconPath="/custom-favicon.svg"
          baseTitle="Security Dashboard"
        />
      );
      // Component should render without errors
      expect(document.title).toBe('(5) Security Dashboard');
      unmount();
    });
  });

  describe('cleanup', () => {
    it('restores base title on unmount', () => {
      const { unmount } = render(
        <FaviconBadge alertCount={5} baseTitle="Security Dashboard" />
      );
      expect(document.title).toBe('(5) Security Dashboard');

      unmount();
      // After unmount, title should be restored to base title
      expect(document.title).toBe('Security Dashboard');
    });

    it('restores base title when count goes to 0', () => {
      const { rerender } = render(
        <FaviconBadge alertCount={5} baseTitle="Security Dashboard" />
      );
      expect(document.title).toBe('(5) Security Dashboard');

      rerender(<FaviconBadge alertCount={0} baseTitle="Security Dashboard" />);
      expect(document.title).toBe('Security Dashboard');
    });
  });
});

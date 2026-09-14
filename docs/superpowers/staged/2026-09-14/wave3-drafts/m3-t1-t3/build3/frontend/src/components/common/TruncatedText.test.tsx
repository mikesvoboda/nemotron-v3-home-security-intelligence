import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import TruncatedText, { type TruncatedTextProps } from './TruncatedText';

describe('TruncatedText', () => {
  // Short text that shouldn't be truncated
  const shortText = 'This is a short text.';

  // Long text that should be truncated
  const longText =
    'This is a very long description text that exceeds the default maximum character limit and should be truncated with a "Show more" button. It contains multiple sentences to demonstrate how the truncation works with real-world content that might appear in alert descriptions or event summaries.';

  const defaultProps: TruncatedTextProps = {
    text: longText,
  };

  describe('basic rendering', () => {
    it('renders text content', () => {
      render(<TruncatedText {...defaultProps} />);
      // Should show truncated text
      expect(screen.getByText(/This is a very long/)).toBeInTheDocument();
    });

    it('renders without errors for short text', () => {
      render(<TruncatedText text={shortText} />);
      expect(screen.getByText(shortText)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<TruncatedText {...defaultProps} className="custom-class" />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('custom-class');
    });

    it('renders as paragraph element by default', () => {
      render(<TruncatedText {...defaultProps} />);
      const textElement = screen.getByText(/This is a very long/).closest('p');
      expect(textElement).toBeInTheDocument();
      expect(textElement?.tagName).toBe('P');
    });
  });

  describe('truncation behavior', () => {
    it('does not show toggle button for short text', () => {
      render(<TruncatedText text={shortText} maxLength={200} />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('shows "Show more" button for long text', () => {
      render(<TruncatedText text={longText} maxLength={100} />);
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('truncates text at specified maxLength', () => {
      render(<TruncatedText text={longText} maxLength={50} />);
      // The truncated text should end with ellipsis
      expect(screen.getByText(/\.\.\./)).toBeInTheDocument();
    });

    it('uses default maxLength of 200 characters', () => {
      render(<TruncatedText text={longText} />);
      // Default is 200 chars, so long text should be truncated
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('does not truncate text exactly at maxLength if it would cut a word', () => {
      // Truncation should try to end at a word boundary
      render(<TruncatedText text="Hello world this is a test" maxLength={12} />);
      // Should truncate at "Hello world" (11 chars) not "Hello world " (12 chars)
      const textContent = screen.getByText(/Hello/).textContent;
      expect(textContent).toMatch(/Hello world/);
    });
  });

  describe('expand/collapse functionality', () => {
    it('expands text when "Show more" is clicked', async () => {
      const user = userEvent.setup();
      render(<TruncatedText text={longText} maxLength={100} />);

      const showMoreButton = screen.getByRole('button', { name: /show more/i });
      await user.click(showMoreButton);

      // Full text should be visible
      expect(screen.getByText(longText)).toBeInTheDocument();
      // Button should now say "Show less"
      expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument();
    });

    it('collapses text when "Show less" is clicked', async () => {
      const user = userEvent.setup();
      render(<TruncatedText text={longText} maxLength={100} />);

      // Expand
      await user.click(screen.getByRole('button', { name: /show more/i }));
      expect(screen.getByText(longText)).toBeInTheDocument();

      // Collapse
      await user.click(screen.getByRole('button', { name: /show less/i }));
      expect(screen.queryByText(longText)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('starts collapsed by default', () => {
      render(<TruncatedText text={longText} maxLength={100} />);
      // Should show truncated version, not full text
      expect(screen.queryByText(longText)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('can start expanded when initialExpanded is true', () => {
      render(<TruncatedText text={longText} maxLength={100} initialExpanded />);
      // Should show full text
      expect(screen.getByText(longText)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('toggle button has accessible name', () => {
      render(<TruncatedText text={longText} maxLength={100} />);
      const button = screen.getByRole('button', { name: /show more/i });
      expect(button).toBeInTheDocument();
    });

    it('has aria-expanded attribute on button', () => {
      render(<TruncatedText text={longText} maxLength={100} />);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    it('aria-expanded is true when text is expanded', async () => {
      const user = userEvent.setup();
      render(<TruncatedText text={longText} maxLength={100} />);

      await user.click(screen.getByRole('button'));
      expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
    });

    it('text container has proper data attribute for testing', () => {
      const { container } = render(<TruncatedText text={longText} maxLength={100} />);
      expect(container.querySelector('[data-testid="truncated-text"]')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies text styling classes', () => {
      const { container } = render(<TruncatedText {...defaultProps} />);
      const textElement = container.querySelector('p');
      expect(textElement).toHaveClass('text-sm', 'leading-relaxed', 'text-gray-200');
    });

    it('toggle button has consistent styling', () => {
      render(<TruncatedText text={longText} maxLength={100} />);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('text-[#76B900]');
    });

    it('applies transition classes for smooth animation', () => {
      const { container } = render(<TruncatedText text={longText} maxLength={100} />);
      const textWrapper = container.querySelector('[data-testid="truncated-text"]');
      expect(textWrapper).toHaveClass('transition-all');
    });
  });

  describe('edge cases', () => {
    it('handles empty string', () => {
      render(<TruncatedText text="" />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('handles text exactly at maxLength', () => {
      const exactText = 'a'.repeat(100);
      render(<TruncatedText text={exactText} maxLength={100} />);
      // Should not show button since text is exactly at limit
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('handles text slightly over maxLength', () => {
      const overText = 'a'.repeat(101);
      render(<TruncatedText text={overText} maxLength={100} />);
      // Should show button since text exceeds limit
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('handles text with only whitespace', () => {
      render(<TruncatedText text="   " />);
      // Should render whitespace without toggle
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('handles text with newlines', () => {
      const multilineText = 'Line 1\nLine 2\nLine 3\n'.repeat(20);
      render(<TruncatedText text={multilineText} maxLength={100} />);
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('handles special characters', () => {
      const specialText = '<script>alert("xss")</script> & special chars: < > " \' &';
      render(<TruncatedText text={specialText} maxLength={20} />);
      // Text should be safely escaped
      expect(screen.getByText(/script/)).toBeInTheDocument();
    });

    it('handles maxLength of 0', () => {
      render(<TruncatedText text={longText} maxLength={0} />);
      // Should show toggle button since any text exceeds 0
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('handles very large maxLength', () => {
      render(<TruncatedText text={shortText} maxLength={10000} />);
      // Short text should not be truncated
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('maxLines mode', () => {
    // Some implementations support truncation by lines instead of characters
    it('supports maxLines prop for line-based truncation', () => {
      // This test uses CSS-based truncation with line-clamp
      render(<TruncatedText text={longText} maxLines={3} />);
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });

    it('maxLines takes precedence over maxLength when both provided', () => {
      // Create a very long text that would exceed both maxLength and maxLines
      const veryLongText = 'This is a long sentence. '.repeat(50);
      render(<TruncatedText text={veryLongText} maxLength={1000} maxLines={2} />);
      // Even though maxLength is 1000, maxLines should trigger truncation via CSS
      // and show the toggle button
      expect(screen.getByRole('button', { name: /show more/i })).toBeInTheDocument();
    });
  });

  describe('custom labels', () => {
    it('supports custom showMoreLabel', () => {
      render(<TruncatedText text={longText} maxLength={100} showMoreLabel="Read more" />);
      expect(screen.getByRole('button', { name: /read more/i })).toBeInTheDocument();
    });

    it('supports custom showLessLabel', async () => {
      const user = userEvent.setup();
      render(
        <TruncatedText
          text={longText}
          maxLength={100}
          showMoreLabel="Read more"
          showLessLabel="Read less"
        />
      );

      await user.click(screen.getByRole('button', { name: /read more/i }));
      expect(screen.getByRole('button', { name: /read less/i })).toBeInTheDocument();
    });
  });

  describe('callback support', () => {
    it('calls onToggle callback when expanded', async () => {
      const onToggle = vi.fn();
      const user = userEvent.setup();
      render(<TruncatedText text={longText} maxLength={100} onToggle={onToggle} />);

      await user.click(screen.getByRole('button'));
      expect(onToggle).toHaveBeenCalledWith(true);
    });

    it('calls onToggle callback when collapsed', async () => {
      const onToggle = vi.fn();
      const user = userEvent.setup();
      render(<TruncatedText text={longText} maxLength={100} onToggle={onToggle} />);

      // Expand
      await user.click(screen.getByRole('button'));
      expect(onToggle).toHaveBeenCalledWith(true);

      // Collapse
      await user.click(screen.getByRole('button'));
      expect(onToggle).toHaveBeenCalledWith(false);
    });
  });
});

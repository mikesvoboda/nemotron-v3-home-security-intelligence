import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import SafeErrorMessage from './SafeErrorMessage';
import { sanitizeErrorMessage } from '../../utils/sanitize';

describe('SafeErrorMessage', () => {
  describe('XSS Prevention', () => {
    it('should neutralize script tags in error messages', () => {
      const xssPayload = '<script>alert("XSS")</script>Error occurred';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Error occurred');
      expect(element.innerHTML).not.toContain('<script>');
      expect(element.innerHTML).not.toContain('alert');
    });

    it('should neutralize onclick attributes', () => {
      const xssPayload = '<img src=x onerror="alert(\'XSS\')">Error message';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Error message');
      expect(element.innerHTML).not.toContain('onerror');
      expect(element.innerHTML).not.toContain('<img');
    });

    it('should neutralize javascript: URLs', () => {
      const xssPayload = '<a href="javascript:alert(\'XSS\')">Click me</a> Error';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Click me Error');
      expect(element.innerHTML).not.toContain('javascript:');
      expect(element.innerHTML).not.toContain('<a');
    });

    it('should neutralize data: URLs with base64 encoded scripts', () => {
      const xssPayload =
        '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=">Link</a> Error';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Link Error');
      expect(element.innerHTML).not.toContain('data:');
    });

    it('should neutralize SVG with embedded scripts', () => {
      const xssPayload = '<svg onload="alert(\'XSS\')"><circle r="10"/></svg>SVG attack';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('SVG attack');
      expect(element.innerHTML).not.toContain('<svg');
      expect(element.innerHTML).not.toContain('onload');
    });

    it('should neutralize event handlers in various tags', () => {
      const xssPayload = '<div onmouseover="alert(\'XSS\')">Hover me</div> Error';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Hover me Error');
      expect(element.innerHTML).not.toContain('onmouseover');
    });

    it('should neutralize iframe injection', () => {
      const xssPayload = '<iframe src="javascript:alert(\'XSS\')"></iframe>Frame attack';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Frame attack');
      expect(element.innerHTML).not.toContain('<iframe');
    });

    it('should neutralize style-based XSS', () => {
      const xssPayload =
        '<style>body{background:url("javascript:alert(\'XSS\')")}</style>Style attack';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toBe('Style attack');
      expect(element.innerHTML).not.toContain('<style');
    });

    it('should handle encoded XSS payloads', () => {
      // URL encoded script tag
      const xssPayload = '%3Cscript%3Ealert(%22XSS%22)%3C/script%3EEncoded error';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      // URL encoding should be preserved as text, not executed
      expect(element.textContent).toContain('Encoded error');
    });

    it('should neutralize nested XSS attempts', () => {
      const xssPayload = '<<script>script>alert("XSS")<</script>/script>Nested';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.innerHTML).not.toContain('<script');
    });

    it('should neutralize unicode-encoded XSS', () => {
      const xssPayload = '\u003cscript\u003ealert("XSS")\u003c/script\u003eUnicode';
      render(<SafeErrorMessage message={xssPayload} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.innerHTML).not.toContain('<script');
      expect(element.textContent).toContain('Unicode');
    });
  });

  describe('sanitizeErrorMessage function', () => {
    it('should remove all HTML tags', () => {
      expect(sanitizeErrorMessage('<b>Bold</b> text')).toBe('Bold text');
    });

    it('should handle script tags', () => {
      expect(sanitizeErrorMessage('<script>alert("XSS")</script>Safe')).toBe('Safe');
    });

    it('should preserve HTML entities for safety', () => {
      // HTML entities are NOT decoded to prevent XSS via double-encoding attacks
      // This is intentional security behavior - &lt;script&gt; stays as-is
      // rather than being decoded to <script> which could be dangerous
      expect(sanitizeErrorMessage('&lt;script&gt;')).toBe('&lt;script&gt;');
    });

    it('should trim whitespace', () => {
      expect(sanitizeErrorMessage('  Error message  ')).toBe('Error message');
    });

    it('should return empty string for empty input', () => {
      expect(sanitizeErrorMessage('')).toBe('');
    });

    it('should handle complex nested tags', () => {
      expect(sanitizeErrorMessage('<div><span onclick="alert()">Text</span></div>')).toBe('Text');
    });
  });

  describe('Basic Rendering', () => {
    it('should render a string message', () => {
      render(<SafeErrorMessage message="Test error message" />);

      expect(screen.getByTestId('safe-error-message')).toHaveTextContent('Test error message');
    });

    it('should render an Error object message', () => {
      const error = new Error('Error object message');
      render(<SafeErrorMessage message={error} />);

      expect(screen.getByTestId('safe-error-message')).toHaveTextContent('Error object message');
    });

    it('should render nothing for null message', () => {
      const { container } = render(<SafeErrorMessage message={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('should render nothing for undefined message', () => {
      const { container } = render(<SafeErrorMessage message={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('should render nothing for empty string message', () => {
      const { container } = render(<SafeErrorMessage message="" />);
      expect(container.firstChild).toBeNull();
    });

    it('should render as p tag by default', () => {
      render(<SafeErrorMessage message="Error" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element.tagName).toBe('P');
    });

    it('should render as span when inline is true', () => {
      render(<SafeErrorMessage message="Error" inline />);
      const element = screen.getByTestId('safe-error-message');
      expect(element.tagName).toBe('SPAN');
    });
  });

  describe('Styling', () => {
    it('should apply default size class (sm)', () => {
      render(<SafeErrorMessage message="Error" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-sm');
    });

    it('should apply xs size class', () => {
      render(<SafeErrorMessage message="Error" size="xs" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-xs');
    });

    it('should apply md size class', () => {
      render(<SafeErrorMessage message="Error" size="md" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-base');
    });

    it('should apply lg size class', () => {
      render(<SafeErrorMessage message="Error" size="lg" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-lg');
    });

    it('should apply default color class (red)', () => {
      render(<SafeErrorMessage message="Error" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-red-400');
    });

    it('should apply gray color class', () => {
      render(<SafeErrorMessage message="Error" color="gray" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-gray-400');
    });

    it('should apply yellow color class', () => {
      render(<SafeErrorMessage message="Error" color="yellow" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('text-yellow-400');
    });

    it('should apply custom className', () => {
      render(<SafeErrorMessage message="Error" className="custom-class mt-2" />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('mt-2', 'custom-class');
    });

    it('should apply line-clamp class when maxLines is set', () => {
      render(<SafeErrorMessage message="Error" maxLines={2} />);
      const element = screen.getByTestId('safe-error-message');
      expect(element).toHaveClass('line-clamp-2');
    });
  });

  describe('Test ID', () => {
    it('should use default testId', () => {
      render(<SafeErrorMessage message="Error" />);
      expect(screen.getByTestId('safe-error-message')).toBeInTheDocument();
    });

    it('should use custom testId', () => {
      render(<SafeErrorMessage message="Error" testId="custom-error" />);
      expect(screen.getByTestId('custom-error')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long error messages', () => {
      const longMessage = 'Error '.repeat(1000);
      render(<SafeErrorMessage message={longMessage} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element).toBeInTheDocument();
      expect(element.textContent).toContain('Error');
    });

    it('should handle special characters in messages', () => {
      const specialMessage = 'Error: file "test.txt" not found <path>';
      render(<SafeErrorMessage message={specialMessage} />);

      const element = screen.getByTestId('safe-error-message');
      // The < and > should be preserved after sanitization since they're not actual tags
      expect(element.textContent).toContain('Error');
    });

    it('should handle newlines in messages', () => {
      const multilineMessage = 'Error line 1\nError line 2';
      render(<SafeErrorMessage message={multilineMessage} />);

      const element = screen.getByTestId('safe-error-message');
      expect(element.textContent).toContain('Error line 1');
      expect(element.textContent).toContain('Error line 2');
    });

    it('should handle messages with only whitespace', () => {
      const { container } = render(<SafeErrorMessage message="   " />);
      expect(container.firstChild).toBeNull();
    });

    it('should handle messages that become empty after sanitization', () => {
      const xssOnlyMessage = '<script>alert("XSS")</script>';
      const { container } = render(<SafeErrorMessage message={xssOnlyMessage} />);
      expect(container.firstChild).toBeNull();
    });
  });
});

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PrintableReport from './PrintableReport';

describe('PrintableReport', () => {
  // Mock window.print
  const mockPrint = vi.fn();
  const originalPrint = window.print;

  beforeEach(() => {
    window.print = mockPrint;
    mockPrint.mockClear();
  });

  afterEach(() => {
    window.print = originalPrint;
  });

  describe('rendering', () => {
    it('renders children correctly', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Report content</p>
        </PrintableReport>
      );
      expect(screen.getByText('Report content')).toBeInTheDocument();
    });

    it('renders title when provided', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.getByText('Test Report')).toBeInTheDocument();
    });

    it('renders without title', () => {
      render(
        <PrintableReport>
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('renders print button by default', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.getByRole('button', { name: /print/i })).toBeInTheDocument();
    });

    it('hides print button when showPrintButton is false', () => {
      render(
        <PrintableReport title="Test Report" showPrintButton={false}>
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.queryByRole('button', { name: /print/i })).not.toBeInTheDocument();
    });

    it('renders timestamp in footer', () => {
      const now = new Date('2025-01-25T10:30:00Z');
      vi.setSystemTime(now);

      render(
        <PrintableReport title="Test Report" showTimestamp>
          <p>Content</p>
        </PrintableReport>
      );

      // The timestamp should be visible
      expect(screen.getByText(/generated/i)).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('hides timestamp when showTimestamp is false', () => {
      render(
        <PrintableReport title="Test Report" showTimestamp={false}>
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.queryByText(/generated/i)).not.toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <PrintableReport title="Test Report" className="custom-class">
          <p>Content</p>
        </PrintableReport>
      );
      const container = screen.getByTestId('printable-report');
      expect(container).toHaveClass('custom-class');
    });

    it('applies printable-report class for print styles', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );
      const container = screen.getByTestId('printable-report');
      expect(container).toHaveClass('printable-report');
    });
  });

  describe('print functionality', () => {
    it('calls window.print when print button is clicked', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      const printButton = screen.getByRole('button', { name: /print/i });
      fireEvent.click(printButton);

      expect(mockPrint).toHaveBeenCalledTimes(1);
    });

    it('triggers print on Ctrl+P keyboard shortcut', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      // Simulate Ctrl+P
      fireEvent.keyDown(document, { key: 'p', ctrlKey: true });

      expect(mockPrint).toHaveBeenCalledTimes(1);
    });

    it('triggers print on Cmd+P keyboard shortcut (Mac)', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      // Simulate Cmd+P (metaKey on Mac)
      fireEvent.keyDown(document, { key: 'p', metaKey: true });

      expect(mockPrint).toHaveBeenCalledTimes(1);
    });

    it('does not trigger print on P key without modifier', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      // Simulate just P key
      fireEvent.keyDown(document, { key: 'p' });

      expect(mockPrint).not.toHaveBeenCalled();
    });

    it('does not handle keyboard shortcut when enableKeyboardShortcut is false', () => {
      render(
        <PrintableReport title="Test Report" enableKeyboardShortcut={false}>
          <p>Content</p>
        </PrintableReport>
      );

      fireEvent.keyDown(document, { key: 'p', ctrlKey: true });

      expect(mockPrint).not.toHaveBeenCalled();
    });
  });

  describe('print button customization', () => {
    it('renders default print button text', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.getByRole('button')).toHaveTextContent(/print/i);
    });

    it('renders custom print button text', () => {
      render(
        <PrintableReport title="Test Report" printButtonText="Generate PDF">
          <p>Content</p>
        </PrintableReport>
      );
      expect(screen.getByRole('button')).toHaveTextContent('Generate PDF');
    });
  });

  describe('header and footer sections', () => {
    it('renders header section for print', () => {
      render(
        <PrintableReport title="Security Event Report">
          <p>Content</p>
        </PrintableReport>
      );

      const header = screen.getByTestId('print-header');
      expect(header).toBeInTheDocument();
      expect(header).toHaveClass('print-header');
    });

    it('renders footer section for print', () => {
      render(
        <PrintableReport title="Security Event Report" showTimestamp>
          <p>Content</p>
        </PrintableReport>
      );

      const footer = screen.getByTestId('print-footer');
      expect(footer).toBeInTheDocument();
      expect(footer).toHaveClass('print-footer');
    });
  });

  describe('accessibility', () => {
    it('print button has accessible name', () => {
      render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      const button = screen.getByRole('button', { name: /print/i });
      expect(button).toBeInTheDocument();
    });

    it('report has appropriate heading structure', () => {
      render(
        <PrintableReport title="Security Report">
          <p>Content</p>
        </PrintableReport>
      );

      // Title should be rendered with appropriate heading level
      expect(screen.getByRole('heading', { name: 'Security Report' })).toBeInTheDocument();
    });
  });

  describe('cleanup', () => {
    it('removes keyboard event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      const { unmount } = render(
        <PrintableReport title="Test Report">
          <p>Content</p>
        </PrintableReport>
      );

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });
  });
});

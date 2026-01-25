import { Printer } from 'lucide-react';
import { type ReactNode, useCallback, useEffect } from 'react';

import Button from './Button';

/**
 * PrintableReport component props
 */
export interface PrintableReportProps {
  /**
   * Report content to be printed
   */
  children: ReactNode;
  /**
   * Optional report title displayed in the header
   */
  title?: string;
  /**
   * Whether to show the print button
   * @default true
   */
  showPrintButton?: boolean;
  /**
   * Custom text for the print button
   * @default 'Print Report'
   */
  printButtonText?: string;
  /**
   * Whether to show the generated timestamp in the footer
   * @default true
   */
  showTimestamp?: boolean;
  /**
   * Whether to enable Ctrl+P / Cmd+P keyboard shortcut
   * @default true
   */
  enableKeyboardShortcut?: boolean;
  /**
   * Additional CSS classes for the container
   */
  className?: string;
}

/**
 * Format a date for display in the print footer
 */
function formatPrintTimestamp(date: Date): string {
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * PrintableReport - A wrapper component for print-optimized content
 *
 * Features:
 * - Print button that triggers window.print()
 * - Ctrl+P / Cmd+P keyboard shortcut handler
 * - Header with title (hidden on screen, shown on print)
 * - Footer with generated timestamp (hidden on screen, shown on print)
 * - Applies print-specific CSS class for @media print styles
 *
 * @example
 * ```tsx
 * // Basic usage
 * <PrintableReport title="Security Event Report">
 *   <EventDetails event={event} />
 * </PrintableReport>
 *
 * // Without keyboard shortcut
 * <PrintableReport
 *   title="Monthly Summary"
 *   enableKeyboardShortcut={false}
 * >
 *   <SummaryContent />
 * </PrintableReport>
 *
 * // Custom print button text
 * <PrintableReport
 *   title="Detection Report"
 *   printButtonText="Generate PDF"
 * >
 *   <ReportContent />
 * </PrintableReport>
 * ```
 */
export default function PrintableReport({
  children,
  title,
  showPrintButton = true,
  printButtonText = 'Print Report',
  showTimestamp = true,
  enableKeyboardShortcut = true,
  className = '',
}: PrintableReportProps) {
  /**
   * Trigger the browser's print dialog
   */
  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  /**
   * Handle keyboard shortcut (Ctrl+P or Cmd+P)
   */
  useEffect(() => {
    if (!enableKeyboardShortcut) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for Ctrl+P (Windows/Linux) or Cmd+P (Mac)
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault();
        handlePrint();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [enableKeyboardShortcut, handlePrint]);

  const containerClasses = ['printable-report', className].filter(Boolean).join(' ');

  return (
    <div className={containerClasses} data-testid="printable-report">
      {/* Print Header - Hidden on screen, shown on print */}
      <div className="print-header hidden print:block" data-testid="print-header">
        {title && (
          <h1 className="text-2xl font-bold text-gray-900 print:text-black">{title}</h1>
        )}
        <div className="mt-2 border-b border-gray-300 pb-4" />
      </div>

      {/* Print Button - Shown on screen, hidden on print */}
      {showPrintButton && (
        <div className="mb-4 flex justify-end print:hidden">
          <Button
            variant="secondary"
            leftIcon={<Printer className="h-4 w-4" />}
            onClick={handlePrint}
            aria-label={printButtonText}
          >
            {printButtonText}
          </Button>
        </div>
      )}

      {/* Main Content */}
      <div className="print-content">{children}</div>

      {/* Print Footer - Hidden on screen, shown on print */}
      {showTimestamp && (
        <div className="print-footer hidden print:block" data-testid="print-footer">
          <div className="mt-8 border-t border-gray-300 pt-4 text-sm text-gray-600 print:text-gray-700">
            <p>Generated: {formatPrintTimestamp(new Date())}</p>
            <p className="mt-1 text-xs text-gray-500">
              Home Security AI Monitoring Dashboard
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

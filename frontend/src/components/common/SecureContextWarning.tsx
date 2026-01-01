import { AlertTriangle, Shield, X } from 'lucide-react';
import { useState } from 'react';

import { getWebCodecsStatus, isSecureContext } from '../../utils/webcodecs';

export interface SecureContextWarningProps {
  /** Whether to show the warning even in secure contexts (for testing) */
  forceShow?: boolean;
  /** Whether the warning can be dismissed */
  dismissible?: boolean;
  /** Callback when warning is dismissed */
  onDismiss?: () => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * SecureContextWarning displays a banner when the application is not running
 * in a secure context (HTTPS). This affects certain browser APIs like WebCodecs.
 *
 * The warning is automatically hidden when in a secure context unless forceShow is true.
 * It provides helpful information about what features may be affected and how to resolve.
 */
export default function SecureContextWarning({
  forceShow = false,
  dismissible = true,
  onDismiss,
  className = '',
}: SecureContextWarningProps) {
  const [isDismissed, setIsDismissed] = useState(false);

  // Don't render if in secure context (unless forced) or dismissed
  const inSecureContext = isSecureContext();
  if ((inSecureContext && !forceShow) || isDismissed) {
    return null;
  }

  const status = getWebCodecsStatus();

  const handleDismiss = () => {
    setIsDismissed(true);
    onDismiss?.();
  };

  return (
    <div
      className={`rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 ${className}`}
      role="alert"
      data-testid="secure-context-warning"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-amber-500">
            Insecure Context Detected
          </h3>
          <div className="mt-1 text-sm text-amber-400/80">
            <p>{status.message}</p>
            {status.recommendation && (
              <p className="mt-2">{status.recommendation}</p>
            )}
          </div>
          <div className="mt-3 flex items-center gap-4 text-xs text-amber-400/60">
            <div className="flex items-center gap-1">
              <Shield className="h-3 w-3" aria-hidden="true" />
              <span>Current: HTTP</span>
            </div>
            <div className="flex items-center gap-1">
              <Shield className="h-3 w-3" aria-hidden="true" />
              <span>Required: HTTPS or localhost</span>
            </div>
          </div>
        </div>
        {dismissible && (
          <button
            type="button"
            onClick={handleDismiss}
            className="flex-shrink-0 rounded-md p-1 text-amber-500 hover:bg-amber-500/20 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            aria-label="Dismiss warning"
            data-testid="dismiss-warning-button"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}

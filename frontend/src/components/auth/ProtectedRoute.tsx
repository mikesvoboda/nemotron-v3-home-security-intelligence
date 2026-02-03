/**
 * ProtectedRoute - Route wrapper that requires authentication.
 *
 * Protects routes by checking authentication state and redirecting
 * unauthorized users appropriately:
 * - Redirects to /setup if first-time setup is required
 * - Redirects to /login if user is not authenticated
 * - Shows loading spinner while checking auth state
 * - Renders children when authenticated
 *
 * Preserves the intended destination in location state so users can
 * be redirected back after logging in.
 *
 * @example
 * ```tsx
 * <Route
 *   path="/dashboard"
 *   element={
 *     <ProtectedRoute>
 *       <DashboardPage />
 *     </ProtectedRoute>
 *   }
 * />
 * ```
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */
import { type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../contexts/AuthContext';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ProtectedRoute component.
 */
export interface ProtectedRouteProps {
  /** Child components to render when authenticated */
  children: ReactNode;
}

// ============================================================================
// Component
// ============================================================================

/**
 * ProtectedRoute component that wraps routes requiring authentication.
 *
 * Priority of redirects:
 * 1. If loading - show spinner
 * 2. If setup required or error checking setup - redirect to /setup
 * 3. If not authenticated - redirect to /login with intended destination
 * 4. If authenticated - render children
 */
export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isLoading, isAuthenticated, setupRequired, error } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth state
  if (isLoading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-[#121212]"
        data-testid="loading-spinner"
      >
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 rounded-full border-4 border-gray-700 border-t-green-500 motion-safe:animate-spin" />
          <p className="text-sm text-gray-400">Checking authentication...</p>
        </div>
      </div>
    );
  }

  // Redirect to setup if required or if there was an error checking setup status
  // (error likely means server issue - setup page can handle gracefully)
  if (setupRequired === true || (setupRequired === null && error)) {
    return <Navigate to="/setup" replace />;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  // Render children when authenticated
  return <>{children}</>;
}

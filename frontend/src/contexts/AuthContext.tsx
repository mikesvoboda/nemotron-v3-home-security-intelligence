/**
 * AuthContext - Authentication state management for the React frontend.
 *
 * Provides authentication state and operations including:
 * - Setup status checking (first-time setup flow)
 * - Current user state
 * - Login, logout, and registration functions
 * - Loading and error states
 *
 * Uses React Query for data fetching and caching.
 *
 * @example
 * // Wrap your app with the provider (inside QueryClientProvider)
 * <QueryClientProvider client={queryClient}>
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 * </QueryClientProvider>
 *
 * @example
 * // Use the hook in components
 * const { user, isAuthenticated, login, logout } = useAuth();
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';

import { setUnauthorizedHandler } from '../services/api';
import {
  getSetupStatus,
  getCurrentUser,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
  type User,
  type LoginRequest,
  type RegisterRequest,
} from '../services/authApi';

// ============================================================================
// Types
// ============================================================================

/**
 * Context value interface for authentication state and operations.
 */
export interface AuthContextType {
  /** Currently authenticated user, or null if not authenticated */
  user: User | null;
  /** True while initial auth state is being determined */
  isLoading: boolean;
  /** True if a user is currently authenticated */
  isAuthenticated: boolean;
  /** True if first-time setup is required (no users exist) */
  setupRequired: boolean | null;
  /**
   * True when the backend reported `auth_required` on setup-status
   * (`EXPOSE_LAN=true`). `null` until setup status has been answered.
   * `ProtectedRoute` shows the login screen only when this is true; an
   * absent flag (a backend predating B1.5) is treated as required.
   */
  authRequired: boolean | null;
  /** Error from setup status or current user fetch */
  error: Error | null;
  /**
   * Log in with credentials.
   * @param credentials - Email and password
   * @throws Error on invalid credentials
   */
  login: (credentials: LoginRequest) => Promise<void>;
  /**
   * Log out the current user.
   */
  logout: () => Promise<void>;
  /**
   * Register a new user account.
   * @param data - Registration data
   * @throws Error on validation errors
   */
  register: (data: RegisterRequest) => Promise<void>;
}

/**
 * Props for the AuthProvider component.
 */
export interface AuthProviderProps {
  /** Child components that can access the auth context */
  children: ReactNode;
}

// ============================================================================
// Context
// ============================================================================

/**
 * The Auth context - null when accessed outside of provider.
 */
const AuthContext = createContext<AuthContextType | null>(null);

// ============================================================================
// Query Keys
// ============================================================================

const SETUP_STATUS_KEY = ['auth', 'setup-status'] as const;
const CURRENT_USER_KEY = ['auth', 'current-user'] as const;

// ============================================================================
// Provider
// ============================================================================

/**
 * AuthProvider component - wraps the application to provide authentication state.
 *
 * Fetches setup status on mount to determine if first-time setup is required.
 * If setup is not required, fetches the current user to check authentication.
 *
 * @example
 * <QueryClientProvider client={queryClient}>
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 * </QueryClientProvider>
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();

  // Fetch setup status on mount
  const {
    data: setupStatus,
    isLoading: isSetupLoading,
    error: setupError,
  } = useQuery({
    queryKey: SETUP_STATUS_KEY,
    queryFn: getSetupStatus,
    staleTime: 60000, // 1 minute
    retry: false,
  });

  // Derive setupRequired from query result
  const setupRequired = setupStatus?.setup_required ?? null;

  // F1.3: does the backend gate its API? B1.5 put the flag in the
  // setup-status body (EXPOSE_LAN). A response predating the field omits it;
  // fail closed — guessing "open" would expose the UI, guessing "required"
  // only shows a login form the (older) backend can still answer.
  const authRequired = setupStatus ? (setupStatus.auth_required ?? true) : null;

  // Fetch current user only when setup is not required AND the backend
  // gates its API. With EXPOSE_LAN unset nothing is being gated, so the
  // guard must not round-trip /api/auth/me and bounce to a login nobody
  // asked for (F1.3 Done when: "with EXPOSE_LAN unset no login appears").
  const {
    data: currentUser,
    isLoading: isUserLoading,
    error: userError,
  } = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: getCurrentUser,
    enabled: setupRequired === false && authRequired !== false,
    staleTime: 60000, // 1 minute
    retry: false,
  });

  // F1.3: a 401 from any fetchApi call means the session stopped being valid
  // (the B1.5 gate refuses with 401 {"detail": "Authentication required"}).
  // Drop the cached user; ProtectedRoute re-derives from the empty cache and
  // routes to /login. The guard's own redirect is the router — AuthProvider
  // renders outside BrowserRouter, so this layer cannot call useNavigate.
  useEffect(
    () =>
      setUnauthorizedHandler(() => {
        queryClient.setQueryData(CURRENT_USER_KEY, null);
      }),
    [queryClient]
  );

  // Determine overall loading state
  // F1.3: setup-status must be ANSWERED before the guard decides anything.
  // The persisted-query provider renders children during restore, and a
  // query that is pending-but-not-yet-fetching reports isLoading false
  // (React Query v5: isLoading = isPending && isFetching). Without this
  // window covered, ProtectedRoute's fail-closed branch (authRequired null
  // !== false) bounces a cold-starting visitor to /login before the
  // backend has answered — observed at +143ms against a live stack, with
  // the setup-status response landing 42ms later. Done when run 2 forbids
  // that bounce. An ANSWERED-but-fieldless status still fails closed (see
  // authRequired above); only an errored one skips the loading window.
  const setupStatusPending = setupStatus === undefined && !setupError;
  const isLoading =
    setupStatusPending || isSetupLoading || (setupRequired === false && isUserLoading);

  // User is null if not authenticated or setup required
  const user = setupRequired ? null : (currentUser ?? null);

  // Determine if authenticated
  const isAuthenticated = user !== null;

  // Combine errors
  const error = setupError || (setupRequired === false ? userError : null);

  /**
   * Log in with credentials and refresh user state.
   */
  const login = useCallback(
    async (credentials: LoginRequest) => {
      await loginApi(credentials);
      // Refetch current user after successful login
      await queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
    },
    [queryClient]
  );

  /**
   * Log out and clear user state.
   */
  const logout = useCallback(async () => {
    await logoutApi();
    // Refetch current user after logout (will fail with 401, clearing state)
    await queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
  }, [queryClient]);

  /**
   * Register a new user and refresh auth state.
   */
  const register = useCallback(
    async (data: RegisterRequest) => {
      await registerApi(data);
      // Refetch setup status and current user after registration.
      // Use refetchQueries (not invalidateQueries) to ensure the new data
      // is fetched before returning — prevents race condition where navigation
      // to '/' sees stale setup_required=true from the cache.
      await queryClient.refetchQueries({ queryKey: SETUP_STATUS_KEY });
      await queryClient.refetchQueries({ queryKey: CURRENT_USER_KEY });
    },
    [queryClient]
  );

  /**
   * Memoized context value to prevent unnecessary re-renders.
   */
  const contextValue = useMemo<AuthContextType>(
    () => ({
      user,
      isLoading,
      isAuthenticated,
      setupRequired,
      authRequired,
      error: error,
      login,
      logout,
      register,
    }),
    [user, isLoading, isAuthenticated, setupRequired, authRequired, error, login, logout, register]
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to access the authentication context.
 *
 * Must be used within an AuthProvider. Throws an error if used outside.
 *
 * @returns The auth context with user state and auth operations
 * @throws Error if used outside of AuthProvider
 *
 * @example
 * function MyComponent() {
 *   const { user, isAuthenticated, login, logout } = useAuth();
 *
 *   if (!isAuthenticated) {
 *     return <LoginForm onSubmit={login} />;
 *   }
 *
 *   return (
 *     <div>
 *       Welcome, {user.full_name}!
 *       <button onClick={logout}>Logout</button>
 *     </div>
 *   );
 * }
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// ============================================================================
// Re-exports
// ============================================================================

export type { User, LoginRequest, RegisterRequest } from '../services/authApi';

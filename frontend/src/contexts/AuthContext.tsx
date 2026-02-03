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
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

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

  // Fetch current user only when setup is not required
  const {
    data: currentUser,
    isLoading: isUserLoading,
    error: userError,
  } = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: getCurrentUser,
    enabled: setupRequired === false, // Only fetch when setup not required
    staleTime: 60000, // 1 minute
    retry: false,
  });

  // Determine overall loading state
  const isLoading = isSetupLoading || (setupRequired === false && isUserLoading);

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
      // Refetch setup status and current user after registration
      await queryClient.invalidateQueries({ queryKey: SETUP_STATUS_KEY });
      await queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
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
      error: error as Error | null,
      login,
      logout,
      register,
    }),
    [user, isLoading, isAuthenticated, setupRequired, error, login, logout, register]
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

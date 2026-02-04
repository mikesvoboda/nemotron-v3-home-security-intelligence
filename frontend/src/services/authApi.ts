/**
 * Authentication API Client
 *
 * API client for authentication operations including:
 * - Setup status checking (first-time setup flow)
 * - User registration
 * - User login/logout
 * - Current user fetching
 *
 * All requests include credentials for cookie-based session authentication.
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */

// ============================================================================
// Types
// ============================================================================

/**
 * User model returned from authentication endpoints.
 */
export interface User {
  /** Unique user identifier */
  id: number;
  /** Username for login */
  username: string;
  /** User email address */
  email: string;
  /** Whether the user account is active */
  is_active?: boolean;
  /** Whether the user has admin privileges */
  is_admin?: boolean;
  /** ISO 8601 timestamp of account creation */
  created_at: string;
  /** ISO 8601 timestamp of last login */
  last_login_at?: string | null;
}

/**
 * Response from setup-status endpoint.
 */
export interface SetupStatusResponse {
  /** True if no users exist and setup is required */
  setup_required: boolean;
}

/**
 * Request payload for user registration.
 */
export interface RegisterRequest {
  /** Username for login (alphanumeric, underscores, hyphens only) */
  username: string;
  /** User email address */
  email: string;
  /** User password (minimum 12 characters) */
  password: string;
}

/**
 * Request payload for user login.
 */
export interface LoginRequest {
  /** User email address */
  email: string;
  /** User password */
  password: string;
}

/**
 * Response from login/logout endpoints.
 */
export interface LoginResponse {
  /** Success message */
  message: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the base URL for API requests.
 */
function getBaseUrl(): string {
  return (import.meta.env.VITE_API_URL as string | undefined) || '';
}

/**
 * Handle API response and throw error if not successful.
 * Validates JSON response format.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    // Try to extract error detail from response body
    let detail: string | undefined;
    try {
      const errorBody: unknown = await response.json();
      if (
        typeof errorBody === 'object' &&
        errorBody !== null &&
        'detail' in errorBody &&
        typeof (errorBody as { detail: unknown }).detail === 'string'
      ) {
        detail = (errorBody as { detail: string }).detail;
      }
    } catch {
      // Ignore JSON parsing errors for error responses
    }

    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  // Validate response is JSON
  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    throw new Error('Response is not valid JSON');
  }

  return response.json() as Promise<T>;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Check if first-time setup is required.
 *
 * Returns setup_required: true if no users exist in the system,
 * indicating the user should be redirected to the setup page.
 *
 * @returns SetupStatusResponse indicating if setup is required
 * @throws Error on network or server errors
 *
 * @example
 * ```typescript
 * const { setup_required } = await getSetupStatus();
 * if (setup_required) {
 *   navigate('/setup');
 * }
 * ```
 */
export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const baseUrl = getBaseUrl();

  const response = await fetch(`${baseUrl}/api/auth/setup-status`, {
    method: 'GET',
    credentials: 'include',
  });

  return handleResponse<SetupStatusResponse>(response);
}

/**
 * Register a new user account.
 *
 * Creates the first admin user during initial setup or additional
 * users if registration is enabled. Returns the created user on success.
 *
 * @param data - Registration request data
 * @returns Created User object
 * @throws Error on validation errors (400) or network errors
 *
 * @example
 * ```typescript
 * const user = await register({
 *   email: 'admin@example.com',
 *   password: 'securepassword123',
 *   full_name: 'Admin User',
 * });
 * ```
 */
export async function register(data: RegisterRequest): Promise<User> {
  const baseUrl = getBaseUrl();

  const response = await fetch(`${baseUrl}/api/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
    credentials: 'include',
  });

  return handleResponse<User>(response);
}

/**
 * Log in with email and password.
 *
 * Authenticates the user and establishes a session cookie.
 * Returns a success message on valid credentials.
 *
 * @param credentials - Login credentials
 * @returns LoginResponse with success message
 * @throws Error on invalid credentials (401) or network errors
 *
 * @example
 * ```typescript
 * await login({ email: 'user@example.com', password: 'password123' });
 * // Session cookie is now set, user is authenticated
 * ```
 */
export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const baseUrl = getBaseUrl();

  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
    credentials: 'include',
  });

  return handleResponse<LoginResponse>(response);
}

/**
 * Log out the current user.
 *
 * Invalidates the session and clears the session cookie.
 *
 * @returns LoginResponse with success message
 * @throws Error on server errors or if not authenticated
 *
 * @example
 * ```typescript
 * await logout();
 * // Session is now invalidated
 * ```
 */
export async function logout(): Promise<LoginResponse> {
  const baseUrl = getBaseUrl();

  const response = await fetch(`${baseUrl}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  return handleResponse<LoginResponse>(response);
}

/**
 * Get the currently authenticated user.
 *
 * Returns the user associated with the current session cookie.
 * Throws on 401 if not authenticated.
 *
 * @returns Current User object
 * @throws Error if not authenticated (401) or on server errors
 *
 * @example
 * ```typescript
 * try {
 *   const user = await getCurrentUser();
 *   console.log('Logged in as:', user.email);
 * } catch (error) {
 *   // Not authenticated
 *   navigate('/login');
 * }
 * ```
 */
export async function getCurrentUser(): Promise<User> {
  const baseUrl = getBaseUrl();

  const response = await fetch(`${baseUrl}/api/auth/me`, {
    method: 'GET',
    credentials: 'include',
  });

  return handleResponse<User>(response);
}

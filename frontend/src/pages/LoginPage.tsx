/**
 * LoginPage - User authentication page.
 *
 * Provides a login form for users to authenticate with their credentials.
 * Supports redirect back to the intended destination after login.
 *
 * Features:
 * - Email and password fields
 * - Client-side validation
 * - Error handling for invalid credentials
 * - Redirect to dashboard or intended destination on success
 * - Redirect to setup page if setup is required
 * - Link to setup page if no account exists
 * - Accessible form with proper labels and ARIA attributes
 *
 * @example
 * ```tsx
 * <Route path="/login" element={<LoginPage />} />
 * ```
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */
import { clsx } from 'clsx';
import { AlertCircle, LogIn, Shield } from 'lucide-react';
import { useCallback, useEffect, useId, useState, type FormEvent } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';

import Button from '../components/common/Button';
import { useAuth } from '../contexts/AuthContext';

// ============================================================================
// Types
// ============================================================================

/**
 * Form data for the login form.
 */
interface LoginFormData {
  email: string;
  password: string;
}

/**
 * Validation errors for each form field.
 */
interface FormErrors {
  email?: string;
  password?: string;
}

/**
 * Location state with intended destination.
 */
interface LocationState {
  from?: string;
}

// ============================================================================
// Validation
// ============================================================================

/**
 * Email validation regex pattern.
 */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validates the form data and returns any errors.
 */
function validateForm(data: LoginFormData): FormErrors {
  const errors: FormErrors = {};

  // Email validation
  if (!data.email.trim()) {
    errors.email = 'Email is required';
  } else if (!EMAIL_REGEX.test(data.email)) {
    errors.email = 'Invalid email format';
  }

  // Password validation
  if (!data.password) {
    errors.password = 'Password is required';
  }

  return errors;
}

// ============================================================================
// Component
// ============================================================================

/**
 * LoginPage component for user authentication.
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, isLoading, setupRequired } = useAuth();
  const formId = useId();

  // Get the intended destination from location state
  const locationState = location.state as LocationState | null;
  const from = locationState?.from ?? '/';

  // Form state
  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      void navigate(from, { replace: true });
    }
  }, [isLoading, isAuthenticated, navigate, from]);

  // Redirect to setup if required
  useEffect(() => {
    if (!isLoading && setupRequired === true) {
      void navigate('/setup', { replace: true });
    }
  }, [isLoading, setupRequired, navigate]);

  /**
   * Handle form field changes.
   */
  const handleChange = useCallback(
    (field: keyof LoginFormData) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setFormData((prev) => ({ ...prev, [field]: value }));
      // Clear field error when user starts typing
      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
      // Clear API error when user makes changes
      if (apiError) {
        setApiError(null);
      }
    },
    [errors, apiError]
  );

  /**
   * Handle form submission.
   */
  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();

      // Validate form
      const validationErrors = validateForm(formData);
      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors);
        return;
      }

      setIsSubmitting(true);
      setApiError(null);

      try {
        await login({
          email: formData.email,
          password: formData.password,
        });
        // Navigate to intended destination on success
        void navigate(from, { replace: true });
      } catch (error) {
        // Handle login error
        if (error instanceof Error) {
          // Check for network errors (fetch failures) and show generic message
          const isNetworkError =
            error.name === 'TypeError' ||
            error.message.toLowerCase().includes('fetch') ||
            error.message.toLowerCase().includes('network');
          if (isNetworkError) {
            setApiError('Failed to log in. Please check your credentials and try again.');
          } else {
            setApiError(error.message);
          }
        } else {
          setApiError('Failed to log in. Please check your credentials and try again.');
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [formData, login, navigate, from]
  );

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212]">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 rounded-full border-4 border-gray-700 border-t-green-500 motion-safe:animate-spin" />
          <p className="text-sm text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#121212] px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#76B900]/10">
            <Shield className="h-8 w-8 text-[#76B900]" />
          </div>
          <h1 className="text-2xl font-bold text-white">Welcome Back</h1>
          <p className="mt-2 text-gray-400">Sign in to your account to continue</p>
        </div>

        {/* Form */}
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6" noValidate>
          {/* API Error Display */}
          {apiError && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3"
            >
              <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
              <span className="text-sm text-red-400">{apiError}</span>
            </div>
          )}

          {/* Email Field */}
          <div>
            <label
              htmlFor={`${formId}-email`}
              className="block text-sm font-medium text-white"
            >
              Email
            </label>
            <input
              type="email"
              id={`${formId}-email`}
              value={formData.email}
              onChange={handleChange('email')}
              disabled={isSubmitting}
              autoComplete="email"
              aria-describedby={errors.email ? `${formId}-email-error` : undefined}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.email
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="you@example.com"
            />
            {errors.email && (
              <p id={`${formId}-email-error`} className="mt-1 text-sm text-red-500">
                {errors.email}
              </p>
            )}
          </div>

          {/* Password Field */}
          <div>
            <label
              htmlFor={`${formId}-password`}
              className="block text-sm font-medium text-white"
            >
              Password
            </label>
            <input
              type="password"
              id={`${formId}-password`}
              value={formData.password}
              onChange={handleChange('password')}
              disabled={isSubmitting}
              autoComplete="current-password"
              aria-describedby={errors.password ? `${formId}-password-error` : undefined}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.password
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="Enter your password"
            />
            {errors.password && (
              <p id={`${formId}-password-error`} className="mt-1 text-sm text-red-500">
                {errors.password}
              </p>
            )}
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            isLoading={isSubmitting}
            leftIcon={!isSubmitting ? <LogIn className="h-5 w-5" /> : undefined}
          >
            {isSubmitting ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>

        {/* Setup Link */}
        <p className="mt-6 text-center text-sm text-gray-400">
          First time here?{' '}
          <Link
            to="/setup"
            className="text-[#76B900] hover:text-[#8ED100] hover:underline focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]"
          >
            Set up your account
          </Link>
        </p>
      </div>
    </div>
  );
}

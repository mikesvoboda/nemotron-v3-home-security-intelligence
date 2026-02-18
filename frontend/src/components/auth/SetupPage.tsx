/**
 * SetupPage - First-time setup page for creating the admin account.
 *
 * Displayed when the system has no users and requires initial setup.
 * Provides a registration form for creating the first admin user.
 *
 * Features:
 * - Full name, email, password, and confirm password fields
 * - Client-side validation with real-time error feedback
 * - Redirects away if setup is not required
 * - On success, redirects to dashboard
 * - Accessible form with proper labels and ARIA attributes
 *
 * @example
 * ```tsx
 * <Route path="/setup" element={<SetupPage />} />
 * ```
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */
import { clsx } from 'clsx';
import { AlertCircle, LogIn, Shield, UserPlus } from 'lucide-react';
import { useCallback, useId, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../../contexts/AuthContext';
import Button from '../common/Button';

// ============================================================================
// Types
// ============================================================================

/**
 * Form data for the setup registration form.
 */
interface SetupFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

/**
 * Validation errors for each form field.
 */
interface FormErrors {
  username?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

// ============================================================================
// Validation
// ============================================================================

/**
 * Email validation regex pattern.
 */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Minimum password length requirement.
 */
const MIN_PASSWORD_LENGTH = 8;

/**
 * Username validation regex pattern (alphanumeric, underscores, hyphens).
 */
const USERNAME_REGEX = /^[a-zA-Z0-9_-]+$/;

/**
 * Validates the form data and returns any errors.
 */
function validateForm(data: SetupFormData): FormErrors {
  const errors: FormErrors = {};

  // Username validation
  if (!data.username.trim()) {
    errors.username = 'Username is required';
  } else if (data.username.length < 3) {
    errors.username = 'Username must be at least 3 characters';
  } else if (data.username.length > 50) {
    errors.username = 'Username must be at most 50 characters';
  } else if (!USERNAME_REGEX.test(data.username)) {
    errors.username = 'Username can only contain letters, numbers, underscores, and hyphens';
  }

  // Email validation
  if (!data.email.trim()) {
    errors.email = 'Email is required';
  } else if (!EMAIL_REGEX.test(data.email)) {
    errors.email = 'Invalid email format';
  }

  // Password validation
  if (!data.password) {
    errors.password = 'Password is required';
  } else if (data.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
  } else if (!/[A-Z]/.test(data.password)) {
    errors.password = 'Password must contain at least one uppercase letter'; // pragma: allowlist secret
  } else if (!/[a-z]/.test(data.password)) {
    errors.password = 'Password must contain at least one lowercase letter'; // pragma: allowlist secret
  } else if (!/\d/.test(data.password)) {
    errors.password = 'Password must contain at least one number'; // pragma: allowlist secret
  }

  // Confirm password validation
  if (data.password && data.confirmPassword !== data.password) {
    errors.confirmPassword = 'Passwords do not match';
  }

  return errors;
}

// ============================================================================
// Component
// ============================================================================

/**
 * SetupPage component for first-time admin registration.
 */
export default function SetupPage() {
  const navigate = useNavigate();
  const { setupRequired, isLoading, register: registerUser } = useAuth();
  const formId = useId();

  // Form state
  const [formData, setFormData] = useState<SetupFormData>({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * Handle form field changes.
   */
  const handleChange = useCallback(
    (field: keyof SetupFormData) => (e: React.ChangeEvent<HTMLInputElement>) => {
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
        await registerUser({
          username: formData.username,
          email: formData.email,
          password: formData.password,
        });
        // Navigate to dashboard on success
        void navigate('/');
      } catch (error) {
        // Handle registration error
        if (error instanceof Error) {
          // Check for network errors (fetch failures) and show generic message
          const isNetworkError =
            error.name === 'TypeError' ||
            error.message.toLowerCase().includes('fetch') ||
            error.message.toLowerCase().includes('network');
          if (isNetworkError) {
            setApiError('Failed to create account. Please try again.');
          } else {
            setApiError(error.message);
          }
        } else {
          setApiError('Failed to create account. Please try again.');
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [formData, registerUser, navigate]
  );

  // Show loading state while checking setup status
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
          <h1 className="text-2xl font-bold text-white">First Time Setup</h1>
          <p className="mt-2 text-gray-400">Create your admin account to get started</p>
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
              aria-describedby={errors.email ? `${formId}-email-error` : undefined}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.email
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="admin@example.com"
            />
            {errors.email && (
              <p id={`${formId}-email-error`} className="mt-1 text-sm text-red-500">
                {errors.email}
              </p>
            )}
          </div>

          {/* Username Field */}
          <div>
            <label
              htmlFor={`${formId}-username`}
              className="block text-sm font-medium text-white"
            >
              Username
            </label>
            <input
              type="text"
              id={`${formId}-username`}
              value={formData.username}
              onChange={handleChange('username')}
              disabled={isSubmitting}
              aria-describedby={errors.username ? `${formId}-username-error` : undefined}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.username
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="admin"
            />
            {errors.username && (
              <p id={`${formId}-username-error`} className="mt-1 text-sm text-red-500">
                {errors.username}
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
              aria-describedby={`${formId}-password-requirements ${errors.password ? `${formId}-password-error` : ''}`}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.password
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="Enter a strong password"
            />
            <p id={`${formId}-password-requirements`} className="mt-1 text-xs text-gray-400">
              Must be at least 8 characters with uppercase, lowercase, and a number
            </p>
            {errors.password && (
              <p id={`${formId}-password-error`} className="mt-1 text-sm text-red-500">
                {errors.password}
              </p>
            )}
          </div>

          {/* Confirm Password Field */}
          <div>
            <label
              htmlFor={`${formId}-confirm-password`}
              className="block text-sm font-medium text-white"
            >
              Confirm Password
            </label>
            <input
              type="password"
              id={`${formId}-confirm-password`}
              value={formData.confirmPassword}
              onChange={handleChange('confirmPassword')}
              disabled={isSubmitting}
              aria-describedby={
                errors.confirmPassword ? `${formId}-confirm-password-error` : undefined
              }
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1E1E1E] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.confirmPassword
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              placeholder="Re-enter your password"
            />
            {errors.confirmPassword && (
              <p id={`${formId}-confirm-password-error`} className="mt-1 text-sm text-red-500">
                {errors.confirmPassword}
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
            leftIcon={!isSubmitting ? <UserPlus className="h-5 w-5" /> : undefined}
          >
            {isSubmitting ? 'Creating...' : 'Create Account'}
          </Button>
        </form>

        {/* Login link - shown when users already exist */}
        {setupRequired === false && (
          <div className="mt-6 rounded-lg border border-[#76B900]/20 bg-[#76B900]/5 px-4 py-4 text-center">
            <p className="mb-3 text-sm text-gray-300">
              An account already exists on this system.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#8ED100] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]"
            >
              <LogIn className="h-4 w-4" />
              Login with existing account
            </Link>
          </div>
        )}

        {/* Setup link to login when setup is still required */}
        {setupRequired === true && (
          <p className="mt-6 text-center text-sm text-gray-400">
            Already have an account?{' '}
            <Link
              to="/login"
              className="text-[#76B900] hover:text-[#8ED100] hover:underline focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]"
            >
              Sign in
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}

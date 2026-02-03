/**
 * Tests for SetupPage component.
 *
 * These tests verify first-time setup flow including:
 * - Registration form rendering
 * - Form validation
 * - Registration submission
 * - Error handling
 * - Redirect behavior
 *
 * Tests follow TDD principles and should initially FAIL until SetupPage is implemented.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { BrowserRouter, useNavigate } from 'react-router-dom';

import { server } from '../../mocks/server';
import { AuthProvider } from '../../contexts/AuthContext';
import SetupPage from './SetupPage';

import type { User } from '../../services/authApi';

// Mock useNavigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: vi.fn(),
  };
});

// ============================================================================
// Test Utilities
// ============================================================================

const mockUser: User = {
  id: 1,
  email: 'admin@example.com',
  full_name: 'Admin User',
  created_at: '2024-01-01T00:00:00Z',
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>{children}</BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('SetupPage', () => {
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useNavigate).mockReturnValue(mockNavigate);

    // Default: setup is required
    server.use(
      http.get('/api/auth/setup-status', () => {
        return HttpResponse.json({ setup_required: true });
      })
    );
  });

  describe('rendering', () => {
    it('renders registration form', async () => {
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    it('displays setup page title', async () => {
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/first time setup/i)).toBeInTheDocument();
      });
    });

    it('displays welcome message', async () => {
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(
          screen.getByText(/create your admin account to get started/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('form validation', () => {
    it('validates required fields', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/full name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });

    it('validates email format', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      const emailInput = screen.getByLabelText(/email/i);
      await user.type(emailInput, 'invalid-email');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
      });
    });

    it('validates password strength', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByLabelText(/^password$/i);
      await user.type(passwordInput, 'weak');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
      });
    });

    it('validates password confirmation matches', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmInput = screen.getByLabelText(/confirm password/i);

      await user.type(passwordInput, 'password123');
      await user.type(confirmInput, 'different123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });
    });

    it('accepts valid form data', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      // Should not show validation errors
      await waitFor(() => {
        expect(screen.queryByText(/email is required/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('form submission', () => {
    it('submits registration data', async () => {
      const user = userEvent.setup();
      let registrationData: any = null;

      server.use(
        http.post('/api/auth/register', async ({ request }) => {
          registrationData = await request.json();
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(registrationData).toEqual({
          email: 'admin@example.com',
          full_name: 'Admin User',
          password: 'password123',
        });
      });
    });

    it('shows loading state during submission', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/register', async () => {
          // Simulate slow response
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      expect(screen.getByRole('button', { name: /creating/i })).toBeInTheDocument();
    });

    it('disables form during submission', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/register', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      expect(submitButton).toBeDisabled();
    });
  });

  describe('error handling', () => {
    it('shows error on registration failure', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.json({ detail: 'Email already exists' }, { status: 400 });
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'existing@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
      });
    });

    it('shows generic error on network failure', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.error();
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to create account/i)).toBeInTheDocument();
      });
    });
  });

  describe('navigation', () => {
    it('redirects to dashboard on success', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.json(mockUser, { status: 201 });
        }),
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/');
      });
    });

    it('redirects away if setup not required', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/');
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible form labels', async () => {
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      const emailInput = screen.getByLabelText(/email/i);
      const nameInput = screen.getByLabelText(/full name/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmInput = screen.getByLabelText(/confirm password/i);

      expect(emailInput).toHaveAttribute('type', 'email');
      expect(passwordInput).toHaveAttribute('type', 'password');
      expect(confirmInput).toHaveAttribute('type', 'password');
    });

    it('associates error messages with inputs', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<SetupPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      await waitFor(() => {
        const emailInput = screen.getByLabelText(/email/i);
        expect(emailInput).toHaveAccessibleDescription();
      });
    });
  });
});

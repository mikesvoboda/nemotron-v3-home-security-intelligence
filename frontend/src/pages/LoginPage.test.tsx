/**
 * Tests for LoginPage component.
 *
 * These tests verify login flow including:
 * - Form rendering
 * - Form validation
 * - Login submission
 * - Error handling
 * - Redirect behavior
 *
 * @see NEM-5322 Phase 4: Frontend Integration
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import LoginPage from './LoginPage';
import { AuthProvider } from '../contexts/AuthContext';
import { server } from '../mocks/server';

import type { User } from '../services/authApi';

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
  username: 'testuser',
  email: 'test@example.com',
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
          <MemoryRouter>{children}</MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('LoginPage', () => {
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useNavigate).mockReturnValue(mockNavigate);

    // Default: setup is not required and user is not authenticated
    server.use(
      http.get('/api/auth/setup-status', () => {
        return HttpResponse.json({ setup_required: false });
      }),
      http.get('/api/auth/me', () => {
        return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
      })
    );
  });

  describe('rendering', () => {
    it('renders login form', async () => {
      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('displays welcome message', async () => {
      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
      });
    });
  });

  describe('form validation', () => {
    it('validates required fields', async () => {
      const user = userEvent.setup();
      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/username is required/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });

  });

  describe('form submission', () => {
    it('submits login credentials', async () => {
      const user = userEvent.setup();
      let loginData: any = null;

      server.use(
        http.post('/api/auth/login', async ({ request }) => {
          loginData = await request.json();
          return HttpResponse.json({ message: 'Login successful' });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/username/i), 'testuser');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(loginData).toEqual({
          username: 'testuser',
          password: 'password123',
        });
      });
    });

    it('shows loading state during submission', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/login', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/username/i), 'testuser');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      expect(screen.getByRole('button', { name: /signing in/i })).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('shows error on invalid credentials', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/username/i), 'testuser');
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });
    });

    it('shows generic error on network failure', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.error();
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/username/i), 'testuser');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to log in/i)).toBeInTheDocument();
      });
    });
  });

  describe('navigation', () => {
    it('redirects to dashboard on success', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ message: 'Login successful' });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/username/i), 'testuser');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
      });
    });

    it('redirects away if already authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
      });
    });

    it('redirects to setup if setup is required', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/setup', { replace: true });
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible form labels', async () => {
      const Wrapper = createWrapper();
      render(<LoginPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(usernameInput).toHaveAttribute('type', 'text');
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });
});

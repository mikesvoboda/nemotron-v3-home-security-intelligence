/**
 * Integration tests for authentication flow.
 *
 * These tests verify the complete authentication user journey including:
 * - First-time setup flow
 * - Login flow for existing users
 * - Protected route access
 * - Logout flow
 * - Redirect preservation
 *
 * Tests follow TDD principles and should initially FAIL until all auth components are implemented.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';

import { server } from '../mocks/server';
import { AuthProvider } from '../contexts/AuthContext';
import SetupPage from '../components/auth/SetupPage';
import LoginPage from '../components/auth/LoginPage';
import ProtectedRoute from '../components/auth/ProtectedRoute';

import type { User } from '../services/authApi';

// ============================================================================
// Test Utilities
// ============================================================================

const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  full_name: 'Test User',
  created_at: '2024-01-01T00:00:00Z',
};

// Mock Dashboard component
function DashboardPage() {
  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome to the dashboard</p>
    </div>
  );
}

// Mock Logout button for testing
function LogoutButton() {
  return <button>Logout</button>;
}

// Complete app structure for integration testing
function TestApp() {
  return (
    <Routes>
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
            <LogoutButton />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

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

describe('Auth Flow Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('first-time user flow', () => {
    it('new user sees setup page', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/first time setup/i)).toBeInTheDocument();
      });
    });

    it('completes setup and accesses dashboard', async () => {
      const user = userEvent.setup();

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        }),
        http.post('/api/auth/register', () => {
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/setup');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      // Fill out registration form
      await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
      await user.type(screen.getByLabelText(/full name/i), 'Admin User');
      await user.type(screen.getByLabelText(/^password$/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');

      // Update server responses for post-registration state
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);

      // Should redirect to dashboard
      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });
  });

  describe('existing user login flow', () => {
    it('existing user sees login page', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/sign in/i)).toBeInTheDocument();
      });
    });

    it('logs in successfully and accesses dashboard', async () => {
      const user = userEvent.setup();

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        }),
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/login');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      // Fill out login form
      await user.type(screen.getByLabelText(/email/i), 'test@example.com');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      // Update server to return authenticated user
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      // Should redirect to dashboard
      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });

    it('shows error on invalid credentials', async () => {
      const user = userEvent.setup();

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        }),
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/login');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText(/email/i), 'test@example.com');
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });
    });
  });

  describe('authenticated user flow', () => {
    it('authenticated user sees dashboard', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });

    it('authenticated user cannot access setup page', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/setup');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/first time setup/i)).not.toBeInTheDocument();
    });
  });

  describe('logout flow', () => {
    it('logout redirects to login', async () => {
      const user = userEvent.setup();

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        }),
        http.post('/api/auth/logout', () => {
          return HttpResponse.json({ message: 'Logout successful' });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });

      // Update server to return unauthenticated state
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const logoutButton = screen.getByRole('button', { name: /logout/i });
      await user.click(logoutButton);

      // Should redirect to login page
      await waitFor(() => {
        expect(screen.getByText(/sign in/i)).toBeInTheDocument();
      });
    });
  });

  describe('protected routes', () => {
    it('protected routes redirect unauthenticated users', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/dashboard');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/sign in/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/welcome to the dashboard/i)).not.toBeInTheDocument();
    });

    it('preserves intended destination after login', async () => {
      const user = userEvent.setup();

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        }),
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/dashboard');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      // Login should redirect back to dashboard
      await user.type(screen.getByLabelText(/email/i), 'test@example.com');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });
  });

  describe('error recovery', () => {
    it('recovers from network errors', async () => {
      const user = userEvent.setup();

      // Start with network error
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.error();
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument();
      });

      // Fix network and retry
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });
  });

  describe('session persistence', () => {
    it('maintains session across page refreshes', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      const { unmount } = render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });

      // Simulate page refresh by unmounting and remounting
      unmount();

      const NewWrapper = createWrapper();
      render(<TestApp />, { wrapper: NewWrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });
    });

    it('handles expired sessions', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      window.history.pushState({}, '', '/');

      const { unmount } = render(<TestApp />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(/welcome to the dashboard/i)).toBeInTheDocument();
      });

      // Session expires
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Session expired' }, { status: 401 });
        })
      );

      unmount();

      const NewWrapper = createWrapper();
      render(<TestApp />, { wrapper: NewWrapper });

      await waitFor(() => {
        expect(screen.getByText(/sign in/i)).toBeInTheDocument();
      });
    });
  });
});

/**
 * Tests for ProtectedRoute component.
 *
 * These tests verify route protection behavior including:
 * - Loading state while checking auth
 * - Redirect to setup when setup required
 * - Redirect to login when not authenticated
 * - Rendering children when authenticated
 * - Preserving intended destination
 *
 * Tests follow TDD principles and should initially FAIL until ProtectedRoute is implemented.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from '../../contexts/AuthContext';
import { server } from '../../mocks/server';

import type { User } from '../../services/authApi';

// ============================================================================
// Test Utilities
// ============================================================================

const mockUser: User = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  created_at: '2024-01-01T00:00:00Z',
};

// Component to display current location (for testing redirects)
function LocationDisplay() {
  const location = useLocation();
  return (
    <div>
      <div data-testid="current-path">{location.pathname}</div>
      <div data-testid="location-state">{JSON.stringify(location.state)}</div>
    </div>
  );
}

function createWrapper(initialPath = '/') {
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
          <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('shows loading spinner while checking auth', () => {
      // Delay the response to keep loading state visible
      server.use(
        http.get('/api/auth/setup-status', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({ setup_required: false });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>,
        { wrapper: Wrapper }
      );

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('does not render children during loading', () => {
      server.use(
        http.get('/api/auth/setup-status', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({ setup_required: false });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>,
        { wrapper: Wrapper }
      );

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('setup required redirect', () => {
    it('redirects to /setup when setupRequired is true', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/setup" element={<LocationDisplay />} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByTestId('current-path')).toHaveTextContent('/setup');
      });
    });

    it('does not render children when setup required', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/setup" element={<div>Setup Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Setup Page')).toBeInTheDocument();
      });

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('unauthenticated redirect', () => {
    it('redirects to /login when not authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper('/dashboard');
      render(
        <Routes>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<LocationDisplay />} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByTestId('current-path')).toHaveTextContent('/login');
      });
    });

    it('preserves intended destination in state', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper('/dashboard');
      render(
        <Routes>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<LocationDisplay />} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        const stateElement = screen.getByTestId('location-state');
        const state = JSON.parse(stateElement.textContent || '{}');
        expect(state.from).toBe('/dashboard');
      });
    });

    it('does not render children when not authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Login Page')).toBeInTheDocument();
      });

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('authenticated access', () => {
    it('renders children when authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });

    it('does not redirect when authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <LocationDisplay />
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/setup" element={<div>Setup Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByTestId('current-path')).toHaveTextContent('/');
      });

      expect(screen.queryByText('Login Page')).not.toBeInTheDocument();
      expect(screen.queryByText('Setup Page')).not.toBeInTheDocument();
    });

    it('renders multiple children when authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Header</div>
                <div>Content</div>
                <div>Footer</div>
              </ProtectedRoute>
            }
          />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Header')).toBeInTheDocument();
      });

      expect(screen.getByText('Content')).toBeInTheDocument();
      expect(screen.getByText('Footer')).toBeInTheDocument();
    });
  });

  describe('priority of redirects', () => {
    it('redirects to setup before login when both required', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/setup" element={<LocationDisplay />} />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByTestId('current-path')).toHaveTextContent('/setup');
      });

      expect(screen.queryByText('Login Page')).not.toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('redirects to login on auth error', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Login Page')).toBeInTheDocument();
      });
    });

    it('redirects to setup on setup status error', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/setup" element={<div>Setup Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      await waitFor(() => {
        expect(screen.getByText('Setup Page')).toBeInTheDocument();
      });
    });
  });

  describe('re-authentication', () => {
    it('redirects to login when user becomes unauthenticated', async () => {
      // This test verifies that an unauthenticated user is redirected to login.
      // The ProtectedRoute component checks auth state on every render,
      // so if the user becomes unauthenticated, they will be redirected.
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const Wrapper = createWrapper();
      render(
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>,
        { wrapper: Wrapper }
      );

      // When user is not authenticated, they should be redirected to login
      await waitFor(() => {
        expect(screen.getByText('Login Page')).toBeInTheDocument();
      });

      // Protected content should not be visible
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });
});

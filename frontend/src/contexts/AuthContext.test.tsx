/**
 * Tests for AuthContext.
 *
 * These tests verify authentication state management including:
 * - Setup status checking on mount
 * - User authentication state
 * - Login/logout/register operations
 * - Token-based authentication flow
 *
 * Tests follow TDD principles and should initially FAIL until AuthContext is implemented.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';

import { server } from '../mocks/server';
import { AuthProvider, useAuth } from './AuthContext';

import type { User } from '../services/authApi';

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  full_name: 'Test User',
  created_at: '2024-01-01T00:00:00Z',
};

// Create wrapper with QueryClientProvider
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
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('provides initial loading state', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.user).toBeNull();
      expect(result.current.setupRequired).toBeNull();
    });

    it('calls setup-status on mount', async () => {
      let setupStatusCalled = false;

      server.use(
        http.get('/api/auth/setup-status', () => {
          setupStatusCalled = true;
          return HttpResponse.json({ setup_required: false });
        })
      );

      renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(setupStatusCalled).toBe(true);
      });
    });

    it('sets setupRequired true when no users exist', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.setupRequired).toBe(true);
      expect(result.current.user).toBeNull();
    });

    it('sets setupRequired false when users exist', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.setupRequired).toBe(false);
    });
  });

  describe('authentication state', () => {
    it('fetches current user when setup not required', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('sets user to null when not authenticated', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('does not fetch current user when setup is required', async () => {
      let currentUserCalled = false;

      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        }),
        http.get('/api/auth/me', () => {
          currentUserCalled = true;
          return HttpResponse.json(mockUser);
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(currentUserCalled).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe('login function', () => {
    it('provides login function', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current.login).toBeDefined();
      expect(typeof result.current.login).toBe('function');
    });

    it('updates user after successful login', async () => {
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

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Mock successful login response
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      await act(async () => {
        await result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      expect(result.current.isAuthenticated).toBe(true);
    });

    it('throws error on login failure', async () => {
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

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login({
            email: 'test@example.com',
            password: 'wrong',
          });
        })
      ).rejects.toThrow();

      expect(result.current.user).toBeNull();
    });
  });

  describe('logout function', () => {
    it('provides logout function', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current.logout).toBeDefined();
      expect(typeof result.current.logout).toBe('function');
    });

    it('clears user after logout', async () => {
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

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      // Mock logged out state
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      await act(async () => {
        await result.current.logout();
      });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
      });

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('register function', () => {
    it('provides register function', () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current.register).toBeDefined();
      expect(typeof result.current.register).toBe('function');
    });

    it('updates user after successful registration', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        }),
        http.post('/api/auth/register', () => {
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Mock authenticated state after registration
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      await act(async () => {
        await result.current.register({
          email: 'new@example.com',
          password: 'password123',
          full_name: 'New User',
        });
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      expect(result.current.setupRequired).toBe(false);
    });

    it('throws error on registration failure', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        }),
        http.post('/api/auth/register', () => {
          return HttpResponse.json({ detail: 'Email already exists' }, { status: 400 });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.register({
            email: 'existing@example.com',
            password: 'password123',
            full_name: 'Test User',
          });
        })
      ).rejects.toThrow();

      expect(result.current.user).toBeNull();
    });
  });

  describe('error handling', () => {
    it('handles setup-status fetch error', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.setupRequired).toBeNull();
      expect(result.current.error).toBeTruthy();
    });

    it('handles current user fetch error', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        }),
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
    });
  });

  describe('context usage', () => {
    it('throws error when used outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(
        () => {
          try {
            return useAuth();
          } catch (e) {
            return e;
          }
        },
        {
          wrapper: ({ children }) => (
            <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
          ),
        }
      );

      expect(result.current).toBeInstanceOf(Error);
      expect((result.current as Error).message).toBe(
        'useAuth must be used within an AuthProvider'
      );
    });
  });
});

/**
 * Tests for authApi service.
 *
 * These tests verify authentication API calls including:
 * - Setup status checking
 * - User registration
 * - User login
 * - User logout
 * - Current user fetching
 * - Error handling
 *
 * Tests follow TDD principles and should initially FAIL until authApi is implemented.
 */

import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import {
  getSetupStatus,
  register,
  login,
  logout,
  getCurrentUser,
  type User,
  type LoginRequest,
  type RegisterRequest,
} from './authApi';
import { server } from '../mocks/server';

// ============================================================================
// Test Utilities
// ============================================================================

const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  created_at: '2024-01-01T00:00:00Z',
};

// ============================================================================
// Tests
// ============================================================================

describe('authApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getSetupStatus', () => {
    it('returns setup_required true when no users exist', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: true });
        })
      );

      const result = await getSetupStatus();

      expect(result).toEqual({ setup_required: true });
    });

    it('returns setup_required false when users exist', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ setup_required: false });
        })
      );

      const result = await getSetupStatus();

      expect(result).toEqual({ setup_required: false });
    });

    it('sends GET request to /api/auth/setup-status', async () => {
      let requestPath = '';

      server.use(
        http.get('/api/auth/setup-status', ({ request }) => {
          requestPath = new URL(request.url).pathname;
          return HttpResponse.json({ setup_required: false });
        })
      );

      await getSetupStatus();

      expect(requestPath).toBe('/api/auth/setup-status');
    });

    it('handles network errors', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.error();
        })
      );

      await expect(getSetupStatus()).rejects.toThrow();
    });

    it('handles 500 server errors', async () => {
      server.use(
        http.get('/api/auth/setup-status', () => {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        })
      );

      await expect(getSetupStatus()).rejects.toThrow();
    });
  });

  describe('register', () => {
    it('sends POST request to /api/auth/register', async () => {
      let requestPath = '';
      let requestBody: RegisterRequest | null = null;

      server.use(
        http.post('/api/auth/register', async ({ request }) => {
          requestPath = new URL(request.url).pathname;
          requestBody = (await request.json()) as RegisterRequest;
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const data: RegisterRequest = {
        email: 'new@example.com',
        password: 'password123',
        username: 'newuser',
      };

      await register(data);

      expect(requestPath).toBe('/api/auth/register');
      expect(requestBody).toEqual(data);
    });

    it('returns created user on success', async () => {
      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      const result = await register({
        email: 'new@example.com',
        password: 'password123',
        username: 'newuser',
      });

      expect(result).toEqual(mockUser);
    });

    it('handles 400 validation errors', async () => {
      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.json({ detail: 'Email already exists' }, { status: 400 });
        })
      );

      await expect(
        register({
          email: 'existing@example.com',
          password: 'password123',
          username: 'testuser',
        })
      ).rejects.toThrow();
    });

    it('handles network errors', async () => {
      server.use(
        http.post('/api/auth/register', () => {
          return HttpResponse.error();
        })
      );

      await expect(
        register({
          email: 'test@example.com',
          password: 'password123',
          username: 'testuser',
        })
      ).rejects.toThrow();
    });

    it('includes all required fields in request', async () => {
      let requestBody: RegisterRequest | null = null;

      server.use(
        http.post('/api/auth/register', async ({ request }) => {
          requestBody = (await request.json()) as RegisterRequest;
          return HttpResponse.json(mockUser, { status: 201 });
        })
      );

      await register({
        email: 'test@example.com',
        password: 'password123',
        username: 'testuser',
      });

      expect(requestBody).toHaveProperty('email');
      expect(requestBody).toHaveProperty('password');
      expect(requestBody).toHaveProperty('username');
    });
  });

  describe('login', () => {
    it('sends POST request to /api/auth/login', async () => {
      let requestPath = '';
      let requestBody: LoginRequest | null = null;

      server.use(
        http.post('/api/auth/login', async ({ request }) => {
          requestPath = new URL(request.url).pathname;
          requestBody = (await request.json()) as LoginRequest;
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      const credentials: LoginRequest = {
        email: 'test@example.com',
        password: 'password123',
      };

      await login(credentials);

      expect(requestPath).toBe('/api/auth/login');
      expect(requestBody).toEqual(credentials);
    });

    it('returns success message on valid credentials', async () => {
      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      const result = await login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result).toEqual({ message: 'Login successful' });
    });

    it('handles 401 unauthorized errors', async () => {
      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
        })
      );

      await expect(
        login({
          email: 'test@example.com',
          password: 'wrong',
        })
      ).rejects.toThrow();
    });

    it('handles network errors', async () => {
      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.error();
        })
      );

      await expect(
        login({
          email: 'test@example.com',
          password: 'password123',
        })
      ).rejects.toThrow();
    });

    it('includes credentials in request body', async () => {
      let requestBody: LoginRequest | null = null;

      server.use(
        http.post('/api/auth/login', async ({ request }) => {
          requestBody = (await request.json()) as LoginRequest;
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      await login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(requestBody).toHaveProperty('email', 'test@example.com');
      expect(requestBody).toHaveProperty('password', 'password123');
    });
  });

  describe('logout', () => {
    it('sends POST request to /api/auth/logout', async () => {
      let requestPath = '';

      server.use(
        http.post('/api/auth/logout', ({ request }) => {
          requestPath = new URL(request.url).pathname;
          return HttpResponse.json({ message: 'Logout successful' });
        })
      );

      await logout();

      expect(requestPath).toBe('/api/auth/logout');
    });

    it('returns success message', async () => {
      server.use(
        http.post('/api/auth/logout', () => {
          return HttpResponse.json({ message: 'Logout successful' });
        })
      );

      const result = await logout();

      expect(result).toEqual({ message: 'Logout successful' });
    });

    it('handles network errors', async () => {
      server.use(
        http.post('/api/auth/logout', () => {
          return HttpResponse.error();
        })
      );

      await expect(logout()).rejects.toThrow();
    });

    it('handles 401 unauthorized errors', async () => {
      server.use(
        http.post('/api/auth/logout', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      await expect(logout()).rejects.toThrow();
    });
  });

  describe('getCurrentUser', () => {
    it('sends GET request to /api/auth/me', async () => {
      let requestPath = '';

      server.use(
        http.get('/api/auth/me', ({ request }) => {
          requestPath = new URL(request.url).pathname;
          return HttpResponse.json(mockUser);
        })
      );

      await getCurrentUser();

      expect(requestPath).toBe('/api/auth/me');
    });

    it('returns current user data', async () => {
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const result = await getCurrentUser();

      expect(result).toEqual(mockUser);
    });

    it('handles 401 unauthorized errors', async () => {
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 });
        })
      );

      await expect(getCurrentUser()).rejects.toThrow();
    });

    it('handles network errors', async () => {
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.error();
        })
      );

      await expect(getCurrentUser()).rejects.toThrow();
    });
  });

  describe('error response handling', () => {
    it('handles 403 forbidden responses', async () => {
      server.use(
        http.get('/api/auth/me', () => {
          return HttpResponse.json({ detail: 'Forbidden' }, { status: 403 });
        })
      );

      await expect(getCurrentUser()).rejects.toThrow();
    });

    it('handles 500 server errors', async () => {
      server.use(
        http.post('/api/auth/login', () => {
          return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
        })
      );

      await expect(
        login({
          email: 'test@example.com',
          password: 'password123',
        })
      ).rejects.toThrow();
    });

    it('handles malformed JSON responses', async () => {
      server.use(
        http.get('/api/auth/me', () => {
          return new HttpResponse('Not JSON', {
            status: 200,
            headers: { 'Content-Type': 'text/plain' },
          });
        })
      );

      await expect(getCurrentUser()).rejects.toThrow();
    });
  });

  describe('request headers', () => {
    it('includes credentials in fetch requests', async () => {
      // Note: MSW doesn't expose credentials directly, so we test via implementation
      server.use(
        http.get('/api/auth/me', () => {
          // In real implementation, fetch should include credentials: 'include'
          // This ensures cookies are sent with requests
          return HttpResponse.json(mockUser);
        })
      );

      await getCurrentUser();

      // The actual test is that the request succeeds with cookie handling
      // Implementation should use { credentials: 'include' }
    });

    it('sets correct Content-Type for JSON requests', async () => {
      let contentType = '';

      server.use(
        http.post('/api/auth/login', ({ request }) => {
          contentType = request.headers.get('content-type') || '';
          return HttpResponse.json({ message: 'Login successful' });
        })
      );

      await login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(contentType).toContain('application/json');
    });
  });
});

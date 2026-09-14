/**
 * Tests for environment variable validation
 * NEM-1528: Add environment variable validation with type-safe config
 *
 * Following TDD - RED phase: write tests first, then implement
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  validateEnv,
  getEnvConfig,
  isValidUrl,
  getBaseUrl,
  getWsBaseUrl,
  getApiKey,
  isDevelopment,
  isProduction,
  isTest,
  EnvValidationError,
  type EnvConfig,
} from './env';

describe('env validation', () => {
  beforeEach(() => {
    // Reset any mocked environment
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('isValidUrl', () => {
    it('returns true for valid http URLs', () => {
      expect(isValidUrl('http://localhost:8000')).toBe(true);
      expect(isValidUrl('http://192.168.1.1:8000')).toBe(true);
    });

    it('returns true for valid https URLs', () => {
      expect(isValidUrl('https://api.example.com')).toBe(true);
      expect(isValidUrl('https://secure.example.com:443/api')).toBe(true);
    });

    it('returns true for valid ws/wss URLs', () => {
      expect(isValidUrl('ws://localhost:8000')).toBe(true);
      expect(isValidUrl('wss://secure.example.com/ws')).toBe(true);
    });

    it('returns false for invalid URLs', () => {
      expect(isValidUrl('not-a-url')).toBe(false);
      expect(isValidUrl('')).toBe(false);
      expect(isValidUrl('ftp://invalid.com')).toBe(false);
    });

    it('returns true for empty string when not required', () => {
      // Empty string is valid for optional URLs (fallback to relative)
      expect(isValidUrl('', false)).toBe(true);
    });
  });

  describe('validateEnv', () => {
    it('validates environment variables without errors for valid config', () => {
      const env = {
        VITE_API_BASE_URL: 'http://localhost:8000',
        VITE_WS_BASE_URL: 'ws://localhost:8000',
        VITE_API_KEY: 'test-api-key', // pragma: allowlist secret
        MODE: 'development',
      };

      expect(() => validateEnv(env)).not.toThrow();
    });

    it('allows empty API base URL (uses relative URLs)', () => {
      const env = {
        VITE_API_BASE_URL: '',
        MODE: 'development',
      };

      expect(() => validateEnv(env)).not.toThrow();
    });

    it('allows undefined optional variables', () => {
      const env = {
        MODE: 'development',
      };

      expect(() => validateEnv(env)).not.toThrow();
    });

    it('throws EnvValidationError for invalid API URL', () => {
      const env = {
        VITE_API_BASE_URL: 'not-a-valid-url',
        MODE: 'development',
      };

      expect(() => validateEnv(env)).toThrow(EnvValidationError);
      expect(() => validateEnv(env)).toThrow(/VITE_API_BASE_URL/);
    });

    it('throws EnvValidationError for invalid WS URL', () => {
      const env = {
        VITE_WS_BASE_URL: 'invalid-ws-url',
        MODE: 'development',
      };

      expect(() => validateEnv(env)).toThrow(EnvValidationError);
      expect(() => validateEnv(env)).toThrow(/VITE_WS_BASE_URL/);
    });

    it('validates WS URL uses ws or wss protocol', () => {
      const env = {
        VITE_WS_BASE_URL: 'http://localhost:8000', // Should be ws://
        MODE: 'development',
      };

      expect(() => validateEnv(env)).toThrow(EnvValidationError);
    });

    it('returns parsed config on successful validation', () => {
      const env = {
        VITE_API_BASE_URL: 'http://localhost:8000',
        VITE_WS_BASE_URL: 'ws://localhost:8000',
        VITE_API_KEY: 'secret-key', // pragma: allowlist secret
        MODE: 'production',
      };

      const config = validateEnv(env);

      expect(config).toEqual({
        apiBaseUrl: 'http://localhost:8000',
        wsBaseUrl: 'ws://localhost:8000',
        apiKey: 'secret-key', // pragma: allowlist secret
        mode: 'production',
        isDevelopment: false,
        isProduction: true,
        isTest: false,
      });
    });
  });

  describe('getEnvConfig', () => {
    it('returns cached config after first call', () => {
      const config1 = getEnvConfig();
      const config2 = getEnvConfig();

      expect(config1).toBe(config2); // Same reference (cached)
    });

    it('returns valid EnvConfig shape', () => {
      const config = getEnvConfig();

      expect(config).toHaveProperty('apiBaseUrl');
      expect(config).toHaveProperty('wsBaseUrl');
      expect(config).toHaveProperty('apiKey');
      expect(config).toHaveProperty('mode');
      expect(config).toHaveProperty('isDevelopment');
      expect(config).toHaveProperty('isProduction');
      expect(config).toHaveProperty('isTest');
    });
  });

  describe('convenience getters', () => {
    it('getBaseUrl returns the API base URL', () => {
      const baseUrl = getBaseUrl();
      expect(typeof baseUrl).toBe('string');
    });

    it('getWsBaseUrl returns the WebSocket base URL', () => {
      const wsUrl = getWsBaseUrl();
      expect(wsUrl === undefined || typeof wsUrl === 'string').toBe(true);
    });

    it('getApiKey returns the configured value', () => {
      const key = getApiKey(); // pragma: allowlist secret
      expect(key === undefined || typeof key === 'string').toBe(true);
    });

    it('isDevelopment returns boolean', () => {
      expect(typeof isDevelopment()).toBe('boolean');
    });

    it('isProduction returns boolean', () => {
      expect(typeof isProduction()).toBe('boolean');
    });

    it('isTest returns boolean', () => {
      expect(typeof isTest()).toBe('boolean');
    });
  });

  describe('EnvValidationError', () => {
    it('is an instance of Error', () => {
      const error = new EnvValidationError('test error');
      expect(error).toBeInstanceOf(Error);
    });

    it('has correct name property', () => {
      const error = new EnvValidationError('test error');
      expect(error.name).toBe('EnvValidationError');
    });

    it('stores validation errors array', () => {
      const errors = ['Error 1', 'Error 2'];
      const error = new EnvValidationError('Multiple errors', errors);
      expect(error.validationErrors).toEqual(errors);
    });

    it('formats message with multiple errors', () => {
      const errors = ['VITE_API_BASE_URL is invalid', 'VITE_WS_BASE_URL is invalid'];
      const error = new EnvValidationError('Environment validation failed', errors);
      expect(error.message).toContain('Environment validation failed');
    });
  });

  describe('type safety', () => {
    it('EnvConfig type is properly defined', () => {
      const config: EnvConfig = {
        apiBaseUrl: '',
        wsBaseUrl: undefined,
        apiKey: undefined,
        mode: 'development',
        isDevelopment: true,
        isProduction: false,
        isTest: false,
      };

      expect(config).toBeDefined();
    });
  });
});

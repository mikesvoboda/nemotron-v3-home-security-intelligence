/**
 * Tests for WebCodecs feature detection utilities
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  canUseVideoDecoder,
  canUseVideoEncoder,
  getWebCodecsStatus,
  isAudioDecoderSupported,
  isAudioEncoderSupported,
  isSecureContext,
  isVideoDecoderSupported,
  isVideoEncoderSupported,
  isWebCodecsSupported,
  logWebCodecsStatus,
  WebCodecsNotAvailableError,
  WEBCODECS_NOT_AVAILABLE_MESSAGE,
  withWebCodecs,
} from './webcodecs';

// Helper type for WebCodecs globals
type WindowWithWebCodecs = Window &
  typeof globalThis & {
    VideoDecoder?: typeof VideoDecoder;
    VideoEncoder?: typeof VideoEncoder;
    AudioDecoder?: typeof AudioDecoder;
    AudioEncoder?: typeof AudioEncoder;
  };

// Cast window once for cleaner code
const windowWithCodecs = window as WindowWithWebCodecs;

describe('webcodecs utilities', () => {
  // Store original window properties
  const originalIsSecureContext = Object.getOwnPropertyDescriptor(window, 'isSecureContext');
  let originalVideoDecoder: typeof VideoDecoder | undefined;
  let originalVideoEncoder: typeof VideoEncoder | undefined;
  let originalAudioDecoder: typeof AudioDecoder | undefined;
  let originalAudioEncoder: typeof AudioEncoder | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    // Store originals
    originalVideoDecoder = windowWithCodecs.VideoDecoder;
    originalVideoEncoder = windowWithCodecs.VideoEncoder;
    originalAudioDecoder = windowWithCodecs.AudioDecoder;
    originalAudioEncoder = windowWithCodecs.AudioEncoder;
  });

  afterEach(() => {
    // Restore original window properties
    if (originalIsSecureContext) {
      Object.defineProperty(window, 'isSecureContext', originalIsSecureContext);
    } else {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
    }

    // Restore WebCodecs APIs (use type assertion to handle undefined assignment)
    (windowWithCodecs as unknown as Record<string, unknown>).VideoDecoder = originalVideoDecoder;
    (windowWithCodecs as unknown as Record<string, unknown>).VideoEncoder = originalVideoEncoder;
    (windowWithCodecs as unknown as Record<string, unknown>).AudioDecoder = originalAudioDecoder;
    (windowWithCodecs as unknown as Record<string, unknown>).AudioEncoder = originalAudioEncoder;
  });

  describe('isSecureContext', () => {
    it('returns true when window.isSecureContext is true', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });

      expect(isSecureContext()).toBe(true);
    });

    it('returns false when window.isSecureContext is false', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isSecureContext()).toBe(false);
    });

    it('returns false when window.isSecureContext is undefined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      expect(isSecureContext()).toBe(false);
    });
  });

  describe('isVideoDecoderSupported', () => {
    it('returns false when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isVideoDecoderSupported()).toBe(false);
    });

    it('returns false when VideoDecoder is not defined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      (windowWithCodecs as unknown as Record<string, unknown>).VideoDecoder = undefined;

      expect(isVideoDecoderSupported()).toBe(false);
    });

    it('returns true when in secure context and VideoDecoder is defined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;

      expect(isVideoDecoderSupported()).toBe(true);
    });
  });

  describe('isVideoEncoderSupported', () => {
    it('returns false when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isVideoEncoderSupported()).toBe(false);
    });

    it('returns true when in secure context and VideoEncoder is defined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoEncoder = vi.fn() as unknown as typeof VideoEncoder;

      expect(isVideoEncoderSupported()).toBe(true);
    });
  });

  describe('isAudioDecoderSupported', () => {
    it('returns false when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isAudioDecoderSupported()).toBe(false);
    });

    it('returns true when in secure context and AudioDecoder is defined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.AudioDecoder = vi.fn() as unknown as typeof AudioDecoder;

      expect(isAudioDecoderSupported()).toBe(true);
    });
  });

  describe('isAudioEncoderSupported', () => {
    it('returns false when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isAudioEncoderSupported()).toBe(false);
    });

    it('returns true when in secure context and AudioEncoder is defined', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.AudioEncoder = vi.fn() as unknown as typeof AudioEncoder;

      expect(isAudioEncoderSupported()).toBe(true);
    });
  });

  describe('isWebCodecsSupported', () => {
    it('returns false when no WebCodecs APIs are available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      expect(isWebCodecsSupported()).toBe(false);
    });

    it('returns true when any WebCodecs API is available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;

      expect(isWebCodecsSupported()).toBe(true);
    });
  });

  describe('getWebCodecsStatus', () => {
    it('returns unavailable status when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      const status = getWebCodecsStatus();

      expect(status.available).toBe(false);
      expect(status.secureContext).toBe(false);
      expect(status.message).toContain('secure context');
      expect(status.recommendation).toContain('HTTPS');
    });

    it('returns available status when WebCodecs is supported', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;
      windowWithCodecs.VideoEncoder = vi.fn() as unknown as typeof VideoEncoder;

      const status = getWebCodecsStatus();

      expect(status.available).toBe(true);
      expect(status.secureContext).toBe(true);
      expect(status.apis.videoDecoder).toBe(true);
      expect(status.apis.videoEncoder).toBe(true);
      expect(status.message).toContain('available');
    });

    it('returns detailed API availability', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;
      (windowWithCodecs as unknown as Record<string, unknown>).VideoEncoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioDecoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioEncoder = undefined;

      const status = getWebCodecsStatus();

      expect(status.apis.videoDecoder).toBe(true);
      expect(status.apis.videoEncoder).toBe(false);
      expect(status.apis.audioDecoder).toBe(false);
      expect(status.apis.audioEncoder).toBe(false);
    });

    it('recommends modern browser when in secure context but APIs not available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      (windowWithCodecs as unknown as Record<string, unknown>).VideoDecoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).VideoEncoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioDecoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioEncoder = undefined;

      const status = getWebCodecsStatus();

      expect(status.available).toBe(false);
      expect(status.secureContext).toBe(true);
      expect(status.recommendation).toContain('modern browser');
    });
  });

  describe('logWebCodecsStatus', () => {
    it('logs warning when WebCodecs is not available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      logWebCodecsStatus();

      expect(warnSpy).toHaveBeenCalled();
      expect(warnSpy.mock.calls[0][0]).toContain('[WebCodecs]');
    });

    it('logs info when WebCodecs is available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;
      const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

      logWebCodecsStatus();

      expect(infoSpy).toHaveBeenCalled();
      expect(infoSpy.mock.calls[0][0]).toContain('[WebCodecs] Available');
    });

    it('uses custom log level when specified', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      logWebCodecsStatus('error');

      expect(errorSpy).toHaveBeenCalled();
    });
  });

  describe('withWebCodecs', () => {
    it('executes callback when WebCodecs is available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;
      const callback = vi.fn().mockReturnValue('success');

      const result = withWebCodecs(callback);

      expect(callback).toHaveBeenCalled();
      expect(result).toBe('success');
    });

    it('executes fallback when WebCodecs is not available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
      const callback = vi.fn();
      const fallback = vi.fn().mockReturnValue('fallback');

      const result = withWebCodecs(callback, fallback);

      expect(callback).not.toHaveBeenCalled();
      expect(fallback).toHaveBeenCalled();
      expect(result).toBe('fallback');
    });

    it('returns undefined when no fallback and WebCodecs not available', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
      const callback = vi.fn();

      const result = withWebCodecs(callback);

      expect(callback).not.toHaveBeenCalled();
      expect(result).toBeUndefined();
    });
  });

  describe('canUseVideoDecoder', () => {
    it('returns same as isVideoDecoderSupported', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoDecoder = vi.fn() as unknown as typeof VideoDecoder;

      expect(canUseVideoDecoder()).toBe(isVideoDecoderSupported());
    });
  });

  describe('canUseVideoEncoder', () => {
    it('returns same as isVideoEncoderSupported', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      windowWithCodecs.VideoEncoder = vi.fn() as unknown as typeof VideoEncoder;

      expect(canUseVideoEncoder()).toBe(isVideoEncoderSupported());
    });
  });

  describe('WEBCODECS_NOT_AVAILABLE_MESSAGE', () => {
    it('contains helpful information', () => {
      expect(WEBCODECS_NOT_AVAILABLE_MESSAGE).toContain('HTTPS');
      expect(WEBCODECS_NOT_AVAILABLE_MESSAGE).toContain('localhost');
      expect(WEBCODECS_NOT_AVAILABLE_MESSAGE).toContain('secure context');
    });
  });

  describe('WebCodecsNotAvailableError', () => {
    it('creates error with appropriate message when not in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      const error = new WebCodecsNotAvailableError();

      expect(error.name).toBe('WebCodecsNotAvailableError');
      expect(error.message).toContain('secure context');
      expect(error.isSecureContext).toBe(false);
      expect(error.recommendation).toContain('HTTPS');
    });

    it('creates error with browser recommendation when in secure context', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
      (windowWithCodecs as unknown as Record<string, unknown>).VideoDecoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).VideoEncoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioDecoder = undefined;
      (windowWithCodecs as unknown as Record<string, unknown>).AudioEncoder = undefined;

      const error = new WebCodecsNotAvailableError();

      expect(error.isSecureContext).toBe(true);
      expect(error.recommendation).toContain('modern browser');
    });

    it('is an instance of Error', () => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });

      const error = new WebCodecsNotAvailableError();

      expect(error).toBeInstanceOf(Error);
    });
  });
});

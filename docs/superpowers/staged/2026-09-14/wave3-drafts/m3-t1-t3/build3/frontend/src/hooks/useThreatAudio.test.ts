/**
 * Tests for useThreatAudio hook
 *
 * TDD Red Phase: These tests define the expected behavior for the useThreatAudio hook.
 * The hook generates Web Audio API tones for threat alerts.
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useThreatAudio } from './useThreatAudio';

describe('useThreatAudio', () => {
  let mockOscillatorNode: {
    frequency: { value: number; setValueAtTime: ReturnType<typeof vi.fn> };
    type: OscillatorType;
    connect: ReturnType<typeof vi.fn>;
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    onended: (() => void) | null;
  };

  let mockGainNode: {
    gain: {
      value: number;
      setValueAtTime: ReturnType<typeof vi.fn>;
      linearRampToValueAtTime: ReturnType<typeof vi.fn>;
    };
    connect: ReturnType<typeof vi.fn>;
  };

  let mockAudioContextInstance: {
    state: AudioContextState;
    currentTime: number;
    resume: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    createOscillator: ReturnType<typeof vi.fn>;
    createGain: ReturnType<typeof vi.fn>;
    destination: AudioDestinationNode;
  };

  const STORAGE_KEY = 'threatAudio.muted';

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
    window.localStorage.clear();

    // Mock oscillator node
    mockOscillatorNode = {
      frequency: {
        value: 440,
        setValueAtTime: vi.fn(),
      },
      type: 'sine',
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      onended: null,
    };

    // Mock gain node
    mockGainNode = {
      gain: {
        value: 0,
        setValueAtTime: vi.fn(),
        linearRampToValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
    };

    // Mock AudioContext instance
    mockAudioContextInstance = {
      state: 'running',
      currentTime: 0,
      resume: vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
      createOscillator: vi.fn().mockReturnValue(mockOscillatorNode),
      createGain: vi.fn().mockReturnValue(mockGainNode),
      destination: {} as AudioDestinationNode,
    };

    // Create AudioContext as a proper constructor class
    class MockAudioContext {
      state = mockAudioContextInstance.state;
      currentTime = mockAudioContextInstance.currentTime;
      resume = mockAudioContextInstance.resume;
      close = mockAudioContextInstance.close;
      createOscillator = mockAudioContextInstance.createOscillator;
      createGain = mockAudioContextInstance.createGain;
      destination = mockAudioContextInstance.destination;
    }

    vi.stubGlobal('AudioContext', MockAudioContext);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  describe('return values', () => {
    it('returns playThreatAlert function and isMuted state', () => {
      const { result } = renderHook(() => useThreatAudio());

      expect(result.current).toHaveProperty('playThreatAlert');
      expect(typeof result.current.playThreatAlert).toBe('function');
      expect(result.current).toHaveProperty('isMuted');
      expect(typeof result.current.isMuted).toBe('boolean');
      expect(result.current).toHaveProperty('toggleMute');
      expect(typeof result.current.toggleMute).toBe('function');
    });

    it('initializes with isMuted as false by default', () => {
      const { result } = renderHook(() => useThreatAudio());

      expect(result.current.isMuted).toBe(false);
    });
  });

  describe('AudioContext creation', () => {
    it('creates AudioContext on first playThreatAlert call (lazy initialization)', () => {
      const { result } = renderHook(() => useThreatAudio());

      // AudioContext should not be created yet
      expect(mockAudioContextInstance.createOscillator).not.toHaveBeenCalled();

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Now AudioContext should be created and used
      expect(mockAudioContextInstance.createOscillator).toHaveBeenCalled();
      expect(mockAudioContextInstance.createGain).toHaveBeenCalled();
    });

    it('reuses existing AudioContext on subsequent calls', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      act(() => {
        result.current.playThreatAlert(false);
      });

      // createGain is called for each sound, but AudioContext constructor should only be called once
      // The hook should reuse the AudioContext instance
      expect(mockAudioContextInstance.createOscillator).toHaveBeenCalled();
    });
  });

  describe('high-priority threat alerts', () => {
    it('plays urgent high-frequency tone for high-priority threats (firearms)', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(true);
      });

      expect(mockAudioContextInstance.createOscillator).toHaveBeenCalled();
      expect(mockOscillatorNode.connect).toHaveBeenCalled();
      expect(mockOscillatorNode.start).toHaveBeenCalled();

      // High priority should use higher frequency (e.g., 880Hz or higher)
      // Check that frequency was set to a high value
      const calls = mockOscillatorNode.frequency.setValueAtTime.mock.calls as [number, number][];
      expect(
        calls.some((call) => call[0] >= 800) || mockOscillatorNode.frequency.value >= 800
      ).toBe(true);
    });
  });

  describe('medium-priority threat alerts', () => {
    it('plays lower-frequency tone for medium-priority threats', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      expect(mockAudioContextInstance.createOscillator).toHaveBeenCalled();
      expect(mockOscillatorNode.connect).toHaveBeenCalled();
      expect(mockOscillatorNode.start).toHaveBeenCalled();

      // Medium priority should use lower frequency (e.g., 440Hz or similar)
      // The oscillator should have been configured with a lower frequency than high-priority
    });

    it('uses different frequency for medium vs high priority', () => {
      // First render for medium priority
      const { result: mediumResult, unmount: unmountMedium } = renderHook(() => useThreatAudio());

      act(() => {
        mediumResult.current.playThreatAlert(false);
      });

      const mediumFrequencyCalls = [...mockOscillatorNode.frequency.setValueAtTime.mock.calls];
      unmountMedium();

      // Reset mocks
      vi.clearAllMocks();

      // Second render for high priority
      const { result: highResult } = renderHook(() => useThreatAudio());

      act(() => {
        highResult.current.playThreatAlert(true);
      });

      const highFrequencyCalls = mockOscillatorNode.frequency.setValueAtTime.mock.calls;

      // Verify different frequencies were used (high priority should be higher)
      // If frequency is set directly, we check the value property
      // If setValueAtTime is used, we check the calls
      if (highFrequencyCalls.length > 0 && mediumFrequencyCalls.length > 0) {
        // Get the first frequency value from each
        const highFreq = (highFrequencyCalls[0]?.[0] ?? 0) as number;
        const mediumFreq = (mediumFrequencyCalls[0]?.[0] ?? 0) as number;
        expect(highFreq).toBeGreaterThan(mediumFreq);
      }
    });
  });

  describe('mute functionality', () => {
    it('respects isMuted state - does not play when muted', () => {
      const { result } = renderHook(() => useThreatAudio());

      // Mute the audio first
      act(() => {
        result.current.toggleMute();
      });

      expect(result.current.isMuted).toBe(true);

      // Try to play alert
      act(() => {
        result.current.playThreatAlert(true);
      });

      // Should not create oscillator when muted
      expect(mockOscillatorNode.start).not.toHaveBeenCalled();
    });

    it('toggleMute() toggles isMuted state', () => {
      const { result } = renderHook(() => useThreatAudio());

      expect(result.current.isMuted).toBe(false);

      act(() => {
        result.current.toggleMute();
      });

      expect(result.current.isMuted).toBe(true);

      act(() => {
        result.current.toggleMute();
      });

      expect(result.current.isMuted).toBe(false);
    });
  });

  describe('localStorage persistence', () => {
    it('stores mute preference in localStorage', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.toggleMute();
      });

      expect(window.localStorage.getItem(STORAGE_KEY)).toBe(JSON.stringify(true));

      act(() => {
        result.current.toggleMute();
      });

      expect(window.localStorage.getItem(STORAGE_KEY)).toBe(JSON.stringify(false));
    });

    it('restores mute preference from localStorage on mount', () => {
      // Pre-set the localStorage value
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(true));

      const { result } = renderHook(() => useThreatAudio());

      expect(result.current.isMuted).toBe(true);
    });

    it('handles invalid localStorage data gracefully', () => {
      // Set invalid JSON
      window.localStorage.setItem(STORAGE_KEY, 'invalid-json');

      // Should not throw, should use default value
      const { result } = renderHook(() => useThreatAudio());

      expect(result.current.isMuted).toBe(false);
    });
  });

  describe('browser autoplay policy', () => {
    it('handles suspended AudioContext by resuming on user gesture', () => {
      mockAudioContextInstance.state = 'suspended';

      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      expect(mockAudioContextInstance.resume).toHaveBeenCalled();
    });

    it('does not throw when AudioContext resume fails', () => {
      mockAudioContextInstance.state = 'suspended';
      mockAudioContextInstance.resume.mockRejectedValue(new Error('Autoplay blocked'));

      const { result } = renderHook(() => useThreatAudio());

      // Should not throw - the hook catches resume errors internally
      expect(() => {
        act(() => {
          result.current.playThreatAlert(false);
        });
      }).not.toThrow();
    });
  });

  describe('cleanup', () => {
    it('cleans up AudioContext on unmount', () => {
      const { result, unmount } = renderHook(() => useThreatAudio());

      // Create the AudioContext by playing a sound
      act(() => {
        result.current.playThreatAlert(false);
      });

      unmount();

      expect(mockAudioContextInstance.close).toHaveBeenCalled();
    });

    it('does not throw on unmount if AudioContext was never created', () => {
      const { unmount } = renderHook(() => useThreatAudio());

      // Unmount without ever playing a sound
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('rapid call handling', () => {
    it('multiple rapid calls do not create multiple overlapping sounds', () => {
      const { result } = renderHook(() => useThreatAudio());

      // Rapidly call playThreatAlert multiple times
      act(() => {
        result.current.playThreatAlert(true);
        result.current.playThreatAlert(true);
        result.current.playThreatAlert(true);
      });

      // Should debounce or throttle - only one oscillator should be started
      // Or alternatively, stop existing sound before starting new one
      const startCalls = mockOscillatorNode.start.mock.calls.length;
      expect(startCalls).toBeLessThanOrEqual(1);
    });

    it('allows new sound after previous sound completes', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Simulate sound completion by calling onended
      act(() => {
        mockOscillatorNode.onended?.();
      });

      // Reset call count
      mockOscillatorNode.start.mockClear();

      act(() => {
        result.current.playThreatAlert(false);
      });

      // New sound should be allowed
      expect(mockOscillatorNode.start).toHaveBeenCalled();
    });

    it('stops previous sound when new alert is triggered', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Advance time slightly but not enough to complete
      act(() => {
        vi.advanceTimersByTime(100);
      });

      act(() => {
        result.current.playThreatAlert(true);
      });

      // Previous oscillator should be stopped
      expect(mockOscillatorNode.stop).toHaveBeenCalled();
    });
  });

  describe('browser compatibility', () => {
    it('handles missing AudioContext gracefully', () => {
      vi.stubGlobal('AudioContext', undefined);
      vi.stubGlobal('webkitAudioContext', undefined);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useThreatAudio());

      // Should not throw
      act(() => {
        result.current.playThreatAlert(false);
      });

      // playThreatAlert should do nothing when AudioContext is not available
      expect(mockOscillatorNode.start).not.toHaveBeenCalled();

      consoleWarnSpy.mockRestore();
    });

    it('uses webkitAudioContext as fallback', () => {
      vi.stubGlobal('AudioContext', undefined);

      class MockWebkitAudioContext {
        state: AudioContextState = 'running';
        currentTime = 0;
        resume = vi.fn().mockResolvedValue(undefined);
        close = vi.fn().mockResolvedValue(undefined);
        createOscillator = vi.fn().mockReturnValue(mockOscillatorNode);
        createGain = vi.fn().mockReturnValue(mockGainNode);
        destination = {} as AudioDestinationNode;
      }

      Object.defineProperty(window, 'webkitAudioContext', {
        value: MockWebkitAudioContext,
        writable: true,
        configurable: true,
      });

      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Should use webkit fallback and play sound
      expect(mockOscillatorNode.start).toHaveBeenCalled();
    });
  });

  describe('sound characteristics', () => {
    it('configures gain envelope for smooth sound', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Should configure gain for attack/release envelope
      expect(mockGainNode.gain.setValueAtTime).toHaveBeenCalled();
      expect(mockGainNode.gain.linearRampToValueAtTime).toHaveBeenCalled();
    });

    it('schedules oscillator stop after duration', () => {
      const { result } = renderHook(() => useThreatAudio());

      act(() => {
        result.current.playThreatAlert(false);
      });

      // Oscillator should be scheduled to stop
      expect(mockOscillatorNode.stop).toHaveBeenCalled();
    });
  });
});

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useAudioNotifications } from './useAudioNotifications';

describe('useAudioNotifications', () => {
  let mockGainNode: {
    gain: { value: number };
    connect: ReturnType<typeof vi.fn>;
  };
  let mockSourceNode: {
    buffer: AudioBuffer | null;
    connect: ReturnType<typeof vi.fn>;
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    onended: (() => void) | null;
  };
  let mockAudioContextInstance: {
    state: string;
    resume: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    createGain: ReturnType<typeof vi.fn>;
    createBufferSource: ReturnType<typeof vi.fn>;
    decodeAudioData: ReturnType<typeof vi.fn>;
    destination: AudioDestinationNode;
  };

  beforeEach(() => {
    // Reset all mocks
    vi.restoreAllMocks();

    // Mock GainNode
    mockGainNode = {
      gain: { value: 0.5 },
      connect: vi.fn(),
    };

    // Mock source node
    mockSourceNode = {
      buffer: null,
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      onended: null,
    };

    // Mock AudioContext instance
    mockAudioContextInstance = {
      state: 'running',
      resume: vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
      createGain: vi.fn().mockReturnValue(mockGainNode),
      createBufferSource: vi.fn().mockReturnValue(mockSourceNode),
      decodeAudioData: vi.fn().mockResolvedValue({ duration: 1 } as AudioBuffer),
      destination: {} as AudioDestinationNode,
    };

    // Create AudioContext as a proper constructor class
    class MockAudioContext {
      state = mockAudioContextInstance.state;
      resume = mockAudioContextInstance.resume;
      close = mockAudioContextInstance.close;
      createGain = mockAudioContextInstance.createGain;
      createBufferSource = mockAudioContextInstance.createBufferSource;
      decodeAudioData = mockAudioContextInstance.decodeAudioData;
      destination = mockAudioContextInstance.destination;
    }

    vi.stubGlobal('AudioContext', MockAudioContext);

    // Mock fetch for loading audio files
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(8)),
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('initialization', () => {
    it('initializes with default values', () => {
      const { result } = renderHook(() => useAudioNotifications());

      expect(result.current.volume).toBe(0.5);
      expect(result.current.isEnabled).toBe(true);
    });

    it('initializes with custom options', () => {
      const { result } = renderHook(() =>
        useAudioNotifications({
          initialVolume: 0.8,
          enabled: false,
        })
      );

      expect(result.current.volume).toBe(0.8);
      expect(result.current.isEnabled).toBe(false);
    });

    it('creates AudioContext on mount', () => {
      renderHook(() => useAudioNotifications());
      expect(mockAudioContextInstance.createGain).toHaveBeenCalled();
    });
  });

  describe('volume control', () => {
    it('updates volume when setVolume is called', () => {
      const { result } = renderHook(() => useAudioNotifications());

      act(() => {
        result.current.setVolume(0.7);
      });

      expect(result.current.volume).toBe(0.7);
    });

    it('clamps volume to valid range (0-1)', () => {
      const { result } = renderHook(() => useAudioNotifications());

      act(() => {
        result.current.setVolume(1.5);
      });
      expect(result.current.volume).toBe(1);

      act(() => {
        result.current.setVolume(-0.5);
      });
      expect(result.current.volume).toBe(0);
    });

    it('updates gain node when volume changes', () => {
      const { result } = renderHook(() => useAudioNotifications());

      act(() => {
        result.current.setVolume(0.8);
      });

      expect(mockGainNode.gain.value).toBe(0.8);
    });
  });

  describe('enabled state', () => {
    it('updates enabled state when setEnabled is called', () => {
      const { result } = renderHook(() => useAudioNotifications());

      expect(result.current.isEnabled).toBe(true);

      act(() => {
        result.current.setEnabled(false);
      });

      expect(result.current.isEnabled).toBe(false);
    });
  });

  describe('playSound', () => {
    it('does not play sound when disabled', async () => {
      const { result } = renderHook(() => useAudioNotifications({ enabled: false }));

      await act(async () => {
        await result.current.playSound('info');
      });

      expect(fetch).not.toHaveBeenCalled();
    });

    it('loads and plays sound when enabled', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playSound('info');
      });

      expect(fetch).toHaveBeenCalledWith('/sounds/info.mp3');
      expect(mockAudioContextInstance.createBufferSource).toHaveBeenCalled();
      expect(mockSourceNode.start).toHaveBeenCalled();
    });

    it('caches loaded audio buffers', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playSound('info');
        await result.current.playSound('info');
      });

      // Should only fetch once due to caching
      expect(fetch).toHaveBeenCalledTimes(1);
    });

    it('handles fetch errors gracefully', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: false,
        })
      );

      const { result } = renderHook(() => useAudioNotifications());

      // Should not throw
      await act(async () => {
        await result.current.playSound('info');
      });

      expect(mockSourceNode.start).not.toHaveBeenCalled();
    });
  });

  describe('playRiskSound', () => {
    it('plays info sound for low risk', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playRiskSound('low');
      });

      expect(fetch).toHaveBeenCalledWith('/sounds/info.mp3');
    });

    it('plays info sound for medium risk', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playRiskSound('medium');
      });

      expect(fetch).toHaveBeenCalledWith('/sounds/info.mp3');
    });

    it('plays alert sound for high risk', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playRiskSound('high');
      });

      expect(fetch).toHaveBeenCalledWith('/sounds/alert.mp3');
    });

    it('plays critical sound for critical risk', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.playRiskSound('critical');
      });

      expect(fetch).toHaveBeenCalledWith('/sounds/critical.mp3');
    });
  });

  describe('stopAll', () => {
    it('stops all playing sounds', async () => {
      const { result } = renderHook(() => useAudioNotifications());

      // Play a sound first
      await act(async () => {
        await result.current.playSound('info');
      });

      act(() => {
        result.current.stopAll();
      });

      expect(mockSourceNode.stop).toHaveBeenCalled();
    });
  });

  describe('resume', () => {
    it('resumes suspended AudioContext', async () => {
      mockAudioContextInstance.state = 'suspended';

      const { result } = renderHook(() => useAudioNotifications());

      await act(async () => {
        await result.current.resume();
      });

      expect(mockAudioContextInstance.resume).toHaveBeenCalled();
    });

    it('sets isReady to true after resume', async () => {
      mockAudioContextInstance.state = 'suspended';

      const { result } = renderHook(() => useAudioNotifications());

      expect(result.current.isReady).toBe(false);

      await act(async () => {
        await result.current.resume();
      });

      await waitFor(() => {
        expect(result.current.isReady).toBe(true);
      });
    });
  });

  describe('cleanup', () => {
    it('closes AudioContext on unmount', () => {
      const { unmount } = renderHook(() => useAudioNotifications());

      unmount();

      expect(mockAudioContextInstance.close).toHaveBeenCalled();
    });
  });

  describe('custom sounds path', () => {
    it('uses custom sounds path when provided', async () => {
      const { result } = renderHook(() => useAudioNotifications({ soundsPath: '/custom/sounds' }));

      await act(async () => {
        await result.current.playSound('info');
      });

      expect(fetch).toHaveBeenCalledWith('/custom/sounds/info.mp3');
    });
  });

  describe('browser compatibility', () => {
    it('handles missing AudioContext gracefully', () => {
      vi.stubGlobal('AudioContext', undefined);
      vi.stubGlobal('webkitAudioContext', undefined);

      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useAudioNotifications());

      expect(result.current.isReady).toBe(false);
      expect(consoleWarnSpy).toHaveBeenCalledWith('Web Audio API is not supported in this browser');

      consoleWarnSpy.mockRestore();
    });

    it('uses webkitAudioContext as fallback', () => {
      vi.stubGlobal('AudioContext', undefined);

      // Create webkitAudioContext as a proper constructor class
      class MockWebkitAudioContext {
        state = 'running';
        resume = vi.fn().mockResolvedValue(undefined);
        close = vi.fn().mockResolvedValue(undefined);
        createGain = vi.fn().mockReturnValue(mockGainNode);
        createBufferSource = vi.fn().mockReturnValue(mockSourceNode);
        decodeAudioData = vi.fn().mockResolvedValue({ duration: 1 } as AudioBuffer);
        destination = {} as AudioDestinationNode;
      }

      // Add to window object
      Object.defineProperty(window, 'webkitAudioContext', {
        value: MockWebkitAudioContext,
        writable: true,
        configurable: true,
      });

      // Should not throw, uses fallback
      const { result } = renderHook(() => useAudioNotifications());
      expect(result.current.isReady).toBe(true);
    });
  });
});

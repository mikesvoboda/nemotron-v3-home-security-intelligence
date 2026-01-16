/**
 * useAudioNotifications hook
 *
 * Manages audio notifications for security alerts using the Web Audio API.
 * Provides volume control and supports different sound types for various
 * alert severities.
 */

import { useCallback, useRef, useEffect, useState } from 'react';

import { type RiskLevel } from '../utils/risk';

export type SoundType = 'info' | 'alert' | 'critical';

export interface UseAudioNotificationsOptions {
  /**
   * Initial volume level (0.0 to 1.0)
   * @default 0.5
   */
  initialVolume?: number;
  /**
   * Whether audio is enabled
   * @default true
   */
  enabled?: boolean;
  /**
   * Base path for audio files
   * @default '/sounds'
   */
  soundsPath?: string;
}

export interface UseAudioNotificationsReturn {
  /**
   * Current volume level (0.0 to 1.0)
   */
  volume: number;
  /**
   * Set the volume level (0.0 to 1.0)
   */
  setVolume: (volume: number) => void;
  /**
   * Whether audio is currently enabled
   */
  isEnabled: boolean;
  /**
   * Enable or disable audio
   */
  setEnabled: (enabled: boolean) => void;
  /**
   * Play a sound by type
   */
  playSound: (type: SoundType) => Promise<void>;
  /**
   * Play a sound based on risk level
   */
  playRiskSound: (riskLevel: RiskLevel) => Promise<void>;
  /**
   * Stop all currently playing sounds
   */
  stopAll: () => void;
  /**
   * Whether the AudioContext is available and ready
   */
  isReady: boolean;
  /**
   * Resume the AudioContext after user interaction
   * (required for browsers that suspend AudioContext until user gesture)
   */
  resume: () => Promise<void>;
}

// Map sound types to file names
const SOUND_FILES: Record<SoundType, string> = {
  info: 'info.mp3',
  alert: 'alert.mp3',
  critical: 'critical.mp3',
};

// Map risk levels to sound types
const RISK_SOUND_MAP: Record<RiskLevel, SoundType> = {
  low: 'info',
  medium: 'info',
  high: 'alert',
  critical: 'critical',
};

/**
 * Hook to manage audio notifications for security alerts.
 *
 * @example
 * ```tsx
 * const { playRiskSound, volume, setVolume, isEnabled, setEnabled } = useAudioNotifications();
 *
 * // Play sound based on event risk
 * useEffect(() => {
 *   if (newEvent && isEnabled) {
 *     playRiskSound(newEvent.riskLevel);
 *   }
 * }, [newEvent, isEnabled, playRiskSound]);
 *
 * // Volume control in settings
 * <input
 *   type="range"
 *   min={0}
 *   max={1}
 *   step={0.1}
 *   value={volume}
 *   onChange={(e) => setVolume(Number(e.target.value))}
 * />
 * ```
 */
export function useAudioNotifications(
  options: UseAudioNotificationsOptions = {}
): UseAudioNotificationsReturn {
  const { initialVolume = 0.5, enabled: initialEnabled = true, soundsPath = '/sounds' } = options;

  const [volume, setVolumeState] = useState(initialVolume);
  const [isEnabled, setIsEnabled] = useState(initialEnabled);
  const [isReady, setIsReady] = useState(false);

  // Refs for Web Audio API
  const audioContextRef = useRef<AudioContext | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const audioBuffersRef = useRef<Map<SoundType, AudioBuffer>>(new Map());
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());

  // Initialize AudioContext
  useEffect(() => {
    // Only initialize in browser environment
    if (typeof window === 'undefined') return;

    // Create AudioContext (with vendor prefix for older browsers)
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) {
      console.warn('Web Audio API is not supported in this browser');
      return;
    }

    const audioContext = new AudioContextClass();
    const gainNode = audioContext.createGain();
    gainNode.connect(audioContext.destination);
    gainNode.gain.value = volume;

    audioContextRef.current = audioContext;
    gainNodeRef.current = gainNode;

    // Mark as ready when context state is running or after resume
    if (audioContext.state === 'running') {
      setIsReady(true);
    }

    // Capture refs for cleanup
    const activeSources = activeSourcesRef.current;
    const audioBuffers = audioBuffersRef.current;

    return () => {
      // Cleanup
      activeSources.forEach((source) => {
        try {
          source.stop();
        } catch {
          // Ignore errors from already stopped sources
        }
      });
      activeSources.clear();
      audioBuffers.clear();
      void audioContext.close();
    };
    // Intentionally only run on mount/unmount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update gain node when volume changes
  useEffect(() => {
    if (gainNodeRef.current) {
      gainNodeRef.current.gain.value = volume;
    }
  }, [volume]);

  /**
   * Load an audio file and cache the buffer
   */
  const loadSound = useCallback(
    async (type: SoundType): Promise<AudioBuffer | null> => {
      const audioContext = audioContextRef.current;
      if (!audioContext) return null;

      // Check cache
      const cached = audioBuffersRef.current.get(type);
      if (cached) return cached;

      try {
        const response = await fetch(`${soundsPath}/${SOUND_FILES[type]}`);
        if (!response.ok) {
          console.warn(`Failed to load sound: ${type}`);
          return null;
        }

        const arrayBuffer = await response.arrayBuffer();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

        // Cache the buffer
        audioBuffersRef.current.set(type, audioBuffer);
        return audioBuffer;
      } catch (error) {
        console.warn(`Failed to decode audio: ${type}`, error);
        return null;
      }
    },
    [soundsPath]
  );

  /**
   * Resume the AudioContext after user interaction
   */
  const resume = useCallback(async (): Promise<void> => {
    const audioContext = audioContextRef.current;
    if (!audioContext) return;

    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }
    setIsReady(true);
  }, []);

  /**
   * Play a sound by type
   */
  const playSound = useCallback(
    async (type: SoundType): Promise<void> => {
      if (!isEnabled) return;

      const audioContext = audioContextRef.current;
      const gainNode = gainNodeRef.current;
      if (!audioContext || !gainNode) return;

      // Resume if suspended
      if (audioContext.state === 'suspended') {
        await resume();
      }

      // Load the sound buffer
      const buffer = await loadSound(type);
      if (!buffer) return;

      // Create and configure source
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(gainNode);

      // Track active source
      activeSourcesRef.current.add(source);

      // Remove from tracking when finished
      source.onended = () => {
        activeSourcesRef.current.delete(source);
      };

      // Play the sound
      source.start(0);
    },
    [isEnabled, loadSound, resume]
  );

  /**
   * Play a sound based on risk level
   */
  const playRiskSound = useCallback(
    async (riskLevel: RiskLevel): Promise<void> => {
      const soundType = RISK_SOUND_MAP[riskLevel];
      await playSound(soundType);
    },
    [playSound]
  );

  /**
   * Stop all currently playing sounds
   */
  const stopAll = useCallback((): void => {
    activeSourcesRef.current.forEach((source) => {
      try {
        source.stop();
      } catch {
        // Ignore errors from already stopped sources
      }
    });
    activeSourcesRef.current.clear();
  }, []);

  /**
   * Set volume with validation
   */
  const setVolume = useCallback((newVolume: number): void => {
    const clampedVolume = Math.max(0, Math.min(1, newVolume));
    setVolumeState(clampedVolume);
  }, []);

  /**
   * Enable or disable audio
   */
  const setEnabled = useCallback((newEnabled: boolean): void => {
    setIsEnabled(newEnabled);
    if (!newEnabled) {
      // Stop all sounds when disabled
      activeSourcesRef.current.forEach((source) => {
        try {
          source.stop();
        } catch {
          // Ignore errors
        }
      });
      activeSourcesRef.current.clear();
    }
  }, []);

  return {
    volume,
    setVolume,
    isEnabled,
    setEnabled,
    playSound,
    playRiskSound,
    stopAll,
    isReady,
    resume,
  };
}

export default useAudioNotifications;

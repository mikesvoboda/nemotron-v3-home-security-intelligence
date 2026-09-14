/**
 * useThreatAudio hook
 *
 * Generates Web Audio API tones for threat alerts with different
 * frequencies based on priority level. Supports mute toggling with
 * localStorage persistence and proper cleanup.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'threatAudio.muted';

// Frequency constants
const HIGH_PRIORITY_FREQUENCY = 880; // Hz (A5) - urgent tone
const MEDIUM_PRIORITY_FREQUENCY = 440; // Hz (A4) - standard alert
const TONE_DURATION = 0.3; // seconds
const GAIN_LEVEL = 0.3;
const GAIN_FADE_TARGET = 0.01;

export interface UseThreatAudioReturn {
  /**
   * Play a threat alert tone
   * @param isHighPriority - If true, plays an urgent high-frequency tone
   */
  playThreatAlert: (isHighPriority: boolean) => void;
  /**
   * Whether audio is currently muted
   */
  isMuted: boolean;
  /**
   * Toggle the muted state and persist to localStorage
   */
  toggleMute: () => void;
}

/**
 * Get AudioContext constructor with vendor prefix fallback
 */
function getAudioContextClass(): typeof AudioContext | undefined {
  if (typeof window === 'undefined') return undefined;

  return (
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  );
}

/**
 * Read muted state from localStorage
 */
function readMutedState(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === null) return false;
    return JSON.parse(stored) === true;
  } catch {
    return false;
  }
}

/**
 * Write muted state to localStorage
 */
function writeMutedState(muted: boolean): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(muted));
  } catch {
    // Ignore localStorage errors
  }
}

/**
 * Hook to generate Web Audio API tones for threat alerts.
 *
 * @example
 * ```tsx
 * const { playThreatAlert, isMuted, toggleMute } = useThreatAudio();
 *
 * // Play alert when threat detected
 * useEffect(() => {
 *   if (threatDetected) {
 *     playThreatAlert(threat.hasFirearm);
 *   }
 * }, [threatDetected, playThreatAlert]);
 *
 * // Mute toggle button
 * <button onClick={toggleMute}>
 *   {isMuted ? 'Unmute' : 'Mute'}
 * </button>
 * ```
 */
export function useThreatAudio(): UseThreatAudioReturn {
  const [isMuted, setIsMuted] = useState<boolean>(() => readMutedState());

  // Refs for Web Audio API
  const audioContextRef = useRef<AudioContext | null>(null);
  const currentOscillatorRef = useRef<OscillatorNode | null>(null);
  const isPlayingRef = useRef<boolean>(false);

  // Cleanup AudioContext on unmount
  useEffect(() => {
    return () => {
      const audioContext = audioContextRef.current;
      if (audioContext) {
        try {
          void audioContext.close();
        } catch {
          // Ignore close errors
        }
      }
    };
  }, []);

  /**
   * Toggle mute state and persist to localStorage
   */
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const newValue = !prev;
      writeMutedState(newValue);
      return newValue;
    });
  }, []);

  /**
   * Play a threat alert tone
   */
  const playThreatAlert = useCallback(
    (isHighPriority: boolean) => {
      // Don't play if muted
      if (isMuted) return;

      // Get AudioContext class
      const AudioContextClass = getAudioContextClass();
      if (!AudioContextClass) {
        console.warn('Web Audio API is not supported in this browser');
        return;
      }

      // If currently playing, stop the previous sound
      if (isPlayingRef.current && currentOscillatorRef.current) {
        try {
          currentOscillatorRef.current.stop();
        } catch {
          // Ignore stop errors (oscillator may already be stopped)
        }
        currentOscillatorRef.current = null;
      }

      // Prevent overlapping sounds - if we just stopped, don't start a new one in the same call
      if (isPlayingRef.current) {
        return;
      }

      // Lazy-create AudioContext on first call
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextClass();
      }

      const audioContext = audioContextRef.current;

      // Resume if suspended (browser autoplay policy)
      if (audioContext.state === 'suspended') {
        audioContext.resume().catch(() => {
          // Ignore resume errors (autoplay blocked)
        });
      }

      // Create oscillator and gain nodes
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      // Configure oscillator
      oscillator.type = 'sine';
      const frequency = isHighPriority ? HIGH_PRIORITY_FREQUENCY : MEDIUM_PRIORITY_FREQUENCY;
      oscillator.frequency.setValueAtTime(frequency, audioContext.currentTime);

      // Configure gain envelope (attack/decay for smooth sound)
      gainNode.gain.setValueAtTime(GAIN_LEVEL, audioContext.currentTime);
      gainNode.gain.linearRampToValueAtTime(
        GAIN_FADE_TARGET,
        audioContext.currentTime + TONE_DURATION
      );

      // Connect nodes
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      // Track current oscillator
      currentOscillatorRef.current = oscillator;
      isPlayingRef.current = true;

      // Handle sound completion
      oscillator.onended = () => {
        isPlayingRef.current = false;
        currentOscillatorRef.current = null;
      };

      // Start and schedule stop
      oscillator.start();
      oscillator.stop(audioContext.currentTime + TONE_DURATION);
    },
    [isMuted]
  );

  return {
    playThreatAlert,
    isMuted,
    toggleMute,
  };
}

export default useThreatAudio;

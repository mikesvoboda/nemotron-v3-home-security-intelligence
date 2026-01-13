import { clsx } from 'clsx';
import {
  Loader2,
  Maximize,
  Minimize,
  Pause,
  Play,
  Volume2,
  VolumeX,
} from 'lucide-react';
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

export interface VideoPlayerProps {
  /** Video source URL */
  src: string;
  /** Optional poster image URL */
  poster?: string;
  /** Whether to autoplay the video */
  autoPlay?: boolean;
  /** Callback when video time updates */
  onTimeUpdate?: (currentTime: number) => void;
  /** Callback when video ends */
  onEnded?: () => void;
  /** Callback when video playback encounters an error */
  onError?: (error: string, mediaErrorCode?: number) => void;
  /** Additional CSS classes */
  className?: string;
}

/** Available playback speed options */
const PLAYBACK_SPEEDS = [0.5, 1, 1.5, 2] as const;

/** Auto-hide timeout for controls (ms) */
const CONTROLS_HIDE_TIMEOUT = 3000;

/** Seek step in seconds for keyboard navigation */
const SEEK_STEP = 5;

/**
 * Formats time in seconds to MM:SS or HH:MM:SS format
 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds) || isNaN(seconds)) {
    return '0:00';
  }

  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * VideoPlayer component provides a custom HTML5 video player with dark theme styling.
 *
 * Features:
 * - Custom controls: play/pause, seek bar, volume, fullscreen, playback speed
 * - Keyboard shortcuts: space=play/pause, arrows=seek, f=fullscreen
 * - Auto-hiding controls after 3 seconds of inactivity
 * - Loading state and error handling
 * - Mobile-friendly touch targets (min 44px)
 * - Buffered progress visualization
 * - NVIDIA green (#76B900) theme accent
 */
const VideoPlayer: React.FC<VideoPlayerProps> = ({
  src,
  poster,
  autoPlay = false,
  onTimeUpdate,
  onEnded,
  onError,
  className,
}) => {
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // State
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [showVolumeSlider, setShowVolumeSlider] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSeeking, setIsSeeking] = useState(false);

  // Reset controls hide timer
  const resetControlsTimer = useCallback(() => {
    setShowControls(true);

    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current);
    }

    if (isPlaying && !isSeeking) {
      controlsTimeoutRef.current = setTimeout(() => {
        setShowControls(false);
        setShowVolumeSlider(false);
      }, CONTROLS_HIDE_TIMEOUT);
    }
  }, [isPlaying, isSeeking]);

  // Play/pause toggle
  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    if (video.paused) {
      const playPromise = video.play();
      // Handle browsers where play() returns undefined
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.error('Failed to play video:', err);
          setError('Failed to play video');
        });
      }
    } else {
      video.pause();
    }
  }, []);

  // Seek to position
  const seekTo = useCallback((time: number) => {
    const video = videoRef.current;
    if (!video) return;

    const clampedTime = Math.max(0, Math.min(time, duration));
    video.currentTime = clampedTime;
    setCurrentTime(clampedTime);
  }, [duration]);

  // Handle seek bar change
  const handleSeekChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    seekTo(newTime);
  }, [seekTo]);

  // Handle seek bar mouse/touch events
  const handleSeekStart = useCallback(() => {
    setIsSeeking(true);
  }, []);

  const handleSeekEnd = useCallback(() => {
    setIsSeeking(false);
    resetControlsTimer();
  }, [resetControlsTimer]);

  // Volume control
  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
    if (newVolume > 0 && isMuted) {
      setIsMuted(false);
      if (videoRef.current) {
        videoRef.current.muted = false;
      }
    }
  }, [isMuted]);

  // Toggle mute
  const toggleMute = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const newMuted = !isMuted;
    setIsMuted(newMuted);
    video.muted = newMuted;
  }, [isMuted]);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    if (!document.fullscreenElement) {
      container.requestFullscreen().catch((err) => {
        console.error('Failed to enter fullscreen:', err);
      });
    } else {
      document.exitFullscreen().catch((err) => {
        console.error('Failed to exit fullscreen:', err);
      });
    }
  }, []);

  // Change playback speed
  const cyclePlaybackSpeed = useCallback(() => {
    const currentIndex = PLAYBACK_SPEEDS.indexOf(playbackSpeed as typeof PLAYBACK_SPEEDS[number]);
    const nextIndex = (currentIndex + 1) % PLAYBACK_SPEEDS.length;
    const newSpeed = PLAYBACK_SPEEDS[nextIndex];
    setPlaybackSpeed(newSpeed);
    if (videoRef.current) {
      videoRef.current.playbackRate = newSpeed;
    }
  }, [playbackSpeed]);

  // Keyboard event handler
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    // Prevent default for handled keys
    const handledKeys = [' ', 'ArrowLeft', 'ArrowRight', 'f', 'F', 'm', 'M'];
    if (handledKeys.includes(e.key)) {
      e.preventDefault();
    }

    switch (e.key) {
      case ' ':
        togglePlay();
        break;
      case 'ArrowLeft':
        seekTo(currentTime - SEEK_STEP);
        break;
      case 'ArrowRight':
        seekTo(currentTime + SEEK_STEP);
        break;
      case 'f':
      case 'F':
        toggleFullscreen();
        break;
      case 'm':
      case 'M':
        toggleMute();
        break;
    }

    resetControlsTimer();
  }, [togglePlay, seekTo, currentTime, toggleFullscreen, toggleMute, resetControlsTimer]);

  // Video event handlers
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      onTimeUpdate?.(video.currentTime);
    };
    const handleDurationChange = () => setDuration(video.duration);
    const handleProgress = () => {
      if (video.buffered.length > 0) {
        const bufferedEnd = video.buffered.end(video.buffered.length - 1);
        setBuffered(bufferedEnd);
      }
    };
    const handleLoadedData = () => {
      setIsLoading(false);
      setError(null);
    };
    const handleWaiting = () => setIsLoading(true);
    const handleCanPlay = () => setIsLoading(false);
    const handleError = () => {
      setIsLoading(false);
      // Extract detailed error information from the video element's MediaError
      const mediaError = video.error;
      let errorMessage = 'Failed to load video';

      if (mediaError) {
        // MediaError codes: https://developer.mozilla.org/en-US/docs/Web/API/MediaError/code
        // Using numeric constants directly for compatibility with jsdom test environment
        // MEDIA_ERR_ABORTED = 1, MEDIA_ERR_NETWORK = 2, MEDIA_ERR_DECODE = 3, MEDIA_ERR_SRC_NOT_SUPPORTED = 4
        switch (mediaError.code) {
          case 1: // MEDIA_ERR_ABORTED
            errorMessage = 'Video playback was aborted';
            break;
          case 2: // MEDIA_ERR_NETWORK
            errorMessage = 'A network error occurred while loading the video';
            break;
          case 3: // MEDIA_ERR_DECODE
            errorMessage = 'Video decoding failed - the format may not be supported';
            break;
          case 4: // MEDIA_ERR_SRC_NOT_SUPPORTED
            errorMessage = 'Video format not supported or file not found';
            break;
          default:
            // Include the browser's error message if available
            errorMessage = mediaError.message || 'Failed to load video';
        }
      }

      setError(errorMessage);
      // Invoke callback with error details for parent component debugging
      onError?.(errorMessage, mediaError?.code);
    };
    const handleEnded = () => {
      setIsPlaying(false);
      onEnded?.();
    };

    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('durationchange', handleDurationChange);
    video.addEventListener('progress', handleProgress);
    video.addEventListener('loadeddata', handleLoadedData);
    video.addEventListener('waiting', handleWaiting);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('error', handleError);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('durationchange', handleDurationChange);
      video.removeEventListener('progress', handleProgress);
      video.removeEventListener('loadeddata', handleLoadedData);
      video.removeEventListener('waiting', handleWaiting);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('error', handleError);
      video.removeEventListener('ended', handleEnded);
    };
  }, [onTimeUpdate, onEnded, onError]);

  // Fullscreen change handler
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Cleanup controls timeout
  useEffect(() => {
    return () => {
      if (controlsTimeoutRef.current) {
        clearTimeout(controlsTimeoutRef.current);
      }
    };
  }, []);

  // Reset state when src changes
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setBuffered(0);
    setIsLoading(true);
    setError(null);
  }, [src]);

  // Calculate progress percentage
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;
  const bufferedPercent = duration > 0 ? (buffered / duration) * 100 : 0;

  /*
   * Video player container uses role="application" because it's a custom widget
   * that handles its own keyboard interactions (space=play, arrows=seek, f=fullscreen).
   * eslint rules for non-interactive elements don't recognize role="application".
   * Disabling no-noninteractive-element-interactions and no-noninteractive-tabindex
   * because role="application" makes this an interactive widget.
   */
  /* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex */
  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative overflow-hidden rounded-lg bg-black',
        'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
        className
      )}
      onMouseMove={resetControlsTimer}
      onMouseEnter={resetControlsTimer}
      onMouseLeave={() => {
        if (isPlaying && !isSeeking) {
          setShowControls(false);
          setShowVolumeSlider(false);
        }
      }}
      onTouchStart={resetControlsTimer}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="application"
      aria-label="Video player"
    >
      {/* eslint-enable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex */}
      {/*
        Video Element - Security camera footage does not require captions.
        This is a valid accessibility exception because:
        1. Security camera recordings are visual-only surveillance footage
        2. There is no meaningful audio content to transcribe
        3. The AI-generated event summaries provide textual descriptions of detected activity
      */}
      {/* eslint-disable-next-line jsx-a11y/media-has-caption -- Security camera footage has no audio to caption */}
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        autoPlay={autoPlay}
        className="h-full w-full object-contain"
        playsInline
        onClick={togglePlay}
        data-testid="video-element"
      />

      {/* Loading Spinner Overlay */}
      {isLoading && !error && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-black/50"
          data-testid="loading-overlay"
        >
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
        </div>
      )}

      {/* Error Overlay */}
      {error && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-black/80"
          data-testid="error-overlay"
        >
          <p className="mb-4 text-lg text-red-500">{error}</p>
          <button
            onClick={() => {
              setError(null);
              setIsLoading(true);
              if (videoRef.current) {
                videoRef.current.load();
              }
            }}
            className="rounded-lg bg-primary px-4 py-2 text-white hover:bg-primary-600"
          >
            Retry
          </button>
        </div>
      )}

      {/* Controls Overlay */}
      <div
        className={clsx(
          'absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent',
          'px-4 pb-4 pt-12 transition-opacity duration-300',
          showControls ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
        data-testid="controls-overlay"
      >
        {/* Progress Bar */}
        <div className="group relative mb-3 h-1 w-full cursor-pointer">
          {/* Buffered Progress */}
          <div
            className="absolute left-0 top-0 h-full rounded-full bg-gray-600"
            style={{ width: `${bufferedPercent}%` }}
            data-testid="buffered-bar"
          />

          {/* Played Progress */}
          <div
            className="absolute left-0 top-0 h-full rounded-full bg-primary"
            style={{ width: `${progressPercent}%` }}
            data-testid="progress-bar"
          />

          {/* Seek Input (invisible, for interaction) */}
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={handleSeekChange}
            onMouseDown={handleSeekStart}
            onMouseUp={handleSeekEnd}
            onTouchStart={handleSeekStart}
            onTouchEnd={handleSeekEnd}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            aria-label="Seek"
            data-testid="seek-slider"
          />

          {/* Hover handle (visible track) */}
          <div className="absolute inset-0 h-1 rounded-full bg-gray-700 group-hover:h-2 group-hover:-translate-y-0.5 transition-all" />
          <div
            className="absolute left-0 top-0 h-1 rounded-full bg-primary group-hover:h-2 group-hover:-translate-y-0.5 transition-all"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Controls Row */}
        <div className="flex items-center justify-between">
          {/* Left Controls */}
          <div className="flex items-center gap-2">
            {/* Play/Pause Button */}
            <button
              onClick={togglePlay}
              className={clsx(
                'flex h-11 w-11 items-center justify-center rounded-lg',
                'text-white hover:bg-white/10 transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-primary'
              )}
              aria-label={isPlaying ? 'Pause' : 'Play'}
              data-testid="play-button"
            >
              {isPlaying ? (
                <Pause className="h-6 w-6" />
              ) : (
                <Play className="h-6 w-6" />
              )}
            </button>

            {/* Volume Control */}
            <div
              className="relative flex items-center"
              onMouseEnter={() => setShowVolumeSlider(true)}
              onMouseLeave={() => setShowVolumeSlider(false)}
              onFocus={() => setShowVolumeSlider(true)}
              onBlur={(e) => {
                // Only hide if focus is leaving the volume control group entirely
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                  setShowVolumeSlider(false);
                }
              }}
              role="group"
              aria-label="Volume controls"
            >
              <button
                onClick={toggleMute}
                className={clsx(
                  'flex h-11 w-11 items-center justify-center rounded-lg',
                  'text-white hover:bg-white/10 transition-colors',
                  'focus:outline-none focus:ring-2 focus:ring-primary'
                )}
                aria-label={isMuted ? 'Unmute' : 'Mute'}
                data-testid="mute-button"
              >
                {isMuted || volume === 0 ? (
                  <VolumeX className="h-5 w-5" />
                ) : (
                  <Volume2 className="h-5 w-5" />
                )}
              </button>

              {/* Volume Slider */}
              <div
                className={clsx(
                  'absolute bottom-full left-1/2 mb-2 -translate-x-1/2 transform',
                  'flex h-24 w-8 items-center justify-center rounded-lg bg-gray-900 p-2',
                  'transition-opacity duration-200',
                  showVolumeSlider ? 'opacity-100' : 'pointer-events-none opacity-0'
                )}
                data-testid="volume-slider-container"
              >
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={isMuted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className={clsx(
                    'h-20 w-2 cursor-pointer appearance-none rounded-full bg-gray-700',
                    '[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4',
                    '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full',
                    '[&::-webkit-slider-thumb]:bg-primary',
                    'rotate-[-90deg]'
                  )}
                  style={{
                    writingMode: 'vertical-lr' as const,
                    direction: 'rtl',
                  }}
                  aria-label="Volume"
                  data-testid="volume-slider"
                />
              </div>
            </div>

            {/* Time Display */}
            <div className="ml-2 text-sm text-white" data-testid="time-display">
              <span>{formatTime(currentTime)}</span>
              <span className="mx-1 text-gray-400">/</span>
              <span className="text-gray-400">{formatTime(duration)}</span>
            </div>
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-2">
            {/* Playback Speed */}
            <button
              onClick={cyclePlaybackSpeed}
              className={clsx(
                'flex h-11 min-w-[44px] items-center justify-center rounded-lg px-2',
                'text-sm font-medium text-white hover:bg-white/10 transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-primary'
              )}
              aria-label={`Playback speed: ${playbackSpeed}x`}
              data-testid="speed-button"
            >
              {playbackSpeed}x
            </button>

            {/* Fullscreen Toggle */}
            <button
              onClick={toggleFullscreen}
              className={clsx(
                'flex h-11 w-11 items-center justify-center rounded-lg',
                'text-white hover:bg-white/10 transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-primary'
              )}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              data-testid="fullscreen-button"
            >
              {isFullscreen ? (
                <Minimize className="h-5 w-5" />
              ) : (
                <Maximize className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Play button overlay (shown when paused) */}
      {!isPlaying && !isLoading && !error && (
        <button
          onClick={togglePlay}
          className={clsx(
            'absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 transform',
            'flex h-16 w-16 items-center justify-center rounded-full',
            'bg-primary/80 text-white hover:bg-primary transition-colors',
            'focus:outline-none focus:ring-4 focus:ring-primary/50'
          )}
          aria-label="Play"
          data-testid="center-play-button"
        >
          <Play className="h-8 w-8 translate-x-0.5" />
        </button>
      )}
    </div>
  );
};

export default VideoPlayer;

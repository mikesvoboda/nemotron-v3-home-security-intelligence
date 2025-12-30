# Video Components Directory

## Purpose

Contains components for video playback with custom controls. Provides a dark-themed HTML5 video player with NVIDIA green accent styling for viewing security camera recordings.

## Files

| File                   | Purpose                   |
| ---------------------- | ------------------------- |
| `VideoPlayer.tsx`      | Custom HTML5 video player |
| `VideoPlayer.test.tsx` | Comprehensive test suite  |
| `index.ts`             | Barrel export             |

## Key Components

### VideoPlayer.tsx

**Purpose:** Custom HTML5 video player with dark theme styling and full playback controls

**Props Interface:**

```typescript
interface VideoPlayerProps {
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
  /** Additional CSS classes */
  className?: string;
}
```

**Key Features:**

- Custom dark-themed controls overlay
- Play/pause with center play button
- Seek bar with buffered progress visualization
- Volume slider (vertical, appears on hover)
- Playback speed control (0.5x, 1x, 1.5x, 2x)
- Fullscreen toggle
- Auto-hiding controls (3 second timeout)
- Loading spinner overlay
- Error state with retry button

**Keyboard Shortcuts:**

| Key         | Action            |
| ----------- | ----------------- |
| Space       | Play/Pause        |
| Left Arrow  | Seek -5 seconds   |
| Right Arrow | Seek +5 seconds   |
| F           | Toggle fullscreen |
| M           | Toggle mute       |

**Constants:**

```typescript
const PLAYBACK_SPEEDS = [0.5, 1, 1.5, 2];
const CONTROLS_HIDE_TIMEOUT = 3000; // ms
const SEEK_STEP = 5; // seconds
```

**State Management:**

```typescript
const [isPlaying, setIsPlaying] = useState(false);
const [currentTime, setCurrentTime] = useState(0);
const [duration, setDuration] = useState(0);
const [buffered, setBuffered] = useState(0);
const [volume, setVolume] = useState(1);
const [isMuted, setIsMuted] = useState(false);
const [isFullscreen, setIsFullscreen] = useState(false);
const [showControls, setShowControls] = useState(true);
const [playbackSpeed, setPlaybackSpeed] = useState(1);
const [isLoading, setIsLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

**Usage:**

```tsx
import { VideoPlayer } from '../video';

<VideoPlayer
  src="/api/events/123/video"
  poster="/api/events/123/thumbnail"
  onTimeUpdate={(time) => console.log('Current time:', time)}
  onEnded={() => console.log('Video ended')}
/>;
```

### index.ts

**Barrel exports:**

```typescript
export { default as VideoPlayer } from './VideoPlayer';
export type { VideoPlayerProps } from './VideoPlayer';
```

## Important Patterns

### Auto-Hiding Controls

Controls hide after 3 seconds of inactivity when playing:

```typescript
const resetControlsTimer = useCallback(() => {
  setShowControls(true);
  if (controlsTimeoutRef.current) {
    clearTimeout(controlsTimeoutRef.current);
  }
  if (isPlaying && !isSeeking) {
    controlsTimeoutRef.current = setTimeout(() => {
      setShowControls(false);
    }, CONTROLS_HIDE_TIMEOUT);
  }
}, [isPlaying, isSeeking]);
```

### Video Event Handling

Comprehensive event listener setup:

```typescript
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
```

### Time Formatting

Formats seconds to MM:SS or HH:MM:SS:

```typescript
function formatTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
```

### Fullscreen API

Uses native Fullscreen API:

```typescript
const toggleFullscreen = useCallback(() => {
  if (!document.fullscreenElement) {
    containerRef.current?.requestFullscreen();
  } else {
    document.exitFullscreen();
  }
}, []);
```

## Styling Conventions

### Container

- Background: bg-black
- Rounded corners: rounded-lg
- Focus ring: focus:ring-primary

### Controls Overlay

- Gradient: from-black/90 via-black/50 to-transparent
- Padding: px-4 pb-4 pt-12
- Transition: opacity duration-300

### Progress Bar

- Track: bg-gray-700
- Buffered: bg-gray-600
- Progress: bg-primary (#76B900)
- Hover: h-1 -> h-2 (grows on hover)

### Buttons

- Size: h-11 w-11 (44px touch target)
- Background: hover:bg-white/10
- Focus: focus:ring-2 focus:ring-primary

### Volume Slider

- Vertical orientation (rotated)
- Appears above mute button on hover
- Background: bg-gray-900

## Testing

### VideoPlayer.test.tsx

Comprehensive tests cover:

- Initial render with poster
- Play/pause functionality
- Seek bar interaction
- Volume control
- Mute toggle
- Playback speed cycling
- Fullscreen toggle
- Keyboard shortcuts
- Loading state
- Error state with retry
- Time display formatting
- Controls auto-hide
- Source change reset

## Dependencies

- `clsx` - Conditional class composition
- `lucide-react` - Icons (Loader2, Maximize, Minimize, Pause, Play, Volume2, VolumeX)
- `react` - useState, useEffect, useCallback, useRef

## Accessibility

- Container: `role="application"`, `aria-label="Video player"`, `tabIndex={0}`
- Play button: `aria-label="Play"` or `aria-label="Pause"`
- Mute button: `aria-label="Mute"` or `aria-label="Unmute"`
- Seek slider: `aria-label="Seek"`
- Volume slider: `aria-label="Volume"`
- Fullscreen: `aria-label="Enter fullscreen"` or `aria-label="Exit fullscreen"`
- Speed button: `aria-label="Playback speed: Xx"`

## Entry Points

**Start here:** `VideoPlayer.tsx` - Understand the complete video player implementation

## Future Enhancements

- HLS streaming support (hls.js integration)
- Picture-in-picture mode
- Quality selection for adaptive streaming
- Chapter markers for event segments
- Frame-by-frame navigation
- Download button
- Thumbnail preview on seek bar hover
- Multiple audio track support
- Subtitles/captions support (if needed)
- Video annotation overlay

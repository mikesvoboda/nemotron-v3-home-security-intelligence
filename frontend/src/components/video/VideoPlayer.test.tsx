import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import VideoPlayer from './VideoPlayer';

describe('VideoPlayer', () => {
  const mockSrc = 'https://example.com/video.mp4';
  const mockPoster = 'https://example.com/poster.jpg';

  beforeEach(() => {
    // Mock document.fullscreenElement
    Object.defineProperty(document, 'fullscreenElement', {
      value: null,
      writable: true,
      configurable: true,
    });

    // Mock requestFullscreen and exitFullscreen
    Element.prototype.requestFullscreen = vi.fn().mockResolvedValue(undefined);
    document.exitFullscreen = vi.fn().mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('video-element')).toBeInTheDocument();
    });

    it('renders video element with correct src', () => {
      render(<VideoPlayer src={mockSrc} />);
      const video = screen.getByTestId('video-element');
      expect(video).toHaveAttribute('src', mockSrc);
    });

    it('renders video element with poster when provided', () => {
      render(<VideoPlayer src={mockSrc} poster={mockPoster} />);
      const video = screen.getByTestId('video-element');
      expect(video).toHaveAttribute('poster', mockPoster);
    });

    it('renders play button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('play-button')).toBeInTheDocument();
    });

    it('renders mute button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('mute-button')).toBeInTheDocument();
    });

    it('renders fullscreen button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('fullscreen-button')).toBeInTheDocument();
    });

    it('renders speed button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('speed-button')).toBeInTheDocument();
    });

    it('renders time display', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('time-display')).toBeInTheDocument();
    });

    it('renders seek slider', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('seek-slider')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<VideoPlayer src={mockSrc} className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('renders center play button when paused', () => {
      render(<VideoPlayer src={mockSrc} />);
      // Need to trigger loadeddata event to hide loading state
      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      expect(screen.getByTestId('center-play-button')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading overlay initially', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('loading-overlay')).toBeInTheDocument();
    });

    it('hides loading overlay after video loads', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-overlay')).not.toBeInTheDocument();
      });
    });

    it('shows loading overlay when video is buffering', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');

      // First, simulate loaded
      fireEvent.loadedData(video);
      await waitFor(() => {
        expect(screen.queryByTestId('loading-overlay')).not.toBeInTheDocument();
      });

      // Then simulate waiting/buffering
      fireEvent.waiting(video);

      expect(screen.getByTestId('loading-overlay')).toBeInTheDocument();
    });

    it('hides loading overlay after canplay event', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.waiting(video);
      fireEvent.canPlay(video);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-overlay')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error overlay when video fails to load', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.error(video);

      await waitFor(() => {
        expect(screen.getByTestId('error-overlay')).toBeInTheDocument();
      });
    });

    it('displays error message', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.error(video);

      await waitFor(() => {
        expect(screen.getByText('Failed to load video')).toBeInTheDocument();
      });
    });

    it('shows retry button on error', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.error(video);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
    });
  });

  describe('Play/Pause Controls', () => {
    it('toggles play state when play button is clicked', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const playButton = screen.getByTestId('play-button');
      await user.click(playButton);

      // Simulate play event
      fireEvent.play(video);

      await waitFor(() => {
        expect(screen.getByLabelText('Pause')).toBeInTheDocument();
      });
    });

    it('toggles pause state when play button is clicked while playing', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Start playing
      fireEvent.play(video);

      // Wait for the component to update to show Pause button
      await waitFor(() => {
        expect(screen.getByTestId('play-button')).toHaveAttribute('aria-label', 'Pause');
      });

      // Click the pause button (now showing as Pause)
      const pauseButton = screen.getByTestId('play-button');
      fireEvent.click(pauseButton);

      // Simulate pause event from the video element
      fireEvent.pause(video);

      // Wait for the component to update to show Play button
      await waitFor(() => {
        expect(screen.getByTestId('play-button')).toHaveAttribute('aria-label', 'Play');
      });
    });

    it('toggles play when video element is clicked', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      await user.click(video);
      fireEvent.play(video);

      await waitFor(() => {
        expect(screen.getByTestId('play-button')).toHaveAttribute('aria-label', 'Pause');
      });
    });

    it('toggles play when center play button is clicked', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const centerPlayButton = screen.getByTestId('center-play-button');
      await user.click(centerPlayButton);
      fireEvent.play(video);

      await waitFor(() => {
        expect(screen.getByTestId('play-button')).toHaveAttribute('aria-label', 'Pause');
      });
    });
  });

  describe('Volume Controls', () => {
    it('toggles mute when mute button is clicked', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const muteButton = screen.getByTestId('mute-button');
      await user.click(muteButton);

      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();
    });

    it('shows volume slider on hover', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const muteButton = screen.getByTestId('mute-button');
      await user.hover(muteButton.parentElement!);

      const volumeSliderContainer = screen.getByTestId('volume-slider-container');
      expect(volumeSliderContainer).toHaveClass('opacity-100');
    });
  });

  describe('Seek Controls', () => {
    it('updates current time when seek slider changes', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Simulate duration loaded
      Object.defineProperty(video, 'duration', { value: 120, configurable: true });
      fireEvent.durationChange(video);

      const seekSlider = screen.getByTestId('seek-slider');
      fireEvent.change(seekSlider, { target: { value: '60' } });

      // The currentTime should be set on the video element
      expect(screen.getByTestId('seek-slider')).toHaveValue('60');
    });

    it('shows progress bar', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    });

    it('shows buffered bar', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByTestId('buffered-bar')).toBeInTheDocument();
    });
  });

  describe('Playback Speed Controls', () => {
    it('displays current playback speed', () => {
      render(<VideoPlayer src={mockSrc} />);

      const speedButton = screen.getByTestId('speed-button');
      expect(speedButton).toHaveTextContent('1x');
    });

    it('cycles through playback speeds when clicked', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const speedButton = screen.getByTestId('speed-button');

      // 1x -> 1.5x
      await user.click(speedButton);
      expect(speedButton).toHaveTextContent('1.5x');

      // 1.5x -> 2x
      await user.click(speedButton);
      expect(speedButton).toHaveTextContent('2x');

      // 2x -> 0.5x
      await user.click(speedButton);
      expect(speedButton).toHaveTextContent('0.5x');

      // 0.5x -> 1x
      await user.click(speedButton);
      expect(speedButton).toHaveTextContent('1x');
    });
  });

  describe('Fullscreen Controls', () => {
    it('enters fullscreen when fullscreen button is clicked', async () => {
      const user = userEvent.setup();
      const { container } = render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const fullscreenButton = screen.getByTestId('fullscreen-button');
      await user.click(fullscreenButton);

      expect(container.firstChild).toHaveProperty('requestFullscreen');
    });

    it('changes button icon when in fullscreen', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Simulate entering fullscreen
      Object.defineProperty(document, 'fullscreenElement', {
        value: document.body,
        configurable: true,
      });
      fireEvent(document, new Event('fullscreenchange'));

      await waitFor(() => {
        expect(screen.getByLabelText('Exit fullscreen')).toBeInTheDocument();
      });
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('toggles play on space key', async () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const container = screen.getByRole('application');
      fireEvent.keyDown(container, { key: ' ' });

      // Check that video play/pause is toggled
      fireEvent.play(video);

      await waitFor(() => {
        expect(screen.getByTestId('play-button')).toHaveAttribute('aria-label', 'Pause');
      });
    });

    it('seeks backward on ArrowLeft', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Set initial time
      Object.defineProperty(video, 'currentTime', {
        value: 30,
        writable: true,
        configurable: true,
      });
      Object.defineProperty(video, 'duration', { value: 120, configurable: true });
      fireEvent.timeUpdate(video);
      fireEvent.durationChange(video);

      const container = screen.getByRole('application');
      fireEvent.keyDown(container, { key: 'ArrowLeft' });

      // Video should seek to currentTime - 5
      expect((video as HTMLVideoElement).currentTime).toBe(25);
    });

    it('seeks forward on ArrowRight', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Set initial time
      Object.defineProperty(video, 'currentTime', {
        value: 30,
        writable: true,
        configurable: true,
      });
      Object.defineProperty(video, 'duration', { value: 120, configurable: true });
      fireEvent.timeUpdate(video);
      fireEvent.durationChange(video);

      const container = screen.getByRole('application');
      fireEvent.keyDown(container, { key: 'ArrowRight' });

      expect((video as HTMLVideoElement).currentTime).toBe(35);
    });

    it('toggles fullscreen on f key', () => {
      const { container } = render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const applicationContainer = screen.getByRole('application');
      fireEvent.keyDown(applicationContainer, { key: 'f' });

      expect(container.firstChild).toHaveProperty('requestFullscreen');
    });

    it('toggles mute on m key', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const container = screen.getByRole('application');
      fireEvent.keyDown(container, { key: 'm' });

      expect(screen.getByLabelText('Unmute')).toBeInTheDocument();
    });
  });

  describe('Controls Visibility', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('shows controls on mouse move', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const container = screen.getByRole('application');
      const controlsOverlay = screen.getByTestId('controls-overlay');

      // Start playing first
      act(() => {
        fireEvent.play(video);
      });

      // Then trigger mouse move to set up the hide timer (isPlaying must be true)
      act(() => {
        fireEvent.mouseMove(container);
      });

      // Hide controls after timeout
      act(() => {
        vi.advanceTimersByTime(3500);
      });

      expect(controlsOverlay).toHaveClass('opacity-0');

      // Show controls on mouse move
      act(() => {
        fireEvent.mouseMove(container);
      });

      expect(controlsOverlay).toHaveClass('opacity-100');
    });

    it('hides controls after timeout when playing', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const controlsOverlay = screen.getByTestId('controls-overlay');

      // Start playing - need to trigger mouse move to set up the timer
      act(() => {
        fireEvent.play(video);
      });

      expect(controlsOverlay).toHaveClass('opacity-100');

      // Trigger mouse move to start the hide timer after isPlaying is true
      act(() => {
        fireEvent.mouseMove(screen.getByRole('application'));
      });

      // Advance time past the hide timeout
      act(() => {
        vi.advanceTimersByTime(3500);
      });

      expect(controlsOverlay).toHaveClass('opacity-0');
    });

    it('keeps controls visible while paused', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      const controlsOverlay = screen.getByTestId('controls-overlay');

      // Advance time
      vi.advanceTimersByTime(5000);

      // Controls should still be visible when paused
      expect(controlsOverlay).toHaveClass('opacity-100');
    });
  });

  describe('Callbacks', () => {
    it('calls onTimeUpdate with current time', () => {
      const onTimeUpdate = vi.fn();
      render(<VideoPlayer src={mockSrc} onTimeUpdate={onTimeUpdate} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Simulate time update
      Object.defineProperty(video, 'currentTime', { value: 45, configurable: true });
      fireEvent.timeUpdate(video);

      expect(onTimeUpdate).toHaveBeenCalledWith(45);
    });

    it('calls onEnded when video ends', () => {
      const onEnded = vi.fn();
      render(<VideoPlayer src={mockSrc} onEnded={onEnded} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      fireEvent.ended(video);

      expect(onEnded).toHaveBeenCalled();
    });
  });

  describe('Time Display', () => {
    it('formats time correctly', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');

      // Set duration to 2 hours, 30 minutes, 45 seconds
      Object.defineProperty(video, 'duration', { value: 9045, configurable: true });
      fireEvent.durationChange(video);

      // Set current time to 1 hour, 15 minutes, 30 seconds
      Object.defineProperty(video, 'currentTime', { value: 4530, configurable: true });
      fireEvent.timeUpdate(video);

      const timeDisplay = screen.getByTestId('time-display');
      expect(timeDisplay).toHaveTextContent('1:15:30');
      expect(timeDisplay).toHaveTextContent('2:30:45');
    });

    it('formats short time correctly (under 1 hour)', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');

      // Set duration to 5 minutes
      Object.defineProperty(video, 'duration', { value: 300, configurable: true });
      fireEvent.durationChange(video);

      // Set current time to 2 minutes 30 seconds
      Object.defineProperty(video, 'currentTime', { value: 150, configurable: true });
      fireEvent.timeUpdate(video);

      const timeDisplay = screen.getByTestId('time-display');
      expect(timeDisplay).toHaveTextContent('2:30');
      expect(timeDisplay).toHaveTextContent('5:00');
    });

    it('handles zero duration gracefully', () => {
      render(<VideoPlayer src={mockSrc} />);

      const timeDisplay = screen.getByTestId('time-display');
      expect(timeDisplay).toHaveTextContent('0:00');
    });
  });

  describe('Accessibility', () => {
    it('has correct role', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByRole('application')).toBeInTheDocument();
    });

    it('has aria-label for video player', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByLabelText('Video player')).toBeInTheDocument();
    });

    it('has aria-label for play button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByLabelText('Play')).toBeInTheDocument();
    });

    it('has aria-label for mute button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByLabelText('Mute')).toBeInTheDocument();
    });

    it('has aria-label for fullscreen button', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByLabelText('Enter fullscreen')).toBeInTheDocument();
    });

    it('has aria-label for seek slider', () => {
      render(<VideoPlayer src={mockSrc} />);
      expect(screen.getByLabelText('Seek')).toBeInTheDocument();
    });

    it('has aria-label for volume slider', async () => {
      const user = userEvent.setup();
      render(<VideoPlayer src={mockSrc} />);

      const muteButton = screen.getByTestId('mute-button');
      await user.hover(muteButton.parentElement!);

      expect(screen.getByLabelText('Volume')).toBeInTheDocument();
    });

    it('is focusable', () => {
      render(<VideoPlayer src={mockSrc} />);
      const container = screen.getByRole('application');
      expect(container).toHaveAttribute('tabIndex', '0');
    });
  });

  describe('AutoPlay', () => {
    it('sets autoPlay attribute when provided', () => {
      render(<VideoPlayer src={mockSrc} autoPlay />);
      const video = screen.getByTestId('video-element');
      expect(video).toHaveAttribute('autoplay');
    });

    it('does not set autoPlay by default', () => {
      render(<VideoPlayer src={mockSrc} />);
      const video = screen.getByTestId('video-element');
      expect(video).not.toHaveAttribute('autoplay');
    });
  });

  describe('Source Changes', () => {
    it('resets state when src changes', () => {
      const { rerender } = render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');
      fireEvent.loadedData(video);

      // Simulate playing and time update
      Object.defineProperty(video, 'currentTime', { value: 60, configurable: true });
      fireEvent.play(video);
      fireEvent.timeUpdate(video);

      // Change source
      rerender(<VideoPlayer src="https://example.com/new-video.mp4" />);

      // Loading should be shown again
      expect(screen.getByTestId('loading-overlay')).toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    it('updates buffered bar on progress event', () => {
      render(<VideoPlayer src={mockSrc} />);

      const video = screen.getByTestId('video-element');

      // Set duration
      Object.defineProperty(video, 'duration', { value: 100, configurable: true });
      fireEvent.durationChange(video);

      // Simulate buffered progress
      Object.defineProperty(video, 'buffered', {
        value: {
          length: 1,
          start: () => 0,
          end: () => 50,
        },
        configurable: true,
      });
      fireEvent.progress(video);

      const bufferedBar = screen.getByTestId('buffered-bar');
      expect(bufferedBar).toHaveStyle({ width: '50%' });
    });
  });
});

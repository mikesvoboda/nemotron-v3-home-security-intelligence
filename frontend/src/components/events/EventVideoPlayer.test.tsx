import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import EventVideoPlayer from './EventVideoPlayer';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEventClipInfo: vi.fn(),
    generateEventClip: vi.fn(),
    getEventClipUrl: vi.fn((url: string) => url),
  };
});

describe('EventVideoPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('displays loading indicator while fetching clip info', () => {
      // Mock a pending promise that never resolves
      vi.mocked(api.fetchEventClipInfo).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<EventVideoPlayer eventId={123} />);

      expect(screen.getByTestId('clip-loading')).toBeInTheDocument();
      expect(screen.getByText(/loading clip info/i)).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error when clip info fetch fails', async () => {
      vi.mocked(api.fetchEventClipInfo).mockRejectedValue(new Error('Network error'));

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('clip-error')).toBeInTheDocument();
      });

      expect(screen.getByText(/failed to load clip info/i)).toBeInTheDocument();
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  describe('no clip available', () => {
    beforeEach(() => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: false,
        clip_url: null,
        duration_seconds: null,
        generated_at: null,
        file_size_bytes: null,
      });
    });

    it('displays generate button when no clip exists', async () => {
      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('clip-unavailable')).toBeInTheDocument();
      });

      expect(screen.getByText(/no video clip available/i)).toBeInTheDocument();
      expect(screen.getByTestId('generate-clip-button')).toBeInTheDocument();
    });

    it('calls generateEventClip when generate button is clicked', async () => {
      const user = userEvent.setup();

      vi.mocked(api.generateEventClip).mockResolvedValue({
        event_id: 123,
        status: 'completed',
        clip_url: '/api/media/clips/123_clip.mp4',
        generated_at: '2024-01-15T10:30:00Z',
        message: 'Clip generated successfully',
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('generate-clip-button')).toBeInTheDocument();
      });

      const generateButton = screen.getByTestId('generate-clip-button');
      await user.click(generateButton);

      await waitFor(() => {
        expect(api.generateEventClip).toHaveBeenCalledWith(123);
      });
    });

    it('shows loading state while generating clip', async () => {
      const user = userEvent.setup();
      let resolveGenerate: (value: api.ClipGenerateResponse) => void;
      const generatePromise = new Promise<api.ClipGenerateResponse>((resolve) => {
        resolveGenerate = resolve;
      });

      vi.mocked(api.generateEventClip).mockReturnValue(generatePromise);

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('generate-clip-button')).toBeInTheDocument();
      });

      const generateButton = screen.getByTestId('generate-clip-button');
      await user.click(generateButton);

      // Should show generating state
      await waitFor(() => {
        expect(screen.getByText(/generating/i)).toBeInTheDocument();
      });
      expect(generateButton).toBeDisabled();

      // Resolve the promise
      resolveGenerate!({
        event_id: 123,
        status: 'completed',
        clip_url: '/api/media/clips/123_clip.mp4',
        generated_at: '2024-01-15T10:30:00Z',
        message: 'Clip generated successfully',
      });

      // Should eventually show video player
      await waitFor(() => {
        expect(screen.getByTestId('clip-available')).toBeInTheDocument();
      });
    });

    it('displays error message when clip generation fails', async () => {
      const user = userEvent.setup();

      vi.mocked(api.generateEventClip).mockResolvedValue({
        event_id: 123,
        status: 'failed',
        clip_url: null,
        generated_at: null,
        message: 'No detection images available',
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('generate-clip-button')).toBeInTheDocument();
      });

      const generateButton = screen.getByTestId('generate-clip-button');
      await user.click(generateButton);

      await waitFor(() => {
        expect(screen.getByText(/no detection images available/i)).toBeInTheDocument();
      });
    });

    it('handles network error during clip generation', async () => {
      const user = userEvent.setup();

      vi.mocked(api.generateEventClip).mockRejectedValue(new Error('Network timeout'));

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('generate-clip-button')).toBeInTheDocument();
      });

      const generateButton = screen.getByTestId('generate-clip-button');
      await user.click(generateButton);

      await waitFor(() => {
        expect(screen.getByText(/network timeout/i)).toBeInTheDocument();
      });
    });
  });

  describe('clip available', () => {
    const mockClipInfo = {
      event_id: 123,
      clip_available: true,
      clip_url: '/api/media/clips/123_clip.mp4',
      duration_seconds: 45,
      generated_at: '2024-01-15T10:30:00Z',
      file_size_bytes: 5242880, // 5 MB
    };

    beforeEach(() => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue(mockClipInfo);
    });

    it('displays video player when clip is available', async () => {
      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('clip-available')).toBeInTheDocument();
      });

      expect(screen.getByTestId('video-player')).toBeInTheDocument();
    });

    it('displays clip metadata', async () => {
      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/duration:/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/45s/)).toBeInTheDocument();
      expect(screen.getByText(/5.0 MB/)).toBeInTheDocument();
      expect(screen.getByText(/generated:/i)).toBeInTheDocument();
    });

    it('renders download button', async () => {
      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('download-clip-button')).toBeInTheDocument();
      });
    });

    it('triggers download when download button is clicked', async () => {
      const user = userEvent.setup();

      // Create a real link element but spy on its click method
      const originalCreateElement = document.createElement.bind(document);
      let capturedLink: HTMLAnchorElement | null = null;

      const createElementSpy = vi
        .spyOn(document, 'createElement')
        .mockImplementation((tagName: string) => {
          if (tagName === 'a') {
            const link = originalCreateElement('a');
            capturedLink = link;
            vi.spyOn(link, 'click').mockImplementation(() => {});
            return link;
          }
          return originalCreateElement(tagName);
        });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('download-clip-button')).toBeInTheDocument();
      });

      const downloadButton = screen.getByTestId('download-clip-button');
      await user.click(downloadButton);

      expect(createElementSpy).toHaveBeenCalledWith('a');
      expect(capturedLink).toBeTruthy();
      // Type assertion after truthiness check - double assertion needed due to TypeScript strictness
      const link = capturedLink as unknown as HTMLAnchorElement;
      expect(link.href).toContain('/api/media/clips/123_clip.mp4');
      expect(link.download).toBe('event_123_clip.mp4');
      // eslint-disable-next-line @typescript-eslint/unbound-method -- testing spied method was called
      expect(link.click).toHaveBeenCalled();

      createElementSpy.mockRestore();
    });

    it('passes correct src to video element', async () => {
      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        const video = screen.getByTestId('video-player');
        expect((video as HTMLVideoElement).src).toContain('/api/media/clips/123_clip.mp4');
      });
    });

    it('handles missing optional metadata gracefully', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: true,
        clip_url: '/api/media/clips/123_clip.mp4',
        duration_seconds: null,
        generated_at: null,
        file_size_bytes: null,
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('clip-available')).toBeInTheDocument();
      });

      // Should still render video player without metadata
      expect(screen.getByTestId('video-player')).toBeInTheDocument();
      expect(screen.queryByText(/duration:/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/size:/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/generated:/i)).not.toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className to root element', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: false,
        clip_url: null,
        duration_seconds: null,
        generated_at: null,
        file_size_bytes: null,
      });

      const { container } = render(<EventVideoPlayer eventId={123} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('clip-unavailable')).toBeInTheDocument();
      });

      const rootElement = container.firstChild as HTMLElement;
      expect(rootElement.className).toContain('custom-class');
    });
  });

  describe('accessibility', () => {
    it('has aria-label on generate button', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: false,
        clip_url: null,
        duration_seconds: null,
        generated_at: null,
        file_size_bytes: null,
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        const generateButton = screen.getByTestId('generate-clip-button');
        expect(generateButton).toHaveAttribute('aria-label', 'Generate video clip');
      });
    });

    it('has aria-label on download button', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: true,
        clip_url: '/api/media/clips/123_clip.mp4',
        duration_seconds: 45,
        generated_at: '2024-01-15T10:30:00Z',
        file_size_bytes: 5242880,
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        const downloadButton = screen.getByTestId('download-clip-button');
        expect(downloadButton).toHaveAttribute('aria-label', 'Download clip');
      });
    });

    it('video element has controls attribute', async () => {
      vi.mocked(api.fetchEventClipInfo).mockResolvedValue({
        event_id: 123,
        clip_available: true,
        clip_url: '/api/media/clips/123_clip.mp4',
        duration_seconds: 45,
        generated_at: '2024-01-15T10:30:00Z',
        file_size_bytes: 5242880,
      });

      render(<EventVideoPlayer eventId={123} />);

      await waitFor(() => {
        const video = screen.getByTestId('video-player');
        expect((video as HTMLVideoElement).controls).toBe(true);
      });
    });
  });
});

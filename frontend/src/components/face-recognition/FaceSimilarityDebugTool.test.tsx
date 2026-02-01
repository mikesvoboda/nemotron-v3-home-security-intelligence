/**
 * Tests for FaceSimilarityDebugTool component
 *
 * @see NEM-4955 - Face Similarity Comparison Debug Tool
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// eslint-disable-next-line import/order
import FaceSimilarityDebugTool from './FaceSimilarityDebugTool';

// Mock the useFaceRecognitionApi hook
vi.mock('../../hooks/useFaceRecognitionApi', () => ({
  useCompareFaceSimilarity: vi.fn(() => ({
    mutate: vi.fn(),
    data: undefined,
    isPending: false,
    reset: vi.fn(),
  })),
}));

// Import the mocked module
import { useCompareFaceSimilarity } from '../../hooks/useFaceRecognitionApi';

const mockMutate = vi.fn();
const mockReset = vi.fn();

// Helper to create a test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// Helper to create a mock file
function createMockFile(name: string, type: string = 'image/jpeg'): File {
  const blob = new Blob(['mock image data'], { type });
  return new File([blob], name, { type });
}

describe('FaceSimilarityDebugTool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useCompareFaceSimilarity as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
      data: undefined,
      isPending: false,
      reset: mockReset,
    });
  });

  it('renders the component with initial state', () => {
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByTestId('face-similarity-debug-tool')).toBeInTheDocument();
    expect(screen.getByText('Face Similarity Comparison')).toBeInTheDocument();
    expect(screen.getByText('Debug Tool')).toBeInTheDocument();
    expect(screen.getByText('Face 1')).toBeInTheDocument();
    expect(screen.getByText('Face 2')).toBeInTheDocument();
    expect(screen.getByText('Match Threshold')).toBeInTheDocument();
    expect(screen.getByText('Compare Faces')).toBeInTheDocument();
    expect(screen.getByText('Reset')).toBeInTheDocument();
  });

  it('displays info banner about CLIP embeddings', () => {
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByText(/CLIP embeddings \(768-dim\)/)).toBeInTheDocument();
    expect(screen.getByText(/ArcFace embeddings \(512-dim\)/)).toBeInTheDocument();
  });

  it('disables compare button when no images are uploaded', () => {
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    const compareButton = screen.getByRole('button', { name: /compare faces/i });
    expect(compareButton).toBeDisabled();
  });

  it('allows uploading images via file input', async () => {
    const user = userEvent.setup();
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    const file1 = createMockFile('face1.jpg');
    const file2 = createMockFile('face2.jpg');

    // Find file inputs (hidden)
    const fileInputs = document.querySelectorAll('input[type="file"]');
    expect(fileInputs).toHaveLength(2);

    // Upload first image
    await user.upload(fileInputs[0] as HTMLInputElement, file1);

    // Upload second image
    await user.upload(fileInputs[1] as HTMLInputElement, file2);

    // Compare button should now be enabled
    await waitFor(() => {
      const compareButton = screen.getByRole('button', { name: /compare faces/i });
      expect(compareButton).not.toBeDisabled();
    });
  });

  it('adjusts threshold slider', () => {
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    const slider = screen.getByRole('slider');
    expect(slider).toHaveValue('70'); // Default 0.7 = 70%

    // Change slider value
    fireEvent.change(slider, { target: { value: '85' } });
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('calls mutate when compare button is clicked', async () => {
    const user = userEvent.setup();
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    const file1 = createMockFile('face1.jpg');
    const file2 = createMockFile('face2.jpg');

    // Upload images
    const fileInputs = document.querySelectorAll('input[type="file"]');
    await user.upload(fileInputs[0] as HTMLInputElement, file1);
    await user.upload(fileInputs[1] as HTMLInputElement, file2);

    // Click compare button
    await waitFor(() => {
      const compareButton = screen.getByRole('button', { name: /compare faces/i });
      expect(compareButton).not.toBeDisabled();
    });

    const compareButton = screen.getByRole('button', { name: /compare faces/i });
    await user.click(compareButton);

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        image1: expect.any(File),
        image2: expect.any(File),
        threshold: 0.7,
      })
    );
  });

  it('displays match result when comparison succeeds', () => {
    (useCompareFaceSimilarity as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
      data: {
        similarity_score: 0.85,
        is_match: true,
        threshold: 0.7,
        embedding_dimension: 768,
        processing_time_ms: 245,
        error: null,
      },
      isPending: false,
      reset: mockReset,
    });

    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByTestId('comparison-result')).toBeInTheDocument();
    expect(screen.getByText('Match Found')).toBeInTheDocument();
    expect(screen.getByText('These appear to be the same person')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument();
    expect(screen.getByText('768')).toBeInTheDocument();
    expect(screen.getByText('245ms')).toBeInTheDocument();
  });

  it('displays no match result when comparison does not match', () => {
    (useCompareFaceSimilarity as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
      data: {
        similarity_score: 0.45,
        is_match: false,
        threshold: 0.7,
        embedding_dimension: 768,
        processing_time_ms: 180,
        error: null,
      },
      isPending: false,
      reset: mockReset,
    });

    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByTestId('comparison-result')).toBeInTheDocument();
    expect(screen.getByText('No Match')).toBeInTheDocument();
    expect(screen.getByText('These appear to be different people')).toBeInTheDocument();
    expect(screen.getByText('45.0%')).toBeInTheDocument();
  });

  it('displays error message when comparison fails', () => {
    (useCompareFaceSimilarity as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
      data: {
        similarity_score: 0.0,
        is_match: false,
        threshold: 0.7,
        embedding_dimension: 768,
        processing_time_ms: 50,
        error: 'CLIP service unavailable',
      },
      isPending: false,
      reset: mockReset,
    });

    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('CLIP service unavailable')).toBeInTheDocument();
  });

  it('shows loading state during comparison', () => {
    (useCompareFaceSimilarity as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
      data: undefined,
      isPending: true,
      reset: mockReset,
    });

    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    expect(screen.getByText('Comparing...')).toBeInTheDocument();
  });

  it('resets state when reset button is clicked', async () => {
    const user = userEvent.setup();
    render(<FaceSimilarityDebugTool />, { wrapper: createWrapper() });

    const resetButton = screen.getByRole('button', { name: /reset/i });
    await user.click(resetButton);

    expect(mockReset).toHaveBeenCalled();
  });

  it('accepts className prop', () => {
    render(<FaceSimilarityDebugTool className="custom-class" />, { wrapper: createWrapper() });

    expect(screen.getByTestId('face-similarity-debug-tool')).toHaveClass('custom-class');
  });
});

/**
 * FaceSimilarityDebugTool - Debug tool for comparing face similarity
 *
 * Allows developers to upload two face images and compare their similarity
 * using CLIP embeddings. Shows the cosine similarity score and match decision.
 *
 * Features:
 * - Two image upload areas with drag-and-drop support
 * - Image preview for both uploads
 * - Configurable similarity threshold
 * - Visual comparison display side-by-side
 * - Clear match/no-match indication with color coding
 * - Processing time display
 *
 * Note: This tool uses CLIP embeddings (768-dim) for visual similarity,
 * not ArcFace embeddings (512-dim) used in production face recognition.
 *
 * @module components/face-recognition/FaceSimilarityDebugTool
 * @see NEM-4955 - Face Similarity Comparison Debug Tool
 */

import { clsx } from 'clsx';
import {
  Upload,
  X,
  Check,
  AlertTriangle,
  Loader2,
  Image as ImageIcon,
  RefreshCw,
  Info,
} from 'lucide-react';
import { memo, useState, useCallback, useRef } from 'react';

import {
  useCompareFaceSimilarity,
  type FaceSimilarityCompareResponse,
} from '../../hooks/useFaceRecognitionApi';

// ============================================================================
// Types
// ============================================================================

export interface FaceSimilarityDebugToolProps {
  /** Additional CSS classes */
  className?: string;
}

interface ImageUploadState {
  file: File | null;
  previewUrl: string | null;
}

// ============================================================================
// Image Upload Component
// ============================================================================

interface ImageUploadAreaProps {
  label: string;
  state: ImageUploadState;
  onChange: (file: File | null) => void;
  disabled?: boolean;
  testId?: string;
}

const ImageUploadArea = memo(function ImageUploadArea({
  label,
  state,
  onChange,
  disabled = false,
  testId,
}: ImageUploadAreaProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleClick = useCallback(() => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  }, [disabled]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0] || null;
      onChange(file);
      // Reset input so same file can be selected again
      e.target.value = '';
    },
    [onChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;

      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith('image/')) {
        onChange(file);
      }
    },
    [disabled, onChange]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (!disabled) {
        setIsDragOver(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange(null);
    },
    [onChange]
  );

  return (
    <div className="flex flex-col" data-testid={testId}>
      <label className="mb-2 text-sm font-medium text-gray-300">{label}</label>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleClick();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={clsx(
          'relative flex h-48 w-48 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-all',
          isDragOver && !disabled && 'border-[#76B900] bg-[#76B900]/10',
          !isDragOver && !state.previewUrl && 'border-gray-600 hover:border-gray-500',
          state.previewUrl && 'border-transparent',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        {state.previewUrl ? (
          <>
            <img
              src={state.previewUrl}
              alt={label}
              className="h-full w-full rounded-lg object-cover"
            />
            <button
              onClick={handleClear}
              disabled={disabled}
              className="absolute -right-2 -top-2 rounded-full bg-gray-700 p-1 hover:bg-gray-600"
              aria-label="Remove image"
            >
              <X className="h-4 w-4 text-white" />
            </button>
          </>
        ) : (
          <>
            <Upload className="mb-2 h-8 w-8 text-gray-500" />
            <span className="text-center text-xs text-gray-500">
              Drop image or click to upload
            </span>
          </>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/jpg"
        onChange={handleFileChange}
        className="hidden"
        disabled={disabled}
      />
      {state.file && (
        <span className="mt-1 truncate text-xs text-gray-500" title={state.file.name}>
          {state.file.name}
        </span>
      )}
    </div>
  );
});

// ============================================================================
// Result Display Component
// ============================================================================

interface ComparisonResultProps {
  result: FaceSimilarityCompareResponse;
}

const ComparisonResult = memo(function ComparisonResult({ result }: ComparisonResultProps) {
  if (result.error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="h-5 w-5" />
          <span className="font-medium">Error</span>
        </div>
        <p className="mt-2 text-sm text-red-300">{result.error}</p>
      </div>
    );
  }

  const similarityPercent = (result.similarity_score * 100).toFixed(1);
  const thresholdPercent = (result.threshold * 100).toFixed(0);

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        result.is_match
          ? 'border-green-500/20 bg-green-500/10'
          : 'border-yellow-500/20 bg-yellow-500/10'
      )}
      data-testid="comparison-result"
    >
      {/* Match Status Header */}
      <div className="flex items-center gap-3">
        {result.is_match ? (
          <>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20">
              <Check className="h-6 w-6 text-green-400" />
            </div>
            <div>
              <span className="text-lg font-semibold text-green-400">Match Found</span>
              <p className="text-sm text-green-300">These appear to be the same person</p>
            </div>
          </>
        ) : (
          <>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/20">
              <X className="h-6 w-6 text-yellow-400" />
            </div>
            <div>
              <span className="text-lg font-semibold text-yellow-400">No Match</span>
              <p className="text-sm text-yellow-300">These appear to be different people</p>
            </div>
          </>
        )}
      </div>

      {/* Similarity Score Bar */}
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-sm">
          <span className="text-gray-400">Similarity Score</span>
          <span
            className={clsx('font-mono font-medium', result.is_match ? 'text-green-400' : 'text-yellow-400')}
          >
            {similarityPercent}%
          </span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-700">
          <div
            className={clsx(
              'h-full rounded-full transition-all duration-500',
              result.is_match ? 'bg-green-500' : 'bg-yellow-500'
            )}
            style={{ width: `${result.similarity_score * 100}%` }}
          />
          {/* Threshold marker */}
          <div
            className="relative h-0.5 bg-white/50"
            style={{ marginTop: '-6px', marginLeft: `${result.threshold * 100}%`, width: '2px' }}
            title={`Threshold: ${thresholdPercent}%`}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-gray-500">
          <span>0%</span>
          <span>Threshold: {thresholdPercent}%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Stats */}
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-500">Embedding Dimension</span>
          <p className="font-mono text-gray-300">{result.embedding_dimension}</p>
        </div>
        <div>
          <span className="text-gray-500">Processing Time</span>
          <p className="font-mono text-gray-300">{result.processing_time_ms}ms</p>
        </div>
      </div>
    </div>
  );
});

// ============================================================================
// Main Component
// ============================================================================

export const FaceSimilarityDebugTool = memo(function FaceSimilarityDebugTool({
  className,
}: FaceSimilarityDebugToolProps) {
  const [image1, setImage1] = useState<ImageUploadState>({ file: null, previewUrl: null });
  const [image2, setImage2] = useState<ImageUploadState>({ file: null, previewUrl: null });
  const [threshold, setThreshold] = useState(0.7);

  const { mutate: compare, data: result, isPending, reset } = useCompareFaceSimilarity();

  const handleImage1Change = useCallback((file: File | null) => {
    if (image1.previewUrl) {
      URL.revokeObjectURL(image1.previewUrl);
    }
    setImage1({
      file,
      previewUrl: file ? URL.createObjectURL(file) : null,
    });
    // Reset result when images change
    reset();
  }, [image1.previewUrl, reset]);

  const handleImage2Change = useCallback((file: File | null) => {
    if (image2.previewUrl) {
      URL.revokeObjectURL(image2.previewUrl);
    }
    setImage2({
      file,
      previewUrl: file ? URL.createObjectURL(file) : null,
    });
    // Reset result when images change
    reset();
  }, [image2.previewUrl, reset]);

  const handleCompare = useCallback(() => {
    if (image1.file && image2.file) {
      compare({ image1: image1.file, image2: image2.file, threshold });
    }
  }, [compare, image1.file, image2.file, threshold]);

  const handleReset = useCallback(() => {
    if (image1.previewUrl) URL.revokeObjectURL(image1.previewUrl);
    if (image2.previewUrl) URL.revokeObjectURL(image2.previewUrl);
    setImage1({ file: null, previewUrl: null });
    setImage2({ file: null, previewUrl: null });
    setThreshold(0.7);
    reset();
  }, [image1.previewUrl, image2.previewUrl, reset]);

  const canCompare = image1.file && image2.file && !isPending;

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-[#1A1A1A] p-6', className)}
      data-testid="face-similarity-debug-tool"
    >
      {/* Header */}
      <div className="mb-6">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
          <ImageIcon className="h-5 w-5 text-[#76B900]" />
          Face Similarity Comparison
          <span className="rounded bg-[#76B900]/20 px-2 py-0.5 text-xs font-normal text-[#76B900]">
            Debug Tool
          </span>
        </h3>
        <p className="mt-1 text-sm text-gray-400">
          Upload two face images to compare their visual similarity using CLIP embeddings.
        </p>
      </div>

      {/* Info Banner */}
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-blue-500/20 bg-blue-500/10 p-3">
        <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-400" />
        <div className="text-sm text-blue-300">
          <p>
            This debug tool uses <strong>CLIP embeddings (768-dim)</strong> for visual similarity
            comparison. Production face recognition uses ArcFace embeddings (512-dim) which are
            optimized specifically for face recognition tasks.
          </p>
        </div>
      </div>

      {/* Image Upload Areas */}
      <div className="mb-6 flex flex-wrap items-center justify-center gap-8">
        <ImageUploadArea
          label="Face 1"
          state={image1}
          onChange={handleImage1Change}
          disabled={isPending}
          testId="image1-upload"
        />

        <div className="flex flex-col items-center">
          <span className="text-2xl text-gray-600">vs</span>
        </div>

        <ImageUploadArea
          label="Face 2"
          state={image2}
          onChange={handleImage2Change}
          disabled={isPending}
          testId="image2-upload"
        />
      </div>

      {/* Threshold Slider */}
      <div className="mb-6">
        <label className="mb-2 flex items-center justify-between text-sm font-medium text-gray-300">
          <span>Match Threshold</span>
          <span className="font-mono text-[#76B900]">{(threshold * 100).toFixed(0)}%</span>
        </label>
        <input
          type="range"
          min="0"
          max="100"
          value={threshold * 100}
          onChange={(e) => setThreshold(parseInt(e.target.value, 10) / 100)}
          disabled={isPending}
          className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-[#76B900]"
        />
        <div className="mt-1 flex justify-between text-xs text-gray-500">
          <span>Lenient (0.50)</span>
          <span>Strict (0.90)</span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mb-6 flex gap-3">
        <button
          onClick={handleCompare}
          disabled={!canCompare}
          className={clsx(
            'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 font-medium transition-colors',
            canCompare
              ? 'bg-[#76B900] text-gray-950 hover:bg-[#5C9200]'
              : 'cursor-not-allowed bg-gray-700 text-gray-500'
          )}
        >
          {isPending ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Comparing...
            </>
          ) : (
            <>
              <Check className="h-5 w-5" />
              Compare Faces
            </>
          )}
        </button>
        <button
          onClick={handleReset}
          disabled={isPending}
          className="flex items-center gap-2 rounded-lg border border-gray-600 px-4 py-2.5 text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-800"
        >
          <RefreshCw className="h-4 w-4" />
          Reset
        </button>
      </div>

      {/* Results */}
      {result && <ComparisonResult result={result} />}
    </div>
  );
});

export default FaceSimilarityDebugTool;

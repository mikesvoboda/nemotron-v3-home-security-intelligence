/**
 * LoadingSpinner Component
 *
 * A simple loading spinner used as a fallback for React.lazy Suspense boundaries.
 * Displays a centered loading message with animation.
 *
 * Usage:
 * ```tsx
 * <Suspense fallback={<LoadingSpinner />}>
 *   <LazyComponent />
 * </Suspense>
 * ```
 */
export default function LoadingSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#121212]">
      <div className="text-center">
        <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-green-500"></div>
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    </div>
  );
}

import { Dialog, Transition } from '@headlessui/react';
import { ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react';
import { Fragment, useCallback, useEffect, useState } from 'react';

export interface LightboxImage {
  src: string;
  alt: string;
  caption?: string;
}

export interface LightboxProps {
  /** Images to display in the lightbox. Single image or array for multi-image navigation. */
  images: LightboxImage | LightboxImage[];
  /** Index of the initially selected image (when images is an array) */
  initialIndex?: number;
  /** Whether the lightbox is open */
  isOpen: boolean;
  /** Callback when the lightbox should close */
  onClose: () => void;
  /** Callback when the image index changes (for controlled navigation) */
  onIndexChange?: (index: number) => void;
  /** Show navigation arrows for multi-image galleries */
  showNavigation?: boolean;
  /** Show image counter (e.g., "1 / 5") */
  showCounter?: boolean;
  /** Custom className for the lightbox container */
  className?: string;
}

/**
 * Lightbox component displays full-size images in a modal overlay.
 * Supports single images or multi-image galleries with keyboard navigation.
 *
 * Features:
 * - Dark backdrop with smooth transitions
 * - Close on backdrop click, Escape key, or close button
 * - Arrow key navigation for multi-image galleries
 * - Touch-friendly close on mobile
 * - NVIDIA green (#76B900) accent styling
 */
export default function Lightbox({
  images,
  initialIndex = 0,
  isOpen,
  onClose,
  onIndexChange,
  showNavigation = true,
  showCounter = true,
  className = '',
}: LightboxProps) {
  // Normalize images to always be an array
  const imageArray = Array.isArray(images) ? images : [images];

  // Track when modal opens to reset index - use a key-like pattern
  // by deriving initial state from props when modal opens
  const [lastOpenState, setLastOpenState] = useState(isOpen);
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isImageLoading, setIsImageLoading] = useState(false);

  // Derive state reset from prop changes (avoids set-state-in-effect)
  if (isOpen && !lastOpenState) {
    setLastOpenState(true);
    setCurrentIndex(initialIndex);
    setIsImageLoading(true); // Start loading when lightbox opens
  } else if (!isOpen && lastOpenState) {
    setLastOpenState(false);
  }

  // Navigation handlers
  const goToPrevious = useCallback(() => {
    const newIndex = currentIndex > 0 ? currentIndex - 1 : imageArray.length - 1;
    setCurrentIndex(newIndex);
    setIsImageLoading(true); // Start loading when navigating
    onIndexChange?.(newIndex);
  }, [currentIndex, imageArray.length, onIndexChange]);

  const goToNext = useCallback(() => {
    const newIndex = currentIndex < imageArray.length - 1 ? currentIndex + 1 : 0;
    setCurrentIndex(newIndex);
    setIsImageLoading(true); // Start loading when navigating
    onIndexChange?.(newIndex);
  }, [currentIndex, imageArray.length, onIndexChange]);

  // Handle image load
  const handleImageLoad = useCallback(() => {
    setIsImageLoading(false);
  }, []);

  const handleImageError = useCallback(() => {
    setIsImageLoading(false);
  }, []);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'ArrowLeft':
          if (imageArray.length > 1) {
            e.preventDefault();
            goToPrevious();
          }
          break;
        case 'ArrowRight':
          if (imageArray.length > 1) {
            e.preventDefault();
            goToNext();
          }
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, goToPrevious, goToNext, imageArray.length]);

  // Prevent body scroll when lightbox is open
  useEffect(() => {
    if (isOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isOpen]);

  if (imageArray.length === 0) {
    return null;
  }

  const currentImage = imageArray[currentIndex];
  const hasMultipleImages = imageArray.length > 1;

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className={`relative z-[100] ${className}`}
        onClose={onClose}
        aria-labelledby="lightbox-title"
      >
        {/* Dark backdrop */}
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div
            className="fixed inset-0 bg-black/90"
            aria-hidden="true"
            data-testid="lightbox-backdrop"
          />
        </Transition.Child>

        {/* Full screen container */}
        <div className="fixed inset-0 overflow-hidden">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="relative flex max-h-[90vh] max-w-[90vw] flex-col items-center">
                {/* Close button - top right */}
                <button
                  onClick={onClose}
                  className="absolute -right-2 -top-12 z-10 rounded-full bg-gray-800/80 p-2 text-gray-300 transition-all hover:bg-gray-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-black"
                  aria-label="Close lightbox"
                  data-testid="lightbox-close-button"
                >
                  <X className="h-6 w-6" />
                </button>

                {/* Image counter - top left */}
                {showCounter && hasMultipleImages && (
                  <div
                    className="absolute -left-2 -top-12 rounded-full bg-gray-800/80 px-4 py-2 text-sm font-medium text-gray-300"
                    aria-live="polite"
                    data-testid="lightbox-counter"
                  >
                    {currentIndex + 1} / {imageArray.length}
                  </div>
                )}

                {/* Main image container */}
                <div className="relative flex items-center justify-center">
                  {/* Previous button */}
                  {showNavigation && hasMultipleImages && (
                    <button
                      onClick={goToPrevious}
                      className="absolute -left-16 z-10 rounded-full bg-gray-800/80 p-3 text-gray-300 transition-all hover:bg-[#76B900] hover:text-black focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-black"
                      aria-label="Previous image"
                      data-testid="lightbox-prev-button"
                    >
                      <ChevronLeft className="h-6 w-6" />
                    </button>
                  )}

                  {/* Image with loading state */}
                  <div className="relative">
                    {isImageLoading && (
                      <div
                        className="absolute inset-0 flex items-center justify-center rounded-lg bg-gray-900/50"
                        data-testid="lightbox-loading"
                      >
                        <Loader2 className="h-10 w-10 animate-spin text-[#76B900]" />
                      </div>
                    )}
                    <img
                      src={currentImage.src}
                      alt={currentImage.alt}
                      className={`max-h-[85vh] max-w-full rounded-lg object-contain shadow-2xl transition-opacity duration-200 ${isImageLoading ? 'opacity-50' : 'opacity-100'}`}
                      data-testid="lightbox-image"
                      onLoad={handleImageLoad}
                      onError={handleImageError}
                    />
                  </div>

                  {/* Next button */}
                  {showNavigation && hasMultipleImages && (
                    <button
                      onClick={goToNext}
                      className="absolute -right-16 z-10 rounded-full bg-gray-800/80 p-3 text-gray-300 transition-all hover:bg-[#76B900] hover:text-black focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-black"
                      aria-label="Next image"
                      data-testid="lightbox-next-button"
                    >
                      <ChevronRight className="h-6 w-6" />
                    </button>
                  )}
                </div>

                {/* Caption */}
                {currentImage.caption && (
                  <div
                    className="mt-4 max-w-xl text-center text-sm text-gray-300"
                    data-testid="lightbox-caption"
                  >
                    {currentImage.caption}
                  </div>
                )}

                {/* Hidden title for accessibility */}
                <Dialog.Title id="lightbox-title" className="sr-only">
                  {currentImage.alt}
                </Dialog.Title>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

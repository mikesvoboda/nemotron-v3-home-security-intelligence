import { User, Car, Scan, MapPin, Clock } from 'lucide-react';
import { Link } from 'react-router-dom';

/**
 * EntitiesEmptyState component - Enhanced empty state with illustration and onboarding
 *
 * Features:
 * - Visual illustration using animated Lucide icons
 * - Clear explanation of entity tracking feature
 * - "How it works" section with 4 steps
 * - CTA button linking to detection settings
 * - Subtle float animation on illustration icons
 */
export default function EntitiesEmptyState() {
  return (
    <div className="flex min-h-[600px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
      <div className="max-w-2xl px-6 text-center">
        {/* Animated Illustration */}
        <div className="relative mx-auto mb-8 h-40 w-full">
          {/* Central scanning icon */}
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#76B900]/10 ring-4 ring-[#76B900]/20">
              <Scan className="h-10 w-10 animate-pulse text-[#76B900]" />
            </div>
          </div>

          {/* Floating person icon - top left */}
          <div
            className="absolute left-1/4 top-0 animate-float"
            style={{ animationDelay: '0s' }}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10 ring-2 ring-blue-500/30">
              <User className="h-6 w-6 text-blue-400" />
            </div>
          </div>

          {/* Floating vehicle icon - top right */}
          <div
            className="absolute right-1/4 top-0 animate-float"
            style={{ animationDelay: '1s' }}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-500/10 ring-2 ring-purple-500/30">
              <Car className="h-6 w-6 text-purple-400" />
            </div>
          </div>

          {/* Floating location icon - bottom left */}
          <div
            className="absolute bottom-0 left-1/4 animate-float"
            style={{ animationDelay: '2s' }}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-500/10 ring-2 ring-green-500/30">
              <MapPin className="h-6 w-6 text-green-400" />
            </div>
          </div>

          {/* Floating clock icon - bottom right */}
          <div
            className="absolute bottom-0 right-1/4 animate-float"
            style={{ animationDelay: '3s' }}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 ring-2 ring-amber-500/30">
              <Clock className="h-6 w-6 text-amber-400" />
            </div>
          </div>
        </div>

        {/* Title */}
        <h2 className="mb-4 text-2xl font-bold text-white">No Entities Tracked Yet</h2>

        {/* Description */}
        <p className="mb-8 text-gray-400">
          Entities are automatically created when the AI identifies recurring persons or vehicles
          across your cameras using re-identification technology.
        </p>

        {/* How it works section */}
        <div className="mb-8 rounded-lg border border-gray-800 bg-black/30 p-6">
          <h3 className="mb-4 text-lg font-semibold text-white">How it works</h3>

          <div className="grid gap-4 text-left sm:grid-cols-2">
            {/* Step 1 */}
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#76B900]/10 text-sm font-bold text-[#76B900]">
                1
              </div>
              <div>
                <p className="text-sm text-gray-300">Camera detects a person or vehicle</p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#76B900]/10 text-sm font-bold text-[#76B900]">
                2
              </div>
              <div>
                <p className="text-sm text-gray-300">AI extracts visual features</p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#76B900]/10 text-sm font-bold text-[#76B900]">
                3
              </div>
              <div>
                <p className="text-sm text-gray-300">System matches across all camera feeds</p>
              </div>
            </div>

            {/* Step 4 */}
            <div className="flex gap-3">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#76B900]/10 text-sm font-bold text-[#76B900]">
                4
              </div>
              <div>
                <p className="text-sm text-gray-300">Entity profile created with movement history</p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA Button */}
        <Link
          to="/settings"
          className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-6 py-3 text-sm font-medium text-black transition-colors hover:bg-[#5a8f00]"
        >
          View Detection Settings
        </Link>
      </div>
    </div>
  );
}

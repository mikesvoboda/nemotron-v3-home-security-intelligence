import { Clock, Users } from 'lucide-react';

/**
 * EntitiesPage component - Placeholder for future entity tracking feature
 *
 * This page will eventually display:
 * - Tracked people and vehicles detected across cameras
 * - Entity history and movement patterns
 * - Known vs unknown entity classification
 * - Entity search and filtering
 */
export default function EntitiesPage() {
  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <Users className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-3xl font-bold text-white">Entities</h1>
        </div>
        <p className="mt-2 text-gray-400">
          Track and identify people and vehicles across your cameras
        </p>
      </div>

      {/* Coming Soon Placeholder */}
      <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
        <div className="max-w-md text-center">
          <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#76B900]/10">
            <Users className="h-10 w-10 text-[#76B900]" />
          </div>
          <h2 className="mb-3 text-xl font-semibold text-white">Coming Soon</h2>
          <p className="mb-6 text-gray-400">
            The Entities feature is currently under development. Once available, you will be able
            to:
          </p>
          <ul className="mb-6 space-y-2 text-left text-sm text-gray-400">
            <li className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>Track detected people and vehicles over time</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>View movement patterns across multiple cameras</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>Classify entities as known or unknown</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
              <span>Search and filter entity history</span>
            </li>
          </ul>
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
            <Clock className="h-4 w-4" />
            <span>Check back for updates</span>
          </div>
        </div>
      </div>
    </div>
  );
}

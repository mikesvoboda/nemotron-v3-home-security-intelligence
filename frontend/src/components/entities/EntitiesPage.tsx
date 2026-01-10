import { AlertCircle, Car, Loader2, RefreshCw, User, Users } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import EntitiesEmptyState from './EntitiesEmptyState';
import EntityCard from './EntityCard';
import EntityDetailModal from './EntityDetailModal';
import {
  fetchEntities,
  fetchEntity,
  type EntitySummary,
  type EntityDetail,
  type EntitiesQueryParams,
} from '../../services/api';
import { EntityCardSkeleton } from '../common';

/**
 * EntitiesPage component - Display and manage tracked entities
 *
 * Features:
 * - List of tracked people and vehicles detected across cameras
 * - Filter by entity type (person/vehicle)
 * - View entity detail with appearance timeline
 * - Refresh functionality
 */
export default function EntitiesPage() {
  // State for entities list
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for filters
  const [entityTypeFilter, setEntityTypeFilter] = useState<'all' | 'person' | 'vehicle'>('all');

  // State for entity detail modal
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Fetch entities from API
  const loadEntities = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params: EntitiesQueryParams = {
        limit: 50,
      };

      if (entityTypeFilter !== 'all') {
        params.entity_type = entityTypeFilter;
      }

      const response = await fetchEntities(params);
      setEntities(response.items);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load entities';
      setError(message);
      setEntities([]);
    } finally {
      setLoading(false);
    }
  }, [entityTypeFilter]);

  // Load entities on mount and when filter changes
  useEffect(() => {
    void loadEntities();
  }, [loadEntities]);

  // Handle entity card click - open detail modal
  const handleEntityClick = (entityId: string) => {
    setLoadingDetail(true);
    setModalOpen(true);

    fetchEntity(entityId)
      .then((detail) => {
        setSelectedEntity(detail);
      })
      .catch((err) => {
        console.error('Failed to load entity detail:', err);
        setSelectedEntity(null);
        setModalOpen(false);
      })
      .finally(() => {
        setLoadingDetail(false);
      });
  };

  // Handle modal close
  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedEntity(null);
  };

  // Handle refresh button click
  const handleRefresh = () => {
    void loadEntities();
  };

  // Count entities by type
  const personCount = entities.filter((e) => e.entity_type === 'person').length;
  const vehicleCount = entities.filter((e) => e.entity_type === 'vehicle').length;

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Users className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-3xl font-bold text-white">Entities</h1>
          </div>
          <p className="mt-2 text-gray-400">
            Track and identify people and vehicles across your cameras
          </p>
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
          aria-label="Refresh entities"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters and stats */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        {/* Entity type filter */}
        <div className="flex rounded-lg border border-gray-700 bg-[#1F1F1F]">
          <button
            onClick={() => setEntityTypeFilter('all')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'all'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            } rounded-l-lg`}
            aria-pressed={entityTypeFilter === 'all'}
          >
            All
          </button>
          <button
            onClick={() => setEntityTypeFilter('person')}
            className={`flex items-center gap-2 border-l border-gray-700 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'person'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            }`}
            aria-pressed={entityTypeFilter === 'person'}
          >
            <User className="h-4 w-4" />
            Persons
          </button>
          <button
            onClick={() => setEntityTypeFilter('vehicle')}
            className={`flex items-center gap-2 border-l border-gray-700 px-4 py-2 text-sm font-medium transition-colors ${
              entityTypeFilter === 'vehicle'
                ? 'bg-[#76B900] text-black'
                : 'text-gray-300 hover:text-white'
            } rounded-r-lg`}
            aria-pressed={entityTypeFilter === 'vehicle'}
          >
            <Car className="h-4 w-4" />
            Vehicles
          </button>
        </div>

        {/* Stats */}
        {!loading && !error && entities.length > 0 && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {personCount} {personCount === 1 ? 'person' : 'persons'}
            </span>
            <span className="flex items-center gap-1">
              <Car className="h-4 w-4" />
              {vehicleCount} {vehicleCount === 1 ? 'vehicle' : 'vehicles'}
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      {loading ? (
        /* Loading state with skeletons */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <EntityCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        /* Error state */
        <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-red-900/50 bg-red-900/10">
          <div className="flex flex-col items-center gap-3 text-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <p className="text-red-400">{error}</p>
            <button
              onClick={handleRefresh}
              className="mt-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : entities.length === 0 ? (
        /* Empty state */
        entityTypeFilter === 'all' ? (
          <EntitiesEmptyState />
        ) : (
          /* Filtered empty state - simpler message */
          <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]">
            <div className="max-w-md text-center">
              <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#76B900]/10">
                {entityTypeFilter === 'person' ? (
                  <User className="h-10 w-10 text-[#76B900]" />
                ) : (
                  <Car className="h-10 w-10 text-[#76B900]" />
                )}
              </div>
              <h2 className="mb-3 text-xl font-semibold text-white">
                No {entityTypeFilter === 'person' ? 'Persons' : 'Vehicles'} Found
              </h2>
              <p className="text-gray-400">
                No {entityTypeFilter === 'person' ? 'persons' : 'vehicles'} have been tracked yet.
              </p>
            </div>
          </div>
        )
      ) : (
        /* Entity grid */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {entities.map((entity) => (
            <EntityCard
              key={entity.id}
              id={entity.id}
              entity_type={entity.entity_type}
              first_seen={entity.first_seen}
              last_seen={entity.last_seen}
              appearance_count={entity.appearance_count}
              cameras_seen={entity.cameras_seen}
              thumbnail_url={entity.thumbnail_url}
              onClick={handleEntityClick}
            />
          ))}
        </div>
      )}

      {/* Entity Detail Modal */}
      <EntityDetailModal
        entity={selectedEntity}
        isOpen={modalOpen}
        onClose={handleCloseModal}
      />

      {/* Loading overlay for modal */}
      {loadingDetail && modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75">
          <div className="flex flex-col items-center gap-3 text-white">
            <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
            <p>Loading entity details...</p>
          </div>
        </div>
      )}
    </div>
  );
}

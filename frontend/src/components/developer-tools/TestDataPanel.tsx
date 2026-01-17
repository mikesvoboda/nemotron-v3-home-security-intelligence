/**
 * TestDataPanel - Main panel for seeding and cleanup operations
 *
 * Provides controls for:
 * - Seeding test cameras, events, and pipeline latency data
 * - Cleaning up events or performing a full database reset
 *
 * Warning: These operations modify database data. Cleanup operations
 * require typed confirmation to prevent accidental data loss.
 *
 * @example
 * ```tsx
 * <TestDataPanel />
 * ```
 */

import { Card, Title, Text, Callout } from '@tremor/react';
import { AlertTriangle, Database } from 'lucide-react';
import { useCallback } from 'react';


import CleanupRow from './CleanupRow';
import SeedRow from './SeedRow';
import {
  useSeedCamerasMutation,
  useSeedEventsMutation,
  useSeedPipelineLatencyMutation,
  useClearSeededDataMutation,
} from '../../hooks/useAdminMutations';
import { useToast } from '../../hooks/useToast';

// Seed count options
const CAMERA_COUNT_OPTIONS = [5, 10, 25, 50] as const;
const EVENT_COUNT_OPTIONS = [50, 100, 500, 1000] as const;
const PIPELINE_DAYS_OPTIONS = [7, 14, 30, 90] as const;

export interface TestDataPanelProps {
  /** Optional className for the card */
  className?: string;
}

/**
 * TestDataPanel component
 */
export default function TestDataPanel({ className }: TestDataPanelProps) {
  const toast = useToast();

  // Mutations
  const seedCamerasMutation = useSeedCamerasMutation();
  const seedEventsMutation = useSeedEventsMutation();
  const seedPipelineLatencyMutation = useSeedPipelineLatencyMutation();
  const clearSeededDataMutation = useClearSeededDataMutation();

  // Seed handlers
  const handleSeedCameras = useCallback(
    async (count: number) => {
      try {
        const result = await seedCamerasMutation.mutateAsync({ count });
        toast.success(`Created ${result.created} cameras`, {
          description: result.cleared > 0 ? `Cleared ${result.cleared} existing cameras` : undefined,
        });
      } catch (error) {
        toast.error('Failed to seed cameras', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    },
    [seedCamerasMutation, toast]
  );

  const handleSeedEvents = useCallback(
    async (count: number) => {
      try {
        const result = await seedEventsMutation.mutateAsync({ count });
        toast.success(`Created ${result.events_created} events`, {
          description: `With ${result.detections_created} detections`,
        });
      } catch (error) {
        toast.error('Failed to seed events', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    },
    [seedEventsMutation, toast]
  );

  const handleSeedPipelineLatency = useCallback(
    async (days: number) => {
      try {
        // Convert days to hours for the API
        const timeSpanHours = days * 24;
        const result = await seedPipelineLatencyMutation.mutateAsync({
          time_span_hours: timeSpanHours,
        });
        toast.success(`Pipeline latency data seeded`, {
          description: `${result.samples_per_stage} samples across ${result.stages_seeded.length} stages for ${days} days`,
        });
      } catch (error) {
        toast.error('Failed to seed pipeline data', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    },
    [seedPipelineLatencyMutation, toast]
  );

  // Cleanup handlers
  const handleDeleteAllEvents = useCallback(async () => {
    try {
      const result = await clearSeededDataMutation.mutateAsync({
        confirm: 'DELETE_ALL_DATA',
      });
      toast.success('Data deleted', {
        description: `Deleted ${result.events_cleared} events, ${result.detections_cleared} detections, ${result.cameras_cleared} cameras`,
      });
    } catch (error) {
      toast.error('Failed to delete data', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [clearSeededDataMutation, toast]);

  const handleFullReset = useCallback(async () => {
    try {
      const result = await clearSeededDataMutation.mutateAsync({
        confirm: 'DELETE_ALL_DATA',
      });
      toast.success('Database reset complete', {
        description: `Deleted ${result.events_cleared} events, ${result.detections_cleared} detections, ${result.cameras_cleared} cameras`,
      });
    } catch (error) {
      toast.error('Failed to reset database', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [clearSeededDataMutation, toast]);

  return (
    <Card
      className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}
      data-testid="test-data-panel"
    >
      {/* Header */}
      <div className="mb-4 flex items-center gap-2">
        <Database className="h-5 w-5 text-[#76B900]" />
        <Title className="text-white">Test Data</Title>
      </div>

      {/* Warning banner */}
      <Callout
        title="These operations modify database data"
        icon={AlertTriangle}
        color="amber"
        className="mb-6"
      >
        <span className="text-tremor-default text-amber-200/80">
          Seeding creates test data for development. Cleanup operations are destructive and
          require confirmation.
        </span>
      </Callout>

      {/* Seed Section */}
      <div className="mb-6">
        <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
          Seed Data
        </Text>
        <div className="space-y-3">
          <SeedRow
            label="Cameras"
            description="Creates test cameras with realistic names and configurations"
            options={CAMERA_COUNT_OPTIONS}
            defaultValue={10}
            onSeed={handleSeedCameras}
            isLoading={seedCamerasMutation.isPending}
          />
          <SeedRow
            label="Events"
            description="Creates test events with detections. Requires cameras to exist."
            options={EVENT_COUNT_OPTIONS}
            defaultValue={100}
            onSeed={handleSeedEvents}
            isLoading={seedEventsMutation.isPending}
          />
          <SeedRow
            label="Pipeline Data"
            description="Seeds pipeline latency metrics for the selected number of days"
            options={PIPELINE_DAYS_OPTIONS}
            defaultValue={7}
            onSeed={handleSeedPipelineLatency}
            isLoading={seedPipelineLatencyMutation.isPending}
            buttonText="Seed Pipeline Data"
          />
        </div>
      </div>

      {/* Cleanup Section */}
      <div>
        <Text className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-400">
          Cleanup
        </Text>
        <div className="space-y-3">
          <CleanupRow
            label="Delete All Events"
            description="Permanently deletes all events and detections from the database."
            confirmText="DELETE"
            onCleanup={handleDeleteAllEvents}
            isLoading={clearSeededDataMutation.isPending}
            variant="warning"
          />
          <CleanupRow
            label="Full Database Reset"
            description="Deletes ALL data including cameras, events, and detections. Use with caution."
            confirmText="RESET DATABASE"
            onCleanup={handleFullReset}
            isLoading={clearSeededDataMutation.isPending}
            variant="danger"
          />
        </div>
      </div>
    </Card>
  );
}

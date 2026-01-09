import { useState, useCallback, useEffect } from 'react';

/**
 * Section IDs for the System Monitoring page
 */
export type SystemSectionId =
  | 'system-health'
  | 'gpu-stats'
  | 'ai-models'
  | 'model-zoo'
  | 'pipeline-metrics'
  | 'databases'
  | 'workers'
  | 'background-jobs'
  | 'containers'
  | 'host-system'
  | 'circuit-breakers'
  | 'services';

/**
 * Default expanded state for each section
 * Based on task requirements:
 * - System Health: EXPANDED
 * - GPU Statistics: EXPANDED
 * - Services: COLLAPSED
 * - Background Workers: COLLAPSED
 * - Model Zoo: COLLAPSED
 * - Databases: COLLAPSED
 * - Circuit Breakers: COLLAPSED
 */
const DEFAULT_SECTION_STATES: Record<SystemSectionId, boolean> = {
  'system-health': true,
  'gpu-stats': true,
  'ai-models': true,
  'model-zoo': false,
  'pipeline-metrics': true,
  'databases': false,
  'workers': false,
  'background-jobs': true,
  'containers': true,
  'host-system': true,
  'circuit-breakers': false,
  'services': false,
};

const STORAGE_KEY = 'system-page-sections';

/**
 * Custom hook for managing system page section states with localStorage persistence
 *
 * Features:
 * - Persists section expanded/collapsed state to localStorage
 * - Provides default states for initial load
 * - Individual section toggle functions
 * - Batch state management
 */
export function useSystemPageSections() {
  const [sectionStates, setSectionStates] = useState<Record<SystemSectionId, boolean>>(() => {
    // Try to load from localStorage
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<Record<SystemSectionId, boolean>>;
        // Merge with defaults to handle new sections
        return { ...DEFAULT_SECTION_STATES, ...parsed };
      }
    } catch (error) {
      console.error('Failed to parse system page section states from localStorage:', error);
    }
    return DEFAULT_SECTION_STATES;
  });

  // Save to localStorage whenever state changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sectionStates));
    } catch (error) {
      console.error('Failed to save system page section states to localStorage:', error);
    }
  }, [sectionStates]);

  /**
   * Toggle a specific section's expanded state
   */
  const toggleSection = useCallback((sectionId: SystemSectionId) => {
    setSectionStates((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  }, []);

  /**
   * Set a specific section's expanded state
   */
  const setSection = useCallback((sectionId: SystemSectionId, isOpen: boolean) => {
    setSectionStates((prev) => ({
      ...prev,
      [sectionId]: isOpen,
    }));
  }, []);

  /**
   * Expand all sections
   */
  const expandAll = useCallback(() => {
    setSectionStates((prev) => {
      const allExpanded = {} as Record<SystemSectionId, boolean>;
      Object.keys(prev).forEach((key) => {
        allExpanded[key as SystemSectionId] = true;
      });
      return allExpanded;
    });
  }, []);

  /**
   * Collapse all sections
   */
  const collapseAll = useCallback(() => {
    setSectionStates((prev) => {
      const allCollapsed = {} as Record<SystemSectionId, boolean>;
      Object.keys(prev).forEach((key) => {
        allCollapsed[key as SystemSectionId] = false;
      });
      return allCollapsed;
    });
  }, []);

  /**
   * Reset to default states
   */
  const resetToDefaults = useCallback(() => {
    setSectionStates(DEFAULT_SECTION_STATES);
  }, []);

  return {
    sectionStates,
    toggleSection,
    setSection,
    expandAll,
    collapseAll,
    resetToDefaults,
  };
}

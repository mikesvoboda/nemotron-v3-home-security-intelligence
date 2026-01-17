import { useState, useCallback, useEffect } from 'react';

/**
 * Section IDs for the Developer Tools page
 */
export type DevToolsSectionId =
  | 'profiling'
  | 'recording'
  | 'config-inspector'
  | 'log-level'
  | 'test-data';

/**
 * Default expanded state for each section
 * All sections are collapsed by default per requirements
 */
const DEFAULT_SECTION_STATES: Record<DevToolsSectionId, boolean> = {
  profiling: false,
  recording: false,
  'config-inspector': false,
  'log-level': false,
  'test-data': false,
};

const STORAGE_KEY = 'dev-tools-sections';

/**
 * Custom hook for managing Developer Tools page section states with localStorage persistence
 *
 * Features:
 * - Persists section expanded/collapsed state to localStorage
 * - All sections collapsed by default
 * - Individual section toggle functions
 */
export function useDevToolsSections() {
  const [sectionStates, setSectionStates] = useState<Record<DevToolsSectionId, boolean>>(() => {
    // Try to load from localStorage
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<Record<DevToolsSectionId, boolean>>;
        // Merge with defaults to handle new sections
        return { ...DEFAULT_SECTION_STATES, ...parsed };
      }
    } catch (error) {
      console.error('Failed to parse dev tools section states from localStorage:', error);
    }
    return DEFAULT_SECTION_STATES;
  });

  // Save to localStorage whenever state changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sectionStates));
    } catch (error) {
      console.error('Failed to save dev tools section states to localStorage:', error);
    }
  }, [sectionStates]);

  /**
   * Toggle a specific section's expanded state
   */
  const toggleSection = useCallback((sectionId: DevToolsSectionId) => {
    setSectionStates((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  }, []);

  /**
   * Set a specific section's expanded state
   */
  const setSection = useCallback((sectionId: DevToolsSectionId, isOpen: boolean) => {
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
      const allExpanded = {} as Record<DevToolsSectionId, boolean>;
      Object.keys(prev).forEach((key) => {
        allExpanded[key as DevToolsSectionId] = true;
      });
      return allExpanded;
    });
  }, []);

  /**
   * Collapse all sections
   */
  const collapseAll = useCallback(() => {
    setSectionStates((prev) => {
      const allCollapsed = {} as Record<DevToolsSectionId, boolean>;
      Object.keys(prev).forEach((key) => {
        allCollapsed[key as DevToolsSectionId] = false;
      });
      return allCollapsed;
    });
  }, []);

  /**
   * Reset to default states (all collapsed)
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

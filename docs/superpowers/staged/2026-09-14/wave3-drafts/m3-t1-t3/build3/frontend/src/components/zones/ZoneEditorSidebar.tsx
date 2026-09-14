/**
 * ZoneEditorSidebar - Collapsible sidebar for zone editor with tabs (NEM-3200)
 *
 * Provides a tabbed interface for zone management:
 * - Draw tab: Zone list and drawing tools
 * - Configure tab: Zone ownership and settings
 * - Analytics tab: Activity heatmap and status
 *
 * Part of Phase 5.1: Enhanced Zone Editor Integration.
 *
 * @module components/zones/ZoneEditorSidebar
 */

import { Tab } from '@headlessui/react';
import { Select, SelectItem } from '@tremor/react';
import { clsx } from 'clsx';
import { BarChart3, ChevronLeft, ChevronRight, Layers, PenTool, Settings } from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import ZoneActivityHeatmap from './ZoneActivityHeatmap';
import ZoneList from './ZoneList';
import ZoneOwnershipPanel from './ZoneOwnershipPanel';
import ZoneStatusCard from './ZoneStatusCard';

import type { Zone } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Tab identifiers for the sidebar.
 */
export type SidebarTab = 'draw' | 'configure' | 'analytics';

/**
 * Props for the ZoneEditorSidebar component.
 */
export interface ZoneEditorSidebarProps {
  /** Camera ID for zone context */
  cameraId: string;
  /** List of zones for the camera */
  zones: Zone[];
  /** Currently selected zone ID */
  selectedZoneId?: string | null;
  /** Active tab */
  activeTab?: SidebarTab;
  /** Whether the sidebar is collapsed */
  collapsed?: boolean;
  /** Callback when a zone is selected */
  onZoneSelect?: (zoneId: string) => void;
  /** Callback when a zone should be edited */
  onZoneEdit?: (zone: Zone) => void;
  /** Callback when a zone should be deleted */
  onZoneDelete?: (zone: Zone) => void;
  /** Callback when zone enabled status is toggled */
  onZoneToggleEnabled?: (zone: Zone) => void;
  /** Callback when tab changes */
  onTabChange?: (tab: SidebarTab) => void;
  /** Callback when collapse state changes */
  onCollapseChange?: (collapsed: boolean) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const TABS: { id: SidebarTab; label: string; icon: typeof PenTool }[] = [
  { id: 'draw', label: 'Draw', icon: PenTool },
  { id: 'configure', label: 'Configure', icon: Settings },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
];

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Zone selector dropdown.
 */
interface ZoneSelectorProps {
  zones: Zone[];
  selectedZoneId?: string | null;
  onSelect: (zoneId: string) => void;
}

function ZoneSelector({ zones, selectedZoneId, onSelect }: ZoneSelectorProps) {
  if (zones.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3 text-center">
        <Layers className="mx-auto mb-2 h-6 w-6 text-gray-500" />
        <p className="text-sm text-gray-400">No zones defined</p>
        <p className="text-xs text-gray-500">Draw a zone to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <span id="zone-selector-label" className="block text-sm font-medium text-gray-300">
        Select Zone
      </span>
      <Select
        value={selectedZoneId ?? ''}
        onValueChange={onSelect}
        placeholder="Choose a zone..."
        data-testid="zone-selector"
        aria-labelledby="zone-selector-label"
      >
        {zones.map((zone) => (
          <SelectItem key={zone.id} value={zone.id}>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: zone.color }} />
              {zone.name}
            </div>
          </SelectItem>
        ))}
      </Select>
    </div>
  );
}

/**
 * Draw tab content.
 */
interface DrawTabContentProps {
  zones: Zone[];
  selectedZoneId?: string | null;
  onSelect: (zoneId: string) => void;
  onEdit: (zone: Zone) => void;
  onDelete: (zone: Zone) => void;
  onToggleEnabled: (zone: Zone) => void;
}

function DrawTabContent({
  zones,
  selectedZoneId,
  onSelect,
  onEdit,
  onDelete,
  onToggleEnabled,
}: DrawTabContentProps) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-3 text-lg font-semibold text-white">Zones ({zones.length})</h3>
        <ZoneList
          zones={zones}
          selectedZoneId={selectedZoneId}
          onSelect={onSelect}
          onEdit={onEdit}
          onDelete={onDelete}
          onToggleEnabled={onToggleEnabled}
        />
      </div>
    </div>
  );
}

/**
 * Configure tab content.
 */
interface ConfigureTabContentProps {
  cameraId: string;
  zones: Zone[];
  selectedZoneId?: string | null;
  onZoneSelect: (zoneId: string) => void;
}

function ConfigureTabContent({
  cameraId,
  zones,
  selectedZoneId,
  onZoneSelect,
}: ConfigureTabContentProps) {
  const selectedZone = zones.find((z) => z.id === selectedZoneId);

  // Suppress unused variable warning - cameraId may be used for future API calls
  void cameraId;

  return (
    <div className="space-y-4">
      <ZoneSelector zones={zones} selectedZoneId={selectedZoneId} onSelect={onZoneSelect} />

      {selectedZone ? (
        <div className="space-y-4">
          <ZoneStatusCard zoneId={selectedZone.id} zoneName={selectedZone.name} compact />

          <ZoneOwnershipPanel
            zoneId={selectedZone.id}
            zoneName={selectedZone.name}
            editable
            compact
          />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-700 bg-gray-800/30 p-6 text-center">
          <Settings className="mx-auto mb-2 h-8 w-8 text-gray-500" />
          <p className="text-sm text-gray-400">Select a zone to configure</p>
          <p className="mt-1 text-xs text-gray-500">
            Configure ownership, access control, and settings
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Analytics tab content.
 */
interface AnalyticsTabContentProps {
  cameraId: string;
  zones: Zone[];
  selectedZoneId?: string | null;
  onZoneSelect: (zoneId: string) => void;
}

function AnalyticsTabContent({
  cameraId,
  zones,
  selectedZoneId,
  onZoneSelect,
}: AnalyticsTabContentProps) {
  const selectedZone = zones.find((z) => z.id === selectedZoneId);

  // Suppress unused variable warning - cameraId may be used for future API calls
  void cameraId;

  return (
    <div className="space-y-4">
      <ZoneSelector zones={zones} selectedZoneId={selectedZoneId} onSelect={onZoneSelect} />

      {selectedZone ? (
        <div className="space-y-4">
          <ZoneStatusCard zoneId={selectedZone.id} zoneName={selectedZone.name} compact />

          <ZoneActivityHeatmap zoneId={selectedZone.id} zoneName={selectedZone.name} compact />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-700 bg-gray-800/30 p-6 text-center">
          <BarChart3 className="mx-auto mb-2 h-8 w-8 text-gray-500" />
          <p className="text-sm text-gray-400">Select a zone for analytics</p>
          <p className="mt-1 text-xs text-gray-500">View activity patterns, heatmaps, and trends</p>
        </div>
      )}
    </div>
  );
}

/**
 * Collapsed sidebar view showing only icons.
 */
interface CollapsedSidebarProps {
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  onExpand: () => void;
}

function CollapsedSidebar({ activeTab, onTabChange, onExpand }: CollapsedSidebarProps) {
  return (
    <div className="flex h-full w-12 flex-col border-l border-gray-700 bg-[#1A1A1A]">
      {/* Expand button */}
      <button
        type="button"
        onClick={onExpand}
        className="flex h-10 items-center justify-center border-b border-gray-700 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
        title="Expand sidebar"
        data-testid="expand-sidebar-btn"
      >
        <ChevronLeft className="h-5 w-5" />
      </button>

      {/* Tab icons */}
      <div className="flex flex-col gap-1 p-1">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={clsx(
                'flex h-10 w-10 items-center justify-center rounded transition-colors',
                isActive
                  ? 'bg-[#76B900]/20 text-[#76B900]'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              )}
              title={tab.label}
              data-testid={`collapsed-tab-${tab.id}`}
            >
              <Icon className="h-5 w-5" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneEditorSidebar component.
 *
 * Provides a tabbed sidebar interface for the zone editor with:
 * - Draw tab: Zone list and CRUD operations
 * - Configure tab: Zone ownership and access settings
 * - Analytics tab: Activity heatmaps and status
 *
 * The sidebar can be collapsed to save space and is responsive.
 *
 * @param props - Component props
 * @returns Rendered component
 */
export default function ZoneEditorSidebar({
  cameraId,
  zones,
  selectedZoneId,
  activeTab = 'draw',
  collapsed = false,
  onZoneSelect,
  onZoneEdit,
  onZoneDelete,
  onZoneToggleEnabled,
  onTabChange,
  onCollapseChange,
  className,
}: ZoneEditorSidebarProps) {
  // Internal state for tab if not controlled
  const [internalTab, setInternalTab] = useState<SidebarTab>(activeTab);
  const currentTab = onTabChange ? activeTab : internalTab;

  // Internal state for collapse if not controlled
  const [internalCollapsed, setInternalCollapsed] = useState(collapsed);
  const isCollapsed = onCollapseChange ? collapsed : internalCollapsed;

  const handleTabChange = useCallback(
    (tab: SidebarTab) => {
      if (onTabChange) {
        onTabChange(tab);
      } else {
        setInternalTab(tab);
      }
    },
    [onTabChange]
  );

  const handleCollapse = useCallback(() => {
    if (onCollapseChange) {
      onCollapseChange(!isCollapsed);
    } else {
      setInternalCollapsed(!isCollapsed);
    }
  }, [isCollapsed, onCollapseChange]);

  const handleZoneSelect = useCallback(
    (zoneId: string) => {
      onZoneSelect?.(zoneId === selectedZoneId ? '' : zoneId);
    },
    [onZoneSelect, selectedZoneId]
  );

  const handleZoneEdit = useCallback(
    (zone: Zone) => {
      onZoneEdit?.(zone);
    },
    [onZoneEdit]
  );

  const handleZoneDelete = useCallback(
    (zone: Zone) => {
      onZoneDelete?.(zone);
    },
    [onZoneDelete]
  );

  const handleZoneToggleEnabled = useCallback(
    (zone: Zone) => {
      onZoneToggleEnabled?.(zone);
    },
    [onZoneToggleEnabled]
  );

  // Render collapsed state
  if (isCollapsed) {
    return (
      <CollapsedSidebar
        activeTab={currentTab}
        onTabChange={handleTabChange}
        onExpand={handleCollapse}
      />
    );
  }

  // Map tab ID to index for Tab.Group
  const tabIndex = TABS.findIndex((t) => t.id === currentTab);

  return (
    <div
      className={clsx(
        'flex h-full w-80 shrink-0 flex-col border-l border-gray-700 bg-[#1A1A1A]',
        className
      )}
      data-testid="zone-editor-sidebar"
    >
      {/* Header with collapse button */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
        <h2 className="text-lg font-semibold text-white">Zone Editor</h2>
        <button
          type="button"
          onClick={handleCollapse}
          className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
          title="Collapse sidebar"
          data-testid="collapse-sidebar-btn"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {/* Tab navigation */}
      <Tab.Group
        selectedIndex={tabIndex >= 0 ? tabIndex : 0}
        onChange={(index) => handleTabChange(TABS[index].id)}
      >
        <Tab.List className="flex border-b border-gray-700">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <Tab key={tab.id} as={Fragment}>
                {({ selected }) => (
                  <button
                    type="button"
                    className={clsx(
                      'flex flex-1 items-center justify-center gap-1.5 py-2.5 text-sm font-medium transition-colors focus:outline-none',
                      selected
                        ? 'border-b-2 border-[#76B900] text-[#76B900]'
                        : 'border-b-2 border-transparent text-gray-400 hover:text-white'
                    )}
                    data-testid={`tab-${tab.id}`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                )}
              </Tab>
            );
          })}
        </Tab.List>

        {/* Tab panels */}
        <Tab.Panels className="flex-1 overflow-y-auto p-4">
          <Tab.Panel>
            <DrawTabContent
              zones={zones}
              selectedZoneId={selectedZoneId}
              onSelect={handleZoneSelect}
              onEdit={handleZoneEdit}
              onDelete={handleZoneDelete}
              onToggleEnabled={handleZoneToggleEnabled}
            />
          </Tab.Panel>

          <Tab.Panel>
            <ConfigureTabContent
              cameraId={cameraId}
              zones={zones}
              selectedZoneId={selectedZoneId}
              onZoneSelect={handleZoneSelect}
            />
          </Tab.Panel>

          <Tab.Panel>
            <AnalyticsTabContent
              cameraId={cameraId}
              zones={zones}
              selectedZoneId={selectedZoneId}
              onZoneSelect={handleZoneSelect}
            />
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}

// ============================================================================
// Exports
// ============================================================================

export {
  ZoneSelector,
  DrawTabContent,
  ConfigureTabContent,
  AnalyticsTabContent,
  CollapsedSidebar,
  TABS,
};

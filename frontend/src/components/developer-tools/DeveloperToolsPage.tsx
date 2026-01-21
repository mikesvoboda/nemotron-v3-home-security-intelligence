import { Text } from '@tremor/react';
import {
  Activity,
  Database,
  FileText,
  HardDrive,
  Settings,
  Terminal,
  Video,
  Zap,
} from 'lucide-react';

import CircuitBreakerDebugPanel from './CircuitBreakerDebugPanel';
import ConfigInspectorPanel from './ConfigInspectorPanel';
import LogLevelPanel from './LogLevelPanel';
import MemorySnapshotPanel from './MemorySnapshotPanel';
import ProfilingPanel from './ProfilingPanel';
import RecordingReplayPanel from './RecordingReplayPanel';
import TestDataPanel from './TestDataPanel';
import { useDevToolsSections } from '../../hooks/useDevToolsSections';
import { useSystemConfigQuery } from '../../hooks/useSystemConfigQuery';
import CollapsibleSection from '../system/CollapsibleSection';

/**
 * DeveloperToolsPage - Developer debugging and tooling dashboard
 *
 * Provides access to development tools:
 * - Performance Profiling
 * - Request Recording/Replay
 * - Configuration Inspector
 * - Log Level Control
 * - Test Data Generation
 *
 * @see NEM-2719 - Create Developer Tools page structure and routing
 */
export default function DeveloperToolsPage() {
  const { isLoading, error } = useSystemConfigQuery();
  const { sectionStates, toggleSection } = useDevToolsSections();

  // Show loading state while checking config
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="developer-tools-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-64 animate-pulse rounded-lg bg-gray-800" />
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800" />
          </div>

          {/* Sections skeleton */}
          <div className="space-y-4">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-gray-800" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Show error state if config fetch failed
  if (error) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="developer-tools-error">
        <div className="mx-auto max-w-[1920px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
            <Text className="text-red-400">Failed to load configuration: {error.message}</Text>
          </div>
        </div>
      </div>
    );
  }

  // Developer tools are always accessible (no debug flag required)

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="developer-tools-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <Terminal className="h-8 w-8 text-[#76B900]" />
            <h1 className="text-4xl font-bold text-white">Developer Tools</h1>
          </div>
          <p className="mt-2 text-sm text-gray-400">
            Debugging and development utilities for the home security system
          </p>
        </div>

        {/* Collapsible Sections */}
        <div className="space-y-4">
          {/* Performance Profiling */}
          <CollapsibleSection
            title="Performance Profiling"
            icon={<Activity className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates.profiling}
            onToggle={() => toggleSection('profiling')}
            data-testid="profiling-section"
          >
            <ProfilingPanel />
          </CollapsibleSection>

          {/* Request Recording */}
          <CollapsibleSection
            title="Request Recording"
            icon={<Video className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates.recording}
            onToggle={() => toggleSection('recording')}
            data-testid="recording-section"
          >
            <RecordingReplayPanel />
          </CollapsibleSection>

          {/* Configuration Inspector */}
          <CollapsibleSection
            title="Configuration Inspector"
            icon={<Settings className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates['config-inspector']}
            onToggle={() => toggleSection('config-inspector')}
            data-testid="config-inspector-section"
          >
            <ConfigInspectorPanel />
          </CollapsibleSection>

          {/* Log Level Control */}
          <CollapsibleSection
            title="Log Level"
            icon={<FileText className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates['log-level']}
            onToggle={() => toggleSection('log-level')}
            data-testid="log-level-section"
          >
            <LogLevelPanel />
          </CollapsibleSection>

          {/* Test Data Generation */}
          <CollapsibleSection
            title="Test Data"
            icon={<Database className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates['test-data']}
            onToggle={() => toggleSection('test-data')}
            data-testid="test-data-section"
          >
            <TestDataPanel />
          </CollapsibleSection>

          {/* Memory Snapshot */}
          <CollapsibleSection
            title="Memory Snapshot"
            icon={<HardDrive className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates.memory}
            onToggle={() => toggleSection('memory')}
            data-testid="memory-section"
          >
            <MemorySnapshotPanel />
          </CollapsibleSection>

          {/* Circuit Breakers Debug */}
          <CollapsibleSection
            title="Circuit Breakers"
            icon={<Zap className="h-5 w-5 text-[#76B900]" />}
            isOpen={sectionStates['circuit-breakers']}
            onToggle={() => toggleSection('circuit-breakers')}
            data-testid="circuit-breakers-section"
          >
            <CircuitBreakerDebugPanel />
          </CollapsibleSection>
        </div>
      </div>
    </div>
  );
}

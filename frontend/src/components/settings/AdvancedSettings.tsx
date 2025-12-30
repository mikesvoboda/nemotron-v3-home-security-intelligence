import { Card, Title, Text, Badge } from '@tremor/react';
import {
  AlertCircle,
  Info,
  Zap,
  Clock,
  Video,
  BarChart3,
} from 'lucide-react';
import { useEffect, useState, useMemo } from 'react';

import {
  fetchSeverityMetadata,
  type SeverityMetadataResponse,
  type SeverityDefinitionResponse,
  type SeverityThresholds,
} from '../../services/api';

export interface AdvancedSettingsProps {
  className?: string;
}

/**
 * Severity bar visualization showing the risk score ranges for each severity level.
 * Displays a gradient bar with LOW, MEDIUM, HIGH, CRITICAL segments.
 */
function SeverityBar({
  thresholds,
  definitions,
}: {
  thresholds: SeverityThresholds;
  definitions: SeverityDefinitionResponse[];
}) {
  // Sort definitions by priority (low priority number = higher severity)
  const sortedDefinitions = useMemo(() => {
    return [...definitions].sort((a, b) => b.priority - a.priority);
  }, [definitions]);

  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
        <span>0</span>
        <span>Risk Score</span>
        <span>100</span>
      </div>
      <div className="relative h-8 w-full overflow-hidden rounded-lg">
        <div className="absolute inset-0 flex">
          {sortedDefinitions.map((def) => {
            const width = def.max_score - def.min_score + 1;
            return (
              <div
                key={def.severity}
                className="flex h-full items-center justify-center text-xs font-medium"
                style={{
                  width: `${width}%`,
                  backgroundColor: def.color,
                  color: def.severity === 'low' || def.severity === 'medium' ? '#000' : '#fff',
                }}
                title={`${def.label}: ${def.min_score}-${def.max_score}`}
              >
                {width > 15 && def.label}
              </div>
            );
          })}
        </div>
      </div>
      {/* Threshold markers */}
      <div className="relative mt-1 h-6">
        <div
          className="absolute flex flex-col items-center"
          style={{ left: `${thresholds.low_max}%`, transform: 'translateX(-50%)' }}
        >
          <div className="h-2 w-px bg-gray-500"></div>
          <span className="text-xs text-gray-400">{thresholds.low_max}</span>
        </div>
        <div
          className="absolute flex flex-col items-center"
          style={{ left: `${thresholds.medium_max}%`, transform: 'translateX(-50%)' }}
        >
          <div className="h-2 w-px bg-gray-500"></div>
          <span className="text-xs text-gray-400">{thresholds.medium_max}</span>
        </div>
        <div
          className="absolute flex flex-col items-center"
          style={{ left: `${thresholds.high_max}%`, transform: 'translateX(-50%)' }}
        >
          <div className="h-2 w-px bg-gray-500"></div>
          <span className="text-xs text-gray-400">{thresholds.high_max}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Single severity level definition display
 */
function SeverityDefinitionCard({ definition }: { definition: SeverityDefinitionResponse }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 p-3">
      <div className="flex items-center gap-3">
        <div className="h-4 w-4 rounded" style={{ backgroundColor: definition.color }}></div>
        <div>
          <Text className="font-medium text-white">{definition.label}</Text>
          <Text className="text-xs text-gray-400">{definition.description}</Text>
        </div>
      </div>
      <Badge
        className="border-gray-600 bg-gray-700 text-gray-300"
        size="sm"
      >
        {definition.min_score} - {definition.max_score}
      </Badge>
    </div>
  );
}

/**
 * AdvancedSettings component displays severity thresholds and advanced detection settings.
 *
 * Features:
 * - Visual severity threshold bar showing LOW/MEDIUM/HIGH/CRITICAL ranges
 * - Severity level definitions with colors and descriptions
 * - Fast path detection settings (read-only display)
 * - Video processing settings (read-only display)
 * - GPU monitoring settings (read-only display)
 *
 * Note: Currently read-only as backend PATCH /api/system/config does not support
 * modifying severity thresholds. These require environment variable changes.
 */
export default function AdvancedSettings({ className }: AdvancedSettingsProps) {
  const [severityData, setSeverityData] = useState<SeverityMetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSeverityData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSeverityMetadata();
        setSeverityData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load severity settings');
      } finally {
        setLoading(false);
      }
    };

    void loadSeverityData();
  }, []);

  // Sort definitions by min_score for display
  const sortedDefinitions = useMemo(() => {
    if (!severityData) return [];
    return [...severityData.definitions].sort((a, b) => a.min_score - b.min_score);
  }, [severityData]);

  return (
    <div className={`space-y-6 ${className || ''}`}>
      {/* Severity Thresholds Card */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <BarChart3 className="h-5 w-5 text-[#76B900]" />
          Severity Thresholds
        </Title>

        {loading && (
          <div className="space-y-4">
            <div className="skeleton h-12 w-full"></div>
            <div className="skeleton h-32 w-full"></div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
            <Text className="text-red-500">{error}</Text>
          </div>
        )}

        {!loading && severityData && (
          <div className="space-y-6">
            {/* Info banner */}
            <div className="flex items-start gap-3 rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
              <Info className="h-5 w-5 flex-shrink-0 text-blue-400" />
              <div>
                <Text className="font-medium text-blue-400">Risk Score Classification</Text>
                <Text className="mt-1 text-sm text-gray-300">
                  Events are classified by risk score (0-100) into severity levels. The AI model
                  (Nemotron) assigns risk scores based on detected objects and context. These
                  thresholds determine how events are categorized in the dashboard.
                </Text>
              </div>
            </div>

            {/* Visual severity bar */}
            <SeverityBar
              thresholds={severityData.thresholds}
              definitions={severityData.definitions}
            />

            {/* Severity level definitions */}
            <div className="space-y-3">
              <Text className="text-sm font-medium text-gray-300">Severity Levels</Text>
              {sortedDefinitions.map((def) => (
                <SeverityDefinitionCard key={def.severity} definition={def} />
              ))}
            </div>

            {/* Configuration note */}
            <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
              <Text className="text-xs text-gray-400">
                <span className="font-medium text-gray-300">Configuration: </span>
                Severity thresholds are configured via environment variables (SEVERITY_LOW_MAX,
                SEVERITY_MEDIUM_MAX, SEVERITY_HIGH_MAX). Adjusting these requires a server restart.
              </Text>
            </div>
          </div>
        )}
      </Card>

      {/* Fast Path Detection Settings */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Zap className="h-5 w-5 text-[#76B900]" />
          Fast Path Detection
        </Title>

        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
            <Zap className="h-5 w-5 flex-shrink-0 text-yellow-400" />
            <div>
              <Text className="font-medium text-yellow-400">Priority Analysis Mode</Text>
              <Text className="mt-1 text-sm text-gray-300">
                When high-confidence detections of certain object types are found, they bypass
                normal batch processing and are analyzed immediately. This ensures critical
                detections (like a person at high confidence) get faster risk assessment.
              </Text>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
              <Text className="text-sm text-gray-400">Confidence Threshold</Text>
              <Text className="mt-1 text-2xl font-bold text-white">
                90%
                <span className="ml-2 text-sm font-normal text-gray-400">(0.90)</span>
              </Text>
              <Text className="mt-1 text-xs text-gray-500">
                Detections above this confidence trigger fast path
              </Text>
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
              <Text className="text-sm text-gray-400">Fast Path Object Types</Text>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge className="bg-[#76B900] text-black">person</Badge>
              </div>
              <Text className="mt-2 text-xs text-gray-500">
                Only these object types trigger fast path analysis
              </Text>
            </div>
          </div>

          <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
            <Text className="text-xs text-gray-400">
              <span className="font-medium text-gray-300">Configuration: </span>
              Fast path settings are configured via environment variables
              (FAST_PATH_CONFIDENCE_THRESHOLD, FAST_PATH_OBJECT_TYPES).
            </Text>
          </div>
        </div>
      </Card>

      {/* Video Processing Settings */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Video className="h-5 w-5 text-[#76B900]" />
          Video Processing
        </Title>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <Text className="text-sm text-gray-400">Frame Extraction Interval</Text>
            <Text className="mt-1 text-2xl font-bold text-white">2.0s</Text>
            <Text className="mt-1 text-xs text-gray-500">Time between extracted video frames</Text>
          </div>

          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <Text className="text-sm text-gray-400">Pre-Roll Duration</Text>
            <Text className="mt-1 text-2xl font-bold text-white">5s</Text>
            <Text className="mt-1 text-xs text-gray-500">
              Seconds before event to include in clip
            </Text>
          </div>

          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <Text className="text-sm text-gray-400">Post-Roll Duration</Text>
            <Text className="mt-1 text-2xl font-bold text-white">5s</Text>
            <Text className="mt-1 text-xs text-gray-500">
              Seconds after event to include in clip
            </Text>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
          <Text className="text-xs text-gray-400">
            <span className="font-medium text-gray-300">Configuration: </span>
            Video processing settings are configured via environment variables
            (VIDEO_FRAME_INTERVAL_SECONDS, CLIP_PRE_ROLL_SECONDS, CLIP_POST_ROLL_SECONDS,
            CLIP_GENERATION_ENABLED).
          </Text>
        </div>
      </Card>

      {/* GPU Monitoring Settings */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Clock className="h-5 w-5 text-[#76B900]" />
          GPU Monitoring
        </Title>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <Text className="text-sm text-gray-400">Stats Polling Interval</Text>
            <Text className="mt-1 text-2xl font-bold text-white">5.0s</Text>
            <Text className="mt-1 text-xs text-gray-500">
              How often GPU statistics are collected
            </Text>
          </div>

          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <Text className="text-sm text-gray-400">Stats History Duration</Text>
            <Text className="mt-1 text-2xl font-bold text-white">60 min</Text>
            <Text className="mt-1 text-xs text-gray-500">
              GPU stats retained in memory for charting
            </Text>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800/30 p-4">
          <Text className="text-xs text-gray-400">
            <span className="font-medium text-gray-300">Configuration: </span>
            GPU monitoring settings are configured via environment variables
            (GPU_POLL_INTERVAL_SECONDS, GPU_STATS_HISTORY_MINUTES).
          </Text>
        </div>
      </Card>
    </div>
  );
}

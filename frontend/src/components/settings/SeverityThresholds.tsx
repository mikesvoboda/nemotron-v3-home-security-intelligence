import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';

import { fetchSeverityConfig, type SeverityMetadataResponse } from '../../services/api';

export interface SeverityThresholdsProps {
  className?: string;
}

/**
 * SeverityThresholds component displays risk score thresholds for each severity level.
 * - Fetches severity definitions from /api/system/severity endpoint
 * - Shows a table with severity levels, score ranges, and descriptions
 * - Displays color-coded indicators for each severity level
 * - Handles loading, error, and success states
 */
export default function SeverityThresholds({ className }: SeverityThresholdsProps) {
  const [severityData, setSeverityData] = useState<SeverityMetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSeverityConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSeverityConfig();
        setSeverityData(data);
      } catch {
        setError('Failed to load severity thresholds');
      } finally {
        setLoading(false);
      }
    };

    void loadSeverityConfig();
  }, []);

  // Sort definitions by min_score to display in ascending order (low to critical)
  const sortedDefinitions = severityData?.definitions
    ? [...severityData.definitions].sort((a, b) => a.min_score - b.min_score)
    : [];

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <ShieldAlert className="h-5 w-5 text-[#76B900]" />
        Risk Score Thresholds
      </Title>

      {loading && (
        <div className="space-y-3">
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
          <div className="skeleton h-8 w-full"></div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <Text className="text-red-500">{error}</Text>
        </div>
      )}

      {!loading && !error && severityData && (
        <div className="overflow-hidden rounded-lg border border-gray-700">
          <table className="w-full" role="table">
            <thead>
              <tr className="border-b border-gray-700 bg-gray-800/50">
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                  role="columnheader"
                >
                  Level
                </th>
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                  role="columnheader"
                >
                  Range
                </th>
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-300"
                  role="columnheader"
                >
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedDefinitions.map((definition) => (
                <tr
                  key={definition.severity}
                  className="border-b border-gray-700/50 last:border-b-0"
                  role="row"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div
                        data-testid={`severity-indicator-${definition.severity}`}
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: definition.color }}
                      />
                      <Text className="font-medium text-white">{definition.label}</Text>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Text className="font-mono text-gray-300">
                      {definition.min_score}-{definition.max_score}
                    </Text>
                  </td>
                  <td className="px-4 py-3">
                    <Text className="text-gray-400">{definition.description}</Text>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

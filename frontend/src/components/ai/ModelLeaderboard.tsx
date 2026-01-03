/**
 * ModelLeaderboard - Sortable table ranking AI models by contribution
 *
 * Displays a table of AI models ranked by their contribution rate,
 * with event counts and quality correlation data.
 */

import { Card, Title, Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell, Badge, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { Trophy, ArrowUpDown } from 'lucide-react';
import React, { useState, useMemo } from 'react';

import type { AiAuditModelLeaderboardEntry } from '../../services/api';

export interface ModelLeaderboardProps {
  /** Leaderboard entries */
  entries: AiAuditModelLeaderboardEntry[];
  /** Period in days this data covers */
  periodDays: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Human-readable labels for model names
 */
const MODEL_LABELS: Record<string, string> = {
  rtdetr: 'RT-DETR',
  florence: 'Florence-2',
  clip: 'CLIP',
  violence: 'Violence Detection',
  clothing: 'Clothing Analysis',
  vehicle: 'Vehicle Classification',
  pet: 'Pet Detection',
  weather: 'Weather Classification',
  image_quality: 'Image Quality',
  zones: 'Zone Analysis',
  baseline: 'Baseline Comparison',
  cross_camera: 'Cross-Camera Correlation',
};

type SortKey = 'model_name' | 'contribution_rate' | 'event_count' | 'quality_correlation';
type SortDirection = 'asc' | 'desc';

/**
 * Get badge color based on contribution rate
 */
function getContributionBadgeColor(rate: number): 'emerald' | 'yellow' | 'gray' {
  if (rate >= 0.8) return 'emerald';
  if (rate >= 0.5) return 'yellow';
  return 'gray';
}

/**
 * Get rank badge for top 3 models
 */
function getRankBadge(rank: number): React.ReactNode {
  if (rank === 1) return <Badge color="amber" size="xs">1st</Badge>;
  if (rank === 2) return <Badge color="gray" size="xs">2nd</Badge>;
  if (rank === 3) return <Badge color="orange" size="xs">3rd</Badge>;
  return null;
}

/**
 * ModelLeaderboard - Sortable table of AI model rankings
 */
export default function ModelLeaderboard({
  entries,
  periodDays,
  className,
}: ModelLeaderboardProps) {
  const [sortKey, setSortKey] = useState<SortKey>('contribution_rate');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Sort entries
  const sortedEntries = useMemo(() => {
    const sorted = [...entries].sort((a, b) => {
      let aVal: string | number = a[sortKey] ?? 0;
      let bVal: string | number = b[sortKey] ?? 0;

      // Handle model_name sorting
      if (sortKey === 'model_name') {
        aVal = MODEL_LABELS[a.model_name] || a.model_name;
        bVal = MODEL_LABELS[b.model_name] || b.model_name;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return sortDirection === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
    return sorted;
  }, [entries, sortKey, sortDirection]);

  // Handle column header click
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDirection('desc');
    }
  };

  // Get rank for original sorted entries (by contribution rate desc)
  const getRank = (modelName: string): number => {
    const byContribution = [...entries].sort((a, b) => b.contribution_rate - a.contribution_rate);
    return byContribution.findIndex((e) => e.model_name === modelName) + 1;
  };

  const hasData = entries.length > 0;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="model-leaderboard"
    >
      <div className="flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Trophy className="h-5 w-5 text-[#76B900]" />
          Model Leaderboard
        </Title>
        <Text className="text-sm text-gray-400">Last {periodDays} days</Text>
      </div>

      {hasData ? (
        <Table className="mt-4" data-testid="leaderboard-table">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="text-gray-400">Rank</TableHeaderCell>
              <TableHeaderCell
                className="cursor-pointer text-gray-400 hover:text-white"
                onClick={() => handleSort('model_name')}
              >
                <span className="flex items-center gap-1">
                  Model
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </TableHeaderCell>
              <TableHeaderCell
                className="cursor-pointer text-gray-400 hover:text-white"
                onClick={() => handleSort('contribution_rate')}
              >
                <span className="flex items-center gap-1">
                  Contribution Rate
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </TableHeaderCell>
              <TableHeaderCell
                className="cursor-pointer text-gray-400 hover:text-white"
                onClick={() => handleSort('event_count')}
              >
                <span className="flex items-center gap-1">
                  Events
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </TableHeaderCell>
              <TableHeaderCell
                className="cursor-pointer text-gray-400 hover:text-white"
                onClick={() => handleSort('quality_correlation')}
              >
                <span className="flex items-center gap-1">
                  Quality Correlation
                  <ArrowUpDown className="h-3 w-3" />
                </span>
              </TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedEntries.map((entry) => {
              const rank = getRank(entry.model_name);
              return (
                <TableRow key={entry.model_name} data-testid={`leaderboard-row-${entry.model_name}`}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-gray-400">{rank}</span>
                      {getRankBadge(rank)}
                    </div>
                  </TableCell>
                  <TableCell className="font-medium text-white">
                    {MODEL_LABELS[entry.model_name] || entry.model_name}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge color={getContributionBadgeColor(entry.contribution_rate)} size="sm">
                        {(entry.contribution_rate * 100).toFixed(0)}%
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-gray-300">
                    {entry.event_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-gray-400">
                    {entry.quality_correlation !== null
                      ? entry.quality_correlation.toFixed(2)
                      : '-'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <Trophy className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No leaderboard data available</p>
            <p className="mt-1 text-xs text-gray-600">
              Model rankings will appear here once events are processed
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

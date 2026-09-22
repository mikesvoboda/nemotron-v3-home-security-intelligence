# Data Display Patterns

> Patterns for displaying data in tables, cards, lists, and charts.

---

## Overview

The application uses consistent patterns for displaying data across different views. This document covers common patterns for tables, cards, lists, and data visualization.

---

## Card Patterns

### Basic Card Structure

Tremor (`@tremor/react`) is a dependency, but most domain cards (including the real `EventCard` in `frontend/src/components/events/EventCard.tsx`, which takes flat event fields, not an `event` object) use `Card`/`Badge` from Tremor with Tailwind classes. The local component below is illustrative and intentionally named `EventSummaryCard` to avoid shadowing the real `EventCard`:

```tsx
import { Card } from '@tremor/react';

function EventSummaryCard({ event }: { event: Event }) {
  return (
    <Card className="p-4 bg-[#1A1A1A] border-gray-800">
      <div className="flex items-start gap-4">
        <ThumbnailImage src={event.thumbnail} alt={event.title} />
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-medium truncate">{event.title}</h3>
          <p className="text-gray-400 text-sm">{formatDate(event.timestamp)}</p>
          <div className="flex gap-2 mt-2">
            <RiskBadge level={event.riskLevel} />
            <ConfidenceBadge confidence={event.confidence} />
          </div>
        </div>
      </div>
    </Card>
  );
}
```

### Card with Actions

```tsx
function AlertCard({ alert, onAcknowledge, onDismiss }: AlertCardProps) {
  return (
    <Card className="p-4 bg-[#1A1A1A] border-gray-800">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-white font-medium">{alert.title}</h3>
          <p className="text-gray-400 text-sm">{alert.message}</p>
        </div>
        <div className="flex gap-2">
          <IconButton icon={<Check />} label="Acknowledge" onClick={onAcknowledge} />
          <IconButton icon={<X />} label="Dismiss" onClick={onDismiss} />
        </div>
      </div>
    </Card>
  );
}
```

### Card Grid

```tsx
function EntityGrid({ entities }: { entities: Entity[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {entities.map((entity) => (
        <EntityCard key={entity.id} entity={entity} />
      ))}
    </div>
  );
}
```

---

## Table Patterns

### Basic Table

```tsx
import { Table, TableHead, TableRow, TableHeaderCell, TableBody, TableCell } from '@tremor/react';

function AuditTable({ entries }: { entries: AuditEntry[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>Timestamp</TableHeaderCell>
          <TableHeaderCell>Action</TableHeaderCell>
          <TableHeaderCell>User</TableHeaderCell>
          <TableHeaderCell>Details</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {entries.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell>{formatDate(entry.timestamp)}</TableCell>
            <TableCell>{entry.action}</TableCell>
            <TableCell>{entry.user}</TableCell>
            <TableCell className="truncate max-w-xs">{entry.details}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

### Sortable Table

```tsx
function SortableTable<T>({ data, columns }: SortableTableProps<T>) {
  const [sortConfig, setSortConfig] = useState<SortConfig | null>(null);

  const sortedData = useMemo(() => {
    if (!sortConfig) return data;

    return [...data].sort((a, b) => {
      const aValue = a[sortConfig.key];
      const bValue = b[sortConfig.key];

      if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  const handleSort = (key: keyof T) => {
    setSortConfig((current) => ({
      key,
      direction: current?.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  return (
    <Table>
      <TableHead>
        <TableRow>
          {columns.map((column) => (
            <TableHeaderCell
              key={String(column.key)}
              onClick={() => column.sortable && handleSort(column.key)}
              className={column.sortable ? 'cursor-pointer select-none' : ''}
            >
              <span className="flex items-center gap-1">
                {column.label}
                {sortConfig?.key === column.key && <SortIcon direction={sortConfig.direction} />}
              </span>
            </TableHeaderCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {sortedData.map((row, index) => (
          <TableRow key={index}>
            {columns.map((column) => (
              <TableCell key={String(column.key)}>
                {column.render ? column.render(row) : row[column.key]}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

---

## List Patterns

### Virtual List

`VirtualizedList` is generic (`VirtualizedListProps<T>`). Key props: `items`, `renderItem(item, index, measureRef)` (the third argument is the measurement ref that must be attached to each row for dynamic heights), `getItemKey`, `estimateSize` (default 100), `overscan` (default 5), `height`, `gap`, `onEndReached` + `endReachedThreshold` (default 200), `isLoadingMore`, `emptyState`, `footer`.

```tsx
import { VirtualizedList } from '@/components/common';

function EventList({ events }: { events: EventListItem[] }) {
  return (
    <VirtualizedList
      items={events}
      estimateSize={120}
      getItemKey={(event) => event.id}
      renderItem={(event, _index, measureRef) => (
        <div ref={measureRef} key={event.id}>
          {event.summary}
        </div>
      )}
    />
  );
}
```

### Animated List

```tsx
import { AnimatedList } from '@/components/common';

function ActivityFeed({ activities }: { activities: Activity[] }) {
  return (
    <AnimatedList
      items={activities}
      keyExtractor={(item) => item.id}
      renderItem={(activity) => <ActivityItem key={activity.id} activity={activity} />}
    />
  );
}
```

### Infinite Scroll List

`InfiniteScrollStatus` renders the sentinel element itself: pass the `sentinelRef` callback from `useInfiniteScroll`, and it wires up the intersection observer.

```tsx
import { useInfiniteQuery } from '@tanstack/react-query';
import { InfiniteScrollStatus } from '@/components/common';
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll';

function EventTimeline() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['events'],
    queryFn: fetchEvents,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });

  const events = data?.pages.flatMap((page) => page.events) ?? [];

  const { sentinelRef } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: !!hasNextPage,
    isLoading: isFetchingNextPage,
  });

  return (
    <div>
      {events.map((event) => (
        <EventCard key={event.id} {...event} />
      ))}

      <InfiniteScrollStatus
        sentinelRef={sentinelRef}
        isLoading={isFetchingNextPage}
        hasMore={!!hasNextPage}
      />
    </div>
  );
}
```

---

## Chart Patterns

### Area Chart

```tsx
import { AreaChart, Card } from '@tremor/react';

function RiskTrendChart({ data }: { data: RiskDataPoint[] }) {
  return (
    <Card className="bg-[#1A1A1A]">
      <h3 className="text-white font-medium mb-4">Risk Score Trend</h3>
      <AreaChart
        data={data}
        index="date"
        categories={['riskScore']}
        colors={['emerald']}
        valueFormatter={(value) => `${value}%`}
        showLegend={false}
        className="h-72"
      />
    </Card>
  );
}
```

### Bar Chart

```tsx
import { BarChart, Card } from '@tremor/react';

function ObjectDistributionChart({ data }: { data: ObjectCount[] }) {
  return (
    <Card className="bg-[#1A1A1A]">
      <h3 className="text-white font-medium mb-4">Object Distribution</h3>
      <BarChart
        data={data}
        index="objectType"
        categories={['count']}
        colors={['lime']}
        layout="vertical"
        className="h-72"
      />
    </Card>
  );
}
```

### Responsive Chart Wrapper

`ResponsiveChart` takes a `children` render prop receiving `{ width, height }`, sizing options via `dimensionOptions` (`UseChartDimensionsOptions`, e.g. `{ minHeight, maxHeight }`), plus loading/error/empty/fullscreen handling.

```tsx
import { AreaChart } from '@tremor/react';
import { ResponsiveChart } from '@/components/common';

function DashboardChart({ data }: { data: ChartData[] }) {
  return (
    <ResponsiveChart
      title="Risk Trend"
      dimensionOptions={{ minHeight: 200, maxHeight: 400 }}
      isLoading={isLoading}
      isEmpty={!data.length}
    >
      {({ width, height }) => (
        <AreaChart
          data={data}
          index="date"
          categories={['riskScore']}
          colors={['emerald']}
          showLegend={false}
          width={width}
          height={height}
        />
      )}
    </ResponsiveChart>
  );
}
```

---

## Empty States

`EmptyState` takes a Lucide **icon component** (not an element) and an `actions` array of `{ label, onClick, variant? }`.

```tsx
import { Calendar } from 'lucide-react';
import { EmptyState } from '@/components/common';

function EventsList({ events, resetFilters }: { events: Event[]; resetFilters: () => void }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={Calendar}
        title="No events found"
        description="Try adjusting your filters or date range"
        actions={[{ label: 'Reset Filters', onClick: resetFilters, variant: 'primary' }]}
      />
    );
  }

  return (
    // Event list rendering
  );
}
```

---

## Loading States

Skeleton components live in `frontend/src/components/common/skeletons/` (`EventCardSkeleton`, `CameraCardSkeleton`, `ChartSkeleton`, `StatsCardSkeleton`, `TableRowSkeleton`, `AlertCardSkeleton`, `EntityCardSkeleton`) plus the base `Skeleton` primitive. `ErrorState` requires a `title`.

```tsx
function DataDisplay({ isLoading, error, data, refetch }) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState title="Failed to load events" message={error.message} onRetry={refetch} />;
  }

  if (!data?.length) {
    return <EmptyState icon={Inbox} title="No data" description="Nothing to show yet." />;
  }

  return (
    // Render data
  );
}
```

---

## Filtering and Search

There is no generic `SearchInput` / `FilterDropdown` component. The search-and-filter UI is composed from the domain components in `frontend/src/components/events/`: `EventSearch` (controlled input: `value`, `onChange`, `placeholder?`, `showIcon?`) and `EventFilters` (`filters: FilterState`, `onFilterChange`, `cameras?`), with active selections surfaced through `FilterChips`.

```tsx
import { useDeferredValue, useMemo, useState, useTransition } from 'react';
import { EventSearch, EventFilters, FilterChips } from '@/components/events';

function FilterableEventList({ events, cameras }: FilterableEventListProps) {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<FilterState>({});
  const [, startTransition] = useTransition();

  const filteredEvents = useMemo(() => {
    const q = search.toLowerCase();
    return events
      .filter((event) => (!q ? true : event.summary.toLowerCase().includes(q)))
      .filter((event) =>
        Object.entries(filters).every(([key, value]) => !value || event[key] === value)
      );
  }, [events, search, filters]);

  return (
    <div>
      <div className="mb-4 flex gap-4">
        <EventSearch value={search} onChange={setSearch} />
        <EventFilters
          filters={filters}
          cameras={cameras}
          onFilterChange={(next) => startTransition(() => setFilters(next))}
        />
      </div>
      <div>{filteredEvents.map(renderEvent)}</div>
    </div>
  );
}
```

---

## Accessibility

- Tables use proper `<table>` semantics
- Cards use appropriate heading levels
- Empty states have descriptive text
- Charts include text alternatives
- Loading states announce to screen readers
- Interactive elements are keyboard accessible

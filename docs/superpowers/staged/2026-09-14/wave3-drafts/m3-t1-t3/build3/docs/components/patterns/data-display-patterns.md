# Data Display Patterns

> Patterns for displaying data in tables, cards, lists, and charts.

---

## Overview

The application uses consistent patterns for displaying data across different views. This document covers common patterns for tables, cards, lists, and data visualization.

---

## Card Patterns

### Basic Card Structure

```tsx
import { Card } from '@tremor/react';

function EventCard({ event }: { event: Event }) {
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

```tsx
import { VirtualizedList } from '@/components/common';

function EventList({ events }: { events: Event[] }) {
  return (
    <VirtualizedList
      items={events}
      itemHeight={120}
      renderItem={(event) => <EventCard key={event.id} event={event} />}
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

```tsx
function EventTimeline() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['events'],
    queryFn: fetchEvents,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });

  const events = data?.pages.flatMap((page) => page.events) ?? [];

  return (
    <div>
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}

      <InfiniteScrollStatus
        isLoading={isFetchingNextPage}
        hasMore={!!hasNextPage}
        onLoadMore={fetchNextPage}
        itemCount={events.length}
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

```tsx
import { ResponsiveChart } from '@/components/common';

function DashboardChart({ data }: { data: ChartData[] }) {
  return (
    <ResponsiveChart minHeight={200} maxHeight={400}>
      {({ width, height }) => (
        <AreaChart
          data={data}
          width={width}
          height={height}
          // ... chart props
        />
      )}
    </ResponsiveChart>
  );
}
```

---

## Empty States

```tsx
import { EmptyState } from '@/components/common';

function EventsList({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={<Calendar className="h-12 w-12" />}
        title="No events found"
        description="Try adjusting your filters or date range"
        action={
          <Button onClick={resetFilters}>Reset Filters</Button>
        }
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

```tsx
function DataDisplay({ isLoading, error, data }) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        message={error.message}
        onRetry={refetch}
      />
    );
  }

  if (!data?.length) {
    return <EmptyState title="No data" />;
  }

  return (
    // Render data
  );
}
```

---

## Filtering and Search

```tsx
function FilterableList<T>({
  items,
  searchKeys,
  filterConfig,
  renderItem,
}: FilterableListProps<T>) {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Filters>({});

  const filteredItems = useMemo(() => {
    return items
      .filter((item) => {
        // Search filter
        if (search) {
          const searchLower = search.toLowerCase();
          return searchKeys.some((key) => String(item[key]).toLowerCase().includes(searchLower));
        }
        return true;
      })
      .filter((item) => {
        // Active filters
        return Object.entries(filters).every(([key, value]) => {
          if (!value) return true;
          return item[key] === value;
        });
      });
  }, [items, search, filters, searchKeys]);

  return (
    <div>
      <div className="flex gap-4 mb-4">
        <SearchInput value={search} onChange={setSearch} />
        <FilterDropdown config={filterConfig} values={filters} onChange={setFilters} />
      </div>
      <div>{filteredItems.map(renderItem)}</div>
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

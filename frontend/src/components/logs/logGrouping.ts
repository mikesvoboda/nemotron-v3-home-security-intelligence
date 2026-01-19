// Define a minimal LogEntry interface to avoid circular dependency
export interface LogEntryForGrouping {
  id: number;
  timestamp: string;
  level: string;
  component: string;
  message: string;
}

export interface LogGroup<T extends LogEntryForGrouping = LogEntryForGrouping> {
  /** First entry's ID used as group key */
  groupId: number;
  /** Number of entries in this group */
  count: number;
  /** All log entries in this group */
  entries: T[];
  /** The representative log entry (first one) */
  representative: T;
}

/**
 * Groups consecutive log entries with the same message, level, and component
 */
export function groupRepeatedLogs<T extends LogEntryForGrouping>(logs: T[]): LogGroup<T>[] {
  if (logs.length === 0) return [];

  const groups: LogGroup<T>[] = [];
  let currentGroup: LogGroup<T> | null = null;

  for (const log of logs) {
    if (
      currentGroup &&
      currentGroup.representative.message === log.message &&
      currentGroup.representative.level === log.level &&
      currentGroup.representative.component === log.component
    ) {
      // Add to current group
      currentGroup.entries.push(log);
      currentGroup.count++;
    } else {
      // Start a new group
      currentGroup = {
        groupId: log.id,
        count: 1,
        entries: [log],
        representative: log,
      };
      groups.push(currentGroup);
    }
  }

  return groups;
}

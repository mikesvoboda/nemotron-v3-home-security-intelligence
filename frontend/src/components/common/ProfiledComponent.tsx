/**
 * React Profiler wrapper components for performance tracking.
 *
 * Provides a declarative way to measure component render times using
 * React's built-in Profiler API. Metrics are collected and reported
 * via the PerformanceTracker service.
 *
 * Usage:
 *
 *   // Wrapper component approach
 *   import { ProfiledComponent } from '@/components/common/ProfiledComponent';
 *
 *   function MyPage() {
 *     return (
 *       <ProfiledComponent id="ExpensiveWidget">
 *         <ExpensiveWidget data={data} />
 *       </ProfiledComponent>
 *     );
 *   }
 *
 *   // HOC approach
 *   import { withProfiling } from '@/components/common/ProfiledComponent';
 *
 *   const ProfiledEventsTable = withProfiling(EventsTable, 'EventsTable');
 *
 * Note: Profiling has some overhead. By default, it's only enabled in
 * development mode. Use the `enabled` prop to control at runtime.
 */

/* eslint-disable react-refresh/only-export-components */

import { ComponentType, Profiler, ProfilerOnRenderCallback, ReactNode } from 'react';

import { performanceTracker, type RenderPhase } from '@/services/performanceTracker';

/**
 * Props for the ProfiledComponent wrapper.
 */
export interface ProfiledComponentProps {
  /** Unique identifier for this profiled component */
  id: string;
  /** Child components to profile */
  children: ReactNode;
  /** Whether profiling is enabled (default: true if tracker is enabled) */
  enabled?: boolean;
}

/**
 * Wrapper component that profiles its children using React's Profiler API.
 *
 * @example
 * ```tsx
 * <ProfiledComponent id="EventsTable">
 *   <EventsTable events={events} />
 * </ProfiledComponent>
 * ```
 */
export function ProfiledComponent({
  id,
  children,
  enabled = performanceTracker.isEnabled(),
}: ProfiledComponentProps): ReactNode {
  const onRender: ProfilerOnRenderCallback = (
    componentId,
    phase,
    actualDuration,
    baseDuration,
    startTime,
    commitTime
  ) => {
    if (enabled) {
      performanceTracker.recordRender({
        component: componentId,
        phase: phase as RenderPhase,
        actualDuration,
        baseDuration,
        startTime,
        commitTime,
      });
    }
  };

  return (
    <Profiler id={id} onRender={onRender}>
      {children}
    </Profiler>
  );
}

/**
 * Higher-order component that wraps a component with profiling.
 *
 * @param WrappedComponent - Component to wrap with profiling
 * @param componentId - Identifier for the profiled component
 * @param defaultEnabled - Whether profiling is enabled by default
 * @returns Wrapped component with profiling
 *
 * @example
 * ```tsx
 * // Wrap a component
 * const ProfiledEventsTable = withProfiling(EventsTable, 'EventsTable');
 *
 * // Use it like normal
 * <ProfiledEventsTable events={events} onEventClick={handleClick} />
 * ```
 */
export function withProfiling<P extends object>(
  WrappedComponent: ComponentType<P>,
  componentId: string,
  defaultEnabled: boolean = performanceTracker.isEnabled()
): ComponentType<P & { profilingEnabled?: boolean }> {
  // Create the wrapper component
  function ProfiledWrapper(props: P & { profilingEnabled?: boolean }): ReactNode {
    const { profilingEnabled = defaultEnabled, ...componentProps } = props;

    return (
      <ProfiledComponent id={componentId} enabled={profilingEnabled}>
        <WrappedComponent {...(componentProps as P)} />
      </ProfiledComponent>
    );
  }

  // Set display name for debugging
  const wrappedName = WrappedComponent.displayName || WrappedComponent.name || 'Component';
  ProfiledWrapper.displayName = `withProfiling(${wrappedName})`;

  return ProfiledWrapper;
}

/**
 * Hook to manually record render metrics.
 *
 * Useful when you need more control over when metrics are recorded,
 * or when using the Profiler API directly.
 *
 * @returns Function to record a render metric
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const recordRender = useProfiler('MyComponent');
 *
 *   // Record custom timing
 *   useEffect(() => {
 *     const start = performance.now();
 *     // ... expensive operation
 *     const end = performance.now();
 *
 *     recordRender({
 *       phase: 'update',
 *       actualDuration: end - start,
 *       baseDuration: end - start,
 *       startTime: start,
 *       commitTime: end,
 *     });
 *   }, [recordRender]);
 * }
 * ```
 */
export function useProfiler(
  componentId: string
): (metric: Omit<Parameters<typeof performanceTracker.recordRender>[0], 'component'>) => void {
  return (metric) => {
    performanceTracker.recordRender({
      ...metric,
      component: componentId,
    });
  };
}

export default ProfiledComponent;

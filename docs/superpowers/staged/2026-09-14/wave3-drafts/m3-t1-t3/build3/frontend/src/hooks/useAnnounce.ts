/**
 * useAnnounce - Hook for making screen reader announcements.
 *
 * Re-exports the useAnnounce hook from AnnouncementContext for convenience.
 * Use this hook to announce dynamic content changes to screen reader users.
 *
 * Must be used within an AnnouncementProvider.
 *
 * @example
 * import { useAnnounce } from '../hooks/useAnnounce';
 *
 * function MyComponent() {
 *   const { announce } = useAnnounce();
 *
 *   const handleDataLoad = () => {
 *     // Polite announcement (default) - waits for idle
 *     announce('5 new items loaded');
 *   };
 *
 *   const handleError = () => {
 *     // Assertive announcement - interrupts immediately
 *     announce('Error: Connection lost', 'assertive');
 *   };
 *
 *   return (
 *     <div>
 *       <button onClick={handleDataLoad}>Load Data</button>
 *       <button onClick={handleError}>Simulate Error</button>
 *     </div>
 *   );
 * }
 */

export { useAnnounce } from '../contexts/AnnouncementContext';
export type { AnnouncementContextType } from '../contexts/AnnouncementContext';

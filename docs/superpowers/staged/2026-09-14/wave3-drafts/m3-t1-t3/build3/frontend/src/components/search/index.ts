/**
 * Search Components
 *
 * Components for full-text event search functionality:
 * - SearchBar: Input with advanced filters and query syntax help
 * - SearchResultCard: Individual search result display with relevance score
 * - SearchResultsPanel: Grid of search results with pagination
 */

export { default as SearchBar } from './SearchBar';
export type { SearchBarProps, SearchFilters } from './SearchBar';

export { default as SearchResultCard } from './SearchResultCard';
export type { SearchResultCardProps } from './SearchResultCard';

export { default as SearchResultsPanel } from './SearchResultsPanel';
export type { SearchResultsPanelProps } from './SearchResultsPanel';

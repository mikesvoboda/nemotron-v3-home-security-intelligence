# Search Components Directory

## Purpose

Contains components for full-text search functionality across security events. Provides a search bar with advanced filter options, result cards with matched text highlighting, and a paginated results panel integrated with the EventTimeline.

## Files

| File                          | Purpose                              |
| ----------------------------- | ------------------------------------ |
| `SearchBar.tsx`               | Search input with expandable filters |
| `SearchBar.test.tsx`          | Test suite for SearchBar             |
| `SearchResultCard.tsx`        | Individual search result display     |
| `SearchResultCard.test.tsx`   | Test suite for SearchResultCard      |
| `SearchResultsPanel.tsx`      | Paginated results container          |
| `SearchResultsPanel.test.tsx` | Test suite for SearchResultsPanel    |
| `index.ts`                    | Barrel exports                       |

## Key Components

### SearchBar.tsx

**Purpose:** Search input with expandable advanced filter options

**Key Features:**

- Text input with search icon and submit button
- Expandable advanced filters panel (toggle via chevron button)
- Filter options:
  - Camera dropdown (populated from parent)
  - Severity/risk level dropdown (low/medium/high/critical)
  - Object type dropdown (person/vehicle/animal/package/other)
  - Review status dropdown (all/unreviewed/reviewed)
  - Date range pickers (start date, end date)
- Submit on Enter key or button click
- Loading state indicator (spinner in search button)
- Clear individual filters or all filters
- "Active" indicator when filters are applied
- NVIDIA dark theme styling

**Props:**

```typescript
interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string, filters: SearchFilters) => void;
  isSearching: boolean;
  cameras: Camera[];
  initialFilters?: SearchFilters;
  placeholder?: string;
  className?: string;
}

interface SearchFilters {
  camera_id?: string;
  start_date?: string;
  end_date?: string;
  severity?: string;
  object_type?: string;
  reviewed?: boolean;
}
```

### SearchResultCard.tsx

**Purpose:** Compact card displaying a single search result with matched text highlighting

**Key Features:**

- Camera name and timestamp display
- Risk score badge with color coding
- AI-generated summary text
- Matched text snippet with highlighting (bold keywords)
- Detection count indicator
- Click to view event details
- Hover effect on card border
- NVIDIA green accent for highlights

**Props:**

```typescript
interface SearchResultCardProps {
  result: SearchResult;
  onClick?: (eventId: number) => void;
}

interface SearchResult {
  id: number;
  camera_name: string;
  started_at: string;
  risk_score: number;
  risk_level: string;
  summary: string;
  matched_text?: string;
  detection_count: number;
}
```

### SearchResultsPanel.tsx

**Purpose:** Container for displaying search results with pagination controls

**Key Features:**

- Grid layout for result cards (responsive: 1 col -> 2 cols -> 3 cols)
- Loading spinner state with pulsing animation
- Error message display with retry option
- Empty state with helpful message and icon
- Pagination controls:
  - Previous/Next buttons with disabled states
  - "Showing X-Y of Z results" display
  - Page number calculation
- Clear search button to exit search mode
- Search query display for context

**Props:**

```typescript
interface SearchResultsPanelProps {
  results: SearchResult[];
  totalCount: number;
  offset: number;
  limit: number;
  isLoading: boolean;
  error?: string | null;
  onPageChange: (newOffset: number) => void;
  onResultClick?: (eventId: number) => void;
  onClearSearch?: () => void;
  searchQuery?: string;
  className?: string;
}
```

## Component Hierarchy

```
EventTimeline (parent)
├── SearchBar
│   ├── Search input
│   ├── Submit button
│   └── Advanced filters panel (collapsible)
│       ├── Camera dropdown
│       ├── Severity dropdown
│       ├── Object type dropdown
│       ├── Review status dropdown
│       └── Date range pickers
└── SearchResultsPanel (conditional: isSearchMode)
    ├── Results count display
    ├── Clear search button
    ├── SearchResultCard[] (grid layout)
    └── Pagination controls
```

## Important Patterns

### Search Flow

```
User types query -> onQueryChange updates parent state
User clicks search or presses Enter -> onSearch(query, filters)
Parent calls API -> fetchSearchResults(query, filters)
Results returned -> SearchResultsPanel displays results
User clicks result -> onResultClick(eventId)
Parent opens EventDetailModal
```

### Filter State Management

SearchBar maintains local filter state:

```typescript
const [localFilters, setLocalFilters] = useState<SearchFilters>(initialFilters || {});
const [showAdvanced, setShowAdvanced] = useState(false);

// Filters applied on search submit, not on change
const handleSearch = () => {
  onSearch(query, localFilters);
};
```

### Matched Text Highlighting

SearchResultCard highlights matched terms:

```typescript
// matched_text contains text with <mark> tags from backend
<p dangerouslySetInnerHTML={{ __html: result.matched_text }} />
```

## Styling Conventions

### SearchBar

- Container: `bg-[#1F1F1F]`, `border-gray-800`
- Input: `bg-[#1A1A1A]`, `border-gray-700`, `focus:border-[#76B900]`
- Search button: `bg-[#76B900]`, `hover:bg-[#6aa300]`
- Advanced panel: `bg-[#1A1A1A]`, `border-t border-gray-800`
- Filter dropdowns: same as input styling

### SearchResultCard

- Card: `bg-[#1F1F1F]`, `border-gray-800`, `hover:border-gray-700`
- Risk badge: uses `getRiskColor()` utility
- Matched text highlight: `bg-[#76B900]/20`, `text-[#76B900]`
- Camera name: `text-gray-400`
- Summary: `text-gray-300`

### SearchResultsPanel

- Container: `bg-[#1F1F1F]`, `border-gray-800`
- Loading spinner: `border-t-[#76B900]`
- Pagination buttons: `bg-[#1A1A1A]`, `hover:bg-[#76B900]/10`
- Empty state icon: `text-gray-600`
- Clear button: `text-[#76B900]`, `hover:underline`

## Testing

Comprehensive test coverage:

- `SearchBar.test.tsx` - Input handling, Enter key submit, filter toggles, loading state
- `SearchResultCard.test.tsx` - Rendering, click handling, matched text display
- `SearchResultsPanel.test.tsx` - Pagination, empty/error states, result clicks

```bash
# Run search component tests
cd frontend && npm test -- --grep "Search"
```

Test coverage should include:

- Search submission on Enter key
- Filter state management
- Pagination behavior (next/previous, boundary conditions)
- Empty and error states
- Result click handling
- Loading state transitions

## Entry Points

**Start here:** `SearchBar.tsx` - Understand search input and filter interface
**Then explore:** `SearchResultsPanel.tsx` - See results container and pagination
**Finally:** `SearchResultCard.tsx` - Learn result display pattern

## Dependencies

- `lucide-react` - Icons (Search, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, FileSearch, XCircle, Filter, Calendar)
- `clsx` - Conditional class composition
- `react` - useState, useEffect
- `../../services/api` - SearchResult type, Camera type
- `../../utils/risk` - getRiskColor, getRiskLevel utilities

## API Integration

Search components work with these API endpoints (called by parent):

- `GET /api/events/search` - Full-text search with filters
  - Query params: `q`, `camera_id`, `start_date`, `end_date`, `severity`, `object_type`, `reviewed`, `limit`, `offset`
  - Returns: `{ results: SearchResult[], total_count: number }`

## Future Enhancements

- Search suggestions/autocomplete
- Recent searches history
- Saved search filters
- Search within specific fields (camera, summary, etc.)
- Regex search support
- Search result sorting options
- Export search results
- Keyboard navigation through results

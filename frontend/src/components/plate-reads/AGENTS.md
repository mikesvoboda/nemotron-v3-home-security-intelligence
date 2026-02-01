# Plate Reads Components

License Plate Recognition (LPR/ALPR) UI components for the home security monitoring dashboard.

## Purpose

This directory contains React components for viewing, searching, and analyzing license plate recognition data. The ALPR system detects license plates from camera feeds and performs OCR to extract plate text.

## Key Files

| File | Purpose |
|------|---------|
| `index.ts` | Barrel exports for the module |
| `PlateReadsPage.tsx` | Main page component with statistics and table |

## Related Files

| File | Purpose |
|------|---------|
| `frontend/src/types/plateRead.ts` | TypeScript type definitions |
| `frontend/src/services/plateReadsApi.ts` | API client for plate read endpoints |
| `backend/api/routes/plate_reads.py` | Backend API endpoints |
| `backend/api/schemas/plate_read.py` | Backend Pydantic schemas |
| `backend/services/plate_detector.py` | Plate detection service |

## Features

### Implemented
- Basic page structure with navigation
- Type definitions matching backend schemas
- API client with full CRUD operations

### Planned
- Statistics cards (total reads, unique plates, confidence metrics)
- Search by plate text (partial and exact match)
- Filterable/sortable data table
- Date range filtering
- Camera-specific views
- Detail modal with plate image and metadata
- Export functionality

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/plate-reads` | List plate reads with filters |
| GET | `/api/plate-reads/stats` | Aggregate statistics |
| GET | `/api/plate-reads/search` | Search by plate text |
| GET | `/api/plate-reads/{id}` | Get single plate read |

## Type Definitions

Key types from `frontend/src/types/plateRead.ts`:

```typescript
interface PlateRead {
  id: number;
  camera_id: string;
  timestamp: string;
  plate_text: string;
  raw_text: string;
  detection_confidence: number;
  ocr_confidence: number;
  bbox: [number, number, number, number];
  image_quality_score: number;
  is_enhanced: boolean;
  is_blurry: boolean;
  created_at: string;
}

interface PlateStatisticsResponse {
  total_reads: number;
  unique_plates: number;
  avg_ocr_confidence: number;
  avg_quality_score: number;
  enhanced_count: number;
  blurry_count: number;
  reads_last_hour: number;
  reads_last_24h: number;
}
```

## Testing

Run component tests:
```bash
cd frontend && npm test -- --testPathPattern=plate-reads
```

Run type checking:
```bash
cd frontend && npm run typecheck
```

## Entry Points

- **Navigation**: Sidebar under ANALYTICS group as "Plate Reads"
- **Route**: `/plate-reads`
- **Component**: `PlateReadsPage` (lazy-loaded)

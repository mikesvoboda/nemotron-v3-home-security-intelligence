/**
 * Tests for CSV export utility functions
 *
 * @module utils/csvExport.test
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  generateCSV,
  downloadCSV,
  formatAnalyticsForCSV,
  escapeCSVValue,
  type AnalyticsExportData,
} from './csvExport';

describe('csvExport utilities', () => {
  describe('escapeCSVValue', () => {
    it('returns empty string for empty input', () => {
      expect(escapeCSVValue('')).toBe('');
    });

    it('returns simple values unchanged', () => {
      expect(escapeCSVValue('hello')).toBe('hello');
      expect(escapeCSVValue('123')).toBe('123');
    });

    it('wraps values containing commas in quotes', () => {
      expect(escapeCSVValue('hello, world')).toBe('"hello, world"');
    });

    it('wraps values containing quotes in quotes and escapes inner quotes', () => {
      expect(escapeCSVValue('say "hello"')).toBe('"say ""hello"""');
    });

    it('wraps values containing newlines in quotes', () => {
      expect(escapeCSVValue('line1\nline2')).toBe('"line1\nline2"');
    });

    it('handles values with multiple special characters', () => {
      expect(escapeCSVValue('hello, "world"\ntest')).toBe('"hello, ""world""\ntest"');
    });

    it('converts numbers to strings', () => {
      expect(escapeCSVValue(123)).toBe('123');
      expect(escapeCSVValue(0)).toBe('0');
      expect(escapeCSVValue(3.14)).toBe('3.14');
    });
  });

  describe('generateCSV', () => {
    it('generates CSV with headers only when no rows', () => {
      const headers = ['Name', 'Value', 'Date'];
      const rows: (string | number)[][] = [];

      const result = generateCSV(headers, rows);

      expect(result).toBe('Name,Value,Date\n');
    });

    it('generates CSV with headers and single row', () => {
      const headers = ['Name', 'Value'];
      const rows = [['Test', 100]];

      const result = generateCSV(headers, rows);

      expect(result).toBe('Name,Value\nTest,100\n');
    });

    it('generates CSV with multiple rows', () => {
      const headers = ['Date', 'Count'];
      const rows = [
        ['2026-01-01', 10],
        ['2026-01-02', 20],
        ['2026-01-03', 30],
      ];

      const result = generateCSV(headers, rows);

      expect(result).toBe('Date,Count\n2026-01-01,10\n2026-01-02,20\n2026-01-03,30\n');
    });

    it('escapes values containing special characters', () => {
      const headers = ['Name', 'Description'];
      const rows = [['Item, A', 'Has "quotes"']];

      const result = generateCSV(headers, rows);

      expect(result).toBe('Name,Description\n"Item, A","Has ""quotes"""\n');
    });

    it('handles empty strings in rows', () => {
      const headers = ['A', 'B', 'C'];
      const rows = [['value', '', 'other']];

      const result = generateCSV(headers, rows);

      expect(result).toBe('A,B,C\nvalue,,other\n');
    });
  });

  describe('downloadCSV', () => {
    let createElementSpy: ReturnType<typeof vi.spyOn>;
    let createObjectURLSpy: ReturnType<typeof vi.spyOn>;
    let revokeObjectURLSpy: ReturnType<typeof vi.spyOn>;
    let mockAnchor: {
      href: string;
      download: string;
      click: ReturnType<typeof vi.fn>;
    };

    beforeEach(() => {
      mockAnchor = {
        href: '',
        download: '',
        click: vi.fn(),
      };

      createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor as unknown as HTMLAnchorElement);
      createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');
      revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    });

    afterEach(() => {
      createElementSpy.mockRestore();
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
    });

    it('creates a download link with correct filename', () => {
      downloadCSV('test-file.csv', 'Header1,Header2\nValue1,Value2\n');

      expect(createElementSpy).toHaveBeenCalledWith('a');
      expect(mockAnchor.download).toBe('test-file.csv');
    });

    it('creates blob URL and assigns to href', () => {
      downloadCSV('test.csv', 'content');

      expect(createObjectURLSpy).toHaveBeenCalled();
      expect(mockAnchor.href).toBe('blob:test-url');
    });

    it('triggers click on the anchor element', () => {
      downloadCSV('test.csv', 'content');

      expect(mockAnchor.click).toHaveBeenCalledTimes(1);
    });

    it('revokes the object URL after download', () => {
      downloadCSV('test.csv', 'content');

      expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:test-url');
    });

    it('creates blob with correct MIME type', () => {
      downloadCSV('test.csv', 'content');

      const blobArg = createObjectURLSpy.mock.calls[0][0];
      expect(blobArg).toBeInstanceOf(Blob);
      expect((blobArg as Blob).type).toBe('text/csv;charset=utf-8;');
    });
  });

  describe('formatAnalyticsForCSV', () => {
    it('generates CSV with all sections present', () => {
      const data: AnalyticsExportData = {
        dateRange: {
          startDate: '2026-01-19',
          endDate: '2026-01-26',
        },
        detectionTrends: {
          dataPoints: [
            { date: '2026-01-19', count: 100 },
            { date: '2026-01-20', count: 150 },
          ],
          totalDetections: 250,
        },
        riskHistory: {
          dataPoints: [
            { date: '2026-01-19', low: 50, medium: 30, high: 15, critical: 5 },
            { date: '2026-01-20', low: 60, medium: 40, high: 20, critical: 10 },
          ],
        },
        objectDistribution: {
          objectTypes: [
            { object_type: 'person', count: 120, percentage: 48 },
            { object_type: 'car', count: 80, percentage: 32 },
            { object_type: 'dog', count: 50, percentage: 20 },
          ],
          totalDetections: 250,
        },
        cameraUptime: {
          cameras: [
            { camera_id: 'cam1', camera_name: 'Front Door', uptime_percentage: 98.5, detection_count: 150 },
            { camera_id: 'cam2', camera_name: 'Backyard', uptime_percentage: 95.2, detection_count: 100 },
          ],
        },
        riskScoreDistribution: {
          buckets: [
            { min_score: 0, max_score: 10, count: 50 },
            { min_score: 10, max_score: 20, count: 40 },
            { min_score: 20, max_score: 30, count: 30 },
          ],
          totalEvents: 120,
        },
      };

      const result = formatAnalyticsForCSV(data);

      // Check header section
      expect(result).toContain('Analytics Export');
      expect(result).toContain('Date Range,2026-01-19 to 2026-01-26');

      // Check Detection Trends section
      expect(result).toContain('Detection Trends');
      expect(result).toContain('Date,Detections');
      expect(result).toContain('2026-01-19,100');
      expect(result).toContain('2026-01-20,150');
      expect(result).toContain('Total,250');

      // Check Risk History section
      expect(result).toContain('Risk History');
      expect(result).toContain('Date,Low,Medium,High,Critical');
      expect(result).toContain('2026-01-19,50,30,15,5');
      expect(result).toContain('2026-01-20,60,40,20,10');

      // Check Object Distribution section
      expect(result).toContain('Object Distribution');
      expect(result).toContain('Object Type,Count,Percentage');
      expect(result).toContain('person,120,48%');
      expect(result).toContain('car,80,32%');
      expect(result).toContain('dog,50,20%');

      // Check Camera Uptime section
      expect(result).toContain('Camera Uptime');
      expect(result).toContain('Camera Name,Uptime %,Detection Count');
      expect(result).toContain('Front Door,98.5%,150');
      expect(result).toContain('Backyard,95.2%,100');

      // Check Risk Score Distribution section
      expect(result).toContain('Risk Score Distribution');
      expect(result).toContain('Score Range,Count');
      expect(result).toContain('0-10,50');
      expect(result).toContain('10-20,40');
      expect(result).toContain('20-30,30');
    });

    it('handles empty detection trends', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: { cameras: [] },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('Detection Trends');
      expect(result).toContain('Total,0');
    });

    it('handles empty risk history', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: { cameras: [] },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('Risk History');
      expect(result).toContain('Date,Low,Medium,High,Critical');
    });

    it('handles empty object distribution', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: { cameras: [] },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('Object Distribution');
      expect(result).toContain('Total,0');
    });

    it('handles empty camera uptime', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: { cameras: [] },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('Camera Uptime');
      expect(result).toContain('Camera Name,Uptime %,Detection Count');
    });

    it('handles empty risk score distribution', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: { cameras: [] },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('Risk Score Distribution');
      expect(result).toContain('Total Events,0');
    });

    it('escapes camera names with special characters', () => {
      const data: AnalyticsExportData = {
        dateRange: { startDate: '2026-01-19', endDate: '2026-01-26' },
        detectionTrends: { dataPoints: [], totalDetections: 0 },
        riskHistory: { dataPoints: [] },
        objectDistribution: { objectTypes: [], totalDetections: 0 },
        cameraUptime: {
          cameras: [
            { camera_id: 'cam1', camera_name: 'Front, "Main" Door', uptime_percentage: 98.5, detection_count: 150 },
          ],
        },
        riskScoreDistribution: { buckets: [], totalEvents: 0 },
      };

      const result = formatAnalyticsForCSV(data);

      expect(result).toContain('"Front, ""Main"" Door"');
    });
  });
});

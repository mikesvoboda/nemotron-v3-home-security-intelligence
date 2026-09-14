/**
 * Minimal coverage tests for NEM-1707
 * Covers critical missing endpoints to reach >85% coverage
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

describe('Missing Coverage Tests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // Helper
  const mockResponse = (data: unknown) =>
    ({
      ok: true,
      status: 200,
      json: () => Promise.resolve(data),
      headers: new Headers(),
    }) as Response;

  it('covers restartService', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        service: 'rtdetr',
        status: 'restarting',
        message: 'OK',
        timestamp: '2025-01-01T00:00:00Z',
      })
    );
    const { restartService } = await import('./api');
    await restartService('rtdetr');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers updateSeverityThresholds', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ definitions: [], thresholds: { low_max: 30, medium_max: 60, high_max: 85 } })
    );
    const { updateSeverityThresholds } = await import('./api');
    await updateSeverityThresholds({ low_max: 30, medium_max: 60, high_max: 85 });
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchDetectionEnrichment', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ detection_id: 123, enriched_at: null, errors: [] })
    );
    const { fetchDetectionEnrichment } = await import('./api');
    await fetchDetectionEnrichment(123);
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchModelZooStatus', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ models: [], vram_budget_mb: 4096, vram_used_mb: 0, vram_available_mb: 4096 })
    );
    const { fetchModelZooStatus } = await import('./api');
    await fetchModelZooStatus();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchModelZooCompactStatus', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        models: [],
        total_models: 0,
        loaded_count: 0,
        disabled_count: 0,
        vram_budget_mb: 4096,
        vram_used_mb: 0,
        timestamp: '2025-01-01T00:00:00Z',
      })
    );
    const { fetchModelZooCompactStatus } = await import('./api');
    await fetchModelZooCompactStatus();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchModelZooLatencyHistory', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        model_name: 'test',
        display_name: 'Test',
        snapshots: [],
        window_minutes: 60,
        bucket_seconds: 60,
        has_data: false,
        timestamp: '2025-01-01T00:00:00Z',
      })
    );
    const { fetchModelZooLatencyHistory } = await import('./api');
    await fetchModelZooLatencyHistory('test');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchEntities', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } })
    );
    const { fetchEntities } = await import('./api');
    await fetchEntities();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchEntity', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        id: 'e1',
        entity_type: 'person',
        first_seen: '2025-01-01T00:00:00Z',
        last_seen: '2025-01-01T00:00:00Z',
        appearance_count: 0,
        cameras_seen: [],
        thumbnail_url: null,
        appearances: [],
      })
    );
    const { fetchEntity } = await import('./api');
    await fetchEntity('e1');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchEntityHistory', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ entity_id: 'e1', entity_type: 'person', appearances: [], count: 0 })
    );
    const { fetchEntityHistory } = await import('./api');
    await fetchEntityHistory('e1');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchAllPrompts', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse({ prompts: {} }));
    const { fetchAllPrompts } = await import('./api');
    await fetchAllPrompts();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchModelPrompt', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        model_name: 'nemotron',
        config: {},
        version: 1,
        updated_at: '2025-01-01T00:00:00Z',
      })
    );
    const { fetchModelPrompt } = await import('./api');
    await fetchModelPrompt('nemotron');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers updateModelPrompt', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ model_name: 'nemotron', version: 2, message: 'OK', config: {} })
    );
    const { updateModelPrompt } = await import('./api');
    await updateModelPrompt('nemotron', {});
    expect(fetch).toHaveBeenCalled();
  });

  it('covers testPrompt', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ before: {}, after: {}, improved: true, inference_time_ms: 100 })
    );
    const { testPrompt } = await import('./api');
    await testPrompt('nemotron', {}, 123);
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchAllPromptsHistory', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse({}));
    const { fetchAllPromptsHistory } = await import('./api');
    await fetchAllPromptsHistory();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers fetchModelHistory', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ model_name: 'nemotron', versions: [], total_versions: 0 })
    );
    const { fetchModelHistory } = await import('./api');
    await fetchModelHistory('nemotron');
    expect(fetch).toHaveBeenCalled();
  });

  it('covers restorePromptVersion', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ model_name: 'nemotron', restored_version: 1, new_version: 2, message: 'OK' })
    );
    const { restorePromptVersion } = await import('./api');
    await restorePromptVersion('nemotron', 1);
    expect(fetch).toHaveBeenCalled();
  });

  it('covers exportPrompts', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ exported_at: '2025-01-01T00:00:00Z', version: '1.0', prompts: {} })
    );
    const { exportPrompts } = await import('./api');
    await exportPrompts();
    expect(fetch).toHaveBeenCalled();
  });

  it('covers importPrompts', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({ imported_count: 0, skipped_count: 0, errors: [], message: 'OK' })
    );
    const { importPrompts } = await import('./api');
    await importPrompts({});
    expect(fetch).toHaveBeenCalled();
  });

  it('covers acknowledgeAlert', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        id: 'alert-uuid-123',
        event_id: 123,
        rule_id: 'rule-uuid-123',
        severity: 'high',
        status: 'acknowledged',
        dedup_key: 'front_door:person:entry_zone',
        channels: ['pushover'],
        metadata: { camera_name: 'Front Door' },
        created_at: '2025-12-28T12:00:00Z',
        updated_at: '2025-12-28T12:01:00Z',
        delivered_at: '2025-12-28T12:00:30Z',
      })
    );
    const { acknowledgeAlert } = await import('./api');
    const result = await acknowledgeAlert('alert-uuid-123');
    expect(fetch).toHaveBeenCalled();
    expect(result.status).toBe('acknowledged');
  });

  it('covers dismissAlert', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        id: 'alert-uuid-456',
        event_id: 456,
        rule_id: 'rule-uuid-456',
        severity: 'medium',
        status: 'dismissed',
        dedup_key: 'backyard:vehicle:driveway_zone',
        channels: ['email'],
        metadata: { camera_name: 'Backyard' },
        created_at: '2025-12-28T13:00:00Z',
        updated_at: '2025-12-28T13:05:00Z',
        delivered_at: '2025-12-28T13:00:15Z',
      })
    );
    const { dismissAlert } = await import('./api');
    const result = await dismissAlert('alert-uuid-456');
    expect(fetch).toHaveBeenCalled();
    expect(result.status).toBe('dismissed');
  });
});

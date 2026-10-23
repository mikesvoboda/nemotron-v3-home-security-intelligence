import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  CHORD_ROUTES,
  EASY_HUBS,
  ADVANCED_HUBS,
  HUBS,
  hubForPath,
  modeOfPath,
  tabForPath,
} from './surfaces';

describe('surfaces registry (F4.9)', () => {
  it('defines five Easy hubs first, followed by four Advanced hubs', () => {
    expect(EASY_HUBS).toHaveLength(5);
    expect(ADVANCED_HUBS).toHaveLength(4);
    expect(HUBS).toHaveLength(9);

    expect(HUBS.slice(0, 5).map((h) => h.id)).toEqual([
      'dashboard',
      'timeline-search',
      'alerts-rules',
      'household',
      'settings',
    ]);
    expect(HUBS.slice(5).map((h) => h.id)).toEqual([
      'ai-workbench',
      'gpu-models',
      'entities-reid',
      'operations-monitoring',
    ]);
  });

  it('ensures every hub has non-empty tabs and no duplicate tab paths across the registry', () => {
    const seenPaths = new Set<string>();
    for (const hub of HUBS) {
      expect(hub.tabs.length).toBeGreaterThan(0);
      for (const tab of hub.tabs) {
        expect(seenPaths.has(tab.path), `duplicate tab path ${tab.path}`).toBe(false);
        seenPaths.add(tab.path);
      }
    }
  });

  it('maps every routed page in App.tsx (except /login, /setup, /events/:eventId, *) to exactly one hub', () => {
    const appSource = readFileSync(path.resolve(__dirname, '../App.tsx'), 'utf-8');
    const routeRegex = /<Route\s+[^>]*path="([^"]+)"/g;
    const rawPaths: string[] = [];
    let match: RegExpExecArray | null;
    while ((match = routeRegex.exec(appSource)) !== null) {
      rawPaths.push(match[1]);
    }

    const excluded = new Set(['/login', '/setup', '/*', '/events/:eventId', '*']);
    const routedPaths: string[] = [];
    for (const p of rawPaths) {
      if (excluded.has(p)) continue;
      if (!p.startsWith('/')) {
        routedPaths.push(`/settings/${p}`);
      } else {
        routedPaths.push(p);
      }
    }

    expect(routedPaths.length).toBeGreaterThan(25);
    for (const routePath of routedPaths) {
      const hub = hubForPath(routePath);
      expect(hub, `routed path ${routePath} should map to a hub`).toBeDefined();
    }

    // Excluded routes belong to no hub
    expect(hubForPath('/login')).toBeUndefined();
    expect(hubForPath('/setup')).toBeUndefined();
    expect(hubForPath('/events/42')).toBeUndefined();
    expect(hubForPath('/nonexistent-route')).toBeUndefined();
  });

  it('matches / and /settings exactly, and matches other tab paths by segment with longest match winning', () => {
    expect(hubForPath('/')?.id).toBe('dashboard');
    expect(hubForPath('/settings')?.id).toBe('settings');
    expect(hubForPath('/settings/unknown')).toBeUndefined();

    // Longest-prefix segment disambiguation under /settings/*
    expect(hubForPath('/settings/cameras')?.id).toBe('settings');
    expect(hubForPath('/settings/rules')?.id).toBe('alerts-rules');
    expect(hubForPath('/settings/prompts')?.id).toBe('ai-workbench');
    expect(hubForPath('/settings/ai-models')?.id).toBe('gpu-models');
    expect(hubForPath('/settings/gpu')?.id).toBe('gpu-models');
    expect(hubForPath('/settings/admin')?.id).toBe('operations-monitoring');

    // Segment boundary check: /alerts/123 matches /alerts, but /alerts-extra does not
    expect(hubForPath('/alerts/123')?.id).toBe('alerts-rules');
    expect(hubForPath('/alerts-extra')).toBeUndefined();
    expect(tabForPath('/settings/rules')?.tab.path).toBe('/settings/rules');
  });

  it('returns the mode of a path via modeOfPath', () => {
    expect(modeOfPath('/')).toBe('easy');
    expect(modeOfPath('/timeline')).toBe('easy');
    expect(modeOfPath('/settings/rules')).toBe('easy');
    expect(modeOfPath('/operations')).toBe('advanced');
    expect(modeOfPath('/settings/admin')).toBe('advanced');
    expect(modeOfPath('/ai')).toBe('advanced');
    expect(modeOfPath('/unknown')).toBeUndefined();
  });

  it('carries tour targets on Timeline & Search and Settings hubs and derives CHORD_ROUTES', () => {
    const timelineHub = HUBS.find((h) => h.id === 'timeline-search');
    const settingsHub = HUBS.find((h) => h.id === 'settings');
    expect(timelineHub?.dataTour).toBe('timeline-link');
    expect(settingsHub?.dataTour).toBe('settings-link');

    expect(CHORD_ROUTES).toMatchObject({
      d: '/',
      t: '/timeline',
      a: '/alerts',
      s: '/settings',
      n: '/analytics',
      e: '/entities',
      o: '/logs',
      y: '/operations',
    });
  });
});

import { describe, it, expect } from 'vitest';

import { PAGE_DOCUMENTATION } from './pageDocumentation';

describe('pageDocumentation', () => {
  it('exports PAGE_DOCUMENTATION config object', () => {
    expect(PAGE_DOCUMENTATION).toBeDefined();
    expect(typeof PAGE_DOCUMENTATION).toBe('object');
  });

  it('has config for dashboard route', () => {
    const config = PAGE_DOCUMENTATION['/'];
    expect(config).toBeDefined();
    expect(config.label).toBe('Dashboard');
    expect(config.docPath).toMatch(/docs\/ui\/dashboard\.md$/);
  });

  it('has config for all main routes', () => {
    const expectedRoutes = [
      '/',
      '/timeline',
      '/entities',
      '/alerts',
      '/audit',
      '/analytics',
      '/jobs',
      '/ai-audit',
      '/ai',
      '/operations',
      '/trash',
      '/logs',
      '/settings',
    ];

    expectedRoutes.forEach((route) => {
      expect(PAGE_DOCUMENTATION[route]).toBeDefined();
      expect(PAGE_DOCUMENTATION[route].label).toBeTruthy();
      expect(PAGE_DOCUMENTATION[route].docPath).toMatch(/^docs\/ui\/.+\.md$/);
    });
  });

  it('does not have config for dev-tools route', () => {
    expect(PAGE_DOCUMENTATION['/dev-tools']).toBeUndefined();
  });
});

import { describe, expect, it } from 'vitest';

import { buildSearchContextKey } from './searchContext';

describe('buildSearchContextKey', () => {
  it('changes when page changes so stale auto-compare state is cleared on search navigation', () => {
    const first = buildSearchContextKey({ page: 1, size: 20, county: 'Dublin', sort_by: 'created_at', sort_dir: 'desc' });
    const second = buildSearchContextKey({ page: 2, size: 20, county: 'Dublin', sort_by: 'created_at', sort_dir: 'desc' });

    expect(first).not.toBe(second);
  });

  it('changes when search filters change so stale auto-compare state cannot rehydrate into a new search', () => {
    const first = buildSearchContextKey({ page: 1, size: 20, county: 'Dublin', keywords: 'garden' });
    const second = buildSearchContextKey({ page: 1, size: 20, county: 'Cork', keywords: 'garden' });

    expect(first).not.toBe(second);
  });
});
import { describe, expect, it } from 'vitest';
import type { FolderCacheEntry } from './files';
import { getFolderCacheKey, selectFolderCacheForMode } from './files';

function cacheEntry(label: string): FolderCacheEntry {
  return {
    items: [{ name: label, type: 'directory', path: `/${label}` }],
    total: 1,
    offset: 1,
    has_more: false,
    loaded_at: 1,
    dirty: false,
    loading: false,
  };
}

describe('file store cache helpers', () => {
  it('separates folder cache entries by explorer mode', () => {
    const entries = {
      [getFolderCacheKey('user', '/')]: cacheEntry('user-root'),
      [getFolderCacheKey('developer', '/')]: cacheEntry('developer-root'),
    };

    expect(selectFolderCacheForMode(entries, 'user')['/'].items[0].name).toBe('user-root');
    expect(selectFolderCacheForMode(entries, 'developer')['/'].items[0].name).toBe('developer-root');
  });
});

import { describe, expect, it } from 'vitest';

import { buildExplorerRows, getVirtualExplorerRows } from './workspaceExplorerRows';
import type { FolderCacheEntry, TreeNode } from '../stores/files';

const cache = (hasMore = false): FolderCacheEntry => ({
  items: [],
  total: 0,
  offset: 0,
  has_more: hasMore,
  loaded_at: 0,
  dirty: false,
  loading: false,
});

describe('workspaceExplorerRows', () => {
  it('flattens expanded tree nodes with create and load-more rows', () => {
    const nodes: TreeNode[] = [
      {
        name: 'docs',
        type: 'directory',
        path: '/docs',
        expanded: true,
        children: [{ name: 'readme.md', type: 'file', path: '/docs/readme.md' }],
      },
    ];

    const rows = buildExplorerRows(nodes, { '/docs': cache(true) }, true, '/docs');

    expect(rows.map((row) => row.key)).toEqual([
      'node:/docs',
      'new-folder:/docs',
      'node:/docs/readme.md',
      'load-more:/docs',
    ]);
  });

  it('returns a stable virtual window', () => {
    const rows = Array.from({ length: 100 }, (_, index) => ({
      key: `row-${index}`,
      kind: 'load-more' as const,
      path: '/',
      depth: 0,
    }));

    const virtual = getVirtualExplorerRows(rows, 300, 120, 30, 2);

    expect(virtual.rows[0].key).toBe('row-8');
    expect(virtual.totalHeight).toBe(3000);
    expect(virtual.translateY).toBe(240);
  });
});

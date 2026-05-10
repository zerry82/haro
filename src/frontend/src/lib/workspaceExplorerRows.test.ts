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

  it('keeps rows visible when scrollTop is stale after the tree shrinks', () => {
    const rows = Array.from({ length: 3 }, (_, index) => ({
      key: `row-${index}`,
      kind: 'load-more' as const,
      path: '/',
      depth: 0,
    }));

    const virtual = getVirtualExplorerRows(rows, 3000, 120, 30, 2);

    expect(virtual.rows.map((row) => row.key)).toEqual(['row-0', 'row-1', 'row-2']);
    expect(virtual.translateY).toBe(0);
  });

  it('keeps row keys unique when alias shortcuts point at the same canonical path', () => {
    const nodes: TreeNode[] = [
      {
        name: '팀 폴더',
        type: 'directory',
        path: '/clean-room',
        aliasPath: '팀 폴더',
        expanded: true,
        children: [
          {
            name: '데이터',
            type: 'directory',
            path: '/clean-room/data',
            aliasPath: '팀 폴더/데이터',
            expanded: true,
            children: [
              {
                name: '30_outputs',
                type: 'directory',
                path: '/clean-room/data/30_outputs',
                expanded: false,
              },
            ],
          },
          {
            name: '공유 결과',
            type: 'directory',
            path: '/clean-room/data/30_outputs',
            aliasPath: '팀 폴더/공유 결과',
            expanded: false,
          },
        ],
      },
    ];

    const rows = buildExplorerRows(nodes, {}, false, '/');
    const keys = rows.map((row) => row.key);

    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toContain('node:팀 폴더/공유 결과');
    expect(keys).toContain('node:/clean-room/data/30_outputs');
  });
});

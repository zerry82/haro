import { describe, expect, it } from 'vitest';

import {
  collectExpandedPaths,
  collectNodeMap,
  getLanguageFromPath,
  getParentPath,
  insertChildren,
  joinPath,
  mapDirectoryItems,
  normalizeWorkspacePath,
  toggleNode,
} from './fileTreeUtils';
import type { FolderCacheEntry, TreeNode } from './fileTypes';

const cache: FolderCacheEntry = {
  items: [],
  total: 2,
  offset: 0,
  has_more: true,
  loaded_at: 0,
  dirty: false,
  loading: false,
};

describe('fileTreeUtils', () => {
  it('normalizes, joins, and classifies paths', () => {
    expect(normalizeWorkspacePath('docs\\../readme.md')).toBe('/readme.md');
    expect(joinPath('/docs/', 'guide.md')).toBe('/docs/guide.md');
    expect(getParentPath('/docs/guide.md')).toBe('/docs');
    expect(getLanguageFromPath('/src/app.ts')).toBe('typescript');
  });

  it('maps directory items preserving expanded children', () => {
    const existing: TreeNode = {
      name: 'docs',
      type: 'directory',
      path: '/docs',
      expanded: true,
      loaded: true,
      children: [{ name: 'a.md', type: 'file', path: '/docs/a.md' }],
    };

    const nodes = mapDirectoryItems('/', [{ name: 'docs', type: 'directory' }], collectNodeMap([existing]));

    expect(nodes[0].expanded).toBe(true);
    expect(nodes[0].children).toEqual(existing.children);
  });

  it('preserves alias labels when a user-mode virtual child is refreshed by canonical path', () => {
    const existing: TreeNode = {
      name: '결과',
      type: 'directory',
      path: '/playground/users/u1/30_outputs',
      aliasPath: '내 폴더/결과',
      expanded: true,
      loaded: true,
      children: [{ name: 'report.html', type: 'file', path: '/playground/users/u1/30_outputs/report.html' }],
    };

    const nodes = mapDirectoryItems(
      '/playground/users/u1',
      [{ name: '30_outputs', type: 'directory' }],
      collectNodeMap([existing]),
    );

    expect(nodes[0].name).toBe('결과');
    expect(nodes[0].aliasPath).toBe('내 폴더/결과');
    expect(nodes[0].children).toEqual(existing.children);
  });

  it('inserts children, toggles nodes, and collects expanded paths', () => {
    const tree: TreeNode[] = [{ name: 'docs', type: 'directory', path: '/docs', expanded: false }];
    const withChildren = insertChildren(tree, '/docs', [{ name: 'a.md', type: 'file', path: '/docs/a.md' }], cache);

    expect(withChildren[0].children_count).toBe(2);
    expect(toggleNode(withChildren, '/docs')[0].expanded).toBe(false);
    expect(collectExpandedPaths(withChildren)).toEqual(['/docs']);
  });
});

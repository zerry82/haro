import { describe, expect, it } from 'vitest';

import {
  buildFocusedSearchNode,
  isDirectorySearchResult,
  shouldConfirmDiscardUnsaved,
} from './workspaceExplorerActions';

describe('workspaceExplorerActions', () => {
  it('builds a focused node from a search result', () => {
    expect(buildFocusedSearchNode({
      name: 'docs',
      path: '/docs',
      item_type: 'directory',
    })).toEqual({
      name: 'docs',
      path: '/docs',
      type: 'directory',
      children: [],
      expanded: false,
      loaded: false,
    });

    expect(buildFocusedSearchNode({
      name: 'guide.md',
      path: '/docs/guide.md',
      item_type: 'file',
    })).toEqual({
      name: 'guide.md',
      path: '/docs/guide.md',
      type: 'file',
      children: undefined,
      expanded: false,
      loaded: false,
    });
  });

  it('detects directory search results', () => {
    expect(isDirectorySearchResult({ name: 'docs', path: '/docs', item_type: 'directory' })).toBe(true);
    expect(isDirectorySearchResult({ name: 'guide.md', path: '/docs/guide.md', item_type: 'file' })).toBe(false);
  });

  it('decides when unsaved changes need confirmation', () => {
    expect(shouldConfirmDiscardUnsaved('/docs/guide.md', '/docs/guide.md', true)).toBe(false);
    expect(shouldConfirmDiscardUnsaved('/docs/guide.md', '/docs/guide.md', false)).toBe(false);
    expect(shouldConfirmDiscardUnsaved('/docs/other.md', '/docs/guide.md', true)).toBe(true);
    expect(shouldConfirmDiscardUnsaved('/docs/other.md', null, true)).toBe(true);
    expect(shouldConfirmDiscardUnsaved(null, '/docs/guide.md', true)).toBe(false);
  });
});

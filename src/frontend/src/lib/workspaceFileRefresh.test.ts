import { describe, expect, it } from 'vitest';

import {
  getAffectedRefreshDirectories,
  getSelectedFileRefreshDecision,
  mergeRefreshQueue,
  normalizeFileChangedDetail,
  shouldReloadSelectedFile,
} from './workspaceFileRefresh';

describe('workspaceFileRefresh', () => {
  it('normalizes file changed event details', () => {
    expect(normalizeFileChangedDetail({ path: 'docs\\guide.md', type: 'file' })).toEqual({
      path: '/docs/guide.md',
      itemType: 'file',
    });
    expect(normalizeFileChangedDetail({ path: '/docs', item_type: 'directory' })).toEqual({
      path: '/docs',
      itemType: 'directory',
    });
    expect(normalizeFileChangedDetail(null)).toEqual({ path: null });
  });

  it('computes affected directories for files and directories', () => {
    expect(getAffectedRefreshDirectories('/docs/guide.md', 'file')).toEqual(['/docs', '/']);
    expect(getAffectedRefreshDirectories('/docs/reference', 'directory')).toEqual(['/docs', '/', '/docs/reference']);
    expect(getAffectedRefreshDirectories('/docs/reference', 'dir')).toEqual(['/docs', '/', '/docs/reference']);
    expect(getAffectedRefreshDirectories('/playground/users/u1/30_outputs/report/index.html', 'file')).toEqual([
      '/playground/users/u1/30_outputs/report',
      '/playground/users/u1/30_outputs',
      '/playground/users/u1',
      '/playground/users',
      '/playground',
      '/',
    ]);
  });

  it('decides whether the selected file should reload', () => {
    expect(shouldReloadSelectedFile('/docs/guide.md', '/docs/guide.md')).toBe(true);
    expect(shouldReloadSelectedFile(null, '/docs/guide.md')).toBe(true);
    expect(shouldReloadSelectedFile('/docs/other.md', '/docs/guide.md')).toBe(false);
    expect(shouldReloadSelectedFile('/docs/guide.md', null)).toBe(false);
  });

  it('protects unsaved selected files from automatic reload', () => {
    expect(getSelectedFileRefreshDecision({
      changedPath: '/docs/guide.md',
      selectedPath: '/docs/guide.md',
      hasUnsavedChanges: true,
    })).toEqual({ externalChanged: true, reloadPath: null });

    expect(getSelectedFileRefreshDecision({
      changedPath: '/docs/guide.md',
      selectedPath: '/docs/guide.md',
      hasUnsavedChanges: false,
    })).toEqual({ externalChanged: false, reloadPath: '/docs/guide.md' });
  });

  it('merges refresh queues by normalized path', () => {
    const queue = new Map<string, string | undefined>([['/docs/guide.md', 'file']]);
    const merged = mergeRefreshQueue(queue, 'docs\\guide.md');

    expect(queue.get('/docs/guide.md')).toBe('file');
    expect(merged.get('/docs/guide.md')).toBe('file');
    expect(mergeRefreshQueue(merged, '/docs/reference', 'directory').get('/docs/reference')).toBe('directory');
  });
});

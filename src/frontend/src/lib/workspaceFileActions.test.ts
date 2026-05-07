import { describe, expect, it } from 'vitest';

import {
  formatFileActionError,
  getExplorerTargetDir,
  getNodeTargetDir,
  hasDraggedFiles,
  isReadOnlyMutationTarget,
  validateNewFolderName,
} from './workspaceFileActions';

describe('workspaceFileActions', () => {
  it('validates folder names', () => {
    expect(validateNewFolderName(' docs ')).toEqual({ ok: true, name: 'docs' });
    expect(validateNewFolderName('')).toEqual({ ok: false, message: '올바른 폴더 이름을 입력하세요.' });
    expect(validateNewFolderName('.')).toEqual({ ok: false, message: '올바른 폴더 이름을 입력하세요.' });
    expect(validateNewFolderName('..')).toEqual({ ok: false, message: '올바른 폴더 이름을 입력하세요.' });
    expect(validateNewFolderName('docs/guide')).toEqual({ ok: false, message: '올바른 폴더 이름을 입력하세요.' });
    expect(validateNewFolderName('docs\\guide')).toEqual({ ok: false, message: '올바른 폴더 이름을 입력하세요.' });
  });

  it('resolves explorer mutation target directories', () => {
    expect(getExplorerTargetDir({
      focusedNode: { type: 'directory', path: '/docs' },
      selectedFilePath: '/selected/file.md',
      defaultInbox: '/inbox',
    })).toBe('/docs');
    expect(getExplorerTargetDir({
      focusedNode: { type: 'file', path: '/docs/guide.md' },
      selectedFilePath: '/selected/file.md',
      defaultInbox: '/inbox',
    })).toBe('/docs');
    expect(getExplorerTargetDir({
      focusedNode: null,
      selectedFilePath: '/selected/file.md',
      defaultInbox: '/inbox',
    })).toBe('/selected');
    expect(getExplorerTargetDir({
      focusedNode: null,
      selectedFilePath: null,
      defaultInbox: '/inbox',
    })).toBe('/inbox');
  });

  it('resolves node drop target directories', () => {
    expect(getNodeTargetDir(null, '/fallback')).toBe('/fallback');
    expect(getNodeTargetDir({ type: 'directory', path: '/docs' }, '/fallback')).toBe('/docs');
    expect(getNodeTargetDir({ type: 'file', path: '/docs/guide.md' }, '/fallback')).toBe('/docs');
  });

  it('detects readonly targets and dragged files', () => {
    expect(isReadOnlyMutationTarget('/clean-room/data/source.csv')).toBe(true);
    expect(isReadOnlyMutationTarget('/playground/users/u1/file.md')).toBe(false);
    expect(hasDraggedFiles(['text/plain', 'Files'])).toBe(true);
    expect(hasDraggedFiles(['text/plain'])).toBe(false);
    expect(hasDraggedFiles(null)).toBe(false);
  });

  it('formats unknown errors', () => {
    expect(formatFileActionError(new Error('failed'), 'fallback')).toBe('failed');
    expect(formatFileActionError('failed', 'fallback')).toBe('fallback');
  });
});

import { describe, expect, it } from 'vitest';

import {
  escapeHtml,
  getDefaultPlaygroundInbox,
  getDefaultViewerTab,
  getExtension,
  getHtmlPreviewKey,
  getParentPath,
  getPathBadge,
  getRoomLabel,
  getRuntimeModeLabel,
  getViewerContent,
  getViewerTabs,
  isCleanRoomPath,
  isCsvFile,
  isEditableTextFile,
  isHtmlFile,
  isMarkdownFile,
  isOwnPlaygroundPath,
  isSystemManagedPath,
  joinExplorerPath,
  normalizeWorkspacePath,
} from './workspaceUtils';

describe('workspaceUtils path helpers', () => {
  it('normalizes workspace paths without escaping root', () => {
    expect(normalizeWorkspacePath(null)).toBe('/');
    expect(normalizeWorkspacePath('docs\\guide.md')).toBe('/docs/guide.md');
    expect(normalizeWorkspacePath('/docs/../guide.md')).toBe('/guide.md');
    expect(normalizeWorkspacePath('../../outside.txt')).toBe('/outside.txt');
  });

  it('detects path ownership and badges', () => {
    expect(isCleanRoomPath('/clean-room/data/source.csv')).toBe(true);
    expect(isCleanRoomPath('/playground/users/u1/00_inbox/a.txt')).toBe(false);
    expect(isSystemManagedPath('/playground/users/u1/.HARO.md')).toBe(true);
    expect(isSystemManagedPath('/playground/users/u1/AGENTS.md')).toBe(false);
    expect(getDefaultPlaygroundInbox('u1')).toBe('/playground/users/u1/00_inbox');
    expect(isOwnPlaygroundPath('/playground/users/u1/20_working/a.txt', 'u1')).toBe(true);
    expect(isOwnPlaygroundPath('/playground/users/u2/20_working/a.txt', 'u1')).toBe(false);
    expect(getPathBadge('/clean-room/data/source.csv', 'u1')).toBe('읽기 전용');
    expect(getPathBadge('/playground/users/u1/.HARO.md', 'u1')).toBe('시스템');
    expect(getPathBadge('/playground/users/u1/20_working/a.txt', 'u1')).toBe('내 작업공간');
  });

  it('joins and resolves parent paths', () => {
    expect(getParentPath('/docs/guide.md')).toBe('/docs');
    expect(getParentPath('/guide.md')).toBe('/');
    expect(joinExplorerPath('/', 'docs')).toBe('/docs');
    expect(joinExplorerPath('/docs/', 'guide.md')).toBe('/docs/guide.md');
  });
});

describe('workspaceUtils viewer helpers', () => {
  it('detects file types from path or language', () => {
    expect(getExtension('/docs/README.MD')).toBe('.md');
    expect(isMarkdownFile('/docs/readme.md', 'plaintext')).toBe(true);
    expect(isHtmlFile('/preview/index.txt', 'html')).toBe(true);
    expect(isCsvFile('/data/report.csv', 'plaintext')).toBe(true);
    expect(isEditableTextFile('/notes/readme.md', 'plaintext')).toBe(true);
  });

  it('chooses viewer tabs and default tabs by file type', () => {
    expect(getViewerTabs('/docs/readme.md', 'markdown').map((tab) => tab.id)).toEqual(['preview', 'editor', 'source']);
    expect(getDefaultViewerTab('/docs/readme.md', 'markdown')).toBe('preview');
    expect(getViewerTabs('/src/app.ts', 'typescript').map((tab) => tab.id)).toEqual(['code', 'editor']);
    expect(getDefaultViewerTab('/data/report.csv', 'csv')).toBe('editor');
    expect(getViewerTabs('/assets/logo.png', 'binary').map((tab) => tab.id)).toEqual(['source']);
  });

  it('returns draft content for editable files and source content for non-editable files', () => {
    expect(getViewerContent('saved', '/docs/readme.md', 'markdown', 'draft')).toBe('draft');
    expect(getViewerContent('saved', '/assets/logo.png', 'binary', 'draft')).toBe('saved');
    expect(getViewerContent(null, '/assets/logo.png', 'binary', 'draft')).toBe('');
  });

  it('generates stable html preview keys', () => {
    expect(getHtmlPreviewKey('/index.html', '<h1>Hello</h1>', 2)).toBe(getHtmlPreviewKey('/index.html', '<h1>Hello</h1>', 2));
    expect(getHtmlPreviewKey('/index.html', '<h1>Hello</h1>', 2)).not.toBe(getHtmlPreviewKey('/index.html', '<h1>Hello</h1>', 3));
  });
});

describe('workspaceUtils labels and escaping', () => {
  it('maps runtime and room labels', () => {
    expect(getRuntimeModeLabel('work')).toBe('작업모드');
    expect(getRuntimeModeLabel('deploy')).toBe('배포모드');
    expect(getRoomLabel('clean_room_data')).toBe('Data Clean Room');
    expect(getRoomLabel('unknown')).toBe('Root');
  });

  it('escapes html special characters', () => {
    expect(escapeHtml(`<button title="x">A & B's</button>`)).toBe('&lt;button title=&quot;x&quot;&gt;A &amp; B&#039;s&lt;/button&gt;');
  });
});

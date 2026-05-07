export type RuntimeMode = 'work' | 'deploy';
export type ViewerTab = 'preview' | 'source' | 'code' | 'editor';
export type ViewerTabItem = { id: ViewerTab; label: string };

const EDITABLE_EXTENSIONS = [
  '.html', '.md', '.csv', '.ts', '.js', '.json',
  '.txt', '.css', '.py', '.yaml', '.yml', '.svg',
];

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function getExtension(path: string | null) {
  if (!path) return '';
  const name = path.split('/').pop() || '';
  const dotIndex = name.lastIndexOf('.');
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : '';
}

export function isMarkdownFile(path: string | null, language: string) {
  return getExtension(path) === '.md' || language === 'markdown';
}

export function isHtmlFile(path: string | null, language: string) {
  return getExtension(path) === '.html' || language === 'html';
}

export function isCsvFile(path: string | null, language: string) {
  return getExtension(path) === '.csv' || language === 'csv';
}

export function isCodePreviewFile(path: string | null, language: string) {
  return ['.ts', '.js', '.json'].includes(getExtension(path)) ||
    ['typescript', 'javascript', 'json'].includes(language);
}

export function isEditableTextFile(path: string | null, language: string) {
  const extension = getExtension(path);
  return EDITABLE_EXTENSIONS.includes(extension) ||
    ['html', 'markdown', 'csv', 'typescript', 'javascript', 'json', 'plaintext', 'css', 'python', 'yaml', 'xml'].includes(language);
}

export function getViewerContent(content: string | null, path: string | null, language: string, draft: string) {
  return isEditableTextFile(path, language) ? draft : content || '';
}

export function getLightweightHash(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
  }
  return hash.toString(36);
}

export function getHtmlPreviewKey(path: string | null, content: string, revision: number) {
  return `${path || ''}:${content.length}:${getLightweightHash(content)}:${revision}`;
}

export function getParentPath(path: string | null) {
  if (!path || path === '/') return '/';
  const normalized = path.endsWith('/') ? path.slice(0, -1) : path;
  const index = normalized.lastIndexOf('/');
  return index <= 0 ? '/' : normalized.slice(0, index);
}

export function normalizeWorkspacePath(path: string | null) {
  if (!path) return '/';
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  const normalized: string[] = [];
  for (const part of parts) {
    if (part === '.') continue;
    if (part === '..') {
      normalized.pop();
    } else {
      normalized.push(part);
    }
  }
  return normalized.length === 0 ? '/' : `/${normalized.join('/')}`;
}

export function isCleanRoomPath(path: string | null) {
  const normalized = normalizeWorkspacePath(path);
  return normalized === '/clean-room' || normalized.startsWith('/clean-room/');
}

export function getDefaultPlaygroundInbox(userId: string | null | undefined) {
  return userId ? `/playground/users/${userId}/00_inbox` : '/';
}

export function isOwnPlaygroundPath(path: string | null, userId: string | null | undefined) {
  const normalized = normalizeWorkspacePath(path);
  const root = userId ? `/playground/users/${userId}` : '';
  return Boolean(root && (normalized === root || normalized.startsWith(`${root}/`)));
}

export function getPathBadge(path: string | null, userId: string | null | undefined) {
  if (isCleanRoomPath(path)) return '읽기 전용';
  if (isOwnPlaygroundPath(path, userId)) return '내 작업공간';
  return '';
}

export function joinExplorerPath(basePath: string, name: string) {
  return basePath === '/' ? `/${name}` : `${basePath.replace(/\/$/, '')}/${name}`;
}

export function getRuntimeModeLabel(runtimeMode: RuntimeMode) {
  return runtimeMode === 'deploy' ? '배포모드' : '작업모드';
}

export function getRoomLabel(room: string) {
  if (room === 'clean_room_data') return 'Data Clean Room';
  if (room === 'clean_room_meta') return 'Meta Clean Room';
  if (room === 'playground') return 'Playground';
  if (room === 'archive') return 'Archive';
  return 'Root';
}

export function getViewerTabs(path: string | null, language: string): ViewerTabItem[] {
  if (isCsvFile(path, language)) {
    return [
      { id: 'preview', label: '프리뷰' },
      { id: 'editor', label: '에디터' },
      { id: 'source', label: '원본' },
    ];
  }
  if (isMarkdownFile(path, language) || isHtmlFile(path, language)) {
    return [
      { id: 'preview', label: '프리뷰' },
      { id: 'editor', label: '에디터' },
      { id: 'source', label: '원본' },
    ];
  }
  if (isCodePreviewFile(path, language)) {
    return [
      { id: 'code', label: '코드' },
      { id: 'editor', label: '에디터' },
    ];
  }
  if (isEditableTextFile(path, language)) {
    return [
      { id: 'editor', label: '에디터' },
      { id: 'source', label: '원본' },
    ];
  }
  return [{ id: 'source', label: '원본' }];
}

export function getDefaultViewerTab(path: string | null, language: string): ViewerTab {
  if (isCsvFile(path, language)) return 'editor';
  if (isMarkdownFile(path, language) || isHtmlFile(path, language)) return 'preview';
  if (isCodePreviewFile(path, language)) return 'code';
  if (isEditableTextFile(path, language)) return 'editor';
  return 'source';
}

export function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

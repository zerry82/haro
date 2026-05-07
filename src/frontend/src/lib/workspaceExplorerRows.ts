import type { FolderCacheEntry, TreeNode } from '../stores/files';

export type ExplorerRow =
  | { key: string; kind: 'node'; node: TreeNode; depth: number }
  | { key: string; kind: 'new-folder'; depth: number }
  | { key: string; kind: 'load-more'; path: string; depth: number };

export const FILE_ROW_HEIGHT = 30;
export const FILE_ROW_BUFFER = 8;

export function buildExplorerRows(
  nodes: TreeNode[],
  folderCache: Record<string, FolderCacheEntry>,
  creatingFolder: boolean,
  creatingFolderParentPath: string,
) {
  const rows: ExplorerRow[] = [];
  if (creatingFolder && creatingFolderParentPath === '/') {
    rows.push({ key: 'new-folder:/', kind: 'new-folder', depth: 0 });
  }
  appendExplorerRows(rows, nodes, folderCache, creatingFolder, creatingFolderParentPath, 0);
  if (folderCache['/']?.has_more) {
    rows.push({ key: 'load-more:/', kind: 'load-more', path: '/', depth: 0 });
  }
  return rows;
}

export function getVirtualExplorerRows(
  rows: ExplorerRow[],
  scrollTop: number,
  viewportHeight: number,
  rowHeight = FILE_ROW_HEIGHT,
  buffer = FILE_ROW_BUFFER,
) {
  const height = Math.max(viewportHeight || 0, 360);
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - buffer);
  const end = Math.min(rows.length, Math.ceil((scrollTop + height) / rowHeight) + buffer);
  return {
    rows: rows.slice(start, end),
    totalHeight: rows.length * rowHeight,
    translateY: start * rowHeight,
  };
}

function appendExplorerRows(
  rows: ExplorerRow[],
  nodes: TreeNode[],
  folderCache: Record<string, FolderCacheEntry>,
  creatingFolder: boolean,
  creatingFolderParentPath: string,
  depth: number,
) {
  for (const item of nodes) {
    rows.push({ key: `node:${item.path}`, kind: 'node', node: item, depth });
    if (creatingFolder && item.type === 'directory' && item.path === creatingFolderParentPath) {
      rows.push({ key: `new-folder:${item.path}`, kind: 'new-folder', depth: depth + 1 });
    }
    if (item.type === 'directory' && item.expanded && item.children) {
      appendExplorerRows(rows, item.children, folderCache, creatingFolder, creatingFolderParentPath, depth + 1);
      if (folderCache[item.path]?.has_more || item.has_more) {
        rows.push({ key: `load-more:${item.path}`, kind: 'load-more', path: item.path, depth: depth + 1 });
      }
    }
  }
}

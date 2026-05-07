import type { FileListResponse, FolderCacheEntry, TreeNode } from './fileTypes';

const LANG_MAP: Record<string, string> = {
  '.py': 'python',
  '.js': 'javascript',
  '.ts': 'typescript',
  '.html': 'html',
  '.css': 'css',
  '.json': 'json',
  '.csv': 'csv',
  '.md': 'markdown',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.txt': 'plaintext',
  '.svg': 'xml',
};

export const DIRECTORY_PAGE_SIZE = 200;

export function normalizeWorkspacePath(path: string | null | undefined) {
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

export function joinPath(basePath: string, name: string) {
  return basePath === '/' ? `/${name}` : `${basePath.replace(/\/$/, '')}/${name}`;
}

export function getParentPath(path: string) {
  const normalized = normalizeWorkspacePath(path);
  if (normalized === '/') return '/';
  const index = normalized.lastIndexOf('/');
  return index <= 0 ? '/' : normalized.slice(0, index);
}

export function getLanguageFromPath(path: string) {
  const name = path.split('/').pop() || '';
  const dotIndex = name.lastIndexOf('.');
  const extension = dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : '';
  return LANG_MAP[extension] || 'plaintext';
}

export function mapDirectoryItems(basePath: string, items: FileListResponse['items'], existingMap: Map<string, TreeNode>) {
  return items.map((item) => {
    const path = joinPath(basePath, item.name);
    const existing = existingMap.get(path);
    const isDirectory = item.type === 'directory';
    return {
      ...item,
      path,
      expanded: existing?.expanded || false,
      loaded: existing?.loaded || false,
      children: isDirectory ? existing?.children || [] : undefined,
      total: existing?.total,
      has_more: existing?.has_more,
      loading: existing?.loading,
    } satisfies TreeNode;
  });
}

export function collectNodeMap(nodes: TreeNode[], result = new Map<string, TreeNode>()) {
  for (const node of nodes) {
    result.set(node.path, node);
    if (node.children) collectNodeMap(node.children, result);
  }
  return result;
}

export function insertChildren(nodes: TreeNode[], parentPath: string, children: TreeNode[], cache: FolderCacheEntry): TreeNode[] {
  return nodes.map(node => {
    if (node.path === parentPath) {
      return {
        ...node,
        children,
        loaded: true,
        expanded: true,
        total: cache.total,
        has_more: cache.has_more,
        loading: cache.loading,
        children_count: cache.total,
      };
    }
    if (node.children) {
      return { ...node, children: insertChildren(node.children, parentPath, children, cache) };
    }
    return node;
  });
}

export function toggleNode(nodes: TreeNode[], path: string): TreeNode[] {
  return nodes.map(node => {
    if (node.path === path) {
      return { ...node, expanded: !node.expanded };
    }
    if (node.children) {
      return { ...node, children: toggleNode(node.children, path) };
    }
    return node;
  });
}

export function collectExpandedPaths(nodes: TreeNode[]): string[] {
  const paths: string[] = [];
  for (const node of nodes) {
    if (node.type === 'directory' && node.expanded) {
      paths.push(node.path);
      if (node.children) {
        paths.push(...collectExpandedPaths(node.children));
      }
    }
  }
  return paths;
}

import { writable, get } from 'svelte/store';
import { api } from '../lib/api';

export interface TreeNode {
  name: string;
  type: string;
  path: string;
  size?: number;
  children_count?: number;
  children?: TreeNode[];
  expanded?: boolean;
  loaded?: boolean;
}

export interface FileContentResponse {
  path: string;
  content: string;
  size: number;
  language: string;
}

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

export const fileTree = writable<TreeNode[]>([]);
export const selectedFilePath = writable<string | null>(null);
export const fileContent = writable<string | null>(null);
export const fileLanguage = writable<string>('plaintext');
export const fileLoading = writable(false);
export const loadingFilePath = writable<string | null>(null);

let loadFileRequestSeq = 0;

function getLanguageFromPath(path: string) {
  const name = path.split('/').pop() || '';
  const dotIndex = name.lastIndexOf('.');
  const extension = dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : '';
  return LANG_MAP[extension] || 'plaintext';
}

export async function loadFiles(projectId: string, path: string = '/') {
  const res: any = await api(`/projects/${projectId}/files?path=${encodeURIComponent(path)}`);
  const nodes: TreeNode[] = (res.items || []).map((item: any) => ({
    ...item,
    path: path === '/' ? `/${item.name}` : `${path}/${item.name}`,
    expanded: false,
    loaded: false,
    children: item.type === 'directory' ? [] : undefined,
  }));
  if (path === '/') {
    fileTree.set(nodes);
  } else {
    fileTree.update(tree => insertChildren(tree, path, nodes));
  }
}

function insertChildren(nodes: TreeNode[], parentPath: string, children: TreeNode[]): TreeNode[] {
  return nodes.map(node => {
    if (node.path === parentPath) {
      return { ...node, children, loaded: true, expanded: true };
    }
    if (node.children && node.children.length > 0) {
      return { ...node, children: insertChildren(node.children, parentPath, children) };
    }
    return node;
  });
}

export function toggleFolder(path: string) {
  fileTree.update(tree => toggleNode(tree, path));
}

function toggleNode(nodes: TreeNode[], path: string): TreeNode[] {
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

export async function expandFolder(projectId: string, node: TreeNode) {
  if (node.loaded) {
    toggleFolder(node.path);
  } else {
    await loadFiles(projectId, node.path);
  }
}

export async function loadFileContent(projectId: string, path: string) {
  const requestSeq = ++loadFileRequestSeq;
  selectedFilePath.set(path);
  fileContent.set(null);
  fileLanguage.set(getLanguageFromPath(path));
  fileLoading.set(true);
  loadingFilePath.set(path);

  try {
    const res = await api<FileContentResponse>(`/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`);
    if (requestSeq !== loadFileRequestSeq) return;

    selectedFilePath.set(path);
    fileContent.set(res.content);
    fileLanguage.set(res.language);
  } catch (error) {
    if (requestSeq === loadFileRequestSeq) throw error;
  } finally {
    if (requestSeq === loadFileRequestSeq) {
      fileLoading.set(false);
      loadingFilePath.set(null);
    }
  }
}

export async function saveFileContent(projectId: string, path: string, content: string) {
  const res = await api<FileContentResponse>(`/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
  selectedFilePath.set(path);
  fileContent.set(res.content);
  fileLanguage.set(res.language);
  fileLoading.set(false);
  loadingFilePath.set(null);
  return res;
}

export async function reloadAllExpanded(projectId: string) {
  const tree = get(fileTree);
  await loadFiles(projectId, '/');
  const expandedPaths = collectExpandedPaths(tree);
  for (const p of expandedPaths) {
    await loadFiles(projectId, p);
  }
}

function collectExpandedPaths(nodes: TreeNode[]): string[] {
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

import { writable, get } from 'svelte/store';
import { api } from '../lib/api';
import type {
  FileContentResponse,
  FileListResponse,
  FileMutationResponse,
  FileSearchItem,
  FileSearchResponse,
  FileUploadResponse,
  FolderCacheEntry,
  LoadDirectoryOptions,
  TreeNode,
} from './fileTypes';
import {
  DIRECTORY_PAGE_SIZE,
  collectExpandedPaths,
  collectNodeMap,
  getLanguageFromPath,
  getParentPath,
  insertChildren,
  mapDirectoryItems,
  normalizeWorkspacePath,
  toggleNode,
} from './fileTreeUtils';

export type {
  FileContentResponse,
  FileMutationResponse,
  FileSearchItem,
  FileSearchResponse,
  FileUploadResponse,
  FolderCacheEntry,
  TreeNode,
} from './fileTypes';

export const fileTree = writable<TreeNode[]>([]);
export const folderCache = writable<Record<string, FolderCacheEntry>>({});
export const selectedFilePath = writable<string | null>(null);
export const fileContent = writable<string | null>(null);
export const fileLanguage = writable<string>('plaintext');
export const fileLoading = writable(false);
export const loadingFilePath = writable<string | null>(null);

let loadFileRequestSeq = 0;

export async function loadFiles(projectId: string, path: string = '/') {
  await loadDirectory(projectId, path);
}
export async function loadDirectory(projectId: string, path: string = '/', options: LoadDirectoryOptions = {}) {
  const normalizedPath = normalizeWorkspacePath(path);
  const cache = get(folderCache)[normalizedPath];
  if (!options.append && !options.force && cache && !cache.dirty) {
    applyDirectoryToTree(normalizedPath, cache.items, cache);
    return cache;
  }

  const requestOffset = options.append && cache ? cache.offset : 0;
  const limit = options.limit || DIRECTORY_PAGE_SIZE;
  setFolderCacheLoading(normalizedPath, true);

  try {
    const res = await api<FileListResponse>(
      `/projects/${projectId}/files?path=${encodeURIComponent(normalizedPath)}&limit=${limit}&offset=${requestOffset}`
    );
    const existingMap = collectNodeMap(get(fileTree));
    const pageNodes = mapDirectoryItems(normalizedPath, res.items || [], existingMap);
    const combinedItems = options.append && cache ? [...cache.items, ...pageNodes] : pageNodes;
    const nextCache: FolderCacheEntry = {
      items: combinedItems,
      total: res.total ?? combinedItems.length,
      offset: combinedItems.length,
      has_more: Boolean(res.has_more),
      loaded_at: Date.now(),
      dirty: false,
      loading: false,
    };
    folderCache.update((entries) => ({ ...entries, [normalizedPath]: nextCache }));
    applyDirectoryToTree(normalizedPath, combinedItems, nextCache);
    return nextCache;
  } catch (error) {
    setFolderCacheLoading(normalizedPath, false);
    throw error;
  }
}
function setFolderCacheLoading(path: string, loading: boolean) {
  const normalizedPath = normalizeWorkspacePath(path);
  folderCache.update((entries) => {
    const existing = entries[normalizedPath];
    if (!existing && !loading) return entries;
    return {
      ...entries,
      [normalizedPath]: {
        items: existing?.items || [],
        total: existing?.total || 0,
        offset: existing?.offset || 0,
        has_more: existing?.has_more || false,
        loaded_at: existing?.loaded_at || 0,
        dirty: existing?.dirty || false,
        loading,
      },
    };
  });
}

function applyDirectoryToTree(path: string, items: TreeNode[], cache: FolderCacheEntry) {
  if (path === '/') {
    fileTree.set(items);
  } else {
    fileTree.update(tree => insertChildren(tree, path, items, cache));
  }
}

export function toggleFolder(path: string) {
  fileTree.update(tree => toggleNode(tree, path));
}

export async function expandFolder(projectId: string, node: TreeNode) {
  const cache = get(folderCache)[normalizeWorkspacePath(node.path)];
  if (node.loaded && !cache?.dirty) {
    toggleFolder(node.path);
  } else {
    await loadDirectory(projectId, node.path, { force: Boolean(cache?.dirty) });
  }
}

export async function loadMoreDirectory(projectId: string, path: string) {
  return loadDirectory(projectId, path, { append: true });
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

export async function createFolder(projectId: string, path: string) {
  return api<FileMutationResponse>(`/projects/${projectId}/files/directories`, {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function uploadFiles(projectId: string, targetDir: string, files: File[] | FileList, overwrite = false) {
  const body = new FormData();
  for (const file of Array.from(files)) {
    body.append('files', file);
  }

  return api<FileUploadResponse>(
    `/projects/${projectId}/files/upload?path=${encodeURIComponent(targetDir)}&overwrite=${overwrite}`,
    {
      method: 'POST',
      body,
    }
  );
}

export async function searchFiles(projectId: string, query: string, limit = 50) {
  return api<FileSearchResponse>(
    `/projects/${projectId}/files/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}

export async function reloadAllExpanded(projectId: string) {
  const tree = get(fileTree);
  await loadDirectory(projectId, '/', { force: true });
  const expandedPaths = collectExpandedPaths(tree);
  for (const p of expandedPaths) {
    await loadDirectory(projectId, p, { force: true });
  }
}

export async function refreshDirectory(projectId: string, path: string) {
  return loadDirectory(projectId, path, { force: true });
}

export function markDirectoryDirty(path: string) {
  const normalizedPath = normalizeWorkspacePath(path);
  folderCache.update((entries) => {
    const existing = entries[normalizedPath];
    if (!existing || existing.dirty) return entries;
    return { ...entries, [normalizedPath]: { ...existing, dirty: true } };
  });
}

export async function refreshChangedPath(projectId: string, path: string, itemType?: string) {
  const normalizedPath = normalizeWorkspacePath(path);
  const affected = new Set<string>([getParentPath(normalizedPath)]);
  if (itemType === 'directory' || itemType === 'dir') affected.add(normalizedPath);
  for (const directoryPath of affected) markDirectoryDirty(directoryPath);

  const cache = get(folderCache);
  for (const directoryPath of affected) {
    if (cache[directoryPath]) {
      try {
        await refreshDirectory(projectId, directoryPath);
      } catch {
        if (directoryPath !== getParentPath(normalizedPath)) {
          folderCache.update((entries) => {
            const next = { ...entries };
            delete next[directoryPath];
            return next;
          });
        }
      }
    }
  }
}

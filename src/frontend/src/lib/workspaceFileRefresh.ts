import {
  getParentPath,
  normalizeWorkspacePath,
} from './workspaceUtils';

export type FileChangedDetail = {
  path: string | null;
  itemType?: string;
};

export type SelectedFileRefreshDecision = {
  externalChanged: boolean;
  reloadPath: string | null;
};

export function normalizeFileChangedDetail(detail: unknown): FileChangedDetail {
  if (!detail || typeof detail !== 'object') return { path: null };
  const record = detail as Record<string, unknown>;
  const path = typeof record.path === 'string' ? normalizeWorkspacePath(record.path) : null;
  const itemType = typeof record.type === 'string'
    ? record.type
    : typeof record.item_type === 'string'
      ? record.item_type
      : undefined;
  return { path, itemType };
}

export function getAffectedRefreshDirectories(path: string, itemType?: string) {
  const normalized = normalizeWorkspacePath(path);
  const affected = new Set<string>([getParentPath(normalized)]);
  if (itemType === 'directory' || itemType === 'dir') {
    affected.add(normalized);
  }
  return Array.from(affected);
}

export function shouldReloadSelectedFile(changedPath: string | null, selectedPath: string | null) {
  if (!selectedPath) return false;
  if (!changedPath) return true;
  return normalizeWorkspacePath(changedPath) === normalizeWorkspacePath(selectedPath);
}

export function getSelectedFileRefreshDecision({
  changedPath,
  selectedPath,
  hasUnsavedChanges,
}: {
  changedPath: string | null;
  selectedPath: string | null;
  hasUnsavedChanges: boolean;
}): SelectedFileRefreshDecision {
  if (!shouldReloadSelectedFile(changedPath, selectedPath)) {
    return { externalChanged: false, reloadPath: null };
  }
  if (hasUnsavedChanges) {
    return { externalChanged: true, reloadPath: null };
  }
  return { externalChanged: false, reloadPath: selectedPath };
}

export function mergeRefreshQueue(
  queue: ReadonlyMap<string, string | undefined>,
  path: string,
  itemType?: string,
) {
  const normalized = normalizeWorkspacePath(path);
  const next = new Map(queue);
  next.set(normalized, itemType ?? next.get(normalized));
  return next;
}

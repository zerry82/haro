import {
  getParentPath,
  isCleanRoomPath,
} from './workspaceUtils';

export type WorkspaceTargetNode = {
  type: string;
  path: string;
};

export type FolderNameValidation =
  | { ok: true; name: string }
  | { ok: false; message: string };

export function validateNewFolderName(name: string): FolderNameValidation {
  const trimmed = name.trim();
  if (!trimmed || trimmed === '.' || trimmed === '..' || trimmed.includes('/') || trimmed.includes('\\')) {
    return { ok: false, message: '올바른 폴더 이름을 입력하세요.' };
  }
  return { ok: true, name: trimmed };
}

export function getExplorerTargetDir({
  focusedNode,
  selectedFilePath,
  defaultInbox,
}: {
  focusedNode: WorkspaceTargetNode | null;
  selectedFilePath: string | null;
  defaultInbox: string;
}) {
  if (focusedNode?.type === 'directory') return focusedNode.path;
  if (focusedNode?.type === 'file') return getParentPath(focusedNode.path);
  if (selectedFilePath) return getParentPath(selectedFilePath);
  return defaultInbox;
}

export function getNodeTargetDir(node: WorkspaceTargetNode | null, fallback: string) {
  if (!node) return fallback;
  return node.type === 'directory' ? node.path : getParentPath(node.path);
}

export function isReadOnlyMutationTarget(path: string | null) {
  return isCleanRoomPath(path);
}

export function hasDraggedFiles(types: ArrayLike<string> | Iterable<string> | null | undefined) {
  return Array.from(types || []).includes('Files');
}

export function formatFileActionError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

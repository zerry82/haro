import { normalizeWorkspacePath } from './workspaceUtils';

export type WorkspaceSearchItem = {
  path: string;
  name: string;
  item_type: 'file' | 'directory';
};

export type WorkspaceExplorerNode = {
  name: string;
  type: 'file' | 'directory';
  path: string;
  children?: WorkspaceExplorerNode[];
  expanded: boolean;
  loaded: boolean;
};

export function buildFocusedSearchNode(item: WorkspaceSearchItem): WorkspaceExplorerNode {
  return {
    name: item.name,
    type: item.item_type,
    path: item.path,
    children: item.item_type === 'directory' ? [] : undefined,
    expanded: false,
    loaded: false,
  };
}

export function isDirectorySearchResult(item: WorkspaceSearchItem) {
  return item.item_type === 'directory';
}

export function shouldConfirmDiscardUnsaved(
  nextPath: string | null,
  selectedPath: string | null,
  hasUnsavedChanges: boolean,
) {
  if (!hasUnsavedChanges || !nextPath) return false;
  if (!selectedPath) return true;
  return normalizeWorkspacePath(nextPath) !== normalizeWorkspacePath(selectedPath);
}

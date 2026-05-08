import type { TreeNode, WorkspaceExplorerMode } from '../stores/files';

export type WorkspacePathAlias = {
  label: string;
  aliasPrefix: string;
  canonicalPrefix: string;
  type?: 'directory' | 'file';
};

export function getDeveloperModeStorageKey(userId?: string | null) {
  return `haro:developerMode:${userId || 'anonymous'}`;
}

export function getWorkspacePathAliases(userId: string | null | undefined): WorkspacePathAlias[] {
  const userRoot = userId ? `/playground/users/${userId}` : '/playground/users/anonymous';
  return [
    { label: '데이터', aliasPrefix: '팀 폴더/데이터', canonicalPrefix: '/clean-room/data' },
    { label: '규칙/스킬', aliasPrefix: '팀 폴더/규칙/스킬', canonicalPrefix: '/clean-room/meta' },
    { label: '공유 결과', aliasPrefix: '팀 폴더/공유 결과', canonicalPrefix: '/clean-room/data/30_outputs' },
    { label: '받은 파일', aliasPrefix: '내 폴더/받은 파일', canonicalPrefix: `${userRoot}/00_inbox` },
    { label: '작업 중', aliasPrefix: '내 폴더/작업 중', canonicalPrefix: `${userRoot}/20_working` },
    { label: '결과', aliasPrefix: '내 폴더/결과', canonicalPrefix: `${userRoot}/30_outputs` },
    { label: 'AGENTS.md', aliasPrefix: '내 폴더/AGENTS.md', canonicalPrefix: `${userRoot}/AGENTS.md`, type: 'file' },
  ];
}

export function createUserModeRootNodes(userId: string | null | undefined): TreeNode[] {
  const aliases = getWorkspacePathAliases(userId);
  const teamAliases = aliases.slice(0, 3);
  const myAliases = aliases.slice(3);
  const userRoot = userId ? `/playground/users/${userId}` : '/playground/users/anonymous';

  return [
    makeVirtualRoot('팀 폴더', '/clean-room', teamAliases),
    makeVirtualRoot('내 폴더', userRoot, myAliases),
  ];
}

export function aliasPathForCanonicalPath(
  path: string | null | undefined,
  userId: string | null | undefined,
) {
  const canonical = normalizePath(path);
  const aliases = getWorkspacePathAliases(userId)
    .sort((a, b) => b.canonicalPrefix.length - a.canonicalPrefix.length);
  for (const alias of aliases) {
    const prefix = normalizePath(alias.canonicalPrefix);
    if (canonical === prefix || canonical.startsWith(`${prefix}/`)) {
      const rest = canonical.slice(prefix.length).replace(/^\//, '');
      return rest ? `${alias.aliasPrefix}/${rest}` : alias.aliasPrefix;
    }
  }
  if (userId) {
    const userRoot = `/playground/users/${userId}`;
    if (canonical === userRoot) return '내 폴더';
  }
  if (canonical === '/clean-room') return '팀 폴더';
  return canonical;
}

export function displayPathForMode(
  path: string | null | undefined,
  mode: WorkspaceExplorerMode,
  userId: string | null | undefined,
) {
  return mode === 'user' ? aliasPathForCanonicalPath(path, userId) : normalizePath(path);
}

export function userModeMutationTarget(path: string, userId: string | null | undefined) {
  if (userId && normalizePath(path) === `/playground/users/${userId}`) {
    return `/playground/users/${userId}/00_inbox`;
  }
  return path;
}

function makeVirtualRoot(name: string, path: string, aliases: WorkspacePathAlias[]): TreeNode {
  return {
    name,
    type: 'directory',
    path,
    aliasPath: name,
    virtual: true,
    expanded: true,
    loaded: true,
    children: aliases.map((alias) => ({
      name: alias.label,
      type: alias.type || 'directory',
      path: alias.canonicalPrefix,
      aliasPath: alias.aliasPrefix,
      children: alias.type === 'file' ? undefined : [],
      expanded: alias.type === 'file' ? undefined : false,
      loaded: alias.type === 'file' ? undefined : false,
    })),
  };
}

function normalizePath(path: string | null | undefined) {
  if (!path) return '/';
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  return parts.length ? `/${parts.join('/')}` : '/';
}

import { describe, expect, it } from 'vitest';
import {
  aliasPathForCanonicalPath,
  createUserModeRootNodes,
  displayPathForMode,
  getDeveloperModeStorageKey,
  getWorkspacePathAliases,
  userModeMutationTarget,
} from './workspaceFolderView';

describe('workspaceFolderView', () => {
  it('uses a developer mode key separate from chat debug mode', () => {
    expect(getDeveloperModeStorageKey('u1')).toBe('haro:developerMode:u1');
    expect(getDeveloperModeStorageKey(null)).toBe('haro:developerMode:anonymous');
  });

  it('builds user mode roots without exposing internal user ids in labels', () => {
    const roots = createUserModeRootNodes('u1');

    expect(roots.map((node) => node.name)).toEqual(['팀 폴더', '내 폴더']);
    expect(roots[1].children?.map((node) => node.name)).toEqual(['받은 파일', '작업 중', '결과', 'AGENTS.md']);
    expect(roots[1].children?.map((node) => node.aliasPath)).toEqual([
      '내 폴더/받은 파일',
      '내 폴더/작업 중',
      '내 폴더/결과',
      '내 폴더/AGENTS.md',
    ]);
    expect(roots[1].children?.at(-1)?.type).toBe('file');
  });

  it('keeps the alias mapping aligned with the backend policy', () => {
    expect(getWorkspacePathAliases('u1').map((alias) => [alias.aliasPrefix, alias.canonicalPrefix])).toEqual([
      ['팀 폴더/데이터', '/clean-room/data'],
      ['팀 폴더/규칙/스킬', '/clean-room/meta'],
      ['팀 폴더/공유 결과', '/clean-room/data/30_outputs'],
      ['내 폴더/받은 파일', '/playground/users/u1/00_inbox'],
      ['내 폴더/작업 중', '/playground/users/u1/20_working'],
      ['내 폴더/결과', '/playground/users/u1/30_outputs'],
      ['내 폴더/AGENTS.md', '/playground/users/u1/AGENTS.md'],
    ]);
  });

  it('converts canonical paths to user-friendly display paths in user mode only', () => {
    expect(aliasPathForCanonicalPath('/playground/users/u1/20_working/report.md', 'u1')).toBe('내 폴더/작업 중/report.md');
    expect(aliasPathForCanonicalPath('/playground/users/u1/AGENTS.md', 'u1')).toBe('내 폴더/AGENTS.md');
    expect(aliasPathForCanonicalPath('/clean-room/data/source.csv', 'u1')).toBe('팀 폴더/데이터/source.csv');
    expect(displayPathForMode('/playground/users/u1/20_working/report.md', 'developer', 'u1')).toBe('/playground/users/u1/20_working/report.md');
  });

  it('uses inbox as the mutation target for the user mode my-folder root', () => {
    expect(userModeMutationTarget('/playground/users/u1', 'u1')).toBe('/playground/users/u1/00_inbox');
    expect(userModeMutationTarget('/playground/users/u1/20_working', 'u1')).toBe('/playground/users/u1/20_working');
  });
});

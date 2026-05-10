import { aliasPathForCanonicalPath } from './workspaceFolderView';

const TOOL_LABELS: Record<string, string> = {
  file_create: '파일 생성',
  file_read: '파일 읽기',
  file_write: '파일 수정',
  file_delete: '파일 삭제',
  file_move: '파일 이동',
  file_export: '파일 내보내기',
  file_search: '파일 검색',
  file_count: '파일 개수 확인',
  dir_list: '폴더 조회',
  dir_create: '폴더 생성',
  dir_delete: '폴더 삭제',
  code_run: '코드 실행',
  web_preview: '웹 프리뷰 준비',
};

export function formatChatMessageContent(
  content: string | null,
  userId: string | null | undefined,
  showRawPaths: boolean,
) {
  const text = content || '';
  return showRawPaths ? text : replaceCanonicalPathsWithAliases(text, userId);
}

export function formatToolStepContent(
  content: string | null,
  metadata: any,
  showRawDetails: boolean,
) {
  const text = content || '';
  if (showRawDetails) return text;

  const toolName = extractToolName(metadata?.description || text);
  const label = TOOL_LABELS[toolName || ''] || '작업';
  const status = metadata?.status || '';
  const icon = status === 'completed' ? '✅' : status === 'blocked' ? '⬜' : '🔄';
  const suffix = status === 'completed' ? '완료' : status === 'blocked' ? '차단됨' : '진행 중';
  return `${icon} ${label} ${suffix}`;
}

export function replaceCanonicalPathsWithAliases(text: string, userId: string | null | undefined) {
  return text.replace(/\/(?:playground\/users|clean-room|90_archive|\.haro)\/[^\s`"'<>]*/g, (rawPath) => {
    const { path, trailing } = splitTrailingPunctuation(rawPath);
    return `${chatFriendlyPath(path, userId)}${trailing}`;
  });
}

function extractToolName(value: string) {
  return Object.keys(TOOL_LABELS).find((name) => value.includes(name)) || null;
}

function splitTrailingPunctuation(value: string) {
  let path = value;
  let trailing = '';
  while (/[),;:!?]$/.test(path)) {
    trailing = `${path[path.length - 1]}${trailing}`;
    path = path.slice(0, -1);
  }
  return { path, trailing };
}

function chatFriendlyPath(path: string, userId: string | null | undefined) {
  const chatPath = userId ? `/playground/users/${userId}/50_chats/` : '';
  if (chatPath && path.startsWith(chatPath)) {
    const rest = path.slice(chatPath.length);
    const parts = rest.split('/').filter(Boolean);
    const areaIndex = parts.findIndex((part) => ['inputs', 'working', 'outputs', 'summaries'].includes(part));
    if (areaIndex >= 0) {
      const area = parts[areaIndex];
      const remainder = parts.slice(areaIndex + 1).join('/');
      const areaLabel = area === 'outputs' ? '결과' : area === 'working' ? '작업' : area === 'inputs' ? '입력' : '요약';
      return remainder ? `채팅 임시공간/${areaLabel}/${remainder}` : `채팅 임시공간/${areaLabel}`;
    }
    return '채팅 임시공간';
  }
  return aliasPathForCanonicalPath(path, userId);
}

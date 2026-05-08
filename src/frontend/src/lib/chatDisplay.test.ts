import { describe, expect, it } from 'vitest';

import {
  formatChatMessageContent,
  formatToolStepContent,
  replaceCanonicalPathsWithAliases,
} from './chatDisplay';

describe('chatDisplay', () => {
  it('replaces canonical user paths with aliases for user-facing chat', () => {
    const text = '저장 위치: /playground/users/u1/30_outputs/report.md';

    expect(replaceCanonicalPathsWithAliases(text, 'u1')).toBe('저장 위치: 내 폴더/결과/report.md');
  });

  it('keeps raw paths when raw details are enabled', () => {
    const text = '대상 경로: /playground/users/u1/50_chats/chat/outputs/report.md';

    expect(formatChatMessageContent(text, 'u1', true)).toBe(text);
    expect(formatChatMessageContent(text, 'u1', false)).toBe('대상 경로: 채팅 임시공간/결과/report.md');
  });

  it('simplifies tool step content unless raw details are enabled', () => {
    const content = '✅ file_create 완료';
    const metadata = { description: 'file_create({"path":"x.md"})', status: 'completed' };

    expect(formatToolStepContent(content, metadata, false)).toBe('✅ 파일 생성 완료');
    expect(formatToolStepContent(content, metadata, true)).toBe(content);
  });
});

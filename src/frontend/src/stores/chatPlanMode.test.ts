import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  streamPost: vi.fn(),
}));

vi.mock('../lib/api', () => ({ api: mocks.api }));
vi.mock('../lib/sse', () => ({ streamPost: mocks.streamPost }));

import { loadPlanModeState, messages, planMode, sendMessage } from './chat';

function resetPlanMode() {
  messages.set([]);
  planMode.set({
    active: false,
    planSessionId: null,
    status: 'idle',
    planFilePath: '',
    planContent: '',
    approvalRequested: false,
    approvalSummary: '',
  });
}

describe('chat Plan Mode store', () => {
  beforeEach(() => {
    mocks.api.mockReset();
    mocks.streamPost.mockReset();
    resetPlanMode();
    let seq = 0;
    vi.stubGlobal('crypto', { randomUUID: () => `uuid-${++seq}` });
  });

  it('loads current Plan Mode state', async () => {
    mocks.api.mockResolvedValue({
      active: true,
      plan_session_id: 'plan-1',
      status: 'plan_awaiting_approval',
      plan_file_path: '/chat/working/plan.md',
      plan_content: '# Plan',
    });

    await loadPlanModeState('project-1', 'chat-1');

    expect(mocks.api).toHaveBeenCalledWith('/projects/project-1/chats/chat-1/plan-mode');
    expect(get(planMode)).toMatchObject({
      active: true,
      planSessionId: 'plan-1',
      status: 'plan_awaiting_approval',
      approvalRequested: true,
      planContent: '# Plan',
    });
    expect(get(messages)).toContainEqual(
      expect.objectContaining({
        id: 'plan-approval-plan-1',
        role: 'plan_approval',
        content: '계획 승인을 요청했습니다.',
        metadata: expect.objectContaining({
          planSessionId: 'plan-1',
          planContent: '# Plan',
          status: 'plan_awaiting_approval',
        }),
      })
    );
  });

  it('falls back to idle Plan Mode state when state loading fails', async () => {
    planMode.set({
      active: true,
      planSessionId: 'plan-1',
      status: 'plan_awaiting_approval',
      planFilePath: '/chat/working/plan.md',
      planContent: '# Plan',
      approvalRequested: true,
      approvalSummary: '검토해주세요',
    });
    mocks.api.mockRejectedValue(new Error('plan state unavailable'));

    await loadPlanModeState('project-1', 'chat-1');

    expect(get(planMode)).toMatchObject({
      active: false,
      planSessionId: null,
      status: 'idle',
      planFilePath: '',
      planContent: '',
      approvalRequested: false,
    });
  });

  it('sends Plan Mode request payload', async () => {
    let payload: any = null;
    mocks.streamPost.mockImplementation(async (_path, body, onEvent) => {
      payload = body;
      onEvent('done', {});
    });

    await sendMessage('project-1', 'chat-1', '계획 세워줘', { planModeRequested: true });

    expect(payload).toMatchObject({
      content: '계획 세워줘',
      plan_mode_requested: true,
      plan_response: null,
    });
  });

  it('updates approval card state from SSE', async () => {
    mocks.streamPost.mockImplementation(async (_path, _body, onEvent) => {
      onEvent('plan_approval_requested', {
        plan_session_id: 'plan-1',
        summary: '검토해주세요',
        plan_file_path: '/chat/working/plan.md',
        plan_content: '# Plan',
      });
      onEvent('done', {});
    });

    await sendMessage('project-1', 'chat-1', '계획', {});

    expect(get(planMode)).toMatchObject({
      active: true,
      planSessionId: 'plan-1',
      status: 'plan_awaiting_approval',
      approvalRequested: true,
      approvalSummary: '검토해주세요',
      planContent: '# Plan',
    });
    expect(get(messages)).toContainEqual(
      expect.objectContaining({
        role: 'plan_approval',
        content: '검토해주세요',
        metadata: expect.objectContaining({
          planSessionId: 'plan-1',
          planFilePath: '/chat/working/plan.md',
          planContent: '# Plan',
          status: 'plan_awaiting_approval',
        }),
      })
    );
  });

  it('adds a fresh approval card after feedback creates a revised plan', async () => {
    mocks.streamPost.mockImplementation(async (_path, _body, onEvent) => {
      onEvent('plan_approval_requested', {
        plan_session_id: 'plan-1',
        summary: '초안 승인 요청',
        plan_content: '# Draft 1',
      });
      onEvent('plan_rejected', {});
      onEvent('plan_approval_requested', {
        plan_session_id: 'plan-1',
        summary: '수정본 승인 요청',
        plan_content: '# Draft 2',
      });
      onEvent('done', {});
    });

    await sendMessage('project-1', 'chat-1', '계획', {});

    const planCards = get(messages).filter((msg) => msg.role === 'plan_approval');
    expect(planCards).toHaveLength(2);
    expect(planCards[0]).toMatchObject({
      content: '초안 승인 요청',
      metadata: expect.objectContaining({
        planContent: '# Draft 1',
        status: 'plan_rejected',
      }),
    });
    expect(planCards[1]).toMatchObject({
      content: '수정본 승인 요청',
      metadata: expect.objectContaining({
        planContent: '# Draft 2',
        status: 'plan_awaiting_approval',
      }),
    });
  });
});

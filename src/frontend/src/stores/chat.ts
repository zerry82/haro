import { writable, get } from 'svelte/store';
import { api } from '../lib/api';
import { streamPost } from '../lib/sse';

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  metadata?: any;
  created_at?: string;
}

interface TodoStep {
  description: string;
  status: string;
}

export interface DebugTraceEvent {
  id: string;
  round_index: number;
  event_type: string;
  payload: any;
  duration_ms?: number | null;
  created_at: string;
}

export interface DebugTraceResponse {
  message_id: string;
  has_trace: boolean;
  events: DebugTraceEvent[];
}

export interface PlanModeState {
  active: boolean;
  planSessionId: string | null;
  status: string;
  planFilePath: string;
  planContent: string;
  approvalRequested: boolean;
  approvalSummary: string;
}

export interface OpenFileSelectionContext {
  start_line?: number;
  end_line?: number;
  text_preview?: string;
}

export interface OpenFileContext {
  active_file_path?: string | null;
  opened_file_paths?: string[];
  language?: string;
  active_viewer_tab?: string;
  dirty?: boolean;
  selection?: OpenFileSelectionContext | null;
}

const idlePlanMode: PlanModeState = {
  active: false,
  planSessionId: null,
  status: 'idle',
  planFilePath: '',
  planContent: '',
  approvalRequested: false,
  approvalSummary: '',
};

export const messages = writable<ChatMessage[]>([]);
export const streaming = writable(false);
export const agentStatus = writable('idle');
export const todoSteps = writable<TodoStep[]>([]);
export const planMode = writable<PlanModeState>({ ...idlePlanMode });

function addPlanApprovalMessage(input: {
  planSessionId: string | null;
  summary: string;
  planFilePath: string;
  planContent: string;
  status: string;
  requirements?: any[];
  evidenceRequired?: boolean;
  evidenceLedgerHasSources?: boolean;
  asOfDate?: string | null;
  acceptanceChecksPresent?: boolean;
}) {
  if (!input.planSessionId) return;
  const metadata = {
    planApproval: true,
    planSessionId: input.planSessionId,
    summary: input.summary,
    planFilePath: input.planFilePath,
    planContent: input.planContent,
    status: input.status,
    requirements: input.requirements || [],
    evidenceRequired: Boolean(input.evidenceRequired),
    evidenceLedgerHasSources: Boolean(input.evidenceLedgerHasSources),
    asOfDate: input.asOfDate || null,
    acceptanceChecksPresent: Boolean(input.acceptanceChecksPresent),
  };
  messages.update((items) => {
    const pendingIndex = items.findIndex(
      (msg) =>
        msg.role === 'plan_approval' &&
        msg.metadata?.planSessionId === input.planSessionId &&
        msg.metadata?.status === 'plan_awaiting_approval'
    );
    if (pendingIndex >= 0) {
      return items.map((msg, index) =>
        index === pendingIndex
          ? { ...msg, role: 'plan_approval', content: input.summary, metadata }
          : msg
      );
    }
    const messageId = `plan-approval-${input.planSessionId}-${crypto.randomUUID()}`;
    return [...items, { id: messageId, role: 'plan_approval', content: input.summary, metadata }];
  });
}

function restorePlanApprovalMessage(input: {
  planSessionId: string | null;
  summary: string;
  planFilePath: string;
  planContent: string;
  status: string;
  requirements?: any[];
  evidenceRequired?: boolean;
  evidenceLedgerHasSources?: boolean;
  asOfDate?: string | null;
  acceptanceChecksPresent?: boolean;
}) {
  if (!input.planSessionId) return;
  const messageId = `plan-approval-${input.planSessionId}`;
  const metadata = {
    planApproval: true,
    planSessionId: input.planSessionId,
    summary: input.summary,
    planFilePath: input.planFilePath,
    planContent: input.planContent,
    status: input.status,
    requirements: input.requirements || [],
    evidenceRequired: Boolean(input.evidenceRequired),
    evidenceLedgerHasSources: Boolean(input.evidenceLedgerHasSources),
    asOfDate: input.asOfDate || null,
    acceptanceChecksPresent: Boolean(input.acceptanceChecksPresent),
  };
  messages.update((items) => {
    let updated = false;
    const next = items.map((msg) => {
      if (msg.id !== messageId) {
        return msg;
      }
      updated = true;
      return { ...msg, id: messageId, role: 'plan_approval', content: input.summary, metadata };
    });
    if (updated) return next;
    return [...items, { id: messageId, role: 'plan_approval', content: input.summary, metadata }];
  });
}

function updatePlanApprovalMessageStatus(planSessionId: string | null, status: string) {
  if (!planSessionId) return;
  messages.update((items) => {
    let targetIndex = -1;
    for (let index = items.length - 1; index >= 0; index -= 1) {
      const msg = items[index];
      if (msg.role !== 'plan_approval' || msg.metadata?.planSessionId !== planSessionId) continue;
      if (targetIndex < 0) targetIndex = index;
      if (msg.metadata?.status === 'plan_awaiting_approval') {
        targetIndex = index;
        break;
      }
    }
    if (targetIndex < 0) return items;
    return items.map((msg, index) =>
      index === targetIndex ? { ...msg, metadata: { ...(msg.metadata || {}), status } } : msg
    );
  });
}

export async function loadMessages(projectId: string, chatId: string) {
  const res: any = await api(`/projects/${projectId}/chats/${chatId}/messages`);
  messages.set(res.messages);
}

export async function loadDebugTrace(projectId: string, chatId: string, messageId: string): Promise<DebugTraceResponse> {
  return api(`/projects/${projectId}/chats/${chatId}/messages/${messageId}/debug-trace`);
}

export async function loadPlanModeState(projectId: string, chatId: string) {
  try {
    const res: any = await api(`/projects/${projectId}/chats/${chatId}/plan-mode`);
    const status = res.status || 'idle';
    const approvalRequested = status === 'plan_awaiting_approval';
    const summary = approvalRequested ? '계획 승인을 요청했습니다.' : '';
    planMode.set({
      active: Boolean(res.active),
      planSessionId: res.plan_session_id || null,
      status,
      planFilePath: res.plan_file_path || '',
      planContent: res.plan_content || '',
      approvalRequested,
      approvalSummary: summary,
    });
    if (approvalRequested) {
      restorePlanApprovalMessage({
        planSessionId: res.plan_session_id || null,
        summary,
        planFilePath: res.plan_file_path || '',
        planContent: res.plan_content || '',
        status,
      });
    }
  } catch {
    planMode.set({ ...idlePlanMode });
  }
}

export async function sendMessage(
  projectId: string,
  chatId: string,
  content: string,
  options: {
    debugEnabled?: boolean;
    planModeRequested?: boolean;
    planResponse?: { plan_session_id: string; action: 'approve' | 'reject'; feedback?: string };
    openFileContext?: OpenFileContext | null;
  } = {},
) {
  const clientMessageId = crypto.randomUUID();
  const debugEnabled = Boolean(options.debugEnabled);
  const userMsg: ChatMessage = {
    id: clientMessageId,
    role: 'user',
    content,
    metadata: {
      client_message_id: clientMessageId,
      debug_enabled: debugEnabled,
      open_file_context: options.openFileContext || null,
    },
  };
  messages.update((m) => [...m, userMsg]);
  streaming.set(true);
  todoSteps.set([]);

  let currentMsgId = '';
  let currentContent = '';

  try {
    await streamPost(
      `/projects/${projectId}/chats/${chatId}/messages`,
      {
        content,
        debug_enabled: debugEnabled,
        client_message_id: clientMessageId,
        plan_mode_requested: Boolean(options.planModeRequested),
        plan_response: options.planResponse || null,
        open_file_context: options.openFileContext || null,
      },
      (event, data) => {
      switch (event) {
        case 'user_message_saved':
          messages.update((m) =>
            m.map((msg) =>
              msg.id === data.client_message_id
                ? {
                    ...msg,
                    id: data.message_id,
                    metadata: {
                      ...(msg.metadata || {}),
                      server_message_id: data.message_id,
                      debug_enabled: data.debug_enabled,
                    },
                  }
                : msg
            )
          );
          break;
        case 'status':
          agentStatus.set(data.session_status);
          break;
        case 'message_start':
          currentMsgId = data.message_id;
          currentContent = '';
          messages.update((m) => [...m, { id: currentMsgId, role: 'assistant', content: '' }]);
          break;
        case 'message_delta':
          currentContent += data.content;
          messages.update((m) =>
            m.map((msg) => (msg.id === currentMsgId ? { ...msg, content: currentContent } : msg))
          );
          break;
        case 'message_end':
          break;
        case 'todo_step_updated': {
          const step = data.step;
          // 스텝을 메시지 흐름에 인라인으로 추가
          const stepIcon = step.status === 'completed' ? '✅' : step.status === 'in_progress' ? '🔄' : '⬜';
          const stepId = `step-${crypto.randomUUID()}`;
          
          // 이미 같은 description의 in_progress 스텝이 있으면 업데이트
          const existingSteps = get(messages);
          const existingIdx = existingSteps.findIndex(
            (m) => m.role === 'tool_step' && m.metadata?.description === step.description
          );
          if (existingIdx >= 0) {
            messages.update((m) =>
              m.map((msg, i) =>
                i === existingIdx
                  ? { ...msg, content: `${stepIcon} ${step.description}`, metadata: { ...step } }
                  : msg
              )
            );
          } else {
            messages.update((m) => [
              ...m,
              { id: stepId, role: 'tool_step', content: `${stepIcon} ${step.description}`, metadata: { ...step } },
            ]);
          }
          
          // todoSteps도 업데이트 (호환성)
          todoSteps.update((steps) => {
            const existing = steps.findIndex((s) => s.description === step.description);
            if (existing >= 0) {
              steps[existing] = step;
              return [...steps];
            }
            return [...steps, step];
          });
          break;
        }
        case 'file_changed':
          window.dispatchEvent(new CustomEvent('file-changed', { detail: data }));
          break;
        case 'plan_mode_entered':
          planMode.update((state) => ({
            ...state,
            active: true,
            planSessionId: data.plan_session_id,
            status: data.status || 'plan_drafting',
            planFilePath: data.plan_file_path || state.planFilePath,
            approvalRequested: false,
          }));
          break;
        case 'plan_file_updated':
          planMode.update((state) => ({
            ...state,
            active: true,
            planSessionId: data.plan_session_id || state.planSessionId,
            status: data.status || state.status || 'plan_drafting',
            planFilePath: data.plan_file_path || state.planFilePath,
            planContent: data.plan_content || '',
          }));
          break;
        case 'plan_approval_requested':
          {
            const currentPlan = get(planMode);
            const planSessionId = data.plan_session_id || currentPlan.planSessionId;
            const summary = data.summary || '계획 승인을 요청했습니다.';
            const planFilePath = data.plan_file_path || currentPlan.planFilePath;
            const planContent = data.plan_content || currentPlan.planContent;
            addPlanApprovalMessage({
              planSessionId,
              summary,
              planFilePath,
              planContent,
              status: 'plan_awaiting_approval',
              requirements: data.requirements || [],
              evidenceRequired: Boolean(data.evidence_required),
              evidenceLedgerHasSources: Boolean(data.evidence_ledger_has_sources),
              asOfDate: data.as_of_date || null,
              acceptanceChecksPresent: Boolean(data.acceptance_checks_present),
            });
            planMode.update((state) => ({
              ...state,
              active: true,
              planSessionId,
              status: 'plan_awaiting_approval',
              planFilePath,
              planContent,
              approvalRequested: true,
              approvalSummary: summary,
            }));
          }
          break;
        case 'plan_approved':
          updatePlanApprovalMessageStatus(get(planMode).planSessionId, 'plan_approved');
          planMode.update((state) => ({
            ...state,
            active: true,
            status: 'plan_approved',
            approvalRequested: false,
          }));
          break;
        case 'plan_rejected':
          updatePlanApprovalMessageStatus(get(planMode).planSessionId, 'plan_rejected');
          planMode.update((state) => ({
            ...state,
            active: true,
            status: 'plan_drafting',
            approvalRequested: false,
          }));
          break;
        case 'plan_mode_exited':
          updatePlanApprovalMessageStatus(get(planMode).planSessionId, data.status || 'execution_running');
          planMode.update((state) => ({
            ...state,
            active: false,
            status: data.status || 'execution_running',
            approvalRequested: false,
          }));
          break;
        case 'execution_completed':
          updatePlanApprovalMessageStatus(get(planMode).planSessionId, 'execution_completed');
          planMode.set({ ...idlePlanMode });
          break;
        case 'execution_todo_updated':
          if (data.step) {
            todoSteps.update((steps) => [...steps, data.step]);
          }
          break;
        case 'execution_blocked':
          messages.update((m) => [
            ...m,
            { id: crypto.randomUUID(), role: 'system', content: `⚠️ ${data.reason}` },
          ]);
          planMode.update((state) => ({ ...state, status: 'blocked' }));
          break;
        case 'summary_suggested':
          messages.update((m) => [
            ...m,
            { id: crypto.randomUUID(), role: 'system', content: `요약 제안: ${data.message}` },
          ]);
          break;
        case 'error':
          messages.update((m) => [
            ...m,
            { id: crypto.randomUUID(), role: 'system', content: `⚠️ ${data.message}` },
          ]);
          break;
        case 'done':
          agentStatus.set('idle');
          break;
      }
    });
  } catch (e: any) {
    messages.update((m) => [
      ...m,
      { id: crypto.randomUUID(), role: 'system', content: `⚠️ 오류: ${e.message}` },
    ]);
  } finally {
    streaming.set(false);
    agentStatus.set('idle');
  }
}

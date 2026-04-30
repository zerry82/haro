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

export const messages = writable<ChatMessage[]>([]);
export const streaming = writable(false);
export const agentStatus = writable('idle');
export const todoSteps = writable<TodoStep[]>([]);

export async function loadMessages(projectId: string, chatId: string) {
  const res: any = await api(`/projects/${projectId}/chats/${chatId}/messages`);
  messages.set(res.messages);
}

export async function loadDebugTrace(projectId: string, chatId: string, messageId: string): Promise<DebugTraceResponse> {
  return api(`/projects/${projectId}/chats/${chatId}/messages/${messageId}/debug-trace`);
}

export async function sendMessage(
  projectId: string,
  chatId: string,
  content: string,
  options: { debugEnabled?: boolean } = {},
) {
  const clientMessageId = crypto.randomUUID();
  const debugEnabled = Boolean(options.debugEnabled);
  const userMsg: ChatMessage = {
    id: clientMessageId,
    role: 'user',
    content,
    metadata: { client_message_id: clientMessageId, debug_enabled: debugEnabled },
  };
  messages.update((m) => [...m, userMsg]);
  streaming.set(true);
  todoSteps.set([]);

  let currentMsgId = '';
  let currentContent = '';

  try {
    await streamPost(
      `/projects/${projectId}/chats/${chatId}/messages`,
      { content, debug_enabled: debugEnabled, client_message_id: clientMessageId },
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

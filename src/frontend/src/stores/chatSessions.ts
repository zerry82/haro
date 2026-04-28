import { writable } from 'svelte/store';
import { api } from '../lib/api';

export interface ChatSessionItem {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export const chatSessions = writable<ChatSessionItem[]>([]);
export const currentChatId = writable<string | null>(null);

export async function loadChatSessions(projectId: string) {
  const res: any = await api(`/projects/${projectId}/chats`);
  chatSessions.set(res.chats);
}

export async function createChatSession(projectId: string, title: string = '새 채팅'): Promise<string> {
  const res: any = await api(`/projects/${projectId}/chats`, {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
  await loadChatSessions(projectId);
  return res.id;
}

export async function deleteChatSession(projectId: string, chatId: string) {
  await api(`/projects/${projectId}/chats/${chatId}`, { method: 'DELETE' });
  await loadChatSessions(projectId);
}

export async function renameChatSession(projectId: string, chatId: string, title: string) {
  await api(`/projects/${projectId}/chats/${chatId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
  await loadChatSessions(projectId);
}

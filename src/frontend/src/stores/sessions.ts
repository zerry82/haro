import { writable } from 'svelte/store';
import { api } from '../lib/api';

interface Session {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export const sessions = writable<Session[]>([]);
export const currentSessionId = writable<string | null>(null);

export async function loadSessions() {
  const res: any = await api('/sessions');
  sessions.set(res.sessions);
}

export async function createSession(title: string = '새 작업'): Promise<string> {
  const res: any = await api('/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
  await loadSessions();
  return res.id;
}

export async function deleteSession(id: string) {
  await api(`/sessions/${id}`, { method: 'DELETE' });
  await loadSessions();
}

export async function renameSession(id: string, title: string) {
  await api(`/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
  await loadSessions();
}

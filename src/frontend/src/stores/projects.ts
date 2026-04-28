import { writable } from 'svelte/store';
import { api } from '../lib/api';

export interface ProjectItem {
  id: string;
  title: string;
  status: string;
  container_status: string;
  created_at: string;
  updated_at: string;
  chat_session_count: number;
}

export const projects = writable<ProjectItem[]>([]);
export const currentProjectId = writable<string | null>(null);

export async function loadProjects() {
  const res: any = await api('/projects');
  projects.set(res.projects);
}

export async function createProject(title: string = '새 프로젝트'): Promise<string> {
  const res: any = await api('/projects', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
  await loadProjects();
  return res.id;
}

export async function deleteProject(id: string) {
  await api(`/projects/${id}`, { method: 'DELETE' });
  await loadProjects();
}

export async function renameProject(id: string, title: string) {
  await api(`/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
  await loadProjects();
}

import { writable } from 'svelte/store';
import { api, setToken, clearToken, getToken } from '../lib/api';

interface User {
  id: string;
  email: string;
  name: string;
}

export const user = writable<User | null>(null);
export const isAuthenticated = writable(false);

export async function login(email: string, password: string) {
  const res: any = await api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(res.access_token);
  user.set(res.user);
  isAuthenticated.set(true);
}

export async function register(email: string, password: string, name: string) {
  await api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
}

export async function checkAuth() {
  const token = getToken();
  if (!token) return false;
  try {
    const u: any = await api('/auth/me');
    user.set(u);
    isAuthenticated.set(true);
    return true;
  } catch {
    clearToken();
    isAuthenticated.set(false);
    return false;
  }
}

export function logout() {
  clearToken();
  user.set(null);
  isAuthenticated.set(false);
}

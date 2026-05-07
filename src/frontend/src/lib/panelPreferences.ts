export function loadStoredPanelWidth(key: string, fallback: number) {
  if (typeof localStorage === 'undefined') return fallback;
  const saved = Number(localStorage.getItem(key));
  return Number.isFinite(saved) && saved > 0 ? saved : fallback;
}

export function saveStoredPanelWidth(key: string, value: number) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(key, String(Math.round(value)));
}

export function loadStoredBool(key: string, fallback: boolean) {
  if (typeof localStorage === 'undefined') return fallback;
  const saved = localStorage.getItem(key);
  if (saved === null) return fallback;
  return saved === 'true';
}

export function saveStoredBool(key: string, value: boolean) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(key, value ? 'true' : 'false');
}

export function getDebugModeStorageKey(userId?: string | null) {
  return `haro:debugMode:${userId || 'anonymous'}`;
}

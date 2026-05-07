import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getDebugModeStorageKey,
  loadStoredBool,
  loadStoredPanelWidth,
  saveStoredBool,
  saveStoredPanelWidth,
} from './panelPreferences';

describe('panelPreferences', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('builds user-specific debug mode storage keys', () => {
    expect(getDebugModeStorageKey('u1')).toBe('haro:debugMode:u1');
    expect(getDebugModeStorageKey(null)).toBe('haro:debugMode:anonymous');
  });

  it('loads and saves values through localStorage when available', () => {
    const values = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    });

    expect(loadStoredPanelWidth('width', 300)).toBe(300);
    saveStoredPanelWidth('width', 312.7);
    expect(loadStoredPanelWidth('width', 300)).toBe(313);
    expect(loadStoredBool('debug', false)).toBe(false);
    saveStoredBool('debug', true);
    expect(loadStoredBool('debug', false)).toBe(true);
  });
});

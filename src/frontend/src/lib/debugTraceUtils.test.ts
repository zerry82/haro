import { describe, expect, it } from 'vitest';

import {
  buildDebugTraceExport,
  debugMacroLabel,
  debugEventLabel,
  debugPayloadSections,
  formatDebugPayload,
  highlightDebugPayload,
  isDebugInspectable,
} from './debugTraceUtils';

describe('debugTraceUtils', () => {
  it('formats and highlights debug payloads', () => {
    expect(formatDebugPayload({ ok: true })).toContain('"ok": true');
    expect(highlightDebugPayload({ ok: true })).toContain('debug-json-key');
    expect(highlightDebugPayload({ ok: true })).toContain('debug-json-boolean');
  });

  it('builds sections for known event types', () => {
    const sections = debugPayloadSections('tool_call', { tool: 'file_read', args: { path: '/a.md' } });

    expect(sections.map((section) => section.title)).toEqual(['도구 이름', '인자']);
    expect(sections[1].code).toBe(true);
  });

  it('shows prompt macro references in llm request sections', () => {
    const sections = debugPayloadSections('llm_request', {
      model: 'gemini-3-flash-preview',
      system_instruction: { $macro: 'system_prompt.full' },
      system_prompt_hash: 'sha256:abc',
      system_prompt_chars: 123,
      prompt_cache: { strategy: 'gemini_explicit_stable_system', cache_state: 'reused' },
      contents: [],
      config: { cached_content: 'cachedContents/1' },
    });

    expect(debugMacroLabel({ $macro: 'system_prompt.full' })).toBe('$macro: system_prompt.full');
    expect(sections.find((section) => section.title === 'System Instruction')?.content)
      .toBe('$macro: system_prompt.full');
    expect(sections.find((section) => section.title === 'Prompt Cache')?.code).toBe(true);
  });

  it('maps labels and export payloads', () => {
    expect(debugEventLabel('router_result')).toBe('라우터 판단');
    expect(debugEventLabel('custom')).toBe('custom');
    expect(isDebugInspectable('user')).toBe(true);
    expect(isDebugInspectable('assistant')).toBe(false);
    expect(buildDebugTraceExport(
      'project-1',
      'chat-1',
      { id: 'm1', role: 'user', content: 'hello' },
      {
        prompt_macros: {
          'system_prompt.full': { text: 'full prompt' },
          'system_prompt.cached_system': { text: 'cached prompt' },
          'system_prompt.runtime_context': { text: 'runtime context' },
        },
        events: [],
      },
      '2026-05-07T00:00:00.000Z',
    )).toEqual({
      exported_at: '2026-05-07T00:00:00.000Z',
      project_id: 'project-1',
      chat_id: 'chat-1',
      message: {
        id: 'm1',
        role: 'user',
        content: 'hello',
        metadata: null,
        created_at: null,
      },
      trace: {
        prompt_macros: {
          'system_prompt.full': { text: 'full prompt' },
          'system_prompt.cached_system': { text: 'cached prompt' },
          'system_prompt.runtime_context': { text: 'runtime context' },
        },
        events: [],
      },
    });
  });
});

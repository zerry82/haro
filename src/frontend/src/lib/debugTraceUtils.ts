export type DebugPayloadSection = { title: string; content: string; code?: boolean };

export type DebugTraceExportMessage = {
  id: string;
  role: string;
  content: string;
  metadata?: unknown;
  created_at?: string | null;
};

export function isDebugInspectable(role: string) {
  return role === 'user';
}

export function formatDebugPayload(payload: unknown) {
  if (typeof payload === 'string') return payload;
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

export function escapeDebugHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function highlightDebugPayload(payload: unknown) {
  const escaped = escapeDebugHtml(formatDebugPayload(payload));
  return escaped.replace(
    /("(\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let className = 'debug-json-number';
      if (/^"/.test(match)) {
        className = /:$/.test(match) ? 'debug-json-key' : 'debug-json-string';
      } else if (/true|false/.test(match)) {
        className = 'debug-json-boolean';
      } else if (/null/.test(match)) {
        className = 'debug-json-null';
      }
      return `<span class="${className}">${match}</span>`;
    }
  );
}

export function stringifyDebugValue(value: unknown) {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function debugMacroLabel(value: unknown) {
  const record = debugPayloadRecord(value);
  const macroId = record.$macro;
  if (typeof macroId === 'string') {
    return `$macro: ${macroId}`;
  }
  return stringifyDebugValue(value);
}

export function debugPayloadRecord(payload: unknown): Record<string, unknown> {
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    return payload as Record<string, unknown>;
  }
  return { value: payload };
}

export function debugContentText(entry: unknown) {
  const record = debugPayloadRecord(entry);
  const parts = record.parts;
  if (Array.isArray(parts)) {
    return parts
      .map((part) => {
        const partRecord = debugPayloadRecord(part);
        return typeof partRecord.text === 'string' ? partRecord.text : stringifyDebugValue(part);
      })
      .filter(Boolean)
      .join('\n\n');
  }
  return stringifyDebugValue(entry);
}

export function debugPayloadSections(eventType: string, payload: unknown): DebugPayloadSection[] {
  const record = debugPayloadRecord(payload);
  const sections: DebugPayloadSection[] = [];

  if (eventType === 'llm_request') {
    sections.push({ title: '모델', content: stringifyDebugValue(record.model) || '-' });
    sections.push({ title: 'System Instruction', content: debugMacroLabel(record.system_instruction) });
    if (record.system_prompt_hash) {
      sections.push({ title: 'System Prompt Hash', content: stringifyDebugValue(record.system_prompt_hash) });
    }
    if (record.system_prompt_chars) {
      sections.push({ title: 'System Prompt Chars', content: stringifyDebugValue(record.system_prompt_chars) });
    }
    if (record.cached_system_hash) {
      sections.push({ title: 'Cached System Hash', content: stringifyDebugValue(record.cached_system_hash) });
    }
    if (record.cached_system_chars) {
      sections.push({ title: 'Cached System Chars', content: stringifyDebugValue(record.cached_system_chars) });
    }
    if (record.runtime_context_hash) {
      sections.push({ title: 'Runtime Context Hash', content: stringifyDebugValue(record.runtime_context_hash) });
    }
    if (record.runtime_context_chars) {
      sections.push({ title: 'Runtime Context Chars', content: stringifyDebugValue(record.runtime_context_chars) });
    }
    if (record.prompt_cache) {
      sections.push({ title: 'Prompt Cache', content: stringifyDebugValue(record.prompt_cache), code: true });
    }
    addContentSections(sections, record.contents);
    sections.push({ title: 'Generation Config', content: stringifyDebugValue(record.config), code: true });
    return sections;
  }

  if (eventType === 'llm_response') {
    sections.push({ title: '응답 원문', content: stringifyDebugValue(record.text) });
    sections.push({ title: 'Tool Call 포함 여부', content: record.has_tool_call ? '예' : '아니오' });
    if (record.usage_metadata) {
      sections.push({ title: 'Usage Metadata', content: stringifyDebugValue(record.usage_metadata), code: true });
    }
    if (record.parsed_tool_call) {
      sections.push({ title: '파싱된 Tool Call', content: stringifyDebugValue(record.parsed_tool_call), code: true });
    }
    return sections;
  }

  if (eventType === 'tool_call') {
    sections.push({ title: '도구 이름', content: stringifyDebugValue(record.tool) || '-' });
    sections.push({ title: '인자', content: stringifyDebugValue(record.args), code: true });
    return sections;
  }

  if (eventType === 'tool_result') {
    sections.push({ title: '도구 이름', content: stringifyDebugValue(record.tool) || '-' });
    sections.push({ title: '실행 결과', content: stringifyDebugValue(record.result) });
    return sections;
  }

  if (eventType === 'error') {
    sections.push({ title: '오류 메시지', content: stringifyDebugValue(record.message) });
    sections.push({ title: 'Traceback', content: stringifyDebugValue(record.traceback), code: true });
    return sections;
  }

  if (eventType === 'gate_decision') {
    sections.push({ title: '판단', content: stringifyDebugValue(record.decision) || '-' });
    sections.push({ title: '이유', content: stringifyDebugValue(record.reason) || '-' });
    if (record.candidates) sections.push({ title: '후보 작업', content: stringifyDebugValue(record.candidates), code: true });
    return sections;
  }

  if (eventType === 'router_result') {
    sections.push({ title: '의도', content: stringifyDebugValue(record.intent) || '-' });
    sections.push({ title: '실행 가능 여부', content: record.can_execute ? '예' : '아니오' });
    sections.push({ title: '선택 도구', content: stringifyDebugValue(record.selected_tools), code: true });
    sections.push({ title: '부족한 정보', content: stringifyDebugValue(record.missing_info), code: true });
    sections.push({ title: '질문', content: stringifyDebugValue(record.question) || '-' });
    sections.push({ title: '판단 이유', content: stringifyDebugValue(record.reason) || '-' });
    return sections;
  }

  if (eventType === 'selected_tools') {
    sections.push({ title: '선택 도구', content: stringifyDebugValue(record.selected_tools), code: true });
    sections.push({ title: '선택 스킬', content: stringifyDebugValue(record.selected_skills), code: true });
    return sections;
  }

  Object.entries(record).forEach(([key, value]) => {
    sections.push({ title: key, content: stringifyDebugValue(value), code: typeof value !== 'string' });
  });
  return sections;
}

export function debugEventLabel(eventType: string) {
  switch (eventType) {
    case 'llm_request': return 'LLM에게 보낸 내용';
    case 'llm_response': return 'LLM이 돌려준 내용';
    case 'tool_call': return '실행하려 한 도구';
    case 'tool_result': return '도구 실행 결과';
    case 'error': return '오류';
    case 'gate_decision': return '메시지 게이트 판단';
    case 'router_result': return '라우터 판단';
    case 'clarification_question': return '맥락 확인 질문';
    case 'clarification_answer': return '맥락 확인 답변';
    case 'selected_tools': return '선택된 도구/스킬';
    case 'result': return '작업 결과';
    default: return eventType;
  }
}

export function buildDebugTraceExport(
  projectId: string | null,
  chatId: string | null,
  message: DebugTraceExportMessage | null,
  trace: unknown,
  exportedAt = new Date().toISOString()
) {
  return {
    exported_at: exportedAt,
    project_id: projectId,
    chat_id: chatId,
    message: message ? {
      id: message.id,
      role: message.role,
      content: message.content,
      metadata: message.metadata || null,
      created_at: message.created_at || null,
    } : null,
    trace,
  };
}

function addContentSections(sections: DebugPayloadSection[], contents: unknown) {
  if (!Array.isArray(contents)) {
    sections.push({ title: '대화 내용', content: stringifyDebugValue(contents), code: true });
    return;
  }
  contents.forEach((entry, index) => {
    const record = debugPayloadRecord(entry);
    const role = typeof record.role === 'string' ? record.role : 'unknown';
    sections.push({
      title: `대화 내용 ${index + 1} · ${role}`,
      content: debugContentText(entry),
    });
  });
}

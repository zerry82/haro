<script lang="ts">
  import { onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated } from '../stores/auth';
  import { api } from '../lib/api';

  let { params = {} }: { params?: { sessionId?: string } } = $props();

  interface LogEntry {
    id: string;
    round_index: number;
    event_type: string;
    content: string;
    duration_ms: number | null;
    created_at: string;
  }

  interface SessionItem {
    id: string;
    title: string;
  }

  let sessions = $state<SessionItem[]>([]);
  let selectedSessionId = $state<string | null>(params.sessionId || null);
  let logs = $state<LogEntry[]>([]);
  let loading = $state(false);
  let expandedIds = $state<Set<string>>(new Set());

  onMount(async () => {
    if (!$isAuthenticated) { push('/login'); return; }
    const res: any = await api('/sessions');
    sessions = res.sessions;
    if (selectedSessionId) await loadLogs(selectedSessionId);
  });

  async function loadLogs(sessionId: string) {
    selectedSessionId = sessionId;
    loading = true;
    try {
      const res: any = await api(`/sessions/${sessionId}/logs`);
      logs = res.logs;
    } catch { logs = []; }
    loading = false;
  }

  function toggleExpand(id: string) {
    const next = new Set(expandedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedIds = next;
  }

  function eventIcon(type: string) {
    switch (type) {
      case 'llm_request': return '📤';
      case 'llm_response': return '📥';
      case 'tool_call': return '🔧';
      case 'tool_result': return '✅';
      case 'error': return '❌';
      default: return '📋';
    }
  }

  function eventLabel(type: string) {
    switch (type) {
      case 'llm_request': return 'LLM 요청';
      case 'llm_response': return 'LLM 응답';
      case 'tool_call': return '도구 호출';
      case 'tool_result': return '도구 결과';
      case 'error': return '에러';
      default: return type;
    }
  }

  function eventColor(type: string) {
    switch (type) {
      case 'llm_request': return '#4a9eff';
      case 'llm_response': return '#50c878';
      case 'tool_call': return '#ffa500';
      case 'tool_result': return '#9370db';
      case 'error': return '#e94560';
      default: return '#888';
    }
  }

  function formatTime(iso: string) {
    return new Date(iso).toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>📊 에이전트 로그</h2>
      <button class="back-btn" onclick={() => push('/chat')}>← 채팅으로</button>
    </div>
    <div class="session-list">
      {#each sessions as s}
        <button
          class="session-item"
          class:active={selectedSessionId === s.id}
          onclick={() => loadLogs(s.id)}
        >
          {s.title}
        </button>
      {/each}
    </div>
  </aside>

  <main class="log-panel">
    {#if !selectedSessionId}
      <div class="empty">좌측에서 세션을 선택하세요</div>
    {:else if loading}
      <div class="empty">로딩 중...</div>
    {:else if logs.length === 0}
      <div class="empty">이 세션에 로그가 없습니다</div>
    {:else}
      <div class="log-header">
        <span>총 {logs.length}개 이벤트</span>
        <span class="legend">
          <span style="color:#4a9eff">📤 LLM요청</span>
          <span style="color:#50c878">📥 LLM응답</span>
          <span style="color:#ffa500">🔧 도구호출</span>
          <span style="color:#9370db">✅ 도구결과</span>
        </span>
      </div>
      <div class="timeline">
        {#each logs as log}
          <div class="log-entry" style="border-left-color: {eventColor(log.event_type)}">
            <button class="log-summary" onclick={() => toggleExpand(log.id)}>
              <span class="log-icon">{eventIcon(log.event_type)}</span>
              <span class="log-type" style="color: {eventColor(log.event_type)}">{eventLabel(log.event_type)}</span>
              <span class="log-round">R{log.round_index}</span>
              {#if log.duration_ms != null}
                <span class="log-duration">{log.duration_ms.toFixed(0)}ms</span>
              {/if}
              <span class="log-time">{formatTime(log.created_at)}</span>
              <span class="log-expand">{expandedIds.has(log.id) ? '▼' : '▶'}</span>
            </button>
            {#if expandedIds.has(log.id)}
              <div class="log-content">
                <pre>{log.content}</pre>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </main>
</div>

<style>
  .layout { display: flex; height: 100vh; }
  .sidebar { width: 260px; background: #0f3460; display: flex; flex-direction: column; border-right: 1px solid #333; }
  .sidebar-header { padding: 1rem; border-bottom: 1px solid #333; }
  .sidebar-header h2 { margin: 0 0 0.75rem; color: #e94560; font-size: 1.1rem; }
  .back-btn { width: 100%; padding: 0.4rem; border: 1px solid #555; border-radius: 6px; background: transparent; color: #e0e0e0; cursor: pointer; font-size: 0.8rem; }
  .back-btn:hover { border-color: #e94560; }
  .session-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
  .session-item { display: block; width: 100%; padding: 0.5rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem; margin-bottom: 2px; background: transparent; border: none; color: #e0e0e0; text-align: left; font-family: inherit; }
  .session-item:hover { background: #16213e; }
  .session-item.active { background: #1a1a2e; color: #e94560; }

  .log-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .log-header { padding: 0.75rem 1rem; background: #16213e; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; }
  .legend { display: flex; gap: 1rem; font-size: 0.75rem; }

  .timeline { flex: 1; overflow-y: auto; padding: 0.75rem 1rem; }
  .log-entry { border-left: 3px solid #555; margin-bottom: 0.25rem; margin-left: 0.5rem; }
  .log-summary { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.75rem; cursor: pointer; width: 100%; background: transparent; border: none; color: #e0e0e0; font-family: inherit; font-size: 0.8rem; text-align: left; }
  .log-summary:hover { background: #16213e; }
  .log-icon { font-size: 1rem; }
  .log-type { font-weight: 600; min-width: 70px; }
  .log-round { background: #333; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; }
  .log-duration { color: #888; font-size: 0.75rem; }
  .log-time { color: #666; font-size: 0.7rem; margin-left: auto; }
  .log-expand { color: #666; font-size: 0.7rem; }

  .log-content { padding: 0.5rem 0.75rem 0.5rem 2rem; }
  .log-content pre { margin: 0; padding: 0.75rem; background: #0a0a1a; border-radius: 6px; font-size: 0.75rem; line-height: 1.5; white-space: pre-wrap; word-break: break-all; max-height: 400px; overflow-y: auto; color: #ccc; }

  .empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #555; }
</style>

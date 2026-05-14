<script lang="ts">
  import type { ChatMessage, DebugTraceResponse } from '../stores/chat';

  type DebugPayloadView = 'expanded' | 'json';
  type DebugPayloadSection = { title: string; content: string; code?: boolean };

  let {
    debugTraceLoading,
    debugTraceError,
    debugTrace,
    debugTraceMessage,
    debugPayloadView,
    debugTraceCopyMessage,
    onClose,
    onPayloadViewChange,
    onCopyFullDebugTrace,
    onCopyDebugPayload,
    debugEventLabel,
    debugPayloadSections,
    highlightDebugPayload,
  }: {
    debugTraceLoading: boolean;
    debugTraceError: string;
    debugTrace: DebugTraceResponse | null;
    debugTraceMessage: ChatMessage | null;
    debugPayloadView: DebugPayloadView;
    debugTraceCopyMessage: string;
    onClose: () => void;
    onPayloadViewChange: (view: DebugPayloadView) => void;
    onCopyFullDebugTrace: () => void;
    onCopyDebugPayload: (payload: unknown) => void;
    debugEventLabel: (eventType: string) => string;
    debugPayloadSections: (eventType: string, payload: unknown) => DebugPayloadSection[];
    highlightDebugPayload: (payload: unknown) => string;
  } = $props();

  function getPromptMacros(trace: DebugTraceResponse | null): { id: string; macro: Record<string, any> }[] {
    const macros = trace?.prompt_macros;
    if (!macros || typeof macros !== 'object') return [];
    return Object.entries(macros)
      .filter((entry): entry is [string, Record<string, any>] => Boolean(entry[1]) && typeof entry[1] === 'object')
      .map(([id, macro]) => ({ id, macro }));
  }

  function macroText(macro: Record<string, any> | null) {
    return typeof macro?.text === 'string' ? macro.text : '';
  }

  function macroMeta(macro: Record<string, any> | null) {
    const parts = [];
    if (macro?.chars) parts.push(`${macro.chars} chars`);
    if (macro?.sha256) parts.push(String(macro.sha256));
    return parts.join(' · ');
  }
</script>

<div class="modal-backdrop" role="presentation" onclick={onClose}>
  <div
    class="debug-modal"
    role="dialog"
    aria-modal="true"
    aria-label="디버그 trace"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <header class="debug-modal-header">
      <div class="debug-modal-title">
        <strong>디버그 trace</strong>
        <span>{debugTraceMessage?.created_at || '현재 메시지'}</span>
      </div>
      <button type="button" class="modal-close" onclick={onClose}>닫기</button>
    </header>
    <div class="debug-message-preview">{debugTraceMessage?.content}</div>
    <div class="debug-view-toggle" role="group" aria-label="디버그 payload 보기 방식">
      <button
        type="button"
        class:active={debugPayloadView === 'expanded'}
        onclick={() => onPayloadViewChange('expanded')}
      >풀어서 보기</button>
      <button
        type="button"
        class:active={debugPayloadView === 'json'}
        onclick={() => onPayloadViewChange('json')}
      >JSON</button>
      <button
        type="button"
        class="debug-copy-all"
        disabled={!debugTrace?.has_trace || debugTraceLoading}
        onclick={onCopyFullDebugTrace}
      >전체 JSON 복사</button>
      {#if debugTraceCopyMessage}
        <span class="debug-copy-message">{debugTraceCopyMessage}</span>
      {/if}
    </div>
    <div class="debug-modal-body">
      {#if debugTraceLoading}
        <div class="empty">디버그 기록을 불러오는 중...</div>
      {:else if debugTraceError}
        <div class="side-error">{debugTraceError}</div>
      {:else if !debugTrace?.has_trace}
        <div class="empty">이 메시지는 디버그 기록이 없습니다.</div>
      {:else}
        {#each getPromptMacros(debugTrace) as promptMacro}
          <details class="debug-event prompt-macro" open>
            <summary>
              <span>{promptMacro.id}</span>
              <small>{macroMeta(promptMacro.macro)}</small>
            </summary>
            <div class="debug-event-toolbar">
              <span>prompt macro</span>
              <button type="button" class="link-btn" onclick={() => onCopyDebugPayload(promptMacro.macro)}>복사</button>
            </div>
            {#if debugPayloadView === 'expanded'}
              <div class="debug-expanded-view">
                <section class="debug-md-section">
                  <h4>Macro Metadata</h4>
                  <pre class="debug-md-code">{JSON.stringify({ id: promptMacro.macro?.id, sha256: promptMacro.macro?.sha256, chars: promptMacro.macro?.chars, sections: promptMacro.macro?.sections }, null, 2)}</pre>
                </section>
                <section class="debug-md-section">
                  <h4>Prompt Text</h4>
                  <pre class="debug-md-code prompt-text">{macroText(promptMacro.macro) || '-'}</pre>
                </section>
              </div>
            {:else}
              <pre class="debug-payload">{@html highlightDebugPayload(promptMacro.macro)}</pre>
            {/if}
          </details>
        {/each}
        {#each debugTrace.events as event}
          <details class="debug-event" open={event.round_index === 0}>
            <summary>
              <span>{debugEventLabel(event.event_type)}</span>
              <small>round {event.round_index}{event.duration_ms ? ` · ${Math.round(event.duration_ms)}ms` : ''}</small>
            </summary>
            <div class="debug-event-toolbar">
              <span>{event.created_at}</span>
              <button type="button" class="link-btn" onclick={() => onCopyDebugPayload(event.payload)}>복사</button>
            </div>
            {#if debugPayloadView === 'expanded'}
              <div class="debug-expanded-view">
                {#each debugPayloadSections(event.event_type, event.payload) as section}
                  <section class="debug-md-section">
                    <h4>{section.title}</h4>
                    {#if section.code}
                      <pre class="debug-md-code">{section.content || '-'}</pre>
                    {:else}
                      <div class="debug-md-text">{section.content || '-'}</div>
                    {/if}
                  </section>
                {/each}
              </div>
            {:else}
              <pre class="debug-payload">{@html highlightDebugPayload(event.payload)}</pre>
            {/if}
          </details>
        {/each}
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-backdrop { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.46); backdrop-filter: blur(2px); }
  .modal-close { flex-shrink: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-muted); padding: 0.35rem 0.7rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .modal-close:hover { border-color: var(--color-pink); color: var(--color-pink); background: var(--color-pink-soft); }
  .link-btn { background: transparent; border: none; color: var(--color-text-muted); cursor: pointer; font: inherit; font-size: 0.75rem; }
  .link-btn:hover:not(:disabled) { color: var(--color-accent-strong); }
  .link-btn:disabled { cursor: default; opacity: 0.45; }
  .side-error { border: 1px solid var(--color-danger-soft); border-radius: var(--radius-md); background: var(--color-danger-soft); color: var(--color-danger); padding: 0.6rem; font-size: 0.75rem; line-height: 1.45; }
  .empty { color: var(--color-text-muted); font-size: 0.8rem; padding: 1rem; text-align: center; }
  .debug-modal { width: min(920px, 92vw); max-height: 86vh; display: flex; flex-direction: column; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); color: var(--color-text); box-shadow: 0 22px 70px rgba(15, 23, 42, 0.28); overflow: hidden; }
  .debug-modal-header { flex-shrink: 0; display: flex; align-items: center; gap: 1rem; padding: 0.8rem 1rem; border-bottom: 1px solid var(--color-border); background: var(--color-sidebar); }
  .debug-modal-title { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.15rem; }
  .debug-modal-title strong { font-size: 0.95rem; }
  .debug-modal-title span { color: var(--color-text-muted); font-size: 0.72rem; }
  .debug-message-preview { flex-shrink: 0; max-height: 110px; overflow: auto; padding: 0.75rem 1rem; border-bottom: 1px solid var(--color-border); background: var(--color-info-soft); color: var(--color-text); white-space: pre-wrap; font-size: 0.8rem; line-height: 1.45; }
  .debug-view-toggle { flex-shrink: 0; display: flex; align-items: center; gap: 0.35rem; padding: 0.55rem 1rem; border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
  .debug-view-toggle button { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-muted); padding: 0.3rem 0.65rem; font: inherit; font-size: 0.75rem; cursor: pointer; }
  .debug-view-toggle button:hover { border-color: var(--color-pink); color: var(--color-pink); }
  .debug-view-toggle button.active { border-color: var(--color-pink); background: var(--color-pink-soft); color: var(--color-pink); font-weight: 700; }
  .debug-view-toggle button:disabled { cursor: default; opacity: 0.45; }
  .debug-copy-all { margin-left: auto; }
  .debug-copy-message { color: var(--color-accent-strong); font-size: 0.72rem; white-space: nowrap; }
  .debug-modal-body { flex: 1; min-height: 0; overflow: auto; padding: 0.85rem; background: var(--color-canvas); }
  .debug-event { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); margin-bottom: 0.65rem; overflow: hidden; }
  .debug-event.prompt-macro { border-color: var(--color-accent-soft); }
  .debug-event summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.65rem 0.8rem; cursor: pointer; font-weight: 700; font-size: 0.82rem; }
  .debug-event summary small { color: var(--color-text-muted); font-weight: 500; }
  .debug-event-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.4rem 0.8rem; border-top: 1px solid var(--color-border-soft); color: var(--color-text-muted); font-size: 0.7rem; }
  .debug-expanded-view { display: flex; flex-direction: column; gap: 0.65rem; padding: 0.75rem; border-top: 1px solid var(--color-border-soft); background: var(--color-canvas); }
  .debug-md-section { border: 1px solid var(--color-border-soft); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }
  .debug-md-section h4 { margin: 0; padding: 0.45rem 0.7rem; border-bottom: 1px solid var(--color-border-soft); background: var(--color-sidebar); color: var(--color-text); font-size: 0.75rem; }
  .debug-md-text { padding: 0.7rem 0.8rem; white-space: pre-wrap; word-break: break-word; color: var(--color-text); font-size: 0.78rem; line-height: 1.55; }
  .debug-md-code { margin: 0; padding: 0.7rem 0.8rem; max-height: 320px; overflow: auto; background: var(--color-sidebar); color: var(--color-text); font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .debug-md-code.prompt-text { max-height: 440px; }
  .debug-payload { margin: 0; max-height: 420px; overflow: auto; border-top: 1px solid var(--color-border-soft); background: #0f172a; color: #dbeafe; padding: 0.85rem; font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.55; tab-size: 2; white-space: pre-wrap; word-break: break-word; }
  .debug-payload :global(.debug-json-key) { color: #93c5fd; font-weight: 700; }
  .debug-payload :global(.debug-json-string) { color: #86efac; }
  .debug-payload :global(.debug-json-number) { color: #fbbf24; }
  .debug-payload :global(.debug-json-boolean) { color: #f0abfc; font-weight: 700; }
  .debug-payload :global(.debug-json-null) { color: #94a3b8; font-style: italic; }
</style>

<script lang="ts">
  import type { ChatMessage, PlanModeState } from '../stores/chat';
  import type { ChatSessionItem } from '../stores/chatSessions';

  let {
    width,
    showChatList,
    agentStatus,
    planMode,
    planModeRequested,
    debugMode,
    summarizingChat,
    streaming,
    chatActionMessage,
    chatSessions,
    currentChatId,
    messages,
    inputText,
    onShowChatListChange,
    onPlanModeRequestedChange,
    onDebugModeChange,
    onInputTextChange,
    onSelectChat,
    onDeleteChat,
    onNewChat,
    onSend,
    onApprovePlan,
    onRejectPlan,
    onSummarizeChat,
    onMessagesElementChange,
    renderChatMarkdown,
    formatToolStepContent,
    isDebugInspectable,
    onOpenDebugTrace,
    onDebugMessageKeydown,
  }: {
    width: number;
    showChatList: boolean;
    agentStatus: string;
    planMode: PlanModeState;
    planModeRequested: boolean;
    debugMode: boolean;
    summarizingChat: boolean;
    streaming: boolean;
    chatActionMessage: string;
    chatSessions: ChatSessionItem[];
    currentChatId: string | null;
    messages: ChatMessage[];
    inputText: string;
    onShowChatListChange: (value: boolean) => void;
    onPlanModeRequestedChange: (value: boolean) => void;
    onDebugModeChange: (value: boolean) => void;
    onInputTextChange: (value: string) => void;
    onSelectChat: (chatId: string) => void;
    onDeleteChat: (chatId: string) => void;
    onNewChat: () => void;
    onSend: () => void;
    onApprovePlan: () => void;
    onRejectPlan: (feedback: string) => void;
    onSummarizeChat: () => void;
    onMessagesElementChange: (element: HTMLElement | undefined) => void;
    renderChatMarkdown: (content: string | null) => string;
    formatToolStepContent: (content: string | null, metadata: any) => string;
    isDebugInspectable: (message: ChatMessage) => boolean;
    onOpenDebugTrace: (message: ChatMessage) => void;
    onDebugMessageKeydown: (event: KeyboardEvent, message: ChatMessage) => void;
  } = $props();

  let messagesElement: HTMLElement | undefined = $state(undefined);
  let planFeedbackDraft = $state('');
  let planFeedbackOpenFor: string | null = $state(null);

  $effect(() => {
    onMessagesElementChange(messagesElement);
  });

  function handleDeleteClick(event: MouseEvent, chatId: string) {
    event.stopPropagation();
    onDeleteChat(chatId);
  }

  function handleDebugChange(event: Event) {
    onDebugModeChange((event.currentTarget as HTMLInputElement).checked);
  }

  function handlePlanModeChange(event: Event) {
    onPlanModeRequestedChange((event.currentTarget as HTMLInputElement).checked);
  }

  function handleInput(event: Event) {
    onInputTextChange((event.currentTarget as HTMLInputElement).value);
  }

  function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    onSend();
  }

  function openPlanFeedback(planSessionId: string) {
    planFeedbackOpenFor = planSessionId;
    planFeedbackDraft = '';
  }

  function closePlanFeedback() {
    planFeedbackOpenFor = null;
    planFeedbackDraft = '';
  }

  function submitPlanFeedback() {
    const feedback = planFeedbackDraft.trim();
    if (!feedback) return;
    onRejectPlan(feedback);
    closePlanFeedback();
  }

  function evidenceStatusLabel(metadata: any) {
    if (!metadata?.evidenceRequired) return '근거 불필요';
    if (metadata?.evidenceLedgerHasSources && metadata?.asOfDate) return '출처 검증 완료';
    return '출처 부족';
  }

  function evidenceStatusClass(metadata: any) {
    if (!metadata?.evidenceRequired) return 'neutral';
    if (metadata?.evidenceLedgerHasSources && metadata?.asOfDate) return 'ok';
    return 'warn';
  }
</script>

<div class="panel chat-panel" style="width: {width}px">
  {#if showChatList}
    <div class="panel-header">
      <button class="link-btn" onclick={() => onShowChatListChange(false)}>← 돌아가기</button>
    </div>
    <div class="chat-list">
      {#each chatSessions as c}
        <div class="chat-item" class:active={currentChatId === c.id}>
          <button class="chat-select" onclick={() => onSelectChat(c.id)}>
            <span class="chat-title">💬 {c.title}</span>
            <span class="chat-meta">{c.message_count}개 메시지</span>
          </button>
          <button class="delete-btn" onclick={(event) => handleDeleteClick(event, c.id)}>×</button>
        </div>
      {/each}
      <button class="new-chat-btn" onclick={onNewChat}>+ 새 채팅</button>
    </div>
  {:else}
    <div class="panel-header">
      채팅
      {#if agentStatus !== 'idle'}
        <span class="status-badge">{agentStatus}</span>
      {/if}
      {#if planMode.active || planModeRequested}
        <span class="plan-badge">Plan</span>
      {/if}
      <span class="spacer"></span>
      <label class="debug-toggle" title="승인 전 계획만 작성하고 실제 실행은 승인 후 진행합니다.">
        <input type="checkbox" checked={planModeRequested} onchange={handlePlanModeChange} />
        <span>Plan</span>
      </label>
      <label class="debug-toggle" title="이후 메시지의 LLM 요청/응답 trace를 저장합니다.">
        <input type="checkbox" checked={debugMode} onchange={handleDebugChange} />
        <span>디버그</span>
      </label>
      <button class="link-btn" disabled={summarizingChat || streaming} onclick={onSummarizeChat}>
        {summarizingChat ? '요약 중...' : '요약'}
      </button>
      <button class="link-btn" onclick={() => onShowChatListChange(true)}>채팅 목록</button>
    </div>
    {#if chatActionMessage}
      <div class="chat-action-message">{chatActionMessage}</div>
    {/if}
    <div class="messages" bind:this={messagesElement}>
      {#each messages as msg}
        {#if msg.role === 'tool_step'}
          <div class="tool-step-inline">
            <span class="step-text">{formatToolStepContent(msg.content, msg.metadata)}</span>
          </div>
        {:else if msg.role === 'plan_approval'}
          <div class="message assistant plan-message">
            <div class="msg-role">📋</div>
            <div class="plan-approval-card inline">
              <div class="plan-title">Plan 승인 요청</div>
              <div class="plan-summary">{msg.metadata?.summary || msg.content}</div>
              <div class="plan-signal-grid">
                <div class="plan-signal">
                  <span class="signal-label">요구사항</span>
                  <span class="signal-value">{msg.metadata?.requirements?.length || 0}개 확정</span>
                </div>
                <div class="plan-signal">
                  <span class="signal-label">기준일</span>
                  <span class="signal-value">{msg.metadata?.asOfDate || '해당 없음'}</span>
                </div>
                <div class="plan-signal">
                  <span class="signal-label">출처</span>
                  <span class={`signal-pill ${evidenceStatusClass(msg.metadata)}`}>{evidenceStatusLabel(msg.metadata)}</span>
                </div>
                <div class="plan-signal">
                  <span class="signal-label">검증</span>
                  <span class={`signal-pill ${msg.metadata?.acceptanceChecksPresent ? 'ok' : 'warn'}`}>{msg.metadata?.acceptanceChecksPresent ? '기준 있음' : '기준 부족'}</span>
                </div>
              </div>
              {#if msg.metadata?.requirements?.length}
                <div class="plan-requirements">
                  {#each msg.metadata.requirements.slice(0, 4) as req}
                    <div class="plan-requirement">- {req.interpreted_requirement || req.source_text}</div>
                  {/each}
                </div>
              {/if}
              {#if msg.metadata?.planContent}
                <div class="plan-markdown">{@html renderChatMarkdown(msg.metadata.planContent)}</div>
              {/if}
              {#if planMode.approvalRequested && msg.metadata?.planSessionId === planMode.planSessionId}
                {#if planFeedbackOpenFor === msg.metadata.planSessionId}
                  <div class="plan-feedback-box">
                    <textarea
                      placeholder="수정할 점을 입력하세요..."
                      value={planFeedbackDraft}
                      disabled={streaming}
                      oninput={(event) => { planFeedbackDraft = (event.currentTarget as HTMLTextAreaElement).value; }}
                    ></textarea>
                    <div class="plan-actions">
                      <button type="button" class="reject-btn" disabled={streaming || !planFeedbackDraft.trim()} onclick={submitPlanFeedback}>피드백 제출</button>
                      <button type="button" class="plain-btn" disabled={streaming} onclick={closePlanFeedback}>취소</button>
                    </div>
                  </div>
                {:else}
                  <div class="plan-actions">
                    <button type="button" class="approve-btn" disabled={streaming} onclick={onApprovePlan}>승인 후 실행</button>
                    <button type="button" class="reject-btn" disabled={streaming} onclick={() => openPlanFeedback(msg.metadata.planSessionId)}>피드백 보내기</button>
                  </div>
                {/if}
              {:else}
                <div class="plan-status-note">
                  {msg.metadata?.status === 'plan_rejected' ? '피드백 반영 대기 중' : msg.metadata?.status === 'execution_completed' ? '실행 완료' : msg.metadata?.status === 'plan_approved' || msg.metadata?.status === 'execution_running' ? '승인됨' : '처리됨'}
                </div>
              {/if}
            </div>
          </div>
        {:else}
          <div class="message" class:user={msg.role === 'user'} class:assistant={msg.role !== 'user'}>
            <div class="msg-role">{msg.role === 'user' ? '🧑' : '🤖'}</div>
            {#if isDebugInspectable(msg)}
              <div
                class="msg-content msg-debug-button"
                role="button"
                tabindex="0"
                title="디버그 trace 보기"
                onclick={() => onOpenDebugTrace(msg)}
                onkeydown={(event) => onDebugMessageKeydown(event, msg)}
              >{@html renderChatMarkdown(msg.content)}</div>
            {:else}
              <div class="msg-content">{@html renderChatMarkdown(msg.content)}</div>
            {/if}
          </div>
        {/if}
      {/each}
    </div>
    <form class="input-area" onsubmit={handleSubmit}>
      <input
        type="text"
        placeholder="메시지를 입력하세요..."
        value={inputText}
        disabled={streaming}
        oninput={handleInput}
      />
      <button type="submit" disabled={streaming || !inputText.trim()}>전송</button>
    </form>
  {/if}
</div>

<style>
  .panel { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); background: var(--color-surface); }
  .panel-header { padding: 0.6rem 1rem; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }
  .chat-panel { flex: 0 0 auto; border-right: none; display: flex; flex-direction: column; }
  .spacer { flex: 1; }
  .link-btn { background: none; border: none; color: var(--color-pink); cursor: pointer; font-size: 0.8rem; padding: 0; }
  .link-btn:hover { text-decoration: underline; }
  .link-btn:disabled { cursor: default; opacity: 0.45; text-decoration: none; }
  .debug-toggle { display: inline-flex; align-items: center; gap: 0.3rem; color: var(--color-text-muted); font-size: 0.75rem; font-weight: 700; cursor: pointer; }
  .debug-toggle input { width: 14px; height: 14px; accent-color: var(--color-pink); }
  .chat-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
  .chat-item { display: flex; align-items: center; margin-bottom: 2px; border-radius: var(--radius-md); }
  .chat-item:hover { background: var(--color-sidebar-strong); }
  .chat-item.active { background: var(--color-pink-soft); }
  .chat-select { flex: 1; background: none; border: none; color: var(--color-text); padding: 0.5rem 0.75rem; cursor: pointer; text-align: left; font-family: inherit; font-size: 0.85rem; display: flex; flex-direction: column; gap: 0.15rem; }
  .chat-title { font-weight: 500; }
  .chat-meta { font-size: 0.75rem; color: var(--color-text-muted); }
  .delete-btn { background: none; border: none; color: var(--color-text-subtle); cursor: pointer; font-size: 1.1rem; padding: 0 8px; }
  .delete-btn:hover { color: var(--color-danger); }
  .new-chat-btn { width: 100%; padding: 0.5rem; border: 1px dashed var(--color-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-muted); cursor: pointer; margin-top: 0.5rem; font-size: 0.85rem; }
  .new-chat-btn:hover { border-color: var(--color-pink); color: var(--color-pink); background: var(--color-pink-soft); }
  .chat-action-message { flex-shrink: 0; padding: 0.35rem 0.75rem; border-bottom: 1px solid var(--color-border); background: var(--color-pink-soft); color: #be185d; font-size: 0.74rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .messages { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem; }
  .message { display: flex; gap: 0.5rem; }
  .message.user { flex-direction: row-reverse; }
  .msg-role { font-size: 1.2rem; flex-shrink: 0; }
  .msg-content { background: var(--color-sidebar); border: 1px solid var(--color-border-soft); padding: 0.6rem 0.8rem; border-radius: var(--radius-md); font-size: 0.85rem; line-height: 1.5; max-width: 85%; overflow-wrap: anywhere; }
  .message.user .msg-content { background: var(--color-info-soft); border-color: #bfdbfe; }
  .msg-content :global(p) { margin: 0 0 0.55rem; }
  .msg-content :global(p:last-child) { margin-bottom: 0; }
  .msg-content :global(ul), .msg-content :global(ol) { margin: 0.35rem 0 0.6rem; padding-left: 1.2rem; }
  .msg-content :global(li + li) { margin-top: 0.2rem; }
  .msg-content :global(pre) { margin: 0.45rem 0; padding: 0.55rem 0.65rem; border-radius: var(--radius-sm); background: var(--color-canvas); overflow-x: auto; }
  .msg-content :global(code) { font-family: var(--font-mono); font-size: 0.78rem; }
  .msg-content :global(:not(pre) > code) { padding: 0.08rem 0.25rem; border-radius: var(--radius-sm); background: var(--color-canvas); }
  .msg-content :global(blockquote) { margin: 0.45rem 0; padding-left: 0.75rem; border-left: 3px solid var(--color-border); color: var(--color-text-muted); }
  .msg-content :global(table) { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; margin: 0.45rem 0; }
  .msg-content :global(th), .msg-content :global(td) { border: 1px solid var(--color-border-soft); padding: 0.3rem 0.45rem; }
  .msg-content :global(a) { color: var(--color-accent-strong); }
  .msg-debug-button { color: inherit; font: inherit; text-align: left; cursor: pointer; }
  .msg-debug-button:hover { border-color: var(--color-pink); box-shadow: 0 0 0 2px var(--color-pink-soft); }
  .tool-step-inline { padding: 0.2rem 0.75rem; font-size: 0.8rem; color: var(--color-text-muted); border-left: 2px solid var(--color-border); margin-left: 1.5rem; }
  .step-text { font-family: var(--font-mono); }
  .input-area { display: flex; gap: 0.5rem; padding: 0.75rem; border-top: 1px solid var(--color-border); }
  .input-area input { flex: 1; padding: 0.6rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text); font-size: 0.9rem; }
  .input-area input:focus { outline: none; border-color: var(--color-pink); box-shadow: 0 0 0 3px var(--color-pink-soft); }
  .input-area button { padding: 0.6rem 1.2rem; border: none; border-radius: var(--radius-md); background: var(--color-pink); color: white; cursor: pointer; font-weight: 700; }
  .input-area button:disabled { opacity: 0.5; }
  .status-badge { background: var(--color-pink); color: white; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.7rem; }
  .plan-badge { background: #2563eb; color: white; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.7rem; }
  .plan-message { align-items: flex-start; }
  .plan-approval-card { padding: 0.75rem; border: 1px solid #bfdbfe; border-radius: var(--radius-md); background: #eff6ff; color: #1e3a8a; font-size: 0.82rem; max-width: 92%; }
  .plan-approval-card.inline { width: min(100%, 620px); box-sizing: border-box; }
  .plan-title { font-weight: 800; margin-bottom: 0.3rem; }
  .plan-summary { color: #1d4ed8; margin-bottom: 0.5rem; }
  .plan-signal-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.4rem; margin: 0.55rem 0; }
  .plan-signal { min-width: 0; padding: 0.45rem 0.5rem; border: 1px solid #dbeafe; border-radius: var(--radius-sm); background: white; display: flex; flex-direction: column; gap: 0.18rem; }
  .signal-label { color: #64748b; font-size: 0.68rem; font-weight: 800; }
  .signal-value { color: #0f172a; font-size: 0.76rem; font-weight: 700; overflow-wrap: anywhere; }
  .signal-pill { width: fit-content; max-width: 100%; border-radius: 999px; padding: 0.08rem 0.42rem; font-size: 0.7rem; font-weight: 800; overflow-wrap: anywhere; }
  .signal-pill.ok { background: #dcfce7; color: #166534; }
  .signal-pill.warn { background: #fef3c7; color: #92400e; }
  .signal-pill.neutral { background: #e2e8f0; color: #334155; }
  .plan-requirements { margin: 0.45rem 0; padding: 0.5rem 0.6rem; border: 1px solid #dbeafe; border-radius: var(--radius-sm); background: white; color: #334155; font-size: 0.76rem; line-height: 1.45; }
  .plan-requirement + .plan-requirement { margin-top: 0.22rem; }
  .plan-markdown { max-height: 300px; overflow: auto; margin: 0.5rem 0; padding: 0.65rem 0.75rem; border-radius: var(--radius-sm); background: white; color: var(--color-text); border: 1px solid #dbeafe; line-height: 1.55; }
  .plan-markdown :global(h1) { margin: 0 0 0.6rem; font-size: 1rem; line-height: 1.3; }
  .plan-markdown :global(h2) { margin: 0.85rem 0 0.4rem; font-size: 0.92rem; line-height: 1.35; }
  .plan-markdown :global(h3) { margin: 0.7rem 0 0.35rem; font-size: 0.86rem; line-height: 1.35; }
  .plan-markdown :global(p) { margin: 0 0 0.55rem; }
  .plan-markdown :global(ul), .plan-markdown :global(ol) { margin: 0.35rem 0 0.65rem; padding-left: 1.15rem; }
  .plan-markdown :global(li + li) { margin-top: 0.22rem; }
  .plan-markdown :global(code) { font-family: var(--font-mono); font-size: 0.78rem; border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.08rem 0.25rem; }
  .plan-status-note { margin-top: 0.45rem; color: #1d4ed8; font-size: 0.76rem; font-weight: 700; }
  .plan-feedback-box { margin-top: 0.55rem; display: flex; flex-direction: column; gap: 0.45rem; }
  .plan-feedback-box textarea { width: 100%; min-height: 82px; resize: vertical; box-sizing: border-box; border: 1px solid #bfdbfe; border-radius: var(--radius-sm); padding: 0.55rem 0.65rem; font: inherit; color: var(--color-text); background: white; }
  .plan-feedback-box textarea:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }
  .plan-actions { display: flex; gap: 0.5rem; }
  .approve-btn, .reject-btn, .plain-btn { border: none; border-radius: var(--radius-sm); padding: 0.45rem 0.7rem; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
  .approve-btn { background: #2563eb; color: white; }
  .reject-btn { background: white; color: #1d4ed8; border: 1px solid #bfdbfe; }
  .plain-btn { background: transparent; color: #64748b; border: 1px solid transparent; }
  .approve-btn:disabled, .reject-btn:disabled, .plain-btn:disabled { opacity: 0.5; cursor: default; }
</style>

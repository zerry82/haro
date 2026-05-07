<script lang="ts">
  import type { ChatMessage } from '../stores/chat';
  import type { ChatSessionItem } from '../stores/chatSessions';

  let {
    width,
    showChatList,
    agentStatus,
    debugMode,
    summarizingChat,
    streaming,
    chatActionMessage,
    chatSessions,
    currentChatId,
    messages,
    inputText,
    onShowChatListChange,
    onDebugModeChange,
    onInputTextChange,
    onSelectChat,
    onDeleteChat,
    onNewChat,
    onSend,
    onSummarizeChat,
    onMessagesElementChange,
    renderChatMarkdown,
    isDebugInspectable,
    onOpenDebugTrace,
    onDebugMessageKeydown,
  }: {
    width: number;
    showChatList: boolean;
    agentStatus: string;
    debugMode: boolean;
    summarizingChat: boolean;
    streaming: boolean;
    chatActionMessage: string;
    chatSessions: ChatSessionItem[];
    currentChatId: string | null;
    messages: ChatMessage[];
    inputText: string;
    onShowChatListChange: (value: boolean) => void;
    onDebugModeChange: (value: boolean) => void;
    onInputTextChange: (value: string) => void;
    onSelectChat: (chatId: string) => void;
    onDeleteChat: (chatId: string) => void;
    onNewChat: () => void;
    onSend: () => void;
    onSummarizeChat: () => void;
    onMessagesElementChange: (element: HTMLElement | undefined) => void;
    renderChatMarkdown: (content: string | null) => string;
    isDebugInspectable: (message: ChatMessage) => boolean;
    onOpenDebugTrace: (message: ChatMessage) => void;
    onDebugMessageKeydown: (event: KeyboardEvent, message: ChatMessage) => void;
  } = $props();

  let messagesElement: HTMLElement | undefined = $state(undefined);

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

  function handleInput(event: Event) {
    onInputTextChange((event.currentTarget as HTMLInputElement).value);
  }

  function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    onSend();
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
      <span class="spacer"></span>
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
            <span class="step-text">{msg.content}</span>
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
</style>

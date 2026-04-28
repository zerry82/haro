<script lang="ts">
  import { onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated, logout, user } from '../stores/auth';
  import { sessions, loadSessions, createSession, deleteSession, currentSessionId } from '../stores/sessions';
  import { messages, loadMessages, sendMessage, streaming, todoSteps, agentStatus } from '../stores/chat';
  import { fileTree, loadFiles, loadFileContent, selectedFilePath, fileContent, fileLanguage, expandFolder, reloadAllExpanded, type TreeNode } from '../stores/files';

  let { params = {} }: { params?: { sessionId?: string } } = $props();

  let inputText = $state('');
  let chatContainer: HTMLElement | undefined = $state(undefined);

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  // 메시지가 변경될 때마다 자동 스크롤
  $effect(() => {
    $messages;
    $todoSteps;
    requestAnimationFrame(scrollToBottom);
  });

  onMount(async () => {
    if (!$isAuthenticated) { push('/login'); return; }
    await loadSessions();
    if (params.sessionId) {
      currentSessionId.set(params.sessionId);
      await loadMessages(params.sessionId);
      await loadFiles(params.sessionId);
    }
  });

  // Listen for file changes from SSE
  function handleFileChanged() {
    const sid = $currentSessionId;
    if (sid) reloadAllExpanded(sid);
    // Reload current file if it was modified
    const sp = $selectedFilePath;
    if (sid && sp) loadFileContent(sid, sp);
  }

  onMount(() => {
    window.addEventListener('file-changed', handleFileChanged);
    return () => window.removeEventListener('file-changed', handleFileChanged);
  });

  async function handleNewChat() {
    const id = await createSession();
    currentSessionId.set(id);
    messages.set([]);
    fileTree.set([]);
    selectedFilePath.set(null);
    fileContent.set(null);
    push(`/chat/${id}`);
  }

  async function handleSelectSession(id: string) {
    currentSessionId.set(id);
    await loadMessages(id);
    await loadFiles(id);
    push(`/chat/${id}`);
  }

  async function handleSend() {
    const sid = $currentSessionId;
    if (!sid || !inputText.trim() || $streaming) return;
    const text = inputText;
    inputText = '';
    await sendMessage(sid, text);
    if (sid) await reloadAllExpanded(sid);
  }

  async function handleNodeClick(node: TreeNode) {
    const sid = $currentSessionId;
    if (!sid) return;
    if (node.type === 'directory') {
      await expandFolder(sid, node);
    } else {
      await loadFileContent(sid, node.path);
    }
  }

  async function handleDeleteSession(id: string) {
    if (!confirm('세션을 삭제하시겠습니까?')) return;
    await deleteSession(id);
    if ($currentSessionId === id) {
      currentSessionId.set(null);
      messages.set([]);
      fileTree.set([]);
      push('/chat');
    }
  }

  function handleLogout() {
    logout();
    push('/login');
  }
</script>

<div class="layout">
  <!-- Session Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>Mini Open Claw</h2>
      <button class="new-chat" onclick={handleNewChat}>+ 새 채팅</button>
    </div>
    <div class="session-list">
      {#each $sessions as s}
        <button
          class="session-item"
          class:active={$currentSessionId === s.id}
          onclick={() => handleSelectSession(s.id)}
        >
          <span class="session-title">{s.title}</span>
          <span class="delete-btn" role="button" tabindex="0" onclick={(e: MouseEvent) => { e.stopPropagation(); handleDeleteSession(s.id); }} onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter') { e.stopPropagation(); handleDeleteSession(s.id); }}}>×</span>
        </button>
      {/each}
    </div>
    <div class="sidebar-footer">
      <span>{$user?.name}</span>
      <button onclick={() => push('/logs')}>📊 로그</button>
      <button onclick={handleLogout}>로그아웃</button>
    </div>
  </aside>

  {#if $currentSessionId}
    <!-- File Explorer -->
    <div class="panel file-panel">
      <div class="panel-header">파일</div>
      <div class="file-list">
        {#snippet renderTree(nodes: TreeNode[], depth: number)}
          {#each nodes as item}
            <button
              class="file-item"
              class:active={$selectedFilePath === item.path}
              style="padding-left: {0.5 + depth * 0.75}rem"
              onclick={() => handleNodeClick(item)}
            >
              <span>
                {#if item.type === 'directory'}
                  {item.expanded ? '📂' : '📁'}
                {:else}
                  📄
                {/if}
                {item.name}
              </span>
            </button>
            {#if item.type === 'directory' && item.expanded && item.children}
              {@render renderTree(item.children, depth + 1)}
            {/if}
          {/each}
        {/snippet}
        {@render renderTree($fileTree, 0)}
        {#if $fileTree.length === 0}
          <p class="empty">파일 없음</p>
        {/if}
      </div>
    </div>

    <!-- File Viewer -->
    <div class="panel viewer-panel">
      <div class="panel-header">{$selectedFilePath || '파일을 선택하세요'}</div>
      <div class="viewer-content">
        {#if $fileContent !== null}
          <pre><code>{$fileContent}</code></pre>
        {:else}
          <p class="empty">좌측에서 파일을 선택하세요</p>
        {/if}
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="panel chat-panel">
      <div class="panel-header">
        채팅
        {#if $agentStatus !== 'idle'}
          <span class="status-badge">{$agentStatus}</span>
        {/if}
      </div>
      <div class="messages" bind:this={chatContainer}>
        {#each $messages as msg}
          <div class="message" class:user={msg.role === 'user'} class:assistant={msg.role !== 'user'}>
            <div class="msg-role">{msg.role === 'user' ? '🧑' : '🤖'}</div>
            <div class="msg-content">{msg.content}</div>
          </div>
        {/each}
        {#if $todoSteps.length > 0}
          <div class="todo-card">
            <div class="todo-title">📋 작업 진행</div>
            {#each $todoSteps as step}
              <div class="todo-step">
                {step.status === 'completed' ? '✅' : '🔄'} {step.description}
              </div>
            {/each}
          </div>
        {/if}
      </div>
      <form class="input-area" onsubmit={(e) => { e.preventDefault(); handleSend(); }}>
        <input
          type="text"
          placeholder="메시지를 입력하세요..."
          bind:value={inputText}
          disabled={$streaming}
        />
        <button type="submit" disabled={$streaming || !inputText.trim()}>전송</button>
      </form>
    </div>
  {:else}
    <div class="empty-state">
      <h2>새 채팅을 시작하세요</h2>
      <p>좌측에서 "새 채팅"을 클릭하거나 기존 세션을 선택하세요.</p>
    </div>
  {/if}
</div>

<style>
  .layout { display: flex; height: 100vh; }
  .sidebar { width: 240px; background: #0f3460; display: flex; flex-direction: column; border-right: 1px solid #333; }
  .sidebar-header { padding: 1rem; border-bottom: 1px solid #333; }
  .sidebar-header h2 { margin: 0 0 0.75rem; color: #e94560; font-size: 1.2rem; }
  .new-chat { width: 100%; padding: 0.5rem; border: 1px dashed #555; border-radius: 6px; background: transparent; color: #e0e0e0; cursor: pointer; }
  .new-chat:hover { border-color: #e94560; color: #e94560; }
  .session-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
  .session-item { padding: 0.5rem 0.75rem; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px; background: transparent; border: none; color: #e0e0e0; width: 100%; text-align: left; font-size: inherit; font-family: inherit; }
  .session-item:hover { background: #16213e; }
  .session-item.active { background: #1a1a2e; }
  .session-title { font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  .delete-btn { background: none; border: none; color: #666; cursor: pointer; font-size: 1.1rem; padding: 0 4px; }
  .delete-btn:hover { color: #e94560; }
  .sidebar-footer { padding: 0.75rem 1rem; border-top: 1px solid #333; display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; }
  .sidebar-footer button { background: none; border: none; color: #888; cursor: pointer; font-size: 0.8rem; }

  .panel { display: flex; flex-direction: column; border-right: 1px solid #333; }
  .panel-header { padding: 0.6rem 1rem; background: #16213e; border-bottom: 1px solid #333; font-size: 0.85rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
  .file-panel { width: 200px; }
  .viewer-panel { flex: 1; }
  .chat-panel { width: 400px; border-right: none; }

  .file-list { flex: 1; overflow-y: auto; padding: 0.25rem; }
  .file-item { padding: 0.35rem 0.5rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; background: transparent; border: none; color: #e0e0e0; width: 100%; text-align: left; font-family: inherit; display: block; }
  .file-item:hover { background: #16213e; }
  .file-item.active { background: #1a1a2e; color: #e94560; }

  .viewer-content { flex: 1; overflow: auto; padding: 1rem; }
  .viewer-content pre { margin: 0; font-size: 0.8rem; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }

  .messages { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem; }
  .message { display: flex; gap: 0.5rem; }
  .message.user { flex-direction: row-reverse; }
  .msg-role { font-size: 1.2rem; flex-shrink: 0; }
  .msg-content { background: #16213e; padding: 0.6rem 0.8rem; border-radius: 8px; font-size: 0.85rem; line-height: 1.5; max-width: 85%; white-space: pre-wrap; }
  .message.user .msg-content { background: #0f3460; }

  .todo-card { background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 0.75rem; }
  .todo-title { font-weight: 600; margin-bottom: 0.5rem; font-size: 0.85rem; }
  .todo-step { font-size: 0.8rem; padding: 0.15rem 0; }

  .input-area { display: flex; gap: 0.5rem; padding: 0.75rem; border-top: 1px solid #333; }
  .input-area input { flex: 1; padding: 0.6rem; border: 1px solid #333; border-radius: 8px; background: #0f3460; color: #e0e0e0; font-size: 0.9rem; }
  .input-area input:focus { outline: none; border-color: #e94560; }
  .input-area button { padding: 0.6rem 1.2rem; border: none; border-radius: 8px; background: #e94560; color: white; cursor: pointer; }
  .input-area button:disabled { opacity: 0.5; }

  .status-badge { background: #e94560; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.7rem; }

  .empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #666; }
  .empty { color: #555; font-size: 0.8rem; text-align: center; padding: 1rem; }
</style>

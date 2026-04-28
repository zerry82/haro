<script lang="ts">
  import { onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated, user } from '../stores/auth';
  import { currentProjectId } from '../stores/projects';
  import { chatSessions, loadChatSessions, createChatSession, deleteChatSession, currentChatId, type ChatSessionItem } from '../stores/chatSessions';
  import { messages, loadMessages, sendMessage, streaming, todoSteps, agentStatus } from '../stores/chat';
  import { fileTree, loadFiles, loadFileContent, saveFileContent, selectedFilePath, fileContent, fileLanguage, fileLoading, expandFolder, reloadAllExpanded, type TreeNode } from '../stores/files';
  import { api } from '../lib/api';
  import CodeEditor from '../components/CodeEditor.svelte';
  import { marked } from 'marked';
  import hljs from 'highlight.js';
  import Papa from 'papaparse';
  import 'highlight.js/styles/github-dark.css';

  let { params = {} }: { params?: { projectId?: string; chatId?: string } } = $props();

  let projectTitle = $state('');
  let inputText = $state('');
  let chatContainer: HTMLElement | undefined = $state(undefined);
  let showChatList = $state(false);
  let activeSideTab = $state<SidePanelTab>('files');
  let activeViewerTab = $state<ViewerTab>('source');
  let lastViewerPath: string | null = null;
  let lastEditorPath: string | null = null;
  let editorContent = $state('');
  let editorBaseContent = $state('');
  let savingFile = $state(false);
  let saveStatus = $state('');
  let externalFileChanged = $state(false);
  let htmlPreviewRevision = $state(0);
  let markdownPreviewHtml = $state('');
  let highlightedCodeHtml = $state('');
  let htmlPreviewContent = $state('');
  let htmlPreviewKey = $state('');
  let htmlPreviewReady = $state(false);
  let csvRows = $state<string[][]>([]);
  let csvPreviewRows = $state<string[][]>([]);
  let csvParseError = $state('');
  let skills = $state<SkillResponse[]>([]);
  let skillsLoading = $state(false);
  let skillsError = $state('');
  let renderComputeSeq = 0;

  type SidePanelTab = 'files' | 'skills' | 'tools' | 'dataSources';
  type SidePanelTabItem = { id: SidePanelTab; label: string };
  type ViewerTab = 'preview' | 'source' | 'code' | 'editor';
  type ViewerTabItem = { id: ViewerTab; label: string };
  type SkillResponse = {
    name: string;
    version: string;
    type: string;
    status: string;
    description: string | null;
    tools: string[];
  };
  type SkillListResponse = { skills: SkillResponse[] };
  type ToolCatalogItem = { name: string; signature: string; description: string };

  const SIDE_PANEL_TABS: SidePanelTabItem[] = [
    { id: 'files', label: '폴더' },
    { id: 'skills', label: '스킬' },
    { id: 'tools', label: '툴' },
    { id: 'dataSources', label: '데이터소스' },
  ];

  const TOOL_CATALOG: ToolCatalogItem[] = [
    { name: 'file_create', signature: 'file_create(path, content)', description: '새 파일 생성' },
    { name: 'file_read', signature: 'file_read(path)', description: '파일 내용 읽기' },
    { name: 'file_write', signature: 'file_write(path, content)', description: '기존 파일 덮어쓰기' },
    { name: 'file_delete', signature: 'file_delete(path)', description: '파일 삭제' },
    { name: 'dir_list', signature: 'dir_list(path)', description: '디렉토리 내용 조회' },
    { name: 'dir_create', signature: 'dir_create(path)', description: '디렉토리 생성' },
    { name: 'code_run', signature: 'code_run(filename, code)', description: '샌드박스 안에서 코드 실행' },
    { name: 'web_preview', signature: 'web_preview()', description: '웹 프리뷰 시작 및 URL 반환' },
  ];

  const EDITABLE_EXTENSIONS = [
    '.html', '.md', '.csv', '.ts', '.js', '.json',
    '.txt', '.css', '.py', '.yaml', '.yml', '.svg',
  ];

  function getExtension(path: string | null) {
    if (!path) return '';
    const name = path.split('/').pop() || '';
    const dotIndex = name.lastIndexOf('.');
    return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : '';
  }

  function isMarkdownFile(path: string | null, language: string) {
    return getExtension(path) === '.md' || language === 'markdown';
  }

  function isHtmlFile(path: string | null, language: string) {
    return getExtension(path) === '.html' || language === 'html';
  }

  function isCsvFile(path: string | null, language: string) {
    return getExtension(path) === '.csv' || language === 'csv';
  }

  function isCodePreviewFile(path: string | null, language: string) {
    return ['.ts', '.js', '.json'].includes(getExtension(path)) ||
      ['typescript', 'javascript', 'json'].includes(language);
  }

  function isEditableTextFile(path: string | null, language: string) {
    const extension = getExtension(path);
    return EDITABLE_EXTENSIONS.includes(extension) ||
      ['html', 'markdown', 'csv', 'typescript', 'javascript', 'json', 'plaintext', 'css', 'python', 'yaml', 'xml'].includes(language);
  }

  function hasUnsavedChanges() {
    return $fileContent !== null && editorContent !== editorBaseContent;
  }

  function getViewerContent(content: string | null, path: string | null, language: string, draft: string) {
    return isEditableTextFile(path, language) ? draft : content || '';
  }

  function getLightweightHash(value: string) {
    let hash = 0;
    for (let i = 0; i < value.length; i += 1) {
      hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0;
    }
    return hash.toString(36);
  }

  function getHtmlPreviewKey(path: string | null, content: string, revision: number) {
    return `${path || ''}:${content.length}:${getLightweightHash(content)}:${revision}`;
  }

  function getViewerTabs(path: string | null, language: string): ViewerTabItem[] {
    if (isCsvFile(path, language)) {
      return [
        { id: 'preview', label: '프리뷰' },
        { id: 'editor', label: '에디터' },
        { id: 'source', label: '원본' },
      ];
    }
    if (isMarkdownFile(path, language) || isHtmlFile(path, language)) {
      return [
        { id: 'preview', label: '프리뷰' },
        { id: 'editor', label: '에디터' },
        { id: 'source', label: '원본' },
      ];
    }
    if (isCodePreviewFile(path, language)) {
      return [
        { id: 'code', label: '코드' },
        { id: 'editor', label: '에디터' },
      ];
    }
    if (isEditableTextFile(path, language)) {
      return [
        { id: 'editor', label: '에디터' },
        { id: 'source', label: '원본' },
      ];
    }
    return [{ id: 'source', label: '원본' }];
  }

  function getDefaultViewerTab(path: string | null, language: string): ViewerTab {
    if (isCsvFile(path, language)) return 'editor';
    if (isMarkdownFile(path, language) || isHtmlFile(path, language)) return 'preview';
    if (isCodePreviewFile(path, language)) return 'code';
    if (isEditableTextFile(path, language)) return 'editor';
    return 'source';
  }

  function escapeHtml(value: string) {
    return value
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function renderMarkdown(content: string | null) {
    return marked.parse(content || '', { async: false }) as string;
  }

  function highlightCode(content: string | null, language: string) {
    const code = content || '';
    const languageMap: Record<string, string> = {
      html: 'xml',
      javascript: 'javascript',
      typescript: 'typescript',
      json: 'json',
    };
    const highlightLanguage = languageMap[language] || language;
    try {
      if (highlightLanguage && hljs.getLanguage(highlightLanguage)) {
        return hljs.highlight(code, { language: highlightLanguage, ignoreIllegals: true }).value;
      }
      return hljs.highlightAuto(code).value;
    } catch {
      return escapeHtml(code);
    }
  }

  function refreshHtmlPreview() {
    htmlPreviewRevision += 1;
  }

  function parseCsvContent(content: string) {
    const result = Papa.parse(content, { skipEmptyLines: false });
    const rows = (result.data as unknown[]).map((row) => {
      if (Array.isArray(row)) {
        return row.map((cell) => cell == null ? '' : String(cell));
      }
      return [row == null ? '' : String(row)];
    });
    const error = result.errors.map((item) => item.message).join('\n');
    return { rows, error };
  }

  function handleCsvCellInput(rowIndex: number, cellIndex: number, event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    const nextRows = csvRows.map((row) => [...row]);
    if (!nextRows[rowIndex] || cellIndex >= nextRows[rowIndex].length) return;
    nextRows[rowIndex][cellIndex] = target.value;
    csvRows = nextRows;
    csvPreviewRows = nextRows;
    editorContent = Papa.unparse(nextRows);
    saveStatus = '';
  }

  function handleViewerTabClick(tab: ViewerTab) {
    activeViewerTab = tab;
    if (tab === 'preview' && isHtmlFile($selectedFilePath, $fileLanguage)) {
      refreshHtmlPreview();
    }
  }

  function runAfterNextFrame(callback: () => void) {
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(callback);
    } else {
      setTimeout(callback, 0);
    }
  }

  $effect(() => {
    const seq = ++renderComputeSeq;
    const path = $selectedFilePath;
    const language = $fileLanguage;
    const content = $fileContent;
    const draft = editorContent;
    const tab = activeViewerTab;
    const revision = htmlPreviewRevision;

    markdownPreviewHtml = '';
    highlightedCodeHtml = '';
    htmlPreviewReady = false;

    if (content === null) {
      htmlPreviewContent = '';
      htmlPreviewKey = '';
      return;
    }

    const viewerContent = getViewerContent(content, path, language, draft);
    runAfterNextFrame(() => {
      if (seq !== renderComputeSeq) return;

      if (tab === 'preview' && isMarkdownFile(path, language)) {
        markdownPreviewHtml = renderMarkdown(viewerContent);
        return;
      }

      if (tab === 'preview' && isHtmlFile(path, language)) {
        htmlPreviewContent = viewerContent;
        htmlPreviewKey = getHtmlPreviewKey(path, viewerContent, revision);
        htmlPreviewReady = true;
        return;
      }

      if (tab === 'code') {
        highlightedCodeHtml = highlightCode(viewerContent, language);
      }
    });
  });

  $effect(() => {
    const path = $selectedFilePath;
    const language = $fileLanguage;
    const content = $fileContent;
    const draft = editorContent;

    if (content === null || !isCsvFile(path, language)) {
      csvRows = [];
      csvPreviewRows = [];
      csvParseError = '';
      return;
    }

    const parsed = parseCsvContent(getViewerContent(content, path, language, draft));
    csvRows = parsed.rows;
    csvPreviewRows = parsed.rows;
    csvParseError = parsed.error;
  });

  $effect(() => {
    const path = $selectedFilePath;
    const language = $fileLanguage;
    const tabs = getViewerTabs(path, language);
    if (path !== lastViewerPath) {
      lastViewerPath = path;
      activeViewerTab = getDefaultViewerTab(path, language);
    } else if (!tabs.some((tab) => tab.id === activeViewerTab)) {
      activeViewerTab = getDefaultViewerTab(path, language);
    }
  });

  $effect(() => {
    const path = $selectedFilePath;
    const content = $fileContent || '';
    if (path !== lastEditorPath) {
      lastEditorPath = path;
      editorContent = content;
      editorBaseContent = content;
      saveStatus = '';
      externalFileChanged = false;
    } else if (!hasUnsavedChanges()) {
      editorContent = content;
      editorBaseContent = content;
    }
  });

  function scrollToBottom() {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  async function loadSkillsPanel() {
    if (skillsLoading) return;
    skillsLoading = true;
    skillsError = '';
    try {
      const res = await api<SkillListResponse>('/skills');
      skills = res.skills || [];
    } catch (e: any) {
      skillsError = e.message || '스킬을 불러오지 못했습니다.';
    } finally {
      skillsLoading = false;
    }
  }

  $effect(() => {
    $messages;
    $todoSteps;
    requestAnimationFrame(scrollToBottom);
  });

  onMount(async () => {
    if (!$isAuthenticated) { push('/login'); return; }
    const pid = params.projectId;
    if (!pid) { push('/projects'); return; }

    currentProjectId.set(pid);

    // Load project info
    try {
      const res: any = await api(`/projects`);
      const proj = res.projects.find((p: any) => p.id === pid);
      if (!proj) { push('/projects'); return; }
      projectTitle = proj.title;
    } catch { push('/projects'); return; }

    void loadSkillsPanel();

    // Load chat sessions
    await loadChatSessions(pid);

    // Determine active chat
    let chatId = params.chatId;
    const chats = $chatSessions;
    if (!chatId && chats.length > 0) {
      chatId = chats[0].id;
    }
    if (!chatId) { push('/projects'); return; }

    // Verify chat exists
    const chatExists = chats.some(c => c.id === chatId);
    if (!chatExists && chats.length > 0) {
      chatId = chats[0].id;
    }

    currentChatId.set(chatId!);
    await loadMessages(pid, chatId!);
    await loadFiles(pid);

    // Update URL if needed
    if (!params.chatId || params.chatId !== chatId) {
      push(`/projects/${pid}/chats/${chatId}`);
    }
  });

  // Listen for file changes from SSE
  function handleFileChanged() {
    const pid = $currentProjectId;
    if (pid) reloadAllExpanded(pid);
    const sp = $selectedFilePath;
    if (pid && sp) {
      if (hasUnsavedChanges()) {
        externalFileChanged = true;
        return;
      }
      loadFileContent(pid, sp);
    }
  }

  onMount(() => {
    window.addEventListener('file-changed', handleFileChanged);
    return () => window.removeEventListener('file-changed', handleFileChanged);
  });

  async function handleSelectChat(chatId: string) {
    const pid = $currentProjectId;
    if (!pid) return;
    currentChatId.set(chatId);
    await loadMessages(pid, chatId);
    showChatList = false;
    push(`/projects/${pid}/chats/${chatId}`);
  }

  async function handleNewChat() {
    const pid = $currentProjectId;
    if (!pid) return;
    const id = await createChatSession(pid);
    currentChatId.set(id);
    messages.set([]);
    showChatList = false;
    push(`/projects/${pid}/chats/${id}`);
  }

  async function handleDeleteChat(chatId: string) {
    const pid = $currentProjectId;
    if (!pid) return;
    if (!confirm('채팅을 삭제하시겠습니까?')) return;
    try {
      await deleteChatSession(pid, chatId);
      if ($currentChatId === chatId) {
        const chats = $chatSessions;
        if (chats.length > 0) {
          await handleSelectChat(chats[0].id);
        }
      }
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handleSend() {
    const pid = $currentProjectId;
    const cid = $currentChatId;
    if (!pid || !cid || !inputText.trim() || $streaming) return;
    const text = inputText;
    inputText = '';
    await sendMessage(pid, cid, text);
    if (pid) await reloadAllExpanded(pid);
  }

  async function handleSaveFile() {
    const pid = $currentProjectId;
    const path = $selectedFilePath;
    if (!pid || !path || savingFile || !isEditableTextFile(path, $fileLanguage)) return;
    savingFile = true;
    saveStatus = '';
    try {
      const saved = await saveFileContent(pid, path, editorContent);
      editorContent = saved.content;
      editorBaseContent = saved.content;
      externalFileChanged = false;
      saveStatus = '저장됨';
      await reloadAllExpanded(pid);
    } catch (e: any) {
      saveStatus = e.message || '저장 실패';
    } finally {
      savingFile = false;
    }
  }

  function handleRevertFile() {
    editorContent = editorBaseContent;
    saveStatus = '되돌림';
  }

  async function handleReloadCurrentFile() {
    const pid = $currentProjectId;
    const path = $selectedFilePath;
    if (!pid || !path) return;
    if (hasUnsavedChanges() && !confirm('저장하지 않은 변경사항을 버리고 다시 불러오시겠습니까?')) return;
    externalFileChanged = false;
    await loadFileContent(pid, path);
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    const path = $selectedFilePath;
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return;
    if (!path || !isEditableTextFile(path, $fileLanguage)) return;
    event.preventDefault();
    if (hasUnsavedChanges() && !savingFile) handleSaveFile();
  }

  async function handleNodeClick(node: TreeNode) {
    const pid = $currentProjectId;
    if (!pid) return;
    if (node.type === 'directory') {
      await expandFolder(pid, node);
    } else {
      const reselectingCurrentHtml = node.path === $selectedFilePath && isHtmlFile(node.path, $fileLanguage);
      if (node.path !== $selectedFilePath && hasUnsavedChanges() &&
        !confirm('저장하지 않은 변경사항을 버리고 다른 파일을 여시겠습니까?')) {
        return;
      }
      await loadFileContent(pid, node.path);
      if (reselectingCurrentHtml) refreshHtmlPreview();
    }
  }
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<div class="layout">
  <!-- Top bar -->
  <header class="top-bar">
    <button class="back-btn" onclick={() => push('/projects')}>← 프로젝트</button>
    <span class="project-name">{projectTitle}</span>
    <span class="spacer"></span>
    <span class="user-name">{$user?.name}</span>
  </header>

  <div class="workspace">
    <!-- File Explorer -->
    <div class="panel file-panel">
      <div class="side-tabs" role="tablist" aria-label="왼쪽 메뉴">
        {#each SIDE_PANEL_TABS as tab}
          <button
            type="button"
            class="side-tab"
            class:active={activeSideTab === tab.id}
            role="tab"
            aria-selected={activeSideTab === tab.id}
            onclick={() => { activeSideTab = tab.id; }}
          >
            {tab.label}
          </button>
        {/each}
      </div>

      {#if activeSideTab === 'files'}
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
      {:else if activeSideTab === 'skills'}
        <div class="side-list">
          {#if skillsLoading}
            <p class="empty">스킬 불러오는 중...</p>
          {:else if skillsError}
            <div class="side-error">{skillsError}</div>
          {:else if skills.length === 0}
            <p class="empty">설치된 스킬 없음</p>
          {:else}
            {#each skills as skill}
              <article class="side-card">
                <div class="side-card-title" title={skill.name}>{skill.name}</div>
                <div class="side-card-meta">
                  <span>{skill.status}</span>
                  <span>{skill.type}</span>
                  <span>v{skill.version}</span>
                </div>
                {#if skill.description}
                  <p class="side-card-description">{skill.description}</p>
                {/if}
                {#if skill.tools.length > 0}
                  <div class="side-chip-list">
                    {#each skill.tools as tool}
                      <span class="side-chip" title={tool}>{tool}</span>
                    {/each}
                  </div>
                {/if}
              </article>
            {/each}
          {/if}
        </div>
      {:else if activeSideTab === 'tools'}
        <div class="side-list">
          {#each TOOL_CATALOG as tool}
            <article class="side-card">
              <div class="side-card-title" title={tool.name}>{tool.name}</div>
              <code class="side-signature" title={tool.signature}>{tool.signature}</code>
              <p class="side-card-description">{tool.description}</p>
            </article>
          {/each}
        </div>
      {:else}
        <div class="side-list">
          <p class="empty">연결된 데이터소스 없음</p>
        </div>
      {/if}
    </div>

    <!-- File Viewer -->
    <div class="panel viewer-panel">
      <div class="panel-header viewer-header">
        <span class="viewer-title">{$selectedFilePath || '파일을 선택하세요'}</span>
        {#if $selectedFilePath !== null}
          <div class="viewer-tabs" role="tablist" aria-label="파일 보기 방식">
            {#each getViewerTabs($selectedFilePath, $fileLanguage) as tab}
              <button
                type="button"
                class="viewer-tab"
                class:active={activeViewerTab === tab.id}
                role="tab"
                aria-selected={activeViewerTab === tab.id}
                onclick={() => handleViewerTabClick(tab.id)}
              >
                {tab.label}{tab.id === 'editor' && hasUnsavedChanges() ? ' *' : ''}
              </button>
            {/each}
          </div>
        {/if}
        <span class="viewer-status-spacer"></span>
        {#if hasUnsavedChanges()}
          <span class="dirty-badge">수정됨</span>
        {/if}
        {#if externalFileChanged}
          <span class="external-badge">외부 변경 있음</span>
        {/if}
      </div>
      <div class="viewer-content">
        {#if $fileContent !== null}
          {#if activeViewerTab === 'preview' && isCsvFile($selectedFilePath, $fileLanguage)}
            <div class="csv-table-wrap">
              {#if csvParseError}
                <div class="csv-error">
                  <strong>CSV 파싱 오류</strong>
                  <pre>{csvParseError}</pre>
                  <span>원본 탭에서 텍스트를 확인해 주세요.</span>
                </div>
              {:else if csvPreviewRows.length === 0}
                <p class="empty">표시할 CSV 데이터가 없습니다.</p>
              {:else}
                <table class="csv-table">
                  <tbody>
                    {#each csvPreviewRows as row, rowIndex}
                      <tr class:header-row={rowIndex === 0}>
                        {#each row as cell}
                          {#if rowIndex === 0}
                            <th>{cell}</th>
                          {:else}
                            <td>{cell}</td>
                          {/if}
                        {/each}
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>
          {:else if activeViewerTab === 'preview' && isMarkdownFile($selectedFilePath, $fileLanguage)}
            <div class="markdown-preview">{@html markdownPreviewHtml}</div>
          {:else if activeViewerTab === 'preview' && isHtmlFile($selectedFilePath, $fileLanguage)}
            {#if htmlPreviewReady}
              {#key htmlPreviewKey}
                <div class="html-preview-frame">
                  <button type="button" class="html-preview-refresh" onclick={refreshHtmlPreview}>새로고침</button>
                  <iframe class="html-preview" sandbox="allow-scripts" srcdoc={htmlPreviewContent} title="HTML preview"></iframe>
                </div>
              {/key}
            {:else}
              <p class="empty loading">프리뷰 준비 중...</p>
            {/if}
          {:else if activeViewerTab === 'code'}
            <pre class="code-preview"><code class="hljs">{@html highlightedCodeHtml}</code></pre>
          {:else if activeViewerTab === 'editor' && isCsvFile($selectedFilePath, $fileLanguage)}
            <div class="editor-pane">
              <div class="editor-toolbar">
                <span class="editor-status" class:dirty={hasUnsavedChanges()} class:warning={externalFileChanged}>
                  {#if externalFileChanged}
                    외부 변경 있음
                  {:else if hasUnsavedChanges()}
                    저장되지 않음
                  {:else if saveStatus}
                    {saveStatus}
                  {:else}
                    저장됨
                  {/if}
                </span>
                <span class="spacer"></span>
                {#if externalFileChanged}
                  <button type="button" class="editor-action" onclick={handleReloadCurrentFile}>다시 불러오기</button>
                {/if}
                <button type="button" class="editor-action" onclick={handleRevertFile} disabled={!hasUnsavedChanges() || savingFile}>되돌리기</button>
                <button type="button" class="editor-save" onclick={handleSaveFile} disabled={!hasUnsavedChanges() || savingFile}>
                  {savingFile ? '저장 중...' : '저장'}
                </button>
              </div>
              <div class="csv-editor-body">
                {#if csvParseError}
                  <div class="csv-error">
                    <strong>CSV 파싱 오류</strong>
                    <pre>{csvParseError}</pre>
                    <span>셀 편집 대신 원본 탭에서 텍스트를 확인해 주세요.</span>
                  </div>
                {:else if csvRows.length === 0}
                  <p class="empty">편집할 CSV 데이터가 없습니다.</p>
                {:else}
                  <table class="csv-table csv-edit-table">
                    <tbody>
                      {#each csvRows as row, rowIndex}
                        <tr class:header-row={rowIndex === 0}>
                          {#each row as cell, cellIndex}
                            <td>
                              <input
                                value={cell}
                                aria-label={`CSV ${rowIndex + 1}행 ${cellIndex + 1}열`}
                                oninput={(event) => handleCsvCellInput(rowIndex, cellIndex, event)}
                              />
                            </td>
                          {/each}
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                {/if}
              </div>
            </div>
          {:else if activeViewerTab === 'editor' && isEditableTextFile($selectedFilePath, $fileLanguage)}
            <div class="editor-pane">
              <div class="editor-toolbar">
                <span class="editor-status" class:dirty={hasUnsavedChanges()} class:warning={externalFileChanged}>
                  {#if externalFileChanged}
                    외부 변경 있음
                  {:else if hasUnsavedChanges()}
                    저장되지 않음
                  {:else if saveStatus}
                    {saveStatus}
                  {:else}
                    저장됨
                  {/if}
                </span>
                <span class="spacer"></span>
                {#if externalFileChanged}
                  <button type="button" class="editor-action" onclick={handleReloadCurrentFile}>다시 불러오기</button>
                {/if}
                <button type="button" class="editor-action" onclick={handleRevertFile} disabled={!hasUnsavedChanges() || savingFile}>되돌리기</button>
                <button type="button" class="editor-save" onclick={handleSaveFile} disabled={!hasUnsavedChanges() || savingFile}>
                  {savingFile ? '저장 중...' : '저장'}
                </button>
              </div>
              <div class="editor-body">
                <CodeEditor
                  value={editorContent}
                  language={$fileLanguage}
                  onchange={(value) => { editorContent = value; saveStatus = ''; }}
                />
              </div>
            </div>
          {:else}
            <pre class="code-preview"><code>{@html escapeHtml(getViewerContent($fileContent, $selectedFilePath, $fileLanguage, editorContent))}</code></pre>
          {/if}
        {:else}
          {#if $fileLoading}
            <p class="empty loading">불러오는 중...</p>
          {:else}
            <p class="empty">좌측에서 파일을 선택하세요</p>
          {/if}
        {/if}
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="panel chat-panel">
      {#if showChatList}
        <!-- Chat List View -->
        <div class="panel-header">
          <button class="link-btn" onclick={() => { showChatList = false; }}>← 돌아가기</button>
        </div>
        <div class="chat-list">
          {#each $chatSessions as c}
            <div class="chat-item" class:active={$currentChatId === c.id}>
              <button class="chat-select" onclick={() => handleSelectChat(c.id)}>
                <span class="chat-title">💬 {c.title}</span>
                <span class="chat-meta">{c.message_count}개 메시지</span>
              </button>
              <button class="delete-btn"
                onclick={(e) => { e.stopPropagation(); handleDeleteChat(c.id); }}
              >×</button>
            </div>
          {/each}
          <button class="new-chat-btn" onclick={handleNewChat}>+ 새 채팅</button>
        </div>
      {:else}
        <!-- Message View -->
        <div class="panel-header">
          채팅
          {#if $agentStatus !== 'idle'}
            <span class="status-badge">{$agentStatus}</span>
          {/if}
          <span class="spacer"></span>
          <button class="link-btn" onclick={() => { showChatList = true; }}>채팅 목록</button>
        </div>
        <div class="messages" bind:this={chatContainer}>
          {#each $messages as msg}
            {#if msg.role === 'tool_step'}
              <div class="tool-step-inline">
                <span class="step-text">{msg.content}</span>
              </div>
            {:else}
              <div class="message" class:user={msg.role === 'user'} class:assistant={msg.role !== 'user'}>
                <div class="msg-role">{msg.role === 'user' ? '🧑' : '🤖'}</div>
                <div class="msg-content">{msg.content}</div>
              </div>
            {/if}
          {/each}
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
      {/if}
    </div>
  </div>
</div>

<style>
  .layout { height: 100vh; display: flex; flex-direction: column; }
  .top-bar { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 1rem; background: #0f3460; border-bottom: 1px solid #333; font-size: 0.85rem; }
  .back-btn { background: none; border: 1px solid #555; border-radius: 6px; color: #ccc; padding: 0.25rem 0.5rem; cursor: pointer; font-size: 0.8rem; }
  .back-btn:hover { border-color: #e94560; color: #e94560; }
  .project-name { font-weight: 600; color: #e94560; }
  .spacer { flex: 1; }
  .user-name { color: #888; font-size: 0.8rem; }

  .workspace { flex: 1; display: flex; overflow: hidden; }

  .panel { display: flex; flex-direction: column; border-right: 1px solid #333; }
  .panel-header { padding: 0.6rem 1rem; background: #16213e; border-bottom: 1px solid #333; font-size: 0.85rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
  .file-panel { width: 200px; }
  .viewer-panel { flex: 1; min-width: 0; }
  .chat-panel { width: 400px; border-right: none; display: flex; flex-direction: column; }

  .side-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); flex-shrink: 0; background: #16213e; border-bottom: 1px solid #333; }
  .side-tab { min-width: 0; border: none; border-right: 1px solid #333; border-bottom: 1px solid #333; background: transparent; color: #aaa; padding: 0.45rem 0.35rem; font: inherit; font-size: 0.74rem; font-weight: 600; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .side-tab:nth-child(2n) { border-right: none; }
  .side-tab:nth-last-child(-n + 2) { border-bottom: none; }
  .side-tab:hover { color: #fff; background: #1a2a4e; }
  .side-tab.active { color: #fff; background: #e94560; }
  .side-list { flex: 1; overflow-y: auto; padding: 0.4rem; }
  .side-card { margin-bottom: 0.4rem; border: 1px solid #27324a; border-radius: 6px; background: #10172a; padding: 0.5rem; }
  .side-card-title { color: #fff; font-size: 0.82rem; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-card-meta { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.35rem; color: #9ca3af; font-size: 0.68rem; }
  .side-card-meta span { border-radius: 999px; background: #16213e; padding: 0.1rem 0.35rem; }
  .side-card-description { margin: 0.45rem 0 0; color: #b8c0cc; font-size: 0.74rem; line-height: 1.45; }
  .side-chip-list { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.45rem; }
  .side-chip { max-width: 100%; border-radius: 4px; background: #1a1a2e; color: #d8e2f1; padding: 0.12rem 0.3rem; font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-signature { display: block; margin-top: 0.35rem; color: #ffd166; font-family: Consolas, 'Courier New', monospace; font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-error { border: 1px solid #5a2735; border-radius: 6px; background: #1f1020; color: #ffbdc9; padding: 0.6rem; font-size: 0.75rem; line-height: 1.45; }
  .file-list { flex: 1; overflow-y: auto; padding: 0.25rem; }
  .file-item { padding: 0.35rem 0.5rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; background: transparent; border: none; color: #e0e0e0; width: 100%; text-align: left; font-family: inherit; display: block; }
  .file-item:hover { background: #16213e; }
  .file-item.active { background: #1a1a2e; color: #e94560; }

  .viewer-header { padding: 0; min-height: 40px; align-items: stretch; gap: 0; }
  .viewer-title { display: flex; align-items: center; flex: 0 1 auto; max-width: 45%; min-width: 0; padding: 0.6rem 1rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .viewer-status-spacer { flex: 1; min-width: 0; }
  .dirty-badge, .external-badge { align-self: center; flex-shrink: 0; margin-right: 0.5rem; border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: 600; }
  .dirty-badge { background: #4b3b18; color: #ffd166; }
  .external-badge { background: #4b1f2c; color: #ff9bb0; }
  .viewer-tabs { display: flex; flex-shrink: 0; border-left: 1px solid #333; }
  .viewer-tab { border: none; border-right: 1px solid #333; background: #16213e; color: #aaa; padding: 0 0.85rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .viewer-tab:hover { color: #fff; background: #1a2a4e; }
  .viewer-tab.active { color: #fff; background: #e94560; }
  .viewer-content { flex: 1; overflow: auto; padding: 0; background: #0a0a1a; }
  .code-preview { margin: 0; min-height: 100%; padding: 1rem; box-sizing: border-box; font-size: 0.8rem; line-height: 1.5; white-space: pre; word-break: normal; overflow: auto; }
  .code-preview code { font-family: Consolas, 'Courier New', monospace; }
  .html-preview-frame { position: relative; width: 100%; height: 100%; min-height: 100%; }
  .html-preview-refresh { position: absolute; top: 0.6rem; right: 0.8rem; z-index: 2; border: 1px solid rgba(0,0,0,0.12); border-radius: 6px; background: rgba(255,255,255,0.92); color: #333; padding: 0.3rem 0.6rem; font: inherit; font-size: 0.75rem; font-weight: 600; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.12); }
  .html-preview-refresh:hover { background: #fff; border-color: rgba(0,0,0,0.24); }
  .html-preview { display: block; width: 100%; height: 100%; min-height: 100%; border: 0; background: #fff; }
  .markdown-preview { min-height: 100%; box-sizing: border-box; padding: 1.25rem; color: #e0e0e0; line-height: 1.65; background: #0f1729; }
  .markdown-preview :global(h1),
  .markdown-preview :global(h2),
  .markdown-preview :global(h3) { margin: 1.1em 0 0.55em; color: #fff; line-height: 1.25; }
  .markdown-preview :global(h1:first-child),
  .markdown-preview :global(h2:first-child),
  .markdown-preview :global(h3:first-child) { margin-top: 0; }
  .markdown-preview :global(p) { margin: 0 0 0.85rem; }
  .markdown-preview :global(a) { color: #7db7ff; }
  .markdown-preview :global(ul),
  .markdown-preview :global(ol) { padding-left: 1.4rem; margin: 0 0 0.85rem; }
  .markdown-preview :global(blockquote) { margin: 0 0 0.85rem; padding-left: 0.85rem; border-left: 3px solid #e94560; color: #bbb; }
  .markdown-preview :global(code) { border-radius: 4px; background: #1a1a2e; padding: 0.1rem 0.25rem; font-family: Consolas, 'Courier New', monospace; font-size: 0.9em; }
  .markdown-preview :global(pre) { overflow: auto; border-radius: 6px; background: #0a0a1a; padding: 0.85rem; }
  .markdown-preview :global(pre code) { background: transparent; padding: 0; }
  .markdown-preview :global(table) { width: 100%; border-collapse: collapse; margin: 0 0 1rem; font-size: 0.9rem; }
  .markdown-preview :global(th),
  .markdown-preview :global(td) { border: 1px solid #333; padding: 0.45rem 0.6rem; }
  .markdown-preview :global(th) { background: #16213e; color: #fff; }
  .csv-table-wrap, .csv-editor-body { min-height: 100%; box-sizing: border-box; overflow: auto; padding: 1rem; background: #0f1729; }
  .csv-editor-body { flex: 1; min-height: 0; }
  .csv-table { width: 100%; min-width: max-content; border-collapse: collapse; color: #e0e0e0; font-size: 0.8rem; line-height: 1.4; }
  .csv-table th, .csv-table td { border: 1px solid #2b3852; padding: 0.45rem 0.6rem; text-align: left; white-space: nowrap; max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
  .csv-table th, .csv-table tr.header-row td { background: #16213e; color: #fff; font-weight: 700; }
  .csv-edit-table td { padding: 0; max-width: none; overflow: visible; }
  .csv-edit-table input { width: 100%; min-width: 120px; box-sizing: border-box; border: 0; background: transparent; color: #f8fafc; padding: 0.45rem 0.6rem; font: inherit; }
  .csv-edit-table input:focus { position: relative; z-index: 1; outline: 2px solid #e94560; outline-offset: -2px; background: #111b33; }
  .csv-error { margin: 0; border: 1px solid #5a2735; border-radius: 6px; background: #1f1020; color: #ffbdc9; padding: 0.85rem; font-size: 0.82rem; line-height: 1.5; }
  .csv-error strong { display: block; margin-bottom: 0.35rem; color: #fff; }
  .csv-error pre { margin: 0 0 0.45rem; white-space: pre-wrap; font-family: Consolas, 'Courier New', monospace; }
  .editor-pane { height: 100%; min-height: 0; display: flex; flex-direction: column; background: #0a0a1a; }
  .editor-toolbar { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; padding: 0.45rem 0.6rem; border-bottom: 1px solid #333; background: #10172a; }
  .editor-status { color: #8bd3a7; font-size: 0.75rem; font-weight: 600; }
  .editor-status.dirty { color: #ffd166; }
  .editor-status.warning { color: #ff9bb0; }
  .editor-action, .editor-save { border: 1px solid #3a4660; border-radius: 6px; padding: 0.3rem 0.65rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .editor-action { background: transparent; color: #d0d7e2; }
  .editor-action:hover:not(:disabled) { border-color: #e94560; color: #fff; }
  .editor-save { border-color: #e94560; background: #e94560; color: #fff; }
  .editor-action:disabled, .editor-save:disabled { cursor: default; opacity: 0.45; }
  .editor-body { flex: 1; min-height: 0; }

  .link-btn { background: none; border: none; color: #e94560; cursor: pointer; font-size: 0.8rem; padding: 0; }
  .link-btn:hover { text-decoration: underline; }

  /* Chat list */
  .chat-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
  .chat-item { display: flex; align-items: center; margin-bottom: 2px; border-radius: 6px; }
  .chat-item:hover { background: #16213e; }
  .chat-item.active { background: #1a1a2e; }
  .chat-select { flex: 1; background: none; border: none; color: #e0e0e0; padding: 0.5rem 0.75rem; cursor: pointer; text-align: left; font-family: inherit; font-size: 0.85rem; display: flex; flex-direction: column; gap: 0.15rem; }
  .chat-title { font-weight: 500; }
  .chat-meta { font-size: 0.75rem; color: #888; }
  .delete-btn { background: none; border: none; color: #666; cursor: pointer; font-size: 1.1rem; padding: 0 8px; }
  .delete-btn:hover { color: #e94560; }
  .new-chat-btn { width: 100%; padding: 0.5rem; border: 1px dashed #555; border-radius: 6px; background: transparent; color: #e0e0e0; cursor: pointer; margin-top: 0.5rem; font-size: 0.85rem; }
  .new-chat-btn:hover { border-color: #e94560; color: #e94560; }

  /* Messages */
  .messages { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem; }
  .message { display: flex; gap: 0.5rem; }
  .message.user { flex-direction: row-reverse; }
  .msg-role { font-size: 1.2rem; flex-shrink: 0; }
  .msg-content { background: #16213e; padding: 0.6rem 0.8rem; border-radius: 8px; font-size: 0.85rem; line-height: 1.5; max-width: 85%; white-space: pre-wrap; }
  .message.user .msg-content { background: #0f3460; }

  .tool-step-inline { padding: 0.2rem 0.75rem; font-size: 0.8rem; color: #888; border-left: 2px solid #333; margin-left: 1.5rem; }
  .step-text { font-family: monospace; }

  .input-area { display: flex; gap: 0.5rem; padding: 0.75rem; border-top: 1px solid #333; }
  .input-area input { flex: 1; padding: 0.6rem; border: 1px solid #333; border-radius: 8px; background: #0f3460; color: #e0e0e0; font-size: 0.9rem; }
  .input-area input:focus { outline: none; border-color: #e94560; }
  .input-area button { padding: 0.6rem 1.2rem; border: none; border-radius: 8px; background: #e94560; color: white; cursor: pointer; }
  .input-area button:disabled { opacity: 0.5; }

  .status-badge { background: #e94560; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.7rem; }

  .empty { color: #555; font-size: 0.8rem; text-align: center; padding: 1rem; }
</style>

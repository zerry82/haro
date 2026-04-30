<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated, user } from '../stores/auth';
  import { currentProjectId, startProjectDeploy, stopProjectDeploy } from '../stores/projects';
  import { chatSessions, loadChatSessions, createChatSession, deleteChatSession, summarizeChatSession, currentChatId, type ChatSessionItem } from '../stores/chatSessions';
  import { messages, loadMessages, sendMessage, streaming, todoSteps, agentStatus, loadDebugTrace, type ChatMessage, type DebugTraceResponse } from '../stores/chat';
  import { fileTree, loadFiles, loadFileContent, saveFileContent, createFolder, uploadFiles, searchFiles, selectedFilePath, fileContent, fileLanguage, fileLoading, expandFolder, reloadAllExpanded, type FileSearchItem, type TreeNode } from '../stores/files';
  import { api } from '../lib/api';
  import CodeEditor from '../components/CodeEditor.svelte';
  import { marked } from 'marked';
  import hljs from 'highlight.js';
  import Papa from 'papaparse';
  import { Database, Files, FolderPlus, Lock, Search, Sparkles, Upload, Wrench } from 'lucide-svelte';
  import 'highlight.js/styles/github.css';

  let { params = {} }: { params?: { projectId?: string; chatId?: string } } = $props();

  let projectTitle = $state('');
  let projectRuntimeMode = $state<RuntimeMode>('work');
  let projectContainerStatus = $state('none');
  let previewUrl = $state('');
  let deployBusy = $state(false);
  let deployMessage = $state('');
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
  let focusedExplorerNode = $state<TreeNode | null>(null);
  let creatingFolder = $state(false);
  let creatingFolderParentPath = $state('/');
  let newFolderName = $state('');
  let fileActionMessage = $state('');
  let fileActionBusy = $state(false);
  let draggingFiles = $state(false);
  let uploadTargetDir = $state('/');
  let uploadInput = $state<HTMLInputElement | undefined>(undefined);
  let fileSearchQuery = $state('');
  let fileSearchResults = $state<FileSearchItem[]>([]);
  let fileSearchLoading = $state(false);
  let fileSearchMessage = $state('');
  let fileSearchSeq = 0;
  let chatActionMessage = $state('');
  let summarizingChat = $state(false);
  let renderComputeSeq = 0;
  let workspaceElement = $state<HTMLDivElement | undefined>(undefined);
  let filePanelWidth = $state(loadStoredPanelWidth('haro:filePanelWidth', 260));
  let chatPanelWidth = $state(loadStoredPanelWidth('haro:chatPanelWidth', 400));
  let debugMode = $state(loadStoredBool('haro:debugMode', false));
  let debugTraceOpen = $state(false);
  let debugTraceLoading = $state(false);
  let debugTraceError = $state('');
  let debugTrace = $state<DebugTraceResponse | null>(null);
  let debugTraceMessage = $state<ChatMessage | null>(null);
  let debugPayloadView = $state<DebugPayloadView>('expanded');
  let debugTraceCopyMessage = $state('');
  let resizingPanel = $state<ResizePanel | null>(null);
  let resizeStartX = 0;
  let resizeStartFileWidth = 0;
  let resizeStartChatWidth = 0;

  type SidePanelTab = 'files' | 'skills' | 'tools' | 'dataSources';
  type SidePanelTabItem = { id: SidePanelTab; label: string };
  type RuntimeMode = 'work' | 'deploy';
  type ViewerTab = 'preview' | 'source' | 'code' | 'editor';
  type ViewerTabItem = { id: ViewerTab; label: string };
  type ResizePanel = 'file' | 'chat';
  type DebugPayloadView = 'expanded' | 'json';
  type DebugPayloadSection = { title: string; content: string; code?: boolean };
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
    { name: 'file_search', signature: 'file_search(query, limit)', description: '파일명, 경로, 요약 텍스트 검색' },
    { name: 'file_count', signature: 'file_count(path, item_type, recursive)', description: '파일/폴더 개수 조회' },
    { name: 'code_run', signature: 'code_run(filename, code)', description: '샌드박스 안에서 코드 실행' },
    { name: 'web_preview', signature: 'web_preview()', description: '웹앱 배포모드 활성화 및 URL 반환' },
  ];

  const EDITABLE_EXTENSIONS = [
    '.html', '.md', '.csv', '.ts', '.js', '.json',
    '.txt', '.css', '.py', '.yaml', '.yml', '.svg',
  ];

  const FILE_PANEL_MIN = 220;
  const FILE_PANEL_MAX = 560;
  const CHAT_PANEL_MIN = 300;
  const CHAT_PANEL_MAX = 720;
  const VIEWER_PANEL_MIN = 360;

  function loadStoredPanelWidth(key: string, fallback: number) {
    if (typeof localStorage === 'undefined') return fallback;
    const saved = Number(localStorage.getItem(key));
    return Number.isFinite(saved) && saved > 0 ? saved : fallback;
  }

  function saveStoredPanelWidth(key: string, value: number) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(key, String(Math.round(value)));
  }

  function loadStoredBool(key: string, fallback: boolean) {
    if (typeof localStorage === 'undefined') return fallback;
    const saved = localStorage.getItem(key);
    if (saved === null) return fallback;
    return saved === 'true';
  }

  function saveStoredBool(key: string, value: boolean) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(key, value ? 'true' : 'false');
  }

  function getDebugModeStorageKey() {
    return `haro:debugMode:${$user?.id || 'anonymous'}`;
  }

  function clamp(value: number, min: number, max: number) {
    return Math.min(Math.max(value, min), max);
  }

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

  function getSidePanelTitle() {
    return SIDE_PANEL_TABS.find((tab) => tab.id === activeSideTab)?.label || '폴더';
  }

  function getParentPath(path: string | null) {
    if (!path || path === '/') return '/';
    const normalized = path.endsWith('/') ? path.slice(0, -1) : path;
    const index = normalized.lastIndexOf('/');
    return index <= 0 ? '/' : normalized.slice(0, index);
  }

  function normalizeWorkspacePath(path: string | null) {
    if (!path) return '/';
    const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
    const normalized: string[] = [];
    for (const part of parts) {
      if (part === '.') continue;
      if (part === '..') {
        normalized.pop();
      } else {
        normalized.push(part);
      }
    }
    return normalized.length === 0 ? '/' : `/${normalized.join('/')}`;
  }

  function isCleanRoomPath(path: string | null) {
    const normalized = normalizeWorkspacePath(path);
    return normalized === '/clean-room' || normalized.startsWith('/clean-room/');
  }

  function getDefaultPlaygroundInbox() {
    return $user?.id ? `/playground/users/${$user.id}/00_inbox` : '/';
  }

  function isOwnPlaygroundPath(path: string | null) {
    const normalized = normalizeWorkspacePath(path);
    const root = $user?.id ? `/playground/users/${$user.id}` : '';
    return Boolean(root && (normalized === root || normalized.startsWith(`${root}/`)));
  }

  function getPathBadge(path: string | null) {
    if (isCleanRoomPath(path)) return '읽기 전용';
    if (isOwnPlaygroundPath(path)) return '내 작업공간';
    return '';
  }

  function joinExplorerPath(basePath: string, name: string) {
    return basePath === '/' ? `/${name}` : `${basePath.replace(/\/$/, '')}/${name}`;
  }

  function getExplorerTargetDir() {
    if (focusedExplorerNode?.type === 'directory') return focusedExplorerNode.path;
    if (focusedExplorerNode?.type === 'file') return getParentPath(focusedExplorerNode.path);
    if ($selectedFilePath) return getParentPath($selectedFilePath);
    return getDefaultPlaygroundInbox();
  }

  function getNodeTargetDir(node: TreeNode | null) {
    if (!node) return getExplorerTargetDir();
    return node.type === 'directory' ? node.path : getParentPath(node.path);
  }

  function isExplorerTargetReadOnly() {
    return isCleanRoomPath(getExplorerTargetDir());
  }

  function hasDraggedFiles(event: DragEvent) {
    return Array.from(event.dataTransfer?.types || []).includes('Files');
  }

  function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
  }

  async function refreshExplorerAfterMutation(projectId: string, targetDir: string) {
    await reloadAllExpanded(projectId);
    await loadFiles(projectId, targetDir);
    if (fileSearchQuery.trim()) {
      await runFileSearch();
    }
  }

  async function loadDefaultHarnessTree(projectId: string) {
    await loadFiles(projectId);
    if (!$user?.id) return;
    await loadFiles(projectId, '/playground');
    await loadFiles(projectId, '/playground/users');
    await loadFiles(projectId, `/playground/users/${$user.id}`);
  }

  function getRuntimeModeLabel() {
    return projectRuntimeMode === 'deploy' ? '배포모드' : '작업모드';
  }

  function getRoomLabel(room: string) {
    if (room === 'clean_room_data') return 'Data Clean Room';
    if (room === 'clean_room_meta') return 'Meta Clean Room';
    if (room === 'playground') return 'Playground';
    if (room === 'archive') return 'Archive';
    return 'Root';
  }

  async function runFileSearch() {
    const pid = $currentProjectId;
    const query = fileSearchQuery.trim();
    const seq = ++fileSearchSeq;
    fileSearchMessage = '';
    if (!pid || !query) {
      fileSearchResults = [];
      fileSearchLoading = false;
      return;
    }

    fileSearchLoading = true;
    try {
      const res = await searchFiles(pid, query, 50);
      if (seq !== fileSearchSeq) return;
      if (res.status === 'search_unavailable') {
        fileSearchResults = [];
        fileSearchMessage = '파일 검색 인덱스가 아직 준비되지 않았습니다.';
      } else {
        fileSearchResults = res.items || [];
        fileSearchMessage = fileSearchResults.length === 0 ? '검색 결과 없음' : '';
      }
    } catch (e) {
      if (seq !== fileSearchSeq) return;
      fileSearchResults = [];
      fileSearchMessage = getErrorMessage(e, '검색 실패');
    } finally {
      if (seq === fileSearchSeq) fileSearchLoading = false;
    }
  }

  function handleFileSearchInput() {
    const query = fileSearchQuery.trim();
    if (!query) {
      fileSearchSeq += 1;
      fileSearchResults = [];
      fileSearchMessage = '';
      fileSearchLoading = false;
      return;
    }
    window.setTimeout(() => {
      if (query === fileSearchQuery.trim()) void runFileSearch();
    }, 180);
  }

  function applyProjectState(project: any) {
    projectTitle = project.title;
    projectRuntimeMode = project.runtime_mode === 'deploy' ? 'deploy' : 'work';
    projectContainerStatus = project.container_status || 'none';
    previewUrl = projectRuntimeMode === 'deploy' ? `/preview/${project.id}/` : '';
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

  function renderChatMarkdown(content: string | null) {
    const html = marked.parse(content || '', { async: false, breaks: true }) as string;
    return sanitizeChatMarkdown(html);
  }

  function sanitizeChatMarkdown(html: string) {
    if (typeof document === 'undefined') return html;
    const template = document.createElement('template');
    template.innerHTML = html;
    template.content.querySelectorAll('script, style, iframe, object, embed, link, meta').forEach((node) => node.remove());
    template.content.querySelectorAll('*').forEach((element) => {
      Array.from(element.attributes).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (name.startsWith('on') || name === 'srcdoc') {
          element.removeAttribute(attribute.name);
          return;
        }
        if ((name === 'href' || name === 'src') && value.startsWith('javascript:')) {
          element.removeAttribute(attribute.name);
        }
      });
      if (element.tagName.toLowerCase() === 'a') {
        element.setAttribute('target', '_blank');
        element.setAttribute('rel', 'noreferrer');
      }
    });
    return template.innerHTML;
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

  async function handleDeployToggle() {
    const pid = $currentProjectId;
    if (!pid || deployBusy) return;
    deployBusy = true;
    deployMessage = '';
    try {
      if (projectRuntimeMode === 'deploy') {
        const res = await stopProjectDeploy(pid);
        projectRuntimeMode = res.runtime_mode;
        projectContainerStatus = res.container_status;
        previewUrl = '';
        deployMessage = '웹앱 비활성화됨';
      } else {
        const res = await startProjectDeploy(pid);
        projectRuntimeMode = res.runtime_mode;
        projectContainerStatus = res.container_status;
        previewUrl = res.preview_url || `/preview/${pid}/`;
        deployMessage = '웹앱 활성화됨';
      }
    } catch (e: any) {
      deployMessage = e.message || '웹앱 상태 변경 실패';
    } finally {
      deployBusy = false;
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
    debugMode = loadStoredBool(getDebugModeStorageKey(), false);

    currentProjectId.set(pid);

    // Load project info
    try {
      const res: any = await api(`/projects`);
      const proj = res.projects.find((p: any) => p.id === pid);
      if (!proj) { push('/projects'); return; }
      applyProjectState(proj);
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
    await loadDefaultHarnessTree(pid);

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

  onDestroy(() => {
    document.body.classList.remove('resizing-columns');
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
    await reloadAllExpanded(pid);
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
    await sendMessage(pid, cid, text, { debugEnabled: debugMode });
    if (pid) await reloadAllExpanded(pid);
  }

  function handleDebugModeChange() {
    saveStoredBool(getDebugModeStorageKey(), debugMode);
  }

  function isDebugInspectable(msg: ChatMessage) {
    return msg.role === 'user';
  }

  function formatDebugPayload(payload: unknown) {
    if (typeof payload === 'string') return payload;
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  }

  function escapeDebugHtml(text: string) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function highlightDebugPayload(payload: unknown) {
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

  function stringifyDebugValue(value: unknown) {
    if (typeof value === 'string') return value;
    if (value === null || value === undefined) return '';
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  function debugPayloadRecord(payload: unknown): Record<string, unknown> {
    if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
      return payload as Record<string, unknown>;
    }
    return { value: payload };
  }

  function debugContentText(entry: unknown) {
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

  function debugPayloadSections(eventType: string, payload: unknown): DebugPayloadSection[] {
    const record = debugPayloadRecord(payload);
    const sections: DebugPayloadSection[] = [];

    if (eventType === 'llm_request') {
      sections.push({ title: '모델', content: stringifyDebugValue(record.model) || '-' });
      sections.push({ title: 'System Instruction', content: stringifyDebugValue(record.system_instruction) });
      addContentSections(sections, record.contents);
      sections.push({ title: 'Generation Config', content: stringifyDebugValue(record.config), code: true });
      return sections;
    }

    if (eventType === 'llm_response') {
      sections.push({ title: '응답 원문', content: stringifyDebugValue(record.text) });
      sections.push({ title: 'Tool Call 포함 여부', content: record.has_tool_call ? '예' : '아니오' });
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

  function debugEventLabel(eventType: string) {
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

  async function openDebugTrace(msg: ChatMessage) {
    if (!isDebugInspectable(msg)) return;
    const pid = $currentProjectId;
    const cid = $currentChatId;
    if (!pid || !cid) return;
    debugTraceOpen = true;
    debugTraceLoading = true;
    debugTraceError = '';
    debugTrace = null;
    debugTraceMessage = msg;
    debugPayloadView = 'expanded';
    debugTraceCopyMessage = '';
    try {
      debugTrace = await loadDebugTrace(pid, cid, msg.id);
    } catch (e: any) {
      debugTraceError = e.message || '디버그 기록을 불러오지 못했습니다.';
    } finally {
      debugTraceLoading = false;
    }
  }

  function handleDebugMessageKeydown(event: KeyboardEvent, msg: ChatMessage) {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    openDebugTrace(msg);
  }

  function closeDebugTrace() {
    debugTraceOpen = false;
    debugTraceLoading = false;
    debugTraceError = '';
    debugTrace = null;
    debugTraceMessage = null;
    debugTraceCopyMessage = '';
  }

  async function copyDebugPayload(payload: unknown) {
    if (!navigator.clipboard) return;
    await navigator.clipboard.writeText(formatDebugPayload(payload));
  }

  function buildDebugTraceExport() {
    return {
      exported_at: new Date().toISOString(),
      project_id: $currentProjectId,
      chat_id: $currentChatId,
      message: debugTraceMessage ? {
        id: debugTraceMessage.id,
        role: debugTraceMessage.role,
        content: debugTraceMessage.content,
        metadata: debugTraceMessage.metadata || null,
        created_at: debugTraceMessage.created_at || null,
      } : null,
      trace: debugTrace,
    };
  }

  async function copyFullDebugTrace() {
    if (!debugTrace || !navigator.clipboard) return;
    debugTraceCopyMessage = '';
    try {
      await navigator.clipboard.writeText(JSON.stringify(buildDebugTraceExport(), null, 2));
      debugTraceCopyMessage = '전체 trace JSON 복사됨';
    } catch (e: any) {
      debugTraceCopyMessage = e.message || '복사 실패';
    }
  }

  async function handleSummarizeChat() {
    const pid = $currentProjectId;
    const cid = $currentChatId;
    if (!pid || !cid || summarizingChat) return;
    summarizingChat = true;
    chatActionMessage = '';
    try {
      const result = await summarizeChatSession(pid, cid);
      chatActionMessage = result.summary_path
        ? `요약 저장: ${result.summary_path}`
        : '요약할 메시지가 없습니다.';
      await reloadAllExpanded(pid);
      await loadChatSessions(pid);
    } catch (e: any) {
      chatActionMessage = e.message || '요약 실패';
    } finally {
      summarizingChat = false;
    }
  }

  async function handleSaveFile() {
    const pid = $currentProjectId;
    const path = $selectedFilePath;
    if (!pid || !path || savingFile || !isEditableTextFile(path, $fileLanguage)) return;
    if (isCleanRoomPath(path)) {
      saveStatus = 'Clean Room은 직접 수정할 수 없습니다.';
      return;
    }
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

  function beginCreateFolder() {
    activeSideTab = 'files';
    if (isExplorerTargetReadOnly()) {
      fileActionMessage = 'Clean Room에는 직접 폴더를 만들 수 없습니다.';
      return;
    }
    creatingFolder = true;
    creatingFolderParentPath = getExplorerTargetDir();
    newFolderName = '';
    fileActionMessage = '';
  }

  function cancelCreateFolder() {
    creatingFolder = false;
    creatingFolderParentPath = '/';
    newFolderName = '';
  }

  async function submitCreateFolder() {
    const pid = $currentProjectId;
    const folderName = newFolderName.trim();
    if (!pid || fileActionBusy) return;
    if (!folderName || folderName === '.' || folderName === '..' || folderName.includes('/') || folderName.includes('\\')) {
      fileActionMessage = '올바른 폴더 이름을 입력하세요.';
      return;
    }

    const targetDir = creatingFolderParentPath || getExplorerTargetDir();
    if (isCleanRoomPath(targetDir)) {
      fileActionMessage = 'Clean Room에는 직접 폴더를 만들 수 없습니다.';
      return;
    }
    const folderPath = joinExplorerPath(targetDir, folderName);
    fileActionBusy = true;
    fileActionMessage = '';
    try {
      await createFolder(pid, folderPath);
      focusedExplorerNode = { name: folderName, type: 'directory', path: folderPath, children: [], expanded: false, loaded: false };
      creatingFolder = false;
      creatingFolderParentPath = '/';
      newFolderName = '';
      await refreshExplorerAfterMutation(pid, targetDir);
      fileActionMessage = `폴더 생성: ${folderName}`;
    } catch (e) {
      fileActionMessage = getErrorMessage(e, '폴더 생성 실패');
    } finally {
      fileActionBusy = false;
    }
  }

  function handleCreateFolderKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      void submitCreateFolder();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      cancelCreateFolder();
    }
  }

  function triggerUpload() {
    activeSideTab = 'files';
    uploadTargetDir = getExplorerTargetDir();
    if (isCleanRoomPath(uploadTargetDir)) {
      fileActionMessage = 'Clean Room에는 직접 업로드할 수 없습니다.';
      return;
    }
    fileActionMessage = '';
    uploadInput?.click();
  }

  async function uploadSelectedFiles(selectedFiles: File[], targetDir: string) {
    const pid = $currentProjectId;
    if (!pid || selectedFiles.length === 0 || fileActionBusy) return;
    if (isCleanRoomPath(targetDir)) {
      fileActionMessage = 'Clean Room에는 직접 업로드할 수 없습니다.';
      return;
    }

    fileActionBusy = true;
    fileActionMessage = '';
    try {
      const res = await uploadFiles(pid, targetDir, selectedFiles, false);
      await refreshExplorerAfterMutation(pid, targetDir);
      fileActionMessage = `업로드 완료: ${res.uploaded.length}개`;
    } catch (e) {
      const message = getErrorMessage(e, '업로드 실패');
      if (message.includes('File already exists') && confirm('같은 이름의 파일이 있습니다. 덮어쓸까요?')) {
        try {
          const res = await uploadFiles(pid, targetDir, selectedFiles, true);
          await refreshExplorerAfterMutation(pid, targetDir);
          fileActionMessage = `덮어쓰기 완료: ${res.uploaded.length}개`;
        } catch (overwriteError) {
          fileActionMessage = getErrorMessage(overwriteError, '업로드 실패');
        }
      } else {
        fileActionMessage = message;
      }
    } finally {
      fileActionBusy = false;
    }
  }

  async function handleUploadChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const selectedFiles = Array.from(input.files || []);
    input.value = '';
    await uploadSelectedFiles(selectedFiles, uploadTargetDir || getExplorerTargetDir());
  }

  function handleFileDragOver(event: DragEvent, node: TreeNode | null = null) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer!.dropEffect = 'copy';
    draggingFiles = true;
    if (node) focusedExplorerNode = node;
  }

  function handleFileDragLeave(event: DragEvent) {
    if (event.currentTarget instanceof HTMLElement &&
      event.relatedTarget instanceof Node &&
      event.currentTarget.contains(event.relatedTarget)) {
      return;
    }
    draggingFiles = false;
  }

  async function handleFileDrop(event: DragEvent, node: TreeNode | null = null) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    draggingFiles = false;
    const droppedFiles = Array.from(event.dataTransfer?.files || []);
    if (droppedFiles.length === 0) return;
    if (node) focusedExplorerNode = node;
    await uploadSelectedFiles(droppedFiles, getNodeTargetDir(node));
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
    if (isCleanRoomPath(path)) {
      saveStatus = 'Clean Room은 직접 수정할 수 없습니다.';
      return;
    }
    if (hasUnsavedChanges() && !savingFile) handleSaveFile();
  }

  function getWorkspaceWidth() {
    return workspaceElement?.clientWidth || window.innerWidth;
  }

  function beginPanelResize(panel: ResizePanel, event: PointerEvent) {
    event.preventDefault();
    resizingPanel = panel;
    resizeStartX = event.clientX;
    resizeStartFileWidth = filePanelWidth;
    resizeStartChatWidth = chatPanelWidth;
    document.body.classList.add('resizing-columns');
  }

  function handleWorkspaceResizeMove(event: PointerEvent) {
    if (!resizingPanel) return;
    event.preventDefault();

    const workspaceWidth = getWorkspaceWidth();
    const deltaX = event.clientX - resizeStartX;

    if (resizingPanel === 'file') {
      const maxWidth = Math.min(FILE_PANEL_MAX, workspaceWidth - chatPanelWidth - VIEWER_PANEL_MIN);
      filePanelWidth = clamp(resizeStartFileWidth + deltaX, FILE_PANEL_MIN, Math.max(FILE_PANEL_MIN, maxWidth));
    } else {
      const maxWidth = Math.min(CHAT_PANEL_MAX, workspaceWidth - filePanelWidth - VIEWER_PANEL_MIN);
      chatPanelWidth = clamp(resizeStartChatWidth - deltaX, CHAT_PANEL_MIN, Math.max(CHAT_PANEL_MIN, maxWidth));
    }
  }

  function endPanelResize() {
    if (!resizingPanel) return;
    saveStoredPanelWidth('haro:filePanelWidth', filePanelWidth);
    saveStoredPanelWidth('haro:chatPanelWidth', chatPanelWidth);
    resizingPanel = null;
    document.body.classList.remove('resizing-columns');
  }

  async function handleNodeClick(node: TreeNode) {
    const pid = $currentProjectId;
    if (!pid) return;
    focusedExplorerNode = node;
    fileActionMessage = '';
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

  async function handleSearchResultClick(item: FileSearchItem) {
    const pid = $currentProjectId;
    if (!pid) return;
    fileActionMessage = '';
    const node: TreeNode = {
      name: item.name,
      type: item.item_type,
      path: item.path,
      children: item.item_type === 'directory' ? [] : undefined,
      expanded: false,
      loaded: false,
    };
    focusedExplorerNode = node;
    if (item.item_type === 'directory') {
      activeSideTab = 'files';
      await loadFiles(pid, item.path);
      return;
    }
    if (item.path !== $selectedFilePath && hasUnsavedChanges() &&
      !confirm('저장하지 않은 변경사항을 버리고 다른 파일을 여시겠습니까?')) {
      return;
    }
    await loadFileContent(pid, item.path);
  }
</script>

<svelte:window
  onkeydown={handleWindowKeydown}
  onpointermove={handleWorkspaceResizeMove}
  onpointerup={endPanelResize}
  onblur={endPanelResize}
/>

<div class="layout">
  <!-- Top bar -->
  <header class="top-bar">
    <button class="back-btn" onclick={() => push('/projects')}>← 프로젝트</button>
    <span class="project-name">{projectTitle}</span>
    <span class="runtime-badge" class:deploy={projectRuntimeMode === 'deploy'}>{getRuntimeModeLabel()}</span>
    <span class="container-badge" class:running={projectContainerStatus === 'running'}>{projectContainerStatus}</span>
    <button class="deploy-btn" onclick={handleDeployToggle} disabled={deployBusy}>
      {#if deployBusy}
        처리 중...
      {:else if projectRuntimeMode === 'deploy'}
        웹앱 비활성화
      {:else}
        웹앱 활성화
      {/if}
    </button>
    {#if previewUrl}
      <a class="preview-link" href={previewUrl} target="_blank" rel="noreferrer">열기</a>
    {/if}
    {#if deployMessage}
      <span class="deploy-message" class:error={deployMessage.includes('실패') || deployMessage.includes('failed')}>{deployMessage}</span>
    {/if}
    <span class="spacer"></span>
    <span class="user-name">{$user?.name}</span>
  </header>

  <div class="workspace" class:resizing={resizingPanel !== null} bind:this={workspaceElement}>
    <!-- File Explorer -->
    <div class="panel file-panel" style="width: {filePanelWidth}px">
      <div class="activity-bar" role="tablist" aria-label="왼쪽 메뉴">
        {#each SIDE_PANEL_TABS as tab}
          <button
            type="button"
            class="activity-tab"
            class:active={activeSideTab === tab.id}
            role="tab"
            aria-selected={activeSideTab === tab.id}
            aria-label={tab.label}
            title={tab.label}
            onclick={() => { activeSideTab = tab.id; }}
          >
            {#if tab.id === 'files'}
              <Files size={24} strokeWidth={1.8} />
            {:else if tab.id === 'skills'}
              <Sparkles size={24} strokeWidth={1.8} />
            {:else if tab.id === 'tools'}
              <Wrench size={24} strokeWidth={1.8} />
            {:else}
              <Database size={24} strokeWidth={1.8} />
            {/if}
            <span class="sr-only">{tab.label}</span>
          </button>
        {/each}
      </div>

      <div class="side-panel-shell">
        <div class="side-panel-header">
          <span class="side-panel-title">{getSidePanelTitle()}</span>
          {#if activeSideTab === 'files'}
            <button
              type="button"
              class="side-icon-btn"
              title="새 폴더"
              aria-label="새 폴더"
              disabled={fileActionBusy || isExplorerTargetReadOnly()}
              onclick={beginCreateFolder}
            >
              <FolderPlus size={15} />
            </button>
            <button
              type="button"
              class="side-icon-btn"
              title="파일 업로드"
              aria-label="파일 업로드"
              disabled={fileActionBusy || isExplorerTargetReadOnly()}
              onclick={triggerUpload}
            >
              <Upload size={15} />
            </button>
            <input
              bind:this={uploadInput}
              class="hidden-file-input"
              type="file"
              multiple
              onchange={handleUploadChange}
            />
          {/if}
        </div>
        {#if activeSideTab === 'files'}
          {#if fileActionMessage}
            <div class="file-action-message">{fileActionMessage}</div>
          {/if}
          <div class="file-search">
            <Search size={14} />
            <input
              type="search"
              placeholder="파일명/요약 검색"
              bind:value={fileSearchQuery}
              oninput={handleFileSearchInput}
            />
          </div>
          <div
            class="file-list"
            class:dragging={draggingFiles}
            role="region"
            aria-label="파일 탐색기"
            ondragover={(event) => handleFileDragOver(event)}
            ondragleave={handleFileDragLeave}
            ondrop={(event) => handleFileDrop(event)}
          >
            {#snippet renderNewFolderRow(depth: number)}
              <div class="new-folder-row" style="margin-left: {depth * 0.75}rem">
                <input
                  class="new-folder-input"
                  type="text"
                  placeholder="새 폴더 이름"
                  bind:value={newFolderName}
                  disabled={fileActionBusy}
                  onkeydown={handleCreateFolderKeydown}
                />
                <button type="button" class="new-folder-action" disabled={fileActionBusy} onclick={submitCreateFolder}>생성</button>
                <button type="button" class="new-folder-action ghost" disabled={fileActionBusy} onclick={cancelCreateFolder}>취소</button>
              </div>
            {/snippet}
            {#if creatingFolder && creatingFolderParentPath === '/'}
              {@render renderNewFolderRow(0)}
            {/if}
            {#if fileSearchQuery.trim()}
              <div class="search-results">
                {#if fileSearchLoading}
                  <p class="empty">검색 중...</p>
                {:else if fileSearchMessage}
                  <p class="empty">{fileSearchMessage}</p>
                {:else}
                  {#each fileSearchResults as item}
                    <button
                      class="search-result"
                      type="button"
                      onclick={() => handleSearchResultClick(item)}
                    >
                      <span class="search-result-name">{item.name}</span>
                      <span class="search-result-path">{item.path}</span>
                      <span class="search-result-meta">
                        <span>{getRoomLabel(item.room)}</span>
                        <span>{item.item_type === 'directory' ? '폴더' : item.language || 'file'}</span>
                        {#if item.access_policy === 'read_only'}
                          <span>읽기 전용</span>
                        {/if}
                        {#if item.summary_status === 'stale'}
                          <span>요약 갱신 필요</span>
                        {/if}
                      </span>
                      {#if item.summary_snippet}
                        <span class="search-result-snippet">{item.summary_snippet}</span>
                      {/if}
                    </button>
                  {/each}
                {/if}
              </div>
            {:else}
              {#snippet renderTree(nodes: TreeNode[], depth: number)}
                {#each nodes as item}
                <button
                  class="file-item"
                  class:active={$selectedFilePath === item.path}
                  class:focused={focusedExplorerNode?.path === item.path}
                  class:readonly={isCleanRoomPath(item.path)}
                  style="padding-left: {0.5 + depth * 0.75}rem"
                  ondragover={(event) => handleFileDragOver(event, item)}
                  ondrop={(event) => handleFileDrop(event, item)}
                  onclick={() => handleNodeClick(item)}
                >
                  <span class="file-label">
                    {#if isCleanRoomPath(item.path)}
                      <Lock size={13} strokeWidth={2} />
                    {/if}
                    <span class="file-icon">
                    {#if item.type === 'directory'}
                      {item.expanded ? '📂' : '📁'}
                    {:else}
                      📄
                    {/if}
                    </span>
                    <span class="file-name">{item.name}</span>
                    {#if getPathBadge(item.path)}
                      <span class="path-badge">{getPathBadge(item.path)}</span>
                    {/if}
                  </span>
                </button>
                {#if creatingFolder && item.type === 'directory' && item.path === creatingFolderParentPath}
                  {@render renderNewFolderRow(depth + 1)}
                {/if}
                {#if item.type === 'directory' && item.expanded && item.children}
                  {@render renderTree(item.children, depth + 1)}
                {/if}
                {/each}
              {/snippet}
              {@render renderTree($fileTree, 0)}
              {#if $fileTree.length === 0}
                <p class="empty">파일 없음</p>
              {/if}
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
    </div>

    <button
      type="button"
      class="panel-resizer file-resizer"
      class:active={resizingPanel === 'file'}
      aria-label="폴더 패널 너비 조절"
      title="폴더 패널 너비 조절"
      onpointerdown={(event) => beginPanelResize('file', event)}
    ></button>

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
                  {#if isCleanRoomPath($selectedFilePath)}
                    Clean Room은 직접 수정할 수 없습니다.
                  {:else if externalFileChanged}
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
                <button type="button" class="editor-action" onclick={handleRevertFile} disabled={isCleanRoomPath($selectedFilePath) || !hasUnsavedChanges() || savingFile}>되돌리기</button>
                <button type="button" class="editor-save" onclick={handleSaveFile} disabled={isCleanRoomPath($selectedFilePath) || !hasUnsavedChanges() || savingFile}>
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
                                disabled={isCleanRoomPath($selectedFilePath)}
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
                  {#if isCleanRoomPath($selectedFilePath)}
                    Clean Room은 직접 수정할 수 없습니다.
                  {:else if externalFileChanged}
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
                <button type="button" class="editor-action" onclick={handleRevertFile} disabled={isCleanRoomPath($selectedFilePath) || !hasUnsavedChanges() || savingFile}>되돌리기</button>
                <button type="button" class="editor-save" onclick={handleSaveFile} disabled={isCleanRoomPath($selectedFilePath) || !hasUnsavedChanges() || savingFile}>
                  {savingFile ? '저장 중...' : '저장'}
                </button>
              </div>
              <div class="editor-body">
                <CodeEditor
                  value={editorContent}
                  language={$fileLanguage}
                  readonly={isCleanRoomPath($selectedFilePath)}
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

    <button
      type="button"
      class="panel-resizer chat-resizer"
      class:active={resizingPanel === 'chat'}
      aria-label="채팅 패널 너비 조절"
      title="채팅 패널 너비 조절"
      onpointerdown={(event) => beginPanelResize('chat', event)}
    ></button>

    <!-- Chat Panel -->
    <div class="panel chat-panel" style="width: {chatPanelWidth}px">
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
          <label class="debug-toggle" title="이후 메시지의 LLM 요청/응답 trace를 저장합니다.">
            <input type="checkbox" bind:checked={debugMode} onchange={handleDebugModeChange} />
            <span>디버그</span>
          </label>
          <button class="link-btn" disabled={summarizingChat || $streaming} onclick={handleSummarizeChat}>
            {summarizingChat ? '요약 중...' : '요약'}
          </button>
          <button class="link-btn" onclick={() => { showChatList = true; }}>채팅 목록</button>
        </div>
        {#if chatActionMessage}
          <div class="chat-action-message">{chatActionMessage}</div>
        {/if}
        <div class="messages" bind:this={chatContainer}>
          {#each $messages as msg}
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
                    onclick={() => openDebugTrace(msg)}
                    onkeydown={(event) => handleDebugMessageKeydown(event, msg)}
                  >{@html renderChatMarkdown(msg.content)}</div>
                {:else}
                  <div class="msg-content">{@html renderChatMarkdown(msg.content)}</div>
                {/if}
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

{#if debugTraceOpen}
  <div class="modal-backdrop" role="presentation" onclick={closeDebugTrace}>
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
        <button type="button" class="modal-close" onclick={closeDebugTrace}>닫기</button>
      </header>
      <div class="debug-message-preview">{debugTraceMessage?.content}</div>
      <div class="debug-view-toggle" role="group" aria-label="디버그 payload 보기 방식">
        <button
          type="button"
          class:active={debugPayloadView === 'expanded'}
          onclick={() => { debugPayloadView = 'expanded'; }}
        >풀어서 보기</button>
        <button
          type="button"
          class:active={debugPayloadView === 'json'}
          onclick={() => { debugPayloadView = 'json'; }}
        >JSON</button>
        <button
          type="button"
          class="debug-copy-all"
          disabled={!debugTrace?.has_trace || debugTraceLoading}
          onclick={copyFullDebugTrace}
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
          {#each debugTrace.events as event}
            <details class="debug-event" open={event.round_index === 0}>
              <summary>
                <span>{debugEventLabel(event.event_type)}</span>
                <small>round {event.round_index}{event.duration_ms ? ` · ${Math.round(event.duration_ms)}ms` : ''}</small>
              </summary>
              <div class="debug-event-toolbar">
                <span>{event.created_at}</span>
                <button type="button" class="link-btn" onclick={() => copyDebugPayload(event.payload)}>복사</button>
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
{/if}

<style>
  .layout { height: 100vh; display: flex; flex-direction: column; background: var(--color-bg); color: var(--color-text); }
  .top-bar { display: flex; align-items: center; gap: 0.75rem; padding: 0.45rem 0.8rem; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 0.85rem; }
  .back-btn { background: transparent; border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text-muted); padding: 0.25rem 0.5rem; cursor: pointer; font-size: 0.8rem; }
  .back-btn:hover { border-color: var(--color-accent); color: var(--color-accent-strong); background: var(--color-accent-soft); }
  .project-name { font-weight: 700; color: var(--color-text); }
  .runtime-badge, .container-badge { flex-shrink: 0; border-radius: 999px; padding: 0.12rem 0.45rem; font-size: 0.7rem; font-weight: 700; }
  .runtime-badge { background: var(--color-info-soft); color: var(--color-info); }
  .runtime-badge.deploy { background: var(--color-pink-soft); color: #be185d; }
  .container-badge { background: var(--color-sidebar-strong); color: var(--color-text-muted); }
  .container-badge.running { color: var(--color-accent-strong); }
  .deploy-btn, .preview-link { flex-shrink: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-muted); padding: 0.25rem 0.55rem; font: inherit; font-size: 0.75rem; cursor: pointer; text-decoration: none; }
  .deploy-btn:hover:not(:disabled), .preview-link:hover { border-color: var(--color-accent); color: var(--color-accent-strong); background: var(--color-accent-soft); }
  .deploy-btn:disabled { cursor: default; opacity: 0.55; }
  .deploy-message { flex-shrink: 1; min-width: 0; color: var(--color-accent-strong); font-size: 0.72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .deploy-message.error { color: var(--color-danger); }
  .spacer { flex: 1; }
  .user-name { color: var(--color-text-muted); font-size: 0.8rem; }

  .workspace { flex: 1; display: flex; overflow: hidden; }
  .workspace.resizing { cursor: col-resize; user-select: none; }

  .panel { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); background: var(--color-surface); }
  .panel-header { padding: 0.6rem 1rem; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }
  .file-panel { flex: 0 0 auto; flex-direction: row; }
  .viewer-panel { flex: 1; min-width: 0; }
  .chat-panel { flex: 0 0 auto; border-right: none; display: flex; flex-direction: column; }
  .panel-resizer { position: relative; z-index: 5; flex: 0 0 8px; margin: 0 -4px; border: 0; padding: 0; background: transparent; cursor: col-resize; }
  .panel-resizer::before { content: ""; position: absolute; top: 0; bottom: 0; left: 3px; width: 1px; background: var(--color-border); transition: background 0.12s ease, width 0.12s ease, left 0.12s ease; }
  .panel-resizer:hover::before,
  .panel-resizer.active::before { left: 2px; width: 3px; background: var(--color-accent); }
  .panel-resizer:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  :global(body.resizing-columns) { cursor: col-resize; user-select: none; }

  .activity-bar { width: 48px; flex-shrink: 0; display: flex; flex-direction: column; align-items: stretch; padding: 0.25rem 0; background: var(--color-surface); border-right: 1px solid var(--color-border); }
  .activity-tab { position: relative; width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border: none; border-left: 2px solid transparent; background: transparent; color: var(--color-text-muted); cursor: pointer; }
  .activity-tab:hover { color: var(--color-text); background: var(--color-sidebar-strong); }
  .activity-tab.active { color: var(--color-text); border-left-color: var(--color-accent); background: var(--color-sidebar-strong); }
  .activity-tab.active::after { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 2px; background: var(--color-accent); }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
  .side-panel-shell { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--color-sidebar); }
  .side-panel-header { flex-shrink: 0; display: flex; align-items: center; gap: 0.35rem; min-height: 40px; padding: 0.35rem 0.5rem 0.35rem 0.75rem; border-bottom: 1px solid var(--color-border); background: var(--color-sidebar); color: var(--color-text); font-size: 0.75rem; font-weight: 700; letter-spacing: 0; }
  .side-panel-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-icon-btn { width: 28px; height: 28px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-muted); cursor: pointer; }
  .side-icon-btn:hover:not(:disabled) { border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
  .side-icon-btn:disabled { cursor: default; opacity: 0.45; }
  .hidden-file-input { display: none; }
  .side-list { flex: 1; overflow-y: auto; padding: 0.4rem; }
  .side-card { margin-bottom: 0.4rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-md); background: var(--color-surface); padding: 0.5rem; }
  .side-card-title { color: var(--color-text); font-size: 0.82rem; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-card-meta { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.35rem; color: var(--color-text-muted); font-size: 0.68rem; }
  .side-card-meta span { border-radius: 999px; background: var(--color-sidebar-strong); padding: 0.1rem 0.35rem; }
  .side-card-description { margin: 0.45rem 0 0; color: var(--color-text-muted); font-size: 0.74rem; line-height: 1.45; }
  .side-chip-list { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.45rem; }
  .side-chip { max-width: 100%; border-radius: var(--radius-sm); background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.12rem 0.3rem; font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-signature { display: block; margin-top: 0.35rem; color: var(--color-info); font-family: var(--font-mono); font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-error { border: 1px solid var(--color-danger-soft); border-radius: var(--radius-md); background: var(--color-danger-soft); color: var(--color-danger); padding: 0.6rem; font-size: 0.75rem; line-height: 1.45; }
  .file-action-message { flex-shrink: 0; margin: 0.35rem 0.4rem 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.35rem 0.45rem; font-size: 0.72rem; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-search { flex-shrink: 0; display: flex; align-items: center; gap: 0.35rem; margin: 0.35rem 0.4rem 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.25rem 0.4rem; }
  .file-search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--color-text); font: inherit; font-size: 0.76rem; }
  .file-search input::placeholder { color: var(--color-text-muted); }
  .file-list { flex: 1; overflow-y: auto; padding: 0.25rem; }
  .file-list.dragging { outline: 1px dashed var(--color-accent); outline-offset: -4px; background: var(--color-accent-soft); }
  .search-results { display: flex; flex-direction: column; gap: 0.3rem; padding: 0.15rem; }
  .search-result { width: 100%; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 0.45rem; text-align: left; cursor: pointer; font: inherit; }
  .search-result:hover { border-color: var(--color-info); background: var(--color-sidebar-strong); }
  .search-result-name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.78rem; font-weight: 700; }
  .search-result-path { display: block; margin-top: 0.16rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-muted); font-size: 0.66rem; }
  .search-result-meta { display: flex; flex-wrap: wrap; gap: 0.2rem; margin-top: 0.3rem; }
  .search-result-meta span { border-radius: 999px; background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.08rem 0.32rem; font-size: 0.62rem; }
  .search-result-snippet { display: -webkit-box; margin-top: 0.35rem; color: var(--color-text-muted); font-size: 0.68rem; line-height: 1.35; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .file-item { padding: 0.35rem 0.5rem; border-radius: var(--radius-sm); cursor: pointer; font-size: 0.8rem; background: transparent; border: none; color: var(--color-text); width: 100%; text-align: left; font-family: inherit; display: block; }
  .file-item.readonly { color: var(--color-text-muted); }
  .file-label { display: flex; align-items: center; gap: 0.25rem; min-width: 0; overflow: hidden; }
  .file-icon { flex-shrink: 0; }
  .file-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .path-badge { flex-shrink: 0; max-width: 72px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-radius: 999px; background: var(--color-info-soft); color: var(--color-info); padding: 0.08rem 0.32rem; font-size: 0.62rem; font-weight: 700; }
  .file-item:hover { background: var(--color-sidebar-strong); }
  .file-item.focused { outline: 1px solid #b7c2d2; outline-offset: -1px; background: var(--color-surface); }
  .file-item.active { background: var(--color-surface); color: var(--color-text); box-shadow: inset 0 0 0 1px var(--color-info); }
  .file-item.active.focused { outline-color: var(--color-info); }
  .new-folder-row { display: flex; align-items: center; gap: 0.25rem; margin: 0.15rem 0.1rem 0.35rem; padding: 0.25rem; border-radius: var(--radius-sm); background: var(--color-surface); }
  .new-folder-input { flex: 1; min-width: 0; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 0.35rem 0.45rem; font: inherit; font-size: 0.76rem; }
  .new-folder-input:focus { outline: none; border-color: var(--color-accent); }
  .new-folder-action { flex-shrink: 0; border: 1px solid var(--color-accent); border-radius: var(--radius-sm); background: var(--color-accent); color: #fff; padding: 0.35rem 0.45rem; font: inherit; font-size: 0.72rem; cursor: pointer; }
  .new-folder-action.ghost { border-color: var(--color-border); background: transparent; color: var(--color-text-muted); }
  .new-folder-action:hover:not(:disabled) { filter: brightness(1.08); }
  .new-folder-action:disabled { cursor: default; opacity: 0.5; }

  .viewer-header { padding: 0; min-height: 40px; align-items: stretch; gap: 0; }
  .viewer-title { display: flex; align-items: center; flex: 0 1 auto; max-width: 45%; min-width: 0; padding: 0.6rem 1rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .viewer-status-spacer { flex: 1; min-width: 0; }
  .dirty-badge, .external-badge { align-self: center; flex-shrink: 0; margin-right: 0.5rem; border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: 600; }
  .dirty-badge { background: var(--color-warning-soft); color: #92400e; }
  .external-badge { background: var(--color-danger-soft); color: var(--color-danger); }
  .viewer-tabs { display: flex; flex-shrink: 0; border-left: 1px solid var(--color-border); }
  .viewer-tab { border: none; border-right: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-text-muted); padding: 0 0.85rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .viewer-tab:hover { color: var(--color-text); background: var(--color-sidebar-strong); }
  .viewer-tab.active { color: var(--color-text); background: var(--color-pink-soft); box-shadow: inset 0 -2px 0 var(--color-pink); }
  .viewer-content { flex: 1; overflow: auto; padding: 0; background: var(--color-canvas); }
  .code-preview { margin: 0; min-height: 100%; padding: 1rem; box-sizing: border-box; font-size: 0.8rem; line-height: 1.5; white-space: pre; word-break: normal; overflow: auto; }
  .code-preview code { font-family: Consolas, 'Courier New', monospace; }
  .html-preview-frame { position: relative; width: 100%; height: 100%; min-height: 100%; }
  .html-preview-refresh { position: absolute; top: 0.6rem; right: 0.8rem; z-index: 2; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: rgba(255,255,255,0.92); color: var(--color-text); padding: 0.3rem 0.6rem; font: inherit; font-size: 0.75rem; font-weight: 600; cursor: pointer; box-shadow: 0 2px 6px rgba(15,23,42,0.12); }
  .html-preview-refresh:hover { background: var(--color-surface); border-color: var(--color-pink); }
  .html-preview { display: block; width: 100%; height: 100%; min-height: 100%; border: 0; background: var(--color-surface); }
  .markdown-preview { min-height: 100%; box-sizing: border-box; padding: 1.25rem; color: var(--color-text); line-height: 1.65; background: var(--color-canvas); }
  .markdown-preview :global(h1),
  .markdown-preview :global(h2),
  .markdown-preview :global(h3) { margin: 1.1em 0 0.55em; color: var(--color-text); line-height: 1.25; }
  .markdown-preview :global(h1:first-child),
  .markdown-preview :global(h2:first-child),
  .markdown-preview :global(h3:first-child) { margin-top: 0; }
  .markdown-preview :global(p) { margin: 0 0 0.85rem; }
  .markdown-preview :global(a) { color: var(--color-info); }
  .markdown-preview :global(ul),
  .markdown-preview :global(ol) { padding-left: 1.4rem; margin: 0 0 0.85rem; }
  .markdown-preview :global(blockquote) { margin: 0 0 0.85rem; padding-left: 0.85rem; border-left: 3px solid var(--color-pink); color: var(--color-text-muted); }
  .markdown-preview :global(code) { border-radius: 4px; background: var(--color-sidebar-strong); padding: 0.1rem 0.25rem; font-family: var(--font-mono); font-size: 0.9em; }
  .markdown-preview :global(pre) { overflow: auto; border-radius: var(--radius-md); background: var(--color-sidebar); padding: 0.85rem; }
  .markdown-preview :global(pre code) { background: transparent; padding: 0; }
  .markdown-preview :global(table) { width: 100%; border-collapse: collapse; margin: 0 0 1rem; font-size: 0.9rem; }
  .markdown-preview :global(th),
  .markdown-preview :global(td) { border: 1px solid var(--color-border); padding: 0.45rem 0.6rem; }
  .markdown-preview :global(th) { background: var(--color-sidebar); color: var(--color-text); }
  .csv-table-wrap, .csv-editor-body { min-height: 100%; box-sizing: border-box; overflow: auto; padding: 1rem; background: var(--color-canvas); }
  .csv-editor-body { flex: 1; min-height: 0; }
  .csv-table { width: 100%; min-width: max-content; border-collapse: collapse; color: var(--color-text); font-size: 0.8rem; line-height: 1.4; }
  .csv-table th, .csv-table td { border: 1px solid var(--color-border); padding: 0.45rem 0.6rem; text-align: left; white-space: nowrap; max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
  .csv-table th, .csv-table tr.header-row td { background: var(--color-sidebar); color: var(--color-text); font-weight: 700; }
  .csv-edit-table td { padding: 0; max-width: none; overflow: visible; }
  .csv-edit-table input { width: 100%; min-width: 120px; box-sizing: border-box; border: 0; background: transparent; color: var(--color-text); padding: 0.45rem 0.6rem; font: inherit; }
  .csv-edit-table input:focus { position: relative; z-index: 1; outline: 2px solid var(--color-pink); outline-offset: -2px; background: var(--color-pink-soft); }
  .csv-edit-table input:disabled { color: var(--color-text-muted); cursor: default; opacity: 0.78; }
  .csv-error { margin: 0; border: 1px solid var(--color-danger-soft); border-radius: var(--radius-md); background: var(--color-danger-soft); color: var(--color-danger); padding: 0.85rem; font-size: 0.82rem; line-height: 1.5; }
  .csv-error strong { display: block; margin-bottom: 0.35rem; color: var(--color-text); }
  .csv-error pre { margin: 0 0 0.45rem; white-space: pre-wrap; font-family: var(--font-mono); }
  .editor-pane { height: 100%; min-height: 0; display: flex; flex-direction: column; background: var(--color-surface); }
  .editor-toolbar { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--color-border); background: var(--color-sidebar); }
  .editor-status { color: var(--color-accent-strong); font-size: 0.75rem; font-weight: 600; }
  .editor-status.dirty { color: #92400e; }
  .editor-status.warning { color: var(--color-danger); }
  .editor-action, .editor-save { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 0.3rem 0.65rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .editor-action { background: transparent; color: var(--color-text-muted); }
  .editor-action:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-accent-strong); background: var(--color-accent-soft); }
  .editor-save { border-color: var(--color-accent); background: var(--color-accent); color: #fff; }
  .editor-action:disabled, .editor-save:disabled { cursor: default; opacity: 0.45; }
  .editor-body { flex: 1; min-height: 0; }

  .link-btn { background: none; border: none; color: var(--color-pink); cursor: pointer; font-size: 0.8rem; padding: 0; }
  .link-btn:hover { text-decoration: underline; }
  .link-btn:disabled { cursor: default; opacity: 0.45; text-decoration: none; }
  .debug-toggle { display: inline-flex; align-items: center; gap: 0.3rem; color: var(--color-text-muted); font-size: 0.75rem; font-weight: 700; cursor: pointer; }
  .debug-toggle input { width: 14px; height: 14px; accent-color: var(--color-pink); }

  /* Chat list */
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

  /* Messages */
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

  .empty { color: var(--color-text-subtle); font-size: 0.8rem; text-align: center; padding: 1rem; }

  .modal-backdrop { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; padding: 2rem; background: rgba(15, 23, 42, 0.35); }
  .debug-modal { width: min(920px, 92vw); max-height: 86vh; display: flex; flex-direction: column; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); color: var(--color-text); box-shadow: 0 22px 70px rgba(15, 23, 42, 0.28); overflow: hidden; }
  .debug-modal-header { flex-shrink: 0; display: flex; align-items: center; gap: 1rem; padding: 0.8rem 1rem; border-bottom: 1px solid var(--color-border); background: var(--color-sidebar); }
  .debug-modal-title { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.15rem; }
  .debug-modal-title strong { font-size: 0.95rem; }
  .debug-modal-title span { color: var(--color-text-muted); font-size: 0.72rem; }
  .modal-close { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-text-muted); padding: 0.35rem 0.65rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .modal-close:hover { border-color: var(--color-pink); color: var(--color-pink); }
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
  .debug-event summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.65rem 0.8rem; cursor: pointer; font-weight: 700; font-size: 0.82rem; }
  .debug-event summary small { color: var(--color-text-muted); font-weight: 500; }
  .debug-event-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.4rem 0.8rem; border-top: 1px solid var(--color-border-soft); color: var(--color-text-muted); font-size: 0.7rem; }
  .debug-expanded-view { display: flex; flex-direction: column; gap: 0.65rem; padding: 0.75rem; border-top: 1px solid var(--color-border-soft); background: var(--color-canvas); }
  .debug-md-section { border: 1px solid var(--color-border-soft); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }
  .debug-md-section h4 { margin: 0; padding: 0.45rem 0.7rem; border-bottom: 1px solid var(--color-border-soft); background: var(--color-sidebar); color: var(--color-text); font-size: 0.75rem; }
  .debug-md-text { padding: 0.7rem 0.8rem; white-space: pre-wrap; word-break: break-word; color: var(--color-text); font-size: 0.78rem; line-height: 1.55; }
  .debug-md-code { margin: 0; padding: 0.7rem 0.8rem; max-height: 320px; overflow: auto; background: var(--color-sidebar); color: var(--color-text); font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .debug-payload { margin: 0; max-height: 420px; overflow: auto; border-top: 1px solid var(--color-border-soft); background: #0f172a; color: #dbeafe; padding: 0.85rem; font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.55; tab-size: 2; white-space: pre-wrap; word-break: break-word; }
  .debug-payload :global(.debug-json-key) { color: #93c5fd; font-weight: 700; }
  .debug-payload :global(.debug-json-string) { color: #86efac; }
  .debug-payload :global(.debug-json-number) { color: #fbbf24; }
  .debug-payload :global(.debug-json-boolean) { color: #f0abfc; font-weight: 700; }
  .debug-payload :global(.debug-json-null) { color: #94a3b8; font-style: italic; }
</style>

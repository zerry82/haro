<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated, user } from '../stores/auth';
  import { currentProjectId, startProjectDeploy, stopProjectDeploy } from '../stores/projects';
  import { chatSessions, loadChatSessions, createChatSession, deleteChatSession, summarizeChatSession, currentChatId, type ChatSessionItem } from '../stores/chatSessions';
  import { messages, loadMessages, sendMessage, streaming, todoSteps, agentStatus, planMode, loadPlanModeState, loadDebugTrace, type ChatMessage, type DebugTraceResponse, type OpenFileContext, type OpenFileSelectionContext, type OpenMailContext } from '../stores/chat';
  import {
    fileTree,
    folderCache,
    selectFolderCacheForMode,
    loadDirectory,
    loadMoreDirectory,
    loadFileContent,
    saveFileContent,
    createFolder,
    uploadFiles,
    searchFiles,
    selectedFilePath,
    fileContent,
    fileLanguage,
    fileLoading,
    expandFolder,
    refreshChangedPath,
    refreshDirectory,
    reloadAllExpanded,
    markDirectoryDirty,
    type FileSearchItem,
    type TreeNode,
    type WorkspaceExplorerMode,
  } from '../stores/files';
  import { api } from '../lib/api';
  import {
    getDefaultPlaygroundInbox as getUserDefaultPlaygroundInbox,
    getDefaultViewerTab,
    getHtmlPreviewKey,
    getParentPath,
    getPathBadge as getWorkspacePathBadge,
    getRoomLabel,
    getRuntimeModeLabel as getWorkspaceRuntimeModeLabel,
    getViewerContent,
    getViewerTabs,
    isCleanRoomPath,
    isCsvFile,
    isEditableTextFile,
    isHtmlFile,
    isMarkdownFile,
    isSystemManagedPath,
    joinExplorerPath,
    type RuntimeMode,
    type ViewerTab,
  } from '../lib/workspaceUtils';
  import {
    buildDebugTraceExport,
    debugEventLabel,
    debugPayloadSections,
    formatDebugPayload,
    highlightDebugPayload,
    isDebugInspectable as isDebugRoleInspectable,
  } from '../lib/debugTraceUtils';
  import {
    highlightCode,
    parseCsvContent,
    registerWorkspaceHighlightLanguages,
    renderChatMarkdown,
    renderMarkdown,
    unparseCsvRows,
  } from '../lib/viewerRenderUtils';
  import {
    buildExplorerRows,
    getVirtualExplorerRows as virtualizeExplorerRows,
  } from '../lib/workspaceExplorerRows';
  import {
    getDebugModeStorageKey,
    loadStoredBool,
    loadStoredPanelWidth,
    saveStoredBool,
    saveStoredPanelWidth,
  } from '../lib/panelPreferences';
  import {
    formatChatMessageContent,
    formatToolStepContent as formatChatToolStepContent,
  } from '../lib/chatDisplay';
  import {
    createUserModeRootNodes,
    displayPathForMode,
    getDeveloperModeStorageKey,
    userModeMutationTarget,
  } from '../lib/workspaceFolderView';
  import {
    computePanelResize,
    type ResizePanel,
  } from '../lib/workspacePanelResize';
  import {
    getAffectedRefreshDirectories,
    getSelectedFileRefreshDecision,
    mergeRefreshQueue,
    normalizeFileChangedDetail,
  } from '../lib/workspaceFileRefresh';
  import {
    formatFileActionError as getErrorMessage,
    getExplorerTargetDir as resolveExplorerTargetDir,
    getNodeTargetDir as resolveNodeTargetDir,
    hasDraggedFiles,
    isReadOnlyMutationTarget,
    validateNewFolderName,
  } from '../lib/workspaceFileActions';
  import {
    buildFocusedSearchNode,
    isDirectorySearchResult,
    shouldConfirmDiscardUnsaved,
  } from '../lib/workspaceExplorerActions';
  import 'highlight.js/styles/github.css';
  import DebugTraceModal from '../components/DebugTraceModal.svelte';
  import FileViewerPanel from '../components/FileViewerPanel.svelte';
  import WorkspaceChatPanel from '../components/WorkspaceChatPanel.svelte';
  import WorkspaceMailShell from '../components/WorkspaceMailShell.svelte';
  import WorkspaceSidePanel from '../components/WorkspaceSidePanel.svelte';
  import WorkspaceTopBar from '../components/WorkspaceTopBar.svelte';
  import type { SidePanelTab, SkillResponse } from '../components/workspaceSidePanelTypes';
  import { SIDE_PANEL_TABS, TOOL_CATALOG } from '../lib/workspaceSidePanelConfig';

  registerWorkspaceHighlightLanguages();

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
  let currentMailContext = $state<OpenMailContext | null>(null);
  let activeViewerTab = $state<ViewerTab>('source');
  let lastViewerPath: string | null = null;
  let lastEditorPath: string | null = null;
  let editorContent = $state('');
  let editorBaseContent = $state('');
  let editorSelection = $state<OpenFileSelectionContext | null>(null);
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
  let planModeRequested = $state(false);
  let developerMode = $state(false);
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
  let fileListElement = $state<HTMLDivElement | undefined>(undefined);
  let fileListScrollTop = $state(0);
  let fileListHeight = $state(0);
  let fileRefreshTimer: ReturnType<typeof setTimeout> | null = null;
  let pendingFileRefreshPaths = new Map<string, string | undefined>();

  type DebugPayloadView = 'expanded' | 'json';
  type SkillListResponse = { skills: SkillResponse[] };

  function getCurrentDebugModeStorageKey() {
    return getDebugModeStorageKey($user?.id);
  }

  function getCurrentDeveloperModeStorageKey() {
    return getDeveloperModeStorageKey($user?.id);
  }

  function getExplorerMode(): WorkspaceExplorerMode {
    return developerMode ? 'developer' : 'user';
  }

  function getDirectoryLoadOptions() {
    return { mode: getExplorerMode(), includeHidden: developerMode };
  }

  function getModeFolderCache() {
    return selectFolderCacheForMode($folderCache, getExplorerMode());
  }

  function hasUnsavedChanges() {
    return $fileContent !== null && editorContent !== editorBaseContent;
  }

  function buildOpenFileContext(): OpenFileContext | null {
    const path = $selectedFilePath;
    if (!path) return null;
    const selection = editorSelection?.text_preview ? editorSelection : null;
    return {
      active_file_path: path,
      opened_file_paths: [path],
      language: $fileLanguage,
      active_viewer_tab: activeViewerTab,
      dirty: hasUnsavedChanges(),
      selection,
    };
  }

  function buildOpenMailContext(): OpenMailContext | null {
    if (activeSideTab !== 'mail') return null;
    return {
      active: true,
      latest_run_id: currentMailContext?.latest_run_id || null,
      latest_run_status: currentMailContext?.latest_run_status || null,
      selected_thread_id: currentMailContext?.selected_thread_id || null,
      selected_subject: currentMailContext?.selected_subject || null,
      selected_sender: currentMailContext?.selected_sender || null,
    };
  }

  function getSidePanelTitle() {
    return SIDE_PANEL_TABS.find((tab) => tab.id === activeSideTab)?.label || '폴더';
  }

  function getExplorerRows() {
    return buildExplorerRows($fileTree, getModeFolderCache(), creatingFolder, creatingFolderParentPath);
  }

  function getVirtualExplorerRows() {
    const rows = getExplorerRows();
    return virtualizeExplorerRows(rows, fileListScrollTop, fileListHeight);
  }

  function updateFileListViewport() {
    fileListScrollTop = fileListElement?.scrollTop || 0;
    fileListHeight = fileListElement?.clientHeight || fileListHeight;
  }

  function getDefaultPlaygroundInbox() {
    return getUserDefaultPlaygroundInbox($user?.id);
  }

  function getPathBadge(path: string | null) {
    return getWorkspacePathBadge(path, $user?.id);
  }

  function getDisplayPath(path: string | null | undefined) {
    return displayPathForMode(path, getExplorerMode(), $user?.id);
  }

  function shouldShowRawChatDetails() {
    return developerMode || debugMode;
  }

  function renderWorkspaceChatMarkdown(content: string | null) {
    return renderChatMarkdown(formatChatMessageContent(content, $user?.id, shouldShowRawChatDetails()));
  }

  function formatWorkspaceToolStep(content: string | null, metadata: any) {
    return formatChatToolStepContent(content, metadata, shouldShowRawChatDetails());
  }

  function getExplorerTargetDir() {
    const target = resolveExplorerTargetDir({
      focusedNode: focusedExplorerNode,
      selectedFilePath: $selectedFilePath,
      defaultInbox: getDefaultPlaygroundInbox(),
    });
    return getExplorerMode() === 'user' ? userModeMutationTarget(target, $user?.id) : target;
  }

  function getNodeTargetDir(node: TreeNode | null) {
    const target = resolveNodeTargetDir(node, getExplorerTargetDir());
    return getExplorerMode() === 'user' ? userModeMutationTarget(target, $user?.id) : target;
  }

  function isExplorerTargetReadOnly() {
    return isReadOnlyMutationTarget(getExplorerTargetDir());
  }

  async function refreshExplorerAfterMutation(projectId: string, targetDir: string) {
    await refreshDirectory(projectId, targetDir || '/', getDirectoryLoadOptions());
    if (fileSearchQuery.trim()) {
      await runFileSearch();
    }
  }

  async function loadWorkspaceTree(projectId: string) {
    focusedExplorerNode = null;
    if (!developerMode) {
      fileListScrollTop = 0;
      fileTree.set(createUserModeRootNodes($user?.id));
      return;
    }

    fileListScrollTop = 0;
    fileTree.set([]);
    const freshDeveloperLoad = { ...getDirectoryLoadOptions(), force: true };
    await loadDirectory(projectId, '/', freshDeveloperLoad);
    if (!$user?.id) return;
    await loadDirectory(projectId, '/playground', freshDeveloperLoad);
    await loadDirectory(projectId, '/playground/users', freshDeveloperLoad);
    await loadDirectory(projectId, `/playground/users/${$user.id}`, freshDeveloperLoad);
  }

  function getRuntimeModeLabel() {
    return getWorkspaceRuntimeModeLabel(projectRuntimeMode);
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
      const res = await searchFiles(pid, query, 50, { includeHidden: developerMode });
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

  function handleFileSearchInput(value?: string) {
    if (value !== undefined) {
      fileSearchQuery = value;
    }
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

  function refreshHtmlPreview() {
    htmlPreviewRevision += 1;
  }

  function handleCsvCellInput(rowIndex: number, cellIndex: number, event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    const nextRows = csvRows.map((row) => [...row]);
    if (!nextRows[rowIndex] || cellIndex >= nextRows[rowIndex].length) return;
    nextRows[rowIndex][cellIndex] = target.value;
    csvRows = nextRows;
    csvPreviewRows = nextRows;
    editorContent = unparseCsvRows(nextRows);
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
      editorSelection = null;
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

  $effect(() => {
    if (!$currentProjectId || developerMode || $fileTree.length > 0) return;
    fileTree.set(createUserModeRootNodes($user?.id));
  });

  onMount(async () => {
    if (!$isAuthenticated) { push('/login'); return; }
    const pid = params.projectId;
    if (!pid) { push('/projects'); return; }
    debugMode = loadStoredBool(getCurrentDebugModeStorageKey(), false);
    developerMode = loadStoredBool(getCurrentDeveloperModeStorageKey(), false);

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
    await loadPlanModeState(pid, chatId!);
    await loadWorkspaceTree(pid);

    // Update URL if needed
    if (!params.chatId || params.chatId !== chatId) {
      push(`/projects/${pid}/chats/${chatId}`);
    }
  });

  function queueExplorerRefresh(path: string, itemType?: string) {
    const pid = $currentProjectId;
    if (!pid) return;
    pendingFileRefreshPaths = mergeRefreshQueue(pendingFileRefreshPaths, path, itemType);
    for (const directoryPath of getAffectedRefreshDirectories(path, itemType)) {
      markDirectoryDirty(directoryPath, getExplorerMode());
    }
    if (fileRefreshTimer) clearTimeout(fileRefreshTimer);
    fileRefreshTimer = setTimeout(() => {
      void flushExplorerRefreshes();
    }, 180);
  }

  async function flushExplorerRefreshes() {
    const pid = $currentProjectId;
    if (!pid) return;
    const entries = Array.from(pendingFileRefreshPaths.entries());
    pendingFileRefreshPaths.clear();
    fileRefreshTimer = null;
    for (const [path, itemType] of entries) {
      await refreshChangedPath(pid, path, itemType, getDirectoryLoadOptions());
    }
    if (fileSearchQuery.trim()) {
      await runFileSearch();
    }
  }

  // Listen for file changes from SSE
  function handleFileChanged(event: Event) {
    const pid = $currentProjectId;
    const detail = normalizeFileChangedDetail(event instanceof CustomEvent ? event.detail : null);
    if (pid && detail.path) {
      queueExplorerRefresh(detail.path, detail.itemType);
    } else if (pid) {
      if (developerMode) {
        void reloadAllExpanded(pid, getDirectoryLoadOptions());
      } else {
        void loadWorkspaceTree(pid);
      }
    }
    const sp = $selectedFilePath;
    const decision = getSelectedFileRefreshDecision({
      changedPath: detail.path,
      selectedPath: sp,
      hasUnsavedChanges: hasUnsavedChanges(),
    });
    if (pid && decision.externalChanged) {
      externalFileChanged = true;
      return;
    }
    if (pid && decision.reloadPath) {
      void loadFileContent(pid, decision.reloadPath);
    }
  }

  onMount(() => {
    updateFileListViewport();
    const handleResize = () => updateFileListViewport();
    window.addEventListener('file-changed', handleFileChanged);
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('file-changed', handleFileChanged);
      window.removeEventListener('resize', handleResize);
      if (fileRefreshTimer) clearTimeout(fileRefreshTimer);
    };
  });

  onDestroy(() => {
    document.body.classList.remove('resizing-columns');
    if (fileRefreshTimer) clearTimeout(fileRefreshTimer);
  });

  async function handleSelectChat(chatId: string) {
    const pid = $currentProjectId;
    if (!pid) return;
    currentChatId.set(chatId);
    await loadMessages(pid, chatId);
    await loadPlanModeState(pid, chatId);
    showChatList = false;
    push(`/projects/${pid}/chats/${chatId}`);
  }

  async function handleNewChat() {
    const pid = $currentProjectId;
    if (!pid) return;
    const id = await createChatSession(pid);
    currentChatId.set(id);
    messages.set([]);
    planModeRequested = false;
    planMode.set({ active: false, planSessionId: null, status: 'idle', planFilePath: '', planContent: '', approvalRequested: false, approvalSummary: '' });
    showChatList = false;
    if (developerMode && $user?.id) {
      await refreshDirectory(pid, `/playground/users/${$user.id}`, getDirectoryLoadOptions());
      await refreshDirectory(pid, `/playground/users/${$user.id}/50_chats`, getDirectoryLoadOptions());
    }
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
    await sendMessage(pid, cid, text, {
      debugEnabled: debugMode,
      planModeRequested,
      openFileContext: buildOpenFileContext(),
      openMailContext: buildOpenMailContext(),
    });
  }

  async function handleApprovePlan() {
    const pid = $currentProjectId;
    const cid = $currentChatId;
    const sessionId = $planMode.planSessionId;
    if (!pid || !cid || !sessionId || $streaming) return;
    await sendMessage(pid, cid, '계획 승인', {
      debugEnabled: debugMode,
      planResponse: { plan_session_id: sessionId, action: 'approve' },
    });
  }

  async function handleRejectPlan(feedbackText: string) {
    const pid = $currentProjectId;
    const cid = $currentChatId;
    const sessionId = $planMode.planSessionId;
    if (!pid || !cid || !sessionId || $streaming) return;
    const feedback = feedbackText.trim();
    if (!feedback) return;
    await sendMessage(pid, cid, feedback, {
      debugEnabled: debugMode,
      planResponse: { plan_session_id: sessionId, action: 'reject', feedback },
    });
  }

  function handleDebugModeChange() {
    saveStoredBool(getCurrentDebugModeStorageKey(), debugMode);
  }

  async function handleDeveloperModeChange(value: boolean) {
    developerMode = value;
    saveStoredBool(getCurrentDeveloperModeStorageKey(), developerMode);
    const pid = $currentProjectId;
    if (pid) await loadWorkspaceTree(pid);
  }

  function isDebugInspectable(msg: ChatMessage) {
    return isDebugRoleInspectable(msg.role);
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

  async function copyFullDebugTrace() {
    if (!debugTrace || !navigator.clipboard) return;
    debugTraceCopyMessage = '';
    try {
      await navigator.clipboard.writeText(JSON.stringify(
        buildDebugTraceExport($currentProjectId, $currentChatId, debugTraceMessage, debugTrace),
        null,
        2,
      ));
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
      if (result.summary_path) {
        await refreshExplorerAfterMutation(pid, getParentPath(result.summary_path));
      }
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
    if (isReadOnlyMutationTarget(path)) {
      saveStatus = isSystemManagedPath(path)
        ? '시스템 파일은 직접 수정할 수 없습니다.'
        : 'Clean Room은 직접 수정할 수 없습니다.';
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
      await refreshExplorerAfterMutation(pid, getParentPath(path));
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
    if (!pid || fileActionBusy) return;
    const validation = validateNewFolderName(newFolderName);
    if (!validation.ok) {
      fileActionMessage = validation.message;
      return;
    }

    const folderName = validation.name;
    const targetDir = creatingFolderParentPath || getExplorerTargetDir();
    if (isReadOnlyMutationTarget(targetDir)) {
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

  function triggerUpload(input?: HTMLInputElement) {
    activeSideTab = 'files';
    uploadTargetDir = getExplorerTargetDir();
    if (isReadOnlyMutationTarget(uploadTargetDir)) {
      fileActionMessage = 'Clean Room에는 직접 업로드할 수 없습니다.';
      return;
    }
    fileActionMessage = '';
    input?.click();
  }

  async function uploadSelectedFiles(selectedFiles: File[], targetDir: string) {
    const pid = $currentProjectId;
    if (!pid || selectedFiles.length === 0 || fileActionBusy) return;
    if (isReadOnlyMutationTarget(targetDir)) {
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
    if (!hasDraggedFiles(event.dataTransfer?.types)) return;
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
    if (!hasDraggedFiles(event.dataTransfer?.types)) return;
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
    if (isReadOnlyMutationTarget(path)) {
      saveStatus = isSystemManagedPath(path)
        ? '시스템 파일은 직접 수정할 수 없습니다.'
        : 'Clean Room은 직접 수정할 수 없습니다.';
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

    const next = computePanelResize({
      panel: resizingPanel,
      deltaX: event.clientX - resizeStartX,
      workspaceWidth: getWorkspaceWidth(),
      filePanelWidth,
      chatPanelWidth,
      resizeStartFileWidth,
      resizeStartChatWidth,
    });
    filePanelWidth = next.filePanelWidth;
    chatPanelWidth = next.chatPanelWidth;
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
      await expandFolder(pid, node, getDirectoryLoadOptions());
    } else {
      const reselectingCurrentHtml = node.path === $selectedFilePath && isHtmlFile(node.path, $fileLanguage);
      if (shouldConfirmDiscardUnsaved(node.path, $selectedFilePath, hasUnsavedChanges()) &&
        !confirm('저장하지 않은 변경사항을 버리고 다른 파일을 여시겠습니까?')) {
        return;
      }
      await loadFileContent(pid, node.path);
      if (reselectingCurrentHtml) refreshHtmlPreview();
    }
  }

  async function handleLoadMoreDirectory(path: string) {
    const pid = $currentProjectId;
    if (!pid) return;
    await loadMoreDirectory(pid, path, getDirectoryLoadOptions());
    updateFileListViewport();
  }

  async function handleSearchResultClick(item: FileSearchItem) {
    const pid = $currentProjectId;
    if (!pid) return;
    fileActionMessage = '';
    const node: TreeNode = buildFocusedSearchNode(item);
    focusedExplorerNode = node;
    if (isDirectorySearchResult(item)) {
      activeSideTab = 'files';
      await loadDirectory(pid, item.path, { ...getDirectoryLoadOptions(), force: true });
      return;
    }
    if (shouldConfirmDiscardUnsaved(item.path, $selectedFilePath, hasUnsavedChanges()) &&
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
  <WorkspaceTopBar
    {projectTitle}
    {projectRuntimeMode}
    {projectContainerStatus}
    runtimeModeLabel={getRuntimeModeLabel()}
    {previewUrl}
    {deployBusy}
    {deployMessage}
    {developerMode}
    userName={$user?.name}
    onBack={() => push('/projects')}
    onDeployToggle={handleDeployToggle}
    onDeveloperModeChange={handleDeveloperModeChange}
  />

  <div class="workspace" class:resizing={resizingPanel !== null} bind:this={workspaceElement}>
    <WorkspaceSidePanel
      width={filePanelWidth}
      projectId={$currentProjectId}
      {activeSideTab}
      sidePanelTabs={SIDE_PANEL_TABS}
      sidePanelTitle={getSidePanelTitle()}
      toolCatalog={TOOL_CATALOG}
      {skills}
      {skillsLoading}
      {skillsError}
      {fileActionBusy}
      {fileActionMessage}
      {fileSearchQuery}
      {fileSearchLoading}
      {fileSearchMessage}
      {fileSearchResults}
      {draggingFiles}
      {creatingFolder}
      {creatingFolderParentPath}
      {newFolderName}
      virtualRows={getVirtualExplorerRows()}
      fileTreeIsEmpty={$fileTree.length === 0}
      rootHasMore={Boolean(getModeFolderCache()['/']?.has_more)}
      folderCache={getModeFolderCache()}
      selectedFilePath={$selectedFilePath}
      {focusedExplorerNode}
      explorerTargetReadOnly={isExplorerTargetReadOnly()}
      onActiveSideTabChange={(tab) => { activeSideTab = tab; }}
      onBeginCreateFolder={beginCreateFolder}
      onTriggerUpload={triggerUpload}
      onUploadChange={handleUploadChange}
      onFileSearchInput={handleFileSearchInput}
      onFileListElementChange={(element) => {
        fileListElement = element;
        updateFileListViewport();
      }}
      onFileListScroll={updateFileListViewport}
      onFileDragOver={handleFileDragOver}
      onFileDragLeave={handleFileDragLeave}
      onFileDrop={handleFileDrop}
      onNewFolderNameChange={(value) => { newFolderName = value; }}
      onCreateFolderKeydown={handleCreateFolderKeydown}
      onSubmitCreateFolder={submitCreateFolder}
      onCancelCreateFolder={cancelCreateFolder}
      onSearchResultClick={handleSearchResultClick}
      onLoadMoreDirectory={handleLoadMoreDirectory}
      onNodeClick={handleNodeClick}
      {getRoomLabel}
      {getPathBadge}
      {getDisplayPath}
      {isCleanRoomPath}
    />

    <button
      type="button"
      class="panel-resizer file-resizer"
      class:active={resizingPanel === 'file'}
      aria-label="폴더 패널 너비 조절"
      title="폴더 패널 너비 조절"
      onpointerdown={(event) => beginPanelResize('file', event)}
    ></button>

    {#if activeSideTab === 'mail'}
      <WorkspaceMailShell
        projectId={$currentProjectId}
        onMailContextChange={(context) => {
          currentMailContext = context;
        }}
        onAskWithMail={(text) => {
          inputText = text;
        }}
      />
    {:else}
      <FileViewerPanel
        selectedFilePath={$selectedFilePath}
        fileLanguage={$fileLanguage}
        fileContent={$fileContent}
        fileLoading={$fileLoading}
        {activeViewerTab}
        hasUnsavedChanges={hasUnsavedChanges()}
        {externalFileChanged}
        {markdownPreviewHtml}
        {highlightedCodeHtml}
        {htmlPreviewKey}
        {htmlPreviewContent}
        {htmlPreviewReady}
        {csvParseError}
        {csvPreviewRows}
        {csvRows}
        {editorContent}
        {savingFile}
        {saveStatus}
        onViewerTabClick={handleViewerTabClick}
        onRefreshHtmlPreview={refreshHtmlPreview}
        onCsvCellInput={handleCsvCellInput}
        onReloadCurrentFile={handleReloadCurrentFile}
        onRevertFile={handleRevertFile}
        onSaveFile={handleSaveFile}
        onEditorChange={(value) => { editorContent = value; saveStatus = ''; }}
        onEditorSelectionChange={(selection) => { editorSelection = selection; }}
      />
    {/if}

    <button
      type="button"
      class="panel-resizer chat-resizer"
      class:active={resizingPanel === 'chat'}
      aria-label="채팅 패널 너비 조절"
      title="채팅 패널 너비 조절"
      onpointerdown={(event) => beginPanelResize('chat', event)}
    ></button>

    <WorkspaceChatPanel
      width={chatPanelWidth}
      {showChatList}
      agentStatus={$agentStatus}
      planMode={$planMode}
      {planModeRequested}
      {debugMode}
      {summarizingChat}
      streaming={$streaming}
      {chatActionMessage}
      openMailContext={buildOpenMailContext()}
      chatSessions={$chatSessions}
      currentChatId={$currentChatId}
      messages={$messages}
      {inputText}
      onShowChatListChange={(value) => { showChatList = value; }}
      onPlanModeRequestedChange={(value) => { planModeRequested = value; }}
      onDebugModeChange={(value) => {
        debugMode = value;
        handleDebugModeChange();
      }}
      onInputTextChange={(value) => { inputText = value; }}
      onSelectChat={handleSelectChat}
      onDeleteChat={handleDeleteChat}
      onNewChat={handleNewChat}
      onSend={handleSend}
      onApprovePlan={handleApprovePlan}
      onRejectPlan={handleRejectPlan}
      onSummarizeChat={handleSummarizeChat}
      onOpenMailWorkbench={() => { activeSideTab = 'mail'; }}
      onMessagesElementChange={(element) => { chatContainer = element; }}
      renderChatMarkdown={renderWorkspaceChatMarkdown}
      formatToolStepContent={formatWorkspaceToolStep}
      {isDebugInspectable}
      onOpenDebugTrace={openDebugTrace}
      onDebugMessageKeydown={handleDebugMessageKeydown}
    />
  </div>
</div>

{#if debugTraceOpen}
  <DebugTraceModal
    {debugTraceLoading}
    {debugTraceError}
    {debugTrace}
    {debugTraceMessage}
    {debugPayloadView}
    {debugTraceCopyMessage}
    onClose={closeDebugTrace}
    onPayloadViewChange={(view) => { debugPayloadView = view; }}
    onCopyFullDebugTrace={copyFullDebugTrace}
    onCopyDebugPayload={copyDebugPayload}
    {debugEventLabel}
    {debugPayloadSections}
    {highlightDebugPayload}
  />
{/if}

<style>
  .layout { height: 100vh; display: flex; flex-direction: column; background: var(--color-bg); color: var(--color-text); }

  .workspace { flex: 1; display: flex; overflow: hidden; }
  .workspace.resizing { cursor: col-resize; user-select: none; }

  .panel-resizer { position: relative; z-index: 5; flex: 0 0 8px; margin: 0 -4px; border: 0; padding: 0; background: transparent; cursor: col-resize; }
  .panel-resizer::before { content: ""; position: absolute; top: 0; bottom: 0; left: 3px; width: 1px; background: var(--color-border); transition: background 0.12s ease, width 0.12s ease, left 0.12s ease; }
  .panel-resizer:hover::before,
  .panel-resizer.active::before { left: 2px; width: 3px; background: var(--color-accent); }
  .panel-resizer:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  :global(body.resizing-columns) { cursor: col-resize; user-select: none; }

</style>

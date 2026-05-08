<script lang="ts">
  import { FolderPlus, Upload } from 'lucide-svelte';
  import type { FileSearchItem, FolderCacheEntry, TreeNode } from '../stores/files';
  import ActivityRail from './ActivityRail.svelte';
  import WorkspaceFileExplorer from './WorkspaceFileExplorer.svelte';
  import WorkspaceSideCatalog from './WorkspaceSideCatalog.svelte';
  import type {
    SidePanelTab,
    SidePanelTabItem,
    SkillResponse,
    ToolCatalogItem,
    VirtualRows,
  } from './workspaceSidePanelTypes';

  let {
    width,
    activeSideTab,
    sidePanelTabs,
    sidePanelTitle,
    toolCatalog,
    skills,
    skillsLoading,
    skillsError,
    fileActionBusy,
    fileActionMessage,
    fileSearchQuery,
    fileSearchLoading,
    fileSearchMessage,
    fileSearchResults,
    draggingFiles,
    creatingFolder,
    creatingFolderParentPath,
    newFolderName,
    virtualRows,
    fileTreeIsEmpty,
    rootHasMore,
    folderCache,
    selectedFilePath,
    focusedExplorerNode,
    explorerTargetReadOnly,
    onActiveSideTabChange,
    onBeginCreateFolder,
    onTriggerUpload,
    onUploadChange,
    onFileSearchInput,
    onFileListElementChange,
    onFileListScroll,
    onFileDragOver,
    onFileDragLeave,
    onFileDrop,
    onNewFolderNameChange,
    onCreateFolderKeydown,
    onSubmitCreateFolder,
    onCancelCreateFolder,
    onSearchResultClick,
    onLoadMoreDirectory,
    onNodeClick,
    getDisplayPath,
    getRoomLabel,
    getPathBadge,
    isCleanRoomPath,
  }: {
    width: number;
    activeSideTab: SidePanelTab;
    sidePanelTabs: SidePanelTabItem[];
    sidePanelTitle: string;
    toolCatalog: ToolCatalogItem[];
    skills: SkillResponse[];
    skillsLoading: boolean;
    skillsError: string;
    fileActionBusy: boolean;
    fileActionMessage: string;
    fileSearchQuery: string;
    fileSearchLoading: boolean;
    fileSearchMessage: string;
    fileSearchResults: FileSearchItem[];
    draggingFiles: boolean;
    creatingFolder: boolean;
    creatingFolderParentPath: string;
    newFolderName: string;
    virtualRows: VirtualRows;
    fileTreeIsEmpty: boolean;
    rootHasMore: boolean;
    folderCache: Record<string, FolderCacheEntry>;
    selectedFilePath: string | null;
    focusedExplorerNode: TreeNode | null;
    explorerTargetReadOnly: boolean;
    onActiveSideTabChange: (tab: SidePanelTab) => void;
    onBeginCreateFolder: () => void;
    onTriggerUpload: (input: HTMLInputElement | undefined) => void;
    onUploadChange: (event: Event) => void;
    onFileSearchInput: (value: string) => void;
    onFileListElementChange: (element: HTMLDivElement | undefined) => void;
    onFileListScroll: () => void;
    onFileDragOver: (event: DragEvent, node?: TreeNode) => void;
    onFileDragLeave: (event: DragEvent) => void;
    onFileDrop: (event: DragEvent, node?: TreeNode) => void;
    onNewFolderNameChange: (value: string) => void;
    onCreateFolderKeydown: (event: KeyboardEvent) => void;
    onSubmitCreateFolder: () => void;
    onCancelCreateFolder: () => void;
    onSearchResultClick: (item: FileSearchItem) => void;
    onLoadMoreDirectory: (path: string) => void;
    onNodeClick: (node: TreeNode) => void;
    getDisplayPath: (path: string | null | undefined) => string;
    getRoomLabel: (room: string | null | undefined) => string;
    getPathBadge: (path: string | null) => string | null;
    isCleanRoomPath: (path: string | null) => boolean;
  } = $props();

  let uploadInput: HTMLInputElement | undefined = $state(undefined);
</script>

<div class="panel file-panel" style="width: {width}px">
  <ActivityRail
    {activeSideTab}
    {sidePanelTabs}
    {onActiveSideTabChange}
  />

  <div class="side-panel-shell">
    <div class="side-panel-header">
      <span class="side-panel-title">{sidePanelTitle}</span>
      {#if activeSideTab === 'files'}
        <button
          type="button"
          class="side-icon-btn"
          title="새 폴더"
          aria-label="새 폴더"
          disabled={fileActionBusy || explorerTargetReadOnly}
          onclick={onBeginCreateFolder}
        >
          <FolderPlus size={15} />
        </button>
        <button
          type="button"
          class="side-icon-btn"
          title="파일 업로드"
          aria-label="파일 업로드"
          disabled={fileActionBusy || explorerTargetReadOnly}
          onclick={() => onTriggerUpload(uploadInput)}
        >
          <Upload size={15} />
        </button>
        <input
          bind:this={uploadInput}
          class="hidden-file-input"
          type="file"
          multiple
          onchange={onUploadChange}
        />
      {/if}
    </div>
    {#if activeSideTab === 'files'}
      <WorkspaceFileExplorer
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
        {virtualRows}
        {fileTreeIsEmpty}
        {rootHasMore}
        {folderCache}
        {selectedFilePath}
        {focusedExplorerNode}
        {onFileSearchInput}
        {onFileListElementChange}
        {onFileListScroll}
        {onFileDragOver}
        {onFileDragLeave}
        {onFileDrop}
        {onNewFolderNameChange}
        {onCreateFolderKeydown}
        {onSubmitCreateFolder}
        {onCancelCreateFolder}
        {onSearchResultClick}
        {onLoadMoreDirectory}
        {onNodeClick}
        {getDisplayPath}
        {getRoomLabel}
        {getPathBadge}
        {isCleanRoomPath}
      />
    {:else}
      <WorkspaceSideCatalog
        {activeSideTab}
        {skills}
        {skillsLoading}
        {skillsError}
        {toolCatalog}
      />
    {/if}
  </div>
</div>

<style>
  .panel { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); background: var(--color-surface); }
  .file-panel { flex: 0 0 auto; flex-direction: row; }
  .side-panel-shell { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--color-sidebar); }
  .side-panel-header { flex-shrink: 0; display: flex; align-items: center; gap: 0.35rem; min-height: 40px; padding: 0.35rem 0.5rem 0.35rem 0.75rem; border-bottom: 1px solid var(--color-border); background: var(--color-sidebar); color: var(--color-text); font-size: 0.75rem; font-weight: 700; letter-spacing: 0; }
  .side-panel-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-icon-btn { width: 28px; height: 28px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-muted); cursor: pointer; }
  .side-icon-btn:hover:not(:disabled) { border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
  .side-icon-btn:disabled { cursor: default; opacity: 0.45; }
  .hidden-file-input { display: none; }
</style>

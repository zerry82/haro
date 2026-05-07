<script lang="ts">
  import { Lock, Search } from 'lucide-svelte';
  import type { FileSearchItem, TreeNode } from '../stores/files';
  import type { FileExplorerProps } from './workspaceSidePanelTypes';

  let {
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
    getRoomLabel,
    getPathBadge,
    isCleanRoomPath,
  }: FileExplorerProps = $props();

  let fileListElement: HTMLDivElement | undefined = $state(undefined);

  $effect(() => {
    onFileListElementChange(fileListElement);
  });

  function handleSearchInput(event: Event) {
    onFileSearchInput((event.currentTarget as HTMLInputElement).value);
  }

  function handleNewFolderNameInput(event: Event) {
    onNewFolderNameChange((event.currentTarget as HTMLInputElement).value);
  }
</script>

{#if fileActionMessage}
  <div class="file-action-message">{fileActionMessage}</div>
{/if}
<div class="file-search">
  <Search size={14} />
  <input
    type="search"
    placeholder="파일명/요약 검색"
    value={fileSearchQuery}
    oninput={handleSearchInput}
  />
</div>
<div
  class="file-list"
  class:dragging={draggingFiles}
  role="region"
  aria-label="파일 탐색기"
  bind:this={fileListElement}
  onscroll={onFileListScroll}
  ondragover={(event) => onFileDragOver(event)}
  ondragleave={onFileDragLeave}
  ondrop={(event) => onFileDrop(event)}
>
  {#snippet renderNewFolderRow(depth: number)}
    <div class="new-folder-row" style="margin-left: {depth * 0.75}rem">
      <input
        class="new-folder-input"
        type="text"
        placeholder="새 폴더 이름"
        value={newFolderName}
        disabled={fileActionBusy}
        oninput={handleNewFolderNameInput}
        onkeydown={onCreateFolderKeydown}
      />
      <button type="button" class="new-folder-action" disabled={fileActionBusy} onclick={onSubmitCreateFolder}>생성</button>
      <button type="button" class="new-folder-action ghost" disabled={fileActionBusy} onclick={onCancelCreateFolder}>취소</button>
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
            onclick={() => onSearchResultClick(item)}
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
    <div class="file-virtual-spacer" style="height: {virtualRows.totalHeight}px">
      <div class="file-virtual-window" style="transform: translateY({virtualRows.translateY}px)">
        {#each virtualRows.rows as row (row.key)}
          {#if row.kind === 'new-folder'}
            {@render renderNewFolderRow(row.depth)}
          {:else if row.kind === 'load-more'}
            <button
              class="file-load-more"
              type="button"
              style="padding-left: {0.5 + row.depth * 0.75}rem"
              disabled={folderCache[row.path]?.loading}
              onclick={() => onLoadMoreDirectory(row.path)}
            >
              {folderCache[row.path]?.loading ? '불러오는 중...' : '더 보기'}
            </button>
          {:else}
            <button
              class="file-item"
              class:active={selectedFilePath === row.node.path}
              class:focused={focusedExplorerNode?.path === row.node.path}
              class:readonly={isCleanRoomPath(row.node.path)}
              style="padding-left: {0.5 + row.depth * 0.75}rem"
              ondragover={(event) => onFileDragOver(event, row.node)}
              ondrop={(event) => onFileDrop(event, row.node)}
              onclick={() => onNodeClick(row.node)}
            >
              <span class="file-label">
                {#if isCleanRoomPath(row.node.path)}
                  <Lock size={13} strokeWidth={2} />
                {/if}
                <span class="file-icon">
                  {#if row.node.type === 'directory'}
                    {row.node.expanded ? '📂' : '📁'}
                  {:else}
                    📄
                  {/if}
                </span>
                <span class="file-name">{row.node.name}</span>
                {#if getPathBadge(row.node.path)}
                  <span class="path-badge">{getPathBadge(row.node.path)}</span>
                {/if}
              </span>
            </button>
          {/if}
        {/each}
      </div>
    </div>
    {#if fileTreeIsEmpty && !creatingFolder && !rootHasMore}
      <p class="empty">파일 없음</p>
    {/if}
  {/if}
</div>

<style>
  .file-action-message { flex-shrink: 0; margin: 0.35rem 0.4rem 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.35rem 0.45rem; font-size: 0.72rem; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-search { flex-shrink: 0; display: flex; align-items: center; gap: 0.35rem; margin: 0.35rem 0.4rem 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.25rem 0.4rem; }
  .file-search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--color-text); font: inherit; font-size: 0.76rem; }
  .file-search input::placeholder { color: var(--color-text-muted); }
  .file-list { flex: 1; overflow-y: auto; padding: 0.25rem; }
  .file-list.dragging { outline: 1px dashed var(--color-accent); outline-offset: -4px; background: var(--color-accent-soft); }
  .file-virtual-spacer { position: relative; min-height: 100%; }
  .file-virtual-window { position: absolute; top: 0; left: 0; right: 0; }
  .search-results { display: flex; flex-direction: column; gap: 0.3rem; padding: 0.15rem; }
  .search-result { width: 100%; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 0.45rem; text-align: left; cursor: pointer; font: inherit; }
  .search-result:hover { border-color: var(--color-info); background: var(--color-sidebar-strong); }
  .search-result-name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.78rem; font-weight: 700; }
  .search-result-path { display: block; margin-top: 0.16rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-muted); font-size: 0.66rem; }
  .search-result-meta { display: flex; flex-wrap: wrap; gap: 0.2rem; margin-top: 0.3rem; }
  .search-result-meta span { border-radius: 999px; background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.08rem 0.32rem; font-size: 0.62rem; }
  .search-result-snippet { display: -webkit-box; margin-top: 0.35rem; color: var(--color-text-muted); font-size: 0.68rem; line-height: 1.35; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .file-item { padding: 0.35rem 0.5rem; border-radius: var(--radius-sm); cursor: pointer; font-size: 0.8rem; background: transparent; border: none; color: var(--color-text); width: 100%; text-align: left; font-family: inherit; display: block; }
  .file-load-more { width: 100%; min-height: 30px; border: none; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-muted); cursor: pointer; font: inherit; font-size: 0.74rem; text-align: left; }
  .file-load-more:hover:not(:disabled) { background: var(--color-sidebar-strong); color: var(--color-info); }
  .file-load-more:disabled { cursor: default; opacity: 0.55; }
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
  .empty { color: var(--color-text-subtle); font-size: 0.8rem; text-align: center; padding: 1rem; }
</style>

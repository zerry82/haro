<script lang="ts">
  import CodeEditor from './CodeEditor.svelte';
  import {
    escapeHtml,
    getViewerContent,
    getViewerTabs,
    isCleanRoomPath,
    isCsvFile,
    isEditableTextFile,
    isHtmlFile,
    isMarkdownFile,
    isSystemManagedPath,
    type ViewerTab,
  } from '../lib/workspaceUtils';

  let {
    selectedFilePath,
    fileLanguage,
    fileContent,
    fileLoading,
    activeViewerTab,
    hasUnsavedChanges,
    externalFileChanged,
    markdownPreviewHtml,
    highlightedCodeHtml,
    htmlPreviewKey,
    htmlPreviewContent,
    htmlPreviewReady,
    csvParseError,
    csvPreviewRows,
    csvRows,
    editorContent,
    savingFile,
    saveStatus,
    onViewerTabClick,
    onRefreshHtmlPreview,
    onCsvCellInput,
    onReloadCurrentFile,
    onRevertFile,
    onSaveFile,
    onEditorChange,
  }: {
    selectedFilePath: string | null;
    fileLanguage: string;
    fileContent: string | null;
    fileLoading: boolean;
    activeViewerTab: ViewerTab;
    hasUnsavedChanges: boolean;
    externalFileChanged: boolean;
    markdownPreviewHtml: string;
    highlightedCodeHtml: string;
    htmlPreviewKey: string;
    htmlPreviewContent: string;
    htmlPreviewReady: boolean;
    csvParseError: string;
    csvPreviewRows: string[][];
    csvRows: string[][];
    editorContent: string;
    savingFile: boolean;
    saveStatus: string;
    onViewerTabClick: (tab: ViewerTab) => void;
    onRefreshHtmlPreview: () => void;
    onCsvCellInput: (rowIndex: number, cellIndex: number, event: Event) => void;
    onReloadCurrentFile: () => void;
    onRevertFile: () => void;
    onSaveFile: () => void;
    onEditorChange: (value: string) => void;
  } = $props();

  function isReadonlyPath(path: string | null) {
    return isCleanRoomPath(path) || isSystemManagedPath(path);
  }

  function readonlyMessage(path: string | null) {
    return isSystemManagedPath(path) ? '시스템 파일은 직접 수정할 수 없습니다.' : 'Clean Room은 직접 수정할 수 없습니다.';
  }
</script>

<div class="panel viewer-panel">
  <div class="panel-header viewer-header">
    <span class="viewer-title">{selectedFilePath || '파일을 선택하세요'}</span>
    {#if selectedFilePath !== null}
      <div class="viewer-tabs" role="tablist" aria-label="파일 보기 방식">
        {#each getViewerTabs(selectedFilePath, fileLanguage) as tab}
          <button
            type="button"
            class="viewer-tab"
            class:active={activeViewerTab === tab.id}
            role="tab"
            aria-selected={activeViewerTab === tab.id}
            onclick={() => onViewerTabClick(tab.id)}
          >
            {tab.label}{tab.id === 'editor' && hasUnsavedChanges ? ' *' : ''}
          </button>
        {/each}
      </div>
    {/if}
    <span class="viewer-status-spacer"></span>
    {#if hasUnsavedChanges}
      <span class="dirty-badge">수정됨</span>
    {/if}
    {#if externalFileChanged}
      <span class="external-badge">외부 변경 있음</span>
    {/if}
  </div>
  <div class="viewer-content">
    {#if fileContent !== null}
      {#if activeViewerTab === 'preview' && isCsvFile(selectedFilePath, fileLanguage)}
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
      {:else if activeViewerTab === 'preview' && isMarkdownFile(selectedFilePath, fileLanguage)}
        <div class="markdown-preview">{@html markdownPreviewHtml}</div>
      {:else if activeViewerTab === 'preview' && isHtmlFile(selectedFilePath, fileLanguage)}
        {#if htmlPreviewReady}
          {#key htmlPreviewKey}
            <div class="html-preview-frame">
              <button type="button" class="html-preview-refresh" onclick={onRefreshHtmlPreview}>새로고침</button>
              <iframe class="html-preview" sandbox="allow-scripts" srcdoc={htmlPreviewContent} title="HTML preview"></iframe>
            </div>
          {/key}
        {:else}
          <p class="empty loading">프리뷰 준비 중...</p>
        {/if}
      {:else if activeViewerTab === 'code'}
        <pre class="code-preview"><code class="hljs">{@html highlightedCodeHtml}</code></pre>
      {:else if activeViewerTab === 'editor' && isCsvFile(selectedFilePath, fileLanguage)}
        <div class="editor-pane">
          <div class="editor-toolbar">
            <span class="editor-status" class:dirty={hasUnsavedChanges} class:warning={externalFileChanged}>
              {#if isReadonlyPath(selectedFilePath)}
                {readonlyMessage(selectedFilePath)}
              {:else if externalFileChanged}
                외부 변경 있음
              {:else if hasUnsavedChanges}
                저장되지 않음
              {:else if saveStatus}
                {saveStatus}
              {:else}
                저장됨
              {/if}
            </span>
            <span class="spacer"></span>
            {#if externalFileChanged}
              <button type="button" class="editor-action" onclick={onReloadCurrentFile}>다시 불러오기</button>
            {/if}
            <button type="button" class="editor-action" onclick={onRevertFile} disabled={isReadonlyPath(selectedFilePath) || !hasUnsavedChanges || savingFile}>되돌리기</button>
            <button type="button" class="editor-save" onclick={onSaveFile} disabled={isReadonlyPath(selectedFilePath) || !hasUnsavedChanges || savingFile}>
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
                            disabled={isReadonlyPath(selectedFilePath)}
                            aria-label={`CSV ${rowIndex + 1}행 ${cellIndex + 1}열`}
                            oninput={(event) => onCsvCellInput(rowIndex, cellIndex, event)}
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
      {:else if activeViewerTab === 'editor' && isEditableTextFile(selectedFilePath, fileLanguage)}
        <div class="editor-pane">
          <div class="editor-toolbar">
            <span class="editor-status" class:dirty={hasUnsavedChanges} class:warning={externalFileChanged}>
              {#if isReadonlyPath(selectedFilePath)}
                {readonlyMessage(selectedFilePath)}
              {:else if externalFileChanged}
                외부 변경 있음
              {:else if hasUnsavedChanges}
                저장되지 않음
              {:else if saveStatus}
                {saveStatus}
              {:else}
                저장됨
              {/if}
            </span>
            <span class="spacer"></span>
            {#if externalFileChanged}
              <button type="button" class="editor-action" onclick={onReloadCurrentFile}>다시 불러오기</button>
            {/if}
            <button type="button" class="editor-action" onclick={onRevertFile} disabled={isReadonlyPath(selectedFilePath) || !hasUnsavedChanges || savingFile}>되돌리기</button>
            <button type="button" class="editor-save" onclick={onSaveFile} disabled={isReadonlyPath(selectedFilePath) || !hasUnsavedChanges || savingFile}>
              {savingFile ? '저장 중...' : '저장'}
            </button>
          </div>
          <div class="editor-body">
            <CodeEditor
              value={editorContent}
              language={fileLanguage}
              readonly={isReadonlyPath(selectedFilePath)}
              onchange={onEditorChange}
            />
          </div>
        </div>
      {:else}
        <pre class="code-preview"><code>{@html escapeHtml(getViewerContent(fileContent, selectedFilePath, fileLanguage, editorContent))}</code></pre>
      {/if}
    {:else}
      {#if fileLoading}
        <p class="empty loading">불러오는 중...</p>
      {:else}
        <p class="empty">좌측에서 파일을 선택하세요</p>
      {/if}
    {/if}
  </div>
</div>

<style>
  .panel { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); background: var(--color-surface); }
  .panel-header { padding: 0.6rem 1rem; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }
  .viewer-panel { flex: 1; min-width: 0; }
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
  .spacer { flex: 1; }
  .editor-action, .editor-save { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 0.3rem 0.65rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .editor-action { background: transparent; color: var(--color-text-muted); }
  .editor-action:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-accent-strong); background: var(--color-accent-soft); }
  .editor-action:disabled, .editor-save:disabled { cursor: default; opacity: 0.45; }
  .editor-save { border-color: var(--color-pink); background: var(--color-pink); color: #fff; font-weight: 700; }
  .editor-save:hover:not(:disabled) { filter: brightness(1.05); }
  .editor-body { flex: 1; min-height: 0; overflow: hidden; }
  .empty { color: var(--color-text-muted); font-size: 0.8rem; padding: 1rem; text-align: center; }
  .loading { opacity: 0.82; }
</style>

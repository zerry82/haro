<script lang="ts">
  import type { RuntimeMode } from '../lib/workspaceUtils';

  let {
    projectTitle,
    projectRuntimeMode,
    projectContainerStatus,
    runtimeModeLabel,
    previewUrl,
    deployBusy,
    deployMessage,
    userName,
    onBack,
    onDeployToggle,
  }: {
    projectTitle: string;
    projectRuntimeMode: RuntimeMode;
    projectContainerStatus: string;
    runtimeModeLabel: string;
    previewUrl: string;
    deployBusy: boolean;
    deployMessage: string;
    userName: string | null | undefined;
    onBack: () => void;
    onDeployToggle: () => void;
  } = $props();
</script>

<header class="top-bar">
  <button class="back-btn" onclick={onBack}>← 프로젝트</button>
  <span class="project-name">{projectTitle}</span>
  <span class="runtime-badge" class:deploy={projectRuntimeMode === 'deploy'}>{runtimeModeLabel}</span>
  <span class="container-badge" class:running={projectContainerStatus === 'running'}>{projectContainerStatus}</span>
  <button class="deploy-btn" onclick={onDeployToggle} disabled={deployBusy}>
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
  <span class="user-name">{userName}</span>
</header>

<style>
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
</style>

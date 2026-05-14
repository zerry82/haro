<script lang="ts">
  import { onMount } from 'svelte';
  import { RefreshCw } from 'lucide-svelte';
  import {
    loadMailAnalysis,
    loadMailStatus,
    type MailAnalysisResponse,
    type MailConnection,
    type MailRunSummary,
  } from '../stores/mail';

  let { projectId }: { projectId: string | null } = $props();

  let connection = $state<MailConnection | null>(null);
  let latestRun = $state<MailRunSummary | null>(null);
  let analysis = $state<MailAnalysisResponse | null>(null);
  let busy = $state(false);
  let message = $state('');
  let loadedProjectId = $state<string | null>(null);

  $effect(() => {
    if (projectId && projectId !== loadedProjectId) {
      loadedProjectId = projectId;
      void refreshStatus(projectId);
    }
  });

  onMount(() => {
    const handler = () => {
      void refreshStatus(projectId);
    };
    window.addEventListener('haro:mail-updated', handler);
    return () => window.removeEventListener('haro:mail-updated', handler);
  });

  async function refreshStatus(targetProjectId = projectId) {
    if (!targetProjectId || busy) return;
    busy = true;
    message = '';
    try {
      const status = await loadMailStatus(targetProjectId);
      connection = status.connection;
      latestRun = status.latest_run;
      analysis = latestRun?.id ? await loadMailAnalysis(targetProjectId, latestRun.id) : null;
    } catch (e: any) {
      message = e.message || '메일 상태를 불러오지 못했습니다.';
    } finally {
      busy = false;
    }
  }

  function connectionStatusLabel() {
    if (connection?.status === 'connected') return '연결됨';
    if (connection?.status === 'needs_oauth') return '연결 필요';
    return '연결 안 됨';
  }

  function runStatusLabel() {
    if (!latestRun) return '분석 전';
    if (latestRun.status === 'completed') return '완료';
    if (latestRun.status === 'failed') return '실패';
    return '진행 중';
  }

  function formatDateTime(value: string | null | undefined) {
    if (!value) return '없음';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }
</script>

<div class="mail-side">
  <section class="summary-section">
    <div class="section-head">
      <span>Gmail</span>
      <button type="button" title="메일 상태 갱신" disabled={busy} onclick={() => refreshStatus()}>
        <RefreshCw size={14} />
      </button>
    </div>
    <div class="status-card" class:connected={connection?.status === 'connected'}>
      <div class="status-row">
        <span class="status-dot" class:active={connection?.status === 'connected'}></span>
        <strong>{connectionStatusLabel()}</strong>
      </div>
      <dl>
        <div><dt>계정</dt><dd>{connection?.email || '-'}</dd></div>
        <div><dt>권한</dt><dd>읽기 전용</dd></div>
        <div><dt>수집</dt><dd>{formatDateTime(connection?.last_sync_at)}</dd></div>
      </dl>
    </div>
  </section>

  <section class="summary-section">
    <div class="section-title">최근 분석</div>
    <div class="metric-list">
      <div><span>상태</span><strong>{runStatusLabel()}</strong></div>
      <div><span>threads</span><strong>{analysis?.stats.thread_count || 0}</strong></div>
      <div><span>actions</span><strong>{analysis?.stats.extracted_action_count || 0}</strong></div>
      <div><span>due dates</span><strong>{analysis?.stats.due_date_count || 0}</strong></div>
    </div>
    {#if latestRun}
      <p class="muted">마지막 분석 {formatDateTime(latestRun.updated_at || latestRun.created_at)}</p>
    {/if}
  </section>

  <section class="summary-section">
    <div class="section-title">중앙 워크벤치</div>
    <div class="nav-hint">
      <span>메일 탐색</span>
      <span>설정</span>
      <span>통계</span>
    </div>
    <p class="muted">연결, 분석, 카테고리와 필터 편집은 중앙 설정 탭에서 진행합니다.</p>
  </section>

  {#if message}
    <div class="mail-message">{message}</div>
  {/if}
</div>

<style>
  .mail-side { flex: 1; overflow-y: auto; padding: 0.5rem; color: var(--color-text); }
  .summary-section { margin-bottom: 0.65rem; border-bottom: 1px solid var(--color-border-soft); padding-bottom: 0.65rem; }
  .section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem; color: var(--color-text-muted); font-size: 0.72rem; font-weight: 800; }
  .section-head button { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); cursor: pointer; }
  .section-head button:disabled { cursor: default; opacity: 0.5; }
  .section-title { margin-bottom: 0.4rem; color: var(--color-text-muted); font-size: 0.72rem; font-weight: 800; }
  .status-card { display: grid; gap: 0.45rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.5rem; }
  .status-card.connected { border-color: var(--color-success-soft); }
  .status-row { display: flex; align-items: center; gap: 0.35rem; font-size: 0.74rem; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-text-subtle); }
  .status-dot.active { background: var(--color-success); }
  dl { display: grid; gap: 0.35rem; margin: 0; }
  dl div, .metric-list div { display: flex; justify-content: space-between; gap: 0.5rem; min-width: 0; color: var(--color-text-muted); font-size: 0.68rem; }
  dt { color: var(--color-text-subtle); }
  dd { margin: 0; min-width: 0; overflow: hidden; color: var(--color-text); text-overflow: ellipsis; white-space: nowrap; }
  .metric-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.35rem; }
  .metric-list div { display: grid; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.45rem; }
  .metric-list strong { color: var(--color-text); font-size: 0.95rem; }
  .nav-hint { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .nav-hint span { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.18rem 0.4rem; font-size: 0.68rem; }
  .muted { margin: 0.4rem 0 0; color: var(--color-text-subtle); font-size: 0.68rem; line-height: 1.45; }
  .mail-message { border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.45rem; font-size: 0.72rem; }
</style>

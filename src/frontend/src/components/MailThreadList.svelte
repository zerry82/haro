<script lang="ts">
  import {
    countMailThreads,
    filterMailThreads,
    formatThreadDate,
    getThreadActions,
    getThreadDueDates,
    getThreadStructureStatus,
    getThreadWarnings,
    MAIL_THREAD_FILTERS,
    type MailThreadFilter,
  } from '../lib/mailThreadFilters';
  import type { MailThread } from '../stores/mail';

  let {
    threads,
    selectedThreadId,
    activeFilter,
    loading = false,
    onFilterChange,
    onSelectThread,
  }: {
    threads: MailThread[];
    selectedThreadId: string | null;
    activeFilter: MailThreadFilter;
    loading?: boolean;
    onFilterChange: (filter: MailThreadFilter) => void;
    onSelectThread: (thread: MailThread) => void;
  } = $props();

  const filteredThreads = $derived(filterMailThreads(threads, activeFilter));
</script>

<section class="thread-list-panel">
  <div class="filter-row">
    {#each MAIL_THREAD_FILTERS as filter}
      <button
        type="button"
        class:active={activeFilter === filter.id}
        onclick={() => onFilterChange(filter.id)}
      >
        <span>{filter.label}</span>
        <strong>{countMailThreads(threads, filter.id)}</strong>
      </button>
    {/each}
  </div>

  <div class="thread-list">
    {#if loading}
      <p class="empty">메일 목록을 불러오는 중입니다.</p>
    {:else if threads.length === 0}
      <p class="empty">최근 분석 완료 후 메일 목록이 표시됩니다.</p>
    {:else if filteredThreads.length === 0}
      <p class="empty">이 필터에 해당하는 메일이 없습니다.</p>
    {:else}
      {#each filteredThreads as thread}
        <button
          type="button"
          class="thread-row"
          class:selected={selectedThreadId === thread.id}
          onclick={() => onSelectThread(thread)}
        >
          <div class="row-top">
            <span class={`status-badge ${getThreadStructureStatus(thread)}`}>
              {getThreadStructureStatus(thread) === 'warning' ? '주의' : '좋음'}
            </span>
            <span class="category">{thread.category}</span>
            <time>{formatThreadDate(thread.received_at)}</time>
          </div>
          <strong title={thread.subject}>{thread.subject}</strong>
          <div class="sender" title={thread.sender}>{thread.sender}</div>
          <p>{thread.summary}</p>
          <div class="signals">
            <span>요청 {getThreadActions(thread).length}</span>
            <span>일정 {getThreadDueDates(thread).length}</span>
            <span>첨부 {thread.attachments.length}</span>
            {#if getThreadWarnings(thread).length}
              <span class="warning">경고 {getThreadWarnings(thread).length}</span>
            {/if}
          </div>
        </button>
      {/each}
    {/if}
  </div>
</section>

<style>
  .thread-list-panel { min-height: 0; display: flex; flex-direction: column; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); overflow: hidden; }
  .filter-row { display: flex; gap: 0.3rem; flex-wrap: wrap; border-bottom: 1px solid var(--color-border-soft); padding: 0.5rem; background: var(--color-sidebar); }
  .filter-row button { display: inline-flex; align-items: center; gap: 0.25rem; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.28rem 0.45rem; font: inherit; font-size: 0.68rem; cursor: pointer; }
  .filter-row button.active { border-color: var(--color-pink); background: var(--color-pink-soft); color: var(--color-text); font-weight: 700; }
  .filter-row strong { color: var(--color-text); }
  .thread-list { flex: 1; min-height: 0; overflow: auto; display: grid; align-content: start; }
  .thread-row { display: grid; gap: 0.28rem; width: 100%; border: 0; border-bottom: 1px solid var(--color-border-soft); background: var(--color-surface); color: var(--color-text); padding: 0.65rem; text-align: left; cursor: pointer; }
  .thread-row:hover { background: var(--color-sidebar-strong); }
  .thread-row.selected { background: var(--color-pink-soft); box-shadow: inset 3px 0 0 var(--color-pink); }
  .row-top { display: flex; align-items: center; gap: 0.35rem; min-width: 0; color: var(--color-text-muted); font-size: 0.68rem; }
  .row-top time { margin-left: auto; flex-shrink: 0; color: var(--color-text-subtle); }
  .status-badge, .category { flex-shrink: 0; border-radius: var(--radius-sm); padding: 0.12rem 0.35rem; font-size: 0.66rem; }
  .status-badge.good { background: var(--color-success-soft); color: var(--color-success); }
  .status-badge.warning { background: var(--color-warning-soft); color: #92400e; }
  .category { max-width: 120px; overflow: hidden; background: var(--color-sidebar-strong); color: var(--color-text-muted); text-overflow: ellipsis; white-space: nowrap; }
  .thread-row strong, .sender, .thread-row p { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .thread-row strong { font-size: 0.82rem; }
  .sender { color: var(--color-text-muted); font-size: 0.72rem; }
  .thread-row p { margin: 0; color: var(--color-text-muted); font-size: 0.74rem; }
  .signals { display: flex; gap: 0.35rem; flex-wrap: wrap; color: var(--color-text-subtle); font-size: 0.68rem; }
  .signals span { border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.12rem 0.35rem; }
  .signals .warning { color: #92400e; }
  .empty { margin: 0; color: var(--color-text-subtle); font-size: 0.78rem; padding: 1rem; text-align: center; }

  @media (max-width: 1180px) {
    .thread-list-panel { max-height: 420px; }
  }

  @media (max-width: 760px) {
    .row-top { flex-wrap: wrap; }
    .row-top time { width: 100%; margin-left: 0; }
    .category { max-width: 100%; }
  }
</style>

<script lang="ts">
  import {
    formatThreadDate,
    getThreadActions,
    getThreadDueDates,
    getThreadStructureStatus,
    getThreadWarnings,
  } from '../lib/mailThreadFilters';
  import type { MailThread } from '../stores/mail';

  let {
    thread,
    loading = false,
    onAskWithThread,
  }: {
    thread: MailThread | null;
    loading?: boolean;
    onAskWithThread?: (thread: MailThread) => void;
  } = $props();

  let bodyView = $state<'original' | 'text'>('original');

  const actions = $derived(thread ? getThreadActions(thread) : []);
  const dueDates = $derived(thread ? getThreadDueDates(thread) : []);
  const warnings = $derived(thread ? getThreadWarnings(thread) : []);
  const bodySourceLabel = $derived(thread ? labelBodySource(thread.body_source) : '');
  const attachmentSourceLabel = $derived(thread ? labelAttachmentSource(thread.attachment_source) : '');
  const contextSourceLabel = $derived(thread ? labelContextSource(thread.metadata?.primary_context_source) : '');
  const hasOriginalBody = $derived(Boolean(thread?.body_html));
  const effectiveBodyView = $derived(hasOriginalBody && bodyView === 'original' ? 'original' : 'text');

  function labelBodySource(source?: string) {
    if (source === 'snapshot') return 'snapshot 본문';
    if (source === 'staging_sample') return '본문 일부';
    return '';
  }

  function labelAttachmentSource(source?: string) {
    if (source === 'snapshot') return 'snapshot 파일';
    if (source === 'staging') return '분석 파일';
    return '';
  }

  function labelContextSource(source?: string) {
    if (source === 'attachment') return '첨부 중심';
    if (source === 'body_attachment') return '본문+첨부';
    if (source === 'body') return '본문 중심';
    return '';
  }

  function labelExtractStatus(status?: string) {
    if (status === 'summarized') return '요약됨';
    if (status === 'supported_pending') return '추출 대기';
    if (status === 'metadata_only') return '메타데이터만';
    if (status === 'unsupported_scanned_pdf') return '스캔 PDF';
    if (status === 'failed') return '추출 실패';
    if (status === 'skipped') return '제외되어 건너뜀';
    return status || '확인 안 됨';
  }

  function labelDownloadStatus(status?: string) {
    if (status === 'downloaded') return '저장됨';
    if (status === 'cached') return '저장됨';
    if (status === 'missing_ref') return '다운로드 참조 없음';
    if (status === 'skipped_excluded') return '제외되어 저장 안 함';
    return status || '저장 전';
  }

  function profileSummary(profile?: Record<string, any>) {
    if (!profile?.kind) return '';
    if (profile.kind === 'csv') return `CSV · 컬럼 ${profile.columns?.length || 0}개 · 샘플 ${profile.row_count_sampled || 0}행`;
    if (profile.kind === 'excel') return `Excel · 시트 ${profile.sheets?.length || 0}개`;
    if (profile.kind === 'pdf') return `PDF · ${profile.page_count || 0}페이지`;
    if (profile.kind === 'image') return '이미지 분석';
    if (profile.kind === 'text') return `텍스트 · ${profile.line_count || 0}줄`;
    return String(profile.kind);
  }
</script>

<section class="detail-panel">
  {#if loading}
    <p class="empty">메일 상세를 불러오는 중입니다.</p>
  {:else if !thread}
    <div class="empty-state">
      <h3>메일을 선택하세요</h3>
      <p>왼쪽 목록에서 thread를 선택하면 구조화 요약, 요청사항, 일정, 첨부파일이 표시됩니다.</p>
    </div>
  {:else}
    <div class="detail-header">
      <div>
        <div class="badge-row">
          <span class={`status-badge ${getThreadStructureStatus(thread)}`}>
            {getThreadStructureStatus(thread) === 'warning' ? '주의 필요' : '구조화 좋음'}
          </span>
          <span class="category">{thread.category}</span>
          {#if contextSourceLabel}
            <span class="context-badge" class:attachment-context={thread.metadata?.primary_context_source === 'attachment'}>
              {contextSourceLabel}
            </span>
          {/if}
        </div>
        <h3>{thread.subject}</h3>
      </div>
      <div class="header-actions">
        <time>{formatThreadDate(thread.received_at)}</time>
        {#if onAskWithThread}
          <button type="button" onclick={() => onAskWithThread?.(thread)}>이 메일 기준 질문</button>
        {/if}
      </div>
    </div>

    <dl class="meta-grid">
      <div><dt>보낸사람</dt><dd title={thread.sender}>{thread.sender}</dd></div>
      <div><dt>받은사람</dt><dd title={thread.recipients.join(', ')}>{thread.recipients.join(', ') || '-'}</dd></div>
      <div><dt>결정</dt><dd>{thread.inclusion_decision}</dd></div>
      <div><dt>confidence</dt><dd>{thread.metadata?.confidence ?? '-'}</dd></div>
    </dl>

    <section class="detail-section">
      <h4>요약</h4>
      <p>{thread.summary || '요약 없음'}</p>
    </section>

    <section class="detail-section">
      <div class="section-title-row">
        <h4>본문</h4>
        <div class="section-actions">
          {#if hasOriginalBody}
            <div class="body-toggle" aria-label="본문 보기 방식">
              <button
                type="button"
                class:active={effectiveBodyView === 'original'}
                onclick={() => (bodyView = 'original')}
              >
                원본
              </button>
              <button
                type="button"
                class:active={effectiveBodyView === 'text'}
                onclick={() => (bodyView = 'text')}
              >
                텍스트
              </button>
            </div>
          {/if}
          {#if bodySourceLabel}
            <span class="source-badge">{bodySourceLabel}</span>
          {/if}
        </div>
      </div>
      {#if effectiveBodyView === 'original' && thread.body_html}
        {#if thread.body_html_truncated}
          <p class="muted body-note">긴 HTML 메일은 저장된 snapshot 한도까지 표시됩니다.</p>
        {/if}
        <iframe class="body-frame" title="메일 원본 렌더러" sandbox="" srcdoc={thread.body_html}></iframe>
      {:else if thread.body}
        {#if thread.body_truncated}
          <p class="muted body-note">긴 메일은 저장된 snapshot 한도까지 표시됩니다.</p>
        {/if}
        <pre class="body-block">{thread.body}</pre>
      {:else}
        <p class="muted">저장된 본문이 없습니다.</p>
      {/if}
    </section>

    <section class="detail-section">
      <h4>요청사항</h4>
      {#if actions.length}
        <div class="item-list">
          {#each actions as action}
            <article>
              <strong>{action.text || action.title || '요청사항'}</strong>
              <span>{action.owner ? `담당: ${action.owner}` : '담당 미정'}</span>
              {#if action.due_date}<span>마감: {action.due_date}</span>{/if}
            </article>
          {/each}
        </div>
      {:else}
        <p class="muted">추출된 요청사항이 없습니다.</p>
      {/if}
    </section>

    <section class="detail-section">
      <h4>일정</h4>
      {#if dueDates.length}
        <div class="item-list">
          {#each dueDates as dueDate}
            <article>
              <strong>{dueDate.date || '날짜 미정'}</strong>
              <span>{dueDate.text || dueDate.description || '일정 표현'}</span>
            </article>
          {/each}
        </div>
      {:else}
        <p class="muted">추출된 일정이 없습니다.</p>
      {/if}
    </section>

    <section class="detail-section">
      <div class="section-title-row">
        <h4>첨부파일</h4>
        <div class="section-actions">
          {#if thread.metadata?.primary_context_source === 'attachment'}
            <span class="source-badge primary-source">이 메일의 핵심 맥락은 첨부파일에서 추출됨</span>
          {/if}
          {#if attachmentSourceLabel}
            <span class="source-badge">{attachmentSourceLabel}</span>
          {/if}
        </div>
      </div>
      {#if thread.attachments.length}
        <div class="attachment-list">
          {#each thread.attachments as attachment}
            <article>
              <div>
                <strong title={attachment.title}>{attachment.title}</strong>
                <span>{attachment.extension || 'file'} · {attachment.size_bytes.toLocaleString()} bytes</span>
                <span>{labelDownloadStatus(attachment.download_status)}</span>
                <span>{labelExtractStatus(attachment.extract_status)}</span>
              </div>
              {#if attachment.inbox_path}
                <p class="path-text">{attachment.inbox_path}</p>
              {/if}
              {#if profileSummary(attachment.content_profile)}
                <p class="profile-text">{profileSummary(attachment.content_profile)}</p>
              {/if}
              {#if attachment.summary}
                <p>{attachment.summary}</p>
                {#if attachment.key_points?.length}
                  <ul class="key-point-list">
                    {#each attachment.key_points as point}
                      <li>{point}</li>
                    {/each}
                  </ul>
                {/if}
              {:else}
                <p class="muted">메타데이터만 수집됨</p>
              {/if}
              {#if attachment.error_reason}
                <p class="error-text">{attachment.error_reason}</p>
              {/if}
            </article>
          {/each}
        </div>
      {:else}
        <p class="muted">첨부파일이 없습니다.</p>
      {/if}
    </section>

    {#if warnings.length}
      <section class="detail-section warning-section">
        <h4>구조화 주의 이유</h4>
        <ul>
          {#each warnings as warning}
            <li>{warning}</li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</section>

<style>
  .detail-panel { min-height: 0; overflow: auto; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.9rem; }
  .detail-header { display: flex; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--color-border-soft); padding-bottom: 0.8rem; }
  .detail-header h3 { margin: 0.35rem 0 0; color: var(--color-text); font-size: 1.05rem; line-height: 1.35; }
  .header-actions { display: grid; justify-items: end; gap: 0.45rem; flex-shrink: 0; }
  .detail-header time { color: var(--color-text-muted); font-size: 0.72rem; }
  .header-actions button { border: 1px solid var(--color-pink); border-radius: var(--radius-sm); background: var(--color-pink-soft); color: var(--color-text); padding: 0.3rem 0.5rem; font: inherit; font-size: 0.72rem; font-weight: 700; cursor: pointer; }
  .badge-row { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .status-badge, .category, .context-badge { border-radius: var(--radius-sm); padding: 0.16rem 0.45rem; font-size: 0.68rem; font-weight: 700; }
  .status-badge.good { background: var(--color-success-soft); color: var(--color-success); }
  .status-badge.warning { background: var(--color-warning-soft); color: #92400e; }
  .category { background: var(--color-sidebar-strong); color: var(--color-text-muted); }
  .context-badge { background: var(--color-info-soft); color: var(--color-text-muted); }
  .context-badge.attachment-context, .primary-source { border-color: var(--color-pink); background: var(--color-pink-soft); color: var(--color-text); }
  .meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.45rem; margin: 0.75rem 0 0; }
  .meta-grid div { min-width: 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.45rem; }
  dt { color: var(--color-text-subtle); font-size: 0.68rem; }
  dd { margin: 0.18rem 0 0; min-width: 0; overflow: hidden; color: var(--color-text); font-size: 0.76rem; text-overflow: ellipsis; white-space: nowrap; }
  .detail-section { margin-top: 0.9rem; }
  .detail-section h4 { margin: 0 0 0.45rem; color: var(--color-text); font-size: 0.84rem; }
  .detail-section p, .muted, .empty-state p { margin: 0; color: var(--color-text-muted); font-size: 0.78rem; line-height: 1.55; }
  .section-title-row { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.45rem; }
  .section-title-row h4 { margin: 0; }
  .section-actions { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; justify-content: flex-end; }
  .source-badge { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); color: var(--color-text-muted); padding: 0.12rem 0.38rem; font-size: 0.66rem; font-weight: 700; white-space: nowrap; }
  .body-toggle { display: inline-flex; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); overflow: hidden; }
  .body-toggle button { border: 0; border-right: 1px solid var(--color-border-soft); background: transparent; color: var(--color-text-muted); padding: 0.16rem 0.45rem; font: inherit; font-size: 0.66rem; font-weight: 700; cursor: pointer; }
  .body-toggle button:last-child { border-right: 0; }
  .body-toggle button.active { background: var(--color-pink-soft); color: var(--color-text); }
  .body-note { margin-bottom: 0.4rem; }
  .body-block { max-height: 24rem; overflow: auto; margin: 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); color: var(--color-text); padding: 0.65rem; font-family: inherit; font-size: 0.76rem; line-height: 1.55; overflow-wrap: anywhere; white-space: pre-wrap; }
  .body-frame { display: block; width: 100%; height: 30rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: #fff; }
  .item-list, .attachment-list { display: grid; gap: 0.45rem; }
  .item-list article, .attachment-list article { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.55rem; }
  .item-list strong, .attachment-list strong { display: block; min-width: 0; overflow: hidden; color: var(--color-text); font-size: 0.78rem; text-overflow: ellipsis; white-space: nowrap; }
  .item-list span, .attachment-list span { display: inline-block; margin-top: 0.28rem; margin-right: 0.45rem; color: var(--color-text-muted); font-size: 0.7rem; }
  .attachment-list p { margin-top: 0.35rem; }
  .path-text { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
  .profile-text { color: var(--color-text-subtle); }
  .error-text { color: #b91c1c; }
  .key-point-list { margin: 0.35rem 0 0; padding-left: 1rem; color: var(--color-text-muted); font-size: 0.72rem; line-height: 1.45; }
  .warning-section { border: 1px solid var(--color-warning-soft); border-radius: var(--radius-sm); background: var(--color-warning-soft); padding: 0.65rem; }
  .warning-section ul { margin: 0; padding-left: 1.1rem; color: #92400e; font-size: 0.76rem; line-height: 1.5; }
  .empty, .empty-state { color: var(--color-text-muted); text-align: center; padding: 1rem; }
  .empty-state h3 { margin: 0 0 0.35rem; color: var(--color-text); }

  @media (max-width: 760px) {
    .detail-header { flex-direction: column; }
    .header-actions { justify-items: start; }
    .meta-grid { grid-template-columns: 1fr; }
    .section-title-row { align-items: flex-start; flex-direction: column; }
    .section-actions { justify-content: flex-start; }
    .body-frame { height: 24rem; }
  }
</style>

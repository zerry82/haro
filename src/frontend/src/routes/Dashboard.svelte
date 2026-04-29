<script lang="ts">
  import { onMount } from 'svelte';
  import { push } from 'svelte-spa-router';
  import { isAuthenticated, logout, user } from '../stores/auth';
  import { projects, loadProjects, createProject, deleteProject, type ProjectItem } from '../stores/projects';

  let showNewForm = $state(false);
  let newTitle = $state('');
  let creating = $state(false);

  onMount(async () => {
    if (!$isAuthenticated) { push('/login'); return; }
    await loadProjects();
  });

  async function handleCreate() {
    if (!newTitle.trim()) return;
    creating = true;
    try {
      const id = await createProject(newTitle.trim());
      newTitle = '';
      showNewForm = false;
      push(`/projects/${id}`);
    } catch (e: any) {
      alert(e.message);
    } finally {
      creating = false;
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('프로젝트를 삭제하시겠습니까? 모든 채팅과 파일이 삭제됩니다.')) return;
    await deleteProject(id);
  }

  function handleLogout() {
    logout();
    push('/login');
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('ko-KR', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function getModeLabel(project: ProjectItem) {
    return project.runtime_mode === 'deploy' ? '배포모드' : '작업모드';
  }
</script>

<div class="dashboard">
  <header class="top-bar">
    <h1>haro</h1>
    <div class="user-area">
      <span>{$user?.name}</span>
      <button onclick={handleLogout}>로그아웃</button>
    </div>
  </header>

  <main class="content">
    <div class="toolbar">
      <h2>내 프로젝트</h2>
      {#if !showNewForm}
        <button class="btn-primary" onclick={() => { showNewForm = true; }}>+ 새 프로젝트</button>
      {/if}
    </div>

    {#if showNewForm}
      <form class="new-form" onsubmit={(e) => { e.preventDefault(); handleCreate(); }}>
        <input
          type="text"
          placeholder="프로젝트 이름"
          bind:value={newTitle}
        />
        <button type="submit" disabled={creating || !newTitle.trim()}>
          {creating ? '생성 중...' : '생성'}
        </button>
        <button type="button" onclick={() => { showNewForm = false; newTitle = ''; }}>취소</button>
      </form>
    {/if}

    <div class="project-grid">
      {#each $projects as p}
        <div class="project-card" role="button" tabindex="0"
          onclick={() => push(`/projects/${p.id}`)}
          onkeydown={(e) => { if (e.key === 'Enter') push(`/projects/${p.id}`); }}
        >
          <div class="card-header">
            <span class="card-title">{p.title}</span>
            <button class="delete-btn"
              onclick={(e) => { e.stopPropagation(); handleDelete(p.id); }}
            >×</button>
          </div>
          <div class="card-meta">
            <span>💬 {p.chat_session_count}개 채팅</span>
            <span class="status-dot" class:running={p.container_status === 'running'}></span>
            <span class="mode-badge" class:deploy={p.runtime_mode === 'deploy'}>{getModeLabel(p)}</span>
            <span>{p.container_status}</span>
          </div>
          <div class="card-date">{formatDate(p.updated_at)}</div>
        </div>
      {/each}

      {#if $projects.length === 0 && !showNewForm}
        <div class="empty-state">
          <p>프로젝트가 없습니다.</p>
          <button class="btn-primary" onclick={() => { showNewForm = true; }}>첫 프로젝트 만들기</button>
        </div>
      {/if}
    </div>
  </main>
</div>

<style>
  .dashboard {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--color-bg);
    color: var(--color-text);
  }

  .top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 56px;
    padding: 0 1.25rem;
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .top-bar h1 {
    margin: 0;
    color: var(--color-pink);
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: 0;
  }

  .user-area {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.82rem;
    color: var(--color-text-muted);
  }

  .user-area button {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    padding: 0.35rem 0.65rem;
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
  }

  .user-area button:hover {
    border-color: var(--color-pink);
    color: var(--color-pink);
    background: var(--color-pink-soft);
  }

  .content {
    flex: 1;
    overflow-y: auto;
    width: 100%;
    max-width: 1120px;
    margin: 0 auto;
    padding: 2rem 2rem 4rem;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .toolbar h2 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: 0;
  }

  .btn-primary {
    background: var(--color-pink);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    padding: 0.6rem 0.95rem;
    cursor: pointer;
    font: inherit;
    font-size: 0.84rem;
    font-weight: 700;
    box-shadow: 0 8px 18px rgba(255, 138, 198, 0.24);
  }

  .btn-primary:hover {
    filter: brightness(0.97);
  }

  .new-form {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-sidebar);
  }

  .new-form input {
    flex: 1;
    min-width: 0;
    padding: 0.58rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 0.9rem;
  }

  .new-form input:focus {
    outline: none;
    border-color: var(--color-pink);
    box-shadow: 0 0 0 3px var(--color-pink-soft);
  }

  .new-form button {
    padding: 0.58rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    color: var(--color-text-muted);
    cursor: pointer;
    font: inherit;
    font-size: 0.84rem;
  }

  .new-form button[type="submit"] {
    border-color: var(--color-pink);
    background: var(--color-pink);
    color: white;
    font-weight: 700;
  }

  .new-form button:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.9rem;
  }

  .project-card {
    min-height: 116px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1rem;
    cursor: pointer;
    transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
    box-shadow: var(--shadow-card);
  }

  .project-card:hover {
    border-color: var(--color-pink);
    box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
  }

  .project-card:focus-visible {
    outline: 3px solid var(--color-pink-soft);
    outline-offset: 2px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.7rem;
  }

  .card-title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 800;
    font-size: 0.95rem;
  }

  .delete-btn {
    background: none;
    border: none;
    color: var(--color-text-subtle);
    cursor: pointer;
    font-size: 1.2rem;
    padding: 0;
    line-height: 1;
  }

  .delete-btn:hover {
    color: var(--color-danger);
  }

  .card-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem;
    font-size: 0.78rem;
    color: var(--color-text-muted);
    margin-bottom: 0.45rem;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--color-text-subtle);
  }

  .status-dot.running {
    background: var(--color-accent);
  }

  .mode-badge {
    border-radius: 999px;
    background: var(--color-sidebar-strong);
    color: var(--color-text-muted);
    padding: 0.1rem 0.45rem;
    font-size: 0.72rem;
    font-weight: 700;
  }

  .mode-badge.deploy {
    background: var(--color-pink-soft);
    color: #be185d;
  }

  .card-date {
    font-size: 0.74rem;
    color: var(--color-text-subtle);
  }

  .empty-state {
    grid-column: 1 / -1;
    text-align: center;
    margin-top: 5rem;
    padding: 3rem;
    color: var(--color-text-muted);
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-sidebar);
  }

  .empty-state p {
    margin: 0 0 1rem;
  }

  @media (max-width: 720px) {
    .content {
      padding: 1.25rem 1rem 3rem;
    }

    .toolbar,
    .new-form {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>

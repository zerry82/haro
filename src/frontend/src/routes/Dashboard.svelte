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
    <h1>Mini Open Claw</h1>
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
          autofocus
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
  .dashboard { height: 100vh; display: flex; flex-direction: column; }
  .top-bar { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.5rem; background: #0f3460; border-bottom: 1px solid #333; }
  .top-bar h1 { margin: 0; color: #e94560; font-size: 1.3rem; }
  .user-area { display: flex; align-items: center; gap: 0.75rem; font-size: 0.85rem; }
  .user-area button { background: none; border: 1px solid #555; border-radius: 6px; color: #ccc; padding: 0.3rem 0.6rem; cursor: pointer; font-size: 0.8rem; }

  .content { flex: 1; overflow-y: auto; padding: 1.5rem 2rem; max-width: 900px; margin: 0 auto; width: 100%; }
  .toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
  .toolbar h2 { margin: 0; font-size: 1.1rem; }
  .btn-primary { background: #e94560; color: white; border: none; border-radius: 8px; padding: 0.5rem 1rem; cursor: pointer; font-size: 0.85rem; }
  .btn-primary:hover { opacity: 0.9; }

  .new-form { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .new-form input { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid #333; border-radius: 8px; background: #0f3460; color: #e0e0e0; font-size: 0.9rem; }
  .new-form input:focus { outline: none; border-color: #e94560; }
  .new-form button { padding: 0.5rem 0.75rem; border: none; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }
  .new-form button[type="submit"] { background: #e94560; color: white; }
  .new-form button[type="button"] { background: #333; color: #ccc; }

  .project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
  .project-card { background: #16213e; border: 1px solid #333; border-radius: 10px; padding: 1rem; cursor: pointer; transition: border-color 0.2s; }
  .project-card:hover { border-color: #e94560; }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; }
  .card-title { font-weight: 600; font-size: 0.95rem; }
  .delete-btn { background: none; border: none; color: #666; cursor: pointer; font-size: 1.2rem; padding: 0; line-height: 1; }
  .delete-btn:hover { color: #e94560; }
  .card-meta { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: #888; margin-bottom: 0.25rem; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #555; }
  .status-dot.running { background: #50c878; }
  .mode-badge { border-radius: 999px; background: #26314a; color: #cbd5e1; padding: 0.1rem 0.45rem; font-size: 0.72rem; font-weight: 600; }
  .mode-badge.deploy { background: #4b1f2c; color: #ff9bb0; }
  .card-date { font-size: 0.75rem; color: #666; }

  .empty-state { grid-column: 1 / -1; text-align: center; padding: 3rem; color: #666; }
  .empty-state p { margin-bottom: 1rem; }
</style>

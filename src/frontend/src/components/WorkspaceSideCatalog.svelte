<script lang="ts">
  import type { SidePanelTab, SkillResponse, ToolCatalogItem } from './workspaceSidePanelTypes';

  let {
    activeSideTab,
    skills,
    skillsLoading,
    skillsError,
    toolCatalog,
  }: {
    activeSideTab: SidePanelTab;
    skills: SkillResponse[];
    skillsLoading: boolean;
    skillsError: string;
    toolCatalog: ToolCatalogItem[];
  } = $props();
</script>

{#if activeSideTab === 'skills'}
  <div class="side-list">
    {#if skillsLoading}
      <p class="empty">스킬 불러오는 중...</p>
    {:else if skillsError}
      <div class="side-error">{skillsError}</div>
    {:else if skills.length === 0}
      <p class="empty">설치된 스킬 없음</p>
    {:else}
      {#each skills as skill}
        <article class="side-card">
          <div class="side-card-title" title={skill.name}>{skill.name}</div>
          <div class="side-card-meta">
            <span>{skill.status}</span>
            <span>{skill.type}</span>
            <span>v{skill.version}</span>
          </div>
          {#if skill.description}
            <p class="side-card-description">{skill.description}</p>
          {/if}
          {#if skill.tools.length > 0}
            <div class="side-chip-list">
              {#each skill.tools as tool}
                <span class="side-chip" title={tool}>{tool}</span>
              {/each}
            </div>
          {/if}
        </article>
      {/each}
    {/if}
  </div>
{:else if activeSideTab === 'tools'}
  <div class="side-list">
    {#each toolCatalog as tool}
      <article class="side-card">
        <div class="side-card-title" title={tool.name}>{tool.name}</div>
        <code class="side-signature" title={tool.signature}>{tool.signature}</code>
        <p class="side-card-description">{tool.description}</p>
      </article>
    {/each}
  </div>
{:else}
  <div class="side-list">
    <p class="empty">연결된 데이터소스 없음</p>
  </div>
{/if}

<style>
  .side-list { flex: 1; overflow-y: auto; padding: 0.4rem; }
  .side-card { margin-bottom: 0.4rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-md); background: var(--color-surface); padding: 0.5rem; }
  .side-card-title { color: var(--color-text); font-size: 0.82rem; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-card-meta { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.35rem; color: var(--color-text-muted); font-size: 0.68rem; }
  .side-card-meta span { border-radius: 999px; background: var(--color-sidebar-strong); padding: 0.1rem 0.35rem; }
  .side-card-description { margin: 0.45rem 0 0; color: var(--color-text-muted); font-size: 0.74rem; line-height: 1.45; }
  .side-chip-list { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.45rem; }
  .side-chip { max-width: 100%; border-radius: var(--radius-sm); background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.12rem 0.3rem; font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-signature { display: block; margin-top: 0.35rem; color: var(--color-info); font-family: var(--font-mono); font-size: 0.68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side-error { border: 1px solid var(--color-danger-soft); border-radius: var(--radius-md); background: var(--color-danger-soft); color: var(--color-danger); padding: 0.6rem; font-size: 0.75rem; line-height: 1.45; }
  .empty { color: var(--color-text-subtle); font-size: 0.8rem; text-align: center; padding: 1rem; }
</style>

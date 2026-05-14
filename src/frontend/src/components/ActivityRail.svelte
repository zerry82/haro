<script lang="ts">
  import { Files, Mail, Sparkles, Wrench } from 'lucide-svelte';
  import type { SidePanelTab, SidePanelTabItem } from './workspaceSidePanelTypes';

  let {
    activeSideTab,
    sidePanelTabs,
    onActiveSideTabChange,
  }: {
    activeSideTab: SidePanelTab;
    sidePanelTabs: SidePanelTabItem[];
    onActiveSideTabChange: (tab: SidePanelTab) => void;
  } = $props();
</script>

<div class="activity-bar" role="tablist" aria-label="왼쪽 메뉴">
  {#each sidePanelTabs as tab}
    <button
      type="button"
      class="activity-tab"
      class:active={activeSideTab === tab.id}
      role="tab"
      aria-selected={activeSideTab === tab.id}
      aria-label={tab.label}
      title={tab.label}
      onclick={() => onActiveSideTabChange(tab.id)}
    >
      {#if tab.id === 'files'}
        <Files size={24} strokeWidth={1.8} />
      {:else if tab.id === 'skills'}
        <Sparkles size={24} strokeWidth={1.8} />
      {:else if tab.id === 'tools'}
        <Wrench size={24} strokeWidth={1.8} />
      {:else if tab.id === 'mail'}
        <Mail size={24} strokeWidth={1.8} />
      {/if}
      <span class="sr-only">{tab.label}</span>
    </button>
  {/each}
</div>

<style>
  .activity-bar { width: 48px; flex-shrink: 0; display: flex; flex-direction: column; align-items: stretch; padding: 0.25rem 0; background: var(--color-surface); border-right: 1px solid var(--color-border); }
  .activity-tab { position: relative; width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border: none; border-left: 2px solid transparent; background: transparent; color: var(--color-text-muted); cursor: pointer; }
  .activity-tab:hover { color: var(--color-text); background: var(--color-sidebar-strong); }
  .activity-tab.active { color: var(--color-text); border-left-color: var(--color-accent); background: var(--color-sidebar-strong); }
  .activity-tab.active::after { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 2px; background: var(--color-accent); }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
</style>

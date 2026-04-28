<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { basicSetup } from 'codemirror';
  import { EditorState, Compartment, type Extension } from '@codemirror/state';
  import { EditorView } from '@codemirror/view';
  import { javascript } from '@codemirror/lang-javascript';
  import { html } from '@codemirror/lang-html';
  import { markdown } from '@codemirror/lang-markdown';
  import { json } from '@codemirror/lang-json';
  import { css } from '@codemirror/lang-css';

  let {
    value = '',
    language = 'plaintext',
    onchange,
  }: {
    value?: string;
    language?: string;
    onchange?: (value: string) => void;
  } = $props();

  let host: HTMLDivElement;
  let view: EditorView | null = null;
  let currentValue = '';
  const languageCompartment = new Compartment();

  function getLanguageExtension(lang: string): Extension {
    switch (lang) {
      case 'javascript':
        return javascript();
      case 'typescript':
        return javascript({ typescript: true });
      case 'html':
      case 'xml':
        return html();
      case 'markdown':
        return markdown();
      case 'json':
        return json();
      case 'css':
        return css();
      default:
        return [];
    }
  }

  onMount(() => {
    currentValue = value;
    view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          EditorView.lineWrapping,
          languageCompartment.of(getLanguageExtension(language)),
          EditorView.updateListener.of((update) => {
            if (!update.docChanged) return;
            currentValue = update.state.doc.toString();
            onchange?.(currentValue);
          }),
          EditorView.theme({
            '&': {
              height: '100%',
              backgroundColor: '#0a0a1a',
              color: '#e0e0e0',
              fontSize: '13px',
            },
            '.cm-scroller': {
              fontFamily: "Consolas, 'Courier New', monospace",
            },
            '.cm-gutters': {
              backgroundColor: '#10172a',
              color: '#7d8799',
              borderRight: '1px solid #2a3448',
            },
            '.cm-activeLine': {
              backgroundColor: '#16213e',
            },
            '.cm-activeLineGutter': {
              backgroundColor: '#1f2d4a',
            },
            '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
              backgroundColor: '#344c7a',
            },
            '&.cm-focused': {
              outline: 'none',
            },
          }),
        ],
      }),
    });
  });

  $effect(() => {
    if (!view || value === currentValue) return;
    currentValue = value;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value },
    });
  });

  $effect(() => {
    if (!view) return;
    view.dispatch({
      effects: languageCompartment.reconfigure(getLanguageExtension(language)),
    });
  });

  onDestroy(() => {
    view?.destroy();
  });
</script>

<div class="code-editor" bind:this={host}></div>

<style>
  .code-editor { height: 100%; min-height: 0; }
  .code-editor :global(.cm-editor) { height: 100%; }
</style>

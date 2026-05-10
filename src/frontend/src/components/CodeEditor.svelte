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

  interface EditorSelectionContext {
    start_line?: number;
    end_line?: number;
    text_preview?: string;
  }

  let {
    value = '',
    language = 'plaintext',
    readonly = false,
    onchange,
    onselectionchange,
  }: {
    value?: string;
    language?: string;
    readonly?: boolean;
    onchange?: (value: string) => void;
    onselectionchange?: (selection: EditorSelectionContext | null) => void;
  } = $props();

  let host: HTMLDivElement;
  let view: EditorView | null = null;
  let currentValue = '';
  const languageCompartment = new Compartment();
  const readOnlyCompartment = new Compartment();

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

  function notifySelection(state: EditorState) {
    const range = state.selection.main;
    if (range.empty) {
      onselectionchange?.(null);
      return;
    }
    const fromLine = state.doc.lineAt(range.from);
    const toLine = state.doc.lineAt(range.to);
    const text = state.sliceDoc(range.from, range.to);
    onselectionchange?.({
      start_line: fromLine.number,
      end_line: toLine.number,
      text_preview: text.slice(0, 2000),
    });
  }

  onMount(() => {
    currentValue = value;
    const token = (name: string, fallback: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
    const surface = token('--color-surface', '#ffffff');
    const sidebar = token('--color-sidebar', '#f7f8fb');
    const sidebarStrong = token('--color-sidebar-strong', '#eef2f7');
    const borderSoft = token('--color-border-soft', '#e7ebf1');
    const text = token('--color-text', '#111827');
    const textSubtle = token('--color-text-subtle', '#98a2b3');
    const infoSoft = token('--color-info-soft', '#dbeafe');

    view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          EditorView.lineWrapping,
          languageCompartment.of(getLanguageExtension(language)),
          readOnlyCompartment.of([
            EditorState.readOnly.of(readonly),
            EditorView.editable.of(!readonly),
          ]),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              currentValue = update.state.doc.toString();
              onchange?.(currentValue);
            }
            if (update.selectionSet || update.docChanged) {
              notifySelection(update.state);
            }
          }),
          EditorView.theme({
            '&': {
              height: '100%',
              backgroundColor: surface,
              color: text,
              fontSize: '13px',
            },
            '.cm-scroller': {
              fontFamily: "var(--font-mono)",
            },
            '.cm-gutters': {
              backgroundColor: sidebar,
              color: textSubtle,
              borderRight: `1px solid ${borderSoft}`,
            },
            '.cm-activeLine': {
              backgroundColor: sidebar,
            },
            '.cm-activeLineGutter': {
              backgroundColor: sidebarStrong,
            },
            '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
              backgroundColor: infoSoft,
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

  $effect(() => {
    if (!view) return;
    view.dispatch({
      effects: readOnlyCompartment.reconfigure([
        EditorState.readOnly.of(readonly),
        EditorView.editable.of(!readonly),
      ]),
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

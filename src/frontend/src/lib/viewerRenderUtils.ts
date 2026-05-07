import { marked } from 'marked';
import hljs from 'highlight.js/lib/core';
import cssLanguage from 'highlight.js/lib/languages/css';
import javascriptLanguage from 'highlight.js/lib/languages/javascript';
import jsonLanguage from 'highlight.js/lib/languages/json';
import pythonLanguage from 'highlight.js/lib/languages/python';
import typescriptLanguage from 'highlight.js/lib/languages/typescript';
import xmlLanguage from 'highlight.js/lib/languages/xml';
import yamlLanguage from 'highlight.js/lib/languages/yaml';
import Papa from 'papaparse';
import { escapeHtml } from './workspaceUtils';

let highlightLanguagesRegistered = false;

export function registerWorkspaceHighlightLanguages() {
  if (highlightLanguagesRegistered) return;
  hljs.registerLanguage('css', cssLanguage);
  hljs.registerLanguage('javascript', javascriptLanguage);
  hljs.registerLanguage('json', jsonLanguage);
  hljs.registerLanguage('python', pythonLanguage);
  hljs.registerLanguage('typescript', typescriptLanguage);
  hljs.registerLanguage('xml', xmlLanguage);
  hljs.registerLanguage('yaml', yamlLanguage);
  highlightLanguagesRegistered = true;
}

export function renderMarkdown(content: string | null) {
  return marked.parse(content || '', { async: false }) as string;
}

export function renderChatMarkdown(content: string | null) {
  const html = marked.parse(content || '', { async: false, breaks: true }) as string;
  return sanitizeChatMarkdown(html);
}

export function sanitizeChatMarkdown(html: string) {
  if (typeof document === 'undefined') return html;
  const template = document.createElement('template');
  template.innerHTML = html;
  template.content.querySelectorAll('script, style, iframe, object, embed, link, meta').forEach((node) => node.remove());
  template.content.querySelectorAll('*').forEach((element) => {
    Array.from(element.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc') {
        element.removeAttribute(attribute.name);
        return;
      }
      if ((name === 'href' || name === 'src') && value.startsWith('javascript:')) {
        element.removeAttribute(attribute.name);
      }
    });
    if (element.tagName.toLowerCase() === 'a') {
      element.setAttribute('target', '_blank');
      element.setAttribute('rel', 'noreferrer');
    }
  });
  return template.innerHTML;
}

export function highlightCode(content: string | null, language: string) {
  registerWorkspaceHighlightLanguages();
  const code = content || '';
  const languageMap: Record<string, string> = {
    html: 'xml',
    javascript: 'javascript',
    typescript: 'typescript',
    json: 'json',
  };
  const highlightLanguage = languageMap[language] || language;
  try {
    if (highlightLanguage && hljs.getLanguage(highlightLanguage)) {
      return hljs.highlight(code, { language: highlightLanguage, ignoreIllegals: true }).value;
    }
    return hljs.highlightAuto(code).value;
  } catch {
    return escapeHtml(code);
  }
}

export function parseCsvContent(content: string) {
  const result = Papa.parse(content, { skipEmptyLines: false });
  const rows = (result.data as unknown[]).map((row) => {
    if (Array.isArray(row)) {
      return row.map((cell) => cell == null ? '' : String(cell));
    }
    return [row == null ? '' : String(row)];
  });
  const error = result.errors.map((item) => item.message).join('\n');
  return { rows, error };
}

export function unparseCsvRows(rows: string[][]) {
  return Papa.unparse(rows);
}

import { describe, expect, it } from 'vitest';

import {
  highlightCode,
  parseCsvContent,
  renderChatMarkdown,
  renderMarkdown,
  unparseCsvRows,
} from './viewerRenderUtils';

describe('viewerRenderUtils', () => {
  it('renders markdown for viewer and chat contexts', () => {
    expect(renderMarkdown('# Title')).toContain('<h1');
    expect(renderChatMarkdown('hello\nworld')).toContain('<br>');
  });

  it('highlights code through registered languages', () => {
    expect(highlightCode('const answer = 42;', 'typescript')).toContain('answer');
  });

  it('parses and serializes csv rows', () => {
    const parsed = parseCsvContent('name,value\nA,1');

    expect(parsed.rows).toEqual([
      ['name', 'value'],
      ['A', '1'],
    ]);
    expect(parsed.error).toBe('');
    expect(unparseCsvRows(parsed.rows)).toBe('name,value\r\nA,1');
  });
});

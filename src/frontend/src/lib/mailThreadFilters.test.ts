import { describe, expect, it } from 'vitest';
import {
  filterMailThreads,
  getThreadActions,
  getThreadDueDates,
  getThreadStructureStatus,
  getThreadWarnings,
  searchMailThreads,
  type MailThreadFilter,
} from './mailThreadFilters';
import type { MailThread } from '../stores/mail';

describe('mailThreadFilters', () => {
  it('filters threads by structure, attachments, due dates, and actions', () => {
    const threads = [
      thread('a', { warnings: [], actions: [{ text: 'reply' }], dueDates: [], attachments: 0 }),
      thread('b', { warnings: ['unclear date'], actions: [], dueDates: [{ date: '2026-05-15' }], attachments: 1 }),
      thread('c', { warnings: [], actions: [], dueDates: [], attachments: 0 }),
    ];

    expect(ids(threads, 'all')).toEqual(['a', 'b', 'c']);
    expect(ids(threads, 'good')).toEqual(['a', 'c']);
    expect(ids(threads, 'warning')).toEqual(['b']);
    expect(ids(threads, 'attachments')).toEqual(['b']);
    expect(ids(threads, 'due_dates')).toEqual(['b']);
    expect(ids(threads, 'actions')).toEqual(['a']);
  });

  it('normalizes structured metadata safely', () => {
    const item = thread('a', { warnings: ['check'], actions: [{ text: 'send' }], dueDates: [{ text: 'tomorrow' }], attachments: 0 });

    expect(getThreadStructureStatus(item)).toBe('warning');
    expect(getThreadWarnings(item)).toEqual(['check']);
    expect(getThreadActions(item)).toEqual([{ text: 'send' }]);
    expect(getThreadDueDates(item)).toEqual([{ text: 'tomorrow' }]);
  });

  it('searches across subject, sender, summary, structured fields, and attachments', () => {
    const threads = [
      thread('a', { warnings: [], actions: [{ text: '성과 보고서 회신' }], dueDates: [], attachments: 0 }),
      thread('b', { warnings: ['일정 애매함'], actions: [], dueDates: [{ date: '2026-05-15' }], attachments: 1 }),
    ];

    expect(searchMailThreads(threads, '성과').map((item) => item.id)).toEqual(['a']);
    expect(searchMailThreads(threads, 'file-0').map((item) => item.id)).toEqual(['b']);
    expect(searchMailThreads(threads, '일정 애매').map((item) => item.id)).toEqual(['b']);
  });
});

function ids(threads: MailThread[], filter: MailThreadFilter): string[] {
  return filterMailThreads(threads, filter).map((item) => item.id);
}

function thread(
  id: string,
  options: { warnings: string[]; actions: Array<Record<string, any>>; dueDates: Array<Record<string, any>>; attachments: number },
): MailThread {
  return {
    id,
    subject: `subject ${id}`,
    sender: `${id}@example.com`,
    recipients: ['me@example.com'],
    received_at: '2026-05-12T00:00:00+00:00',
    summary: `summary ${id}`,
    category: '일반 업무',
    attachments: Array.from({ length: options.attachments }, (_, index) => ({
      title: `file-${index}.pdf`,
      extension: 'pdf',
      size_bytes: 100,
      summary: '',
      summarized: false,
    })),
    inclusion_decision: 'allowed',
    promoted_at: null,
    clean_room_path: null,
    metadata: {
      extracted_actions: options.actions,
      extracted_due_dates: options.dueDates,
      structure_warnings: options.warnings,
    },
  };
}

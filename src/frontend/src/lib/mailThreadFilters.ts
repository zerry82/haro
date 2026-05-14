import type { MailThread } from '../stores/mail';

export type MailThreadFilter = 'all' | 'good' | 'warning' | 'attachments' | 'due_dates' | 'actions';

export const MAIL_THREAD_FILTERS: Array<{ id: MailThreadFilter; label: string }> = [
  { id: 'all', label: '전체' },
  { id: 'good', label: '구조화 좋음' },
  { id: 'warning', label: '주의 필요' },
  { id: 'attachments', label: '첨부 있음' },
  { id: 'due_dates', label: '일정 있음' },
  { id: 'actions', label: '요청사항 있음' },
];

export function filterMailThreads(threads: MailThread[], filter: MailThreadFilter): MailThread[] {
  if (filter === 'all') return threads;
  return threads.filter((thread) => {
    if (filter === 'good') return getThreadWarnings(thread).length === 0;
    if (filter === 'warning') return getThreadWarnings(thread).length > 0;
    if (filter === 'attachments') return thread.attachments.length > 0;
    if (filter === 'due_dates') return getThreadDueDates(thread).length > 0;
    if (filter === 'actions') return getThreadActions(thread).length > 0;
    return true;
  });
}

export function countMailThreads(threads: MailThread[], filter: MailThreadFilter): number {
  return filterMailThreads(threads, filter).length;
}

export function searchMailThreads(threads: MailThread[], query: string): MailThread[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return [];
  return threads.filter((thread) => searchHaystack(thread).includes(normalized));
}

export function getThreadActions(thread: MailThread): Array<Record<string, any>> {
  const actions = thread.metadata?.extracted_actions;
  return Array.isArray(actions) ? actions.filter(isRecord) : [];
}

export function getThreadDueDates(thread: MailThread): Array<Record<string, any>> {
  const dueDates = thread.metadata?.extracted_due_dates;
  return Array.isArray(dueDates) ? dueDates.filter(isRecord) : [];
}

export function getThreadWarnings(thread: MailThread): string[] {
  const warnings = thread.metadata?.structure_warnings;
  if (!Array.isArray(warnings)) return [];
  return warnings.map((warning) => String(warning)).filter(Boolean);
}

export function getThreadStructureStatus(thread: MailThread): 'good' | 'warning' {
  return getThreadWarnings(thread).length > 0 ? 'warning' : 'good';
}

export function formatThreadDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function isRecord(value: unknown): value is Record<string, any> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function searchHaystack(thread: MailThread): string {
  const actionText = getThreadActions(thread).map((action) => Object.values(action).join(' ')).join(' ');
  const dueDateText = getThreadDueDates(thread).map((dueDate) => Object.values(dueDate).join(' ')).join(' ');
  const warningText = getThreadWarnings(thread).join(' ');
  const attachmentText = thread.attachments.map((attachment) => `${attachment.title} ${attachment.extension} ${attachment.summary}`).join(' ');
  return [
    thread.subject,
    thread.sender,
    thread.recipients.join(' '),
    thread.summary,
    thread.category,
    actionText,
    dueDateText,
    warningText,
    attachmentText,
  ].join(' ').toLocaleLowerCase();
}

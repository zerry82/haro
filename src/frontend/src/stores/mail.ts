import { api } from '../lib/api';

export type MailConnection = {
  id: string;
  provider: string;
  email: string | null;
  status: string;
  live_status: string;
  live_poll_interval_minutes: number;
  last_sync_at: string | null;
  created_at?: string;
  updated_at?: string;
};

export type MailPolicy = {
  categories: Array<Record<string, any>>;
  filters: Array<Record<string, any>>;
};

export type MailManagementPolicy = {
  whitelist_rules: Array<Record<string, any>>;
  blacklist_rules: Array<Record<string, any>>;
  llm_blacklist_rules: Array<Record<string, any>>;
  manual_overrides: Array<Record<string, any>>;
};

export type MailStatusResponse = {
  connection: MailConnection | null;
  policy: MailPolicy;
  management_policy?: MailManagementPolicy;
  latest_run: MailRunSummary | null;
};

export type GmailConnectResponse = {
  auth_url: string;
  connection: MailConnection;
};

export type MailRunSummary = {
  id: string;
  provider: string;
  status: string;
  range_start: string;
  range_end: string;
  source_run_id: string | null;
  created_at: string;
  updated_at?: string;
};

export type MailThread = {
  id: string;
  subject: string;
  sender: string;
  recipients: string[];
  received_at: string;
  summary: string;
  category: string;
  attachments: MailAttachment[];
  inclusion_decision: string;
  promoted_at: string | null;
  clean_room_path: string | null;
  metadata?: Record<string, any>;
  body?: string;
  body_source?: string;
  body_truncated?: boolean;
  body_html?: string;
  body_html_source?: string;
  body_html_truncated?: boolean;
  attachment_source?: string;
};

export type MailAttachment = {
  attachment_ref?: string;
  title: string;
  extension: string;
  size_bytes: number;
  mime_type?: string;
  summary: string;
  summarized: boolean;
  download_status?: string;
  inbox_path?: string;
  extract_status?: string;
  key_points?: string[];
  content_profile?: Record<string, any>;
  error_reason?: string;
};

export type MailAnalysisAttachment = MailAttachment & {
  thread_id: string;
  thread_subject: string;
  received_at: string;
};

export type MailAnalysisResponse = {
  run: MailRunSummary;
  stats: {
    received_count?: number;
    thread_count?: number;
    included_count?: number;
    sender_counts?: Array<{ sender: string; count: number }>;
    topic_counts?: Array<{ topic: string; count: number }>;
    attachments?: MailAttachment[];
    categories?: Array<{ name: string; count: number }>;
    extracted_action_count?: number;
    due_date_count?: number;
    structure_warning_count?: number;
    llm_structure_warning_count?: number;
    managed_count?: number;
    excluded_count?: number;
    attachment_primary_count?: number;
    attachment_downloaded_count?: number;
    attachment_summarized_count?: number;
    attachment_extract_failed_count?: number;
    manual_managed_count?: number;
    llm_excluded_count?: number;
    stage?: string;
    error?: { stage?: string; message?: string };
    cache_status?: Record<string, any>;
  };
  proposed_categories: Array<Record<string, any>>;
  proposed_filters: Array<Record<string, any>>;
  threads: MailThread[];
};

export type MailSearchItem = MailThread & {
  thread_id: string;
  score: number;
  matched_fields: string[];
  evidence: Array<{ field: string; snippet: string }>;
  retrieval?: {
    mode?: string;
    vector_score?: number;
    vector_distance?: number | null;
    text_score?: number;
  };
};

export type MailSearchResponse = {
  query: string;
  run: MailRunSummary;
  retrieval?: {
    mode?: string;
    vector?: Record<string, any>;
  };
  items: MailSearchItem[];
};

export type IncrementalMailPreviewThread = {
  source_ref: string;
  subject: string;
  sender: string;
  received_at: string;
  summary: string;
  attachment_count: number;
};

export type IncrementalMailPreview = {
  latest_run: MailRunSummary;
  since_received_at: string | null;
  new_count: number;
  scan_limit: number;
  fetched_count: number;
  fetched_at: string;
  cache_status?: Record<string, any>;
  threads: IncrementalMailPreviewThread[];
};

export type MailInsight = {
  type: string;
  title: string;
  summary: string;
  severity: string;
  thread_count: number;
  thread_ids: string[];
  attachments: MailAttachment[];
  evidence: Array<{ thread_id: string; subject: string; sender: string; reason: string }>;
};

export type MailInsightsResponse = {
  query: string;
  run: MailRunSummary;
  summary: string;
  insights: MailInsight[];
};

export type MailStructureTest = {
  id: string;
  run_id: string;
  query: string;
  result_kind: string;
  rating: string;
  notes?: string | null;
  result: Record<string, any>;
  created_at: string;
};

export type MailImprovementCandidate = {
  id: string;
  run_id: string;
  title: string;
  reason: string;
  priority: string;
  source: string;
  status: string;
  query?: string | null;
  thread_ids: string[];
  evidence: Array<Record<string, any>>;
  created_at: string;
  updated_at: string;
};

export type ContextSearchItem = {
  id: string;
  title: string;
  summary: string;
  category: string;
  clean_room_path: string;
  properties: Record<string, any>;
};

export type ContextSearchResponse = {
  query: string;
  status: string;
  items: ContextSearchItem[];
};

export async function loadMailStatus(projectId: string) {
  return api<MailStatusResponse>(`/projects/${projectId}/mail/gmail/status`);
}

export async function connectGmail(projectId: string, returnUrl: string) {
  return api<GmailConnectResponse>(`/projects/${projectId}/mail/gmail/connect`, {
    method: 'POST',
    body: JSON.stringify({ return_url: returnUrl }),
  });
}

export async function analyzeRecentMail(projectId: string, maxThreads = 50, forceRefresh = false) {
  return api<MailAnalysisResponse>(`/projects/${projectId}/mail/gmail/analyze-recent`, {
    method: 'POST',
    body: JSON.stringify({ max_threads: maxThreads, force_refresh: forceRefresh, threads: [] }),
  });
}

export async function previewIncrementalMail(projectId: string, scanLimit = 500) {
  return api<IncrementalMailPreview>(`/projects/${projectId}/mail/gmail/incremental/preview`, {
    method: 'POST',
    body: JSON.stringify({ scan_limit: scanLimit }),
  });
}

export async function analyzeIncrementalMail(projectId: string, scanLimit = 500) {
  return api<MailAnalysisResponse>(`/projects/${projectId}/mail/gmail/incremental/analyze`, {
    method: 'POST',
    body: JSON.stringify({ scan_limit: scanLimit }),
  });
}

export async function loadMailAnalysis(projectId: string, runId: string) {
  return api<MailAnalysisResponse>(`/projects/${projectId}/mail/gmail/analysis/${runId}`);
}

export async function loadMailAnalysisThreads(projectId: string, runId: string) {
  return api<{ threads: MailThread[] }>(`/projects/${projectId}/mail/gmail/analysis/${runId}/threads`);
}

export async function loadMailAnalysisThread(projectId: string, runId: string, threadId: string) {
  return api<{ thread: MailThread }>(`/projects/${projectId}/mail/gmail/analysis/${runId}/threads/${threadId}`);
}

export async function loadMailAnalysisAttachments(projectId: string, runId: string) {
  return api<{ attachments: MailAnalysisAttachment[] }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/attachments`
  );
}

export async function searchMailAnalysis(projectId: string, runId: string, query: string, limit = 10) {
  return api<MailSearchResponse>(`/projects/${projectId}/mail/gmail/analysis/${runId}/search`, {
    method: 'POST',
    body: JSON.stringify({ query, limit }),
  });
}

export async function createMailInsights(projectId: string, runId: string, query = '') {
  return api<MailInsightsResponse>(`/projects/${projectId}/mail/gmail/analysis/${runId}/insights`, {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

export async function saveMailStructureTest(
  projectId: string,
  runId: string,
  payload: {
    query: string;
    result_kind: string;
    rating: string;
    notes?: string | null;
    result?: Record<string, any>;
  }
) {
  return api<{ test: MailStructureTest }>(`/projects/${projectId}/mail/gmail/analysis/${runId}/structure-tests`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function loadMailStructureTests(projectId: string, runId: string) {
  return api<{ tests: MailStructureTest[] }>(`/projects/${projectId}/mail/gmail/analysis/${runId}/structure-tests`);
}

export async function saveMailImprovementCandidate(
  projectId: string,
  runId: string,
  payload: {
    title: string;
    reason: string;
    priority?: string;
    source?: string;
    query?: string | null;
    thread_ids?: string[];
    evidence?: Array<Record<string, any>>;
  }
) {
  return api<{ candidate: MailImprovementCandidate }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/improvement-candidates`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

export async function loadMailImprovementCandidates(projectId: string, runId: string) {
  return api<{ candidates: MailImprovementCandidate[] }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/improvement-candidates`
  );
}

export async function saveMailPolicy(projectId: string, policy: MailPolicy) {
  return api<{ policy: MailPolicy }>(`/projects/${projectId}/mail/gmail/policies`, {
    method: 'PUT',
    body: JSON.stringify(policy),
  });
}

export async function loadExcludedMailThreads(projectId: string, runId: string) {
  return api<{ threads: MailThread[] }>(`/projects/${projectId}/mail/gmail/analysis/${runId}/excluded`);
}

export async function manageMailThread(
  projectId: string,
  runId: string,
  threadId: string,
  decision = 'managed',
  reason = ''
) {
  return api<{ thread: MailThread; management_policy: MailManagementPolicy }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/threads/${threadId}/manage`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    }
  );
}

export async function saveMailManagementPolicy(projectId: string, policy: MailManagementPolicy) {
  return api<{ management_policy: MailManagementPolicy }>(`/projects/${projectId}/mail/gmail/management-policies`, {
    method: 'PUT',
    body: JSON.stringify(policy),
  });
}

export async function indexManagedMail(projectId: string, runId: string) {
  return api<{ status: string; indexed_count: number; collection?: string }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/index-managed`,
    { method: 'POST' }
  );
}

export async function reanalyzeMail(projectId: string, sourceRunId?: string) {
  return api<MailAnalysisResponse>(`/projects/${projectId}/mail/gmail/reanalyze`, {
    method: 'POST',
    body: JSON.stringify({ source_run_id: sourceRunId || null }),
  });
}

export async function promoteMailAnalysis(projectId: string, runId: string) {
  return api<{ promoted_count: number; items: Array<Record<string, any>> }>(
    `/projects/${projectId}/mail/gmail/analysis/${runId}/promote`,
    { method: 'POST' }
  );
}

export async function startMailLive(projectId: string) {
  return api<{ connection: MailConnection }>(`/projects/${projectId}/mail/gmail/live/start`, {
    method: 'POST',
    body: JSON.stringify({ poll_interval_minutes: 30 }),
  });
}

export async function stopMailLive(projectId: string) {
  return api<{ connection: MailConnection }>(`/projects/${projectId}/mail/gmail/live/stop`, {
    method: 'POST',
  });
}

export async function migrateMailRange(projectId: string) {
  const now = new Date();
  const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  return api<MailAnalysisResponse>(`/projects/${projectId}/mail/gmail/migrations`, {
    method: 'POST',
    body: JSON.stringify({
      range_start: start.toISOString(),
      range_end: now.toISOString(),
      threads: [],
    }),
  });
}

export async function searchContextLibrary(projectId: string, query: string) {
  return api<ContextSearchResponse>(
    `/projects/${projectId}/context-library/search?q=${encodeURIComponent(query)}&limit=20`
  );
}

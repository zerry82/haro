<script lang="ts">
  import { Link, RefreshCw } from 'lucide-svelte';
  import MailThreadDetail from './MailThreadDetail.svelte';
  import MailThreadList from './MailThreadList.svelte';
  import {
    getThreadActions,
    getThreadDueDates,
    getThreadWarnings,
    searchMailThreads,
    type MailThreadFilter,
  } from '../lib/mailThreadFilters';
  import {
    analyzeRecentMail,
    analyzeIncrementalMail,
    connectGmail,
    createMailInsights,
    indexManagedMail,
    loadMailAnalysis,
    loadMailAnalysisAttachments,
    loadMailAnalysisThread,
    loadMailAnalysisThreads,
    loadExcludedMailThreads,
    loadMailImprovementCandidates,
    loadMailStatus,
    loadMailStructureTests,
    manageMailThread,
    previewIncrementalMail,
    saveMailManagementPolicy,
    saveMailPolicy,
    saveMailImprovementCandidate,
    saveMailStructureTest,
    searchMailAnalysis,
    type IncrementalMailPreview,
    type MailAnalysisResponse,
    type MailAnalysisAttachment,
    type MailConnection,
    type MailManagementPolicy,
    type MailImprovementCandidate,
    type MailInsight,
    type MailInsightsResponse,
    type MailPolicy,
    type MailSearchItem,
    type MailStructureTest,
    type MailThread,
  } from '../stores/mail';
  import type { OpenMailContext } from '../stores/chat';

  let {
    projectId,
    onAskWithMail,
    onMailContextChange,
  }: {
    projectId: string | null;
    onAskWithMail?: (text: string) => void;
    onMailContextChange?: (context: OpenMailContext | null) => void;
  } = $props();

  type MailWorkbenchTab = 'explore' | 'settings' | 'stats' | 'excluded';
  type ManagementRuleBucket = 'whitelist_rules' | 'blacklist_rules';

  let activeTab = $state<MailWorkbenchTab>('settings');
  let connection = $state<MailConnection | null>(null);
  let policy = $state<MailPolicy>({ categories: [], filters: [] });
  let managementPolicy = $state<MailManagementPolicy>(emptyManagementPolicy());
  let analysis = $state<MailAnalysisResponse | null>(null);
  let categoryName = $state('');
  let filterEffect = $state('allow');
  let filterField = $state('sender');
  let filterOperator = $state('domain_equals');
  let filterValue = $state('');
  let managementRuleType = $state<ManagementRuleBucket>('whitelist_rules');
  let managementRuleField = $state('sender');
  let managementRuleOperator = $state('domain_equals');
  let managementRuleValue = $state('');
  let llmBlacklistDescription = $state('');
  let threads = $state<MailThread[]>([]);
  let excludedThreads = $state<MailThread[]>([]);
  let selectedThread = $state<MailThread | null>(null);
  let activeThreadFilter = $state<MailThreadFilter>('all');
  let mailSearchQuery = $state('');
  let mailSearchResults = $state<MailSearchItem[]>([]);
  let mailSearchLoading = $state(false);
  let indexingManaged = $state(false);
  let incrementalPreview = $state<IncrementalMailPreview | null>(null);
  let incrementalModalOpen = $state(false);
  let incrementalLoading = $state(false);
  let incrementalScanLimit = $state(500);
  let mailInsights = $state<MailInsightsResponse | null>(null);
  let insightQuery = $state('');
  let insightLoading = $state(false);
  let structureTests = $state<MailStructureTest[]>([]);
  let improvementCandidates = $state<MailImprovementCandidate[]>([]);
  let threadListLoading = $state(false);
  let threadDetailLoading = $state(false);
  let analysisAttachments = $state<MailAnalysisAttachment[]>([]);
  let busy = $state(false);
  let message = $state('');
  let analysisCount = $state(50);
  let loadedProjectId = $state<string | null>(null);
  let callbackHandled = $state(false);
  let lastMailContextSignature = '';

  const canAnalyze = $derived(connection?.status === 'connected');
  const attachmentCount = $derived(analysis?.stats.attachments?.length || 0);
  const warningCount = $derived(analysis?.stats.structure_warning_count || analysis?.stats.llm_structure_warning_count || 0);
  const warningThreadCount = $derived(threads.filter((thread) => getThreadWarnings(thread).length > 0).length);
  const goodThreadCount = $derived(Math.max(0, threads.length - warningThreadCount));
  const localSearchResults = $derived(searchMailThreads(threads, mailSearchQuery).slice(0, 4));
  const suggestedQuestions = $derived(buildSuggestedQuestions(selectedThread));
  const searchTestCounts = $derived(countStructureTests(structureTests));

  const tabs: Array<{ id: MailWorkbenchTab; label: string }> = [
    { id: 'explore', label: '메일 탐색' },
    { id: 'settings', label: '설정' },
    { id: 'stats', label: '통계' },
    { id: 'excluded', label: '제외된 메일' },
  ];

  $effect(() => {
    if (projectId && projectId !== loadedProjectId) {
      loadedProjectId = projectId;
      const callbackMessage = consumeOAuthCallbackMessage();
      void refreshStatus(projectId, callbackMessage);
    }
  });

  $effect(() => {
    const context = buildOpenMailContext();
    const signature = JSON.stringify(context);
    if (signature === lastMailContextSignature) return;
    lastMailContextSignature = signature;
    onMailContextChange?.(context);
  });

  async function refreshStatus(targetProjectId = projectId, successMessage = '') {
    if (!targetProjectId || busy) return;
    busy = true;
    message = '';
    try {
      const res = await loadMailStatus(targetProjectId);
      connection = res.connection;
      policy = res.policy || { categories: [], filters: [] };
      managementPolicy = res.management_policy || emptyManagementPolicy();
      if (res.latest_run?.id) {
        analysis = await loadMailAnalysis(targetProjectId, res.latest_run.id);
        if (isRunningStatus(analysis.run.status)) {
          message = analysisStatusMessage(analysis);
          clearThreadData();
        } else if (analysis.run.status === 'completed') {
          await loadCompletedRunData(targetProjectId, analysis);
        } else {
          clearThreadData();
        }
      } else {
        analysis = null;
        clearThreadData();
      }
      if (successMessage) message = successMessage;
    } catch (e: any) {
      message = e.message || '메일 상태를 불러오지 못했습니다.';
    } finally {
      busy = false;
    }
  }

  async function handleConnect() {
    if (!projectId || busy) return;
    busy = true;
    message = '';
    try {
      const res = await connectGmail(projectId, window.location.href);
      connection = res.connection;
      window.location.href = res.auth_url;
    } catch (e: any) {
      message = e.message || 'Gmail 연결 실패';
      busy = false;
    }
  }

  function consumeOAuthCallbackMessage() {
    if (callbackHandled || typeof window === 'undefined') return '';
    callbackHandled = true;

    const params = new URLSearchParams(window.location.search);
    const connected = params.get('gmail');
    const error = params.get('gmail_error');
    if (!connected && !error) return '';

    params.delete('gmail');
    params.delete('gmail_error');
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
    window.history.replaceState({}, '', nextUrl);

    if (connected === 'connected') return 'Gmail 연결이 완료되었습니다.';
    if (error === 'access_denied') return 'Gmail 연결이 취소되었습니다.';
    if (error === 'missing_code') return 'Google 인증 코드가 없어 연결하지 못했습니다.';
    return 'Gmail 연결 중 오류가 발생했습니다. 다시 시도해 주세요.';
  }

  async function handleAnalyze(forceRefresh = false) {
    if (!projectId || busy) return;
    if (!canAnalyze) {
      message = '먼저 Gmail을 연결해 주세요.';
      activeTab = 'settings';
      return;
    }
    const count = normalizedAnalysisCount();
    analysisCount = count;
    busy = true;
    message = forceRefresh
      ? `Gmail에서 최근 ${count}개 thread를 다시 가져오는 중입니다.`
      : `저장된 Gmail snapshot을 우선 사용해 최근 ${count}개 thread를 분석하는 중입니다.`;
    try {
      analysis = await analyzeRecentMail(projectId, count, forceRefresh);
      message = analysisStatusMessage(analysis);
      analysis = await pollAnalysisUntilDone(projectId, analysis.run.id);
      if (analysis.run.status === 'completed') {
        await afterAnalysis(projectId);
        await loadCompletedRunData(projectId, analysis);
        activeTab = 'explore';
        message = forceRefresh
          ? `Gmail 다시 가져오기 완료: 최근 ${count}개 구조화 분석됨`
          : `최근 ${count}개 구조화 분석 완료`;
      } else {
        message = failedAnalysisMessage(analysis);
      }
      notifyMailUpdated();
    } catch (e: any) {
      message = e.message || (forceRefresh ? 'Gmail 다시 가져오기 실패' : '메일 분석 실패');
    } finally {
      busy = false;
    }
  }

  async function handlePreviewIncremental() {
    if (!projectId || busy || incrementalLoading) return;
    if (!canAnalyze) {
      message = '먼저 Gmail을 연결해 주세요.';
      activeTab = 'settings';
      return;
    }
    const scanLimit = normalizedAnalysisCount();
    incrementalScanLimit = scanLimit;
    incrementalLoading = true;
    message = `Gmail에서 마지막 처리 이후 추가된 메일을 확인하는 중입니다. 최근 ${scanLimit}개를 확인합니다.`;
    try {
      incrementalPreview = await previewIncrementalMail(projectId, scanLimit);
      incrementalModalOpen = true;
    } catch (e: any) {
      message = e.message || '추가 메일 확인 실패';
    } finally {
      incrementalLoading = false;
    }
  }

  async function handleAnalyzeIncremental() {
    if (!projectId || incrementalLoading) return;
    const scanLimit = incrementalPreview?.scan_limit || incrementalScanLimit || normalizedAnalysisCount();
    incrementalLoading = true;
    message = '추가된 메일을 구조화하는 중입니다.';
    try {
      analysis = await analyzeIncrementalMail(projectId, scanLimit);
      incrementalModalOpen = false;
      incrementalPreview = null;
      message = analysisStatusMessage(analysis);
      analysis = await pollAnalysisUntilDone(projectId, analysis.run.id);
      if (analysis.run.status === 'completed') {
        await afterAnalysis(projectId);
        await loadCompletedRunData(projectId, analysis);
        activeTab = 'explore';
        message = `추가 메일 ${analysis.stats.thread_count || 0}개 구조화 완료`;
      } else {
        message = failedAnalysisMessage(analysis);
      }
      notifyMailUpdated();
    } catch (e: any) {
      message = e.message || '추가 메일 구조화 실패';
    } finally {
      incrementalLoading = false;
    }
  }

  function closeIncrementalModal() {
    if (incrementalLoading) return;
    incrementalModalOpen = false;
  }

  async function afterAnalysis(targetProjectId: string) {
    if (analysis?.proposed_categories.length && policy.categories.length === 0) {
      policy = { ...policy, categories: analysis.proposed_categories };
    }
    if (analysis?.proposed_filters.length && policy.filters.length === 0) {
      policy = { ...policy, filters: analysis.proposed_filters };
    }
    const status = await loadMailStatus(targetProjectId);
    connection = status.connection;
    managementPolicy = status.management_policy || managementPolicy;
  }

  async function loadCompletedRunData(targetProjectId: string, loadedAnalysis: MailAnalysisResponse) {
    threadListLoading = true;
    try {
      const [threadResult, attachmentResult, excludedResult] = await Promise.all([
        loadMailAnalysisThreads(targetProjectId, loadedAnalysis.run.id),
        loadMailAnalysisAttachments(targetProjectId, loadedAnalysis.run.id),
        loadExcludedMailThreads(targetProjectId, loadedAnalysis.run.id),
      ]);
      threads = threadResult.threads || [];
      analysisAttachments = attachmentResult.attachments || [];
      excludedThreads = excludedResult.threads || [];
      if (threads.length === 0) {
        selectedThread = null;
        await loadQualityData(targetProjectId, loadedAnalysis.run.id);
        return;
      }
      const preserved = selectedThread ? threads.find((thread) => thread.id === selectedThread?.id) : null;
      await handleSelectThread(preserved || threads[0], targetProjectId, loadedAnalysis.run.id);
      await loadQualityData(targetProjectId, loadedAnalysis.run.id);
    } catch (e: any) {
      message = e.message || '메일 목록을 불러오지 못했습니다.';
    } finally {
      threadListLoading = false;
    }
  }

  async function handleSelectThread(thread: MailThread, targetProjectId = projectId, runId = analysis?.run.id) {
    selectedThread = thread;
    if (!targetProjectId || !runId) return;
    threadDetailLoading = true;
    try {
      const result = await loadMailAnalysisThread(targetProjectId, runId, thread.id);
      selectedThread = result.thread;
    } catch (e: any) {
      message = e.message || '메일 상세를 불러오지 못했습니다.';
    } finally {
      threadDetailLoading = false;
    }
  }

  function clearThreadData() {
    threads = [];
    selectedThread = null;
    analysisAttachments = [];
    excludedThreads = [];
    mailSearchResults = [];
    mailInsights = null;
    structureTests = [];
    improvementCandidates = [];
  }

  async function loadQualityData(targetProjectId: string, runId: string) {
    try {
      const [testsResult, candidatesResult] = await Promise.all([
        loadMailStructureTests(targetProjectId, runId),
        loadMailImprovementCandidates(targetProjectId, runId),
      ]);
      structureTests = testsResult.tests || [];
      improvementCandidates = candidatesResult.candidates || [];
    } catch {
      structureTests = [];
      improvementCandidates = [];
    }
  }

  function buildOpenMailContext(): OpenMailContext | null {
    return {
      active: true,
      latest_run_id: analysis?.run.id || null,
      latest_run_status: analysis?.run.status || null,
      selected_thread_id: selectedThread?.id || null,
      selected_subject: selectedThread?.subject || null,
      selected_sender: selectedThread?.sender || null,
    };
  }

  async function handleSavePolicy() {
    if (!projectId || busy) return;
    busy = true;
    message = '';
    try {
      const res = await saveMailPolicy(projectId, policy);
      policy = res.policy;
      message = '분류 기준 저장됨';
      notifyMailUpdated();
    } catch (e: any) {
      message = e.message || '분류 기준 저장 실패';
    } finally {
      busy = false;
    }
  }

  async function handleManageExcludedThread(thread: MailThread) {
    if (!projectId || !analysis?.run.id || busy) return;
    busy = true;
    message = '';
    try {
      const result = await manageMailThread(projectId, analysis.run.id, thread.id, 'managed', '제외된 메일 탭에서 수동 관리 지정');
      managementPolicy = result.management_policy;
      const refreshed = await loadMailAnalysis(projectId, analysis.run.id);
      analysis = refreshed;
      await loadCompletedRunData(projectId, refreshed);
      selectedThread = result.thread;
      activeTab = 'explore';
      message = '수동 관리 대상으로 지정했습니다.';
      notifyMailUpdated();
    } catch (e: any) {
      message = e.message || '수동 관리 지정 실패';
    } finally {
      busy = false;
    }
  }

  async function handleIndexManaged() {
    if (!projectId || !analysis?.run.id || indexingManaged) return;
    indexingManaged = true;
    message = '';
    try {
      const result = await indexManagedMail(projectId, analysis.run.id);
      message = `관리 대상 ${result.indexed_count}개를 ChromaDB에 인덱싱했습니다.`;
    } catch (e: any) {
      message = e.message || '관리 대상 인덱싱 실패';
    } finally {
      indexingManaged = false;
    }
  }

  async function handleSaveManagementPolicy() {
    if (!projectId || busy) return;
    busy = true;
    message = '';
    try {
      const result = await saveMailManagementPolicy(projectId, managementPolicy);
      managementPolicy = result.management_policy;
      if (analysis?.run.id) {
        const refreshed = await loadMailAnalysis(projectId, analysis.run.id);
        analysis = refreshed;
        if (refreshed.run.status === 'completed') {
          await loadCompletedRunData(projectId, refreshed);
        }
      }
      message = '관리 정책을 저장했습니다.';
      notifyMailUpdated();
    } catch (e: any) {
      message = e.message || '관리 정책 저장 실패';
    } finally {
      busy = false;
    }
  }

  function addManagementRule() {
    const pattern = managementRuleValue.trim();
    if (!pattern) return;
    const rule = {
      id: `${managementRuleType === 'whitelist_rules' ? 'whitelist' : 'blacklist'}-${Date.now()}`,
      field: managementRuleField,
      operator: managementRuleOperator,
      pattern,
      enabled: true,
    };
    managementPolicy = {
      ...managementPolicy,
      [managementRuleType]: [...managementPolicy[managementRuleType], rule],
    };
    managementRuleValue = '';
  }

  function removeManagementRule(bucket: ManagementRuleBucket, index: number) {
    managementPolicy = {
      ...managementPolicy,
      [bucket]: managementPolicy[bucket].filter((_, ruleIndex) => ruleIndex !== index),
    };
  }

  function addLlmBlacklistRule() {
    const description = llmBlacklistDescription.trim();
    if (!description) return;
    managementPolicy = {
      ...managementPolicy,
      llm_blacklist_rules: [
        ...managementPolicy.llm_blacklist_rules,
        { id: `llm-blacklist-${Date.now()}`, description, enabled: true },
      ],
    };
    llmBlacklistDescription = '';
  }

  function removeLlmBlacklistRule(index: number) {
    managementPolicy = {
      ...managementPolicy,
      llm_blacklist_rules: managementPolicy.llm_blacklist_rules.filter((_, ruleIndex) => ruleIndex !== index),
    };
  }

  function managementRuleLabel(rule: Record<string, any>) {
    return `${rule.field || 'sender'} ${rule.operator || 'contains'} ${rule.pattern || rule.value || ''}`.trim();
  }

  function llmRuleLabel(rule: Record<string, any>) {
    return String(rule.description || rule.pattern || 'LLM 제외 규칙');
  }

  function addCategory() {
    const name = categoryName.trim();
    if (!name) return;
    policy = { ...policy, categories: [...policy.categories, { name, keywords: [], confirmed: true }] };
    categoryName = '';
  }

  function removeCategory(index: number) {
    policy = { ...policy, categories: policy.categories.filter((_, i) => i !== index) };
  }

  function addFilter() {
    const value = filterValue.trim();
    if (!value) return;
    policy = {
      ...policy,
      filters: [
        ...policy.filters,
        {
          id: `filter-${Date.now()}`,
          effect: filterEffect,
          field: filterField,
          operator: filterOperator,
          value,
          enabled: true,
        },
      ],
    };
    filterValue = '';
  }

  function removeFilter(index: number) {
    policy = { ...policy, filters: policy.filters.filter((_, i) => i !== index) };
  }

  function handleAnalysisCountInput(event: Event) {
    const value = Number((event.currentTarget as HTMLInputElement).value);
    analysisCount = Number.isFinite(value) ? value : 50;
  }

  function normalizedAnalysisCount() {
    return Math.max(1, Math.min(500, Math.floor(Number(analysisCount) || 50)));
  }

  async function pollAnalysisUntilDone(targetProjectId: string, runId: string) {
    let current = analysis;
    for (let attempt = 0; attempt < 180; attempt += 1) {
      await delay(1500);
      current = await loadMailAnalysis(targetProjectId, runId);
      analysis = current;
      message = analysisStatusMessage(current);
      if (!isRunningStatus(current.run.status)) return current;
    }
    return current || await loadMailAnalysis(targetProjectId, runId);
  }

  function isRunningStatus(status: string) {
    return ['queued', 'fetching', 'normalizing', 'attachment_downloading', 'attachment_extracting', 'structuring', 'indexing'].includes(status);
  }

  function connectionStatusLabel() {
    if (connection?.status === 'connected') return '연결됨';
    if (connection?.status === 'needs_oauth') return '연결 필요';
    return '연결 안 됨';
  }

  function analysisStatusMessage(value: MailAnalysisResponse) {
    const status = value.run.status;
    const stage = value.stats.stage || status;
    if (status === 'completed') return '구조화 분석 완료';
    if (status === 'failed') return failedAnalysisMessage(value);
    if (stage === 'fetching') return 'Gmail snapshot을 수집하는 중입니다.';
    if (stage === 'normalizing') return '메일 thread를 정규화하는 중입니다.';
    if (stage === 'attachment_downloading') return '분석 대상 메일의 첨부파일을 받은 파일 폴더에 저장하는 중입니다.';
    if (stage === 'attachment_extracting') return '첨부파일에서 텍스트와 업무 맥락을 추출하는 중입니다.';
    if (stage === 'structuring') return 'LLM이 요청사항과 due date를 구조화하는 중입니다.';
    if (stage === 'indexing') return '분석 결과를 저장하는 중입니다.';
    return '분석 작업 대기 중입니다.';
  }

  function failedAnalysisMessage(value: MailAnalysisResponse) {
    const error = value.stats.error;
    if (error?.message) return `분석 실패 (${error.stage || value.run.status}): ${error.message}`;
    return '분석 실패: 다시 시도해 주세요.';
  }

  function formatDateTime(value: string | null | undefined) {
    if (!value) return '없음';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function notifyMailUpdated() {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('haro:mail-updated'));
    }
  }

  function handleAskWithThread(thread: MailThread) {
    const text = [
      '선택한 Gmail thread를 기준으로 답해줘.',
      `제목: ${thread.subject}`,
      `보낸사람: ${thread.sender}`,
      `카테고리: ${thread.category}`,
      `요약: ${thread.summary}`,
      '',
      '이 메일에서 내가 지금 해야 할 일과 확인해야 할 리스크를 정리해줘.',
    ].join('\n');
    onAskWithMail?.(text);
    message = '오른쪽 채팅 입력창에 선택 메일 기준 질문을 넣었습니다.';
  }

  function handleAskQuestion(question: string) {
    const context = selectedThread
      ? `선택 메일: ${selectedThread.subject}\n보낸사람: ${selectedThread.sender}\n요약: ${selectedThread.summary}\n\n`
      : '';
    onAskWithMail?.(`${context}${question}`);
    message = '오른쪽 채팅 입력창에 질문을 넣었습니다.';
  }

  async function handleSearchMail() {
    if (!projectId || !analysis?.run.id || !mailSearchQuery.trim()) return;
    mailSearchLoading = true;
    message = '';
    try {
      const result = await searchMailAnalysis(projectId, analysis.run.id, mailSearchQuery.trim(), 10);
      mailSearchResults = result.items || [];
      message = `검색 결과 ${mailSearchResults.length}개`;
    } catch (e: any) {
      message = e.message || '메일 검색 실패';
      mailSearchResults = [];
    } finally {
      mailSearchLoading = false;
    }
  }

  async function handleSelectSearchResult(item: MailSearchItem) {
    const thread = threads.find((candidate) => candidate.id === item.thread_id || candidate.id === item.id);
    if (thread) {
      await handleSelectThread(thread);
    }
  }

  async function handleSaveSearchQuality(rating: 'good' | 'warning' | 'bad') {
    if (!projectId || !analysis?.run.id || !mailSearchQuery.trim()) return;
    try {
      await saveMailStructureTest(projectId, analysis.run.id, {
        query: mailSearchQuery.trim(),
        result_kind: 'search',
        rating,
        result: { items: mailSearchResults.map(compactSearchResult) },
      });
      if (rating !== 'good') {
        await saveMailImprovementCandidate(projectId, analysis.run.id, {
          title: `검색 개선: ${mailSearchQuery.trim()}`,
          reason: rating === 'bad' ? '검색 결과가 부정확함으로 표시되었습니다.' : '검색 결과가 일부 아쉬움으로 표시되었습니다.',
          priority: rating === 'bad' ? 'high' : 'medium',
          source: 'search_test',
          query: mailSearchQuery.trim(),
          thread_ids: mailSearchResults.map((item) => item.thread_id || item.id).filter(Boolean),
          evidence: mailSearchResults.flatMap((item) => item.evidence || []).slice(0, 10),
        });
      }
      await loadQualityData(projectId, analysis.run.id);
      message = rating === 'good' ? '검색 품질 평가를 저장했습니다.' : '검색 품질 평가와 개선 후보를 저장했습니다.';
    } catch (e: any) {
      message = e.message || '검색 품질 평가 저장 실패';
    }
  }

  async function handleCreateInsights() {
    if (!projectId || !analysis?.run.id) return;
    insightLoading = true;
    message = '';
    try {
      mailInsights = await createMailInsights(projectId, analysis.run.id, insightQuery.trim());
      message = `인사이트 ${mailInsights.insights.length}개 생성`;
    } catch (e: any) {
      message = e.message || '인사이트 생성 실패';
    } finally {
      insightLoading = false;
    }
  }

  async function handleSaveInsightQuality(insight: MailInsight, rating: 'good' | 'warning' | 'bad') {
    if (!projectId || !analysis?.run.id) return;
    try {
      await saveMailStructureTest(projectId, analysis.run.id, {
        query: insightQuery.trim() || insight.title,
        result_kind: 'insight',
        rating,
        result: { insight },
      });
      if (rating !== 'good') {
        await saveMailImprovementCandidate(projectId, analysis.run.id, {
          title: `인사이트 개선: ${insight.title}`,
          reason: rating === 'bad' ? '인사이트 결과가 부정확함으로 표시되었습니다.' : insight.summary,
          priority: rating === 'bad' ? 'high' : 'medium',
          source: 'insight',
          query: insightQuery.trim() || insight.title,
          thread_ids: insight.thread_ids || [],
          evidence: insight.evidence || [],
        });
      }
      await loadQualityData(projectId, analysis.run.id);
      message = rating === 'good' ? '인사이트 품질 평가를 저장했습니다.' : '인사이트 개선 후보를 저장했습니다.';
    } catch (e: any) {
      message = e.message || '인사이트 품질 평가 저장 실패';
    }
  }

  async function handleSaveInsightCandidate(insight: MailInsight) {
    if (!projectId || !analysis?.run.id) return;
    try {
      await saveMailImprovementCandidate(projectId, analysis.run.id, {
        title: insight.title,
        reason: insight.summary,
        priority: insight.severity === 'warning' ? 'high' : 'medium',
        source: 'insight',
        query: insightQuery.trim() || insight.title,
        thread_ids: insight.thread_ids || [],
        evidence: insight.evidence || [],
      });
      await loadQualityData(projectId, analysis.run.id);
      message = '개선 후보로 저장했습니다.';
    } catch (e: any) {
      message = e.message || '개선 후보 저장 실패';
    }
  }

  function buildSuggestedQuestions(thread: MailThread | null) {
    if (thread) {
      return [
        '이 메일에서 내가 해야 할 일을 체크리스트로 정리해줘',
        '이 메일의 마감과 리스크를 알려줘',
        '이 메일과 관련된 첨부파일에서 확인할 점을 정리해줘',
      ];
    }
    return [
      '이번 분석에서 마감이 있는 요청만 모아줘',
      '구조화가 애매한 메일을 이유별로 정리해줘',
      '첨부파일이 있는 고객 요청만 요약해줘',
    ];
  }

  function delay(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function compactSearchResult(item: MailSearchItem) {
    return {
      thread_id: item.thread_id || item.id,
      subject: item.subject,
      sender: item.sender,
      score: item.score,
      matched_fields: item.matched_fields,
      evidence: item.evidence,
      retrieval: item.retrieval,
    };
  }

  function retrievalLabel(item: MailSearchItem) {
    const mode = item.retrieval?.mode || '';
    if (mode === 'hybrid_vector') {
      return `vector ${Math.round((item.retrieval?.vector_score || 0) * 100)}%`;
    }
    return mode || 'text';
  }

  function countStructureTests(tests: MailStructureTest[]) {
    return {
      good: tests.filter((test) => test.rating === 'good').length,
      warning: tests.filter((test) => test.rating === 'warning').length,
      bad: tests.filter((test) => test.rating === 'bad').length,
    };
  }

  function emptyManagementPolicy(): MailManagementPolicy {
    return {
      whitelist_rules: [],
      blacklist_rules: [],
      llm_blacklist_rules: [],
      manual_overrides: [],
    };
  }
</script>

<div class="panel mail-workbench">
  <div class="mail-header">
    <div>
      <h2>메일 관리</h2>
      <p>Gmail snapshot을 구조화하고 검색 가능한 업무 지식으로 테스트합니다.</p>
    </div>
    <div class="mail-tabs" role="tablist" aria-label="메일 관리 메뉴">
      {#each tabs as tab}
        <button
          type="button"
          class:active={activeTab === tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          onclick={() => { activeTab = tab.id; }}
        >
          {tab.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="mail-body">
    {#if activeTab === 'explore'}
      <section class="hero-section compact">
        <div>
          <span class="eyebrow">메일 탐색</span>
          <h3>최근 분석 메일 목록과 구조화 상세</h3>
          <p>분석된 thread를 필터링하고 선택한 메일의 요청사항, 일정, 첨부, 구조화 주의 이유를 확인합니다.</p>
        </div>
        <button type="button" class="primary-button" onclick={() => { activeTab = analysis ? 'stats' : 'settings'; }}>
          {analysis ? '통계 보기' : '설정에서 분석 시작'}
        </button>
      </section>
      <section class="explore-summary">
        <span>상태: {analysis ? analysisStatusMessage(analysis) : '분석 전'}</span>
        <span>thread {threads.length}</span>
        <span>첨부 {analysisAttachments.length}</span>
      </section>
      <section class="search-workbench">
        <div class="search-bar">
          <input
            placeholder="분석된 메일에서 검색: 고객명, 주제, 요청사항, 첨부파일"
            value={mailSearchQuery}
            oninput={(event) => { mailSearchQuery = event.currentTarget.value; }}
            onkeydown={(event) => { if (event.key === 'Enter') void handleSearchMail(); }}
          />
          <button type="button" class="primary-button" disabled={!analysis || !mailSearchQuery.trim() || mailSearchLoading} onclick={handleSearchMail}>
            검색
          </button>
          <button type="button" class="secondary-button" disabled={!mailSearchQuery.trim()} onclick={() => handleAskQuestion(`최근 Gmail 분석에서 "${mailSearchQuery}" 관련 메일을 찾아 근거와 함께 요약해줘`)}>
            채팅으로 묻기
          </button>
        </div>
        <div class="question-row">
          {#each suggestedQuestions as question}
            <button type="button" onclick={() => handleAskQuestion(question)}>{question}</button>
          {/each}
        </div>
        {#if mailSearchResults.length}
          <div class="api-search-results">
            <div class="section-title-row">
              <h4>검색 결과</h4>
              <div class="quality-actions">
                <button type="button" onclick={() => handleSaveSearchQuality('good')}>정확함</button>
                <button type="button" onclick={() => handleSaveSearchQuality('warning')}>일부 아쉬움</button>
                <button type="button" onclick={() => handleSaveSearchQuality('bad')}>부정확함</button>
              </div>
            </div>
            {#each mailSearchResults as item}
              <article>
                <button type="button" class="result-title" onclick={() => handleSelectSearchResult(item)}>
                  <strong>{item.subject}</strong>
                  <span>{item.sender} · {retrievalLabel(item)} · score {item.score}</span>
                </button>
                {#if item.evidence?.length}
                  <div class="evidence-list">
                    {#each item.evidence.slice(0, 3) as evidence}
                      <span>{evidence.field}: {evidence.snippet}</span>
                    {/each}
                  </div>
                {/if}
              </article>
            {/each}
          </div>
        {:else if mailSearchQuery.trim()}
          <div class="search-results">
            {#each localSearchResults as thread}
              <button type="button" onclick={() => handleSelectThread(thread)}>
                <strong>{thread.subject}</strong>
                <span>{thread.sender} · {thread.category}</span>
              </button>
            {:else}
              <p class="muted">검색 버튼을 누르면 backend 검색 결과와 근거가 표시됩니다.</p>
            {/each}
          </div>
        {/if}
      </section>
      <section class="explore-layout">
        <MailThreadList
          {threads}
          selectedThreadId={selectedThread?.id || null}
          activeFilter={activeThreadFilter}
          loading={threadListLoading}
          onFilterChange={(filter) => { activeThreadFilter = filter; }}
          onSelectThread={(thread) => handleSelectThread(thread)}
        />
        <MailThreadDetail
          thread={selectedThread}
          loading={threadDetailLoading}
          onAskWithThread={handleAskWithThread}
        />
      </section>
    {:else if activeTab === 'settings'}
      <section class="content-grid settings-grid">
        <article class="work-card span-2">
          <div class="card-header">
            <div>
              <h4>Gmail 연결</h4>
              <p>읽기 전용 권한으로 연결합니다.</p>
            </div>
            <span class="status-pill" class:connected={connection?.status === 'connected'}>{connectionStatusLabel()}</span>
          </div>
          <dl>
            <div><dt>계정</dt><dd>{connection?.email || '-'}</dd></div>
            <div><dt>권한</dt><dd>읽기 전용</dd></div>
            <div><dt>마지막 수집</dt><dd>{formatDateTime(connection?.last_sync_at)}</dd></div>
          </dl>
          <div class="button-row">
            <button type="button" class="secondary-button" disabled={busy} onclick={handleConnect}>
              <Link size={14} /> {connection?.status === 'connected' ? '다시 연결' : 'Gmail 연결'}
            </button>
            <button type="button" class="secondary-button" disabled={busy} onclick={() => refreshStatus()}>
              <RefreshCw size={14} /> 갱신
            </button>
          </div>
        </article>

        <article class="work-card span-2">
          <div class="card-header">
            <div>
              <h4>최근 분석</h4>
              <p>기본은 snapshot cache를 우선 사용하고, 다시 가져오기는 Gmail API를 호출합니다.</p>
            </div>
            <span class="status-pill">{analysis?.run.status || 'none'}</span>
          </div>
          <div class="analysis-controls">
            <label>
              분석 개수
              <input type="number" min="1" max="500" value={analysisCount} oninput={handleAnalysisCountInput} />
            </label>
            <button type="button" class="primary-button" disabled={busy || !canAnalyze} onclick={() => handleAnalyze(false)}>
              최근 {normalizedAnalysisCount()}개 분석
            </button>
            <button type="button" class="secondary-button" disabled={busy || !canAnalyze} onclick={() => handleAnalyze(true)}>
              Gmail 다시 가져오기
            </button>
            <button type="button" class="secondary-button" disabled={busy || !canAnalyze || incrementalLoading} onclick={handlePreviewIncremental}>
              {incrementalLoading ? '추가 메일 확인 중...' : '추가 메일 구조화'}
            </button>
          </div>
          {#if analysis}
            <p class="state-line">상태: {analysisStatusMessage(analysis)}</p>
          {/if}
        </article>

        <article class="work-card span-2">
          <div class="card-header">
            <div>
              <h4>관리 대상 선별과 ChromaDB</h4>
              <p>whitelist, blacklist, 수동 지정 결과를 반영해 관리 대상 메일만 벡터 검색에 넣습니다.</p>
            </div>
            <span class="status-pill">{analysis?.stats.managed_count ?? 0} managed</span>
          </div>
          <dl>
            <div><dt>화이트리스트</dt><dd>{managementPolicy.whitelist_rules.length}개</dd></div>
            <div><dt>블랙리스트</dt><dd>{managementPolicy.blacklist_rules.length}개</dd></div>
            <div><dt>LLM 제외 규칙</dt><dd>{managementPolicy.llm_blacklist_rules.length}개</dd></div>
            <div><dt>수동 지정</dt><dd>{managementPolicy.manual_overrides.length}개</dd></div>
          </dl>
          <div class="button-row">
            <button
              type="button"
              class="primary-button"
              disabled={!analysis || analysis.run.status !== 'completed' || indexingManaged}
              onclick={handleIndexManaged}
            >
              관리 대상 ChromaDB 인덱싱
            </button>
            <button
              type="button"
              class="secondary-button"
              disabled={!analysis}
              onclick={() => { activeTab = 'excluded'; }}
            >
              제외된 메일 보기
            </button>
          </div>
          <div class="management-policy-editor">
            <div class="section-title-row">
              <h4>관리 정책</h4>
              <button type="button" class="secondary-button" disabled={busy} onclick={handleSaveManagementPolicy}>
                관리 정책 저장
              </button>
            </div>
            <div class="management-rule-form">
              <select bind:value={managementRuleType} aria-label="관리 정책 유형">
                <option value="whitelist_rules">화이트리스트</option>
                <option value="blacklist_rules">블랙리스트</option>
              </select>
              <select bind:value={managementRuleField} aria-label="관리 정책 필드">
                <option value="sender">sender</option>
                <option value="domain">domain</option>
                <option value="subject">subject</option>
                <option value="recipient">recipient</option>
                <option value="attachment">attachment</option>
                <option value="body">body</option>
              </select>
              <select bind:value={managementRuleOperator} aria-label="관리 정책 조건">
                <option value="contains">contains</option>
                <option value="equals">equals</option>
                <option value="domain_equals">domain_equals</option>
                <option value="regex">regex</option>
              </select>
              <input
                placeholder="예: client.com, newsletter, noreply@..."
                value={managementRuleValue}
                oninput={(event) => { managementRuleValue = event.currentTarget.value; }}
                onkeydown={(event) => { if (event.key === 'Enter') addManagementRule(); }}
              />
              <button type="button" class="icon-button" onclick={addManagementRule}>+</button>
            </div>

            <div class="policy-columns">
              <section>
                <h5>화이트리스트</h5>
                <div class="chip-list">
                  {#each managementPolicy.whitelist_rules as rule, index}
                    <button type="button" class="chip" onclick={() => removeManagementRule('whitelist_rules', index)}>
                      {managementRuleLabel(rule)}
                    </button>
                  {:else}
                    <span class="muted">무조건 관리할 발신자/도메인을 추가하세요.</span>
                  {/each}
                </div>
              </section>
              <section>
                <h5>블랙리스트</h5>
                <div class="chip-list">
                  {#each managementPolicy.blacklist_rules as rule, index}
                    <button type="button" class="chip deny" onclick={() => removeManagementRule('blacklist_rules', index)}>
                      {managementRuleLabel(rule)}
                    </button>
                  {:else}
                    <span class="muted">관리에서 제외할 뉴스레터/광고 패턴을 추가하세요.</span>
                  {/each}
                </div>
              </section>
            </div>

            <div class="llm-rule-form">
              <div class="inline-form">
                <input
                  placeholder="LLM 제외 규칙: 예) 단순 광고성 뉴스레터 느낌이면 제외"
                  value={llmBlacklistDescription}
                  oninput={(event) => { llmBlacklistDescription = event.currentTarget.value; }}
                  onkeydown={(event) => { if (event.key === 'Enter') addLlmBlacklistRule(); }}
                />
                <button type="button" class="icon-button" onclick={addLlmBlacklistRule}>+</button>
              </div>
              <div class="chip-list">
                {#each managementPolicy.llm_blacklist_rules as rule, index}
                  <button type="button" class="chip deny" onclick={() => removeLlmBlacklistRule(index)}>
                    {llmRuleLabel(rule)}
                  </button>
                {:else}
                  <span class="muted">정적 조건으로 잡기 어려운 제외 기준을 자연어로 추가합니다.</span>
                {/each}
              </div>
            </div>
          </div>
        </article>

        <article class="work-card">
          <h4>카테고리</h4>
          <div class="inline-form">
            <input
              placeholder="카테고리"
              value={categoryName}
              oninput={(event) => { categoryName = event.currentTarget.value; }}
              onkeydown={(event) => { if (event.key === 'Enter') addCategory(); }}
            />
            <button type="button" class="icon-button" onclick={addCategory}>+</button>
          </div>
          <div class="chip-list">
            {#each policy.categories as category, index}
              <button type="button" class="chip" onclick={() => removeCategory(index)}>{category.name || 'category'}</button>
            {/each}
          </div>
        </article>

        <article class="work-card">
          <h4>필터</h4>
          <div class="select-grid">
            <select bind:value={filterEffect}><option value="allow">allow</option><option value="deny">deny</option></select>
            <select bind:value={filterField}><option value="subject">subject</option><option value="sender">sender</option><option value="recipient">recipient</option></select>
            <select bind:value={filterOperator}><option value="contains">contains</option><option value="equals">equals</option><option value="domain_equals">domain</option></select>
          </div>
          <div class="inline-form">
            <input
              placeholder="조건 값"
              value={filterValue}
              oninput={(event) => { filterValue = event.currentTarget.value; }}
              onkeydown={(event) => { if (event.key === 'Enter') addFilter(); }}
            />
            <button type="button" class="icon-button" onclick={addFilter}>+</button>
          </div>
          <div class="chip-list">
            {#each policy.filters as filter, index}
              <button type="button" class="chip" class:deny={filter.effect === 'deny'} onclick={() => removeFilter(index)}>
                {filter.effect} {filter.field} {filter.operator} {filter.value}
              </button>
            {/each}
          </div>
          <button type="button" class="wide-button" disabled={busy} onclick={handleSavePolicy}>분류 기준 저장</button>
        </article>

        <article class="work-card">
          <h4>구조화 기준 요약</h4>
          <dl>
            <div><dt>요청사항 추출</dt><dd>{analysis?.stats.extracted_action_count || 0}개</dd></div>
            <div><dt>일정 추출</dt><dd>{analysis?.stats.due_date_count || 0}개</dd></div>
            <div><dt>주의 항목</dt><dd>{warningThreadCount}개 thread</dd></div>
          </dl>
        </article>

        <article class="work-card">
          <h4>카테고리 후보</h4>
          <div class="row-list">
            {#each (analysis?.proposed_categories || []).slice(0, 6) as category}
              <div><span>{category.name || 'category'}</span><strong>{category.count || 0}</strong></div>
            {:else}
              <p class="muted">분석 후 haro가 제안한 카테고리가 표시됩니다.</p>
            {/each}
          </div>
        </article>

        <article class="work-card span-2">
          <h4>개선 후보</h4>
          <div class="insight-list">
            {#if improvementCandidates.length}
              {#each improvementCandidates.slice(0, 5) as candidate}
                <article>
                  <strong>{candidate.title}</strong>
                  <span>{candidate.priority} · {candidate.source} · {candidate.reason}</span>
                </article>
              {/each}
            {:else if !analysis}
              <p class="muted">분석 후 구조화 경고와 누락 패턴을 기반으로 개선 후보를 보여줍니다.</p>
            {:else if warningThreadCount > 0}
              <article>
                <strong>구조화 주의 항목 검토</strong>
                <span>{warningThreadCount}개 thread에 warning이 있습니다. 검색/인사이트 품질 판단에서 개선 후보로 저장할 수 있습니다.</span>
              </article>
            {:else}
              <article>
                <strong>현재 분석 범위에서는 구조화 경고가 없습니다.</strong>
                <span>자연어 검색 테스트 후 개선 후보를 추가로 판단합니다.</span>
              </article>
            {/if}
          </div>
        </article>
      </section>
    {:else if activeTab === 'stats'}
      <section class="stats-panel">
        <div class="metric-grid">
          <div><strong>{analysis?.stats.thread_count || 0}</strong><span>threads</span></div>
          <div><strong>{analysis?.stats.managed_count ?? analysis?.stats.thread_count ?? 0}</strong><span>managed</span></div>
          <div><strong>{analysis?.stats.excluded_count || 0}</strong><span>excluded</span></div>
          <div><strong>{analysis?.stats.attachment_primary_count || 0}</strong><span>attachment centered</span></div>
          <div><strong>{analysis?.stats.attachment_downloaded_count || 0}</strong><span>downloaded</span></div>
          <div><strong>{analysis?.stats.attachment_summarized_count || 0}</strong><span>attachment summarized</span></div>
          <div><strong>{analysis?.stats.attachment_extract_failed_count || 0}</strong><span>extract failed</span></div>
          <div><strong>{analysis?.stats.manual_managed_count || 0}</strong><span>manual managed</span></div>
          <div><strong>{analysis?.stats.llm_excluded_count || 0}</strong><span>LLM excluded</span></div>
          <div><strong>{goodThreadCount}</strong><span>structured good</span></div>
          <div><strong>{warningThreadCount}</strong><span>needs review</span></div>
          <div><strong>{analysis?.stats.included_count || 0}</strong><span>included</span></div>
          <div><strong>{attachmentCount}</strong><span>attachments</span></div>
          <div><strong>{analysis?.stats.extracted_action_count || 0}</strong><span>actions</span></div>
          <div><strong>{analysis?.stats.due_date_count || 0}</strong><span>due dates</span></div>
          <div><strong>{warningCount}</strong><span>warnings</span></div>
          <div><strong>{searchTestCounts.good}</strong><span>tests passed</span></div>
          <div><strong>{searchTestCounts.warning + searchTestCounts.bad}</strong><span>tests warning</span></div>
        </div>

        <section class="search-workbench insight-workbench">
          <div class="search-bar">
            <input
              placeholder="인사이트 질문: 반복 요청, 고객별 리스크, 첨부파일, 마감 집중"
              value={insightQuery}
              oninput={(event) => { insightQuery = event.currentTarget.value; }}
              onkeydown={(event) => { if (event.key === 'Enter') void handleCreateInsights(); }}
            />
            <button type="button" class="primary-button" disabled={!analysis || insightLoading} onclick={handleCreateInsights}>
              인사이트 생성
            </button>
          </div>
          {#if mailInsights}
            <p class="state-line">{mailInsights.summary}</p>
            <div class="insight-result-grid">
              {#each mailInsights.insights as insight}
                <article class:warning={insight.severity === 'warning'}>
                  <div class="section-title-row">
                    <h4>{insight.title}</h4>
                    <span class="status-pill">{insight.severity}</span>
                  </div>
                  <p>{insight.summary}</p>
                  {#if insight.evidence?.length}
                    <div class="evidence-list">
                      {#each insight.evidence.slice(0, 3) as evidence}
                        <span>{evidence.subject} · {evidence.reason}</span>
                      {/each}
                    </div>
                  {/if}
                  <div class="quality-actions">
                    <button type="button" onclick={() => handleSaveInsightQuality(insight, 'good')}>정확함</button>
                    <button type="button" onclick={() => handleSaveInsightQuality(insight, 'warning')}>일부 아쉬움</button>
                    <button type="button" onclick={() => handleSaveInsightQuality(insight, 'bad')}>부정확함</button>
                    <button type="button" onclick={() => handleSaveInsightCandidate(insight)}>개선 후보로 저장</button>
                  </div>
                </article>
              {/each}
            </div>
          {/if}
        </section>

        <div class="content-grid">
          <article class="work-card">
            <h4>보낸사람</h4>
            <div class="row-list">
              {#each (analysis?.stats.sender_counts || []).slice(0, 8) as sender}
                <div><span>{sender.sender}</span><strong>{sender.count}</strong></div>
              {:else}
                <p class="muted">분석 후 표시됩니다.</p>
              {/each}
            </div>
          </article>
          <article class="work-card">
            <h4>카테고리</h4>
            <div class="row-list">
              {#each (analysis?.stats.categories || []).slice(0, 8) as category}
                <div><span>{category.name}</span><strong>{category.count}</strong></div>
              {:else}
                <p class="muted">분석 후 표시됩니다.</p>
              {/each}
            </div>
          </article>
          <article class="work-card">
            <h4>인사이트 요약</h4>
            <div class="insight-list">
              {#if analysis?.stats.sender_counts?.length}
                <article>
                  <strong>가장 많은 발신자</strong>
                  <span>{analysis.stats.sender_counts[0].sender} · {analysis.stats.sender_counts[0].count}개 thread</span>
                </article>
              {/if}
              {#if analysis?.stats.due_date_count}
                <article>
                  <strong>마감이 있는 요청</strong>
                  <span>{analysis.stats.due_date_count}개 일정 표현이 추출되었습니다.</span>
                </article>
              {/if}
              {#if warningThreadCount}
                <article>
                  <strong>검토 필요</strong>
                  <span>{warningThreadCount}개 thread는 구조화 주의 이유가 있습니다.</span>
                </article>
              {/if}
              {#if !analysis}
                <p class="muted">분석 후 반복 요청, 마감 집중, 구조화 경고 요약이 표시됩니다.</p>
              {/if}
            </div>
          </article>
          <article class="work-card">
            <h4>테스트 결과</h4>
            <div class="row-list">
              <div><span>성공</span><strong>{searchTestCounts.good}</strong></div>
              <div><span>주의</span><strong>{searchTestCounts.warning}</strong></div>
              <div><span>실패</span><strong>{searchTestCounts.bad}</strong></div>
            </div>
            {#if structureTests.length}
              <div class="insight-list test-list">
                {#each structureTests.slice(0, 5) as test}
                  <article>
                    <strong>{test.rating} · {test.result_kind}</strong>
                    <span>{test.query}</span>
                  </article>
                {/each}
              </div>
            {:else}
              <p class="muted">검색/인사이트 결과를 평가하면 테스트 결과가 여기에 쌓입니다.</p>
            {/if}
          </article>

          <article class="work-card span-2">
            <h4>저장된 개선 후보</h4>
            <div class="insight-list">
              {#each improvementCandidates as candidate}
                <article>
                  <strong>{candidate.title}</strong>
                  <span>{candidate.priority} · {candidate.source} · {candidate.reason}</span>
                </article>
              {:else}
                <p class="muted">아직 저장된 개선 후보가 없습니다.</p>
              {/each}
            </div>
          </article>
        </div>
      </section>
    {:else}
      <section class="excluded-panel">
        <section class="hero-section compact">
          <div>
            <span class="eyebrow">제외된 메일</span>
            <h3>관리 대상에서 빠진 메일 검토</h3>
            <p>자동 제외된 메일의 사유를 확인하고, 업무 지식으로 남겨야 할 thread는 수동으로 관리 대상으로 지정합니다.</p>
          </div>
          <button type="button" class="secondary-button" disabled={!analysis} onclick={() => refreshStatus()}>
            <RefreshCw size={14} /> 갱신
          </button>
        </section>

        <div class="excluded-list">
          {#each excludedThreads as thread}
            <article>
              <div>
                <span class="status-pill">{thread.metadata?.decision_source || 'excluded'}</span>
                <h4>{thread.subject}</h4>
                <p>{thread.sender} · {formatDateTime(thread.received_at)}</p>
                <p>{thread.metadata?.decision_reason || '관리 제외로 판정됨'}</p>
                {#if thread.metadata?.attachment_signals?.count}
                  <p>첨부 {thread.metadata.attachment_signals.count}개 · {thread.metadata.attachment_signals.summary_status}</p>
                {/if}
              </div>
              <button type="button" class="primary-button" disabled={busy} onclick={() => handleManageExcludedThread(thread)}>
                관리 지정
              </button>
            </article>
          {:else}
            <article class="empty-excluded">
              <h4>제외된 메일이 없습니다.</h4>
              <p>분석이 완료되면 blacklist/LLM 제외 규칙으로 빠진 메일이 여기에 표시됩니다.</p>
            </article>
          {/each}
        </div>
      </section>
    {/if}
  </div>

  {#if message}
    <div class="mail-message">{message}</div>
  {/if}

  {#if incrementalModalOpen && incrementalPreview}
    <div class="modal-backdrop" role="presentation">
      <div class="incremental-modal" role="dialog" aria-modal="true" aria-labelledby="incremental-title">
        <div class="section-title-row">
          <div>
            <span class="eyebrow">추가 메일 구조화</span>
            <h3 id="incremental-title">마지막 처리 이후 추가된 메일</h3>
          </div>
          <span class="status-pill">{incrementalPreview.new_count}개</span>
        </div>
        <dl>
          <div><dt>마지막 처리 시각</dt><dd>{formatDateTime(incrementalPreview.since_received_at)}</dd></div>
          <div><dt>확인한 최근 thread</dt><dd>{incrementalPreview.fetched_count} / {incrementalPreview.scan_limit}</dd></div>
          <div><dt>Gmail 확인 시각</dt><dd>{formatDateTime(incrementalPreview.fetched_at)}</dd></div>
        </dl>
        {#if incrementalPreview.threads.length}
          <div class="incremental-preview-list">
            {#each incrementalPreview.threads.slice(0, 5) as thread}
              <article>
                <strong>{thread.subject}</strong>
                <span>{thread.sender} · {formatDateTime(thread.received_at)} · 첨부 {thread.attachment_count}</span>
              </article>
            {/each}
            {#if incrementalPreview.threads.length > 5}
              <p class="muted">외 {incrementalPreview.threads.length - 5}개가 더 있습니다.</p>
            {/if}
          </div>
        {:else}
          <p class="muted">마지막 처리 이후 추가된 메일이 없습니다.</p>
        {/if}
        <p class="state-line">진행할까요?</p>
        <div class="modal-actions">
          <button type="button" class="secondary-button" disabled={incrementalLoading} onclick={closeIncrementalModal}>
            아니요
          </button>
          <button
            type="button"
            class="primary-button"
            disabled={incrementalLoading || incrementalPreview.new_count === 0}
            onclick={handleAnalyzeIncremental}
          >
            예, 구조화 진행
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .panel { display: flex; flex-direction: column; border-right: 1px solid var(--color-border); background: var(--color-surface); }
  .mail-workbench { flex: 1; min-width: 0; }
  .mail-header { display: flex; align-items: stretch; justify-content: space-between; gap: 1rem; min-height: 58px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); padding: 0.7rem 1rem; }
  .mail-header h2 { margin: 0; color: var(--color-text); font-size: 1rem; line-height: 1.3; }
  .mail-header p { margin: 0.2rem 0 0; color: var(--color-text-muted); font-size: 0.76rem; }
  .mail-tabs { display: flex; align-items: center; gap: 0.25rem; flex-shrink: 0; }
  .mail-tabs button { border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-muted); padding: 0.38rem 0.65rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .mail-tabs button:hover { background: var(--color-sidebar-strong); color: var(--color-text); }
  .mail-tabs button.active { border-color: var(--color-pink); background: var(--color-pink-soft); color: var(--color-text); font-weight: 700; }
  .mail-body { flex: 1; min-height: 0; overflow: auto; background: var(--color-canvas); padding: 1rem; }
  .hero-section { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--color-border-soft); padding-bottom: 1rem; }
  .hero-section.compact { padding-bottom: 0.75rem; }
  .eyebrow { color: var(--color-pink); font-size: 0.72rem; font-weight: 800; }
  .hero-section h3 { margin: 0.25rem 0; color: var(--color-text); font-size: 1.25rem; }
  .hero-section p, .work-card p, .state-line, .muted { color: var(--color-text-muted); font-size: 0.78rem; line-height: 1.55; }
  .content-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.8rem; margin-top: 0.9rem; }
  .explore-summary { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.75rem 0; color: var(--color-text-muted); font-size: 0.74rem; }
  .explore-summary span { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.25rem 0.5rem; }
  .search-workbench { display: grid; gap: 0.55rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.7rem; margin-bottom: 0.8rem; }
  .search-bar { display: flex; gap: 0.45rem; align-items: center; }
  .search-bar input { flex: 1; }
  .question-row { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .question-row button, .search-results button { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar-strong); color: var(--color-text-muted); cursor: pointer; font: inherit; }
  .question-row button { padding: 0.28rem 0.45rem; font-size: 0.72rem; }
  .question-row button:hover, .search-results button:hover { border-color: var(--color-pink); color: var(--color-text); }
  .search-results { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.45rem; }
  .search-results button { display: grid; gap: 0.18rem; min-width: 0; padding: 0.5rem; text-align: left; }
  .search-results strong, .search-results span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .search-results strong { color: var(--color-text); font-size: 0.76rem; }
  .search-results span { font-size: 0.68rem; }
  .api-search-results, .insight-result-grid { display: grid; gap: 0.55rem; }
  .api-search-results article, .insight-result-grid article { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.6rem; }
  .insight-result-grid article.warning { border-color: var(--color-warning-soft); background: var(--color-warning-soft); }
  .result-title { display: grid; gap: 0.2rem; width: 100%; border: 0; background: transparent; color: var(--color-text); padding: 0; text-align: left; cursor: pointer; }
  .result-title strong, .result-title span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .result-title strong { font-size: 0.8rem; }
  .result-title span { color: var(--color-text-muted); font-size: 0.7rem; }
  .evidence-list { display: grid; gap: 0.25rem; margin-top: 0.45rem; }
  .evidence-list span { color: var(--color-text-muted); font-size: 0.7rem; line-height: 1.45; }
  .section-title-row { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; }
  .section-title-row h4 { margin: 0; }
  .quality-actions { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.55rem; }
  .quality-actions button { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-muted); padding: 0.22rem 0.45rem; font: inherit; font-size: 0.68rem; cursor: pointer; }
  .quality-actions button:hover { border-color: var(--color-pink); color: var(--color-text); }
  .explore-layout { display: grid; grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.1fr); gap: 0.8rem; min-height: 0; height: min(720px, calc(100vh - 230px)); }
  .settings-grid { align-items: start; }
  .span-2 { grid-column: span 2; }
  .work-card { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.85rem; }
  .work-card h4 { margin: 0 0 0.55rem; color: var(--color-text); font-size: 0.9rem; }
  .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.6rem; }
  .card-header h4 { margin-bottom: 0.15rem; }
  .card-header p { margin: 0; }
  dl { display: grid; gap: 0.45rem; margin: 0; }
  dl div { display: flex; justify-content: space-between; gap: 1rem; color: var(--color-text-muted); font-size: 0.78rem; }
  dt { color: var(--color-text-subtle); }
  dd { margin: 0; min-width: 0; overflow: hidden; color: var(--color-text); text-overflow: ellipsis; white-space: nowrap; }
  .button-row, .analysis-controls, .inline-form { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
  .button-row, .analysis-controls { margin-top: 0.75rem; }
  .analysis-controls label { display: grid; gap: 0.25rem; color: var(--color-text-muted); font-size: 0.72rem; }
  input, select { min-width: 0; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); padding: 0.42rem 0.5rem; font: inherit; font-size: 0.78rem; }
  .analysis-controls input { width: 86px; }
  .inline-form input { flex: 1; }
  .select-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.35rem; margin-bottom: 0.45rem; }
  .primary-button, .secondary-button, .wide-button, .icon-button { border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); cursor: pointer; font: inherit; }
  .primary-button { border-color: var(--color-pink); background: var(--color-pink); color: #fff; padding: 0.45rem 0.75rem; font-size: 0.78rem; font-weight: 800; }
  .secondary-button { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.42rem 0.65rem; font-size: 0.78rem; }
  .wide-button { width: 100%; margin-top: 0.6rem; padding: 0.45rem; font-size: 0.78rem; }
  .icon-button { width: 34px; min-height: 34px; }
  button:disabled { cursor: default; opacity: 0.5; }
  .status-pill { flex-shrink: 0; border-radius: 999px; background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.18rem 0.55rem; font-size: 0.72rem; font-weight: 700; }
  .status-pill.connected { background: var(--color-success-soft); color: var(--color-success); }
  .metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.65rem; }
  .metric-grid div { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.8rem; }
  .metric-grid strong { display: block; color: var(--color-text); font-size: 1.35rem; }
  .metric-grid span { color: var(--color-text-muted); font-size: 0.72rem; }
  .insight-workbench { margin-top: 0.8rem; }
  .chip-list { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.55rem; }
  .chip { border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar-strong); color: var(--color-text-muted); padding: 0.24rem 0.45rem; font-size: 0.7rem; cursor: pointer; }
  .chip.deny { color: var(--color-danger); border-color: var(--color-danger-soft); }
  .management-policy-editor { display: grid; gap: 0.75rem; margin-top: 0.85rem; border-top: 1px solid var(--color-border-soft); padding-top: 0.8rem; }
  .management-policy-editor h4, .management-policy-editor h5 { margin: 0; color: var(--color-text); }
  .management-policy-editor h5 { font-size: 0.76rem; }
  .management-rule-form { display: grid; grid-template-columns: 150px 130px 150px minmax(180px, 1fr) 34px; gap: 0.35rem; align-items: center; }
  .policy-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
  .policy-columns section, .llm-rule-form { min-width: 0; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.6rem; }
  .row-list { display: grid; gap: 0.4rem; }
  .row-list div { display: flex; justify-content: space-between; gap: 1rem; color: var(--color-text-muted); font-size: 0.78rem; }
  .row-list span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row-list strong { color: var(--color-text); }
  .insight-list { display: grid; gap: 0.5rem; }
  .insight-list article { display: grid; gap: 0.2rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.55rem; }
  .insight-list strong { color: var(--color-text); font-size: 0.78rem; }
  .insight-list span { color: var(--color-text-muted); font-size: 0.72rem; line-height: 1.45; }
  .test-list { margin-top: 0.6rem; }
  .excluded-panel { display: grid; gap: 0.8rem; }
  .excluded-list { display: grid; gap: 0.65rem; }
  .excluded-list article { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-surface); padding: 0.85rem; }
  .excluded-list h4 { margin: 0.35rem 0 0.25rem; color: var(--color-text); font-size: 0.9rem; line-height: 1.35; }
  .excluded-list p { margin: 0.16rem 0; color: var(--color-text-muted); font-size: 0.74rem; line-height: 1.45; }
  .excluded-list .empty-excluded { display: block; text-align: center; }
  .modal-backdrop { position: fixed; inset: 0; z-index: 30; display: grid; place-items: center; background: rgba(15, 23, 42, 0.28); padding: 1rem; }
  .incremental-modal { display: grid; gap: 0.75rem; width: min(520px, 100%); max-height: min(680px, calc(100vh - 2rem)); overflow: auto; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18); padding: 1rem; }
  .incremental-modal h3 { margin: 0.2rem 0 0; color: var(--color-text); font-size: 1.05rem; }
  .incremental-preview-list { display: grid; gap: 0.45rem; }
  .incremental-preview-list article { display: grid; gap: 0.18rem; border: 1px solid var(--color-border-soft); border-radius: var(--radius-sm); background: var(--color-sidebar); padding: 0.55rem; }
  .incremental-preview-list strong { min-width: 0; overflow: hidden; color: var(--color-text); font-size: 0.8rem; text-overflow: ellipsis; white-space: nowrap; }
  .incremental-preview-list span { min-width: 0; overflow: hidden; color: var(--color-text-muted); font-size: 0.72rem; text-overflow: ellipsis; white-space: nowrap; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 0.45rem; }
  .mail-message { flex-shrink: 0; border-top: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-text-muted); padding: 0.65rem 1rem; font-size: 0.78rem; }

  @media (max-width: 1180px) {
    .mail-header { flex-direction: column; align-items: stretch; }
    .mail-tabs { overflow-x: auto; padding-bottom: 0.1rem; }
    .explore-layout { grid-template-columns: 1fr; height: auto; }
    .content-grid, .search-results { grid-template-columns: 1fr; }
    .span-2 { grid-column: span 1; }
  }

  @media (max-width: 760px) {
    .mail-body { padding: 0.65rem; }
    .hero-section, .search-bar, .analysis-controls { align-items: stretch; flex-direction: column; }
    .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .select-grid { grid-template-columns: 1fr; }
    .management-rule-form, .policy-columns { grid-template-columns: 1fr; }
    .excluded-list article { flex-direction: column; }
    .modal-actions { flex-direction: column-reverse; }
    .quality-actions button { flex: 1 1 7rem; }
    .primary-button, .secondary-button { justify-content: center; }
  }
</style>

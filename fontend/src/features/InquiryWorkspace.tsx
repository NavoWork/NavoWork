import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  GitBranch,
  History,
  LayoutGrid,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  ShieldCheck,
  Sparkles,
  Square,
  TriangleAlert,
} from 'lucide-react';
import { api, ApiError, mode } from '../api';
import type {
  BusinessStatus,
  ExportResult,
  Inquiry,
  Message,
  Revision,
  ReviewResult,
  Run,
  Session,
  Source,
  SourceRef,
} from '../api/types';
import { EmptyState, ErrorNotice, Loading, Modal, StatusBadge } from '../components/ui';
import { ReplyEditor, type DraftState } from './inquiry-replies';
import { InquiryResult } from './InquiryResult';
import { InquiryRunActivity } from './InquiryRunActivity';
import {
  inquiryAssetsChangedEvent,
  resultSnapshot,
  type SavedResult,
} from './inquiry-canvas-model';
import { InquiryCanvas } from './InquiryCanvas';
import { InquiryChatHeading, InquiryChatTranscript } from './InquiryChatTranscript';
import { InquiryComposer } from './InquiryComposer';
import { useAvailableSkills } from './skill-catalog';
import { InvocationContext } from './InvocationContext';
import {
  emptyComposerContext,
  restoreContext,
  runContext,
  type ComposerContext,
} from './inquiry-context';
import { GenerateNodeDialog, type GenerationNode } from './GenerateNodeDialog';
import { CustomerContextCard, channelLabels } from './CustomerContextCard';
import { ResizeHandle } from '../components/ResizeHandle';
import './inquiry.css';

const money = (v: number | null | undefined) =>
  v == null
    ? '待确认'
    : `$${(v / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const date = (v: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(v));
function readPref<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}
function writePref(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function InquiryWorkspace({
  inquiryId,
  session,
  onChanged,
}: {
  inquiryId: string;
  session: Session;
  onChanged: () => void;
}) {
  const base = `/workspaces/${session.workspace.id}`;
  const path = `${base}/inquiries/${encodeURIComponent(inquiryId)}`;
  const scope = `${session.user.id}:${session.workspace.id}:${inquiryId}`;
  const location = useLocation();
  const active = location.pathname === `/inquiries/${encodeURIComponent(inquiryId)}`;
  const prefKey = `easywork:view:${scope}`;
  const initial = useRef(
    readPref(prefKey, {
      input: '',
      composerContext: emptyComposerContext(),
      deferredResults: [] as number[],
      revision: null as number | null,
      lastRunId: '',
      selectedAssets: null as string[] | null,
      assistantWidth: null as number | null,
    }),
  );
  const [input, setInput] = useState(initial.current.input);
  const catalog = useAvailableSkills(session);
  const [composerContext, setComposerContext] = useState<ComposerContext>(
    initial.current.composerContext || emptyComposerContext(),
  );
  const [draftStored, setDraftStored] = useState(true);
  const [deferredResults, setDeferredResults] = useState<number[]>(
    initial.current.deferredResults || [],
  );
  const [savedResults, setSavedResults] = useState<number[]>([]);
  const [saveResultRequest, setSaveResultRequest] = useState<{
    result: SavedResult;
    seq: number;
  } | null>(null);
  const [revisionNumber, setRevisionNumber] = useState<number | null>(initial.current.revision);
  const [lastRunId, setLastRunId] = useState(initial.current.lastRunId);
  const [selectedAssets, setSelectedAssets] = useState<string[] | null>(
    initial.current.selectedAssets ?? null,
  );
  const [mobilePane, setMobilePane] = useState<'chat' | 'results'>('chat');
  const [documentRequest, setDocumentRequest] = useState<{ id: string; seq: number } | null>(null);
  const openDocument = (id: string) => {
    setMobilePane('chat');
    setDocumentRequest((old) => ({ id, seq: (old?.seq || 0) + 1 }));
  };
  const showAIChat = () => {
    setResultsOpen(true);
    setMobilePane('results');
  };
  const [resultsOpen, setResultsOpen] = useState(true);
  const [assistantWidth, setAssistantWidth] = useState<number | null>(
    typeof initial.current.assistantWidth === 'number' &&
      Number.isFinite(initial.current.assistantWidth)
      ? initial.current.assistantWidth
      : null,
  );
  const columnsRef = useRef<HTMLDivElement>(null);
  const assistantRef = useRef<HTMLElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const [modal, setModal] = useState<
    'original' | 'waiting' | 'close' | 'accept' | 'relations' | null
  >(null);
  const [source, setSource] = useState<SourceRef | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [generation, setGeneration] = useState<{
    node: GenerationNode;
    instruction?: string;
  } | null>(null);
  const [draftState, setDraftState] = useState<DraftState>({
    revision: null,
    versions: {},
    pending: true,
  });
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [draftRefresh, setDraftRefresh] = useState(0);
  const queryClient = useQueryClient();
  useEffect(() => {
    window.dispatchEvent(new CustomEvent(inquiryAssetsChangedEvent, { detail: scope }));
  }, [scope, draftState]);
  const changedRef = useRef(onChanged);
  changedRef.current = onChanged;
  const queryKey = ['inquiry', scope];
  const detail = useQuery({
    queryKey,
    enabled: active,
    queryFn: async ({ signal }) => {
      const [inquiry, messages, revisions] = await Promise.all([
        api.get<Inquiry>(path, signal),
        api.get<{ items: Message[] }>(`${path}/messages`, signal),
        api.get<{ items: Revision[] }>(`${path}/revisions`, signal),
      ]);
      return { inquiry, messages: messages.items, revisions: revisions.items };
    },
  });
  const inquiry = detail.data?.inquiry;
  const selectedNumber = revisionNumber ?? inquiry?.currentRevision;
  const revision = detail.data?.revisions.find((r) => r.number === selectedNumber);
  const draftsPending = draftState.pending || draftState.revision !== revision?.number;
  const history = !!inquiry && selectedNumber !== inquiry.currentRevision;
  const activeRunId = inquiry?.activeRunId || inquiry?.pendingRunId || lastRunId;
  const runQuery = useQuery({
    queryKey: ['run', scope, activeRunId],
    enabled: active && !!activeRunId,
    queryFn: ({ signal }) => api.get<Run>(`${base}/runs/${activeRunId}`, signal),
    refetchInterval: (q) =>
      !q.state.data || ['queued', 'running'].includes(q.state.data.status) ? 900 : false,
    retry: false,
  });
  const run = runQuery.data;
  useEffect(() => {
    const messages = messagesRef.current;
    if (messages) messages.scrollTop = messages.scrollHeight;
  }, [detail.data?.messages.length, run?.id, selectedNumber, mobilePane, resultsOpen]);
  const running = !!inquiry?.activeRunId || (!!run && ['queued', 'running'].includes(run.status));
  const readOnly =
    history ||
    inquiry?.businessStatus === 'done' ||
    inquiry?.businessStatus === 'waiting' ||
    running;
  const handledRun = useRef('');
  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['inquiry', scope] });
    changedRef.current();
  }, [queryClient, scope]);
  useEffect(() => {
    setDraftStored(
      writePref(prefKey, {
        input,
        composerContext,
        deferredResults,
        revision: revisionNumber,
        lastRunId,
        selectedAssets,
        assistantWidth,
      }),
    );
  }, [
    input,
    composerContext,
    deferredResults,
    revisionNumber,
    lastRunId,
    selectedAssets,
    assistantWidth,
    prefKey,
  ]);
  useEffect(() => {
    if (
      run &&
      !['queued', 'running'].includes(run.status) &&
      handledRun.current !== `${run.id}:${run.status}`
    ) {
      handledRun.current = `${run.id}:${run.status}`;
      void refresh();
      if (run.status === 'succeeded') {
        setRevisionNumber(null);
        setReview(null);
        setSelectedAssets(null);
      }
    }
  }, [run, refresh]);
  useEffect(() => {
    setReview(null);
    setExportResult(null);
  }, [selectedNumber, draftState.versions['en-US'], draftState.versions['es-MX'], draftsPending]);
  async function operate(task: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      await task();
    } catch (e) {
      setError(e);
      if (
        e instanceof ApiError &&
        ['REVISION_CONFLICT', 'METADATA_CONFLICT', 'RUN_IN_PROGRESS'].includes(e.code)
      ) {
        if (e.code === 'RUN_IN_PROGRESS' && typeof e.details?.runId === 'string')
          setLastRunId(e.details.runId);
        await refresh();
      }
    } finally {
      setBusy(false);
    }
  }
  const deleteMessage = async (message: Message) => {
    if (!window.confirm('删除这条消息？')) return;
    await operate(async () => {
      await api.delete(`${path}/messages/${message.id}`);
      await refresh();
    });
  };
  const clearMessages = async () => {
    if (!window.confirm('清空当前会话？此操作不可撤销。')) return;
    await operate(async () => {
      await api.delete(`${path}/messages`);
      await refresh();
    });
  };
  async function startRun(
    action = inquiry?.currentRevision ? 'revise' : 'analyze',
    evidence?: string,
  ) {
    if (!inquiry || running || (draftsPending && !!revision)) return;
    await operate(async () => {
      const canvas =
        mode === 'real'
          ? await api.get<{ state: { files?: { serverFileId?: string }[] } | null }>(
              `${path}/canvas`,
            )
          : null;
      const canvasFileIds =
        canvas?.state?.files?.flatMap((file) => (file.serverFileId ? [file.serverFileId] : [])) ??
        [];
      const context = runContext(composerContext, catalog.skills);
      const instruction =
        evidence ||
        input.trim() ||
        (action === 'analyze'
          ? '分析客户原始询盘，提取需求与待确认项'
          : '根据当前事实更新方案与回复');
      if (mode === 'real' && composerContext.knowledge.some((doc) => !doc.sourceVersionId))
        throw new Error('引用中包含本机旧资料，请移除后从团队知识库重新选择。');
      const sourceVersionIds = [
        ...new Set([
          ...(revision?.sourceRefs.map((s) => s.sourceVersionId) ?? []),
          ...composerContext.knowledge.flatMap((doc) =>
            doc.sourceVersionId ? [doc.sourceVersionId] : [],
          ),
        ]),
      ];
      const r = await api.post<Run>(`${path}/runs`, {
        ...(mode === 'real' ? { canvasFileIds } : {}),
        baseRevision: inquiry.currentRevision,
        action,
        context,
        assetVersionIds: selectedAssets ?? revision?.assetRefs ?? [],
        ...(mode === 'real' ? { sourceVersionIds } : {}),
        instruction:
          mode === 'real' && context?.skills.length
            ? `${instruction}\n\n本次技能要求：\n${context.skills.map((skill) => `${skill.name}：${skill.instructions.join('；')}`).join('\n')}`
            : instruction,
        ...(run?.status === 'needs_input'
          ? {
              replyToRunId: run.id,
              answers: run.clarification?.questions.map((q) => ({
                questionId: q.id,
                value: input.trim(),
              })),
            }
          : {}),
        ...(evidence && revision
          ? {
              proposalRef: {
                proposalId: revision.proposal.proposalId,
                version: revision.proposal.version,
              },
              acceptanceEvidence: evidence,
            }
          : {}),
      });
      setLastRunId(r.runId || r.id);
      setInput('');
      setComposerContext(emptyComposerContext());
      showAIChat();
      setModal(null);
      setRevisionNumber(null);
      queryClient.setQueryData(['run', scope, r.runId || r.id], r);
      await refresh();
    });
  }
  async function restoreRevision(number: number, target: string): Promise<number | undefined> {
    if (!inquiry || running || busy) return;
    let created: number | undefined;
    await operate(async () => {
      const result = await api.post<Revision>(`${path}/revisions/${number}/restore`, {
        baseRevision: inquiry.currentRevision,
        target,
      });
      created = result.number;
      setRevisionNumber(null);
      setLastRunId('');
      setDraftRefresh((v) => v + 1);
      setReview(null);
      await refresh();
      setNotice(
        `已从 V${number} 恢复${target === 'all' ? '全部节点' : '所选节点'}到 V${result.number}，可以继续编辑。历史仍保留。`,
      );
    });
    return created;
  }
  async function transition(to: BusinessStatus, extra: Record<string, unknown> = {}) {
    if (!inquiry) return;
    await operate(async () => {
      await api.post(`${path}/status-transitions`, {
        from: inquiry.businessStatus,
        to,
        metadataVersion: inquiry.metadataVersion,
        ...extra,
      });
      setModal(null);
      await refresh();
    });
  }
  async function requestReview() {
    if (!revision || draftsPending) return;
    await operate(async () => {
      const result = await api.post<ReviewResult>(`${path}/reviews`, {
        revision: revision.number,
        draftVersions: draftState.versions,
      });
      setReview(result);
      setDraftRefresh((v) => v + 1);
      setNotice(
        result.status === 'passed'
          ? '复核通过，已披露的待确认项将随草稿保留。'
          : '复核发现问题，请按提示修改回复。',
      );
    });
  }
  async function requestExport() {
    if (!revision || draftsPending) return;
    await operate(async () => {
      const result = await api.post<ExportResult>(`${path}/exports`, {
        revision: revision.number,
        draftVersions: draftState.versions,
        assetVersionIds: revision.assetRefs,
        format: 'html',
      });
      setExportResult(result);
    });
  }
  useEffect(() => {
    if (exportResult?.status !== 'pending') return;
    let cancelled = false;
    const timer = setInterval(() => {
      api
        .get<ExportResult>(`${base}/exports/${exportResult.exportId}`)
        .then((v) => {
          if (!cancelled) setExportResult(v);
        })
        .catch((e) => {
          if (!cancelled) setError(e);
        });
    }, 1500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [exportResult, base]);
  async function download() {
    if (!exportResult || !revision) return;
    await operate(async () => {
      const blob =
        exportResult.html && mode === 'mock'
          ? new Blob([exportResult.html], { type: 'text/html;charset=utf-8' })
          : await api.download(`${base}/exports/${exportResult.exportId}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Navowork-${inquiryId}-V${revision.number}-草稿.html`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  if (detail.isPending) return <Loading label="正在打开询盘工作区" />;
  if (!inquiry)
    return (
      <ErrorNotice error={detail.error || '未找到该询盘'} onRetry={() => void detail.refetch()} />
    );
  const canWrite = !readOnly && !busy;
  const canSend = canWrite && (!revision || !draftsPending);
  const resultMessage =
    revision &&
    [...(detail.data?.messages || [])]
      .reverse()
      .find((message) => message.role === 'assistant' && message.runId === revision.runId);
  const resultPreview = revision ? (
    <InquiryResult
      key={revision.number}
      revision={revision}
      draftState={draftState}
      draftsPending={draftsPending}
      base={base}
      path={path}
      scope={scope}
      readOnly={readOnly}
      busy={busy}
      history={history}
      selectedAssets={selectedAssets}
      onSelectAssets={setSelectedAssets}
      onSource={setSource}
      openDocument={openDocument}
      onAccept={() => setModal('accept')}
      saved={savedResults.includes(revision.number)}
      deferred={deferredResults.includes(revision.number)}
      onDefer={() => setDeferredResults((values) => [...values, revision.number])}
      onSave={() => {
        openDocument('result:hub');
      }}
    />
  ) : null;
  return (
    <div className={`iw-page iw-canvas-page ${resultsOpen ? '' : 'iw-focus-chat'}`}>
      <header className="iw-heading">
        <div className="iw-title">
          <h1>{inquiry.title}</h1>
          <StatusBadge status={inquiry.businessStatus} />
        </div>
        <div className="iw-actions">
          <button
            className="button"
            disabled={!revision || draftsPending || busy}
            onClick={requestExport}
          >
            <Download size={14} />
            导出草稿材料
          </button>
          <button
            className="icon-button iw-results-toggle"
            aria-label={resultsOpen ? '收起 AI 面板' : '展开 AI 面板'}
            aria-expanded={resultsOpen}
            aria-controls={`results-${inquiryId}`}
            title={resultsOpen ? '收起 AI 面板' : '展开 AI 面板'}
            onClick={() => setResultsOpen((value) => !value)}
          >
            {resultsOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
          </button>
        </div>
      </header>
      <ErrorNotice
        error={error || detail.error}
        onRetry={
          error
            ? () => {
                setError(undefined);
                void refresh();
              }
            : () => void detail.refetch()
        }
      />
      {notice && (
        <div role="status" className="iw-notice">
          <Check size={14} />
          {notice}
        </div>
      )}
      {history && (
        <div className="iw-readonly">
          <History size={16} />
          正在查看 V{revisionNumber} 历史快照，内容只读。
          <button onClick={() => setRevisionNumber(null)}>回到当前版本</button>
          {mode === 'real' && (
            <button
              disabled={
                busy ||
                running ||
                inquiry.businessStatus === 'done' ||
                inquiry.businessStatus === 'waiting'
              }
              onClick={() => void restoreRevision(selectedNumber!, 'all')}
            >
              从此版本继续编辑
            </button>
          )}
        </div>
      )}
      {inquiry.businessStatus === 'done' && (
        <div className="iw-readonly">
          <CheckCheck size={16} />
          已结束 · {inquiry.closeReason || '本次工作已停止推进'}
          <button disabled={busy} onClick={() => transition('active')}>
            重新打开
          </button>
        </div>
      )}
      {inquiry.businessStatus === 'waiting' && (
        <div className="iw-readonly">
          <Clock3 size={16} />
          待确认 · {inquiry.waiting?.waitingReason}
          <button disabled={busy} onClick={() => transition('active')}>
            恢复处理
          </button>
        </div>
      )}
      {exportResult && (
        <div className="iw-export-status" role="status">
          <FileText size={16} />
          {exportResult.status === 'ready'
            ? '指定版本的草稿材料已准备好，导出不会发送给客户。'
            : exportResult.status === 'failed'
              ? exportResult.error || '材料导出失败'
              : '正在检查并整理指定版本…'}
          {exportResult.status === 'ready' && (
            <button className="button" onClick={download}>
              下载 HTML
            </button>
          )}
        </div>
      )}
      <div className="iw-mobile-switch">
        <button aria-pressed={mobilePane === 'chat'} onClick={() => setMobilePane('chat')}>
          画板与资料
        </button>
        <button aria-pressed={mobilePane === 'results'} onClick={() => setMobilePane('results')}>
          AI 助手
        </button>
      </div>
      <div
        ref={columnsRef}
        className={`iw-columns iw-show-${mobilePane}`}
        style={
          {
            '--iw-assistant-width': assistantWidth === null ? undefined : `${assistantWidth}px`,
          } as CSSProperties
        }
      >
        <section className="iw-conversation iw-data-pane" aria-label="询盘画板与资料">
          <div className="iw-panel-head">
            <h2>
              <MessageSquare size={16} />
              对话与进展
            </h2>
            <span className="iw-small-label">仅当前询盘</span>
          </div>
          <InquiryCanvas
            inquiry={inquiry}
            revision={revision}
            revisions={detail.data?.revisions || []}
            messages={detail.data?.messages || []}
            scope={scope}
            base={base}
            path={path}
            readOnly={readOnly}
            onGenerate={
              mode === 'real'
                ? (node, instruction) => setGeneration({ node, instruction })
                : undefined
            }
            onRestore={mode === 'real' ? restoreRevision : undefined}
            canRestore={
              mode === 'real' &&
              !busy &&
              !running &&
              inquiry.businessStatus !== 'done' &&
              inquiry.businessStatus !== 'waiting'
            }
            openRequest={documentRequest}
            saveResultRequest={saveResultRequest}
            onSavedResultsChange={setSavedResults}
            replyText={
              draftState.revision === revision?.number ? draftState.texts?.['en-US'] : undefined
            }
            onOriginalSaved={refresh}
            onInstruction={(text) => {
              setInput(text);
              showAIChat();
            }}
            onRevision={(number) => {
              setRevisionNumber(number === inquiry.currentRevision ? null : number);
              showAIChat();
            }}
            onOpenChat={showAIChat}
            conversation={
              <div className="ic-document-sheet">
                <div className="ic-document-eyebrow">CONVERSATION HISTORY</div>
                <h2>沟通与处理记录</h2>
                <p className="ic-document-subtitle">当前询盘的沟通留档，可在右侧继续与 AI 对话。</p>
                {(detail.data?.messages || []).map((message) => (
                  <article className="ic-history-message" key={message.id}>
                    <header>
                      <strong>{message.role === 'user' ? '你' : 'Navowork'}</strong>
                      <time>{date(message.createdAt)}</time>
                    </header>
                    <p>{message.text}</p>
                    <InvocationContext context={message.context} />
                  </article>
                ))}
                <button className="button" onClick={showAIChat}>
                  <MessageSquare size={14} />
                  在右侧继续对话
                </button>
              </div>
            }
            replyEditor={
              revision ? (
                <>
                  <ReplyEditor
                    key={`${scope}:${revision.number}`}
                    path={path}
                    revision={revision}
                    scope={scope}
                    readOnly={readOnly}
                    restoreLocal={!history && inquiry.businessStatus !== 'done'}
                    refreshKey={draftRefresh}
                    onState={setDraftState}
                  />
                  <div className="iw-review-bar">
                    <span>
                      <ShieldCheck size={15} />
                      人工编辑后需要重新复核
                    </span>
                    <button
                      className="button"
                      disabled={busy || draftsPending || running}
                      onClick={requestReview}
                    >
                      复核当前草稿
                    </button>
                  </div>
                  {review && (
                    <div className={`iw-review-result ${review.status}`}>
                      <strong>
                        {review.status === 'passed' ? '复核通过' : '需要修改后再导出'}
                      </strong>
                      {review.errors.map((e, i) => (
                        <p key={`e${i}`}>{e.message}</p>
                      ))}
                      {review.warnings.map((w, i) => (
                        <p key={`w${i}`}>{w.message}</p>
                      ))}
                    </div>
                  )}
                </>
              ) : null
            }
          />
        </section>
        <ResizeHandle
          label="调整 AI 面板宽度"
          controls={`results-${inquiryId}`}
          paneRef={assistantRef}
          containerRef={columnsRef}
          min={280}
          max={720}
          remainingMin={380}
          direction={-1}
          onResize={setAssistantWidth}
          onReset={() => setAssistantWidth(null)}
          className="iw-panel-resizer"
        />
        <section
          ref={assistantRef}
          className="iw-results iw-assistant"
          id={`results-${inquiryId}`}
          aria-label="AI 助手"
        >
          <InquiryChatHeading onClear={clearMessages} />
          <div className="iw-ai-chat">
            <div className="iw-messages" ref={messagesRef}>
              <InquiryChatTranscript
                inquiry={inquiry}
                messages={detail.data?.messages || []}
                onOriginal={() => openDocument('original')}
                onDelete={deleteMessage}
                resultMessageId={resultMessage?.id}
                resultPreview={resultPreview}
              />
              {run && (
                <div
                  className={`iw-run ${['queued', 'running'].includes(run.status) ? 'iw-run-active' : ''}`}
                  data-status={run.status}
                  role="region"
                  aria-label="AI 处理进度"
                >
                  <InquiryRunActivity key={run.id} run={run} />
                  {running && <p className="iw-run-hint">可以切换其他询盘，结果会保存在这里。</p>}
                  {run.error && <ErrorNotice error={run.error.message} />}{' '}
                  {run.clarification?.questions.map((q) => (
                    <p key={q.id}>
                      <TriangleAlert size={13} /> {q.question}
                    </p>
                  ))}
                  {!!run.fileOutputs?.length && (
                    <div aria-label="本次生成的文件">
                      <p>已生成文件草稿，需审核后使用。</p>
                      {run.fileOutputs.map((file) => (
                        <button
                          key={file.file_id}
                          className="button button-ghost"
                          title={`SHA-256: ${file.sha256}`}
                          onClick={() =>
                            void operate(async () => {
                              const blob = await api.download(
                                file.downloadUrl.replace(/^\/api\/v1/, ''),
                              );
                              const url = URL.createObjectURL(blob);
                              const anchor = document.createElement('a');
                              anchor.href = url;
                              anchor.download = file.name;
                              anchor.click();
                              URL.revokeObjectURL(url);
                            })
                          }
                        >
                          <Download size={13} /> {file.name}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="iw-run-actions">
                    <details className="iw-run-details">
                      <summary>运行详情</summary>
                      <small>runId: {run.id}</small>
                      <InvocationContext context={run.context} />
                    </details>
                    {run.status === 'failed' && (
                      <button
                        className="button"
                        disabled={!canWrite}
                        onClick={() => {
                          setInput(run.instruction);
                          setComposerContext(restoreContext(run.context));
                          setNotice('已恢复本次指令，确认后可重新处理。');
                        }}
                      >
                        恢复指令并重试
                      </button>
                    )}
                    {(running || run.status === 'needs_input') && (
                      <button
                        className="button button-ghost iw-run-cancel"
                        disabled={busy}
                        onClick={() =>
                          operate(async () => {
                            await api.post(`${base}/runs/${run.id}/cancel`);
                            await runQuery.refetch();
                            await refresh();
                          })
                        }
                      >
                        <Square size={12} />
                        取消本次运行
                      </button>
                    )}
                  </div>
                </div>
              )}
              <ErrorNotice error={runQuery.error} onRetry={() => void runQuery.refetch()} />
            </div>
            <InquiryComposer
              session={session}
              inquiryId={inquiryId}
              input={input}
              selection={composerContext}
              onInput={setInput}
              onSelection={setComposerContext}
              canWrite={canWrite}
              canSend={canSend}
              readOnly={readOnly}
              draftsPending={!!revision && draftsPending}
              draftStored={draftStored}
              sendLabel={inquiry.currentRevision ? '处理反馈' : '开始处理'}
              onSend={() => void startRun()}
              onOriginal={() => openDocument('original')}
            />
            <div className="iw-case-actions">
              {mode === 'real' && (
                <Link to={`/workbench?case=${encodeURIComponent(inquiryId)}`}>业务资料与审批</Link>
              )}
              {inquiry.businessStatus === 'active' && (
                <button
                  disabled={running || busy || (!!revision && draftsPending)}
                  onClick={() => setModal('waiting')}
                >
                  标记待确认
                </button>
              )}
              {inquiry.businessStatus !== 'done' && (
                <button
                  disabled={running || busy || (!!revision && draftsPending)}
                  onClick={() => setModal('close')}
                >
                  结束询盘
                </button>
              )}
              <button onClick={() => setModal('relations')}>
                <GitBranch size={12} /> 业务关联
              </button>
            </div>
          </div>
        </section>
      </div>
      {modal === 'original' && (
        <Modal title="客户原始询盘" onClose={() => setModal(null)}>
          <p className="iw-muted">客户：{inquiry.customer} · 原文留档</p>
          <CustomerContextCard inquiry={inquiry} />
          <pre className="iw-original-full">{inquiry.originalText}</pre>
        </Modal>
      )}
      {generation && (
        <GenerateNodeDialog
          inquiry={inquiry}
          base={base}
          path={path}
          node={generation.node}
          instruction={generation.instruction}
          onClose={() => setGeneration(null)}
          onStarted={(r) => {
            setGeneration(null);
            setLastRunId(r.id);
            setRevisionNumber(null);
            showAIChat();
            queryClient.setQueryData(['run', scope, r.id], r);
            void refresh();
          }}
        />
      )}
      {modal === 'waiting' && (
        <Modal title="标记为待确认" onClose={() => setModal(null)}>
          <form
            className="iw-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void transition('waiting', {
                waiting: {
                  waitingFor: f.get('waitingFor'),
                  waitingReason: f.get('reason'),
                  nextAction: f.get('next'),
                  followUpAt: f.get('date') || undefined,
                },
              });
            }}
          >
            <label>
              等待对象
              <select name="waitingFor">
                <option value="customer">客户</option>
                <option value="internal">内部资料</option>
                <option value="supplier">供应商</option>
                <option value="other">其他</option>
              </select>
            </label>
            <label>
              需要确认什么
              <textarea name="reason" required placeholder="填写明确的等待事项" />
            </label>
            <label>
              下一步行动
              <input name="next" required placeholder="例如：收到地址后确认运费" />
            </label>
            <label>
              跟进日期（可选，不自动发送提醒）
              <input type="date" name="date" />
            </label>
            <ErrorNotice error={error} />
            <button className="button button-primary" disabled={busy}>
              保存待确认事项
            </button>
          </form>
        </Modal>
      )}
      {modal === 'close' && (
        <Modal title="结束本次询盘" onClose={() => setModal(null)}>
          <form
            className="iw-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const reason = String(f.get('reason'));
              const note = String(f.get('note')).trim();
              if (reason === '其他' && !note) {
                setError('选择其他原因时，请填写说明');
                return;
              }
              void transition('done', { closeReason: `${reason}${note ? `：${note}` : ''}` });
            }}
          >
            <p className="iw-muted">结束后保留全部内容并设为只读，之后可重新打开。</p>
            <label>
              结束原因
              <select name="reason">
                <option>本次处理完成</option>
                <option>客户取消</option>
                <option>不再跟进</option>
                <option>其他</option>
              </select>
            </label>
            <label>
              补充说明
              <textarea name="note" placeholder="选择「其他」时必填" />
            </label>
            <ErrorNotice error={error} />
            <button className="button button-primary" disabled={busy}>
              确认结束
            </button>
          </form>
        </Modal>
      )}
      {modal === 'accept' && revision && (
        <Modal title="记录客户接受方案" onClose={() => setModal(null)}>
          <form
            className="iw-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void startRun('accept_proposal', String(f.get('evidence')));
            }}
          >
            <p>
              本次确认绑定 V{revision.number} · {revision.proposal.selectedSku}
              ，后续实质条款变化需要重新确认。
            </p>
            <label>
              客户明确反馈依据
              <textarea
                required
                minLength={4}
                name="evidence"
                placeholder="粘贴客户明确接受此方案的反馈，不能以建议或问句代替。"
              />
            </label>
            <ErrorNotice error={error} />
            <button className="button button-primary" disabled={busy || draftsPending}>
              提交接受记录
            </button>
          </form>
        </Modal>
      )}
      {modal === 'relations' && (
        <Modal title="当前版本的业务关联" wide onClose={() => setModal(null)}>
          {revision ? (
            <div className="iw-relations">
              {[
                ['客户需求', revision.requirements.requestedProduct || '待明确'],
                ['资料依据', `${revision.sourceRefs.length} 项固定来源`],
                [
                  '方案报价',
                  revision.quote
                    ? `${revision.quote.sku} · ${money(revision.quote.goodsSubtotalMinor)}`
                    : '尚无有效报价',
                ],
                ['双语回复', '与本版本事实保持一致'],
                ['风险审校', `${revision.risks.length} 项风险 / 待确认`],
              ].map(([title, text], i) => (
                <div key={title}>
                  <span>0{i + 1}</span>
                  <strong>{title}</strong>
                  <p>{text}</p>
                  {i < 4 && <ArrowRight size={18} />}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="成功分析后可查看关联"
              description="关联图读取当前业务版本，不独立改变业务事实。"
            />
          )}
          <p className="iw-muted">用于查看事实和结果之间的依赖，无需连线或操作节点即可完成询盘。</p>
        </Modal>
      )}
      {source && (
        <SourceDrawer source={source} base={base} scope={scope} onClose={() => setSource(null)} />
      )}
    </div>
  );
}

function SourceDrawer({
  source,
  base,
  scope,
  onClose,
}: {
  source: SourceRef;
  base: string;
  scope: string;
  onClose: () => void;
}) {
  const data = useQuery({
    queryKey: ['source', scope, source.sourceId, source.version],
    queryFn: ({ signal }) =>
      api.get<Source>(`${base}/sources/${source.sourceId}/versions/${source.version}`, signal),
  });
  return (
    <Modal title="查看引用依据" onClose={onClose}>
      {data.isPending ? (
        <Loading />
      ) : data.error ? (
        <ErrorNotice error={data.error} onRetry={() => void data.refetch()} />
      ) : (
        data.data && (
          <>
            <div className="iw-source-heading">
              <BookOpen size={22} />
              <h3>{data.data.title}</h3>
              <StatusBadge status={data.data.status} />
            </div>
            <p className="iw-muted">
              固定版本 V{source.version} ·{' '}
              {source.locator.row
                ? `第 ${source.locator.row} 行`
                : source.locator.section || source.locator.field}
            </p>
            <pre className="iw-source-content">{data.data.content}</pre>
            <p className="iw-muted">引用编号：{source.sourceVersionId}</p>
            <p className="iw-muted">支持字段：{source.supports.join('、')}</p>
          </>
        )
      )}
    </Modal>
  );
}

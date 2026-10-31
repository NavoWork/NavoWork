import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  GitBranch,
  History,
  MessageSquare,
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
import { MaterialsPanel } from './inquiry-materials';
import './inquiry.css';

const stages = ['读懂询盘', '准备方案', '完成回复'];
const resultTabs = ['需求与风险', '方案与报价', '客户回复', '资料依据'];
const phaseNames: Record<string, string> = {
  understanding: '理解客户需求',
  retrieving: '查阅已发布资料',
  calculating: '计算方案报价',
  composing: '准备双语回复',
  validating: '审校业务内容',
  committing: '保存完整版本',
};
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
  } catch {
    /* Storage is optional for view preferences. */
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
  const prefKey = `easywork:view:${scope}`;
  const initial = useRef(
    readPref(prefKey, {
      input: '',
      tab: 0,
      stage: 0,
      revision: null as number | null,
      lastRunId: '',
      selectedAssets: null as string[] | null,
    }),
  );
  const [input, setInput] = useState(initial.current.input);
  const [tab, setTab] = useState(initial.current.tab);
  const [stage, setStage] = useState(initial.current.stage);
  const [revisionNumber, setRevisionNumber] = useState<number | null>(initial.current.revision);
  const [lastRunId, setLastRunId] = useState(initial.current.lastRunId);
  const [selectedAssets, setSelectedAssets] = useState<string[] | null>(
    initial.current.selectedAssets ?? null,
  );
  const [mobilePane, setMobilePane] = useState<'chat' | 'results'>('results');
  const [modal, setModal] = useState<
    'original' | 'history' | 'waiting' | 'close' | 'accept' | 'relations' | null
  >(null);
  const [source, setSource] = useState<SourceRef | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [draftState, setDraftState] = useState<DraftState>({
    revision: null,
    versions: {},
    pending: true,
  });
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [draftRefresh, setDraftRefresh] = useState(0);
  const queryClient = useQueryClient();
  const changedRef = useRef(onChanged);
  changedRef.current = onChanged;
  const queryKey = ['inquiry', scope];
  const detail = useQuery({
    queryKey,
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
  const activeRunId = inquiry?.activeRunId || lastRunId;
  const runQuery = useQuery({
    queryKey: ['run', scope, activeRunId],
    enabled: !!activeRunId,
    queryFn: ({ signal }) => api.get<Run>(`${base}/runs/${activeRunId}`, signal),
    refetchInterval: (q) =>
      !q.state.data || ['queued', 'running'].includes(q.state.data.status) ? 900 : false,
    retry: false,
  });
  const run = runQuery.data;
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
    writePref(prefKey, { input, tab, stage, revision: revisionNumber, lastRunId, selectedAssets });
  }, [input, tab, stage, revisionNumber, lastRunId, selectedAssets, prefKey]);
  useEffect(() => {
    if (
      run &&
      !['queued', 'running'].includes(run.status) &&
      handledRun.current !== `${run.id}:${run.status}`
    ) {
      handledRun.current = `${run.id}:${run.status}`;
      void refresh();
      if (run.status === 'succeeded') {
        setNotice(`V${run.outputRevision} 已保存到此询盘`);
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
  async function startRun(
    action = inquiry?.currentRevision ? 'revise' : 'analyze',
    evidence?: string,
  ) {
    if (!inquiry || running || (draftsPending && !!revision)) return;
    await operate(async () => {
      const r = await api.post<Run>(`${path}/runs`, {
        baseRevision: inquiry.currentRevision,
        action,
        assetVersionIds: selectedAssets ?? revision?.assetRefs ?? [],
        instruction:
          evidence ||
          input.trim() ||
          (action === 'analyze'
            ? '分析客户原始询盘，提取需求与待确认项'
            : '根据当前事实更新方案与回复'),
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
      setModal(null);
      setRevisionNumber(null);
      queryClient.setQueryData(['run', scope, r.runId || r.id], r);
      await refresh();
    });
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
      a.download = `EasyWork-${inquiryId}-V${revision.number}-草稿.html`;
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
  return (
    <div className="iw-page">
      <header className="iw-heading">
        <div>
          <div className="iw-eyebrow">
            <span>询盘工作区</span>
            <ChevronRight size={12} />
            <span>{inquiry.customer}</span>
          </div>
          <div className="iw-title">
            <h1>{inquiry.title}</h1>
            <StatusBadge status={inquiry.businessStatus} />
          </div>
          <p>客户需求、方案和回复，在同一个上下文里推进。</p>
        </div>
        <div className="iw-actions">
          <button className="button" onClick={() => setModal('history')}>
            <History size={14} />
            版本记录{' '}
            <span className="iw-version">
              {inquiry.currentRevision ? `V${inquiry.currentRevision}` : '暂无'}
            </span>
          </button>
          <button
            className="button button-primary"
            disabled={!revision || draftsPending || busy}
            onClick={requestExport}
          >
            <Download size={14} />
            导出草稿材料
          </button>
        </div>
      </header>
      <div className="iw-stage-bar">
        {stages.map((label, i) => (
          <button
            key={label}
            className={stage === i ? 'selected' : ''}
            aria-pressed={stage === i}
            onClick={() => {
              setStage(i);
              setTab(i);
              setMobilePane('results');
            }}
          >
            <span>0{i + 1}</span>
            <strong>{label}</strong>
            {i < 2 && <ChevronRight size={15} />}
          </button>
        ))}
        <button className="iw-relation-button" onClick={() => setModal('relations')}>
          <GitBranch size={14} />
          业务关联
        </button>
      </div>
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
          对话
        </button>
        <button aria-pressed={mobilePane === 'results'} onClick={() => setMobilePane('results')}>
          业务结果
        </button>
      </div>
      <div className={`iw-columns iw-show-${mobilePane}`}>
        <section className="iw-conversation">
          <div className="iw-panel-head">
            <h2>
              <MessageSquare size={16} />
              对话与进展
            </h2>
            <span className="iw-small-label">仅当前询盘</span>
          </div>
          <div className="iw-messages">
            <button className="iw-original" onClick={() => setModal('original')}>
              <FileText size={16} />
              <div>
                <strong>客户原始询盘</strong>
                <p>
                  {inquiry.originalText.slice(0, 110)}
                  {inquiry.originalText.length > 110 ? '…' : ''}
                </p>
              </div>
              <ChevronRight size={14} />
            </button>
            {!detail.data?.messages.length && (
              <div className="iw-assistant-intro">
                <span className="iw-ai-mark">
                  <Sparkles size={16} />
                </span>
                <h3>先把需求读清楚。</h3>
                <p>
                  从客户原文开始，梳理产品、数量、目的地与时间要求。资料不足的地方，会保留为待确认。
                </p>
              </div>
            )}
            {detail.data?.messages.map((message) => (
              <article className={`iw-message ${message.role}`} key={message.id}>
                <div className="iw-message-meta">
                  <span>{message.role === 'user' ? '你' : 'EasyWork'}</span>
                  <time>{date(message.createdAt)}</time>
                </div>
                <p>{message.text}</p>
              </article>
            ))}
            {run && (
              <div className="iw-run">
                <div className="iw-run-title">
                  <Sparkles size={14} />
                  <strong>{running ? phaseNames[run.phase] : '本次运行'}</strong>
                  <StatusBadge status={run.status} />
                </div>
                <div className="iw-run-steps">
                  {Object.entries(phaseNames).map(([phase, title], index) => (
                    <span
                      key={phase}
                      className={
                        Object.keys(phaseNames).indexOf(run.phase) >= index ? 'reached' : ''
                      }
                      title={title}
                    />
                  ))}
                </div>
                <small>runId: {run.id}</small>
                {running && <p>可以切换其他询盘，结果会保存在这里。</p>}
                {run.error && <ErrorNotice error={run.error.message} />}{' '}
                {run.clarification?.questions.map((q) => (
                  <p key={q.id}>
                    <TriangleAlert size={13} /> {q.question}
                  </p>
                ))}
                {run.status === 'failed' && (
                  <button
                    className="button"
                    disabled={!canWrite}
                    onClick={() => {
                      setInput(run.instruction);
                      setNotice('已恢复本次指令，确认后可重新处理。');
                    }}
                  >
                    恢复指令并重试
                  </button>
                )}
                {running && (
                  <button
                    className="button button-ghost"
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
            )}
            <ErrorNotice error={runQuery.error} onRetry={() => void runQuery.refetch()} />
          </div>
          <div className="iw-composer">
            <label htmlFor={`instruction-${inquiryId}`}>
              补充要求或客户反馈 {input && <span>未发送 · 已在本机暂存</span>}
            </label>
            <textarea
              id={`instruction-${inquiryId}`}
              placeholder={
                readOnly
                  ? '请回到当前版本、恢复处理或等待运行完成'
                  : '例如：客户希望先试单 300 件，请准备现货方案…'
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!canWrite}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && canWrite) {
                  e.preventDefault();
                  void startRun();
                }
              }}
            />
            <div className="iw-composer-foot">
              <span>⌘ / Ctrl + Enter 处理</span>
              <button
                className="button button-primary"
                disabled={!canWrite || (!!revision && draftsPending)}
                onClick={() => startRun()}
              >
                {inquiry.currentRevision ? '处理反馈' : '开始处理'}
                <ArrowUp size={14} />
              </button>
            </div>
          </div>
          <div className="iw-case-actions">
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
            <span>状态变更由你决定</span>
          </div>
        </section>
        <section className="iw-results">
          <div className="iw-panel-head">
            <h2>
              业务结果{' '}
              <span className="iw-version">{revision ? `V${revision.number}` : '等待分析'}</span>
            </h2>
            <span className="iw-small-label">
              {revision ? date(revision.createdAt) : '成功运行后生成'}
            </span>
          </div>
          {revision?.risks
            .filter((r) => r.status !== 'resolved' && r.severity !== 'info')
            .slice(0, 1)
            .map((r) => (
              <div className="iw-pinned-risk" key={r.id}>
                <TriangleAlert size={17} />
                <div>
                  <strong>{r.message}</strong>
                  <p>{r.suggestedAction}</p>
                </div>
                <button onClick={() => setTab(0)} aria-label="查看全部风险">
                  <ChevronRight size={16} />
                </button>
              </div>
            ))}
          <div className="iw-result-tabs" role="tablist" aria-label="业务结果">
            {resultTabs.map((label, i) => (
              <button
                key={label}
                id={`${inquiryId}-result-tab-${i}`}
                role="tab"
                aria-selected={tab === i}
                aria-controls={`${inquiryId}-result-${i}`}
                tabIndex={tab === i ? 0 : -1}
                onKeyDown={(e) => {
                  if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
                    e.preventDefault();
                    const next = (i + (e.key === 'ArrowRight' ? 1 : 3)) % 4;
                    setTab(next);
                    document.getElementById(`${inquiryId}-result-tab-${next}`)?.focus();
                  }
                }}
                onClick={() => setTab(i)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="iw-result-content">
            {!revision ? (
              <EmptyState
                title="还没有业务结果"
                description="点击「开始处理」分析客户原文。只有成功保存的完整版本会出现在这里。"
              />
            ) : (
              <>
                <div
                  hidden={tab !== 0}
                  role="tabpanel"
                  id={`${inquiryId}-result-0`}
                  aria-labelledby={`${inquiryId}-result-tab-0`}
                >
                  <div className="iw-section-heading">
                    <span className="iw-kicker">CUSTOMER REQUIREMENTS</span>
                    <h3>客户要什么</h3>
                  </div>
                  <dl className="iw-facts">
                    {[
                      ['产品', revision.requirements.requestedProduct],
                      [
                        '需求数量',
                        revision.requirements.quantity == null
                          ? null
                          : `${revision.requirements.quantity} 件`,
                      ],
                      ['规格', revision.requirements.specification],
                      ['目的地', revision.requirements.destination],
                      ['期望到货', revision.requirements.requestedArrival],
                      ['定制要求', revision.requirements.customization],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd className={!value ? 'unknown' : ''}>{value || '待确认'}</dd>
                      </div>
                    ))}
                  </dl>
                  {revision.requirements.missingFields.length > 0 && (
                    <div className="iw-note">
                      待补信息：{revision.requirements.missingFields.join('、')}
                    </div>
                  )}
                  <div className="iw-section-heading">
                    <span className="iw-kicker">OPEN QUESTIONS</span>
                    <h3>核对后，再向前一步</h3>
                  </div>
                  <div className="iw-risk-list">
                    {revision.risks.length ? (
                      revision.risks.map((r) => (
                        <article key={r.id}>
                          <TriangleAlert size={16} />
                          <div>
                            <div>
                              <strong>{r.message}</strong>
                              <span>
                                {r.status === 'resolved'
                                  ? '已解决'
                                  : r.severity === 'error'
                                    ? '阻断'
                                    : '待确认'}
                              </span>
                            </div>
                            <p>{r.suggestedAction}</p>
                          </div>
                        </article>
                      ))
                    ) : (
                      <p className="iw-muted">此版本没有返回风险项。</p>
                    )}
                  </div>
                  <div className="iw-inline-note">
                    <BookOpen size={14} />
                    客户要求与商家事实分开保留，备选方案需要客户确认。
                  </div>
                </div>
                <div
                  hidden={tab !== 1}
                  role="tabpanel"
                  id={`${inquiryId}-result-1`}
                  aria-labelledby={`${inquiryId}-result-tab-1`}
                >
                  <div className="iw-section-heading">
                    <span className="iw-kicker">PROPOSAL & QUOTATION</span>
                    <h3>把方案的边界说清楚</h3>
                  </div>
                  <div className="iw-proposal">
                    <div>
                      <span>客户原要求</span>
                      <strong>{revision.proposal.requestedSku || '尚未确定 SKU'}</strong>
                    </div>
                    <ArrowRight size={16} />
                    <div>
                      <span>当前方案</span>
                      <strong>{revision.proposal.selectedSku || '等待选择方案'}</strong>
                    </div>
                    <span className="iw-proposal-state">
                      {revision.proposal.status === 'accepted'
                        ? '已记录客户接受'
                        : revision.proposal.status === 'proposed'
                          ? '备选 · 待客户确认'
                          : '需求待准备'}
                    </span>
                  </div>
                  {revision.proposal.differences.map((d) => (
                    <p className="iw-note" key={d}>
                      {d}
                    </p>
                  ))}
                  {revision.quote ? (
                    <>
                      <div className="iw-quote-card">
                        <div className="iw-quote-top">
                          <span>商品小计 · USD</span>
                          <span>草稿报价</span>
                        </div>
                        <strong className="iw-quote-amount">
                          {money(revision.quote.goodsSubtotalMinor)}
                        </strong>
                        <p>
                          {revision.quote.quantity.toLocaleString()} 件 ×{' '}
                          {money(revision.quote.unitPriceMinor)} / 件
                        </p>
                        <dl className="iw-costs">
                          <div>
                            <dt>运费</dt>
                            <dd>{money(revision.quote.freightMinor)}</dd>
                          </div>
                          <div>
                            <dt>税费</dt>
                            <dd>{money(revision.quote.taxMinor)}</dd>
                          </div>
                          <div>
                            <dt>最终总额</dt>
                            <dd>{money(revision.quote.totalMinor)}</dd>
                          </div>
                        </dl>
                      </div>
                      <dl className="iw-facts">
                        <div>
                          <dt>生产时间</dt>
                          <dd>
                            {revision.quote.timing.productionDays == null
                              ? '待确认'
                              : `${revision.quote.timing.productionDays} 天`}
                          </dd>
                        </div>
                        <div>
                          <dt>出库时间</dt>
                          <dd>
                            {revision.quote.timing.dispatchDays == null
                              ? '待确认'
                              : `${revision.quote.timing.dispatchDays} 天`}
                          </dd>
                        </div>
                        <div>
                          <dt>起算条件</dt>
                          <dd>
                            {revision.quote.timing.startsAfter === 'payment_conditions_met'
                              ? '付款条件满足后'
                              : revision.quote.timing.startsAfter}
                          </dd>
                        </div>
                        <div>
                          <dt>运输 / 到货</dt>
                          <dd>
                            {revision.quote.timing.transitDays == null
                              ? '待确认，不承诺到货日期'
                              : `${revision.quote.timing.transitDays} 天运输`}
                          </dd>
                        </div>
                      </dl>
                    </>
                  ) : (
                    <EmptyState
                      title="本版本没有有效报价"
                      description="需要有效商品、数量和价格依据后才能形成报价。"
                    />
                  )}
                  {revision.proposal.status === 'proposed' && (
                    <button
                      className="button"
                      disabled={!canWrite}
                      onClick={() => setModal('accept')}
                    >
                      <Check size={14} />
                      记录客户接受该方案
                    </button>
                  )}
                </div>
                <div
                  hidden={tab !== 2}
                  role="tabpanel"
                  id={`${inquiryId}-result-2`}
                  aria-labelledby={`${inquiryId}-result-tab-2`}
                >
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
                </div>
                <div
                  hidden={tab !== 3}
                  role="tabpanel"
                  id={`${inquiryId}-result-3`}
                  aria-labelledby={`${inquiryId}-result-tab-3`}
                >
                  <div className="iw-section-heading">
                    <span className="iw-kicker">EVIDENCE, NOT ASSUMPTIONS</span>
                    <h3>每一项结论，都有出处</h3>
                    <p>此版本使用的固定来源，更新资料不会改写历史依据。</p>
                  </div>
                  <div className="iw-sources">
                    {revision.sourceRefs.map((s) => (
                      <button key={s.sourceVersionId} onClick={() => setSource(s)}>
                        <span className="iw-source-icon">
                          <FileText size={18} />
                        </span>
                        <div>
                          <strong>{s.title}</strong>
                          <p>
                            V{s.version} ·{' '}
                            {s.locator.row
                              ? `第 ${s.locator.row} 行`
                              : s.locator.section || s.locator.field || '原始资料'}
                          </p>
                        </div>
                        <ChevronRight size={15} />
                      </button>
                    ))}
                  </div>
                  {!revision.sourceRefs.length && (
                    <EmptyState
                      title="暂无引用来源"
                      description="查阅已发布资料后，固定版本引用会展示在这里。"
                    />
                  )}
                  <div className="iw-section-heading">
                    <h3>本次审校记录</h3>
                  </div>
                  {revision.checks.map((c, index) => (
                    <div className="iw-check" key={index}>
                      {c.status === 'passed' ? <Check size={14} /> : <TriangleAlert size={14} />}
                      <span>{c.label}</span>
                      <small>
                        {c.status === 'passed' ? '通过' : c.status === 'error' ? '错误' : '待确认'}
                      </small>
                    </div>
                  ))}
                  <p className="iw-muted">规则版本：{revision.ruleSetVersion}</p>
                  <MaterialsPanel
                    base={base}
                    path={path}
                    scope={scope}
                    revision={revision}
                    readOnly={readOnly || busy}
                    pending={draftsPending}
                    draftVersions={draftState.versions}
                    selectedAssets={history ? null : selectedAssets}
                    onSelect={setSelectedAssets}
                  />
                </div>
              </>
            )}
          </div>
        </section>
      </div>
      {modal === 'original' && (
        <Modal title="客户原始询盘" onClose={() => setModal(null)}>
          <p className="iw-muted">客户：{inquiry.customer} · 原文留档</p>
          <pre className="iw-original-full">{inquiry.originalText}</pre>
        </Modal>
      )}
      {modal === 'history' && (
        <Modal title="版本记录与比较" wide onClose={() => setModal(null)}>
          <HistoryPanel
            revisions={detail.data?.revisions || []}
            selected={selectedNumber || 0}
            onSelect={(n) => {
              setRevisionNumber(n === inquiry.currentRevision ? null : n);
              setModal(null);
            }}
          />
        </Modal>
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

function HistoryPanel({
  revisions,
  selected,
  onSelect,
}: {
  revisions: Revision[];
  selected: number;
  onSelect: (number: number) => void;
}) {
  const ordered = [...revisions].sort((a, b) => b.number - a.number);
  const [oldNumber, setOldNumber] = useState(ordered[1]?.number || ordered[0]?.number || 0);
  const current = ordered[0];
  const previous = ordered.find((r) => r.number === oldNumber);
  if (!current)
    return (
      <EmptyState
        title="还没有成功版本"
        description="成功处理后会保存完整快照，切换阶段不会新增版本。"
      />
    );
  return (
    <div className="iw-history">
      <div className="iw-history-list">
        {ordered.map((r) => (
          <button
            className={selected === r.number ? 'selected' : ''}
            key={r.number}
            onClick={() => onSelect(r.number)}
          >
            <span>V{r.number}</span>
            <div>
              <strong>{r.changeSummary.join('；') || '完整业务快照'}</strong>
              <p>{date(r.createdAt)} · 点击查看只读快照</p>
            </div>
            <ChevronRight size={14} />
          </button>
        ))}
      </div>
      <div className="iw-compare">
        <h3>与当前 V{current.number} 比较</h3>
        <label>
          对比版本{' '}
          <select value={oldNumber} onChange={(e) => setOldNumber(Number(e.target.value))}>
            {ordered.map((r) => (
              <option key={r.number} value={r.number}>
                V{r.number}
              </option>
            ))}
          </select>
        </label>
        {previous && (
          <table>
            <thead>
              <tr>
                <th>字段</th>
                <th>V{previous.number}</th>
                <th>V{current.number}</th>
              </tr>
            </thead>
            <tbody>
              {[
                [
                  '数量',
                  previous.quote?.quantity ?? previous.requirements.quantity,
                  current.quote?.quantity ?? current.requirements.quantity,
                ],
                ['SKU', previous.proposal.selectedSku, current.proposal.selectedSku],
                [
                  '商品小计',
                  money(previous.quote?.goodsSubtotalMinor),
                  money(current.quote?.goodsSubtotalMinor),
                ],
                ['方案确认', previous.proposal.status, current.proposal.status],
                [
                  '出库天数',
                  previous.quote?.timing.dispatchDays,
                  current.quote?.timing.dispatchDays,
                ],
                [
                  '风险',
                  previous.risks.map((r) => r.message).join('；'),
                  current.risks.map((r) => r.message).join('；'),
                ],
                [
                  '来源',
                  previous.sourceRefs.map((r) => r.sourceVersionId).join('、'),
                  current.sourceRefs.map((r) => r.sourceVersionId).join('、'),
                ],
              ].map(([label, a, b]) => (
                <tr className={a !== b ? 'changed' : ''} key={label}>
                  <th>{label}</th>
                  <td>{a ?? '待确认'}</td>
                  <td>{b ?? '待确认'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

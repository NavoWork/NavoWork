import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  ChevronDown,
  CircleAlert,
  Download,
  FileText,
  FolderOpen,
  Loader2,
  Paperclip,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import { api, ApiError, mode } from '../../api';
import type {
  Message,
  Run,
  Session,
  WorkbenchArtifact,
  WorkbenchData,
  WorkbenchEvidence,
  WorkbenchStage,
} from '../../api/types';
import { ErrorNotice, Loading, Modal } from '../../components/ui';
import { AgentPanel } from './AgentPanel';
import {
  CostingPanel,
  InquiryPanel,
  OrderPanel,
  ProductionPanel,
  RequirementsPanel,
  SamplePanel,
  sourceRoleLabel,
} from './panels';
import { EmptyHint, Pill, StatusDot, money, stageStatusLabel } from './ui';
import './workbench.css';

type RecordItem = Record<string, any>;

const CORE_STAGES = ['inquiry', 'requirements', 'costing', 'sample', 'order', 'production'];
const stageIndex: Record<string, string> = {
  inquiry: '01',
  requirements: '02',
  costing: '03',
  sample: '04',
  order: '05',
  production: '06',
};

const stageLabel = (stage: WorkbenchStage) => (stage.key === 'inquiry' && stage.status === 'ready' ? '已整理' : stageStatusLabel[stage.status]);

const approvalLabel: Record<string, string> = {
  customer_spec_approval: '客户规格确认',
  commercial_quotation_approval: '内部报价批准',
  sample_approval: '客户样品批准',
  order_buyer_confirmation: '买方订单确认',
  order_seller_confirmation: '卖方订单确认',
  payment_verification: '付款核验',
  supplier_production_confirmation: '供应商生产确认',
  production_release: '生产放行',
};

interface ConfirmState {
  scope: string;
  target: WorkbenchArtifact;
  evidenceRole: string;
  basis?: string;
}

export function InquiryWorkbench({ inquiryId, session, onChanged }: { inquiryId: string; session: Session; onChanged: () => void }) {
  const base = `/workspaces/${session.workspace.id}`;
  const path = `${base}/inquiries/${encodeURIComponent(inquiryId)}`;
  const scope = `${session.user.id}:${session.workspace.id}:${inquiryId}`;
  const location = useLocation();
  const active = location.pathname === `/inquiries/${encodeURIComponent(inquiryId)}`;
  const qc = useQueryClient();
  const stagePrefKey = `easywork:wb-stage:${scope}`;
  const [stage, setStage] = useState(() => {
    try { return localStorage.getItem(stagePrefKey) || 'inquiry'; } catch { return 'inquiry'; }
  });
  const [runId, setRunId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const [selectedKnowledge, setSelectedKnowledge] = useState<string[]>([]);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const stageInitialized = useRef(false);

  const workbench = useQuery({
    queryKey: ['workbench-v2', scope],
    enabled: active,
    queryFn: ({ signal }) => api.get<WorkbenchData>(`${path}/workbench`, signal),
    retry: false,
  });
  const data = workbench.data;
  const currentRunId = runId || data?.case.pendingRunId || data?.case.activeRunId || '';
  const run = useQuery({
    queryKey: ['workbench-run', scope, currentRunId],
    enabled: active && !!currentRunId,
    queryFn: ({ signal }) => api.get<Run>(`${base}/runs/${currentRunId}`, signal),
    refetchInterval: (query) => (!query.state.data || ['queued', 'running'].includes(query.state.data.status) ? 1100 : false),
    retry: false,
  });
  const messages = useQuery({
    queryKey: ['workbench-messages', scope],
    enabled: active,
    queryFn: ({ signal }) => api.get<{ items: Message[] }>(`${path}/messages`, signal),
    refetchInterval: run.data && ['queued', 'running'].includes(run.data.status) ? 2200 : false,
  });
  const events = useQuery({
    queryKey: ['workbench-events', scope, run.data?.id],
    enabled: active && !!run.data?.id,
    queryFn: ({ signal }) => api.get<{ items: RecordItem[] }>(`${base}/runs/${run.data!.id}/events`, signal),
    refetchInterval: run.data && ['queued', 'running'].includes(run.data.status) ? 1600 : false,
  });

  const invalidate = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['workbench-v2', scope] }),
      qc.invalidateQueries({ queryKey: ['workbench-messages', scope] }),
      qc.invalidateQueries({ queryKey: ['workbench-events', scope] }),
      qc.invalidateQueries({ queryKey: ['workbench-run', scope] }),
    ]);
    onChanged();
  }, [qc, scope, onChanged]);

  useEffect(() => {
    if (!data || stageInitialized.current) return;
    const saved = CORE_STAGES.includes(stage) ? stage : '';
    const next =
      data.stages.find((item) => CORE_STAGES.includes(item.key) && ['draft', 'ready', 'blocked'].includes(item.status)) ||
      data.stages.find((item) => CORE_STAGES.includes(item.key) && item.status !== 'confirmed');
    if (saved && data.stages.some((item) => item.key === saved)) setStage(saved);
    else if (next) setStage(next.key);
    stageInitialized.current = true;
    if (!selectedEvidence.length) setSelectedEvidence(data.evidence.map((item) => item.id));
  }, [data, selectedEvidence.length, stage]);

  useEffect(() => {
    try { localStorage.setItem(`easywork:wb-stage:${scope}`, stage); } catch { /* preference only */ }
  }, [scope, stage]);

  useEffect(() => {
    if (!run.data) return;
    if (!['queued', 'running'].includes(run.data.status)) {
      void invalidate();
    }
  }, [run.data?.status, run.data?.id, invalidate]);

  useEffect(() => {
    const node = run.data?.node;
    if (run.data?.status === 'needs_input' && node && CORE_STAGES.includes(node)) setStage(node);
  }, [run.data?.id, run.data?.status, run.data?.node]);

  const stageData = useMemo(() => data?.stages.find((item) => item.key === stage), [data, stage]);

  const operate = async (operation: () => Promise<void>, success?: string) => {
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      await operation();
      if (success) setNotice(success);
      await invalidate();
    } catch (e) {
      setError(e);
      await invalidate();
    } finally {
      setBusy(false);
    }
  };

  const sendAgent = (instruction: string, node?: string) => {
    if (!data) return;
    void operate(async () => {
      const result = await api.post<Run>(`${path}/workbench/agent`, {
        node,
        instruction,
        baseRevision: data.case.currentRevision,
        inputRefs: selectedEvidence,
        sourceVersionIds: selectedKnowledge,
        assetVersionIds: selectedAssets,
      });
      setRunId(result.id);
      setNotice('任务已提交，Agent 正在处理。');
    });
  };

  const answerAgent = async (answers: { questionId: string; value: string }[]) => {
    if (!data || !run.data) return false;
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      const result = await api.post<Run>(`${path}/runs`, {
        replyToRunId: run.data.id,
        baseRevision: run.data.baseRevision,
        answers,
      });
      setRunId(result.id);
      await invalidate();
      await qc.invalidateQueries({ queryKey: ['workbench-run', scope] });
      setNotice('补充已提交，继续同一任务。');
      return true;
    } catch (e) {
      setError(e);
      await invalidate();
      return false;
    } finally {
      setBusy(false);
    }
  };

  const cancelAgent = () => {
    if (!run.data) return;
    void operate(async () => {
      await api.post(`${base}/runs/${run.data!.id}/cancel`, {});
    }, '任务已停止。');
  };

  const saveArtifact: (kind: string, content: Record<string, any>, baseVersion: number) => Promise<boolean> = async (kind, content, baseVersion) => {
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      await api.put(`${path}/workbench/artifacts/${kind}`, { baseVersion, content });
      await invalidate();
      setNotice('已保存新版本。');
      return true;
    } catch (e) {
      setError(e);
      await invalidate();
      return false;
    } finally {
      setBusy(false);
    }
  };

  const exportArtifact = (kind: string, format: string) => {
    void operate(async () => {
      const result = await api.post<{ downloadUrl: string }>(`${path}/workbench/artifacts/${kind}/export`, { format });
      const blob = await api.download(result.downloadUrl.replace('/api/v1', ''));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${kind}-${format}.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, '已下载固定版本草稿。');
  };

  const openConfirm = (scope: string, target: WorkbenchArtifact, evidenceRole: string, options?: { basis?: string }) => {
    setError(undefined);
    setConfirm({ scope, target, evidenceRole, basis: options?.basis });
  };

  const submitConfirm = async (evidenceIds: string[], note: string, basis: string) => {
    if (!confirm) return;
    await operate(async () => {
      if (confirm.scope === 'production_release') {
        await api.post(`${path}/workbench/release`, { targetVersionId: confirm.target.itemId, note });
      } else {
        await api.post(`${path}/workbench/approvals`, {
          scope: confirm.scope,
          targetVersionId: confirm.target.itemId,
          evidenceRefs: evidenceIds,
          note,
          verificationBasis: basis,
        });
      }
      setConfirm(null);
    }, '确认已记录。');
  };

  const release = () => {
    const production = data?.artifacts.production;
    if (!production) return;
    setError(undefined);
    setConfirm({ scope: 'production_release', target: production, evidenceRole: '' });
  };

  if (workbench.isPending) return <Loading label="正在打开工作台" />;
  if (workbench.error) return <ErrorNotice error={workbench.error} onRetry={() => void workbench.refetch()} />;
  if (!data) return <EmptyHint>项目不存在或没有访问权限。</EmptyHint>;

  const selectedRefCount = selectedEvidence.length + selectedKnowledge.length + selectedAssets.length;
  const stageTitle = data.stages.find((item) => item.key === stage)?.title || '当前工作';

  return (
    <div className="wbv2">
      <header className="wbv2-head">
        <div className="wbv2-head-title">
          <span className="wbv2-eyebrow">CASE / {data.case.customer}</span>
          <h1>{data.case.title}</h1>
          <p>{[data.customerContext?.company || data.case.customer, data.customerContext?.country, data.case.destination].filter(Boolean).join(' · ')}</p>
        </div>
        <div className="wbv2-head-progress">
          {CORE_STAGES.map((key) => {
            const item = data.stages.find((entry) => entry.key === key);
            return (
              <button key={key} className={`wbv2-progress-step is-${item?.status || 'empty'}`} onClick={() => setStage(key)} title={item?.title}>
                <span>{stageIndex[key]}</span>
                <i />
              </button>
            );
          })}
          <div className="wbv2-progress-meta">
            <span>V{data.case.currentRevision}</span>
            <strong>{data.nextAction}</strong>
          </div>
        </div>
      </header>

      <div className="wbv2-body">
        <aside className="wbv2-rail">
          <div className="wbv2-rail-label">业务节点</div>
          <nav className="wbv2-stages">
            {CORE_STAGES.map((key) => {
              const item = data.stages.find((entry) => entry.key === key);
              if (!item) return null;
              return (
                <button key={key} className={`wbv2-stage ${stage === key ? 'is-active' : ''}`} onClick={() => setStage(key)}>
                  <span className="wbv2-stage-index">{stageIndex[key]}</span>
                  <span className="wbv2-stage-copy">
                    <strong>{item.title}</strong>
                    <small>{stageLabel(item)}{item.missing?.length ? ` · ${item.missing.length} 项缺项` : ''}</small>
                  </span>
                  <StatusDot status={item.status} />
                </button>
              );
            })}
          </nav>
          <div className="wbv2-rail-label">项目资料</div>
          <button className="wbv2-resource-button" onClick={() => setSourcesOpen(true)}>
            <Paperclip size={14} />
            <span>原件、知识库与资产</span>
            <strong>{data.evidence.length + data.knowledge.length + data.assets.length}</strong>
          </button>
          <div className="wbv2-rail-note">
            <ShieldCheck size={13} /> 所有确认绑定成果版本和证据。
          </div>
        </aside>

        <main className="wbv2-main">
          <div className="wbv2-main-head">
            <div>
              <span className="wbv2-eyebrow">STAGE {stageIndex[stage]}</span>
              <h2>{stageTitle}</h2>
              <p>{stageData?.nextAction}</p>
            </div>
            <div className="wbv2-main-meta">
              {stageData && <Pill tone={stageData.status === 'confirmed' ? 'green' : stageData.status === 'blocked' ? 'red' : stageData.status === 'ready' ? 'blue' : 'neutral'}>{stageLabel(stageData)}</Pill>}
              {stageData?.missing?.length ? <span>{stageData.missing.length} 项待处理</span> : null}
            </div>
          </div>

          {notice && <div className="wbv2-notice"><Check size={14} />{notice}</div>}
          <ErrorNotice error={error} onRetry={() => setError(undefined)} />

          {stage === 'inquiry' && <InquiryPanel data={data} onAgent={sendAgent} />}
          {stage === 'requirements' && <RequirementsPanel data={data} onAgent={sendAgent} onSave={saveArtifact} onConfirm={openConfirm} busy={busy} />}
          {stage === 'costing' && <CostingPanel data={data} onAgent={sendAgent} onSave={saveArtifact} onConfirm={openConfirm} onExport={exportArtifact} busy={busy} />}
          {stage === 'sample' && <SamplePanel data={data} onAgent={sendAgent} onConfirm={openConfirm} busy={busy} />}
          {stage === 'order' && <OrderPanel data={data} onAgent={sendAgent} onConfirm={openConfirm} busy={busy} />}
          {stage === 'production' && (
            <ProductionPanel data={data} onAgent={sendAgent} onConfirm={openConfirm} onRelease={release} onStage={setStage} busy={busy} />
          )}

          {data.approvals.length > 0 && (
            <details className="wbv2-card wbv2-audit">
              <summary>确认记录 · {data.approvals.length} 项<ChevronDown size={14} /></summary>
              <div className="wbv2-approval-list">
                {data.approvals.slice().reverse().map((item) => (
                  <div key={item.id}>
                    <span className={`wbv2-dot wbv2-dot-${item.decision === 'rejected' ? 'blocked' : 'confirmed'}`} />
                    <div><strong>{approvalLabel[item.scope] || item.scope}</strong><small>{new Date(item.createdAt).toLocaleString('zh-CN')} · {item.evidenceRefs.length} 份证据</small></div>
                    <Pill tone={item.decision === 'rejected' ? 'red' : 'green'}>{item.decision === 'verified' ? '已核验' : item.decision === 'rejected' ? '已拒绝' : '已确认'}</Pill>
                  </div>
                ))}
              </div>
            </details>
          )}
        </main>

        <AgentPanel
          messages={(messages.data?.items || []).filter((message) => !(message.role === 'user' && message.text.trim() === data.case.originalText.trim()))}
          run={run.data || null}
          events={events.data?.items || []}
          running={!!run.data && ['queued', 'running'].includes(run.data.status)}
          busy={busy}
          stage={stage}
          selectedRefs={selectedRefCount}
          onSend={(text) => sendAgent(text, stage)}
          onAnswer={answerAgent}
          onOpenSources={() => setSourcesOpen(true)}
          onCancel={cancelAgent}
          error={run.data?.error?.message || messages.error || run.error}
        />
      </div>

      {confirm && (
        <ConfirmDialog
          state={confirm}
          data={data}
          busy={busy}
          error={error}
          onClose={() => setConfirm(null)}
          onSubmit={submitConfirm}
        />
      )}
      {sourcesOpen && (
        <SourcesDialog
          data={data}
          path={path}
          selectedEvidence={selectedEvidence}
          selectedKnowledge={selectedKnowledge}
          selectedAssets={selectedAssets}
          onChangeEvidence={setSelectedEvidence}
          onChangeKnowledge={setSelectedKnowledge}
          onChangeAssets={setSelectedAssets}
          onClose={() => setSourcesOpen(false)}
          onUploaded={() => void operate(async () => {}, '原件已保存。')}
        />
      )}
    </div>
  );
}

function ConfirmDialog({ state, data, busy, error, onClose, onSubmit }: {
  state: ConfirmState;
  data: WorkbenchData;
  busy: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (evidenceIds: string[], note: string, basis: string) => Promise<void>;
}) {
  const [evidenceId, setEvidenceId] = useState('');
  const [note, setNote] = useState('');
  const [basis, setBasis] = useState(state.basis || '');
  const candidates = state.evidenceRole ? data.evidence.filter((item) => item.sourceRole === state.evidenceRole) : [];
  const requiresEvidence = !!state.evidenceRole;
  const requiresBasis = state.scope === 'payment_verification';
  const ready = (!requiresEvidence || evidenceId) && (!requiresBasis || basis.trim());
  return (
    <Modal title={approvalLabel[state.scope] || '记录确认'} onClose={onClose}>
      <div className="form-stack">
        <p className="wbv2-dialog-lead">
          目标成果：<strong>{state.target.title} V{state.target.version}</strong>
        </p>
        {requiresEvidence && (
          <label className="field">
            确认证据
            <select value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)}>
              <option value="">选择原始证据</option>
              {candidates.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
            {!candidates.length && <small>还没有对应角色的证据，请先在“资料”中上传。</small>}
          </label>
        )}
        {requiresBasis && <label className="field">核验依据<textarea rows={3} value={basis} onChange={(event) => setBasis(event.target.value)} placeholder="例如：财务核对银行入账记录与合同定金金额" /></label>}
        <label className="field">备注<textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} placeholder="可选" /></label>
        <ErrorNotice error={error} />
        <div className="form-actions">
          <button className="button" disabled={busy} onClick={onClose}>取消</button>
          <button className="button button-primary" disabled={busy || !ready} onClick={() => void onSubmit(evidenceId ? [evidenceId] : [], note, basis)}>
            <ShieldCheck size={14} /> 记录确认
          </button>
        </div>
      </div>
    </Modal>
  );
}

function SourcesDialog({ data, path, selectedEvidence, selectedKnowledge, selectedAssets, onChangeEvidence, onChangeKnowledge, onChangeAssets, onClose, onUploaded }: {
  data: WorkbenchData;
  path: string;
  selectedEvidence: string[];
  selectedKnowledge: string[];
  selectedAssets: string[];
  onChangeEvidence: (value: string[]) => void;
  onChangeKnowledge: (value: string[]) => void;
  onChangeAssets: (value: string[]) => void;
  onClose: () => void;
  onUploaded: () => void;
}) {
  const [role, setRole] = useState('customer_request');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [tab, setTab] = useState<'evidence' | 'knowledge' | 'assets'>('evidence');
  const [preview, setPreview] = useState('');

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError(undefined);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('sourceRole', role);
      const uploaded = await api.post<WorkbenchEvidence>(`${path}/evidence`, form);
      onChangeEvidence([...selectedEvidence, uploaded.id]);
      setFile(null);
      onUploaded();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="项目资料" onClose={onClose} wide>
      <div className="wbv2-sources">
        <div className="wbv2-source-tabs">
          <button className={tab === 'evidence' ? 'is-active' : ''} onClick={() => { setTab('evidence'); setPreview(''); }}>原件 {data.evidence.length}</button>
          <button className={tab === 'knowledge' ? 'is-active' : ''} onClick={() => { setTab('knowledge'); setPreview(''); }}>知识库 {data.knowledge.length}</button>
          <button className={tab === 'assets' ? 'is-active' : ''} onClick={() => { setTab('assets'); setPreview(''); }}>资产 {data.assets.length}</button>
        </div>
        {tab === 'evidence' && (
          <>
            <div className="wbv2-upload">
              <input type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="customer_request">客户询盘</option>
                <option value="supplier_quote">供应商报价</option>
                <option value="customer_change">客户变更</option>
                <option value="customer_po">客户 PO</option>
                <option value="customer_approval">客户确认</option>
                <option value="supplier_confirmation">供应商确认</option>
                <option value="payment_receipt">付款凭据</option>
                <option value="sample_inspection">样品检查</option>
                <option value="internal_note">内部记录</option>
              </select>
              <button className="button" disabled={!file || busy} onClick={() => void upload()}>{busy ? '上传中…' : '上传原件'}</button>
            </div>
            <ErrorNotice error={error} />
            <div className="wbv2-source-pick">
              {data.evidence.map((item) => (
                <div className="wbv2-source-item" key={item.id}>
                  <label>
                    <input type="checkbox" checked={selectedEvidence.includes(item.id)} onChange={(event) => onChangeEvidence(event.target.checked ? [...selectedEvidence, item.id] : selectedEvidence.filter((id) => id !== item.id))} />
                    <div><strong>{item.title}</strong><small>{sourceRoleLabel[item.sourceRole] || item.sourceRole}</small></div>
                  </label>
                  <button className="wbv2-text-button" onClick={() => setPreview(preview === item.id ? '' : item.id)}>{preview === item.id ? '收起' : '查看'}</button>
                </div>
              ))}
              {!data.evidence.length && <EmptyHint>还没有原件。</EmptyHint>}
            </div>
            {preview && (() => {
              const item = data.evidence.find((entry) => entry.id === preview);
              return item ? <pre className="wbv2-source-preview">{item.text || '该文件没有可提取的文本。'}</pre> : null;
            })()}
          </>
        )}
        {tab === 'knowledge' && (
          <div className="wbv2-source-pick">
            {data.knowledge.map((item) => (
              <label key={item.id}>
                <input type="checkbox" checked={selectedKnowledge.includes(item.id)} onChange={(event) => onChangeKnowledge(event.target.checked ? [...selectedKnowledge, item.id] : selectedKnowledge.filter((id) => id !== item.id))} />
                <div><strong>{item.title}</strong><small>V{item.version} · 固定版本</small></div>
              </label>
            ))}
            {!data.knowledge.length && <EmptyHint>知识库还没有已发布文档。</EmptyHint>}
          </div>
        )}
        {tab === 'assets' && (
          <div className="wbv2-source-pick">
            {data.assets.map((item) => (
              <label key={item.id}>
                <input type="checkbox" checked={selectedAssets.includes(`${item.id}:v${item.version}`)} onChange={(event) => onChangeAssets(event.target.checked ? [...selectedAssets, `${item.id}:v${item.version}`] : selectedAssets.filter((id) => id !== `${item.id}:v${item.version}`))} />
                <div><strong>{item.title}</strong><small>V{item.version} · {item.mediaType}</small></div>
              </label>
            ))}
            {!data.assets.length && <EmptyHint>公司资产库还没有文件。</EmptyHint>}
          </div>
        )}
        <div className="wbv2-dialog-actions">
          <span>选中的资料会冻结在本轮任务输入中。</span>
          <button className="button button-primary" onClick={onClose}>完成</button>
        </div>
      </div>
    </Modal>
  );
}

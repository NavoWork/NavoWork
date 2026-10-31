import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../api';
import type { Inquiry, Page, Run, Session } from '../../api/types';
import { ErrorNotice, Loading } from '../../components/ui';
import './real-workbench.css';

type RecordItem = Record<string, any>;
type List = { items: RecordItem[] };

const stages = [
  { kind: 'qualify_inquiry', title: '1 客户与询盘评估', hint: '档案、风险、跟进计划' },
  { kind: 'confirm_requirements', title: '2 产品需求确认', hint: '字段来源、未知项、规格草稿' },
  { kind: 'prepare_quote', title: '3a 核价与报价', hint: '供应商报价、成本、报价草稿' },
  { kind: 'manage_sample', title: '3b 打样与样品确认', hint: '样品版本、检查与书面批准' },
  { kind: 'confirm_order', title: '4 PO 与合同确认', hint: '差异、双方确认、付款保障' },
  { kind: 'prepare_production', title: '5 生产资料与验货', hint: '资料包与放行缺口' },
  { kind: 'manage_shipment', title: '6 出口出运', hint: '后续阶段：需真实单证' },
  { kind: 'reconcile_payment', title: '7 收款与售后', hint: '后续阶段：需财务核验' },
] as const;

const nodeStage = (key: string) => {
  if (/profile|follow_up/.test(key)) return 'qualify_inquiry';
  if (/spec|requirements/.test(key)) return 'confirm_requirements';
  if (/sample/.test(key)) return 'manage_sample';
  if (/quote|cost|rfq|normalize/.test(key)) return 'prepare_quote';
  if (/po|contract|payment_assurance/.test(key)) return 'confirm_order';
  if (/production|qc/.test(key)) return 'prepare_production';
  if (/shipment|export/.test(key)) return 'manage_shipment';
  return 'qualify_inquiry';
};

export function RealWorkbench({ session }: { session: Session }) {
  const [search, setSearch] = useSearchParams();
  const [cases, setCases] = useState<Inquiry[]>([]);
  const [caseId, setCaseId] = useState(search.get('case') || '');
  const [stage, setStage] = useState<string>('qualify_inquiry');
  const [data, setData] = useState<Record<string, RecordItem[]>>({});
  const [sopStatus, setSopStatus] = useState<RecordItem | null>(null);
  const [currentCase, setCurrentCase] = useState<Inquiry | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [goal, setGoal] = useState('');
  const [changeText, setChangeText] = useState('');
  const [changeSource, setChangeSource] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [impact, setImpact] = useState<RecordItem | null>(null);
  const [nodeActions, setNodeActions] = useState<RecordItem[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<RecordItem | null>(null);
  const [artifactValidation, setArtifactValidation] = useState<RecordItem | null>(null);
  const [artifactText, setArtifactText] = useState('');
  const [cost, setCost] = useState({ base: '', packaging: '', local: '', exchangeRate: '', margin: '', quantity: '' });
  const [supplierName, setSupplierName] = useState('');
  const [supplierSource, setSupplierSource] = useState('');
  const [selectedOffer, setSelectedOffer] = useState('');
  const [sourceRole, setSourceRole] = useState('customer_request');
  const [evidenceText, setEvidenceText] = useState('');
  const [evidenceTitle, setEvidenceTitle] = useState('');
  const [approvalScope, setApprovalScope] = useState('commercial_quotation_approval');
  const [approvalEvidence, setApprovalEvidence] = useState('');
  const [approvalNote, setApprovalNote] = useState('');
  const [sampleEvidence, setSampleEvidence] = useState('');
  const [orderDocument, setOrderDocument] = useState('');
  const [buyerEvidence, setBuyerEvidence] = useState('');
  const [sellerEvidence, setSellerEvidence] = useState('');
  const [paymentEvidence, setPaymentEvidence] = useState('');
  const [paymentBasis, setPaymentBasis] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const workspace = `/workspaces/${session.workspace.id}`;
  const path = caseId ? `${workspace}/inquiries/${caseId}` : '';

  const refresh = useCallback(async () => {
    const page = await api.get<Page<Inquiry>>(`${workspace}/inquiries?limit=100`);
    setCases(page.items);
    const chosen = page.items.find((item) => item.id === caseId)?.id || page.items[0]?.id;
    if (!chosen) {
      setCurrentCase(null);
      setLoading(false);
      return;
    }
    if (chosen !== caseId) {
      setCaseId(chosen);
      setSearch({ case: chosen });
    }
    const base = `${workspace}/inquiries/${chosen}`;
    const endpoints = ['evidence', 'facts', 'artifacts', 'jobs', 'change-sets', 'approvals', 'samples', 'order-confirmations', 'payment-assurance-checks', 'production-packs', 'revisions', 'supplier-offers'];
    const values = await Promise.all([
      api.get<Inquiry>(base),
      ...endpoints.map((endpoint) => api.get<List>(`${base}/${endpoint}`)),
      api.get<RecordItem>(`${base}/sop-status`),
    ]);
    setCurrentCase(values[0] as Inquiry);
    setData(Object.fromEntries(endpoints.map((endpoint, i) => [endpoint, (values[i + 1] as List).items])));
    setSopStatus(values.at(-1) as RecordItem);
    setLoading(false);
  }, [workspace, caseId, setSearch]);

  useEffect(() => {
    void refresh().catch((e) => { setError(e); setLoading(false); });
  }, [refresh]);

  useEffect(() => {
    if (!impact?.id || !path) { setNodeActions([]); return; }
    void api.get<List>(`${path}/change-sets/${impact.id}/node-actions`).then((result) => setNodeActions(result.items)).catch(setError);
  }, [impact?.id, path, data['change-sets']]);

  useEffect(() => {
    if (!run || !['queued', 'running'].includes(run.status)) return;
    const timer = setInterval(() => {
      void api.get<Run>(`${workspace}/runs/${run.id}`).then((next) => {
        setRun(next);
        if (!['queued', 'running'].includes(next.status)) {
          void refresh();
          if (impact?.id && path) void api.get<RecordItem>(`${path}/change-sets/${impact.id}`).then(setImpact).catch(setError);
        }
      }).catch(setError);
    }, 1100);
    return () => clearInterval(timer);
  }, [run, workspace, refresh, impact?.id, path]);

  async function operate(action: () => Promise<void>, success?: string) {
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      await action();
      await refresh();
      if (impact?.id && path) {
        const next = await api.get<List>(`${path}/change-sets/${impact.id}/node-actions`);
        setNodeActions(next.items);
      }
      if (success) setNotice(success);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File | null) {
    if (!file || !path) return;
    await operate(async () => {
      const body = new FormData();
      body.append('file', file);
      body.append('sourceRole', sourceRole);
      const result = await api.post<RecordItem>(`${path}/evidence`, body);
      await api.post(`${path}/evidence/${result.id}/parse`, {});
    }, '原件已保存，结构化候选字段可在证据区查看。');
  }

  async function submitJob() {
    if (!path) return;
    await operate(async () => {
      const payload: Record<string, unknown> = { kind: stage, goal: goal.trim() || stages.find((s) => s.kind === stage)?.title || '处理当前阶段' };
      if (stage === 'prepare_quote') {
        if (!selectedOffer) throw new Error('请先上传并选择供应商报价原件，再运行核价节点');
        payload.costInputs = cost;
        payload.selectedSupplierOfferId = selectedOffer;
      }
      const next = await api.post<Run>(`${path}/jobs`, payload);
      setRun(next);
      setGoal('');
    }, '任务已提交，后台正在处理。');
  }

  async function submitChange() {
    if (!path || !changeText.trim()) return;
    await operate(async () => {
      const result = await api.post<RecordItem>(`${path}/change-sets`, { triggerType: 'manual', instruction: changeText.trim(), sourceId: changeSource || undefined, manualReason: '操作者提交的变更' });
      setImpact(result);
      setChangeText('');
    }, '已生成节点影响清单，请逐项检查。');
  }

  async function saveArtifact() {
    if (!selectedArtifact || !path) return;
    await operate(async () => {
      let content: unknown;
      try { content = JSON.parse(artifactText); } catch { throw new Error('成果内容需要是有效的 JSON 对象'); }
      const updated = await api.post<RecordItem>(`${path}/artifacts/${selectedArtifact.id}/versions`, { baseVersion: selectedArtifact.version, content, reason: '人工编辑' });
      setSelectedArtifact(updated);
    }, '已保存为新的不可变草稿版本。');
  }

  async function exportRevision(format: 'html' | 'xlsx' | 'pdf' | 'zip') {
    const revision = data.revisions?.at(-1);
    if (!revision || !path) return;
    await operate(async () => {
      const drafts = await api.get<List>(`${path}/revisions/${revision.number}/reply-drafts`);
      const draftVersions = Object.fromEntries(drafts.items.map((d) => [d.locale, d.draftVersion]));
      const result = await api.post<{ downloadUrl: string }>(`${path}/exports`, { revision: revision.number, draftVersions, format, mode: 'draft' });
      const blob = await api.download(result.downloadUrl.replace('/api/v1', ''));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `NavoWork-${caseId}-V${revision.number}-DRAFT.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, '已下载固定版本草稿；未发送、未代表商业批准。');
  }

  async function exportArtifact(item: RecordItem, format: 'pdf' | 'xlsx' | 'html') {
    await operate(async () => {
      const result = await api.post<{ downloadUrl: string }>(`${path}/artifacts/${item.id}/exports`, { format });
      const blob = await api.download(result.downloadUrl.replace('/api/v1', ''));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${item.kind}-V${item.version}-DRAFT.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, `已下载 ${item.title} V${item.version} 草稿。`);
  }

  if (loading) return <Loading label="正在读取服务端工作台" />;
  return <div className="rw-page">
    <header className="rw-header">
      {caseId && <Link className="button" to={`/inquiries/${encodeURIComponent(caseId)}`}>返回询盘画板</Link>}
      <div><span className="tw-eyebrow">REAL WORKSPACE / SOP</span><h1>包袋出口工作流</h1><p>资料、版本、节点影响与人工门禁由服务端记录。</p></div>
      <select aria-label="选择客户项目" value={caseId} onChange={(e) => { setCaseId(e.target.value); setSearch({ case: e.target.value }); setImpact(null); }}>
        {cases.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
      </select>
    </header>
    <ErrorNotice error={error} onRetry={() => void refresh()} />
    {notice && <p className="rw-notice">{notice}</p>}
    {!currentCase ? <p>还没有项目，请在首页创建询盘。</p> : <>
      <section className="rw-card"><div className="rw-title"><h2>{currentCase.title}</h2><span>业务版本 V{currentCase.currentRevision} · {currentCase.businessStatus}</span></div><p>{currentCase.customer} · {currentCase.destination || '目的地待确认'}</p><p>{currentCase.originalText}</p></section>
      <section className="rw-card"><h2>SOP 节点</h2><div className="rw-stages">{stages.map((item) => <button key={item.kind} className={stage === item.kind ? 'rw-stage selected' : 'rw-stage'} onClick={() => setStage(item.kind)}><strong>{item.title}</strong><small>{item.hint}</small><small>{sopStatus?.stages?.find((s: RecordItem) => s.kind === item.kind)?.status || 'not_started'}</small></button>)}</div><label className="rw-field">本次目标<textarea value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="描述需要 Agent 处理的具体工作" /></label>{stage === 'prepare_quote' && <><p>先上传供应商报价原件并录入报价字段，再选择用于核价的供应商。</p><select value={supplierSource} onChange={(e) => setSupplierSource(e.target.value)}><option value="">选择供应商报价证据</option>{data.evidence?.filter((i) => i.sourceRole === 'supplier_quote').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="供应商名称" /><div className="rw-costs">{Object.entries(cost).map(([key, value]) => <label key={key}>{({ base: '供应商基础成本 CNY', packaging: '包装成本 CNY', local: '本地费用 CNY', exchangeRate: '汇率 CNY/USD', margin: '目标毛利率 %', quantity: '数量' } as Record<string, string>)[key]}<input value={value} type="number" onChange={(e) => setCost((old) => ({ ...old, [key]: e.target.value }))} /></label>)}</div><button className="button" disabled={busy || !supplierSource || !supplierName.trim() || !cost.base || !cost.packaging} onClick={() => void operate(async () => { const offer = await api.post<RecordItem>(`${path}/supplier-offers`, { supplier: supplierName.trim(), evidenceSourceId: supplierSource, baseCny: cost.base, packagingCny: cost.packaging, localCny: cost.local || '0', moq: 1, leadDays: 0 }); setSelectedOffer(offer.id); setSupplierName(''); }, '供应商报价已结构化保存。')}>保存供应商报价</button><select value={selectedOffer} onChange={(e) => setSelectedOffer(e.target.value)}><option value="">未选择供应商报价</option>{data['supplier-offers']?.map((item) => <option key={item.id} value={item.id}>{item.supplier} · CNY {item.baseCny} + {item.packagingCny}</option>)}</select></>}<button className="button button-primary" disabled={busy || !!currentCase.activeRunId || ['manage_shipment', 'reconcile_payment'].includes(stage)} onClick={() => void submitJob()}>运行当前节点</button>{run && <p>Run {run.id} · {run.status} · {run.phase}{run.error ? ` · ${run.error.message}` : ''}</p>}</section>
      <div className="rw-grid">
        <section className="rw-card"><h2>原始证据与候选事实</h2><label className="rw-field">来源角色<select value={sourceRole} onChange={(e) => setSourceRole(e.target.value)}><option value="customer_request">客户需求</option><option value="supplier_quote">供应商报价</option><option value="customer_change">客户变更</option><option value="customer_po">客户 PO</option><option value="customer_approval">客户批准</option><option value="supplier_confirmation">供应商确认</option><option value="payment_receipt">财务/银行凭据</option><option value="sample_inspection">样品检查</option><option value="shipping_document">出运单证</option><option value="internal_note">内部记录</option></select></label><input type="file" accept=".txt,.eml,.csv,.pdf,.xlsx,.jpg,.jpeg,.png,.webp" onChange={(e) => { void upload(e.target.files?.[0] || null); e.target.value = ''; }} /><label className="rw-field">粘贴原文<input value={evidenceTitle} onChange={(e) => setEvidenceTitle(e.target.value)} placeholder="标题" /><textarea value={evidenceText} onChange={(e) => setEvidenceText(e.target.value)} placeholder="客户邮件、供应商回复或人工记录" /></label><button className="button" disabled={busy || !evidenceText.trim()} onClick={() => void operate(async () => { const result = await api.post<RecordItem>(`${path}/evidence`, { title: evidenceTitle, text: evidenceText, sourceRole }); await api.post(`${path}/evidence/${result.id}/parse`, {}); setEvidenceText(''); setEvidenceTitle(''); }, '证据与候选字段已保存。')}>保存并提取</button><ul>{data.evidence?.map((item) => <li key={item.id}>{item.title} · {item.sourceRole} · {item.parseStatus}</li>)}</ul><details><summary>查看候选事实（{data.facts?.length || 0}）</summary><ul>{data.facts?.map((item) => <li key={item.id}>{item.fieldPath}: {String(item.value)} · {item.status}</li>)}</ul></details></section>
        <section className="rw-card"><h2>通用变更与节点影响</h2><select value={changeSource} onChange={(e) => setChangeSource(e.target.value)}><option value="">选择变更来源（正式激活必需）</option>{data.evidence?.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.sourceRole}</option>)}</select><textarea value={changeText} onChange={(e) => setChangeText(e.target.value)} placeholder="例如：供应商将交期从 28 天延长到 35 天，请分析影响哪些 SOP 节点" /><button className="button button-primary" disabled={busy || !changeText.trim()} onClick={() => void submitChange()}>分析变更影响</button>{impact && <><p>ChangeSet {impact.id} · 影响 {impact.nodeImpacts?.length || 0} 个节点 · {impact.status}</p><button className="button" disabled={busy || !!currentCase.activeRunId || impact.status === 'applied'} onClick={() => void operate(async () => { const next = await api.post<Run>(`${path}/change-sets/${impact.id}/regenerate`, {}); setRun(next); }, '已提交受影响成果的候选修订。')}>生成联动修订草稿</button><input value={changeReason} onChange={(e) => setChangeReason(e.target.value)} placeholder="逐节点处理依据（必填）" /><div className="rw-impact-list">{impact.nodeImpacts?.map((item: RecordItem) => <div key={item.nodeKey}><button onClick={() => setStage(nodeStage(item.nodeKey))}><strong>{item.nodeKey}</strong><small>{item.reason?.join('；')}</small><span>打开对应阶段 →</span></button><small>处理记录：{nodeActions.filter((action) => action.nodeKey === item.nodeKey).map((action) => action.action).join('、') || '待处理'}</small><button className="button" disabled={busy || !changeReason.trim() || impact.status === 'applied'} onClick={() => void operate(async () => { await api.post(`${path}/change-sets/${impact.id}/node-actions`, { nodeKey: item.nodeKey, action: 'review', reason: changeReason.trim() }); }, `${item.nodeKey} 已记录复核动作`)}>记录复核</button><button className="button" disabled={busy || !changeReason.trim() || !selectedArtifact || selectedArtifact.version < 2 || impact.status === 'applied'} onClick={() => void operate(async () => { await api.post(`${path}/change-sets/${impact.id}/node-actions`, { nodeKey: item.nodeKey, action: 'edit', reason: changeReason.trim(), targetArtifactVersionId: selectedArtifact?.id }); }, `${item.nodeKey} 已关联新版成果`)}>关联已编辑成果</button><button className="button" disabled={busy || !changeReason.trim() || impact.status === 'applied'} onClick={() => void operate(async () => { await api.post(`${path}/change-sets/${impact.id}/node-actions`, { nodeKey: item.nodeKey, action: 'no_impact', reason: changeReason.trim() }); }, `${item.nodeKey} 已记录无影响结论`)}>标记无需修改</button></div>)}</div><button className="button" disabled={busy || !impact.sourceId || impact.status === 'applied'} onClick={() => void operate(async () => { const updated = await api.post<RecordItem>(`${path}/change-sets/${impact.id}/activate`, {}); setImpact(updated); }, '变更已通过门禁并激活。')}>激活已处理变更</button></>}{!impact && <p>任何来源或业务字段变化都可分析；系统不会直接覆盖既有正式版本。</p>}</section>
      </div>
      <section className="rw-card"><h2>已保存的业务变更</h2><ul>{data['change-sets']?.map((item) => <li key={item.id}><button className="button" onClick={() => { setImpact(item); setChangeReason(''); }}>{item.instruction || item.sourceText || item.id} · {item.status}</button></li>)}</ul>{!data['change-sets']?.length && <p>暂无业务变更。</p>}</section>
      <div className="rw-grid">
        <section className="rw-card"><h2>成果版本与编辑</h2><ul>{data.artifacts?.map((item) => <li key={item.id}><button onClick={() => { setSelectedArtifact(item); setArtifactText(JSON.stringify(item.content, null, 2)); setArtifactValidation(null); }}>{item.title} · {item.kind} V{item.version} · {item.status}</button> {(['pdf', 'xlsx', 'html'] as const).map((format) => <button key={format} className="button" disabled={busy} onClick={() => void exportArtifact(item, format)}>{format.toUpperCase()}</button>)}</li>)}</ul>{selectedArtifact && <><p>编辑 {selectedArtifact.title}：保存时生成新版本</p><textarea className="rw-json" value={artifactText} onChange={(e) => setArtifactText(e.target.value)} /><button className="button" disabled={busy} onClick={() => void saveArtifact()}>保存新草稿版本</button><button className="button" disabled={busy} onClick={() => void operate(async () => { setArtifactValidation(await api.post<RecordItem>(`${path}/artifacts/${selectedArtifact.id}/validate`, {})); })}>校验固定版本</button>{artifactValidation && <p>校验：{artifactValidation.status} · {artifactValidation.results?.map((r: RecordItem) => r.message).join('；') || '无缺失字段'}</p>}</>}</section>
        <section className="rw-card"><h2>审批与交付</h2><label className="rw-field">审批范围<select value={approvalScope} onChange={(e) => setApprovalScope(e.target.value)}><option value="commercial_quotation_approval">内部报价批准</option><option value="customer_spec_approval">客户规格确认</option><option value="supplier_production_confirmation">供应商生产确认</option></select></label><label className="rw-field">证据<select value={approvalEvidence} onChange={(e) => setApprovalEvidence(e.target.value)}><option value="">选择证据</option>{data.evidence?.map((item) => <option value={item.id} key={item.id}>{item.title} · {item.sourceRole}</option>)}</select></label><input value={approvalNote} onChange={(e) => setApprovalNote(e.target.value)} placeholder="批准依据或说明" /><button className="button" disabled={busy || !data.revisions?.length || (approvalScope !== 'commercial_quotation_approval' && !approvalEvidence) || (approvalScope === 'customer_spec_approval' && !data.artifacts?.some((i) => i.kind === 'spec')) || (approvalScope === 'commercial_quotation_approval' && !data.artifacts?.some((i) => i.kind === 'quotation'))} onClick={() => void operate(async () => { const latest = (kind: string) => data.artifacts.filter((i) => i.kind === kind).sort((a, b) => b.version - a.version)[0]; await api.post(`${path}/approvals`, { scope: approvalScope, targetVersionId: approvalScope === 'customer_spec_approval' ? latest('spec').id : approvalScope === 'commercial_quotation_approval' ? latest('quotation').id : String(data.revisions.at(-1)?.number), decision: 'approved', evidenceRefs: approvalEvidence ? [approvalEvidence] : [], note: approvalNote }); setApprovalNote(''); }, '批准已绑定指定版本。')}>记录指定版本批准</button><p>已有批准 {data.approvals?.length || 0} 项。草稿导出不代表正式发送。</p><div className="rw-actions">{(['html', 'xlsx', 'pdf', 'zip'] as const).map((format) => <button className="button" key={format} disabled={busy || !data.revisions?.length} onClick={() => void exportRevision(format)}>下载 {format.toUpperCase()} 草稿</button>)}</div></section>
      </div>
      <section className="rw-card"><h2>样品、订单与生产门禁</h2><div className="rw-grid"><div><p>样品批准须附客户书面证据。</p><select value={sampleEvidence} onChange={(e) => setSampleEvidence(e.target.value)}><option value="">选择样品批准证据</option>{data.evidence?.filter((i) => i.sourceRole === 'customer_approval').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><button className="button" disabled={busy || !sampleEvidence || !data.artifacts?.some((i) => i.kind === 'spec')} onClick={() => void operate(async () => { const spec = data.artifacts.filter((i) => i.kind === 'spec').sort((a, b) => b.version - a.version)[0]; await api.post(`${path}/samples`, { specVersionId: spec.id, customerApproved: true, evidenceSourceId: sampleEvidence }); }, '样品批准记录已保存。')}>记录样品批准</button></div><div><p>订单与付款保障分别核验。</p><select value={orderDocument} onChange={(e) => setOrderDocument(e.target.value)}><option value="">选择订单文件</option>{data.evidence?.filter((i) => i.sourceRole === 'customer_po').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><select value={buyerEvidence} onChange={(e) => setBuyerEvidence(e.target.value)}><option value="">选择买方确认</option>{data.evidence?.filter((i) => i.sourceRole === 'customer_approval').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><select value={sellerEvidence} onChange={(e) => setSellerEvidence(e.target.value)}><option value="">选择卖方确认</option>{data.evidence?.filter((i) => i.sourceRole === 'internal_note').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><button className="button" disabled={busy || !orderDocument || !buyerEvidence || !sellerEvidence} onClick={() => void operate(async () => { await api.post(`${path}/order-confirmations`, { documentVersionId: orderDocument, buyerConfirmed: true, sellerConfirmed: true, buyerEvidenceSourceId: buyerEvidence, sellerEvidenceSourceId: sellerEvidence }); }, '订单文件已分别关联买卖双方确认。')}>记录双方确认</button><select value={paymentEvidence} onChange={(e) => setPaymentEvidence(e.target.value)}><option value="">选择付款保障证据</option>{data.evidence?.filter((i) => i.sourceRole === 'payment_receipt').map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><input value={paymentBasis} onChange={(e) => setPaymentBasis(e.target.value)} placeholder="人工核验依据，例如银行入账记录编号" /><button className="button" disabled={busy || !paymentEvidence || !paymentBasis.trim()} onClick={() => void operate(async () => { await api.post(`${path}/payment-assurance-checks`, { decision: 'verified', evidenceSourceId: paymentEvidence, verificationBasis: paymentBasis.trim(), method: 'manual_review' }); }, '已记录责任人核验结果。')}>记录付款保障核验</button></div></div><button className="button button-primary" disabled={busy} onClick={() => void operate(async () => { const pack = await api.post<RecordItem>(`${path}/production-packs`, { revision: currentCase.currentRevision }); const result = await api.post<RecordItem>(`${path}/production-packs/${pack.id}/validate`, {}); setNotice(result.status === 'blocked' ? `放行阻断：${result.missing.join('；')}` : '生产资料门禁通过；仍不代表工厂实际开工。'); })}>检查生产资料门禁</button></section>
    </>}
  </div>;
}

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleAlert,
  Download,
  FileText,
  Link2,
  PackageCheck,
  PencilLine,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Truck,
} from 'lucide-react';
import type {
  SupplierOffer,
  WorkbenchApproval,
  WorkbenchArtifact,
  WorkbenchData,
} from '../../api/types';
import { EmptyHint, Field, MissingList, Pill, Section, money, shortDate, stageStatusLabel } from './ui';

type SaveArtifact = (kind: string, content: Record<string, any>, baseVersion: number) => Promise<boolean>;
type ConfirmGate = (scope: string, target: WorkbenchArtifact, evidenceRole: string, options?: { basis?: string; note?: string }) => void;
type RunAgent = (instruction: string, node?: string) => void;

const sourceRoleLabel: Record<string, string> = {
  customer_request: '客户询盘',
  supplier_quote: '供应商报价',
  customer_change: '客户变更',
  customer_po: '客户 PO',
  customer_approval: '客户确认',
  supplier_confirmation: '供应商确认',
  payment_receipt: '付款凭据',
  sample_inspection: '样品检查',
  shipping_document: '出运单证',
  internal_note: '内部记录',
};

const specValue = (fields: Record<string, any> | undefined, key: string) => {
  const value = fields?.[key];
  return value == null ? '' : String(value);
};

export function InquiryPanel({ data, onAgent }: { data: WorkbenchData; onAgent: RunAgent }) {
  const profile = data.customerProfile?.profile || data.customerContext || {};
  const assessment = data.artifacts.inquiry_assessment?.content || {};
  return (
    <div className="wbv2-stack">
      <Section
        eyebrow="01 · QUALIFY"
        title="客户与询盘"
        description="先确认客户背景、采购条件和缺项，再进入规格与报价。"
        actions={
          <button className="button button-primary" onClick={() => onAgent('请阅读客户询盘，核验客户背景与采购条件，整理需要向客户澄清的关键问题。不要生成规格或报价。', 'inquiry')}>
            <Sparkles size={14} /> 让 Agent 分析
          </button>
        }
      >
        <div className="wbv2-customer">
          <div className="wbv2-customer-main">
            <span className="wbv2-avatar">{String(profile.company || data.case.customer || 'C').slice(0, 1).toUpperCase()}</span>
            <div>
              <h3>{profile.company || data.case.customer}</h3>
              <p>{[profile.country, profile.business].filter(Boolean).join(' · ') || '客户背景待补充'}</p>
            </div>
          </div>
          <div className="wbv2-kv">
            <div><span>来源</span><strong>{profile.channel || data.customerContext.channel || '待补充'}</strong></div>
            <div><span>邮箱</span><strong>{profile.email || data.customerContext.email || '待补充'}</strong></div>
            <div><span>目的地</span><strong>{data.case.destination || '待确认'}</strong></div>
            <div><span>当前版本</span><strong>V{data.case.currentRevision}</strong></div>
          </div>
        </div>
        {(assessment.summary || data.customerContext.summary) && <p className="wbv2-note">{assessment.summary || data.customerContext.summary}</p>}
        <div className="wbv2-split">
          <div>
            <h4 className="wbv2-label">客户原文</h4>
            <pre className="wbv2-original">{data.case.originalText}</pre>
          </div>
          <div>
            <h4 className="wbv2-label">待确认</h4>
            {assessment.missing?.length ? (
              <ul className="wbv2-check-list">
                {assessment.missing.map((item: string) => <li key={item}><CircleAlert size={13} />{item}</li>)}
              </ul>
            ) : data.customerContext.checks?.some((check) => check.status !== 'matched') ? (
              <ul className="wbv2-check-list">
                {data.customerContext.checks.filter((check) => check.status !== 'matched').map((check) => <li key={check.label}><CircleAlert size={13} />{check.label}：{check.detail}</li>)}
              </ul>
            ) : (
              <EmptyHint>当前没有阻断项；可继续推进规格。</EmptyHint>
            )}
            {assessment.risks?.length > 0 && (
              <>
                <h4 className="wbv2-label wbv2-label-gap">风险</h4>
                <ul className="wbv2-check-list is-warn">
                  {assessment.risks.map((item: string) => <li key={item}><CircleAlert size={13} />{item}</li>)}
                </ul>
              </>
            )}
          </div>
        </div>
        {profile.checks?.length > 0 && (
          <div className="wbv2-checks">
            {profile.checks.map((check: any) => (
              <div key={check.label}>
                <span className={`wbv2-dot wbv2-dot-${check.status === 'matched' ? 'confirmed' : check.status === 'review' ? 'draft' : 'empty'}`} />
                <strong>{check.label}</strong>
                <small>{check.detail}</small>
              </div>
            ))}
          </div>
        )}
      </Section>
      <Section eyebrow="SOURCES" title="资料与依据" description="Agent 只读取本项目已授权的原件、知识库和公司资产。">
        <div className="wbv2-source-list">
          {data.evidence.slice(0, 8).map((item) => (
            <div key={item.id} className="wbv2-source-row">
              <FileText size={15} />
              <div><strong>{item.title}</strong><small>{sourceRoleLabel[item.sourceRole] || item.sourceRole}</small></div>
              <Pill tone={item.sourceRole === 'customer_request' ? 'blue' : 'neutral'}>{item.parseStatus === 'succeeded' ? '已解析' : '原件'}</Pill>
            </div>
          ))}
          {!data.evidence.length && <EmptyHint>还没有上传原件。请先在“资料”中导入客户询盘或供应商报价。</EmptyHint>}
        </div>
      </Section>
    </div>
  );
}

export function RequirementsPanel({ data, onAgent, onSave, onConfirm, busy }: { data: WorkbenchData; onAgent: RunAgent; onSave: SaveArtifact; onConfirm: ConfirmGate; busy: boolean }) {
  const spec = data.artifacts.spec;
  const bom = data.artifacts.bom;
  const [fields, setFields] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const version = spec?.version || 0;

  useEffect(() => {
    const next = Object.fromEntries((data.schema.specFields || []).map((field) => [field.key, specValue(spec?.content?.fields, field.key)]));
    setFields(next);
    setDirty(false);
    // Only reset when the server version changes; a refetch of the same
    // version must not discard the user's in-progress edits.
  }, [version, data.schema.specFields]);

  const missing = (spec?.content?.missing as string[]) || [];
  const approved = data.stages.find((item) => item.key === 'requirements')?.status === 'confirmed';
  const groupMissing = (keys: string[]) => keys.filter((key) => missing.includes(key)).length;
  const save = async () => {
    if (!spec) return;
    setSaving(true);
    try {
      const ok = await onSave('spec', { fields }, spec.version);
      if (ok) setDirty(false);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="wbv2-stack">
      <Section
        eyebrow="02 · TECH PACK"
        title="客户需求与规格"
        description="箱包 Tech Pack 是询价、打样、生产和验货的共同依据。未知字段保持空白。"
        actions={
          <>
            <button className="button" onClick={() => onAgent('请读取客户询盘与规格资料，补全箱包 Tech Pack 和 BOM；缺失的关键参数向我提问，不要编造。', 'requirements')}>
              <Sparkles size={14} /> 让 Agent 补齐
            </button>
            {spec && <button className="button" disabled={!dirty || saving || busy} onClick={() => void save()}>{saving ? '保存中…' : '保存规格'}</button>}
            {spec && !approved && <button className="button" disabled={busy || missing.length > 0} onClick={() => onConfirm('customer_spec_approval', spec, 'customer_approval')}><ShieldCheck size={14} /> 客户确认规格</button>}
            {approved && <Pill tone="green"><Check size={12} /> 客户已确认规格</Pill>}
            {spec && <button className="button button-ghost" onClick={() => onAgent('请逐项核对当前 Tech Pack 与客户原件，指出冲突、缺失和需要客户确认的内容。', 'requirements')}><RefreshCw size={13} /> 核对</button>}
          </>
        }
      >
        {!spec ? (
          <EmptyHint>尚未生成规格。点击“让 Agent 补齐”，从客户询盘开始整理 Tech Pack。</EmptyHint>
        ) : (
          <>
            <div className="wbv2-meta-row">
              <Pill tone="blue">V{spec.version}</Pill>
              <span>{missing.length ? `${missing.length} 项待确认` : '必填项已齐备'}</span>
              <MissingList items={missing} />
            </div>
            <div className="wbv2-spec-groups">
              {(data.schema.specGroups || []).map((group) => (
                <div className="wbv2-spec-group" key={group.key}>
                  <header>
                    <h3>{group.title}</h3>
                    {groupMissing(group.fields.map((field) => field.key)) > 0 && <span className="wbv2-group-missing">{groupMissing(group.fields.map((field) => field.key))} 项缺失</span>}
                  </header>
                  <div className="wbv2-spec-grid">
                    {group.fields.map((field) => (
                      <Field key={field.key} label={field.label} wide={field.key === 'logo' || field.key === 'packaging' || field.key === 'structure'}>
                        <input
                          value={fields[field.key] || ''}
                          placeholder={field.required ? '必填' : '未提供可留空'}
                          onChange={(event) => { setFields((old) => ({ ...old, [field.key]: event.target.value })); setDirty(true); }}
                        />
                      </Field>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="wbv2-inline-note">
              <Link2 size={14} /> 已知字段由 Agent 从客户原件抽取；编辑后会生成新的规格版本，旧版本保留。
            </div>
          </>
        )}
      </Section>
      <Section
        eyebrow="BOM"
        title="物料与辅料清单"
        description="主料、里布、拉链/五金、包装各自独立成行，便于询价和核价。"
        actions={<button className="button" onClick={() => onAgent('请根据当前规格和客户要求整理 BOM，包含面料、里布、拉链/五金、包装；没有单价的先留空。', 'requirements')}><Sparkles size={14} /> 让 Agent 补 BOM</button>}
      >
        {!bom?.content?.rows?.length ? (
          <EmptyHint>尚无 BOM。</EmptyHint>
        ) : (
          <div className="wbv2-table-wrap">
            <table className="wbv2-table">
              <thead><tr><th>类别</th><th>物料</th><th>规格</th><th>单件用量</th><th>单位</th><th>单价</th><th>供应商</th></tr></thead>
              <tbody>
                {bom.content.rows.map((row: any, index: number) => (
                  <tr key={`${row.item}-${index}`}>
                    <td><Pill>{row.category || 'material'}</Pill></td>
                    <td><strong>{row.item}</strong></td>
                    <td>{row.spec || '—'}</td>
                    <td>{row.quantityPerPiece || '—'}</td>
                    <td>{row.unit || '—'}</td>
                    <td>{row.unitPriceCny ? `¥${row.unitPriceCny}` : '—'}</td>
                    <td>{row.supplier || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}

export function CostingPanel({ data, onAgent, onSave, onConfirm, onExport, busy }: { data: WorkbenchData; onAgent: RunAgent; onSave: SaveArtifact; onConfirm: ConfirmGate; onExport: (kind: string, format: string) => void; busy: boolean }) {
  const quote = data.artifacts.quotation;
  const cost = data.artifacts.cost;
  const comparison = data.artifacts.comparison;
  const [terms, setTerms] = useState<Record<string, any>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const version = quote?.version || 0;
  useEffect(() => {
    const content = quote?.content || {};
    setTerms({
      incoterm: content.incoterm || '',
      incotermsVersion: content.incotermsVersion || '',
      namedPlace: content.namedPlace || '',
      paymentTerms: content.paymentTerms || '',
      validUntil: content.validUntil || '',
      moq: content.moq ?? '',
      sampleTime: content.sampleTime || '',
      productionTime: content.productionTime || '',
      exclusions: (content.exclusions || []).join(', '),
    });
    setDirty(false);
    // Same rule as Tech Pack: keep local edits across a refetch of this version.
  }, [version]);
  const saveTerms = async () => {
    if (!quote) return;
    setSaving(true);
    try {
      const ok = await onSave('quotation', { ...terms, moq: terms.moq === '' ? null : Number(terms.moq), exclusions: String(terms.exclusions || '').split(',').map((item) => item.trim()).filter(Boolean) }, quote.version);
      if (ok) setDirty(false);
    } finally {
      setSaving(false);
    }
  };
  const costingStatus = data.stages.find((stage) => stage.key === 'costing')?.status;
  const approved = costingStatus === 'confirmed';
  const quoteReady = costingStatus === 'ready';
  return (
    <div className="wbv2-stack">
      <Section
        eyebrow="03 · COSTING"
        title="供应商报价与核价"
        description="多家报价先归一化，再由确定性工具计算；Agent 不手算金额。"
        actions={
          <>
            <button className="button" onClick={() => onAgent('请读取本项目的供应商报价原件，逐家登记报价，并按我为本次任务提供的汇率、毛利和数量核价。不要编造缺失价格。', 'costing')}>
              <Sparkles size={14} /> 让 Agent 核价
            </button>
            {comparison && <button className="button button-ghost" onClick={() => onExport('comparison', 'xlsx')}><Download size={13} /> 导出比较</button>}
          </>
        }
      >
        {!data.supplierOffers.length ? (
          <EmptyHint>还没有结构化供应商报价。上传报价原件后，让 Agent 读取或手动登记。</EmptyHint>
        ) : (
          <div className="wbv2-table-wrap">
            <table className="wbv2-table">
              <thead><tr><th>供应商</th><th>基础价</th><th>包装</th><th>本地费用</th><th>MOQ</th><th>交期</th><th>有效期</th><th>含包装</th></tr></thead>
              <tbody>
                {data.supplierOffers.map((offer: SupplierOffer) => (
                  <tr key={offer.id} className={cost?.content?.supplierOfferId === offer.id ? 'is-selected' : ''}>
                    <td><strong>{offer.supplier}</strong><small>{cost?.content?.supplierOfferId === offer.id ? '本次核价采用' : ''}</small></td>
                    <td>¥{offer.baseCny}</td>
                    <td>¥{offer.packagingCny}</td>
                    <td>¥{offer.localCny}</td>
                    <td>{offer.moq}</td>
                    <td>{offer.leadDays ? `${offer.leadDays} 天` : '—'}</td>
                    <td>{offer.validUntil || '—'}</td>
                    <td>{offer.includesPackaging ? '是' : '否'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="wbv2-inline-note"><CircleAlert size={14} /> 核价需要你明确汇率和毛利率，例如“汇率 7.20、毛利率 20%”；Agent 不会自行假设。</div>
        {cost && (
          <div className="wbv2-cost-grid">
            <div><span>单件成本</span><strong>¥{cost.content.unitCostCny}</strong></div>
            <div><span>汇率</span><strong>{cost.content.exchangeRate}</strong></div>
            <div><span>毛利率</span><strong>{Number(cost.content.margin) * 100}%</strong></div>
            <div><span>建议单价</span><strong className="is-accent">{money(cost.content.unitPriceUsd)}</strong></div>
            <div><span>商品小计</span><strong>{money(cost.content.totalUsd)}</strong></div>
          </div>
        )}
      </Section>
      <Section
        eyebrow="QUOTATION"
        title="客户报价单"
        description="贸易术语、付款方式、有效期与不含项必须写清。草稿不等于已批准或已发送。"
        actions={
          <>
            {quote && <button className="button" disabled={!dirty || saving || busy} onClick={() => void saveTerms()}>{saving ? '保存中…' : '保存条款'}</button>}
            {quote && !approved && <button className="button button-primary" disabled={busy || !quoteReady} onClick={() => onConfirm('commercial_quotation_approval', quote, '')}><ShieldCheck size={14} /> 内部批准报价</button>}
            {approved && <Pill tone="green"><Check size={12} /> 已批准</Pill>}
            {quote && <button className="button button-ghost" onClick={() => onExport('quotation', 'pdf')}><Download size={13} /> 导出 PDF</button>}
          </>
        }
      >
        {!quote ? (
          <EmptyHint>尚未生成客户报价。先完成核价，再让 Agent 写报价条款。</EmptyHint>
        ) : (
          <>
            <div className="wbv2-quote-head">
              <div><span>单价</span><strong>{money(quote.content.unitPriceUsd)}</strong><small>× {quote.content.quantity} 件</small></div>
              <div><span>总额</span><strong>{money(quote.content.totalUsd)}</strong></div>
              <div><span>贸易条款</span><strong>{[quote.content.incoterm, quote.content.incotermsVersion, quote.content.namedPlace].filter(Boolean).join(' / ') || '—'}</strong></div>
              <div><span>有效期</span><strong>{quote.content.validUntil || '—'}</strong></div>
            </div>
            <div className="wbv2-spec-grid">
              <Field label="贸易术语"><input value={terms.incoterm || ''} onChange={(event) => { setTerms((old) => ({ ...old, incoterm: event.target.value })); setDirty(true); }} /></Field>
              <Field label="术语版本"><input value={terms.incotermsVersion || ''} onChange={(event) => { setTerms((old) => ({ ...old, incotermsVersion: event.target.value })); setDirty(true); }} /></Field>
              <Field label="指定地点/港口"><input value={terms.namedPlace || ''} onChange={(event) => { setTerms((old) => ({ ...old, namedPlace: event.target.value })); setDirty(true); }} /></Field>
              <Field label="付款方式"><input value={terms.paymentTerms || ''} onChange={(event) => { setTerms((old) => ({ ...old, paymentTerms: event.target.value })); setDirty(true); }} /></Field>
              <Field label="报价有效期"><input type="date" value={terms.validUntil || ''} onChange={(event) => { setTerms((old) => ({ ...old, validUntil: event.target.value })); setDirty(true); }} /></Field>
              <Field label="MOQ"><input type="number" value={terms.moq} onChange={(event) => { setTerms((old) => ({ ...old, moq: event.target.value })); setDirty(true); }} /></Field>
              <Field label="样品时间"><input value={terms.sampleTime || ''} onChange={(event) => { setTerms((old) => ({ ...old, sampleTime: event.target.value })); setDirty(true); }} /></Field>
              <Field label="生产时间"><input value={terms.productionTime || ''} onChange={(event) => { setTerms((old) => ({ ...old, productionTime: event.target.value })); setDirty(true); }} /></Field>
              <Field label="不含项" wide><input value={terms.exclusions || ''} placeholder="freight, insurance, destination charges" onChange={(event) => { setTerms((old) => ({ ...old, exclusions: event.target.value })); setDirty(true); }} /></Field>
            </div>
          </>
        )}
      </Section>
    </div>
  );
}

export function SamplePanel({ data, onAgent, onConfirm, busy }: { data: WorkbenchData; onAgent: RunAgent; onConfirm: ConfirmGate; busy: boolean }) {
  const sample = data.artifacts.sample;
  const content = sample?.content || {};
  const approved = data.stages.find((item) => item.key === 'sample')?.status === 'confirmed';
  return (
    <Section
      eyebrow="04 · SAMPLE"
      title="打样与样品确认"
      description="样品种类、轮次、检查、反馈和客户书面批准必须形成证据链。"
      actions={
        <>
          <button className="button" onClick={() => onAgent('请记录本轮样品：样品种类、轮次、编号、规格版本、费用、快递单号、检查项、客户反馈和封样；客户批准保持待确认。', 'sample')}>
            <Sparkles size={14} /> 让 Agent 记录
          </button>
          {sample && !approved && <button className="button button-primary" disabled={busy} onClick={() => onConfirm('sample_approval', sample, 'customer_approval')}><ShieldCheck size={14} /> 记录客户批准</button>}
          {approved && <Pill tone="green"><Check size={12} /> 客户已批准</Pill>}
        </>
      }
    >
      {!sample ? (
        <EmptyHint>尚未记录样品。规格和报价形成后，安排开发样/确认样/产前样。</EmptyHint>
      ) : (
        <>
          <div className="wbv2-quote-head">
            <div><span>样品编号</span><strong>{content.sampleRef || '—'}</strong><small>{content.type || '—'} · 第 {content.round || 1} 轮</small></div>
            <div><span>规格版本</span><strong>{content.specVersionId ? `V${content.specVersionId.split('_v').pop()}` : '—'}</strong></div>
            <div><span>费用</span><strong>{content.feeUsd ? `$${content.feeUsd}` : '—'}</strong><small>{content.courierUsd ? `快递 $${content.courierUsd}` : ''}</small></div>
            <div><span>快递</span><strong>{content.courier || '—'}</strong><small>{content.tracking || ''}</small></div>
          </div>
          <div className="wbv2-check-grid">
            {Object.entries(content.checks || {}).map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <Pill tone={value === 'passed' ? 'green' : value === 'failed' ? 'red' : 'amber'}>{value === 'passed' ? '通过' : value === 'failed' ? '未通过' : '待检查'}</Pill>
              </div>
            ))}
          </div>
          {content.feedback && <p className="wbv2-note">{content.feedback}</p>}
          {content.sealedSample?.ref && <p className="wbv2-note">封样：{content.sealedSample.ref} · {content.sealedSample.location || '取样间'}</p>}
        </>
      )}
    </Section>
  );
}

export function OrderPanel({ data, onAgent, onConfirm, busy }: { data: WorkbenchData; onAgent: RunAgent; onConfirm: ConfirmGate; busy: boolean }) {
  const order = data.artifacts.order;
  const payment = data.artifacts.payment;
  const content = order?.content || {};
  const po = content.po || {};
  const pi = content.pi || {};
  const diff = content.diff || [];
  const approvals = data.approvals;
  const buyer = approvals.some((item) => item.scope === 'order_buyer_confirmation' && item.targetVersionId === order?.itemId);
  const seller = approvals.some((item) => item.scope === 'order_seller_confirmation' && item.targetVersionId === order?.itemId);
  const paid = approvals.some((item) => item.scope === 'payment_verification' && item.targetVersionId === payment?.itemId);
  const orderBlocked = diff.some((row: any) => row.status === 'conflict' || row.status === 'missing');
  return (
    <div className="wbv2-stack">
      <Section
        eyebrow="05 · ORDER"
        title="PO、PI 与付款保障"
        description="PO 必须与已报价、已确认的规格对齐；双方确认和付款核验由人记录。"
        actions={
          <button className="button" onClick={() => onAgent('请读取客户 PO，核对数量、单价、贸易术语、指定地点、付款方式和交期，生成 PI 草稿、PO 差异和付款计划；双方确认保持待确认。', 'order')}>
            <Sparkles size={14} /> 让 Agent 核对 PO
          </button>
        }
      >
        {!order ? (
          <EmptyHint>尚未登记订单。客户 PO 到达后，让 Agent 读取并核对。</EmptyHint>
        ) : (
          <>
            <div className="wbv2-order-grid">
              <div>
                <h4 className="wbv2-label">客户 PO</h4>
                <dl className="wbv2-dl">
                  <div><dt>PO 号</dt><dd>{po.number || '—'}</dd></div>
                  <div><dt>买方</dt><dd>{po.buyer || '—'}</dd></div>
                  <div><dt>数量</dt><dd>{po.quantity || '—'}</dd></div>
                  <div><dt>单价</dt><dd>{money(po.unitPriceUsd)}</dd></div>
                  <div><dt>总额</dt><dd>{money(po.totalUsd)}</dd></div>
                  <div><dt>交货</dt><dd>{po.deliveryDate || '—'}</dd></div>
                </dl>
              </div>
              <div>
                <h4 className="wbv2-label">形式发票 PI</h4>
                <dl className="wbv2-dl">
                  <div><dt>PI 号</dt><dd>{pi.number || '—'}</dd></div>
                  <div><dt>卖方</dt><dd>{pi.seller || '—'}</dd></div>
                  <div><dt>银行</dt><dd>{pi.bank || '—'}</dd></div>
                  <div><dt>HS 编码</dt><dd>{pi.hsCode || '—'}</dd></div>
                  <div><dt>原产地</dt><dd>{pi.origin || '—'}</dd></div>
                  <div><dt>收货人</dt><dd>{pi.consignee || '—'}</dd></div>
                </dl>
              </div>
            </div>
            <div className="wbv2-diff">
              {diff.map((row: any) => (
                <div key={row.field} className={`wbv2-diff-row is-${row.status}`}>
                  <span>{row.field}</span>
                  <strong>{String(row.po ?? '—')}</strong>
                  <ChevronRight size={13} />
                  <strong>{String(row.baseline ?? '—')}</strong>
                  <Pill tone={row.status === 'match' ? 'green' : row.status === 'conflict' ? 'red' : 'amber'}>{row.status === 'match' ? '一致' : row.status === 'conflict' ? '冲突' : row.status === 'missing' ? '缺失' : '复核'}</Pill>
                </div>
              ))}
            </div>
          </>
        )}
      </Section>
      <Section
        eyebrow="PAYMENT"
        title="付款计划与确认"
        description="定金、尾款或信用证节点逐项登记；到账只能由人工核验。"
        actions={
          <>
            {order && !buyer && <button className="button" disabled={busy || orderBlocked} onClick={() => onConfirm('order_buyer_confirmation', order, 'customer_approval')}>买方确认</button>}
            {order && !seller && <button className="button" disabled={busy || orderBlocked} onClick={() => onConfirm('order_seller_confirmation', order, 'internal_note')}>卖方确认</button>}
            {payment && !paid && <button className="button button-primary" disabled={busy} onClick={() => onConfirm('payment_verification', payment, 'payment_receipt', { basis: '人工核对付款凭据与合同金额' })}><ShieldCheck size={14} /> 核验付款</button>}
          </>
        }
      >
        {!payment?.content?.schedule?.length ? (
          <EmptyHint>尚未登记付款计划。</EmptyHint>
        ) : (
          <div className="wbv2-table-wrap">
            <table className="wbv2-table">
              <thead><tr><th>节点</th><th>比例</th><th>金额</th><th>到期日</th><th>状态</th></tr></thead>
              <tbody>
                {payment.content.schedule.map((row: any, index: number) => (
                  <tr key={`${row.milestone}-${index}`}>
                    <td><strong>{row.milestone}</strong></td>
                    <td>{row.ratio ? `${Number(row.ratio) * 100}%` : '—'}</td>
                    <td>{money(row.amountUsd)}</td>
                    <td>{row.due || '—'}</td>
                    <td><Pill tone={paid ? 'green' : 'amber'}>{paid ? '已核验' : '待核验'}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {order && <div className="wbv2-inline-note"><Check size={14} /> 买方确认：{buyer ? '已记录' : '待记录'} · 卖方确认：{seller ? '已记录' : '待记录'}</div>}
      </Section>
    </div>
  );
}

export function ProductionPanel({ data, onAgent, onConfirm, onRelease, busy, onStage }: { data: WorkbenchData; onAgent: RunAgent; onConfirm: ConfirmGate; onRelease: () => void; busy: boolean; onStage: (key: string) => void }) {
  const production = data.artifacts.production;
  const ta = data.artifacts.ta?.content || {};
  const qc = data.artifacts.qc?.content || {};
  const content = production?.content || {};
  const supplier = data.approvals.some((item) => item.scope === 'supplier_production_confirmation' && item.targetVersionId === production?.itemId);
  const released = data.stages.find((item) => item.key === 'production')?.status === 'confirmed';
  return (
    <div className="wbv2-stack">
      <Section
        eyebrow="06 · PRODUCTION"
        title="生产资料与验货准备"
        description="生产资料、T&A、QC 检查表引用固定版本；放行前逐项核对门禁。"
        actions={
          <>
            <button className="button" onClick={() => onAgent('请基于当前规格、样品和订单生成生产资料、T&A 和 QC 检查表，并列出放行缺口；不要放行。', 'production')}>
              <Sparkles size={14} /> 让 Agent 生成
            </button>
            {production && !supplier && <button className="button" disabled={busy} onClick={() => onConfirm('supplier_production_confirmation', production, 'supplier_confirmation')}>供应商确认</button>}
            {production && !released && <button className="button button-primary" disabled={busy || data.gate.status !== 'passed'} onClick={onRelease}><PackageCheck size={14} /> 人工放行</button>}
            {released && <Pill tone="green"><Check size={12} /> 已放行</Pill>}
          </>
        }
      >
        {!production ? (
          <EmptyHint>尚未生成生产资料。订单与样品就绪后，让 Agent 生成生产包。</EmptyHint>
        ) : (
          <>
            <div className="wbv2-quote-head">
              <div><span>规格版本</span><strong>{content.specVersionId ? `V${content.specVersionId.split('_v').pop()}` : '—'}</strong></div>
              <div><span>样品版本</span><strong>{content.sampleVersionId ? `V${content.sampleVersionId.split('_v').pop()}` : '—'}</strong></div>
              <div><span>订单版本</span><strong>{content.orderVersionId ? `V${content.orderVersionId.split('_v').pop()}` : '—'}</strong></div>
              <div><span>验货标准</span><strong title={String(qc.standard || '')}>{String(qc.standard || '—').split(/[（(]/)[0].slice(0, 28)}</strong></div>
            </div>
            <div className="wbv2-split">
              <div>
                <h4 className="wbv2-label">T&A 计划</h4>
                <div className="wbv2-timeline">
                  {(ta.tasks || []).map((row: any) => (
                    <div key={row.day}><span>{row.day}</span><strong>{row.task}</strong><small>{row.owner}</small></div>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="wbv2-label">QC 检查</h4>
                <ul className="wbv2-check-list">
                  {(qc.checks || []).map((row: string) => <li key={row}><Check size={13} />{row}</li>)}
                </ul>
              </div>
            </div>
          </>
        )}
      </Section>
      <Section
        eyebrow="RELEASE GATE"
        title="放行检查"
        description="任何一项缺口未关闭，生产资料只能保留草稿。"
        actions={<Pill tone={data.gate.status === 'passed' ? 'green' : 'amber'}>{data.gate.status === 'passed' ? '可以人工放行' : `${data.gate.missing.length} 项缺口`}</Pill>}
      >
        {!data.gate.missing.length ? (
          <div className="wbv2-gate-ok"><Check size={18} /> 所有放行条件已满足。请仍由责任人执行人工放行。</div>
        ) : (
          <div className="wbv2-gate-list">
            {data.gate.missing.map((gap) => (
              <button key={gap.code} onClick={() => onStage(gap.stage)}>
                <span className={`wbv2-dot wbv2-dot-${gap.stage === 'production' ? 'blocked' : 'draft'}`} />
                <div><strong>{gap.message}</strong><small>{data.stages.find((stage) => stage.key === gap.stage)?.title || gap.stage}</small></div>
                <ArrowUpRight size={14} />
              </button>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

export function ApprovalHistory({ approvals }: { approvals: WorkbenchApproval[] }) {
  if (!approvals.length) return null;
  return (
    <Section eyebrow="AUDIT" title="确认记录" description="所有确认绑定具体成果版本和证据。">
      <div className="wbv2-approval-list">
        {approvals.slice().reverse().map((item) => (
          <div key={item.id}>
            <span className={`wbv2-dot wbv2-dot-${item.decision === 'rejected' ? 'blocked' : 'confirmed'}`} />
            <div><strong>{item.scope}</strong><small>{shortDate(item.createdAt)} · {item.evidenceRefs.length} 份证据</small></div>
            <Pill tone={item.decision === 'rejected' ? 'red' : 'green'}>{item.decision === 'verified' ? '已核验' : item.decision === 'rejected' ? '已拒绝' : '已确认'}</Pill>
          </div>
        ))}
      </div>
    </Section>
  );
}

export { sourceRoleLabel };

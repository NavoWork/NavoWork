import { useState } from 'react';
import { Download, MessageSquare, FileCheck2 } from 'lucide-react';
import { api } from '../api';
import { ErrorNotice } from '../components/ui';

export interface BusinessArtifact {
  id: string; kind: string; title: string; version: number; status: string; content: Record<string, unknown>; sourceRefs?: unknown[];
}
export const artifactNames: Record<string, string> = {
  customer_profile: '客户档案', requirements: '客户需求表', spec: '产品规格书', rfq: '供应商询价单', cost: '成本核算表', quotation: '客户报价单', supplier_comparison: '供应商比较', sample: '打样指令', sample_plan: '打样指令', sample_feedback: '样品反馈', po_check: 'PO 核对报告', pi: '形式发票', contract: '订单合同', production: '生产指令', production_pack: '生产资料包', production_instruction: '生产指令', timeline: '生产排程', qc: '验货清单', qc_checklist: '验货清单', follow_up: '跟进计划', shipment: '出运资料', shipping: '出运资料', payment: '收款记录', reply: '客户回复', risk_report: '风险报告', change_report: '变更分析', ta: '生产排程', po_comparison: 'PO 核对报告', order_confirmation: '订单确认', payment_assurance: '付款保障', inspection: '验货报告', packing_list: '装箱单', commercial_invoice: '商业发票', receivable: '应收款核对', after_sales: '售后处理',
};
const fieldNames: Record<string, string> = {
  factorySource: '工厂知识依据', sourceVersionId: '知识版本', sourceId: '知识条目', contentHash: '原文校验值',
  purpose: '产品用途', project_timing_original: '原始项目时间', project_timing_interpretation: '项目时间说明', budget: '预算', product_color: '产品颜色', certification_requirements: '认证要求', delivery_note: '交付说明', source: '来源', requirement: '定制要求', logo_artwork: 'LOGO源文件', method: '工艺', position: '位置', size: '尺寸', colors: '颜色',
  product: '产品', productName: '产品名称', quantity: '数量', destination: '目的地', material: '材料', dimensions: '尺寸', color: '颜色', logo: '标识工艺', packaging: '包装', specification: '产品规格', customization: '定制要求', requested_arrival: '期望到货', requestedArrival: '期望到货', missing_fields: '待补信息', missingFields: '待补信息', requirements: '需求', items: '明细', summary: '摘要', notes: '备注', status: '状态', supplier: '供应商', supplierName: '供应商', supplierOffers: '供应商报价', selectedSupplier: '已选供应商', selectedSupplierOfferId: '报价依据', costInputs: '核价条件', base: '产品成本', packagingCny: '包装费用（CNY）', baseCny: '产品成本（CNY）', localCny: '本地费用（CNY）', local: '本地费用', exchangeRate: '汇率', margin: '毛利率（%）', unitCostCny: '单件成本（CNY）', unitPriceUsd: '单价（USD）', goodsSubtotalUsd: '货值小计（USD）', totalUsd: '总额（USD）', total: '总额', totalPrice: '总价', currency: '币种', incoterm: '贸易条款', namedPlace: '指定地点', paymentTerms: '付款条款', validUntil: '有效期至', productionTime: '生产周期', sampleTime: '打样周期', leadDays: '生产天数', moq: '最低起订量', quote: '报价', risks: '风险事项', reason: '原因', action: '处理要求', nextAction: '下一步', checklist: '核对清单', evidenceRefs: '依据', sourceRefs: '资料依据', sourceVersionIds: '来源版本', evidenceSourceId: '原件依据', inputRefs: '输入资料', changes: '变更', differences: '差异', checks: '检查结果', findings: '核对发现', blockers: '待解决事项', customer: '客户', company: '公司', contact: '联系人', email: '邮箱', country: '国家', conclusion: '结论', instruction: '工作要求', instructions: '操作要求', approved: '已批准', customerApproved: '客户批准', specVersionId: '规格版本', sampleVersionId: '样品版本', version: '版本', owner: '负责人', date: '日期', dueDate: '截止日期', milestone: '里程碑', milestones: '里程碑', tasks: '任务', amount: '金额', unit: '单位', description: '说明', name: '名称', label: '检查项', value: '内容', title: '标题', result: '结果', content: '内容', acceptance: '验收要求', dimensions_cm: '尺寸（cm）', fabric: '面料', lining: '里料', hardware: '五金', sewing: '车缝要求', testing: '测试要求', message: '说明', decision: '结论', delivery: '交付', destinationPort: '目的港', orderedQuantity: '订单数量', incotermsVersion: '贸易术语版本', body: '正文', text: '正文',
};
const statuses: Record<string, string> = { draft: '草稿', needs_review: '待审核', pending: '待确认', approved: '已批准', blocked: '待补资料', passed: '通过', warning: '待确认', failed: '未通过', not_started: '未开始', true: '是', false: '否' };
const privateFields = new Set(['simulation', 'importedBaseline', 'jobId', 'runId', 'caseId', 'sourceRefs', 'evidenceRefs', 'inputRefs', 'sourceVersionIds', 'sourceId', 'sourceVersionId', 'contentHash']);
function title(key: string) { return fieldNames[key] || key.replace(/([a-z])([A-Z])/g, '$1 $2').replaceAll('_', ' '); }
export function artifactPreview(value: unknown): string {
  if (value == null || value === '') return '待确认';
  if (Array.isArray(value)) return value.map(artifactPreview).join('；');
  if (typeof value === 'object') return Object.entries(value).filter(([key]) => !privateFields.has(key)).map(([key, entry]) => `${title(key)}：${artifactPreview(entry)}`).join('\n');
  return statuses[String(value)] || String(value);
}
function Content({ value }: { value: unknown }) {
  if (value == null || value === '') return <span className="iw-muted">待确认</span>;
  if (Array.isArray(value)) return value.length ? <div className="ba-list">{value.map((v, i) => <div key={i}><Content value={v} /></div>)}</div> : <span className="iw-muted">—</span>;
  if (typeof value === 'object') return <dl className="ba-fields">{Object.entries(value).filter(([key]) => !privateFields.has(key)).map(([key, v]) => <div key={key}><dt>{title(key)}</dt><dd><Content value={v} /></dd></div>)}</dl>;
  return <span className="ba-value">{statuses[String(value)] || String(value)}</span>;
}
export function BusinessArtifactDocument({ artifact, path, readOnly, onInstruction }: { artifact: BusinessArtifact; path: string; readOnly: boolean; onInstruction: (value: string) => void }) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function download(format: string) {
    setBusy(true); setError(undefined);
    try {
      const result = await api.post<{ downloadUrl: string }>(`${path}/artifacts/${artifact.id}/exports`, { format });
      const blob = await api.download(result.downloadUrl.replace(/^\/api\/v1/, ''));
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `${artifact.title}-V${artifact.version}.${format}`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return <div className="ic-document-sheet ba-document">
    <div className="ic-document-eyebrow">BUSINESS DOCUMENT</div>
    <h2>{artifact.title || artifactNames[artifact.kind] || '业务成果'}</h2>
    <p className="ic-document-subtitle"><FileCheck2 size={14} /> V{artifact.version} · {statuses[artifact.status] || artifact.status}</p>
    <div className="ic-document-actions"><button className="button button-primary" disabled={readOnly} onClick={() => onInstruction(`请修改《${artifact.title}》V${artifact.version}：`)}><MessageSquare size={14} />让 Agent 修改</button>{['pdf', 'xlsx'].map(format => <button key={format} className="button" disabled={busy} onClick={() => void download(format)}><Download size={14} />{format.toUpperCase()}</button>)}</div>
    <ErrorNotice error={error} />
    <Content value={artifact.content} />
  </div>;
}

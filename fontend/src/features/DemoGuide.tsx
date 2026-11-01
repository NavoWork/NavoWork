import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Sparkles } from 'lucide-react';
import { api, mode } from '../api';
import type { Inquiry, Session } from '../api/types';
import { ErrorNotice, Modal } from '../components/ui';

type Guide = {
  kind: 'run' | 'approval' | 'done'; node: string; title: string; prompt?: string;
  scope?: string; targetVersionId?: string; evidenceRefs?: string[]; version?: number;
  evidence?: { title: string; text: string }; content?: Record<string, any>;
};

function reviewRows(guide: Guide): [string, unknown][] {
  const c = guide.content || {};
  const f = c.fields || c.po || c;
  if (guide.node === 'requirements') return [['产品', f.product], ['数量', f.quantity], ['尺寸', f.dimensions], ['面料', f.fabric], ['Logo', f.logo], ['包装', f.packaging], ['验货', f.inspection]];
  if (guide.node === 'costing') return [['产品', f.product], ['数量', f.quantity], ['单价（USD）', f.unitPriceUsd], ['总价（USD）', f.totalUsd], ['贸易条款', `${f.incoterm || ''} ${f.namedPlace || ''}`], ['付款方式', f.paymentTerms]];
  if (guide.node === 'sample') return [['样品编号', c.sampleRef], ['客户反馈', c.feedback], ['检查结果', Object.values(c.checks || {}).every(v => v === 'passed') ? '全部通过' : '请核对样品检查记录']];
  if (guide.scope === 'payment_verification') return (c.schedule || []).map((s: any) => [s.milestone === 'deposit' ? '定金（USD）' : '尾款（USD）', s.amountUsd]);
  if (guide.node === 'order') return [['PO 编号', f.number], ['买方', f.buyer], ['数量', f.quantity], ['单价（USD）', f.unitPriceUsd], ['总价（USD）', f.totalUsd], ['PI 编号', c.pi?.number], ['卖方', c.pi?.seller]];
  return [['生产资料', `当前版本 V${guide.version}`], ['确认范围', guide.scope === 'production_release' ? '规格、报价、样品、订单、付款与工厂条件全部通过后，放行演示生产包。' : '按模拟工厂确认资料核对当前生产包。']];
}

export function DemoGuide({ inquiry, session, disabled, onPrompt }: {
  inquiry: Inquiry; session: Session; disabled: boolean; onPrompt: (text: string) => void;
}) {
  const qc = useQueryClient();
  const path = `/workspaces/${session.workspace.id}/inquiries/${inquiry.id}`;
  const [workflowOpen, setWorkflowOpen] = useState(false);
  const fullDemo = !!inquiry.demoScenarioId && inquiry.demoDataScope !== 'reference';
  const capabilities = useQuery({
    queryKey: ['ai-capabilities', session.user.id, inquiry.id],
    queryFn: () => api.get<{ image: { configured: boolean; mode: 'preset' | 'provider' } }>(`${path}/workbench/capabilities`),
    enabled: mode === 'real',
  });
  const query = useQuery({
    queryKey: ['demo-guide', session.user.id, inquiry.id, inquiry.currentRevision, inquiry.metadataVersion],
    queryFn: () => api.get<Guide>(`${path}/demo-guide`), enabled: fullDemo && workflowOpen,
  });
  const [review, setReview] = useState<Guide | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  if (mode !== 'real') return null;
  const guide = query.data;
  async function confirm() {
    if (!review || pending) return;
    setPending(true); setError(undefined);
    try {
      await api.post(`${path}/workbench/approvals`, {
        scope: review.scope, targetVersionId: review.targetVersionId, evidenceRefs: review.evidenceRefs,
        note: `路演模拟确认：${review.title}。不代表真实交易、到账或生产指令。`,
        ...(review.scope === 'payment_verification' ? { verificationBasis: '人工核对本询盘模拟付款凭据与当前订单付款计划；仅用于演示。' } : {}),
      });
      setReview(null);
      await qc.invalidateQueries();
    } catch (e) { setError(e); }
    finally { setPending(false); }
  }
  return <>
    <details className="iw-capability-prompts" open={inquiry.currentRevision === 0 ? true : undefined}>
      <summary>试试 AI 能力</summary>
      <div className="iw-capability-grid">
        <button disabled={disabled} onClick={() => onPrompt('请分析这条询盘，整理客户需求和潜在风险，说明还需要确认什么。')}>分析询盘</button>
        <button disabled={disabled || !capabilities.data?.image.configured} title={capabilities.data?.image.mode === 'preset' ? '展示当前询盘的预置产品图' : capabilities.data?.image.configured ? '根据询盘生成产品概念图' : '生图服务待接入'} onClick={() => onPrompt('请按客户需求准备一张产品概念图并说明设计要点。先读取参考资料，若还没有规格草稿请先整理已有规格，再调用产品生图工具。')}>产品生图{capabilities.data?.image.mode === 'preset' ? <small>演示</small> : !capabilities.data?.image.configured && <small>待接入</small>}</button>
        <button disabled={disabled} onClick={() => onPrompt('请比较两家工厂的报价，说明各自优劣，按资料里的汇率、毛利率与数量核价，给出报价建议。')}>比价与报价</button>
        <button disabled={disabled} onClick={() => onPrompt('请基于当前询盘和已有资料，帮我写一封简洁专业的英文客户回复，明确已知信息与需要确认的问题。')}>撰写客户回复</button>
      </div>
      <ErrorNotice error={capabilities.error} onRetry={() => void capabilities.refetch()} />
    </details>
    {fullDemo && <details className="demo-workflow" onToggle={event => setWorkflowOpen(event.currentTarget.open)}>
      <summary>业务进度（可选）</summary>
      <div className="demo-guide" aria-label="路演下一步">
      <div><span className="demo-guide-label">模拟资料 · 真实 AI</span><strong>{guide?.title || '正在读取下一步…'}</strong></div>
      {guide?.kind === 'run' && <button className="button button-ghost" disabled={disabled} onClick={() => onPrompt(guide.prompt!)}><Sparkles size={13} />使用提示</button>}
      {guide?.kind === 'approval' && <button className="button button-ghost" disabled={disabled || session.user.role !== 'admin'} onClick={() => { setError(undefined); setReview(guide); }}>查看并确认</button>}
      {guide?.kind === 'done' && <CheckCircle2 size={19} />}
      <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      </div>
    </details>}
    {review && <Modal title={`${review.title} · 演示`} onClose={() => { if (!pending) setReview(null); }}>
      <div className="form-stack">
        <p className="preferences-note">这是模拟业务确认，仅作用于当前演示询盘。</p>
        <dl className="demo-review">{reviewRows(review).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{String(value ?? '—')}</dd></div>)}</dl>
        {review.evidence && <details><summary>{review.evidence.title}</summary><pre className="iw-original-full">{review.evidence.text}</pre></details>}
        <ErrorNotice error={error} />
        <div className="form-actions"><button className="button button-ghost" disabled={pending} onClick={() => setReview(null)}>取消</button><button className="button button-primary" disabled={pending} onClick={() => void confirm()}>{pending ? '正在保存…' : '确认本次演示'}</button></div>
      </div>
    </Modal>}
  </>;
}

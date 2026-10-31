import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Check, ChevronRight, Sparkles, X } from 'lucide-react';
import { api, mode } from '../api';
import { ErrorNotice } from '../components/ui';
import './inquiry-progress.css';

const stages = [
  { key: 'qualify_inquiry', name: '询盘评估', prompt: '请只处理询盘评估：阅读客户原始来件，整理客户背景、采购需求与待确认事项。先查阅相关知识，不生成后续报价或订单。', outcome: '客户档案 · 需求摘要 · 待确认事项' },
  { key: 'confirm_requirements', name: '产品确认', prompt: '请整理当前产品需求并生成规格书和供应商询价草稿。引用已有原件和知识库规范，缺失的规格保持待确认。', outcome: '产品规格书 · 供应商询价单' },
  { key: 'prepare_quote', name: '成本报价', prompt: '请核对当前供应商报价，按工作空间核价设置比较成本并生成客户报价草稿；缺少报价原件或成本时先列出缺口。', outcome: '供应商比较 · 成本表 · 客户报价' },
  { key: 'manage_sample', name: '打样确认', prompt: '请根据最新规格整理打样指令；如果已有样品反馈，请核对差异并更新修改清单。客户批准须有书面依据。', outcome: '打样指令 · 样品反馈 · 确认清单' },
  { key: 'confirm_order', name: '订单合同', prompt: '请核对客户 PO 与最新规格、报价及样品要求，列出差异并准备 PI 草稿。订单确认和付款状态以现有证据为准。', outcome: 'PO 核对 · PI 草稿 · 订单差异' },
  { key: 'prepare_production', name: '生产准备', prompt: '请检查订单、样品及付款条件，整理生产资料与排程，并列出仍需处理的放行缺口。', outcome: '生产指令 · 生产排程 · 放行清单' },
  { key: 'inspect_quality', name: '验货交付', prompt: '请根据最新规格、样品要求和现有验货资料生成验货清单、整改要求与出货准备草稿，列出未确认项目。', outcome: '验货清单 · 整改要求 · 出货准备' },
];

export function InquiryProgress({ path, scope, readOnly, onInstruction }: { path: string; scope: string; readOnly: boolean; onInstruction: (text: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['inquiry-progress', scope], enabled: mode === 'real', queryFn: ({ signal }) => api.get<{ stages: { kind: string; status: string }[] }>(`${path}/sop-status`, signal) });
  const current = stages.find(s => s.key === selected);
  return <div className="ip-progress">
    <div className="ip-stage-list" aria-label="业务流程">
      {stages.map((stage, index) => {
        const status = query.data?.stages.find(s => s.kind === stage.key)?.status;
        const present = !!status && status !== 'not_started';
        return <button key={stage.key} className={`ip-stage ${present ? 'has-output' : ''} ${selected === stage.key ? 'is-selected' : ''}`} aria-expanded={selected === stage.key} onClick={() => setSelected(selected === stage.key ? null : stage.key)}>
          <span className="ip-number">{present ? <Check size={12} /> : index + 1}</span><span>{stage.name}<small>{present ? '已有成果' : '待推进'}</small></span>{index < stages.length - 1 && <ChevronRight className="ip-arrow" size={12} />}
        </button>;
      })}
    </div>
    {current && <div className="ip-stage-detail"><Sparkles size={15} /><div><strong>{current.name}</strong><span>{current.outcome}</span></div><button className="button" disabled={readOnly} onClick={() => { onInstruction(current.prompt); setSelected(null); }}>交给 Agent <ArrowRight size={13} /></button><button className="icon-button" aria-label="收起阶段" onClick={() => setSelected(null)}><X size={14} /></button></div>}
    <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
  </div>;
}

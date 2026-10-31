import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronRight, FileText, Sparkles } from 'lucide-react';
import { api, mode } from '../api';
import { ErrorNotice } from '../components/ui';
import './inquiry-progress.css';

const stages = [
  {
    key: 'qualify_inquiry',
    name: '询盘评估',
    prompt:
      '请只处理询盘评估：阅读客户原始来件，整理客户背景、采购需求与待确认事项。先查阅相关知识，不生成后续报价或订单。',
    outcome: '客户档案 · 需求摘要 · 待确认事项',
  },
  {
    key: 'confirm_requirements',
    name: '产品确认',
    prompt:
      '请整理当前产品需求并生成规格书和供应商询价草稿。引用已有原件和知识库规范，缺失的规格保持待确认。',
    outcome: '产品规格书 · 供应商询价单',
  },
  {
    key: 'prepare_quote',
    name: '成本报价',
    prompt:
      '请核对当前供应商报价，按工作空间核价设置比较成本并生成客户报价草稿；缺少报价原件或成本时先列出缺口。',
    outcome: '供应商比较 · 成本表 · 客户报价',
  },
  {
    key: 'manage_sample',
    name: '打样确认',
    prompt:
      '请根据最新规格整理打样指令；如果已有样品反馈，请核对差异并更新修改清单。客户批准须有书面依据。',
    outcome: '打样指令 · 样品反馈 · 确认清单',
  },
  {
    key: 'confirm_order',
    name: '订单合同',
    prompt:
      '请核对客户 PO 与最新规格、报价及样品要求，列出差异并准备 PI 草稿。订单确认和付款状态以现有证据为准。',
    outcome: 'PO 核对 · PI 草稿 · 订单差异',
  },
  {
    key: 'prepare_production',
    name: '生产准备',
    prompt: '请检查订单、样品及付款条件，整理生产资料与排程，并列出仍需处理的放行缺口。',
    outcome: '生产指令 · 生产排程 · 放行清单',
  },
  {
    key: 'inspect_quality',
    name: '验货交付',
    prompt:
      '请根据最新规格、样品要求和现有验货资料生成验货清单、整改要求与出货准备草稿，列出未确认项目。',
    outcome: '验货清单 · 整改要求 · 出货准备',
  },
];

export function InquiryProgress({
  path,
  scope,
  readOnly,
  onInstruction,
  onPrepareQuote,
  onReviewQuote,
  active = true,
}: {
  path: string;
  scope: string;
  readOnly: boolean;
  onInstruction: (text: string) => void;
  onPrepareQuote?: () => void;
  onReviewQuote?: () => void;
  active?: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ['inquiry-progress', scope],
    enabled: mode === 'real' && active,
    queryFn: ({ signal }) =>
      api.get<{ stages: { kind: string; status: string }[]; factorySource?: { title: string; version: number; latestVersion: number | null; outdated: boolean } | null }>(`${path}/sop-status`, signal),
  });
  const hasOutput = (key: string) =>
    query.data?.stages.some((s) => s.kind === key && s.status !== 'not_started') ?? false;
  const lastOutputIndex = stages.reduce(
    (last, stage, index) => (hasOutput(stage.key) ? index : last),
    -1,
  );
  const factorySource = query.data?.factorySource;
  const recommended = factorySource?.outdated ? stages[2] : stages[Math.min(lastOutputIndex + 1, stages.length - 1)];
  const current = stages.find((s) => s.key === selected) ?? recommended;
  const next = hasOutput(current.key) ? stages[stages.indexOf(current) + 1] : undefined;
  const preparingQuote = current.key === 'prepare_quote' && !!onPrepareQuote;
  const reviewQuote = preparingQuote && hasOutput('prepare_quote') && !!onReviewQuote && !factorySource?.outdated;
  return (
    <div className="ip-progress">
      <div className="ip-stage-list" aria-label="业务流程">
        {stages.map((stage, index) => {
          const present = hasOutput(stage.key);
          return (
            <button
              key={stage.key}
              className={`ip-stage ${present ? 'has-output' : ''} ${current.key === stage.key ? 'is-selected' : ''}`}
              aria-expanded={current.key === stage.key}
              onClick={() => setSelected(stage.key)}
            >
              <span className="ip-number">{present ? <FileText size={12} /> : index + 1}</span>
              <span>
                {stage.name}
                <small>{stage.key === 'prepare_quote' && factorySource?.outdated ? '资料已变更 · 待重算' : present ? '已有草稿 · 待复核' : '待推进'}</small>
              </span>
              {index < stages.length - 1 && <ChevronRight className="ip-arrow" size={12} />}
            </button>
          );
        })}
      </div>
      <div className="ip-stage-detail">
        <Sparkles size={15} />
        <div className="ip-stage-summary">
          <strong>
            {!selected && lastOutputIndex < stages.length - 1 ? '建议下一步：' : ''}
            {current.name}
          </strong>
          <span>
            {current.key === 'prepare_quote'
              ? factorySource?.outdated ? `《${factorySource.title}》已变更，当前报价依据为 V${factorySource.version}，请重新核价。` : '自动读取知识库中的工厂资料，匹配当前需求并核价，你只需审查结果。'
              : current.outcome}
          </span>
          {current.key === 'confirm_requirements' && hasOutput(current.key) && (
            <span>下一步将自动匹配知识库中的工厂资料，生成待审查报价。</span>
          )}
          {!preparingQuote && <span>点击准备指令后，在 AI 对话中确认并发送。</span>}
        </div>
        <div className="ip-stage-actions">
          <button
            className={`button ${next ? '' : 'button-primary'}`}
            disabled={readOnly && !reviewQuote}
            onClick={() => {
              if (reviewQuote) onReviewQuote!();
              else if (preparingQuote) { setSelected(current.key); onPrepareQuote!(); }
              else onInstruction(current.prompt);
            }}
          >
            {reviewQuote ? '审查报价' : preparingQuote ? factorySource?.outdated ? '重新核价' : '自动核价' : '准备本阶段指令'} <ArrowRight size={13} />
          </button>
          {reviewQuote && <button className="button" disabled={readOnly} onClick={onPrepareQuote}>重新核价</button>}
          {preparingQuote && <Link className="button button-ghost" to="/knowledge">维护工厂资料</Link>}
          {next && (
            <button
              className="button button-primary"
              disabled={readOnly}
              onClick={() => setSelected(next.key)}
            >
              下一步：{next.name} <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>
      <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
    </div>
  );
}

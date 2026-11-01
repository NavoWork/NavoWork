import { useEffect, useState } from 'react';
import { Check, Sparkles, Square, TriangleAlert } from 'lucide-react';
import type { Run } from '../api/types';
import { StatusBadge } from '../components/ui';
import './inquiry-run.css';

const phases = [
  {
    id: 'understanding',
    label: '理解需求',
    title: '正在理解客户需求',
    detail: '梳理产品、数量与交付要求，找出需要确认的细节。',
  },
  {
    id: 'retrieving',
    label: '查阅资料',
    title: '正在查阅相关资料',
    detail: '读取本次任务已选定的资料版本，为处理提供依据。',
  },
  {
    id: 'calculating',
    label: '业务分析',
    title: '正在执行本次业务分析',
    detail: '根据任务计算成本，或分析变更对流程节点的影响。',
  },
  {
    id: 'composing',
    label: '准备回复',
    title: '正在准备双语回复',
    detail: '把方案和待确认事项整理成清晰的客户回复。',
  },
  {
    id: 'validating',
    label: '审校内容',
    title: '正在核对关键细节',
    detail: '检查报价、交期与资料引用，核对回复中的业务信息。',
  },
  {
    id: 'committing',
    label: '保存成果',
    title: '正在保存本轮成果',
    detail: '保存完整版本，准备在对话中展示本轮成果。',
  },
] as const;

const settledTitles = {
  succeeded: '本轮处理已完成',
  needs_input: '需要补充一些信息',
  failed: '本轮处理未完成',
  cancelled: '本轮处理已停止',
};

export function InquiryRunActivity({ run }: { run: Run }) {
  const active = run.status === 'queued' || run.status === 'running';
  const queued = run.status === 'queued';
  const phaseIndex = phases.findIndex((phase) => phase.id === run.phase);
  const phase = phases[phaseIndex] ?? phases[0];
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active, run.id]);
  const elapsed = Math.max(0, Math.floor((now - Date.parse(run.createdAt)) / 1000)) || 0;
  const elapsedLabel =
    elapsed < 60
      ? `${elapsed} 秒`
      : `${Math.floor(elapsed / 60)} 分 ${String(elapsed % 60).padStart(2, '0')} 秒`;
  const title =
    run.status === 'queued'
      ? '正在准备，马上开始'
      : run.status === 'running'
        ? phase.title
        : settledTitles[run.status];
  const Icon =
    run.status === 'succeeded'
      ? Check
      : run.status === 'failed' || run.status === 'needs_input'
        ? TriangleAlert
        : run.status === 'cancelled'
          ? Square
          : Sparkles;

  return (
    <>
      <div className="iw-run-heading">
        <span className="iw-run-mark" aria-hidden="true">
          <Icon size={20} strokeWidth={1.6} />
        </span>
        <div className="iw-run-heading-copy">
          <div className="iw-run-eyebrow">
            <span>
              Navowork{' '}
              <span className="iw-run-eyebrow-label">{active ? '正在为你处理' : '本轮记录'}</span>
            </span>
            {active && (
              <span className="iw-run-elapsed" aria-hidden="true">
                已等待 {elapsedLabel}
              </span>
            )}
          </div>
          <div className="iw-run-title" role="status" aria-live="polite" aria-atomic="true">
            <strong key={title}>{title}</strong>
            {active && (
              <span className="iw-run-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            )}
          </div>
        </div>
        {!active && <StatusBadge status={run.status} />}
      </div>
      {active && (
        <p className="iw-run-description" key={queued ? 'queued' : phase.id}>
          {queued ? '已收到你的要求，即将开始梳理本轮任务。' : phase.detail}
        </p>
      )}
      <ol className="iw-run-steps" aria-label="处理阶段">
        {phases.map((step, index) => {
          const complete = run.completedPhases ? run.completedPhases.includes(step.id) : run.status === 'succeeded' || (!queued && index < phaseIndex);
          const skipped = run.status === 'succeeded' && !complete;
          const current = active && !queued && index === phaseIndex;
          return (
            <li
              key={step.id}
              className={complete ? 'is-complete' : current ? 'is-current' : ''}
              aria-current={current ? 'step' : undefined}
              title={`${step.label} · ${complete ? '已完成' : current ? '处理中' : skipped ? '本次未执行' : '未完成'}`}
            >
              <span className="iw-run-step-track" aria-hidden="true" />
              <span>{step.label}</span>
              {complete && <span className="sr-only">，已完成</span>}
              {skipped && <span className="sr-only">，本次未执行</span>}
            </li>
          );
        })}
      </ol>
    </>
  );
}

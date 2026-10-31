import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  ArrowUp,
  Check,
  ChevronRight,
  Clock3,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  GitBranch,
  Package,
  Paperclip,
  Plus,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api';
import type { Inquiry, Page, Session } from '../../api/types';
import { ErrorNotice, Loading } from '../../components/ui';
import { caseId, calculate, initialState, usd } from './model';
import { readWorkbench } from './use-workbench';

export function WorkHome({
  session,
  onCreate,
  onOpen,
}: {
  session: Session;
  onCreate: (initialText?: string) => void;
  onOpen: (inquiry: Inquiry) => void;
}) {
  const navigate = useNavigate();
  const [goal, setGoal] = useState('');
  const [demo] = useState(() => {
    try {
      return readWorkbench(`${session.user.id}:${session.workspace.id}:${caseId}`);
    } catch {
      return initialState();
    }
  });
  const demoPrice = calculate(demo.current.costs);
  const nextStep = demo.proposal
    ? '审核包装变更'
    : demo.current.approved
      ? '整理交付草稿，补充生产批准'
      : '核对成本，审核报价';
  const recent = useQuery({
    queryKey: ['home', session.workspace.id, 'work-jobs'],
    queryFn: ({ signal }) =>
      api.get<Page<Inquiry>>(`/workspaces/${session.workspace.id}/inquiries?limit=20`, signal),
  });
  const working = recent.data?.items.filter((i) => i.businessStatus !== 'done').slice(0, 2) || [];
  const waiting = recent.data?.items.find((i) => i.businessStatus === 'waiting');
  const date = new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    timeZone: 'Asia/Shanghai',
  }).format(new Date());
  return (
    <div className="wh-page">
      <header className="wh-greeting">
        <div>
          <span className="tw-eyebrow">YOUR WORK, MOVING FORWARD</span>
          <h1>把手上的事，向前推进。</h1>
          <p>{session.user.name}，欢迎回来。从一个目标开始，直到成果可以交付。</p>
        </div>
        <span className="wh-date">
          <span className="tw-live-dot" />
          {date}
        </span>
      </header>
      <section className="wh-start" aria-label="开始新工作">
        <div className="wh-start-heading">
          <span>
            <Sparkles size={17} />
            今天，需要完成什么？
          </span>
          <span>从资料开始，不必先填订单</span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onCreate(goal);
          }}
        >
          <textarea
            aria-label="描述新的工作目标"
            placeholder="例如：帮我给德国客户做 3,000 个定制背包的报价…"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            maxLength={20000}
            rows={2}
          />
          <div className="wh-start-actions">
            <button className="button button-ghost" type="button" onClick={() => onCreate(goal)}>
              <Paperclip size={14} />
              粘贴客户邮件
            </button>
            <span>
              <kbd>⌘</kbd>
              <kbd>K</kbd> 新建工作
            </span>
            <button className="wh-start-submit" aria-label="开始新工作">
              <ArrowUp size={18} />
            </button>
          </div>
        </form>
        <div className="wh-prompts">
          <span>试试演示</span>
          <button onClick={() => navigate('/workbench')}>
            <FileSpreadsheet size={13} />
            询盘 → 客户报价
            <ArrowRight size={11} />
          </button>
          <button onClick={() => navigate('/workbench?mode=review')}>
            <GitBranch size={13} />
            客户变更 → 联动修订
            <ArrowRight size={11} />
          </button>
          <button onClick={() => navigate('/workbench?artifact=production')}>
            <Package size={13} />
            确认 PO → 生产资料
            <ArrowRight size={11} />
          </button>
        </div>
      </section>
      <div className="wh-section-heading">
        <h2>
          继续工作 <span>{working.length + 1}</span>
        </h2>
        <button onClick={() => navigate('/inquiries')}>
          查看全部询盘 <ArrowRight size={13} />
        </button>
      </div>
      <ErrorNotice error={recent.error} onRetry={() => void recent.refetch()} />
      <div className="wh-jobs">
        <button className="wh-job wh-featured-job" onClick={() => navigate('/workbench')}>
          <div className="wh-job-top">
            <span className="wh-job-icon">
              <Package size={20} />
            </span>
            <span className="tw-chip">演示工作流</span>
            <span className="wh-job-arrow">
              <ArrowRight size={16} />
            </span>
          </div>
          <span className="tw-eyebrow">QUOTATION / 德国</span>
          <h3>
            {demo.current.packaging === '定制彩盒' ? '完成包装变更与重新报价' : '完成定制背包报价'}
          </h3>
          <p>Michael Weber · {demo.current.costs.quantity.toLocaleString()} 件 · FOB Ningbo</p>
          <div className="wh-artifact-preview">
            <FileSpreadsheet size={16} />
            <span>
              <strong>可计算成本表 · V{demo.current.version}</strong>
              <small>
                {demoPrice ? `${usd(demoPrice.unitPrice)} / 件` : '成本待修正'} ·{' '}
                {demo.current.approved ? '内部已审核' : '草稿待审核'}
              </small>
            </span>
            <span className="wh-file-extension">XLSX</span>
          </div>
          <div className="wh-job-bottom">
            <span>
              <span className="tw-live-dot" />
              下一步：{nextStep}
            </span>
            <ChevronRight size={14} />
          </div>
        </button>
        {recent.isPending && <Loading label="正在读取最近工作" />}
        {working.map((inquiry, index) => (
          <button className="wh-job" key={inquiry.id} onClick={() => onOpen(inquiry)}>
            <div className="wh-job-top">
              <span className={`wh-job-icon shade-${index}`}>
                <FileText size={20} />
              </span>
              <span className="tw-chip neutral">
                {inquiry.currentRevision ? '处理中' : '待开始'}
              </span>
              <span className="wh-job-arrow">
                <ArrowRight size={16} />
              </span>
            </div>
            <span className="tw-eyebrow">
              {inquiry.currentRevision ? 'FOLLOW UP' : 'NEW INQUIRY'} /{' '}
              {inquiry.destination || '待确认'}
            </span>
            <h3>{inquiry.title}</h3>
            <p>{inquiry.customer}</p>
            <div className="wh-artifact-preview">
              <FileText size={16} />
              <span>
                <strong>
                  {inquiry.currentRevision
                    ? `回复与方案 · V${inquiry.currentRevision}`
                    : '客户原始需求'}
                </strong>
                <small>
                  {inquiry.currentRevision ? '继续上次成果' : '整理需求，建立工作上下文'}
                </small>
              </span>
            </div>
            <div className="wh-job-bottom">
              <span>
                <Clock3 size={11} />
                {inquiry.nextAction}
              </span>
              <ChevronRight size={14} />
            </div>
          </button>
        ))}
      </div>
      <div className="wh-lower-grid">
        <section className="wh-decisions">
          <div className="wh-section-heading">
            <h2>需要我决定</h2>
            <span className="wh-small-label">你的判断，让工作继续</span>
          </div>
          <button
            className="wh-decision-row"
            onClick={() =>
              navigate(
                demo.current.approved ? '/workbench?artifact=production' : '/workbench?mode=review',
              )
            }
          >
            <span className="wh-decision-icon">
              <ShieldCheck size={17} />
            </span>
            <div>
              <h3>
                {demo.current.approved
                  ? '补充生产放行所需确认'
                  : demo.proposal
                    ? '审核四份成果的包装变更'
                    : '核对报价与变更影响'}
              </h3>
              <p>德国定制背包 · 演示场景 · 内部审核不代表生产放行</p>
            </div>
            <span className="tw-chip amber">进入审核</span>
            <ArrowRight size={15} />
          </button>
          {waiting && (
            <button className="wh-decision-row" onClick={() => onOpen(waiting)}>
              <span className="wh-decision-icon neutral">
                <Clock3 size={17} />
              </span>
              <div>
                <h3>{waiting.waiting?.waitingReason || waiting.title}</h3>
                <p>
                  {waiting.customer} · {waiting.waiting?.nextAction}
                </p>
              </div>
              <span className="tw-chip neutral">待补充</span>
              <ArrowRight size={15} />
            </button>
          )}
          <div className="wh-decision-note">
            <ShieldCheck size={13} />
            报价、规格与生产批准，各有自己的确认边界。
          </div>
        </section>
        <section className="wh-workflow-note">
          <span className="tw-eyebrow">ONE WORKSPACE. REAL OUTCOMES.</span>
          <h2>
            从零散资料，
            <br />
            到可以交付的成果。
          </h2>
          <div className="wh-mini-flow">
            <span>
              <FolderOpen size={16} />
              资料
            </span>
            <i />
            <span>
              <FileSpreadsheet size={16} />
              成果
            </span>
            <i />
            <span>
              <Check size={16} />
              交付
            </span>
          </div>
          <p>
            一处编辑，追溯每个来源；
            <br />
            一项变更，检查所有关联文件。
          </p>
        </section>
      </div>
      <footer className="wh-footer">
        <span>
          <span className="tw-live-dot" />
          工作始终围绕同一个业务上下文展开。
        </span>
        <span>
          Navowork <span>/</span> 一个人，一张工作台。
        </span>
      </footer>
    </div>
  );
}

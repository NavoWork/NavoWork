import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCheck,
  ChevronDown,
  Circle,
  Clock3,
  Download,
  ExternalLink,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  GitBranch,
  History,
  Link2,
  LockKeyhole,
  Mail,
  MoreHorizontal,
  Package,
  Paperclip,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  Terminal,
  TriangleAlert,
  Upload,
  X,
} from 'lucide-react';
import type { Session } from '../../api/types';
import { ErrorNotice, Modal } from '../../components/ui';
import {
  applyChange,
  artifacts,
  calculate,
  canApprove,
  caseId,
  log,
  proposeChange,
  usd,
  type ArtifactKind,
  type Evidence,
  type WorkMode,
  type WorkbenchState,
} from './model';
import { ArtifactCanvas } from './Canvas';
import { buildExport, download, emailDraft, printArtifact } from './export';
import { getSourceFile, saveSourceFile, useWorkbench } from './use-workbench';

const taskSteps = [
  '读取客户与供应商证据',
  '识别 4 份关联成果',
  '核算价格与待确认项',
  '生成待审核变更',
];
const time = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
export function TradeWorkbench({ session, onBack }: { session: Session; onBack: () => void }) {
  const [searchParams] = useSearchParams();
  const scope = `${session.user.id}:${session.workspace.id}:${caseId}`;
  const { state, setState, storageError } = useWorkbench(scope);
  const [kind, setKind] = useState<ArtifactKind>(
    searchParams.get('artifact') === 'production' ? 'production' : 'cost',
  );
  const [workMode, setWorkMode] = useState<WorkMode>(
    searchParams.get('mode') === 'review' ? 'review' : 'build',
  );
  const [pane, setPane] = useState<'canvas' | 'resources' | 'agent'>('canvas');
  const [filter, setFilter] = useState('');
  const [resourceOpen, setResourceOpen] = useState(true);
  const [artifactOpen, setArtifactOpen] = useState(true);
  const [activeSource, setActiveSource] = useState<Evidence | null>(null);
  const [historyVersion, setHistoryVersion] = useState<number | null>(null);
  const [bottomTab, setBottomTab] = useState<'logs' | 'checks' | 'history' | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [approvalAcknowledged, setApprovalAcknowledged] = useState(false);
  const [input, setInput] = useState('');
  const [runState, setRunState] = useState<'idle' | 'running' | 'paused' | 'done'>('idle');
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<ArtifactKind[]>(artifacts.map((a) => a.id));
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const snapshot =
    historyVersion === null
      ? state.current
      : state.history.find((h) => h.version === historyVersion) || state.current;
  const historical = historyVersion !== null;
  const result = calculate(snapshot.costs);
  const activeArtifact = artifacts.find((a) => a.id === kind)!;
  const pending = !!state.proposal;
  const proposed = calculate({ ...state.current.costs, packaging: 5 });
  const currentPrice = calculate(state.current.costs);
  useEffect(() => {
    if (runState !== 'running') return;
    const timer = setTimeout(() => {
      if (step < 3) setStep(step + 1);
      else {
        setState((s) => proposeChange(s));
        setRunState('done');
        setWorkMode('review');
        setPane('canvas');
        setNotice('已生成 4 份成果的候选修订，请审核后应用。');
      }
    }, 450);
    return () => clearTimeout(timer);
  }, [runState, step, setState]);
  function selectArtifact(id: ArtifactKind) {
    setKind(id);
    setWorkMode('build');
    setPane('canvas');
  }
  function source(id: string) {
    setActiveSource(
      state.sources.find((s) => s.id === id) || {
        id: 'manual',
        name: '人工填写记录',
        kind: 'file',
        locator: `${session.user.name} · 当前草稿`,
        content:
          '此字段由当前操作者录入。尚未附加客户或供应商确认材料，不自动变为已批准事实。可导入原始材料后重新核对。',
      },
    );
  }
  function startChange() {
    if (historical || runState === 'running' || state.current.packaging === '定制彩盒') return;
    setHistoryVersion(null);
    setStep(0);
    setRunState('running');
    setError('');
    setState((s) => log(s, '开始演示任务：普通纸盒改为定制彩盒，其余条件不变。'));
  }
  function submitGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;
    const instruction = input.trim();
    if (
      /^(包装改为定制彩盒|把包装换成彩盒|客户包装从普通纸盒改成定制彩盒)[。！!]?$/u.test(
        instruction,
      )
    ) {
      if (state.current.packaging === '定制彩盒')
        setNotice('当前草稿已经使用定制彩盒，可继续审核报价。');
      else startChange();
    } else {
      setState((s) => log(s, `已记录目标（尚未执行）：${instruction}`));
      setNotice(
        '目标已保留在执行日志。当前前端演示支持下方预设流程；自由指令需连接 Agent 服务后处理。',
      );
    }
    setInput('');
  }
  async function upload(files: FileList | null) {
    if (!files?.length || uploading) return;
    setUploading(true);
    setError('');
    const additions: Evidence[] = [];
    const failures: string[] = [];
    for (const file of Array.from(files)) {
      if (file.size > 10 * 1024 * 1024) {
        failures.push(`${file.name} 超过 10 MB`);
        continue;
      }
      try {
        const id = crypto.randomUUID();
        await saveSourceFile(scope, id, file);
        const textFile = /\.(txt|eml|csv|md)$/i.test(file.name);
        additions.push({
          id,
          name: file.name,
          kind: /\.eml$/i.test(file.name) ? 'email' : 'file',
          locator: '本地导入 · 尚未解析或确认',
          content: textFile
            ? (await file.text()).slice(0, 20000)
            : '原始文件已保存在当前浏览器。可下载核对；PDF / Excel / 图片自动解析需连接服务，当前不提取业务事实。',
        });
      } catch {
        failures.push(`${file.name} 无法保存至浏览器`);
      }
    }
    if (additions.length) {
      setState((s) =>
        log(
          { ...s, sources: [...s.sources, ...additions] },
          `已保存 ${additions.length} 份原始文件，等待解析与核对。`,
        ),
      );
      setNotice(`已导入 ${additions.length} 份材料，未自动修改任何业务事实。`);
    }
    if (failures.length) setError(failures.join('；'));
    setUploading(false);
    if (fileInput.current) fileInput.current.value = '';
  }
  async function downloadSource(evidence: Evidence) {
    try {
      const file = await getSourceFile(scope, evidence.id);
      if (!file) {
        download(evidence.content, `${evidence.name}.txt`, 'text/plain;charset=utf-8');
        return;
      }
      download(new Uint8Array(await file.arrayBuffer()), file.name, file.type);
    } catch {
      setError('无法读取原始文件，请重新导入。');
    }
  }
  function exportPack() {
    if (!result || !selected.length || pending) return;
    try {
      download(
        buildExport({ ...state, current: snapshot }, selected),
        `${caseId}-V${snapshot.version}-DRAFT.zip`,
      );
      setState((s) =>
        log(
          s,
          `已生成 V${snapshot.version} 草稿下载包（${selected.length} 份成果、邮件草稿、来源快照），未发送。`,
        ),
      );
      setNotice(`V${snapshot.version} 草稿包已准备下载。生产尚未放行，邮件未发送。`);
    } catch {
      setError('生成导出包失败，草稿仍保留，请重试。');
    }
  }
  const readOnly = historical || runState === 'running' || pending;
  return (
    <div className="trade-workbench">
      <header className="tw-case-header">
        <div className="tw-case-title">
          <button className="icon-button" aria-label="返回工作台" onClick={onBack}>
            <ArrowLeft size={17} />
          </button>
          <span className="tw-case-mark">
            <Package size={21} />
          </span>
          <div>
            <div className="tw-case-eyebrow">
              {caseId}
              <span>前端演示</span>
            </div>
            <h1>德国客户 · 定制背包</h1>
            <p>
              Michael Weber <span>·</span> {snapshot.costs.quantity.toLocaleString()} 件{' '}
              <span>·</span> {snapshot.specs.terms || '贸易条款待确认'}
            </p>
          </div>
        </div>
        <div className="tw-case-actions">
          <button
            className="button"
            onClick={() => setBottomTab(bottomTab === 'history' ? null : 'history')}
          >
            <History size={14} />
            版本记录 <span>V{snapshot.version}</span>
          </button>
          <button
            className="button button-primary"
            onClick={() => {
              setWorkMode('deliver');
              setPane('canvas');
            }}
          >
            <Download size={14} />
            导出交付包
          </button>
        </div>
      </header>
      <div className="tw-job-line">
        <span>
          <span className="tw-live-dot" />
          当前工作：
          {kind === 'production' || kind === 'pi'
            ? '准备生产资料'
            : pending
              ? '审核包装变更'
              : '完成客户报价'}
        </span>
        <span>
          <ShieldCheck size={12} />
          重要承诺由你确认
        </span>
      </div>
      <ErrorNotice error={storageError || error} />
      {notice && (
        <div className="tw-notice" role="status">
          <Check size={14} />
          {notice}
          <button className="icon-button" aria-label="关闭提示" onClick={() => setNotice('')}>
            <X size={12} />
          </button>
        </div>
      )}
      {historical && (
        <div className="tw-history-notice">
          正在查看 V{snapshot.version} 历史快照，内容只读。
          <button onClick={() => setHistoryVersion(null)}>返回当前 V{state.current.version}</button>
        </div>
      )}
      <div className="tw-mobile-tabs" aria-label="工作区面板">
        {(
          [
            { id: 'resources', text: '资料与成果' },
            { id: 'canvas', text: '工作画布' },
            { id: 'agent', text: '执行助手' },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            className={pane === t.id ? 'active' : ''}
            aria-pressed={pane === t.id}
            onClick={() => setPane(t.id)}
          >
            {t.text}
          </button>
        ))}
      </div>
      <div className={`tw-layout tw-show-${pane}`}>
        <aside className="tw-resources">
          <div className="tw-panel-label">
            资料与成果{' '}
            <button
              className="icon-button"
              aria-label="导入资料"
              disabled={uploading}
              onClick={() => fileInput.current?.click()}
            >
              <Plus size={15} />
            </button>
          </div>
          <label className="tw-resource-search">
            <Search size={13} />
            <input
              aria-label="搜索资料与成果"
              placeholder="搜索当前工作…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          <button
            className="tw-tree-heading"
            aria-expanded={resourceOpen}
            onClick={() => setResourceOpen(!resourceOpen)}
          >
            <ChevronDown size={13} className={resourceOpen ? '' : 'collapsed'} />
            <FolderOpen size={14} />
            原始材料 <span>{state.sources.length}</span>
          </button>
          {resourceOpen && (
            <div className="tw-source-tree">
              {state.sources
                .filter((s) => s.name.toLowerCase().includes(filter.toLowerCase()))
                .map((s) => (
                  <button
                    className="tw-tree-item"
                    key={s.id}
                    onClick={() => source(s.id)}
                    title={s.name}
                  >
                    {s.kind === 'email' ? (
                      <Mail size={14} />
                    ) : s.kind === 'sheet' ? (
                      <FileSpreadsheet size={14} />
                    ) : (
                      <FileText size={14} />
                    )}
                    <span>{s.name}</span>
                  </button>
                ))}
            </div>
          )}
          <button
            className="tw-tree-heading"
            aria-expanded={artifactOpen}
            onClick={() => setArtifactOpen(!artifactOpen)}
          >
            <ChevronDown size={13} className={artifactOpen ? '' : 'collapsed'} />
            <FolderOpen size={14} />
            工作成果 <span>{artifacts.length}</span>
          </button>
          {artifactOpen && (
            <div className="tw-artifact-tree">
              {artifacts
                .filter((a) => a.title.includes(filter))
                .map((a) => (
                  <button
                    key={a.id}
                    className={`tw-tree-item ${kind === a.id ? 'active' : ''}`}
                    onClick={() => selectArtifact(a.id)}
                  >
                    {a.format === 'XLSX' ? <FileSpreadsheet size={14} /> : <FileText size={14} />}
                    <span>{a.title}</span>
                    <small>V{snapshot.version}</small>
                    {pending && ['spec', 'cost', 'quote', 'rfq'].includes(a.id) && (
                      <i aria-label="受变更影响" />
                    )}
                  </button>
                ))}
            </div>
          )}
          {filter &&
            !state.sources.some((s) => s.name.toLowerCase().includes(filter.toLowerCase())) &&
            !artifacts.some((a) => a.title.includes(filter)) && (
              <p className="tw-footnote">没有匹配的资料或成果。</p>
            )}
          <button
            className="tw-upload"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            <Upload size={17} />
            <strong>{uploading ? '正在保存…' : '添加工作材料'}</strong>
            <span>邮件、PDF、Excel、图片 · ≤ 10 MB</span>
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".txt,.md,.eml,.csv,.pdf,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.webp"
            multiple
            hidden
            onChange={(e) => void upload(e.target.files)}
          />
          <div className="tw-resource-note">
            <Link2 size={14} />
            <p>
              资料留在当前业务上下文中。
              <br />
              点击来源，回到原始依据。
            </p>
          </div>
        </aside>
        <section className="tw-canvas">
          <div className="tw-artifact-tabs" role="tablist" aria-label="打开的成果">
            {(['spec', 'cost', 'quote'] as const).map((id) => (
              <button
                role="tab"
                aria-selected={kind === id && workMode === 'build'}
                key={id}
                className={kind === id && workMode === 'build' ? 'active' : ''}
                onClick={() => selectArtifact(id)}
              >
                <FileSpreadsheet size={13} />
                {artifacts.find((a) => a.id === id)!.title}
                <span>V{snapshot.version}</span>
              </button>
            ))}
          </div>
          <div className="tw-canvas-toolbar">
            <div className="tw-mode-switch" aria-label="画布模式">
              {(
                [
                  { id: 'build', title: '制作', english: 'Build' },
                  { id: 'review', title: '审核', english: 'Review' },
                  { id: 'deliver', title: '交付', english: 'Deliver' },
                ] as const
              ).map((m) => (
                <button
                  key={m.id}
                  className={workMode === m.id ? 'active' : ''}
                  aria-pressed={workMode === m.id}
                  onClick={() => setWorkMode(m.id)}
                >
                  {m.title}
                  <span>{m.english}</span>
                  {m.id === 'review' && pending && <i />}
                </button>
              ))}
            </div>
            <span className={`tw-save-status ${storageError ? 'unsaved' : ''}`}>
              <CheckCheck size={12} />
              {storageError ? '尚未保存' : '已存到此浏览器'}
            </span>
          </div>
          <div className="tw-canvas-body">
            {workMode === 'build' && (
              <>
                <div className="tw-artifact-title">
                  <div>
                    <span className="tw-eyebrow">{activeArtifact.english}</span>
                    <h2>
                      {activeArtifact.title}
                      <span>V{snapshot.version}</span>
                    </h2>
                  </div>
                  <span
                    className={`tw-chip ${snapshot.approved && kind === 'quote' ? 'success' : 'neutral'}`}
                  >
                    {snapshot.approved && kind === 'quote'
                      ? '内部已审核'
                      : historical
                        ? '历史快照'
                        : '草稿'}
                  </span>
                </div>
                {pending && (
                  <div className="tw-warning">
                    <GitBranch size={15} />
                    有待审核变更，先接受或撤销提案后再编辑。
                    <button onClick={() => setWorkMode('review')}>查看变更</button>
                  </div>
                )}
                <ArtifactCanvas
                  kind={kind}
                  snapshot={snapshot}
                  state={historical ? { ...state, current: snapshot } : state}
                  setState={setState}
                  readOnly={readOnly}
                  onSource={source}
                  onPropose={startChange}
                  onApprove={() => {
                    setApprovalAcknowledged(false);
                    setApprovalOpen(true);
                  }}
                />
              </>
            )}
            {workMode === 'review' && (
              <>
                <div className="tw-artifact-title">
                  <div>
                    <span className="tw-eyebrow">REVIEW / HUMAN IN CONTROL</span>
                    <h2>{pending ? '一个变化，四份成果。' : '检查，再确认。'}</h2>
                  </div>
                  <span className="tw-chip amber">{pending ? '待审核变更' : '待人工确认'}</span>
                </div>
                {pending ? (
                  <>
                    <div className="tw-change-request">
                      <Mail size={19} />
                      <div>
                        <strong>“包装改为定制彩盒，其他条件不变。”</strong>
                        <p>Michael Weber · 演示客户来信</p>
                        <button className="tw-source-link" onClick={() => source('change-email')}>
                          查看原文 <ExternalLink size={10} />
                        </button>
                      </div>
                    </div>
                    <div className="tw-diff-title">
                      <span>受影响成果</span>
                      <span>
                        V{state.current.version} → V{state.current.version + 1} 草稿
                      </span>
                    </div>
                    <div className="tw-diff-list">
                      {[
                        {
                          id: 'spec',
                          title: '需求与规格表',
                          field: '包装方式',
                          before: state.current.packaging,
                          after: '定制彩盒',
                        },
                        {
                          id: 'cost',
                          title: '可计算成本表',
                          field: '单件包装成本',
                          before: `¥${state.current.costs.packaging.toFixed(2)}`,
                          after: state.proposal!.costKnown ? '¥5.00' : '缺少供应商价格',
                        },
                        {
                          id: 'quote',
                          title: '客户报价单',
                          field: '建议单价 · USD',
                          before: currentPrice ? usd(currentPrice.unitPrice) : '无效输入',
                          after:
                            state.proposal!.costKnown && proposed
                              ? usd(proposed.unitPrice)
                              : '暂不能核价',
                        },
                        {
                          id: 'rfq',
                          title: '供应商询价单',
                          field: '确认范围',
                          before: '普通包装',
                          after: '彩盒 / MOQ / 样品 / 交期',
                        },
                      ].map((row) => (
                        <label className="tw-diff-row" key={row.id}>
                          <input
                            type="checkbox"
                            aria-label={`接受${row.title}变更`}
                            checked={state.proposal!.accepted.includes(row.id)}
                            disabled={historical}
                            onChange={(e) =>
                              setState((s) => ({
                                ...s,
                                proposal: s.proposal
                                  ? {
                                      ...s.proposal,
                                      accepted: e.target.checked
                                        ? [...s.proposal.accepted, row.id]
                                        : s.proposal.accepted.filter((id) => id !== row.id),
                                    }
                                  : null,
                              }))
                            }
                          />
                          <div>
                            <strong>{row.title}</strong>
                            <small>{row.field}</small>
                          </div>
                          <span className="tw-before">{row.before}</span>
                          <ArrowRight size={13} />
                          <span className="tw-after">{row.after}</span>
                        </label>
                      ))}
                    </div>
                    <label className="tw-evidence-toggle">
                      <input
                        type="checkbox"
                        checked={state.proposal!.costKnown}
                        disabled={historical}
                        onChange={(e) =>
                          setState((s) => ({
                            ...s,
                            proposal: s.proposal
                              ? { ...s.proposal, costKnown: e.target.checked }
                              : null,
                          }))
                        }
                      />
                      <span>
                        使用已载入的供应商彩盒报价（¥5 / 件，演示）
                        <small>取消勾选可检查“缺少价格”时的阻断行为。</small>
                      </span>
                    </label>
                    <div className="tw-warning">
                      <TriangleAlert size={15} />
                      {!state.proposal!.costKnown
                        ? '缺少彩盒成本：暂停重新报价，可查看供应商询价草稿。'
                        : state.proposal!.accepted.length < 4
                          ? '这 4 项共享包装事实，需全部接受才能保持文件一致；也可撤销整项变更。'
                          : '此次仅生成新草稿。客户批准、交期影响与生产放行仍需单独确认。'}
                    </div>
                    <div className="tw-inline-actions">
                      <button
                        className="button button-primary"
                        disabled={
                          historical ||
                          !state.proposal!.costKnown ||
                          state.proposal!.accepted.length < 4 ||
                          !proposed
                        }
                        onClick={() => {
                          setState((s) => applyChange(s));
                          setWorkMode('build');
                          setKind('cost');
                          setNotice('新草稿已建立，旧版本保留在版本记录中。');
                        }}
                      >
                        <Check size={14} />
                        应用变更，生成 V{state.current.version + 1}
                      </button>
                      <button
                        className="button"
                        disabled={historical}
                        onClick={() => {
                          setState((s) =>
                            log(
                              { ...s, proposal: null },
                              '用户撤销了包装变更提案，原版本保持不变。',
                            ),
                          );
                          setRunState('idle');
                          setNotice('已撤销提案，当前成果保持原值。');
                        }}
                      >
                        撤销提案
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="tw-review-card">
                      <ShieldCheck size={24} />
                      <h3>当前报价 {currentPrice ? usd(currentPrice.unitPrice) : '待修正'} / 件</h3>
                      <p>
                        核对成本与来源后，确认当前版本的内部报价。规格、样品和工厂生产确认仍独立保留。
                      </p>
                      <button
                        className="button button-primary"
                        disabled={historical || state.current.approved || !canApprove(state)}
                        onClick={() => {
                          setApprovalAcknowledged(false);
                          setApprovalOpen(true);
                        }}
                      >
                        {state.current.approved ? '内部报价已审核（演示）' : '审核当前报价'}
                      </button>
                    </div>
                    <div className="tw-context-action">
                      <div>
                        <GitBranch size={18} />
                        <span>
                          <strong>试试客户包装变更</strong>
                          <small>查看四份成果的字段差异与价格影响。</small>
                        </span>
                      </div>
                      <button
                        className="button"
                        disabled={
                          historical ||
                          runState === 'running' ||
                          state.current.packaging === '定制彩盒'
                        }
                        onClick={startChange}
                      >
                        生成变更预览 <ArrowRight size={13} />
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
            {workMode === 'deliver' && (
              <>
                <div className="tw-artifact-title">
                  <div>
                    <span className="tw-eyebrow">DELIVER / READY TO HAND OVER</span>
                    <h2>把成果，整理成一份交付。</h2>
                  </div>
                  <span className="tw-chip neutral">草稿包 · V{snapshot.version}</span>
                </div>
                <p className="tw-delivery-intro">
                  选择需要的成果，导出原生 Excel / Word 文件、邮件草稿与来源快照。
                </p>
                <div className="tw-export-list">
                  {artifacts.map((a) => (
                    <label key={a.id}>
                      <input
                        type="checkbox"
                        checked={selected.includes(a.id)}
                        onChange={(e) =>
                          setSelected((old) =>
                            e.target.checked ? [...old, a.id] : old.filter((id) => id !== a.id),
                          )
                        }
                      />
                      <FileCheck2 size={17} />
                      <span>
                        <strong>{a.title}</strong>
                        <small>
                          V{snapshot.version} ·{' '}
                          {a.id === 'production' || a.id === 'pi'
                            ? '待批准 · 不可正式签发'
                            : '演示草稿'}
                        </small>
                      </span>
                      <span className="tw-extension">{a.format}</span>
                    </label>
                  ))}
                </div>
                <details className="tw-mail-preview">
                  <summary>
                    <Mail size={15} />
                    邮件草稿预览 <ChevronDown size={13} />
                  </summary>
                  <dl>
                    <dt>收件人</dt>
                    <dd>Michael Weber &lt;michael@example.com&gt;（示例地址）</dd>
                    <dt>附件</dt>
                    <dd>
                      {selected.length
                        ? selected.map((id) => artifacts.find((a) => a.id === id)!.title).join('、')
                        : '尚未选择'}{' '}
                      · 下载后需手动添加
                    </dd>
                  </dl>
                  <pre>{emailDraft(snapshot).split('\r\n\r\n').slice(1).join('\n\n')}</pre>
                </details>
                <div className="tw-warning">
                  <LockKeyhole size={16} />
                  {pending
                    ? '有待审核变更，请先应用或撤销提案后导出。'
                    : !result
                      ? '成本输入无效，请修正后导出。'
                      : '生产门禁尚未通过，所有文件按草稿导出。邮箱未连接，不会发送。'}
                </div>
                <div className="tw-inline-actions">
                  <button
                    className="button button-primary"
                    onClick={exportPack}
                    disabled={!selected.length || !result || pending}
                  >
                    <Download size={14} />
                    下载草稿包（{selected.length} 份成果）
                  </button>
                  <button
                    className="button"
                    disabled={!result || pending}
                    onClick={() => {
                      if (!printArtifact(kind, snapshot))
                        setError('预览窗口被浏览器阻止，请允许打开预览后重试。');
                    }}
                  >
                    打印当前成果 / PDF <ExternalLink size={12} />
                  </button>
                </div>
              </>
            )}
          </div>
        </section>
        <aside className="tw-agent">
          <div className="tw-panel-label">
            <span>
              <Sparkles size={15} /> 执行助手
            </span>
            <span className="tw-agent-mode">DEMO</span>
          </div>
          <div className="tw-agent-scroll">
            <div className="tw-agent-intro">
              <span className="tw-agent-avatar">
                <Sparkles size={20} />
              </span>
              <h3>让这件事，继续向前。</h3>
              <p>
                围绕当前资料准备成果。
                <br />
                每次变更，都由你掌握。
              </p>
            </div>
            <div className="tw-agent-goal">
              <span className="tw-eyebrow">当前目标</span>
              <p>
                {runState === 'idle'
                  ? '核对 3,000 个定制背包的成本，准备德国客户报价。'
                  : '将普通包装改为定制彩盒，检查受影响的业务成果。'}
              </p>
            </div>
            <div className="tw-plan-heading">
              <strong>执行计划</strong>
              <span>
                {runState === 'idle'
                  ? '等待任务'
                  : runState === 'paused'
                    ? '已暂停'
                    : runState === 'done'
                      ? '等待审核'
                      : `${step + 1} / 4`}
              </span>
            </div>
            <ol className="tw-plan">
              {taskSteps.map((label, i) => (
                <li
                  key={label}
                  className={
                    runState === 'done' || (runState !== 'idle' && i < step)
                      ? 'complete'
                      : runState === 'running' && i === step
                        ? 'running'
                        : ''
                  }
                >
                  <span>
                    {runState === 'done' || (runState !== 'idle' && i < step) ? (
                      <Check size={12} />
                    ) : (
                      <span>{i + 1}</span>
                    )}
                  </span>
                  <div>
                    <strong>{label}</strong>
                    <small>
                      {
                        [
                          '来源保留原文与定位',
                          '规格 · 成本 · 报价 · 询价',
                          '确定性计算，未知项保留',
                          '应用前不覆盖当前版本',
                        ][i]
                      }
                    </small>
                  </div>
                </li>
              ))}
            </ol>
            {(runState === 'running' || runState === 'paused') && (
              <button
                className="button tw-run-control"
                onClick={() => setRunState(runState === 'running' ? 'paused' : 'running')}
              >
                {runState === 'running' ? <Square size={12} /> : <Play size={12} />}
                {runState === 'running' ? '暂停演示执行' : '继续演示执行'}
              </button>
            )}
            <div className="tw-agent-attention">
              <TriangleAlert size={15} />
              <div>
                <strong>仍需你确认</strong>
                <p>规格与样品批准、MOQ 和交期影响。45 天到港尚未承诺。</p>
                <button
                  onClick={() => {
                    setBottomTab('checks');
                    setPane('canvas');
                  }}
                >
                  查看校验项 <ArrowRight size={11} />
                </button>
              </div>
            </div>
            <div className="tw-agent-shortcuts">
              <span className="tw-eyebrow">接着做</span>
              <button
                onClick={startChange}
                disabled={readOnly || state.current.packaging === '定制彩盒'}
              >
                <GitBranch size={13} />
                演示：包装改为定制彩盒
                <ArrowRight size={12} />
              </button>
              <button onClick={() => selectArtifact('production')}>
                <Package size={13} />
                核对 PO，准备生产资料
                <ArrowRight size={12} />
              </button>
            </div>
          </div>
          <form className="tw-agent-composer" onSubmit={submitGoal}>
            <textarea
              aria-label="当前工作目标"
              placeholder="描述目标，或补充客户的要求…"
              rows={3}
              maxLength={3000}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={readOnly}
            />
            <div>
              <button
                className="icon-button"
                type="button"
                aria-label="添加参考材料"
                disabled={uploading}
                onClick={() => fileInput.current?.click()}
              >
                <Paperclip size={15} />
              </button>
              <span>仅当前 Case · 演示</span>
              <button
                className="tw-submit"
                aria-label="提交工作目标"
                disabled={readOnly || !input.trim()}
              >
                <ArrowUp size={16} />
              </button>
            </div>
          </form>
          <p className="tw-agent-disclaimer">预设流程在浏览器执行 · 未连接模型</p>
        </aside>
      </div>
      <div className="tw-bottom">
        <div className="tw-bottom-tabs">
          {(
            [
              { id: 'logs', text: '执行日志', icon: Terminal },
              { id: 'checks', text: '校验结果', icon: ShieldCheck },
              { id: 'history', text: '版本历史', icon: History },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              className={bottomTab === t.id ? 'active' : ''}
              aria-expanded={bottomTab === t.id}
              onClick={() => setBottomTab(bottomTab === t.id ? null : t.id)}
            >
              <t.icon size={13} />
              {t.text}
              {t.id === 'checks' && <span className="tw-warning-dot" />}
            </button>
          ))}
          <span className="tw-bottom-context">
            {caseId} <span>·</span> V{snapshot.version}
          </span>
        </div>
        {bottomTab && (
          <div className="tw-bottom-content">
            {bottomTab === 'logs' &&
              [...state.activity].reverse().map((entry, index) => (
                <div className="tw-log-row" key={`${entry.at}-${index}`}>
                  <time>{time(entry.at)}</time>
                  <span>{entry.text}</span>
                </div>
              ))}
            {bottomTab === 'checks' && (
              <div className="tw-check-results">
                <p>
                  <Check size={14} />
                  {result
                    ? `报价计算有效：${usd(result.unitPrice)} × ${snapshot.costs.quantity} = ${usd(result.totalPrice)}`
                    : '报价计算无效，需修正输入'}
                </p>
                <p>
                  <TriangleAlert size={14} />
                  汇率与本地费用为演示假设，需按企业规则核实。
                </p>
                <p>
                  <TriangleAlert size={14} />
                  面料、尺寸、样品批准与到港可行性未确认。
                </p>
                <p>
                  <LockKeyhole size={14} />
                  生产尚未放行；对外邮件未发送。
                </p>
              </div>
            )}
            {bottomTab === 'history' && (
              <div className="tw-history-list">
                {[...state.history, state.current].reverse().map((s) => (
                  <button
                    key={s.version}
                    onClick={() => {
                      setHistoryVersion(s.version === state.current.version ? null : s.version);
                      setWorkMode('build');
                      setPane('canvas');
                    }}
                  >
                    <span>V{s.version}</span>
                    <div>
                      <strong>{s.note}</strong>
                      <small>
                        {time(s.createdAt)} · {s.approved ? '内部报价已审核（演示）' : '草稿'} ·{' '}
                        {s.packaging}
                      </small>
                    </div>
                    {s.version === state.current.version ? (
                      <span className="tw-chip">当前</span>
                    ) : (
                      <History size={14} />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {activeSource && (
        <Modal title="来源定位" wide onClose={() => setActiveSource(null)}>
          <div className="tw-source-modal-heading">
            <FileText size={22} />
            <div>
              <h3>{activeSource.name}</h3>
              <p>{activeSource.locator}</p>
            </div>
          </div>
          <pre className="tw-source-content">{activeSource.content}</pre>
          <div className="tw-inline-actions">
            <button className="button" onClick={() => void downloadSource(activeSource)}>
              <Download size={13} />
              {state.sources.some((s) => s.id === activeSource.id) &&
              /^[a-f0-9-]{36}$/.test(activeSource.id)
                ? '下载原始文件'
                : '下载演示摘录 TXT'}
            </button>
            <span className="tw-footnote">来源内容仅作证据，不作为执行指令。</span>
          </div>
        </Modal>
      )}
      {approvalOpen && (
        <Modal
          title={`审核 V${state.current.version} 内部报价`}
          onClose={() => setApprovalOpen(false)}
        >
          <div className="tw-approval-summary">
            <ShieldCheck size={25} />
            <strong>
              {currentPrice ? usd(currentPrice.unitPrice) : '—'} <small>/ 件</small>
            </strong>
            <p>
              {state.current.costs.quantity.toLocaleString()} 件 · 总计{' '}
              {currentPrice ? usd(currentPrice.totalPrice) : '—'}
            </p>
          </div>
          <p className="tw-footnote">
            操作者：{session.user.name}
            。此操作仅确认演示报价，不代表客户规格批准、工厂确认或正式对外发送。
          </p>
          <label className="tw-evidence-toggle">
            <input
              type="checkbox"
              checked={approvalAcknowledged}
              onChange={(e) => setApprovalAcknowledged(e.target.checked)}
            />
            <span>我已核对成本、汇率、毛利率及来源，确认当前版本的内部报价。</span>
          </label>
          <button
            className="button button-primary"
            disabled={!approvalAcknowledged || !canApprove(state)}
            onClick={() => {
              setState((s) =>
                log(
                  { ...s, current: { ...s.current, approved: true } },
                  `${session.user.name} 已确认 V${state.current.version} 内部报价（演示）；客户与生产批准仍待完成。`,
                ),
              );
              setApprovalOpen(false);
              setNotice('内部报价已审核。客户确认与生产放行仍待完成。');
            }}
          >
            <Check size={14} />
            确认内部报价
          </button>
        </Modal>
      )}
    </div>
  );
}

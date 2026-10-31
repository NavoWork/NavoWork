import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Inquiry, Run, Source } from '../api/types';
import { ErrorNotice, Loading, Modal } from '../components/ui';
import { createKnowledgeQuoteRun } from './knowledge-quote';

export const nodeLabels = { customer: '客户与询盘评估', requirements: '客户需求与规格', risks: '风险与待确认项', quote: '方案与报价', reply: '双语回复', sample: '打样资料', order: 'PO与PI', production: '生产资料' };
export type GenerationNode = keyof typeof nodeLabels;
type Props = {
  inquiry: Inquiry; base: string; path: string; node: GenerationNode; instruction?: string;
  onClose: () => void; onStarted: (run: Run) => void;
};
type Evidence = { id: string; title: string; sourceRole: string };

export function GenerateNodeDialog(props: Props) {
  return props.node === 'quote' ? <GenerateKnowledgeQuote {...props} /> : <GenerateDocument {...props} />;
}

function GenerateKnowledgeQuote({ inquiry, base, path, onClose, onStarted }: Props) {
  const request = useRef<Promise<Run> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    request.current ??= createKnowledgeQuoteRun(path, base, inquiry);
    void request.current.then(run => { if (active) onStarted(run); }).catch(reason => { if (active) setError(reason); });
    return () => { active = false; };
  }, [attempt, path, base, inquiry, onStarted]);
  return <Modal title="自动核价" onClose={() => { if (error) onClose(); }}>
    {error ? <>
      <ErrorNotice error={error} onRetry={() => { request.current = null; setError(undefined); setAttempt(value => value + 1); }} />
      <div className="form-actions"><Link to="/knowledge" onClick={onClose}>维护工厂资料</Link><button className="button" onClick={onClose}>关闭</button></div>
    </> : <Loading label="正在准备读取工厂知识，核价结果将呈现在工作区供你审查…" />}
  </Modal>;
}

function GenerateDocument({ inquiry, base, path, node, instruction, onClose, onStarted }: Props) {
  const [selected, setSelected] = useState<string[] | null>(null);
  const [knowledge, setKnowledge] = useState<string[]>([]);
  const [goal, setGoal] = useState(instruction || `根据客户原始询盘及所选依据生成「${nodeLabels[node]}」草稿，标记缺项和待确认内容。`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const sources = useQuery({ queryKey: ['generation-sources', path, node], queryFn: async () => {
    const [evidence, wiki] = await Promise.all([
      api.get<{ items: Evidence[] }>(`${path}/evidence`), api.get<{ items: Source[] }>(`${base}/knowledge`),
    ]);
    return { evidence: evidence.items, wiki: wiki.items };
  }});
  const evidenceIds = selected ?? sources.data?.evidence.map(e => e.id) ?? [];
  async function submit() {
    if (busy) return;
    setError(undefined); setBusy(true);
    try {
      const run = await api.post<Run>(`${path}/node-generations`, { node, baseRevision: inquiry.currentRevision, instruction: goal, inputRefs: evidenceIds, sourceVersionIds: knowledge });
      onStarted(run);
    } catch (e) { setError(e); setBusy(false); }
  }
  return <Modal title={`生成${nodeLabels[node]}`} onClose={() => { if (!busy) onClose(); }}>
    <div className="form-stack">
      <p>客户原始询盘会作为输入。勾选本次依据，生成新的节点草稿；其他节点保留当前内容。</p>
      {sources.isPending ? <Loading label="正在读取可用依据" /> : <>
        <fieldset className="ic-generation-sources"><legend>本项目原件 · 已选 {evidenceIds.length} 项</legend>
          {sources.data?.evidence.map(e => <label key={e.id}><input type="checkbox" disabled={busy} checked={evidenceIds.includes(e.id)} onChange={event => setSelected(event.target.checked ? [...evidenceIds, e.id] : evidenceIds.filter(id => id !== e.id))} />{e.title}<small>{e.sourceRole}</small></label>)}
          {!sources.data?.evidence.length && <p>暂无原件，可先依据询盘整理缺项。补充原件请进入“业务资料与审批”。</p>}
        </fieldset>
        <fieldset className="ic-generation-sources"><legend>知识库参考（固定版本）</legend>
          {sources.data?.wiki.filter(w => w.status !== 'revoked').map(w => { const id = `${w.sourceId}:v${w.version}`; return <label key={id}><input type="checkbox" disabled={busy} checked={knowledge.includes(id)} onChange={e => setKnowledge(e.target.checked ? [...knowledge, id] : knowledge.filter(value => value !== id))} />{w.title} · V{w.version}</label>; })}
        </fieldset>
        <label className="field">本次生成要求<textarea rows={3} disabled={busy} value={goal} onChange={e => setGoal(e.target.value)} /></label>
      </>}
      <ErrorNotice error={error || sources.error} onRetry={sources.error ? () => void sources.refetch() : undefined} />
      <div className="form-actions"><button className="button" disabled={busy} onClick={onClose}>取消</button><button className="button button-primary" disabled={busy || sources.isPending || !!sources.error || !goal.trim()} onClick={() => void submit()}>{busy ? '正在提交…' : '依据所选资料生成'}</button></div>
    </div>
  </Modal>;
}

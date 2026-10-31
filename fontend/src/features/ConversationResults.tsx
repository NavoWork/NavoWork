import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import type { Draft, Revision } from '../api/types';
import { ErrorNotice, Loading } from '../components/ui';
import { resultSnapshot, type SavedResult } from './inquiry-canvas-model';

export function ConversationResults({ revisions, saved, path, onRevision }: { revisions: Revision[]; saved: SavedResult[]; path: string; onRevision: (number: number) => void }) {
  const [selected, setSelected] = useState<number | null>(null);
  const revision = revisions.find(r => r.number === selected) || revisions.at(-1);
  const drafts = useQuery({ queryKey: ['result-hub-drafts', path, revision?.number], enabled: !!revision,
    queryFn: () => api.get<{ items: Draft[] }>(`${path}/revisions/${revision!.number}/reply-drafts`) });
  const texts = Object.fromEntries(drafts.data?.items.map(d => [d.locale, d.text]) || []);
  const snapshot = revision ? resultSnapshot(revision, texts) : null;
  return <div className="ic-document-sheet">
    <div className="ic-document-eyebrow">CONVERSATION RESULTS</div><h2>对话成果汇总</h2>
    <p className="ic-document-subtitle">汇总每轮需求、报价、回复与依据。成果随业务版本保存；画布始终保留这一个入口。需要恢复或继续编辑时，打开对应版本。</p>
    <label className="field">查看成果版本<select aria-label="对话成果版本" value={revision?.number || ''} onChange={e => setSelected(Number(e.target.value))}>
      {!revisions.length && <option value="">尚未生成成果</option>}
      {[...revisions].reverse().map(r => <option key={r.number} value={r.number}>V{r.number} · {r.changeSummary[0]}</option>)}
    </select></label>
    <ErrorNotice error={drafts.error} onRetry={() => void drafts.refetch()} />
    {drafts.isFetching ? <Loading label="读取已保存成果" /> : <pre className="ic-source-content">{snapshot?.text || '点击节点上的“依据现有资料生成”，或在右侧发起任务。'}</pre>}
    {revision && <button className="button" onClick={() => onRevision(revision.number)}>打开 V{revision.number}，查看节点与恢复操作</button>}
    {saved.length > 0 && <details><summary>此前收藏的成果（{saved.length}）</summary>{saved.map(r => <details key={r.revision}><summary>{r.title}</summary><pre className="ic-source-content">{r.text}</pre></details>)}</details>}
  </div>;
}

import { ArrowUpRight, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api, mode } from '../api';
import type { Inquiry, Revision, Run } from '../api/types';
import './suggested-messages.css';

interface Suggestion { id: string; title: string; message: string; category: string }
interface Suggestions { items: Suggestion[]; context: string; revision: number }

export function SuggestedMessages({ path, scope, inquiry, revision, run, latestMessageId, enabled, draftEmpty, onChoose }: {
  path: string; scope: string; inquiry: Inquiry; revision?: Revision; run?: Run;
  latestMessageId?: string; enabled: boolean; draftEmpty: boolean; onChoose: (message: string) => void;
}) {
  const query = useQuery({
    queryKey: ['message-suggestions', scope, inquiry.currentRevision, inquiry.metadataVersion, run?.id, run?.lastSeq, latestMessageId],
    enabled: enabled && mode === 'real',
    staleTime: 30000,
    retry: false,
    queryFn: ({ signal }) => api.get<Suggestions>(`${path}/message-suggestions`, signal),
  });
  const local: Suggestions = {
    revision: inquiry.currentRevision, context: revision ? '继续当前工作' : '从这条询盘开始',
    items: revision ? [
      { id: 'clarify', title: '核对当前缺项', category: '需求整理', message: `请根据刚才的回复，核对${revision.requirements.missingFields.length ? revision.requirements.missingFields.join('、') : '当前仍待确认的需求'}，整理一条客户澄清消息。` },
      { id: 'sources', title: '核对资料依据', category: '资料检索', message: '请列出本轮结论所依据的原件与版本，并指出尚未确认的条件，不生成后续节点。' },
    ] : [
      { id: 'requirements', title: '整理客户需求', category: '需求整理', message: '请阅读这条客户询盘，整理产品、数量、定制要求和交付目标，标出缺失信息，仅完成当前需求节点。' },
      { id: 'reply', title: '拟一条首次回复', category: '客户沟通', message: '请根据客户原始询盘起草一条简洁的首次回复，说明已了解的需求并询问必要缺项，暂不承诺价格和交期。' },
    ],
  };
  const data = mode === 'real' ? query.data : local;
  if (!enabled || !draftEmpty || !data?.items.length || data.revision !== inquiry.currentRevision) return null;
  return <section className="iw-suggestions" aria-label="下一步消息建议">
    <div className="iw-suggestions-heading"><span><Sparkles size={12} />{data.context || '接下来可以这样问'}</span><small>点击编辑</small></div>
    <div className="iw-suggestions-list">
      {data.items.slice(0, 3).map(item => <button key={item.id} type="button" aria-label={item.title} title={item.message} onClick={() => onChoose(item.message)}>
        <span className="iw-suggestion-message">{item.message}</span><span className="iw-suggestion-category">{item.category}</span><ArrowUpRight size={14} aria-hidden="true" />
      </button>)}
    </div>
  </section>;
}

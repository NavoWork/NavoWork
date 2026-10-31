import { useEffect, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import {
  ArrowDown,
  ArrowRight,
  CheckCheck,
  CircleDashed,
  FileText,
  Hourglass,
  Layers3,
  Plus,
  Search,
  Sparkles,
} from 'lucide-react';
import { api } from '../api';
import type { BusinessStatus, Inquiry, Page, Session } from '../api/types';
import { EmptyState, ErrorNotice, Loading, StatusBadge, statusLabels } from '../components/ui';
const stats = [
  { key: 'todo', label: '待办询盘', note: '新的机会，从这里开始', icon: CircleDashed },
  { key: 'active', label: '进行中', note: '让每一步都有进展', icon: Layers3 },
  { key: 'waiting', label: '待确认', note: '等待客户或资料确认', icon: Hourglass },
  { key: 'done', label: '已结束', note: '每一次处理，都有沉淀', icon: CheckCheck },
] as const;
export function Home({
  session,
  refreshKey,
  onOpen,
  onCreate,
}: {
  session: Session;
  refreshKey: number;
  onOpen: (inquiry: Inquiry) => void;
  onCreate: () => void;
}) {
  const [status, setStatus] = useState<BusinessStatus | ''>('');
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const base = `/workspaces/${session.workspace.id}/inquiries`;
  const key = ['home', session.workspace.id, session.user.id];
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(t);
  }, [query]);
  const summaryQuery = useQuery({
    queryKey: [...key, 'summary'],
    queryFn: ({ signal }) => api.get<Record<BusinessStatus, number>>(`${base}/summary`, signal),
  });
  const suggestedQuery = useQuery({
    queryKey: [...key, 'next'],
    queryFn: ({ signal }) => api.get<Page<Inquiry>>(`${base}?limit=20`, signal),
  });
  const list = useInfiniteQuery({
    queryKey: [...key, 'list', status, debounced],
    initialPageParam: '',
    queryFn: ({ signal, pageParam }) =>
      api.get<Page<Inquiry>>(
        `${base}?${new URLSearchParams({ limit: '20', q: debounced, status, cursor: pageParam })}`,
        signal,
      ),
    getNextPageParam: (p) => p.nextCursor || undefined,
  });
  const summary = summaryQuery.isError ? null : summaryQuery.data;
  const summaryError = summaryQuery.error;
  const loading = list.isPending;
  const error = list.error;
  const loadingMore = list.isFetchingNextPage;
  const data = list.data
    ? {
        items: list.data.pages.flatMap((p) => p.items),
        matchedCount: list.data.pages[0].matchedCount,
        nextCursor: list.hasNextPage,
      }
    : null;
  const candidates = suggestedQuery.data?.items || [];
  const suggested =
    candidates.find((i) => i.businessStatus === 'waiting') ||
    candidates.find((i) => i.businessStatus !== 'done') ||
    null;
  const loadMore = () => {
    if (!loadingMore) void list.fetchNextPage();
  };
  const date = new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    timeZone: 'Asia/Shanghai',
  }).format(new Date());
  return (
    <div className="home-page">
      <div className="greeting-row">
        <div>
          <div className="section-kicker">YOUR WORK, IN FOCUS</div>
          <h1>
            今天，从一个好机会开始<span style={{ color: 'var(--navo-color-action)' }}>。</span>
          </h1>
          <p>{session.user.name}，欢迎回来。让每一条询盘，都有清晰的下一步。</p>
        </div>
        <span className="date">{date}</span>
      </div>
      {summaryError ? (
        <ErrorNotice error={summaryError} onRetry={() => void summaryQuery.refetch()} />
      ) : (
        <div className="overview-grid">
          {stats.map((s) => (
            <button
              key={s.key}
              className={`stat-card ${status === s.key ? 'selected' : ''}`}
              aria-pressed={status === s.key}
              aria-label={`${s.label} ${summary?.[s.key] ?? '加载中'}`}
              onClick={() => setStatus(status === s.key ? '' : s.key)}
            >
              <div className="stat-top">
                <span>{s.label}</span>
                <s.icon size={17} />
              </div>
              <div className="stat-number">
                {summary ? String(summary[s.key]).padStart(2, '0') : '—'}
              </div>
              <div className="stat-footer">
                <span>{s.note}</span>
                <ArrowRight size={12} />
              </div>
            </button>
          ))}
        </div>
      )}
      <div className="home-columns">
        <section className="inquiry-list-panel">
          <div className="list-heading">
            <h2>我的询盘 {data && <span>{data.matchedCount}</span>}</h2>
            <button className="button button-primary" onClick={onCreate}>
              <Plus size={14} />
              新建询盘
            </button>
          </div>
          <div className="list-toolbar">
            <div className="filter-tabs" aria-label="筛选询盘">
              {(['', 'todo', 'active', 'waiting', 'done'] as const).map((s) => (
                <button
                  className={status === s ? 'active' : ''}
                  key={s}
                  aria-pressed={status === s}
                  onClick={() => setStatus(s)}
                >
                  {s ? statusLabels[s] : '全部询盘'}
                </button>
              ))}
            </div>
            <label className="search-field">
              <Search size={13} />
              <input
                aria-label="搜索询盘或客户"
                placeholder="搜索询盘或客户…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>
          <ErrorNotice error={error} onRetry={() => void list.refetch()} />
          {loading ? (
            <Loading label="正在获取询盘" />
          ) : data?.items.length ? (
            <>
              <table className="inquiry-table">
                <thead>
                  <tr>
                    <th>询盘 / 客户</th>
                    <th>状态</th>
                    <th>下一步</th>
                    <th>最近更新</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => (
                    <tr key={i.id} onClick={() => onOpen(i)}>
                      <td>
                        <div className="inquiry-title-cell">
                          <span className="inquiry-avatar">
                            <FileText size={15} />
                          </span>
                          <div>
                            <button
                              className="inquiry-title"
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpen(i);
                              }}
                            >
                              {i.title}
                            </button>
                            <div className="inquiry-meta">{i.customer}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={i.businessStatus} />
                      </td>
                      <td className="next-step-cell">
                        {i.waiting?.nextAction || i.nextAction || '查看详情'}
                      </td>
                      <td className="time-cell">
                        {new Intl.DateTimeFormat('zh-CN', {
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                          timeZone: 'Asia/Shanghai',
                          hour12: false,
                        }).format(new Date(i.updatedAt))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  匹配 {data.matchedCount} 条 · 已显示 {data.items.length} 条
                </span>
                <span>
                  <ArrowDown size={10} /> 按最近业务更新排序
                </span>
              </div>
              {data.nextCursor && (
                <button className="button" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? '加载中…' : '继续加载'}
                </button>
              )}
            </>
          ) : (
            !error && (
              <EmptyState
                title={debounced || status ? '没有找到匹配的询盘' : '从第一条询盘开始'}
                description={
                  debounced || status
                    ? '试试其他关键词，或切换筛选条件。'
                    : '录入客户原文，开启你的第一项工作。'
                }
              />
            )
          )}
        </section>
        <aside className="home-aside">
          <h2 className="aside-heading">
            <Sparkles size={15} strokeWidth={1.5} />
            接下来，做什么
          </h2>
          <div className="next-card">
            <div className="section-kicker">NEXT BEST STEP</div>
            <h3>{suggested ? suggested.title : '记录一条新的客户询盘'}</h3>
            <p>
              {suggested
                ? suggested.waiting?.waitingReason || suggested.nextAction
                : '保留客户的原始需求，让后续的方案、报价和回复有据可循。'}
            </p>
            <button className="button" onClick={() => (suggested ? onOpen(suggested) : onCreate())}>
              {suggested ? '继续跟进' : '创建询盘'}
              <ArrowRight size={12} />
            </button>
          </div>
          <div className="quick-guide">
            <h3>把机会，变成准备好的回复</h3>
            {[
              ['读懂询盘', '提取需求，发现缺项与风险'],
              ['准备方案', '查阅资料，核对方案与报价'],
              ['完成回复', '双语草稿，审校后整理材料'],
            ].map(([t, d], n) => (
              <div className="guide-step" key={t}>
                <span>0{n + 1}</span>
                <div>
                  <strong>{t}</strong>
                  <p>{d}</p>
                </div>
              </div>
            ))}
            <div className="guide-note">
              你掌握业务判断，Navowork 协助准备。
              <br />
              每一步结果，都可回到原始依据。
            </div>
          </div>
        </aside>
      </div>
      <footer className="home-bottom">
        <span>所有工作都围绕询盘展开，关闭标签不会删除询盘。</span>
        <span className="keyboard-tip">
          <kbd>⌘</kbd> <kbd>K</kbd> 新建询盘
        </span>
      </footer>
    </div>
  );
}

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDown,
  ArrowRight,
  CheckCheck,
  CircleDashed,
  FileText,
  Hourglass,
  Layers3,
  Search,
  Trash2,
  RotateCcw,
  X,
} from 'lucide-react';
import { api } from '../../api';
import type { BusinessStatus, Inquiry, Page, Session } from '../../api/types';
import { EmptyState, ErrorNotice, Loading, Modal, StatusBadge, statusLabels } from '../../components/ui';

const statuses = [
  { key: 'todo', label: '待办询盘', icon: CircleDashed },
  { key: 'active', label: '进行中', icon: Layers3 },
  { key: 'waiting', label: '待确认', icon: Hourglass },
  { key: 'done', label: '已结束', icon: CheckCheck },
] as const;
const updatedAt = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Shanghai',
  hour12: false,
});

export function WorkHome({
  session,
  active,
  onCreate,
  onOpen,
  onDeleted,
}: {
  session: Session;
  active: boolean;
  onCreate: () => void;
  onOpen: (inquiry: Inquiry) => void;
  onDeleted: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const lastSearch = useRef(location.pathname === '/' ? location.search : '');
  if (active) lastSearch.current = location.search;
  const params = new URLSearchParams(lastSearch.current);
  const selected = params.get('status') || '';
  const status: BusinessStatus | '' = statuses.some((item) => item.key === selected)
    ? (selected as BusinessStatus)
    : '';
  const query = params.get('q') || '';
  const deleted = params.get('deleted') === 'true';
  const [deleteTarget, setDeleteTarget] = useState<Inquiry | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  const [debounced, setDebounced] = useState(query.trim());
  const root = useRef<HTMLDivElement>(null);
  const listPanel = useRef<HTMLElement>(null);
  const scrollPosition = useRef(0);
  const base = `/workspaces/${session.workspace.id}/inquiries`;
  const key = ['home', session.workspace.id, session.user.id];

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), query.trim() ? 250 : 0);
    return () => clearTimeout(timer);
  }, [query]);

  // Keep the list mounted, and restore its own scroll position after leaving a detail or resource.
  useLayoutEffect(() => {
    if (!active) return;
    const scroller = root.current?.closest<HTMLElement>('.content-scroll');
    if (!scroller) return;
    scroller.scrollTop = scrollPosition.current;
    const remember = () => {
      scrollPosition.current = scroller.scrollTop;
    };
    scroller.addEventListener('scroll', remember);
    return () => scroller.removeEventListener('scroll', remember);
  }, [active]);

  const summary = useQuery({
    queryKey: [...key, 'summary'],
    queryFn: ({ signal }) => api.get<Record<BusinessStatus, number>>(`${base}/summary`, signal),
    enabled: active,
  });
  const list = useInfiniteQuery({
    queryKey: [...key, 'list', status, debounced, deleted],
    initialPageParam: '',
    queryFn: ({ signal, pageParam }) =>
      api.get<Page<Inquiry>>(
        `${base}?${new URLSearchParams({ limit: '20', q: debounced, status, cursor: pageParam, deleted: String(deleted) })}`,
        signal,
      ),
    getNextPageParam: (page) => page.nextCursor || undefined,
    enabled: active,
  });
  const items = list.data?.pages.flatMap((page) => page.items) || [];
  const count = list.data?.pages[0].matchedCount;
  const searching = query.trim() !== debounced;
  const filtered = Boolean(status || query);
  const totals = summary.isError ? undefined : summary.data;

  function filter(nextStatus: BusinessStatus | '', nextQuery = query, showDeleted = false) {
    const next = new URLSearchParams(lastSearch.current);
    if (showDeleted) next.set('deleted', 'true');
    else next.delete('deleted');
    if (nextStatus) next.set('status', nextStatus);
    else next.delete('status');
    if (nextQuery) next.set('q', nextQuery);
    else next.delete('q');
    navigate({ pathname: '/', search: next.toString() }, { replace: true });
  }

  async function changeDeleted(inquiry: Inquiry, restore = false) {
    if (actionBusy) return;
    setActionBusy(true);
    setActionError(undefined);
    setNotice('');
    try {
      if (restore) await api.post(`${base}/${encodeURIComponent(inquiry.id)}/restore`, {});
      else await api.delete(`${base}/${encodeURIComponent(inquiry.id)}`);
      if (!restore) onDeleted(inquiry.id);
      setDeleteTarget(null);
      setNotice(restore ? `已恢复「${inquiry.title}」` : `已删除「${inquiry.title}」，可在“已删除”中恢复。`);
      await queryClient.invalidateQueries({ queryKey: key });
    } catch (error) {
      setActionError(error);
    } finally {
      setActionBusy(false);
    }
  }

  function selectStatus(nextStatus: BusinessStatus) {
    filter(status === nextStatus ? '' : nextStatus);
    const panel = listPanel.current;
    const scroller = root.current?.closest<HTMLElement>('.content-scroll');
    if (
      panel &&
      scroller &&
      panel.getBoundingClientRect().top > scroller.getBoundingClientRect().bottom - 160
    ) {
      panel.scrollIntoView({
        block: 'start',
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      });
    }
  }

  return (
    <div ref={root} className="wh-page wh-dashboard">
      <p className="wh-greeting">Hello，{session.user.name}，今天想完成什么工作？</p>

      <section className="overview-grid wh-status-grid" aria-label="询盘状态">
        {statuses.map(({ key: value, label, icon: Icon }) => (
          <button
            key={value}
            className={`stat-card ${!deleted && status === value ? 'selected' : ''}`}
            aria-pressed={!deleted && status === value}
            aria-controls="work-list"
            aria-label={`${label} ${totals?.[value] ?? (summary.isError ? '暂不可用' : '加载中')}`}
            title={`筛选${label}工作`}
            onClick={() => selectStatus(value)}
          >
            <span className="wh-stat-label">
              <Icon size={17} />
              {label}
            </span>
            <span className="wh-stat-value">
              {totals ? String(totals[value]).padStart(2, '0') : '—'}
            </span>
            <ArrowRight className="wh-stat-arrow" size={16} aria-hidden="true" />
          </button>
        ))}
      </section>
      <ErrorNotice error={summary.error} onRetry={() => void summary.refetch()} />
      {notice && <p className="wh-action-notice" role="status">{notice}</p>}
      {!deleteTarget && <ErrorNotice error={actionError} />}

      <section
        ref={listPanel}
        id="work-list"
        className="wh-work-panel"
        aria-labelledby="work-heading"
      >
        <div className="wh-work-heading">
          <h1 id="work-heading">
            {deleted ? '已删除的询盘' : '我的工作'}{' '}
            <span aria-live="polite">{searching || list.isPending ? '…' : (count ?? '—')}</span>
          </h1>
          <label className="search-field wh-search">
            <Search size={17} aria-hidden="true" />
            <input
              aria-label="搜索询盘或客户"
              placeholder="搜索询盘或客户"
              value={query}
              onChange={(event) => filter(status, event.target.value, deleted)}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && query) {
                  event.preventDefault();
                  filter(status, '', deleted);
                }
              }}
            />
            {query && (
              <button
                type="button"
                className="icon-button"
                aria-label="清除搜索"
                onClick={() => filter(status, '', deleted)}
              >
                <X size={15} />
              </button>
            )}
          </label>
        </div>
        <div className="wh-list-toolbar">
          <div className="wh-list-filters" aria-label="工作筛选">
            <button
              className={`wh-all-filter ${!status && !deleted ? 'selected' : ''}`}
              aria-pressed={!status && !deleted}
              onClick={() => filter('')}
            >
              全部
            </button>
            <button className={`wh-all-filter ${deleted ? 'selected' : ''}`} aria-pressed={deleted} onClick={() => filter('', query, true)}>已删除</button>
            {status && (
              <span className="wh-filter-chip">
                {statusLabels[status]}
                <button
                  className="icon-button"
                  aria-label="清除状态筛选"
                  onClick={() => filter('')}
                >
                  <X size={13} />
                </button>
              </span>
            )}
          </div>
          <span className="wh-sort-label">最近更新优先</span>
        </div>
        <div
          aria-busy={list.isFetching || searching}
          className={searching ? 'wh-searching' : undefined}
        >
          <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />
          {list.isPending ? (
            <Loading label="正在获取工作" />
          ) : items.length ? (
            <table className="inquiry-table wh-work-table">
              <thead>
                <tr>
                  <th scope="col">工作 / 客户</th>
                  <th scope="col">状态</th>
                  <th scope="col">下一步</th>
                  <th scope="col">最近更新</th>
                  <th scope="col">
                    <span className="sr-only">询盘操作</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((inquiry) => (
                  <tr key={inquiry.id} onClick={() => !deleted && onOpen(inquiry)}>
                    <td className="wh-title-cell">
                      <div className="inquiry-title-cell">
                        <span className="inquiry-avatar">
                          <FileText size={18} />
                        </span>
                        <div>
                          <button
                            className="inquiry-title"
                            onClick={(event) => {
                              event.stopPropagation();
                              if (!deleted) onOpen(inquiry);
                            }}
                          >
                            {inquiry.title}
                          </button>
                          <div className="inquiry-meta">{inquiry.customer}</div>
                        </div>
                      </div>
                    </td>
                    <td className="wh-state-cell">
                      <StatusBadge status={inquiry.businessStatus} />
                    </td>
                    <td className="wh-next-cell">
                      {inquiry.waiting?.nextAction ||
                        inquiry.nextAction ||
                        (inquiry.businessStatus === 'done' ? '查看历史记录' : '查看详情')}
                    </td>
                    <td className="wh-time-cell">
                      <time dateTime={inquiry.updatedAt}>
                        {updatedAt.format(new Date(inquiry.updatedAt))}
                      </time>
                    </td>
                    <td className="wh-open-cell">
                      <div className="wh-row-actions">
                        {(session.user.role === 'admin' || !inquiry.ownerId || inquiry.ownerId === session.user.id) && (deleted ? (
                          <button className="icon-button" aria-label={`恢复询盘 ${inquiry.title}`} title="恢复询盘" disabled={actionBusy}
                            onClick={(event) => { event.stopPropagation(); void changeDeleted(inquiry, true); }}><RotateCcw size={16} /></button>
                        ) : (
                          <button className="icon-button wh-delete-button" aria-label={`删除询盘 ${inquiry.title}`}
                            title={inquiry.activeRunId || inquiry.pendingRunId ? '请先完成或取消当前任务' : '删除询盘'}
                            disabled={actionBusy || !!inquiry.activeRunId || !!inquiry.pendingRunId}
                            onClick={(event) => { event.stopPropagation(); setActionError(undefined); setDeleteTarget(inquiry); }}><Trash2 size={16} /></button>
                        ))}
                        {!deleted && <button className="icon-button" aria-label={`打开询盘 ${inquiry.title}`} title="打开询盘"
                          onClick={(event) => { event.stopPropagation(); onOpen(inquiry); }}><ArrowRight size={16} /></button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            !list.error && (
              <div className="wh-empty">
                <EmptyState
                  title={deleted ? '暂无已删除的询盘' : filtered ? '没有找到匹配的工作' : '开始你的第一项工作'}
                  description={
                    deleted ? '删除的询盘会保留在这里，可随时恢复。' : filtered
                      ? '试试其他关键词，或清除筛选。'
                      : '点击“新建工作”，粘贴客户邮件或描述工作目标。'
                  }
                />
                {deleted ? null : filtered ? (
                  <button className="button" onClick={() => filter('', '')}>
                    清除筛选
                  </button>
                ) : (
                  <button className="button button-primary" onClick={onCreate}>
                    新建工作
                  </button>
                )}
              </div>
            )
          )}
        </div>
        {list.hasNextPage && (
          <div className="wh-list-more">
            <button
              className="button"
              disabled={list.isFetchingNextPage || searching}
              onClick={() => void list.fetchNextPage()}
            >
              {list.isFetchingNextPage ? '加载中…' : '加载更多'}
              <ArrowDown size={15} />
            </button>
            <span>
              已显示 {items.length} / {count}
            </span>
          </div>
        )}
      </section>
      {deleteTarget && <Modal title="删除询盘" onClose={() => { if (!actionBusy) { setDeleteTarget(null); setActionError(undefined); } }}>
        <p>确定删除「{deleteTarget.title}」吗？</p>
        <p className="muted">删除后将从工作台和最近工作中移除，资料与历史版本保留，可在“已删除”中恢复。</p>
        <ErrorNotice error={actionError} />
        <div className="wh-delete-actions">
          <button className="button" disabled={actionBusy} onClick={() => { setDeleteTarget(null); setActionError(undefined); }}>取消</button>
          <button className="button wh-confirm-delete" disabled={actionBusy} onClick={() => void changeDeleted(deleteTarget)}>{actionBusy ? '删除中…' : '确认删除'}</button>
        </div>
      </Modal>}
    </div>
  );
}

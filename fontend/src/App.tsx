import {
  Component,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpen,
  Box,
  ChevronRight,
  Command,
  FlaskConical,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { api, mode, setMockFault } from './api';
import type { Inquiry, Session } from './api/types';
import { ErrorNotice, IconButton, Loading, Modal } from './components/ui';
import { CreateInquiry } from './features/CreateInquiry';
import { InquiryWorkbench } from './features/workbench-v2/InquiryWorkbench';
import { InquiryWorkspace } from './features/InquiryWorkspace';
import { WorkHome } from './features/workbench/WorkHome';
import { BrandMark } from './components/BrandMark';
import { ThemeSwitch } from './theme/ThemeSwitch';
const Resources = lazy(() =>
  import('./features/StaticLibrary').then((module) => ({ default: module.StaticLibrary })),
);
const SkillMarket = lazy(() =>
  import('./features/SkillMarket').then((module) => ({ default: module.SkillMarket })),
);
const TradeWorkbench = lazy(() =>
  mode === 'real'
    ? import('./features/workbench/RealWorkbench').then((module) => ({
        default: module.RealWorkbench,
      }))
    : import('./features/workbench/TradeWorkbench').then((module) => ({
        default: module.TradeWorkbench,
      })),
);

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <button type="button" className="brand brand-link" onClick={onClick} aria-label="Navowork 首页">
      <BrandMark />
      <span>
        <span className="brand-name">Navowork</span>
        <span className="brand-sub" style={{ display: 'block' }}>
          外贸 AI 工作台
        </span>
      </span>
    </button>
  );
}
function Login({
  onSuccess,
  recovery = false,
}: {
  onSuccess: (s: Session) => void;
  recovery?: boolean;
}) {
  const [name, setName] = useState('Alex');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const guard = useRef(false);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    if (guard.current) return;
    guard.current = true;
    setPending(true);
    setError(undefined);
    try {
      onSuccess(
        await api.post<Session>('/auth/session', mode === 'mock' ? { name } : { email, password }),
      );
    } catch (e) {
      setError(e);
    } finally {
      guard.current = false;
      setPending(false);
    }
  }
  const form = (
    <div className="login-form-area">
      <form className="login-form" onSubmit={login}>
        <span className="welcome-tag">
          <Sparkles size={14} /> YOUR NEXT OPPORTUNITY
        </span>
        <h2>{recovery ? '重新连接工作空间' : '开始今天的工作'}</h2>
        <p>
          {mode === 'mock'
            ? '进入示例工作空间，体验一条询盘的完整流程。'
            : '登录你的团队工作空间，继续处理客户询盘。'}
        </p>
        <div className="form-stack">
          {mode === 'mock' ? (
            <label className="field">
              你的称呼
              <input
                required
                maxLength={30}
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="nickname"
              />
            </label>
          ) : (
            <>
              <label className="field">
                账号邮箱
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label className="field">
                密码
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
            </>
          )}
          <ErrorNotice error={error} />
          <button className="button button-primary" disabled={pending}>
            {pending ? '正在进入…' : mode === 'mock' ? '进入演示工作空间' : '登录工作空间'}
            <ArrowRight size={15} />
          </button>
        </div>
        <div className="login-notice">
          {mode === 'mock' ? (
            <>
              <FlaskConical size={13} /> Mock 演示 · 合成测试数据
              <br />
              称呼仅用于体验，不是真实身份认证。数据保存在此浏览器，用于前端联调，不可对客使用。
            </>
          ) : (
            <>
              <ShieldCheck size={13} /> 真实服务模式 · 由服务端验证身份和访问权限。
            </>
          )}
        </div>
      </form>
    </div>
  );
  return recovery ? (
    form
  ) : (
    <main className="login-page">
      <div className="login-theme">
        <ThemeSwitch />
      </div>
      <section className="login-story">
        <Brand />
        <div>
          <span className="section-kicker">A LITTLE CLARITY. A WORLD OF POSSIBILITIES.</span>
          <h1>
            从一条询盘，
            <br />
            到下一次机会。
          </h1>
          <p>
            把需求、资料、方案与回复放在一起。
            <br />
            让每一次跨越语言的沟通，都有据可循。
          </p>
          <div className="login-lines">
            <span />
            <span />
            <span />
          </div>
        </div>
        <footer>Navowork / 出海外贸 AI 工作台</footer>
      </section>
      {form}
    </main>
  );
}
export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [expired, setExpired] = useState(false);
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ['session'],
    queryFn: ({ signal }) => api.get<Session>('/me', signal),
    retry: false,
    refetchOnWindowFocus: false,
  });
  useEffect(() => {
    if (me.data) setSession(me.data);
  }, [me.data]);
  useEffect(() => {
    const on = () => setExpired(true);
    window.addEventListener('easywork:session-expired', on);
    return () => window.removeEventListener('easywork:session-expired', on);
  }, []);
  const enter = (s: Session) => {
    qc.clear();
    qc.setQueryData(['session'], s);
    setSession(s);
    setExpired(false);
  };
  if (me.isPending && !session) return <Loading label="正在连接工作空间" />;
  if (!session) return <Login onSuccess={enter} />;
  return (
    <>
      <Workspace
        key={`${session.user.id}:${session.workspace.id}`}
        session={session}
        onLogout={() => {
          qc.clear();
          setSession(null);
          setExpired(false);
        }}
      />
      {expired && (
        <Modal title="会话已过期" onClose={() => {}}>
          <div className="auth-recovery">
            <p className="preferences-note" style={{ marginBottom: 20 }}>
              写入尚未确认，请重新登录后重试。本地未发送文字仍保留。
            </p>
            <Login recovery onSuccess={enter} />
          </div>
        </Modal>
      )}
    </>
  );
}
interface Tab {
  id: string;
  title: string;
}
function parseInquiryPath(path: string): { id: string | null; invalid: boolean } {
  if (!path.startsWith('/inquiries/')) return { id: null, invalid: false };
  try {
    const id = decodeURIComponent(path.slice('/inquiries/'.length));
    return { id, invalid: !id };
  } catch {
    return { id: null, invalid: true };
  }
}
function Workspace({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pref = `easywork:tabs:${session.user.id}:${session.workspace.id}`;
  const [tabs, setTabs] = useState<Tab[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(pref) || '[]')
        .filter((t: Tab) => typeof t.id === 'string' && typeof t.title === 'string')
        .slice(0, 20);
    } catch {
      return [];
    }
  });
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const [storageUnavailable, setStorageUnavailable] = useState(false);
  const [create, setCreate] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settings, setSettings] = useState(false);
  const homeUrl = useRef('/');
  const [error, setError] = useState<unknown>();
  const [offline, setOffline] = useState(!navigator.onLine);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const path = location.pathname;
  if (path === '/') homeUrl.current = `/${location.search}`;
  useEffect(() => {
    if (path === '/inquiries') {
      navigate({ pathname: '/', search: location.search, hash: location.hash }, { replace: true });
    }
  }, [path, location.search, location.hash, navigate]);
  const isTrade = path === '/workbench';
  const [tradeOpened, setTradeOpened] = useState(isTrade);
  useEffect(() => {
    if (isTrade) setTradeOpened(true);
  }, [isTrade]);
  const { id, invalid: invalidPath } = parseInquiryPath(path);
  const canvasView =
    mode === 'mock' || new URLSearchParams(location.search).get('view') !== 'workflow';
  const page =
    path === '/knowledge'
      ? 'knowledge'
      : path === '/assets'
        ? 'assets'
        : path === '/capabilities'
          ? 'capabilities'
          : 'home';
  const activeTitle = isTrade
    ? mode === 'real'
      ? '包袋出口工作台'
      : '德国客户 · 定制背包'
    : id
      ? tabs.find((t) => t.id === id)?.title || '询盘详情'
      : {
          home: '工作台',
          knowledge: '知识库',
          assets: '资产库',
          capabilities: '技能市场',
        }[page];
  useEffect(() => {
    try {
      localStorage.setItem(pref, JSON.stringify(tabs));
    } catch {
      setStorageUnavailable(true);
    }
  }, [tabs, pref]);
  const open = useCallback(
    (i: Inquiry) => {
      setTabs((old) =>
        old.some((t) => t.id === i.id)
          ? old.map((t) => (t.id === i.id ? { id: i.id, title: i.title } : t))
          : [...old, { id: i.id, title: i.title }],
      );
      navigate(`/inquiries/${encodeURIComponent(i.id)}`);
      setMobile(false);
    },
    [navigate],
  );
  useEffect(() => {
    if (!id || tabs.some((t) => t.id === id)) return;
    const c = new AbortController();
    api
      .get<Inquiry>(
        `/workspaces/${session.workspace.id}/inquiries/${encodeURIComponent(id)}`,
        c.signal,
      )
      .then((i) =>
        setTabs((old) =>
          old.some((t) => t.id === i.id) ? old : [...old, { id: i.id, title: i.title }],
        ),
      )
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e);
      });
    return () => c.abort();
  }, [id, tabs, session.workspace.id, restoreAttempt]);
  useEffect(() => {
    const toggle = () => setOffline(!navigator.onLine);
    window.addEventListener('online', toggle);
    window.addEventListener('offline', toggle);
    return () => {
      window.removeEventListener('online', toggle);
      window.removeEventListener('offline', toggle);
    };
  }, []);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCreate(true);
      }
      if (e.key === 'Escape') setMobile(false);
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  const changed = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['home', session.workspace.id] });
  }, [qc, session.workspace.id]);
  function closeTab(t: Tab) {
    setTabs((old) => old.filter((x) => x.id !== t.id));
    if (id === t.id) {
      const rest = tabs.filter((x) => x.id !== t.id);
      navigate(rest.length ? `/inquiries/${encodeURIComponent(rest.at(-1)!.id)}` : homeUrl.current);
    }
  }
  async function logout() {
    setLogoutBusy(true);
    try {
      await api.delete('/auth/session');
      navigate('/');
      onLogout();
    } catch (e) {
      setError(e);
    } finally {
      setLogoutBusy(false);
    }
  }
  const nav = [
    { path: '/', name: '工作台', icon: LayoutDashboard },
    { path: '/knowledge', name: '知识库', icon: BookOpen },
    { path: '/assets', name: '资产库', icon: Box },
    { path: '/capabilities', name: '技能市场', icon: Command },
  ];
  return (
    <div
      className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${id ? 'inquiry-active' : ''}`}
    >
      {mobile && <div className="mobile-backdrop" onClick={() => setMobile(false)} />}
      <aside className={`sidebar ${mobile ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand-row">
          <Brand
            onClick={() => {
              navigate(homeUrl.current);
              setMobile(false);
            }}
          />
          <IconButton label="收起导航" onClick={() => setSidebarCollapsed(true)}>
            <PanelLeftClose size={17} />
          </IconButton>
        </div>
        <button
          className="button button-ghost new-inquiry"
          aria-label="新建询盘"
          aria-keyshortcuts="Meta+K Control+K"
          onClick={() => {
            setCreate(true);
            setMobile(false);
          }}
        >
          <Plus size={17} />
          新建询盘
          <kbd aria-hidden="true">⌘ K</kbd>
        </button>
        <nav aria-label="主导航">
          {nav.map((n) => (
            <button
              key={n.path}
              className={`nav-item ${!id && !isTrade && (n.path === '/' ? page === 'home' : path === n.path) ? 'active' : ''}`}
              aria-current={!id && !isTrade && path === n.path ? 'page' : undefined}
              onClick={() => {
                navigate(n.path === '/' ? homeUrl.current : n.path);
                setMobile(false);
                setError(undefined);
              }}
            >
              <n.icon />
              {n.name}
            </button>
          ))}
        </nav>
        <div className="recent-items">
          <p className="sidebar-label">最近工作</p>
          {tradeOpened && (
            <div className={`recent-work-row ${isTrade ? 'is-active' : ''}`}>
              <button
                className="recent-item"
                onClick={() => {
                  navigate('/workbench');
                  setMobile(false);
                }}
              >
                <FileText size={15} />
                <span>{mode === 'real' ? '包袋出口工作台' : '德国定制背包 · 报价'}</span>
              </button>
              <IconButton
                label={mode === 'real' ? '关闭包袋出口工作台标签' : '关闭德国背包工作标签'}
                onClick={() => {
                  setTradeOpened(false);
                  if (isTrade) navigate(homeUrl.current);
                }}
              >
                <X size={12} />
              </IconButton>
            </div>
          )}
          {tabs.length ? (
            tabs.map((t) => (
              <div className={`recent-work-row ${id === t.id ? 'is-active' : ''}`} key={t.id}>
                <button
                  className="recent-item"
                  onClick={() => {
                    navigate(`/inquiries/${encodeURIComponent(t.id)}`);
                    setMobile(false);
                  }}
                >
                  <FileText size={15} />
                  <span>{t.title}</span>
                </button>
                <IconButton label={`关闭 ${t.title}`} onClick={() => closeTab(t)}>
                  <X size={12} />
                </IconButton>
              </div>
            ))
          ) : !tradeOpened ? (
            <p className="preferences-note" style={{ padding: '8px 13px', fontSize: 10 }}>
              从工作台打开一条询盘，
              <br />
              在这里继续处理。
            </p>
          ) : null}
        </div>
        <div className="workspace-box">
          <div className="workspace-line">
            <strong>{session.workspace.name}</strong>
            <ShieldCheck size={13} />
          </div>
        </div>
        <div className="user-panel">
          <div className="avatar">{session.user.name.slice(0, 1).toUpperCase()}</div>
          <div>
            {session.user.name}
            <br />
            <small>{session.user.role === 'admin' ? '管理员' : '成员'}</small>
          </div>
          <IconButton label="退出登录" onClick={logout} disabled={logoutBusy}>
            <LogOut size={14} />
          </IconButton>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button desktop-menu-button"
              aria-label={sidebarCollapsed ? '展开导航' : '收起导航'}
              onClick={() => setSidebarCollapsed((value) => !value)}
            >
              {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <button
              className="icon-button mobile-menu-button"
              aria-label="打开导航"
              onClick={() => setMobile(true)}
            >
              <Menu size={18} />
            </button>
            <strong>{id ? '询盘工作区' : activeTitle}</strong>
          </div>
          <div className="topbar-actions">
            {id && mode === 'real' && (
              <div role="group" aria-label="询盘视图">
                <button
                  className="button button-ghost"
                  aria-pressed={canvasView}
                  onClick={() => navigate(`/inquiries/${encodeURIComponent(id)}`)}
                >
                  资料画板
                </button>
                <button
                  className="button button-ghost"
                  aria-pressed={!canvasView}
                  onClick={() => navigate(`/inquiries/${encodeURIComponent(id)}?view=workflow`)}
                >
                  业务流程
                </button>
              </div>
            )}
            <ThemeSwitch />
            <IconButton label="工作空间设置" onClick={() => setSettings(true)}>
              <Settings2 size={15} />
            </IconButton>
          </div>
        </header>
        {offline && (
          <div className="offline-banner" role="alert">
            网络已断开。未确认的修改不会标记为已保存，恢复连接后可重试。
          </div>
        )}
        <div className="content-scroll">
          {invalidPath && <ErrorNotice error="询盘链接格式不正确，请从工作台重新打开。" />}
          {storageUnavailable && (
            <div className="session-notice">
              浏览器无法保存界面偏好，关闭或刷新前请确认修改已同步。
            </div>
          )}
          <ErrorNotice
            error={error}
            onRetry={() => {
              setError(undefined);
              setRestoreAttempt((v) => v + 1);
              changed();
            }}
          />
          <div hidden={Boolean(id) || isTrade || page !== 'home'}>
            <WorkHome
              session={session}
              active={!id && !isTrade && page === 'home'}
              onOpen={open}
              onCreate={() => setCreate(true)}
            />
          </div>
          {isTrade && (
            <FeatureBoundary>
              <Suspense fallback={<Loading label="正在打开工作画布" />}>
                <TradeWorkbench session={session} onBack={() => navigate(homeUrl.current)} />
              </Suspense>
            </FeatureBoundary>
          )}
          {!id && !isTrade && page !== 'home' && (
            <Suspense fallback={<Loading label="正在打开资源" />}>
              {page === 'capabilities' ? (
                <SkillMarket session={session} />
              ) : (
                <Resources key={page} page={page} session={session} />
              )}
            </Suspense>
          )}{' '}
          {tabs.map((t) => (
            <div key={t.id} hidden={id !== t.id} className="inquiry-mount">
              <FeatureBoundary>
                {canvasView ? (
                  <InquiryWorkspace inquiryId={t.id} session={session} onChanged={changed} />
                ) : (
                  <InquiryWorkbench inquiryId={t.id} session={session} onChanged={changed} />
                )}
              </FeatureBoundary>
            </div>
          ))}
        </div>
      </main>
      {create && (
        <CreateInquiry
          session={session}
          onClose={() => setCreate(false)}
          onCreated={(i) => {
            setCreate(false);
            open(i);
            changed();
          }}
        />
      )}
      {settings && (
        <Modal title="工作空间设置" onClose={() => setSettings(false)}>
          <div className="form-stack">
            <div className="card">
              <h3>{session.workspace.name}</h3>
              <p className="preferences-note">
                当前模式：
                {mode === 'mock' ? 'Mock · 浏览器本地合成测试数据' : '真实服务 · 服务端持久化'}
              </p>
            </div>
            {mode === 'mock' && (
              <>
                <label className="field">
                  异常场景演示
                  <select
                    defaultValue="none"
                    onChange={(e) =>
                      setMockFault(e.target.value as Parameters<typeof setMockFault>[0])
                    }
                  >
                    <option value="none">正常请求</option>
                    <option value="network">网络请求失败</option>
                    <option value="session">会话过期</option>
                    <option value="forbidden">无访问权限</option>
                    <option value="draft-conflict">下一次草稿保存冲突</option>
                    <option value="run-failure">下一次运行失败</option>
                  </select>
                </label>
                <p className="preferences-note">
                  用于检查错误提示和重试路径。关闭弹窗后执行对应操作；故障注入不会调用真实模型。
                </p>
              </>
            )}
            <p className="preferences-note">
              界面偏好按账号及工作空间隔离。正式模式的账号、授权及业务事实来自后端接口。
            </p>
            <button className="button" onClick={() => setSettings(false)}>
              完成
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
class FeatureBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    return this.state.error ? (
      <div className="feature-page">
        <ErrorNotice error="页面暂时无法显示，请刷新后重试。已保存数据不受影响。" />
        <button className="button" onClick={() => window.location.reload()}>
          刷新页面
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}

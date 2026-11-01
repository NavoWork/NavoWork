import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, mode } from '../api';
import type { CustomerContext, Inquiry, Session } from '../api/types';
import { channelLabels } from './CustomerContextCard';
import { ErrorNotice, Modal } from '../components/ui';
export function CreateInquiry({
  session,
  onClose,
  onCreated,
  initialText = '',
}: {
  session: Session;
  onClose: () => void;
  onCreated: (i: Inquiry) => void;
  initialText?: string;
}) {
  const [title, setTitle] = useState('');
  const [customer, setCustomer] = useState('');
  const [originalText, setOriginalText] = useState(initialText);
  const [destination, setDestination] = useState('');
  const [channel, setChannel] = useState<CustomerContext['channel']>('unknown');
  const [email, setEmail] = useState('');
  const [website, setWebsite] = useState('');
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [demo, setDemo] = useState(!initialText && mode === 'real');
  const [scenarioId, setScenarioId] = useState('de-backpack');
  const scenarios = useQuery({
    queryKey: ['demo-scenarios', session.workspace.id],
    queryFn: () => api.get<{ items: { id: string; title: string; customer: string; quantity: number; theme: string }[] }>(`/workspaces/${session.workspace.id}/inquiries/demo-scenarios`),
    enabled: mode === 'real',
    staleTime: 300000,
  });
  const inFlight = useRef(false);
  const request = useRef({ key: crypto.randomUUID(), body: '' });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlight.current) return;
    const manualBody = {
      title: title.trim() || originalText.trim().slice(0, 32),
      customer: customer.trim() || '待识别客户',
      originalText: originalText.trim(),
      destination: destination.trim() || undefined,
      requestedLocales: ['en-US', 'es-MX'],
      customerContext: { channel, email: email.trim(), website: website.trim() },
    };
    if (!demo && (!manualBody.title || !manualBody.customer || !manualBody.originalText)) {
      setError('请先粘贴客户原文或描述工作目标');
      return;
    }
    const body = demo ? { demoScenarioId: scenarioId } : manualBody;
    const encoded = JSON.stringify(body);
    if (request.current.body !== encoded)
      request.current = { key: crypto.randomUUID(), body: encoded };
    inFlight.current = true;
    setPending(true);
    setError(undefined);
    try {
      onCreated(
        await api.post<Inquiry>(
          `/workspaces/${session.workspace.id}/inquiries`,
          body,
          request.current.key,
        ),
      );
    } catch (e) {
      setError(e);
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return (
    <Modal
      title="新建询盘"
      wide={demo}
      onClose={() => {
        if (!pending) onClose();
      }}
    >
      <form className={`form-stack ${demo ? 'demo-create-form' : ''}`} onSubmit={submit}>
        {mode === 'real' && <div className="demo-mode-switch" aria-label="询盘来源">
          <button type="button" aria-pressed={demo} disabled={pending} onClick={() => setDemo(true)}>演示询盘</button>
          <button type="button" aria-pressed={!demo} disabled={pending} onClick={() => setDemo(false)}>空白询盘</button>
        </div>}
        {demo ? <>
          <p className="preferences-note">带入模拟询盘与参考资料。AI 现场完成分析、报价和回复，产品生图展示预置演示图。</p>
          {scenarioId === 'de-backpack' && <p className="preferences-note">德国背包已备齐规格、样品、订单与付款模拟资料，适合完整流程演示。</p>}
          <div className="demo-scenarios" role="radiogroup" aria-label="演示数据集">
            {scenarios.data?.items.map((item, index) => <label key={item.id} className={`demo-scenario ${scenarioId === item.id ? 'selected' : ''}`}>
              <input type="radio" name="scenario" value={item.id} checked={scenarioId === item.id} disabled={pending} onChange={() => setScenarioId(item.id)} />
              <span className="demo-scenario-number">0{index + 1}</span>
              <span><strong>{item.title}</strong><small>{item.customer} · {item.quantity.toLocaleString()} 件</small><small>{item.theme}</small></span>
            </label>)}
          </div>
          {scenarios.isPending && <p role="status">正在加载演示资料…</p>}
          <ErrorNotice error={scenarios.error} onRetry={() => void scenarios.refetch()} />
          <p className="demo-includes">包含客户原文、参考规格和两家工厂报价。每次创建都是独立询盘。</p>
        </> : <>
        <p className="preferences-note">
          从客户原文或工作目标开始。客户与工作名称可以稍后整理，原始内容会独立保留。
        </p>
        <label className="field">
          询盘名称{' '}
          <input
            disabled={pending}
            autoFocus
            maxLength={80}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="选填，例如：春季新品采购询价"
          />
        </label>
        <label className="field">
          客户名称{' '}
          <input
            disabled={pending}
            maxLength={120}
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            placeholder="选填，公司名称或客户称呼"
          />
        </label>
        <label className="field">
          客户原文{' '}
          <textarea
            disabled={pending}
            required
            rows={6}
            maxLength={20000}
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value)}
            placeholder="粘贴客户的原始邮件、聊天或询盘内容…"
          />
          <small>{originalText.length.toLocaleString()} / 20,000</small>
        </label>
        <label className="field">询盘来源<select value={channel} disabled={pending} onChange={e => setChannel(e.target.value as CustomerContext['channel'])}>{Object.entries(channelLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="field">客户邮箱（选填）<input type="email" maxLength={254} disabled={pending} value={email} onChange={e => setEmail(e.target.value)} /></label>
        <label className="field">客户官网（选填）<input type="url" placeholder="https://" maxLength={500} disabled={pending} value={website} onChange={e => setWebsite(e.target.value)} /></label>
        <label className="field">
          目标国家 / 地区（选填）
          <input
            disabled={pending}
            maxLength={120}
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="可稍后补充"
          />
        </label>
        </>}
        <ErrorNotice error={error} />
        <div className="form-actions">
          <button
            className="button button-ghost"
            type="button"
            onClick={onClose}
            disabled={pending}
          >
            取消
          </button>
          <button className="button button-primary" disabled={pending || (demo && !scenarios.data)}>
            {pending ? '正在创建…' : demo ? '创建演示询盘' : '创建并打开询盘'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

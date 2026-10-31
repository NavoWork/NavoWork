import { useRef, useState } from 'react';
import { api } from '../api';
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
  const inFlight = useRef(false);
  const request = useRef({ key: crypto.randomUUID(), body: '' });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlight.current) return;
    const body = {
      title: title.trim() || originalText.trim().slice(0, 32),
      customer: customer.trim() || '待识别客户',
      originalText: originalText.trim(),
      destination: destination.trim() || undefined,
      requestedLocales: ['en-US', 'es-MX'],
      customerContext: { channel, email: email.trim(), website: website.trim() },
    };
    if (!body.title || !body.customer || !body.originalText) {
      setError('请先粘贴客户原文或描述工作目标');
      return;
    }
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
      title="开始新工作"
      onClose={() => {
        if (!pending) onClose();
      }}
    >
      <form className="form-stack" onSubmit={submit}>
        <p className="preferences-note">
          保存客户来件，再与 Agent 一起推进下一步。
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
          <button className="button button-primary" disabled={pending}>
            {pending ? '正在创建…' : '创建并打开工作'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

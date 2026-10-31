import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Check, Circle, SlidersHorizontal, Sparkles } from 'lucide-react';
import { api, mode } from '../api';
import type { Session } from '../api/types';
import { ErrorNotice, Loading, Modal } from '../components/ui';
import './workspace-settings.css';

export interface WorkspaceConfiguration {
  company: { name: string; contactEmail: string; defaultCurrency: string; defaultIncoterm: string; defaultPort: string; paymentTerms: string };
  pricing: { exchangeRate: string; targetMargin: string; quotationValidityDays: number };
  agent: { configured: boolean; model: string; baseUrl: string; enabled: boolean; fileToolsEnabled: boolean; stepwise: boolean };
  skills: { id: string; name: string; description: string; enabled: boolean; tools: string[] }[];
}

export function WorkspaceSettings({ session, onClose }: { session: Session; onClose: () => void }) {
  const client = useQueryClient();
  const path = `/workspaces/${session.workspace.id}/settings`;
  const query = useQuery({ queryKey: ['workspace-settings', session.workspace.id], enabled: mode === 'real', queryFn: ({ signal }) => api.get<WorkspaceConfiguration>(path, signal) });
  const [draft, setDraft] = useState<WorkspaceConfiguration>();
  const [error, setError] = useState<unknown>();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const values = draft || query.data;
  const editable = session.user.role === 'admin';
  function update(group: 'company' | 'pricing', key: string, value: string | number) {
    if (!values) return;
    setDraft({ ...values, [group]: { ...values[group], [key]: value } });
    setSaved(false);
  }
  async function save() {
    if (!values) return;
    setSaving(true); setError(undefined);
    try {
      const next = await api.patch<WorkspaceConfiguration>(path, { company: values.company, pricing: values.pricing, agent: { enabled: values.agent.enabled } });
      client.setQueryData(['workspace-settings', session.workspace.id], next);
      setDraft(next); setSaved(true);
      await client.invalidateQueries({ queryKey: ['skill-market'] });
    } catch (e) { setError(e); } finally { setSaving(false); }
  }
  return <Modal title="工作空间设置" onClose={onClose} wide>
    <div className="ws-settings">
      <ErrorNotice error={error || query.error} onRetry={() => void query.refetch()} />
      {mode === 'real' && query.isLoading && <Loading label="正在读取设置" />}
      {mode === 'mock' && <p>当前工作空间使用本机数据。连接团队服务后，可管理业务默认值与 Agent 技能。</p>}
      {values && <>
        <section className="ws-section"><h3><Building2 size={17} /> 公司与贸易条款</h3>
          <div className="ws-form-grid">
            <label className="field">公司名称<input disabled={!editable} value={values.company.name} onChange={e => update('company', 'name', e.target.value)} /></label>
            <label className="field">业务邮箱<input disabled={!editable} type="email" value={values.company.contactEmail} onChange={e => update('company', 'contactEmail', e.target.value)} /></label>
            <label className="field">贸易条款<select disabled={!editable} value={values.company.defaultIncoterm} onChange={e => update('company', 'defaultIncoterm', e.target.value)}>{['FOB', 'EXW', 'FCA', 'CIF', 'CFR', 'DAP', 'DDP'].map(v => <option key={v}>{v}</option>)}</select></label>
            <label className="field">指定港口 / 地点<input disabled={!editable} value={values.company.defaultPort} onChange={e => update('company', 'defaultPort', e.target.value)} /></label>
            <label className="field ws-full">付款条款<input disabled={!editable} value={values.company.paymentTerms} onChange={e => update('company', 'paymentTerms', e.target.value)} /></label>
          </div>
        </section>
        <section className="ws-section"><h3><SlidersHorizontal size={17} /> 核价默认值</h3><div className="ws-form-grid ws-three">
          <label className="field">汇率 CNY / USD<input disabled={!editable} type="number" min="0.0001" step="0.01" value={values.pricing.exchangeRate} onChange={e => update('pricing', 'exchangeRate', e.target.value)} /></label>
          <label className="field">目标毛利率 %<input disabled={!editable} type="number" min="0" max="99" step="0.1" value={values.pricing.targetMargin} onChange={e => update('pricing', 'targetMargin', e.target.value)} /></label>
          <label className="field">报价有效期 / 天<input disabled={!editable} type="number" min="1" max="365" value={values.pricing.quotationValidityDays} onChange={e => update('pricing', 'quotationValidityDays', Number(e.target.value))} /></label>
        </div><p className="ws-note">用于新报价；已有报价保留原核价依据。</p></section>
        <section className="ws-section"><h3><Sparkles size={17} /> Agent</h3><div className="ws-agent-summary"><div><strong>{values.agent.model || '尚未配置模型'}</strong><span><Circle size={8} fill="currentColor" />{values.agent.configured ? '模型已连接配置' : '待配置模型连接'} · 按指令逐节点处理</span></div><label className="ws-switch"><input disabled={!editable || !values.agent.configured} type="checkbox" checked={values.agent.enabled} onChange={e => { setDraft({ ...values, agent: { ...values.agent, enabled: e.target.checked } }); setSaved(false); }} />启用 Agent</label></div><div className="ws-skill-tags">{values.skills.filter(s => s.enabled).map(s => <span key={s.id}>{s.name}</span>)}</div></section>
        <footer className="ws-footer"><span role="status">{saved ? <><Check size={14} />设置已保存</> : !editable ? '管理员可修改工作空间设置' : ''}</span><button className="button" onClick={onClose}>关闭</button>{editable && <button className="button button-primary" disabled={saving || !values.pricing.exchangeRate || !values.company.name.trim()} onClick={() => void save()}>{saving ? '保存中…' : '保存设置'}</button>}</footer>
      </>}
    </div>
  </Modal>;
}

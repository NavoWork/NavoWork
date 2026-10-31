import type { Inquiry } from '../api/types';

export const channelLabels = { unknown: '来源待补充', email: 'Email 邮件', website: '独立站询盘', alibaba: '阿里巴巴国际站', amazon: 'Amazon 商家', linkedin: 'LinkedIn', referral: '客户转介绍' };
const safeLink = (url?: string) => url && /^https?:\/\//i.test(url) ? url : undefined;

export function CustomerContextCard({ inquiry, compact = false }: { inquiry: Inquiry; compact?: boolean }) {
  const context = inquiry.customerContext;
  return <section className={`ic-customer-context ${compact ? 'is-compact' : ''}`} aria-label="客户来源与背景">
    <header><strong>{channelLabels[context?.channel || 'unknown']}</strong>{context?.simulation && <span className="ic-context-badge">模拟背调资料</span>}</header>
    <p>{context?.sourceRef || '尚未登记获客渠道和来件编号'}</p>
    <dl>
      <div><dt>客户</dt><dd>{context?.company || inquiry.customer}{context?.country ? ` · ${context.country}` : ''}</dd></div>
      <div><dt>邮箱</dt><dd>{context?.email || '待补充'}</dd></div>
      {!compact && <>
        <div><dt>官网</dt><dd>{safeLink(context?.website) ? <a href={context!.website} target="_blank" rel="noreferrer">{context!.website}{context?.simulation ? '（模拟）' : ''}</a> : '待补充'}</dd></div>
        <div><dt>LinkedIn</dt><dd>{safeLink(context?.linkedin) ? <a href={context!.linkedin} target="_blank" rel="noreferrer">{context!.linkedin}{context?.simulation ? '（模拟）' : ''}</a> : '待补充'}</dd></div>
        <div><dt>主营业务</dt><dd>{context?.business || '待核实'}</dd></div>
      </>}
    </dl>
    {!compact && <><p>{context?.summary || '尚未完成客户背景核验。'}</p>
      <ul>{context?.checks?.map((check, i) => <li key={i}><strong>{check.label}</strong><span>{({ pending: '待核验', matched: '信息一致', review: '需跟进' })[check.status]}</span><p>{check.detail}</p></li>)}</ul>
      {context?.simulation && <small>用于演示信息整理，网站及账号为虚构示例，未进行真实联网或信用核验。</small>}
    </>}
  </section>;
}

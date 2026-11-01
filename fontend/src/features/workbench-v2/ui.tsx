import type { ReactNode } from 'react';
import type { WorkbenchStageStatus } from '../../api/types';

export const stageStatusLabel: Record<WorkbenchStageStatus, string> = {
  empty: '待生成',
  draft: '草稿',
  ready: '待确认',
  confirmed: '已确认',
  blocked: '受阻',
  locked: '未开放',
};

export function StatusDot({ status }: { status: WorkbenchStageStatus }) {
  return <span className={`wbv2-dot wbv2-dot-${status}`} aria-label={stageStatusLabel[status]} />;
}

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'blue' | 'green' | 'amber' | 'red' | 'violet' }) {
  return <span className={`wbv2-pill wbv2-pill-${tone}`}>{children}</span>;
}

export function Section({
  eyebrow,
  title,
  description,
  actions,
  children,
  className = '',
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`wbv2-card ${className}`}>
      <header className="wbv2-card-head">
        <div>
          {eyebrow && <span className="wbv2-eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="wbv2-card-actions">{actions}</div>}
      </header>
      {children}
    </section>
  );
}

export function Field({ label, hint, children, wide = false }: { label: string; hint?: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`wbv2-field ${wide ? 'is-wide' : ''}`}>
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function EmptyHint({ children }: { children: ReactNode }) {
  return <div className="wbv2-empty">{children}</div>;
}

export function MissingList({ items, max = 6 }: { items: string[]; max?: number }) {
  if (!items.length) return null;
  return (
    <div className="wbv2-missing">
      {items.slice(0, max).map((item) => (
        <span key={item}>{item}</span>
      ))}
      {items.length > max && <span>+{items.length - max}</span>}
    </div>
  );
}

export const money = (value: number | string | null | undefined, currency = 'USD') => {
  if (value == null || value === '') return '—';
  const number = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `${currency} ${number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const shortDate = (value?: string | null) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(new Date(value));
  } catch {
    return value;
  }
};

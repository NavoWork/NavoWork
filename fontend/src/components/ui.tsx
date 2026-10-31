import { useRef, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertCircle, Inbox, X } from 'lucide-react';

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const previous = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          className={`modal ${wide ? 'modal-wide' : ''}`}
          aria-describedby={undefined}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            previous.current?.focus();
          }}
        >
          <header className="modal-header">
            <Dialog.Title asChild>
              <h2>{title}</h2>
            </Dialog.Title>
            <IconButton label="关闭弹窗" onClick={onClose}>
              <X size={18} />
            </IconButton>
          </header>
          <div className="modal-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const e = error as { message?: string; requestId?: string; code?: string };
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>{typeof error === 'string' ? error : e.message || '请求失败，请稍后重试'}</strong>
        {e.requestId && <small>请求编号：{e.requestId}</small>}
      </div>
      {onRetry && (
        <button className="button button-ghost" onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  );
}
export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="empty-state">
      <Inbox size={32} strokeWidth={1.25} />
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export const statusLabels: Record<string, string> = {
  todo: '待办',
  active: '进行中',
  waiting: '待确认',
  done: '已结束',
  draft: '草稿',
  published: '已发布',
  revoked: '已撤销',
  needs_review: '待复核',
  reviewed: '已复核',
  passed: '已复核',
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  needs_input: '需补充信息',
  failed: '失败',
  cancelled: '已取消',
};
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge status-${status}`}>
      <span className="status-dot" />
      {statusLabels[status] || status}
    </span>
  );
}
export function IconButton({
  label,
  onClick,
  children,
  disabled,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="icon-button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
export function Loading({ label = '正在加载' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}

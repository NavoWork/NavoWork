import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import {
  ChevronRight,
  FileText,
  MessageSquare,
  MoreHorizontal,
  Sparkles,
} from 'lucide-react';
import type { Inquiry, Message } from '../api/types';
import { channelLabels } from './CustomerContextCard';
import { InvocationContext } from './InvocationContext';
import './inquiry-chat.css';
import { ErrorNotice } from '../components/ui';
import type { InquiryChat } from './inquiry-chat';

const messageDate = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(value));

export function InquiryChatHeading({
  chat,
  actions,
}: {
  chat: InquiryChat;
  actions?: ReactNode;
}) {
  const [actionsOpen, setActionsOpen] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);
  const actionsButton = useRef<HTMLButtonElement>(null);
  const actionsId = useId();
  useEffect(() => {
    if (!actionsOpen) return;
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !actionsRef.current?.contains(event.target))
        setActionsOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActionsOpen(false);
        actionsButton.current?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [actionsOpen]);
  return (
    <>
      <div className="iw-assistant-heading">
        <h2>
          <MessageSquare size={14} />
          AI 对话
        </h2>
        <span>仅当前询盘</span>
        <div className="iw-chat-heading-actions">
          {actions && (
            <div className="iw-chat-more" ref={actionsRef}>
              <button
                ref={actionsButton}
                className="icon-button"
                aria-label="更多询盘操作"
                title="更多询盘操作"
                aria-expanded={actionsOpen}
                aria-controls={actionsOpen ? actionsId : undefined}
                onClick={() => setActionsOpen((open) => !open)}
              >
                <MoreHorizontal size={16} />
              </button>
              {actionsOpen && (
                <div
                  className="iw-chat-actions-popover"
                  id={actionsId}
                  role="group"
                  aria-label="询盘操作"
                  onClick={(event) => {
                    if (event.target instanceof Element && event.target.closest('button, a')) {
                      actionsButton.current?.focus();
                      setActionsOpen(false);
                    }
                  }}
                >
                  {actions}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <ErrorNotice error={chat.error} onRetry={() => void chat.refresh()} />
    </>
  );
}

export function InquiryChatTranscript({
  inquiry,
  messages,
  onOriginal,
  resultMessageId,
  resultPreview,
}: {
  inquiry: Inquiry;
  messages: Message[];
  onOriginal: () => void;
  resultMessageId?: string;
  resultPreview?: ReactNode;
}) {
  return (
    <>
      <button className="iw-original" onClick={onOriginal}>
        <FileText size={16} />
        <div>
          <strong>客户原始询盘</strong>
          <small>
            {channelLabels[inquiry.customerContext?.channel || 'unknown']}
            {inquiry.customerContext?.email ? ` · ${inquiry.customerContext.email}` : ''}
          </small>
          <p>
            {inquiry.originalText.slice(0, 110)}
            {inquiry.originalText.length > 110 ? '…' : ''}
          </p>
        </div>
        <ChevronRight size={14} />
      </button>
      {!messages.length && (
        <div className="iw-assistant-intro">
          <span className="iw-ai-mark">
            <Sparkles size={16} />
          </span>
          <h3>先把需求读清楚。</h3>
          <p>从客户原文开始，梳理产品、数量、目的地与时间要求。资料不足的地方，会保留为待确认。</p>
        </div>
      )}
      {messages.map((message) => (
        <div key={message.id}>
          <article className={`iw-message ${message.role}`}>
            <div className="iw-message-meta">
              <span>{message.role === 'user' ? '你' : 'Navowork'}</span>
              <time>{messageDate(message.createdAt)}</time>
            </div>
            <p>{message.text}</p>
            {message.images?.map((image) => (
              <figure className="iw-chat-image" key={image.artifactId}>
                <a href={image.url} target="_blank" rel="noreferrer" aria-label={`查看${image.title}`}><img src={image.url} alt={image.title} loading="lazy" /></a>
                <figcaption>{image.title} · V{image.version}<span>{image.generationMode === 'preset' ? '演示图' : 'AI 生成'}</span></figcaption>
                <div><a href={image.url} download>下载图片</a>{image.proposalUrl && <a href={image.proposalUrl} download>下载设计方案</a>}</div>
              </figure>
            ))}
            <InvocationContext context={message.context} />
          </article>
          {message.id === resultMessageId && resultPreview}
        </div>
      ))}
      {!resultMessageId && resultPreview}
    </>
  );
}

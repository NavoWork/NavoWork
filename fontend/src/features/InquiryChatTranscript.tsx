import type { ReactNode } from 'react';
import { ChevronRight, FileText, MessageSquare, Sparkles } from 'lucide-react';
import type { Inquiry, Message } from '../api/types';
import { channelLabels } from './CustomerContextCard';
import { InvocationContext } from './InvocationContext';
import './inquiry-chat.css';

const messageDate = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(new Date(value));

export function InquiryChatHeading() {
  return (
    <div className="iw-assistant-heading">
      <h2>
        <MessageSquare size={14} />
        AI 对话
      </h2>
      <span>仅当前询盘</span>
    </div>
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
            <InvocationContext context={message.context} />
          </article>
          {message.id === resultMessageId && resultPreview}
        </div>
      ))}
      {!resultMessageId && resultPreview}
    </>
  );
}

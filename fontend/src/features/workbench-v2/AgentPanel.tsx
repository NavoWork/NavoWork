import { useEffect, useRef, useState } from 'react';
import {
  ArrowUp,
  ChevronDown,
  CircleAlert,
  Loader2,
  MessageSquare,
  Paperclip,
  Sparkles,
  Square,
  Wrench,
} from 'lucide-react';
import type { Message, Run } from '../../api/types';
import { useEffect as useEffectAlias } from 'react';

type RecordItem = Record<string, any>;

const stagePrompts: Record<string, string[]> = {
  inquiry: ['参考项目补充确认，核对客户背景与询盘关键信息', '核对客户背景与来源，标注待核验项'],
  requirements: ['参考项目补充确认，整理箱包 Tech Pack 与 BOM，缺项再问我', '核对当前规格和客户原件是否一致'],
  costing: ['读取供应商报价；参考项目补充确认中的汇率、毛利和数量核价', '按已确认的汇率和毛利生成客户报价'],
  sample: ['参考项目补充确认，记录本轮样品、检查和客户反馈', '核对样品与规格版本是否一致'],
  order: ['参考项目补充确认和 PO，核对差异并生成 PI 草稿', '登记付款计划和双方确认状态'],
  production: ['参考项目补充确认，生成生产资料、T&A 和 QC 检查表', '检查生产放行缺口'],
};

export function AgentPanel({
  messages,
  run,
  events,
  running,
  busy,
  stage,
  selectedRefs,
  onSend,
  onAnswer,
  onOpenSources,
  onCancel,
  error,
}: {
  messages: Message[];
  run: Run | null;
  events: RecordItem[];
  running: boolean;
  busy: boolean;
  stage: string;
  selectedRefs: number;
  onSend: (text: string) => void;
  onAnswer: (answers: { questionId: string; value: string }[]) => Promise<boolean>;
  onOpenSources: () => void;
  onCancel: () => void;
  error: unknown;
}) {
  const [text, setText] = useState('');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [showTools, setShowTools] = useState(false);
  const messagesRef = useRef<HTMLDivElement>(null);
  const questions = run?.clarification?.questions || [];
  const toolEvents = events.filter((event) => event.type === 'agent.tool');
  const waiting = run?.status === 'needs_input' && questions.length > 0;

  useEffect(() => {
    const element = messagesRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages.length, run?.status, showTools]);

  useEffect(() => {
    setAnswers({});
  }, [run?.id, run?.status]);

  function submit() {
    const value = text.trim();
    if (!value || busy || running || waiting) return;
    onSend(value);
    setText('');
  }

  async function submitAnswers() {
    const payload = questions.map((question) => ({ questionId: question.id, value: (answers[question.id] || '').trim() }));
    if (payload.some((item) => !item.value)) return;
    const ok = await onAnswer(payload);
    if (ok) setAnswers({});
  }

  return (
    <aside className="wbv2-agent">
      <header className="wbv2-agent-head">
        <div>
          <span className="wbv2-eyebrow">NAVOWORK AGENT</span>
          <h2>跟单助手</h2>
        </div>
        <span className={`wbv2-live ${running ? 'is-running' : ''}`}>{waiting ? '待补充' : running ? '执行中' : '就绪'}</span>
      </header>

      <div className="wbv2-agent-scroll" ref={messagesRef}>
        {messages.length === 0 && (
          <div className="wbv2-agent-empty">
            <span className="wbv2-agent-orb"><Sparkles size={18} /></span>
            <h3>从一句话开始</h3>
            <p>告诉我要完成的工作。我会读取客户资料、调用工具，并把结果写入当前节点。</p>
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`wbv2-msg is-${message.role}`}>
            <span className="wbv2-msg-role">{message.role === 'user' ? '你' : 'Agent'}</span>
            <div className="wbv2-msg-body">{message.text}</div>
          </div>
        ))}

        {toolEvents.length > 0 && (
          <div className="wbv2-tools">
            <button className="wbv2-tools-toggle" onClick={() => setShowTools((value) => !value)}>
              <Wrench size={13} /> 执行记录 · {toolEvents.length} 个工具
              <ChevronDown size={13} className={showTools ? 'is-open' : ''} />
            </button>
            {showTools && (
              <div className="wbv2-tools-list">
                {toolEvents.map((event) => (
                  <div key={event.id}>
                    <span className={`wbv2-tool-dot is-${event.payload?.status || 'success'}`} />
                    <div>
                      <strong>{event.payload?.tool}</strong>
                      <small>{event.payload?.summary}</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {running && (
          <div className="wbv2-run-state">
            <Loader2 size={15} className="is-spin" />
            <span>{run?.phase === 'retrieving' ? '读取资料' : run?.phase === 'calculating' ? '计算与核对' : run?.phase === 'committing' ? '保存版本' : '处理中'}</span>
            <button className="wbv2-text-button" onClick={onCancel}><Square size={11} /> 停止</button>
          </div>
        )}

        {waiting && (
          <div className="wbv2-questions">
            <div className="wbv2-questions-head"><CircleAlert size={15} /><strong>需要你补充</strong><button className="wbv2-text-button" onClick={onCancel}>停止任务</button></div>
            {questions.map((question) => (
              <label key={question.id}>
                <span>{question.question}</span>
                <input
                  value={answers[question.id] || ''}
                  placeholder="填写已知信息；不确定可写“待确认”"
                  onChange={(event) => setAnswers((old) => ({ ...old, [question.id]: event.target.value }))}
                />
              </label>
            ))}
            <button className="button button-primary" disabled={busy || questions.some((question) => !(answers[question.id] || '').trim())} onClick={() => void submitAnswers()}>
              提交补充，继续任务
            </button>
          </div>
        )}

        {error != null && (
          <div className="wbv2-agent-error">
            <CircleAlert size={14} />
            <span>{typeof error === 'string' ? error : (error as any)?.message || '请求失败，请重试'}</span>
          </div>
        )}
      </div>

      <div className="wbv2-composer">
        <div className="wbv2-quick">
          {(stagePrompts[stage] || []).map((prompt) => (
            <button key={prompt} disabled={waiting} onClick={() => setText(prompt)}>{prompt}</button>
          ))}
        </div>
        <div className="wbv2-input-shell">
          <textarea
            value={text}
            rows={3}
            placeholder={waiting ? '请先回答上方问题，或停止当前任务' : '告诉 Agent 下一步要完成什么…'}
            disabled={waiting}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <div className="wbv2-input-tools">
            <button className="wbv2-ref-button" onClick={onOpenSources}><Paperclip size={13} /> 资料 {selectedRefs > 0 ? `· ${selectedRefs}` : ''}</button>
            <button className="wbv2-send" disabled={!text.trim() || busy || running || waiting} onClick={submit} aria-label="发送">
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
        <p className="wbv2-composer-note">Agent 只能生成草稿；批准、付款核验与生产放行由你确认。</p>
      </div>
    </aside>
  );
}

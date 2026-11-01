import { useEffect, useRef, useState } from 'react';
import { ChevronDown, CircleAlert, Square, Wrench } from 'lucide-react';
import type { Inquiry, Message, Run, Session } from '../../api/types';
import { InquiryRunActivity } from '../InquiryRunActivity';

import { ErrorNotice, Modal } from '../../components/ui';
import { CustomerContextCard } from '../CustomerContextCard';
import { InquiryComposer } from '../InquiryComposer';
import { InquiryChatHeading, InquiryChatTranscript } from '../InquiryChatTranscript';
import { emptyComposerContext, restoreContext, type ComposerContext } from '../inquiry-context';
import '../inquiry.css';

type RecordItem = Record<string, any>;

export function AgentPanel({
  inquiry,
  session,
  messages,
  run,
  events,
  running,
  busy,
  selectedRefs,
  onSend,
  onAnswer,
  onOpenSources,
  onCancel,
  error,
}: {
  inquiry: Inquiry;
  session: Session;
  messages: Message[];
  run: Run | null;
  events: RecordItem[];
  running: boolean;
  busy: boolean;
  selectedRefs: number;
  onSend: (text: string, selection: ComposerContext) => Promise<boolean>;
  onAnswer: (answers: { questionId: string; value: string }[]) => Promise<boolean>;
  onOpenSources: () => void;
  onCancel: () => void;
  error: unknown;
}) {
  const draftKey = `easywork:business-chat:${session.user.id}:${session.workspace.id}:${inquiry.id}`;
  const [draft, setDraft] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(draftKey) || 'null');
      if (
        typeof saved?.text === 'string' &&
        Array.isArray(saved?.selection?.skillIds) &&
        Array.isArray(saved?.selection?.knowledge)
      )
        return saved as { text: string; selection: ComposerContext };
    } catch {
      /* Use an empty draft when storage is unavailable. */
    }
    return { text: '', selection: emptyComposerContext() };
  });
  const { text, selection } = draft;
  const [draftStored, setDraftStored] = useState(true);
  const [originalOpen, setOriginalOpen] = useState(false);
  const setText = (text: string) => setDraft((old) => ({ ...old, text }));
  const setSelection = (selection: ComposerContext) => setDraft((old) => ({ ...old, selection }));
  useEffect(() => {
    try {
      localStorage.setItem(draftKey, JSON.stringify(draft));
      setDraftStored(true);
    } catch {
      setDraftStored(false);
    }
  }, [draftKey, draft]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [showTools, setShowTools] = useState(false);
  const sendingRef = useRef(false);
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

  async function submit() {
    const submitted = draft;
    const value = text.trim();
    if (!value || busy || running || waiting || sendingRef.current) return;
    sendingRef.current = true;
    try {
      const accepted = await onSend(value, selection);
      if (accepted)
        setDraft((current) =>
          current === submitted ? { text: '', selection: emptyComposerContext() } : current,
        );
    } finally {
      sendingRef.current = false;
    }
  }

  async function submitAnswers() {
    const payload = questions.map((question) => ({
      questionId: question.id,
      value: (answers[question.id] || '').trim(),
    }));
    if (payload.some((item) => !item.value)) return;
    const ok = await onAnswer(payload);
    if (ok) setAnswers({});
  }

  return (
    <aside className="wbv2-agent iw-assistant" aria-label="AI 助手">
      <InquiryChatHeading />
      <div className="iw-ai-chat">
        <div className="iw-messages" ref={messagesRef}>
          <InquiryChatTranscript
            inquiry={inquiry}
            messages={messages}
            onOriginal={() => setOriginalOpen(true)}
          />

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

          {run && (
            <section
              className={`iw-run ${running ? 'iw-run-active' : ''}`}
              data-status={run.status}
              role="region"
              aria-label="AI 处理进度"
            >
              <InquiryRunActivity run={run} />
              <div className="wbv2-run-actions">
                {(running || waiting) && (
                  <button
                    className="button button-ghost iw-run-cancel"
                    onClick={onCancel}
                    disabled={busy}
                  >
                    <Square size={12} /> 取消本次运行
                  </button>
                )}
                {run.status === 'failed' && (
                  <button
                    className="button"
                    disabled={busy}
                    onClick={() =>
                      setDraft({
                        text: run.instruction || '',
                        selection: restoreContext(run.context),
                      })
                    }
                  >
                    恢复指令并重试
                  </button>
                )}
              </div>
            </section>
          )}
          {!!run?.fileOutputs?.length && (
            <div className="wbv2-tools" aria-label="本轮产出文件">
              <strong>本轮产出 · 待复核</strong>
              {run.fileOutputs.map((file) => (
                <p key={file.file_id}>
                  <a href={file.downloadUrl}>{file.name}</a>
                </p>
              ))}
            </div>
          )}

          {waiting && (
            <div className="wbv2-questions">
              <div className="wbv2-questions-head">
                <CircleAlert size={15} />
                <strong>需要你补充</strong>
                <button className="wbv2-text-button" onClick={onCancel}>
                  停止任务
                </button>
              </div>
              {questions.map((question) => (
                <label key={question.id}>
                  <span>{question.question}</span>
                  <input
                    value={answers[question.id] || ''}
                    placeholder="填写已知信息；不确定可写“待确认”"
                    onChange={(event) =>
                      setAnswers((old) => ({ ...old, [question.id]: event.target.value }))
                    }
                  />
                </label>
              ))}
              <button
                className="button button-primary"
                disabled={
                  busy || questions.some((question) => !(answers[question.id] || '').trim())
                }
                onClick={() => void submitAnswers()}
              >
                提交补充，继续任务
              </button>
            </div>
          )}

          <ErrorNotice error={error} />
        </div>

        <InquiryComposer
          session={session}
          inquiryId={inquiry.id}
          input={text}
          selection={selection}
          onInput={setText}
          onSelection={setSelection}
          canWrite={!busy && !running && !waiting}
          canSend={!!text.trim() && !busy && !running && !waiting}
          readOnly={running || waiting}
          draftsPending={false}
          draftStored={draftStored}
          sendLabel={inquiry.currentRevision ? '处理反馈' : '开始处理'}
          onSend={() => void submit()}
          onOriginal={() => setOriginalOpen(true)}
        />
        <div className="iw-case-actions">
          <button onClick={onOpenSources}>
            资料与依据{selectedRefs ? ` · ${selectedRefs}` : ''}
          </button>
        </div>
      </div>
      {originalOpen && (
        <Modal title="客户原始询盘" onClose={() => setOriginalOpen(false)}>
          <p className="iw-muted">客户：{inquiry.customer} · 原文留档</p>
          <CustomerContextCard inquiry={inquiry} />
          <pre className="iw-original-full">{inquiry.originalText}</pre>
        </Modal>
      )}
    </aside>
  );
}

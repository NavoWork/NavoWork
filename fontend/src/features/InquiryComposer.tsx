import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, BookOpen, Check, Paperclip, Search, Sparkles, X } from 'lucide-react';
import type { Session } from '../api';
import { ErrorNotice } from '../components/ui';
import { inlineContextToken, type ComposerContext } from './inquiry-context';
import { marketItems } from './skill-market-data';
import { useWikiDocuments } from './wiki-store';
import './inquiry-composer.css';

type PickerKind = 'skills' | 'knowledge';
type Picker = { kind: PickerKind; query: string; token?: { start: number; end: number } };

export function InquiryComposer({
  session,
  inquiryId,
  input,
  selection,
  canWrite,
  canSend,
  readOnly,
  draftsPending,
  draftStored,
  sendLabel,
  onInput,
  onSelection,
  onSend,
  onOriginal,
}: {
  session: Session;
  inquiryId: string;
  input: string;
  selection: ComposerContext;
  canWrite: boolean;
  canSend: boolean;
  readOnly: boolean;
  draftsPending: boolean;
  draftStored: boolean;
  sendLabel: string;
  onInput: (text: string) => void;
  onSelection: (context: ComposerContext) => void;
  onSend: () => void;
  onOriginal: () => void;
}) {
  const wiki = useWikiDocuments(session);
  const [picker, setPicker] = useState<Picker | null>(null);
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const id = useId();
  const keyword = picker?.query.trim().toLocaleLowerCase() || '';
  const items =
    picker?.kind === 'skills'
      ? marketItems.skills
          .filter((item) =>
            `${item.name} ${item.id} ${item.description} ${item.tags.join(' ')}`
              .toLocaleLowerCase()
              .includes(keyword),
          )
          .map((item) => ({
            id: item.id,
            name: item.name,
            description: item.description,
            caption: `/${item.id}`,
            selected: selection.skillIds.includes(item.id),
          }))
      : wiki.docs
          .filter((doc) =>
            `${doc.title} ${doc.folder} ${doc.content}`.toLocaleLowerCase().includes(keyword),
          )
          .map((doc) => ({
            id: doc.id,
            name: doc.title,
            description: doc.summary,
            caption: doc.folder,
            selected: selection.knowledge.some((item) => item.id === doc.id),
          }));

  useEffect(() => {
    if (!canWrite) setPicker(null);
  }, [canWrite]);
  useEffect(() => {
    if (!picker) return;
    const close = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setPicker(null);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [!!picker]);
  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);
  useEffect(() => setActive(0), [picker?.kind, picker?.query]);

  function detect(value: string, caret: number) {
    const token = inlineContextToken(value, caret);
    if (token && JSON.stringify(token) !== dismissed) {
      setPicker({ kind: token.kind, query: token.query, token });
      setActive(0);
    } else if (picker?.token) setPicker(null);
  }
  function dismiss() {
    if (picker?.token)
      setDismissed(JSON.stringify({ kind: picker.kind, query: picker.query, ...picker.token }));
    setPicker(null);
  }
  function open(kind: PickerKind) {
    if (!canWrite) return;
    setPicker({ kind, query: '', token: picker?.token });
    setActive(0);
    requestAnimationFrame(() => search.current?.focus());
  }
  function choose(index: number) {
    const item = items[index];
    if (!item || !picker || !canWrite) return;
    if (picker.kind === 'skills') {
      onSelection({
        ...selection,
        skillIds: item.selected
          ? selection.skillIds.filter((value) => value !== item.id)
          : [...selection.skillIds, item.id],
      });
    } else {
      const doc = wiki.docs.find((value) => value.id === item.id);
      if (!doc) return;
      const { id, title, folder, content, updated } = doc;
      onSelection({
        ...selection,
        knowledge: item.selected
          ? selection.knowledge.filter((value) => value.id !== id)
          : [...selection.knowledge, { id, title, folder, content, updated }],
      });
    }
    let caret = textarea.current?.selectionStart ?? input.length;
    if (picker.token) {
      const { start, end } = picker.token;
      onInput(input.slice(0, start) + input.slice(end));
      caret = start;
    }
    setPicker(null);
    setDismissed('');
    requestAnimationFrame(() => {
      textarea.current?.focus();
      textarea.current?.setSelectionRange(caret, caret);
    });
  }
  function pickerKey(event: KeyboardEvent) {
    if (
      !picker ||
      event.nativeEvent.isComposing ||
      event.nativeEvent.keyCode === 229 ||
      event.ctrlKey ||
      event.metaKey ||
      event.altKey
    )
      return false;
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      dismiss();
      textarea.current?.focus();
      return true;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (items.length)
        setActive(
          (value) => (value + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length,
        );
      return true;
    }
    if (event.key === 'Enter' || (event.key === 'Tab' && !event.shiftKey && items.length > 0)) {
      event.preventDefault();
      if (items.length) choose(Math.min(active, items.length - 1));
      return true;
    }
    return false;
  }

  return (
    <div className="iw-composer iw-context-composer" ref={root}>
      {!draftStored && (
        <ErrorNotice error="草稿暂存失败，请先保留文字与引用；本机存储恢复后继续编辑可重试。" />
      )}
      {picker && canWrite && (
        <div
          className="iw-context-picker"
          role="dialog"
          aria-label={picker.kind === 'skills' ? '选择技能' : '引用知识库'}
        >
          <div className="iw-picker-heading">
            <div>
              <button
                type="button"
                aria-pressed={picker.kind === 'skills'}
                onClick={() => open('skills')}
              >
                <Sparkles size={14} />
                技能
              </button>
              <button
                type="button"
                aria-pressed={picker.kind === 'knowledge'}
                onClick={() => open('knowledge')}
              >
                <BookOpen size={14} />
                知识库
              </button>
            </div>
            <button type="button" className="icon-button" aria-label="关闭选择器" onClick={dismiss}>
              <X size={14} />
            </button>
          </div>
          <div className="iw-picker-search">
            <Search size={14} />
            <input
              ref={search}
              aria-label={picker.kind === 'skills' ? '搜索技能' : '搜索知识库'}
              placeholder={picker.kind === 'skills' ? '搜索技能名称或用途…' : '搜索文档名称或正文…'}
              value={picker.query}
              onChange={(event) => setPicker({ ...picker, query: event.target.value })}
              onKeyDown={pickerKey}
              aria-controls={`${id}-options`}
              aria-activedescendant={
                items.length ? `${id}-option-${Math.min(active, items.length - 1)}` : undefined
              }
              aria-autocomplete="list"
            />
          </div>
          {picker.kind === 'knowledge' && (
            <ErrorNotice error={wiki.error} onRetry={() => void wiki.retry()} />
          )}
          <div
            className="iw-picker-options"
            role="listbox"
            aria-label={picker.kind === 'skills' ? '可用技能' : '可用知识文档'}
            id={`${id}-options`}
            ref={list}
          >
            {items.map((item, index) => (
              <button
                type="button"
                role="option"
                aria-selected={index === active}
                aria-label={item.name}
                id={`${id}-option-${index}`}
                key={item.id}
                data-index={index}
                tabIndex={-1}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(index)}
              >
                {picker.kind === 'skills' ? <Sparkles size={16} /> : <BookOpen size={16} />}
                <span>
                  <strong>{item.name}</strong>
                  <small>{item.description}</small>
                  <em>{item.caption}</em>
                </span>
                {item.selected && <Check size={15} aria-label="已选择" />}
              </button>
            ))}
            {!items.length && (
              <p className="iw-picker-empty" role="status">
                {picker.kind === 'knowledge' && wiki.loading
                  ? '正在读取知识库…'
                  : '没有找到匹配内容'}
              </p>
            )}
          </div>
          <div className="iw-picker-hint">↑↓ 选择 · Enter 确认 · Esc 关闭</div>
        </div>
      )}
      {(selection.skillIds.length > 0 || selection.knowledge.length > 0) && (
        <div className="iw-context-chips" aria-label="本次消息的技能与知识">
          {selection.skillIds.map((skillId) => {
            const skill = marketItems.skills.find((item) => item.id === skillId);
            return (
              <span className="iw-context-chip skill" key={skillId}>
                <Sparkles size={12} />
                <span title={skill?.description}>{skill?.name || skillId}</span>
                <button
                  type="button"
                  aria-label={`移除技能 ${skill?.name || skillId}`}
                  disabled={!canWrite}
                  onClick={() =>
                    onSelection({
                      ...selection,
                      skillIds: selection.skillIds.filter((id) => id !== skillId),
                    })
                  }
                >
                  <X size={11} />
                </button>
              </span>
            );
          })}
          {selection.knowledge.map((doc) => (
            <span className="iw-context-chip knowledge" key={doc.id}>
              <BookOpen size={12} />
              <span title={`${doc.folder} · ${doc.updated}`}>{doc.title}</span>
              <button
                type="button"
                aria-label={`移除知识 ${doc.title}`}
                disabled={!canWrite}
                onClick={() =>
                  onSelection({
                    ...selection,
                    knowledge: selection.knowledge.filter((item) => item.id !== doc.id),
                  })
                }
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      <label className="sr-only" htmlFor={`instruction-${inquiryId}`}>
        补充要求或客户反馈
      </label>
      <textarea
        ref={textarea}
        id={`instruction-${inquiryId}`}
        value={input}
        disabled={!canWrite}
        placeholder={
          readOnly
            ? '请回到当前版本、恢复处理或等待运行完成'
            : '输入要求，/ 选择技能，@ 引用知识库…'
        }
        onChange={(event) => {
          onInput(event.target.value);
          detect(event.target.value, event.target.selectionStart);
        }}
        onClick={(event) => detect(event.currentTarget.value, event.currentTarget.selectionStart)}
        onKeyUp={(event) => {
          if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key))
            detect(event.currentTarget.value, event.currentTarget.selectionStart);
        }}
        aria-controls={picker ? `${id}-options` : undefined}
        aria-activedescendant={
          picker && items.length ? `${id}-option-${Math.min(active, items.length - 1)}` : undefined
        }
        aria-autocomplete="list"
        onKeyDown={(event) => {
          if (pickerKey(event)) return;
          if (
            event.key !== 'Enter' ||
            event.nativeEvent.isComposing ||
            event.nativeEvent.keyCode === 229
          )
            return;
          event.preventDefault();
          if (event.ctrlKey || event.shiftKey) {
            event.currentTarget.setRangeText(
              '\n',
              event.currentTarget.selectionStart,
              event.currentTarget.selectionEnd,
              'end',
            );
            onInput(event.currentTarget.value);
            setPicker(null);
          } else if (canSend) onSend();
        }}
      />
      <div className="iw-composer-foot">
        <div className="iw-composer-tools">
          <button
            type="button"
            className="icon-button"
            aria-label="查看客户原始询盘"
            title="客户原始询盘"
            onClick={onOriginal}
          >
            <Paperclip size={16} />
          </button>
          <button
            type="button"
            className="iw-composer-tool"
            aria-label="选择技能"
            title="选择技能（/）"
            aria-expanded={picker?.kind === 'skills'}
            aria-haspopup="dialog"
            disabled={!canWrite}
            onClick={() => open('skills')}
          >
            <Sparkles size={14} />
            <span>技能</span>
          </button>
          <button
            type="button"
            className="iw-composer-tool"
            aria-label="引用知识库"
            title="引用知识库（@）"
            aria-expanded={picker?.kind === 'knowledge'}
            aria-haspopup="dialog"
            disabled={!canWrite}
            onClick={() => open('knowledge')}
          >
            <BookOpen size={14} />
            <span>知识库</span>
          </button>
        </div>
        <span className="iw-composer-status">
          {draftsPending
            ? '正在载入草稿…'
            : !draftStored
              ? '草稿未保存'
              : input || selection.skillIds.length || selection.knowledge.length
                ? '草稿已暂存'
                : '仅当前询盘'}
        </span>
        <button
          type="button"
          className="button button-primary iw-send-button"
          aria-label={sendLabel}
          aria-keyshortcuts="Enter"
          title={sendLabel}
          disabled={!canSend}
          onClick={onSend}
        >
          <ArrowUp size={18} />
        </button>
      </div>
    </div>
  );
}

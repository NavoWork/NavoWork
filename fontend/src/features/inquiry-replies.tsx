import { useEffect, useRef, useState } from 'react';
import { Check, Copy, RefreshCw, TriangleAlert } from 'lucide-react';
import { api, ApiError } from '../api';
import type { Draft, Locale, Revision } from '../api/types';
import { ErrorNotice, Loading, Modal, StatusBadge } from '../components/ui';
export interface DraftState {
  revision: number | null;
  versions: Partial<Record<Locale, number>>;
  pending: boolean;
}
type Entry = {
  saved: Draft;
  text: string;
  status: 'saved' | 'dirty' | 'saving' | 'failed' | 'conflict';
  error?: unknown;
  remote?: Draft;
};
type Entries = Partial<Record<Locale, Entry>>;
const locales: Locale[] = ['en-US', 'es-MX'];
const names: Record<Locale, string> = { 'en-US': 'English', 'es-MX': 'Español · México' };
function recovery(key: string): { text: string; baseDraftVersion: number } | null {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null');
  } catch {
    return null;
  }
}
function storeRecovery(key: string, entry?: Entry) {
  try {
    if (!entry || entry.text === entry.saved.text) localStorage.removeItem(key);
    else
      localStorage.setItem(
        key,
        JSON.stringify({ text: entry.text, baseDraftVersion: entry.saved.draftVersion }),
      );
  } catch {
    /* Unsaved recovery does not change server save status. */
  }
}
export function ReplyEditor({
  path,
  revision,
  scope,
  readOnly,
  restoreLocal,
  refreshKey,
  onState,
}: {
  path: string;
  revision: Revision;
  scope: string;
  readOnly: boolean;
  restoreLocal: boolean;
  refreshKey: number;
  onState: (state: DraftState) => void;
}) {
  const [locale, setLocale] = useState<Locale>(() => {
    try {
      return localStorage.getItem(`easywork:language:${scope}`) === 'es-MX' ? 'es-MX' : 'en-US';
    } catch {
      return 'en-US';
    }
  });
  const [entries, setEntries] = useState<Entries>({});
  const refs = useRef(entries);
  refs.current = entries;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [retry, setRetry] = useState(0);
  const [compare, setCompare] = useState<Locale | null>(null);
  const [copied, setCopied] = useState('');
  const mounted = useRef(true);
  const saving = useRef(new Set<Locale>());
  const recoveryKey = (language: Locale) =>
    `easywork:unsaved-reply:${scope}:${revision.number}:${language}`;
  const update = (fn: (current: Entries) => Entries) => {
    const next = fn(refs.current);
    refs.current = next;
    if (mounted.current) setEntries(next);
  };
  useEffect(() => {
    const c = new AbortController();
    if (!Object.keys(refs.current).length) setLoading(true);
    setError(undefined);
    api
      .get<{ items: Draft[] }>(`${path}/revisions/${revision.number}/reply-drafts`, c.signal)
      .then((result) => {
        update((old) => {
          const next = { ...old };
          for (const saved of result.items) {
            if (old[saved.locale] && old[saved.locale]?.status !== 'saved') continue;
            const local = restoreLocal ? recovery(recoveryKey(saved.locale)) : null;
            const isDifferent = local && local.text !== saved.text;
            next[saved.locale] = {
              saved,
              text: isDifferent ? local.text : saved.text,
              status: isDifferent
                ? local.baseDraftVersion === saved.draftVersion
                  ? 'dirty'
                  : 'conflict'
                : 'saved',
              ...(isDifferent && local.baseDraftVersion !== saved.draftVersion
                ? { remote: saved, error: '本机有未保存修改，服务端草稿已更新，请比较后选择。' }
                : {}),
            };
          }
          return next;
        });
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [path, revision.number, refreshKey, retry, restoreLocal]);
  useEffect(() => {
    onState({
      revision: revision.number,
      versions: Object.fromEntries(
        locales.flatMap((l) => (entries[l] ? [[l, entries[l]!.saved.draftVersion]] : [])),
      ),
      pending:
        loading || !!error || locales.some((l) => !entries[l] || entries[l]?.status !== 'saved'),
    });
  }, [entries, loading, error, onState]);
  async function save(language: Locale, explicit = false) {
    const item = refs.current[language];
    if (
      !item ||
      readOnly ||
      saving.current.has(language) ||
      (item.status !== 'dirty' && !(explicit && item.status === 'failed'))
    )
      return;
    if (item.text === item.saved.text) {
      update((old) => ({ ...old, [language]: { ...item, status: 'saved', error: undefined } }));
      storeRecovery(recoveryKey(language));
      return;
    }
    saving.current.add(language);
    const text = item.text;
    update((old) => ({
      ...old,
      [language]: { ...old[language]!, status: 'saving', error: undefined },
    }));
    try {
      const saved = await api.put<Draft>(
        `${path}/revisions/${revision.number}/reply-drafts/${language}`,
        { text, baseDraftVersion: item.saved.draftVersion },
      );
      update((old) => ({
        ...old,
        [language]: {
          ...old[language]!,
          saved,
          status: old[language]!.text === saved.text ? 'saved' : 'dirty',
        },
      }));
      storeRecovery(recoveryKey(language), refs.current[language]);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'DRAFT_CONFLICT') {
        let remote: Draft | undefined;
        try {
          remote = await api.get<Draft>(
            `${path}/revisions/${revision.number}/reply-drafts?locale=${language}`,
          );
        } catch {
          /* Keep the original conflict and local text if re-read fails. */
        }
        update((old) => ({
          ...old,
          [language]: { ...old[language]!, status: 'conflict', error: e, remote },
        }));
      } else
        update((old) => ({
          ...old,
          [language]: { ...old[language]!, status: 'failed', error: e },
        }));
    } finally {
      saving.current.delete(language);
    }
  }
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (Object.values(refs.current).some((e) => e && e.status !== 'saved')) {
        event.preventDefault();
        event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, []);
  const saveRef = useRef(save);
  saveRef.current = save;
  useEffect(() => {
    const timer = setTimeout(() => {
      for (const l of locales) void saveRef.current(l);
    }, 800);
    return () => clearTimeout(timer);
  }, [entries, readOnly]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  function select(language: Locale) {
    void save(locale);
    setLocale(language);
    setCopied('');
    try {
      localStorage.setItem(`easywork:language:${scope}`, language);
    } catch {
      /* optional preference */
    }
  }
  function change(text: string) {
    update((old) => ({
      ...old,
      [locale]: {
        ...old[locale]!,
        text,
        status: old[locale]?.status === 'conflict' ? 'conflict' : 'dirty',
      },
    }));
    storeRecovery(recoveryKey(locale), refs.current[locale]);
    setCopied('');
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(entries[locale]?.text || '');
      setCopied('已复制当前草稿');
    } catch {
      setCopied('复制失败，请选中文字手动复制');
    }
  }
  async function resolve(language: Locale, keep: boolean) {
    const entry = refs.current[language];
    if (!entry) return;
    try {
      const remote =
        entry.remote ||
        (await api.get<Draft>(
          `${path}/revisions/${revision.number}/reply-drafts?locale=${language}`,
        ));
      update((old) => ({
        ...old,
        [language]: {
          saved: remote,
          text: keep ? old[language]!.text : remote.text,
          status: keep ? 'dirty' : 'saved',
        },
      }));
      storeRecovery(recoveryKey(language), refs.current[language]);
      setCompare(null);
      if (keep) void save(language);
    } catch (e) {
      update((old) => ({ ...old, [language]: { ...old[language]!, error: e } }));
    }
  }
  const item = entries[locale];
  return (
    <div className="iw-reply-editor">
      <div className="iw-section-heading">
        <span className="iw-kicker">READY FOR YOUR REVIEW</span>
        <h3>用客户的语言，准确表达</h3>
        <p>两种语言独立保存。回复是待人工核对的草稿材料。</p>
      </div>
      <div className="iw-language-bar">
        <div>
          {locales.map((l) => (
            <button
              key={l}
              aria-pressed={locale === l}
              className={locale === l ? 'selected' : ''}
              onClick={() => select(l)}
            >
              {names[l]}
            </button>
          ))}
        </div>
        <button className="button button-ghost" disabled={!item} onClick={copy}>
          <Copy size={13} />
          复制
        </button>
      </div>
      {loading ? (
        <Loading label="正在读取草稿" />
      ) : (
        <>
          <ErrorNotice error={error} onRetry={() => setRetry((v) => v + 1)} />
          {item && (
            <>
              <div className="iw-draft-status" aria-live="polite">
                <span>
                  {readOnly ? (
                    '只读内容'
                  ) : item.status === 'saved' ? (
                    <>
                      <Check size={12} />
                      已保存 · 草稿 V{item.saved.draftVersion}
                    </>
                  ) : item.status === 'saving' ? (
                    '正在保存…'
                  ) : item.status === 'dirty' ? (
                    '有未保存修改'
                  ) : item.status === 'conflict' ? (
                    '草稿冲突 · 本地修改已保留'
                  ) : (
                    '保存失败 · 尚未保存到服务端'
                  )}
                </span>
                <StatusBadge
                  status={item.status === 'saved' ? item.saved.reviewStatus : 'needs_review'}
                />
              </div>
              <textarea
                className="iw-reply-text"
                aria-label={`${names[locale]} 回复草稿`}
                value={item.text}
                onChange={(e) => change(e.target.value)}
                onBlur={() => void save(locale)}
                readOnly={readOnly}
                spellCheck={false}
              />
              {item.error && (
                <ErrorNotice
                  error={item.error}
                  onRetry={item.status === 'failed' ? () => void save(locale, true) : undefined}
                />
              )}{' '}
              {item.status === 'conflict' && (
                <button className="button" onClick={() => setCompare(locale)}>
                  <TriangleAlert size={13} />
                  比较本地与服务端版本
                </button>
              )}
            </>
          )}
        </>
      )}
      {copied && (
        <p role="status" className="iw-muted">
          {copied}
        </p>
      )}
      {compare && entries[compare] && (
        <Modal title="草稿有更新，请比较后选择" wide onClose={() => setCompare(null)}>
          <p className="iw-muted">
            当前输入不会被静默覆盖。保留本地修改会在最新服务端版本上重新保存，并要求重新复核。
          </p>
          <div className="iw-draft-comparison">
            <section>
              <h3>本地未保存修改</h3>
              <pre>{entries[compare]!.text}</pre>
            </section>
            <section>
              <h3>服务端草稿 V{entries[compare]!.remote?.draftVersion || '?'}</h3>
              <pre>{entries[compare]!.remote?.text || '服务端版本暂未获取，请重试读取。'}</pre>
            </section>
          </div>
          <div className="iw-modal-actions">
            <button className="button" onClick={() => void resolve(compare, false)}>
              <RefreshCw size={14} />
              使用服务端版本
            </button>
            <button
              className="button button-primary"
              disabled={readOnly}
              onClick={() => void resolve(compare, true)}
            >
              保留本地修改并保存
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

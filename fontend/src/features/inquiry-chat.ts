import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { Inquiry, Session } from '../api/types';
import { emptyComposerContext, type ComposerContext } from './inquiry-context';

type ChatDraft = { text: string; selection: ComposerContext };
function read<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback; }
  catch { return fallback; }
}

export function useInquiryChat(session: Session, inquiryId: string, active: boolean, legacyDraft?: ChatDraft) {
  const scope = `${session.user.id}:${session.workspace.id}:${inquiryId}`;
  const storageKey = `easywork:inquiry-chat-draft:${scope}`;
  const qc = useQueryClient();
  const key = ['inquiry-chat', scope];
  const detail = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api.get<Inquiry>(`/workspaces/${session.workspace.id}/inquiries/${encodeURIComponent(inquiryId)}`, signal),
    enabled: active,
    refetchInterval: active ? 3000 : false,
  });
  const [draft, setDraftState] = useState<ChatDraft>(() => {
    const empty = { text: '', selection: emptyComposerContext() };
    // Recover the last selected draft once; old storage stays intact.
    const oldId = read(`easywork:active-chat:${scope}`, 'default');
    const fallback = read(`easywork:chat-draft:${scope}:${oldId}`,
      read(`easywork:chat-draft:${scope}:default`, legacyDraft || read(`easywork:business-chat:${scope}`, empty)));
    const value = read(storageKey, fallback);
    return typeof value?.text === 'string' && Array.isArray(value.selection?.skillIds) && Array.isArray(value.selection?.knowledge) ? value : empty;
  });
  const draftRef = useRef(draft);
  const [stored, setStored] = useState(true);
  const setDraft = (update: ChatDraft | ((old: ChatDraft) => ChatDraft)) => {
    const next = typeof update === 'function' ? update(draftRef.current) : update;
    draftRef.current = next;
    setDraftState(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); setStored(true); }
    catch { setStored(false); }
  };
  useEffect(() => {
    if (!detail.data) return;
    void qc.invalidateQueries({ queryKey: ['inquiry', scope] });
    void qc.invalidateQueries({ queryKey: ['workbench-v2', scope] });
    void qc.invalidateQueries({ queryKey: ['workbench-messages', scope] });
  }, [detail.data?.metadataVersion, qc, scope]);
  const recordRun = (latestRunId: string) => {
    qc.setQueryData<Inquiry>(key, (old) => old && { ...old, latestRunId });
    void qc.invalidateQueries({ queryKey: key });
  };
  return { latestRunId: detail.data?.activeRunId || detail.data?.pendingRunId || detail.data?.latestRunId,
    loading: detail.isPending, error: detail.error, refresh: detail.refetch, recordRun, draft, setDraft, draftStored: stored };
}
export type InquiryChat = ReturnType<typeof useInquiryChat>;

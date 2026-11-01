import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { mode, type Session } from '../api';
import { wikiDocuments, type WikiDocument } from './library-data';
import { useLibraryCollection } from './library-api';

const changedEvent = 'navowork:wiki-changed';
export const wikiStorageKey = (session: Session) =>
  `navowork:wiki:${session.user.id}:${session.workspace.id}`;

function readDocuments(key: string): WikiDocument[] {
  const raw = localStorage.getItem(key);
  if (!raw) return wikiDocuments;
  const docs: unknown = JSON.parse(raw);
  if (
    !Array.isArray(docs) ||
    docs.some(
      (doc) =>
        !doc ||
        ['id', 'title', 'folder', 'summary', 'content', 'updated'].some(
          (field) => typeof doc[field] !== 'string',
        ) ||
        typeof doc.starred !== 'boolean',
    )
  )
    throw new Error('本机知识库无法读取，原数据已保留，请检查存储后重试。');
  return docs;
}

export function useWikiDocuments(session: Session) {
  const remote = useLibraryCollection(session, 'documents', wikiDocuments);
  const client = useQueryClient();
  const key = wikiStorageKey(session);
  const queryKey = ['wiki-documents', session.user.id, session.workspace.id];
  const [writeError, setWriteError] = useState<unknown>();
  const query = useQuery({
    queryKey,
    enabled: mode === 'mock',
    queryFn: () => readDocuments(key),
    staleTime: 0,
  });
  useEffect(() => {
    const refresh = () =>
      void client.invalidateQueries({
        queryKey: ['wiki-documents', session.user.id, session.workspace.id],
      });
    const local = (event: Event) => {
      if ((event as CustomEvent<string>).detail === key) refresh();
    };
    const storage = (event: StorageEvent) => {
      if (event.key === key || event.key === null) refresh();
    };
    window.addEventListener(changedEvent, local);
    window.addEventListener('storage', storage);
    return () => {
      window.removeEventListener(changedEvent, local);
      window.removeEventListener('storage', storage);
    };
  }, [client, key, session.user.id, session.workspace.id]);
  function update(change: (docs: WikiDocument[]) => WikiDocument[]) {
    if (mode === 'real') {
      remote.setValues(change);
      return true;
    }
    try {
      const docs = change(readDocuments(key));
      localStorage.setItem(key, JSON.stringify(docs));
      client.setQueryData(queryKey, docs);
      window.dispatchEvent(new CustomEvent(changedEvent, { detail: key }));
      setWriteError(undefined);
      return true;
    } catch (error) {
      setWriteError(error);
      return false;
    }
  }
  return {
    path: remote.path,
    docs: mode === 'real' ? remote.values : query.data || [],
    update,
    loading: mode === 'real' ? remote.query.isPending : query.isPending,
    error: mode === 'real' ? remote.query.error : writeError || query.error,
    retry: mode === 'real' ? remote.query.refetch : query.refetch,
  };
}

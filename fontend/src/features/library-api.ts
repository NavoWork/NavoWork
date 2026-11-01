import { useState, type SetStateAction } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, mode, type Session } from '../api';

export function useLibraryCollection<T>(session: Session, group: string, demo: T[]) {
  const [local, setLocal] = useState(demo);
  const client = useQueryClient();
  const key = ['library', session.workspace.id, session.user.id, group];
  const path = `/workspaces/${session.workspace.id}/library/${group}`;
  const query = useQuery({ queryKey: key, enabled: mode === 'real',
    refetchInterval: group === 'assets' ? 5000 : false,
    queryFn: ({ signal }) => api.get<{ items: T[] }>(path, signal) });
  const values = mode === 'real' ? query.data?.items || [] : local;
  const setValues = (action: SetStateAction<T[]>) => {
    if (mode === 'mock') { setLocal(action); return; }
    client.setQueryData<{ items: T[] }>(key, old => ({ items:
      typeof action === 'function' ? action(old?.items || []) : action }));
  };
  return { values, setValues, query, path };
}

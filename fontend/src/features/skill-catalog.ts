import { useQuery } from '@tanstack/react-query';
import { api, mode, type Session } from '../api';
import { marketItems } from './skill-market-data';

export interface CatalogSkill {
  id: string;
  name: string;
  description: string;
  tags: string[];
  includes: string[];
  tab: string;
  status: 'available' | 'disabled' | 'planned';
}

export function useAvailableSkills(session: Session) {
  const query = useQuery({
    queryKey: ['skill-market', session.workspace.id, session.user.id],
    enabled: mode === 'real',
    queryFn: ({ signal }) =>
      api.get<{ items: CatalogSkill[] }>(
        `/workspaces/${session.workspace.id}/skill-market`,
        signal,
      ),
  });
  return {
    skills:
      mode === 'mock'
        ? marketItems.skills
        : (query.data?.items || []).filter(
            (item) => item.tab === 'skills' && item.status === 'available',
          ),
    loading: mode === 'real' && query.isPending,
    error: query.error,
    retry: query.refetch,
  };
}

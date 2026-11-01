import { useEffect } from 'react';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, mode } from '../api';
import type {
  Asset,
  Draft,
  Inquiry,
  MaterialBundle,
  Message,
  Page,
  Revision,
  Session,
  Source,
} from '../api/types';
import {
  canvasKey,
  defaultFolders,
  getCanvasFile,
  initialCanvas,
  inquiryAssetsChangedEvent,
  readCanvas,
  resultSnapshot,
  workspaceDocuments,
  type CanvasState,
} from './inquiry-canvas-model';
import type { AssetKind, LibraryAsset } from './library-data';

export interface InquiryAssetGroup {
  id: string;
  title: string;
  folders: { id: string; title: string }[];
  assets: LibraryAsset[];
}

export function inquiryFolderKey(id: string, category?: string) {
  return `inquiry:${id}${category ? `:${category}` : ''}`;
}

function fileKind(name: string, mime: string): AssetKind {
  if (mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|svg|avif|bmp)$/i.test(name))
    return 'image';
  if (mime.startsWith('video/') || /\.(mp4|mov|webm|m4v)$/i.test(name)) return 'video';
  if (/\.(xlsx?|csv|ods|numbers)$/i.test(name)) return 'spreadsheet';
  if (/\.(pdf|docx?|pptx?|txt|md|pages|key)$/i.test(name)) return 'document';
  return 'other';
}

function sizeLabel(size: number) {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export async function loadInquiryAssetGroup(
  session: Session,
  inquiry: Inquiry,
  signal?: AbortSignal,
): Promise<InquiryAssetGroup> {
  const scope = `${session.user.id}:${session.workspace.id}:${inquiry.id}`;
  const base = `/workspaces/${encodeURIComponent(session.workspace.id)}`;
  const path = `${base}/inquiries/${encodeURIComponent(inquiry.id)}`;
  const [messages, revisions, bundles, canvas] = await Promise.all([
    api.get<{ items: Message[] }>(`${path}/messages`, signal),
    api.get<{ items: Revision[] }>(`${path}/revisions`, signal),
    api.get<{ items: MaterialBundle[] }>(`${path}/material-bundles`, signal),
    mode === 'real'
      ? api.get<{ state: CanvasState | null }>(`${path}/canvas`, signal)
      : Promise.resolve({ state: readCanvas(scope) }),
  ]);
  const state = canvas.state || initialCanvas();
  const revision = revisions.items.find((item) => item.number === inquiry.currentRevision);
  const includedRevisions = revisions.items.filter(
    (item) => item.number === inquiry.currentRevision || item.number === state.initialRevision,
  );
  const refs = Array.from(
    new Map(
      includedRevisions.flatMap((item) => item.sourceRefs).map((ref) => [ref.sourceVersionId, ref]),
    ).values(),
  );
  const [sources, assetResponse, drafts] = await Promise.all([
    Promise.all(
      refs.map(
        async (ref) =>
          [
            ref.sourceVersionId,
            await api.get<Source>(
              `${base}/sources/${encodeURIComponent(ref.sourceId)}/versions/${ref.version}`,
              signal,
            ),
          ] as const,
      ),
    ),
    revision?.assetRefs.length
      ? api.get<{ items: Asset[] }>(`${base}/assets`, signal)
      : Promise.resolve({ items: [] as Asset[] }),
    Promise.all(
      revisions.items.map(async (item) => ({
        revision: item.number,
        drafts: (
          await api.get<{ items: Draft[] }>(`${path}/revisions/${item.number}/reply-drafts`, signal)
        ).items,
      })),
    ),
  ]);
  const replies = new Map(
    drafts.map((item) => [
      item.revision,
      Object.fromEntries(item.drafts.filter(Boolean).map((draft) => [draft.locale, draft.text])),
    ]),
  );
  const docs = workspaceDocuments({
    inquiry,
    revision,
    revisions: revisions.items,
    messages: messages.items,
    state,
    replyText: revision ? replies.get(revision.number)?.['en-US'] : undefined,
    sources: Object.fromEntries(sources),
    assets: assetResponse.items,
    bundles: bundles.items,
  });
  const folders = [...defaultFolders, ...state.folders];
  const assets = await Promise.all(
    docs.map(async (doc): Promise<LibraryAsset> => {
      const folderTitle = folders.find((folder) => folder.id === doc.folder)?.title || '未分类';
      const origin = {
        id: inquiry.id,
        title: inquiry.title,
        documentId: doc.id,
        folderId: doc.folder,
        folderTitle,
      };
      const common = {
        id: `${scope}:${doc.id}`,
        space: 'personal' as const,
        folder: `${inquiry.title} / ${folderTitle}`,
        updated: doc.revision?.createdAt || inquiry.updatedAt,
        starred: false,
        art: 'notes' as const,
        inquiry: origin,
      };
      if (doc.file) {
        const file =
          doc.file.assetId || doc.file.serverFileId
            ? undefined
            : await getCanvasFile(scope, doc.file.id);
        const asset = assetResponse.items.find(
          (item) => item.id === doc.file!.assetId && item.version === doc.file!.version,
        );
        const extension = doc.file.name.match(/\.[^.]+$/)?.[0] || '';
        const name = doc.title.endsWith(extension) ? doc.title : `${doc.title}${extension}`;
        return {
          ...common,
          name,
          kind: fileKind(doc.file.name, doc.file.mediaType),
          size: sizeLabel(doc.file.size),
          mime: doc.file.mediaType,
          file,
          content:
            file && (file.type.startsWith('text/') || /\.(txt|md|csv|json)$/i.test(file.name))
              ? await file.text()
              : undefined,
          url: asset?.url,
          downloadPath: doc.file.serverFileId
            ? `${path}/canvas/files/${encodeURIComponent(doc.file.serverFileId)}/download`
            : doc.file.assetId
              ? `${base}/assets/${encodeURIComponent(doc.file.assetId)}/versions/${doc.file.version}/download`
              : undefined,
          unavailable:
            !doc.file.assetId && !doc.file.serverFileId && !file
              ? '本机附件无法读取，请返回原询盘重新添加。'
              : undefined,
        };
      }
      let text = doc.text;
      if (doc.kind === 'conversation') {
        text =
          messages.items
            .map(
              (message) =>
                `${message.role === 'user' ? '你' : 'Navowork'} · ${message.createdAt}\n\n${message.text}`,
            )
            .join('\n\n---\n\n') || doc.text;
      }
      if (doc.kind === 'reply' && doc.revision) {
        const reply = replies.get(doc.revision.number);
        text = `## English\n\n${state.drafts[doc.id] ?? reply?.['en-US'] ?? doc.revision.replies['en-US']}\n\n## Español · México\n\n${reply?.['es-MX'] ?? doc.revision.replies['es-MX']}`;
      }
      if (doc.kind === 'revision' && doc.revision) {
        text = resultSnapshot(doc.revision, replies.get(doc.revision.number)).text;
      }
      const content = `# ${doc.title}\n\n> 询盘：${inquiry.title}\n> 分类：${folderTitle}\n\n${text}`;
      const version =
        doc.revision && ['requirements', 'risks', 'quote', 'reply'].includes(doc.kind)
          ? ` · V${doc.revision.number}`
          : '';
      return {
        ...common,
        name: `${doc.title.replace(/[\\/]/g, '-')}${version}.md`,
        kind: 'document',
        size: sizeLabel(new Blob([content]).size),
        mime: 'text/markdown',
        content,
      };
    }),
  );
  return { id: inquiry.id, title: inquiry.title, folders, assets };
}

export function useInquiryAssets(session: Session) {
  const queryClient = useQueryClient();
  const prefix = ['inquiry-library', session.user.id, session.workspace.id];
  const list = useQuery({
    queryKey: [...prefix, 'list'],
    staleTime: 0,
    queryFn: async ({ signal }) => {
      const items: Inquiry[] = [];
      let cursor: string | null = null;
      do {
        const page: Page<Inquiry> = await api.get(
          `/workspaces/${encodeURIComponent(session.workspace.id)}/inquiries?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
          signal,
        );
        items.push(...page.items);
        cursor = page.nextCursor;
      } while (cursor);
      return items;
    },
  });
  const queries = useQueries({
    queries: (list.data || []).map((inquiry) => ({
      queryKey: [...prefix, inquiry.id, inquiry.updatedAt, inquiry.currentRevision],
      staleTime: 0,
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        loadInquiryAssetGroup(session, inquiry, signal),
    })),
  });
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const invalidate = () => {
      clearTimeout(timer);
      timer = setTimeout(
        () =>
          void queryClient.invalidateQueries({
            queryKey: ['inquiry-library', session.user.id, session.workspace.id],
          }),
        200,
      );
    };
    const onCanvasChanged = (event: Event) => {
      if (
        (event as CustomEvent<string>).detail.startsWith(
          `${session.user.id}:${session.workspace.id}:`,
        )
      )
        invalidate();
    };
    const onStorage = (event: StorageEvent) => {
      if (
        !event.key ||
        event.key.startsWith(canvasKey(`${session.user.id}:${session.workspace.id}:`))
      )
        invalidate();
    };
    window.addEventListener(inquiryAssetsChangedEvent, onCanvasChanged);
    window.addEventListener('storage', onStorage);
    return () => {
      clearTimeout(timer);
      window.removeEventListener(inquiryAssetsChangedEvent, onCanvasChanged);
      window.removeEventListener('storage', onStorage);
    };
  }, [queryClient, session.user.id, session.workspace.id]);
  return {
    groups: queries.flatMap((query) => (query.data ? [query.data] : [])),
    loading: list.isPending || queries.some((query) => query.isPending),
    error: list.error || queries.find((query) => query.error)?.error,
    retry: () => queryClient.invalidateQueries({ queryKey: prefix }),
  };
}

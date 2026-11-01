import { openDB } from 'idb';
import { channelLabels } from './CustomerContextCard';
import type {
  Asset,
  Inquiry,
  Locale,
  MaterialBundle,
  Message,
  Revision,
  Source,
} from '../api/types';

export const inquiryAssetsChangedEvent = 'navowork:inquiry-assets-changed';

export type DocumentKind =
  | 'original'
  | 'conversation'
  | 'requirements'
  | 'risks'
  | 'quote'
  | 'reply'
  | 'source'
  | 'file'
  | 'note'
  | 'result'
  | 'revision';
export interface SavedResult {
  revision: number;
  title: string;
  text: string;
}
export interface WorkspaceDocument {
  id: string;
  title: string;
  kind: DocumentKind;
  folder: string;
  text: string;
  caption: string;
  hasContent?: boolean;
  source?: Source;
  file?: WorkspaceFile;
  revision?: Revision;
  directoryOnly?: boolean;
  evidenceId?: string;
  reference?: { sourceId: string; version: number };
}

const workflowKinds: DocumentKind[] = ['requirements', 'quote', 'risks', 'reply'];

function hasMeaningfulText(text: string): boolean {
  return text.split('\n').some((line) => {
    const value = line.replace(/^(产品|数量|规格|目的地|到货要求|定制)[：:]\s*/, '').trim();
    return (
      value !== '' &&
      !/^(待确认|待补充|待填写|尚未生成。选择现有原件和知识库依据，生成此节点的第一份草稿。)$/.test(
        value,
      )
    );
  });
}

function revisionNodeHasContent(
  revision: Revision | undefined,
  kind: DocumentKind,
  replyText?: string,
): boolean {
  if (!revision) return false;
  switch (kind) {
    case 'requirements':
      return [
        revision.requirements.requestedProduct,
        revision.requirements.specification,
        revision.requirements.quantity,
        revision.requirements.destination,
        revision.requirements.requestedArrival,
        revision.requirements.customization,
      ].some((value) => value != null && hasMeaningfulText(String(value)));
    case 'quote':
      return Boolean(
        revision.quote ||
        revision.proposal.differences.some(hasMeaningfulText) ||
        (revision.generatedNode === 'quote' && revision.proposal.selectedSku),
      );
    case 'risks':
      return (
        revision.risks.length > 0 ||
        revision.generatedNode === 'risks' ||
        Boolean(revision.artifactVersionIds?.inquiry_assessment)
      );
    case 'reply':
      return hasMeaningfulText(replyText ?? revision.replies['en-US']);
    default:
      return false;
  }
}

// Keep existing content visible, and reveal only the first unfinished business node.
// Conversation and result navigation remain available in the document directory.
export function progressiveCanvasDocuments(
  documents: WorkspaceDocument[],
  includeResults = false,
): WorkspaceDocument[] {
  const next = workflowKinds
    .map((kind) => documents.find((doc) => doc.kind === kind))
    .find((doc) => doc && !doc.hasContent);
  return documents.filter((doc) => {
    if (doc.kind === 'conversation' || doc.kind === 'revision') return false;
    if (doc.kind === 'result') return includeResults;
    if (workflowKinds.includes(doc.kind)) return doc.hasContent || doc === next;
    return true;
  });
}
export interface WorkspaceFile {
  serverFileId?: string;
  caseId?: string;
  id: string;
  name: string;
  title: string;
  mediaType: string;
  size: number;
  folder: string;
  assetId?: string;
  version?: number;
}
export interface CanvasState {
  schema: 1;
  positions: Record<string, { x: number; y: number }>;
  viewport?: { x: number; y: number; zoom: number };
  directoryWidth?: number;
  tabs: string[];
  active: string;
  folders: { id: string; title: string }[];
  notes: { id: string; title: string; text: string; folder: string }[];
  files: WorkspaceFile[];
  drafts: Record<string, string>;
  initialRevision?: number;
  results?: SavedResult[];
}
export const defaultFolders = [
  { id: 'inquiry', title: '客户询盘' },
  { id: 'analysis', title: '需求与方案' },
  { id: 'replies', title: '客户回复' },
  { id: 'materials', title: '资料与附件' },
  { id: 'notes', title: '工作笔记' },
  { id: 'history', title: '版本记录' },
];
export function initialCanvas(): CanvasState {
  return {
    schema: 1,
    positions: {},
    tabs: [],
    active: 'canvas',
    folders: [],
    notes: [],
    files: [],
    drafts: {},
  };
}
export function canvasKey(scope: string) {
  return `navowork:inquiry-canvas:${scope}`;
}
export function readCanvas(scope: string): CanvasState {
  const value = localStorage.getItem(canvasKey(scope));
  if (!value) return initialCanvas();
  const state = JSON.parse(value) as CanvasState;
  if (
    state.schema !== 1 ||
    !Array.isArray(state.tabs) ||
    !Array.isArray(state.notes) ||
    !Array.isArray(state.files) ||
    !Array.isArray(state.folders) ||
    !state.positions ||
    !state.drafts ||
    (state.results !== undefined &&
      (!Array.isArray(state.results) ||
        state.results.some(
          (result) =>
            !Number.isInteger(result.revision) ||
            typeof result.title !== 'string' ||
            typeof result.text !== 'string',
        ))) ||
    typeof state.active !== 'string'
  )
    throw new Error('画板草稿格式无法读取');
  return state;
}
export const money = (minor: number | null | undefined) =>
  minor == null
    ? '待确认'
    : `$${(minor / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export function resultSnapshot(
  revision: Revision,
  replies?: Partial<Record<Locale, string>>,
): SavedResult {
  const documents = revisionDocuments(
    { originalText: '', customer: '', currentRevision: revision.number },
    revision,
    [],
    [],
    replies?.['en-US'],
  );
  return {
    revision: revision.number,
    title: `V${revision.number} · 对话成果`,
    text: [
      ...documents
        .filter((doc) => ['requirements', 'risks', 'quote', 'reply'].includes(doc.kind))
        .map((doc) => `## ${doc.title}\n\n${doc.text}`),
      `## Español · México\n\n${replies?.['es-MX'] ?? revision.replies['es-MX']}`,
      `## 资料依据\n\n${revision.sourceRefs.map((ref) => `${ref.title} · V${ref.version}\n${ref.supports.join('、')}`).join('\n\n') || '暂无引用来源'}`,
      `## 内容核对\n\n${revision.checks.map((check) => `${check.status === 'passed' ? '通过' : check.status === 'error' ? '错误' : '待确认'}：${check.label}`).join('\n')}`,
      `规则版本：${revision.ruleSetVersion}`,
      `引用素材：${revision.assetRefs.join('、') || '无'}`,
    ].join('\n\n'),
  };
}
export function revisionDocuments(
  inquiry: Pick<Inquiry, 'originalText' | 'customer' | 'currentRevision' | 'customerContext'>,
  revision: Revision | undefined,
  messages: Message[],
  revisions: Revision[],
  replyText?: string,
): WorkspaceDocument[] {
  const docs: WorkspaceDocument[] = [
    {
      id: 'original',
      title: '客户原始询盘',
      kind: 'original',
      folder: 'inquiry',
      text: `${inquiry.customerContext ? `来源：${channelLabels[inquiry.customerContext.channel]}\n邮箱：${inquiry.customerContext.email || '待补充'}\n\n` : ''}${inquiry.originalText}`,
      caption: `${inquiry.customer}`,
    },
    {
      id: 'conversation',
      title: '沟通与处理记录',
      kind: 'conversation',
      folder: 'inquiry',
      text:
        messages
          .slice(-3)
          .map((m) => `${m.role === 'user' ? '你' : 'Navowork'} · ${m.text}`)
          .join('\n\n') || '从客户原文开始，补充要求并处理这条询盘。',
      caption: `${messages.length} 条记录`,
    },
  ];
  const r = revision;
  if (r) {
    docs.push(
      {
        id: `requirements:${r.number}`,
        title: '客户需求与规格',
        kind: 'requirements',
        folder: 'analysis',
        caption: `V${r.number} · 需求分析`,
        revision: r,
        text: [
          ['产品', r.requirements.requestedProduct],
          ['数量', r.requirements.quantity == null ? null : `${r.requirements.quantity} 件`],
          ['规格', r.requirements.specification],
          ['目的地', r.requirements.destination],
          ['到货要求', r.requirements.requestedArrival],
          ['定制', r.requirements.customization],
        ]
          .map(([k, v]) => `${k}：${v || '待确认'}`)
          .join('\n'),
      },
      {
        id: `risks:${r.number}`,
        title: '风险与待确认项',
        kind: 'risks',
        folder: 'analysis',
        caption: `${r.risks.filter((risk) => risk.status !== 'resolved').length} 项待核对`,
        revision: r,
        text:
          r.risks
            .map(
              (risk) =>
                `${risk.status === 'resolved' ? '✓' : '○'} ${risk.message}\n${risk.suggestedAction}`,
            )
            .join('\n\n') || '当前版本没有风险项。',
      },
      {
        id: `quote:${r.number}`,
        title: '方案与报价草稿',
        kind: 'quote',
        folder: 'analysis',
        caption: `V${r.number} · ${r.proposal.status === 'accepted' ? '已记录接受' : '待确认'}`,
        revision: r,
        text: `当前方案：${r.proposal.selectedSku || '待选择'}\n${r.proposal.differences.join('\n')}${r.quote ? `\n\n数量：${r.quote.quantity} 件\n单价：${money(r.quote.unitPriceMinor)}\n商品小计：${money(r.quote.goodsSubtotalMinor)}\n运费：${money(r.quote.freightMinor)}\n税费：${money(r.quote.taxMinor)}\n总额：${money(r.quote.totalMinor)}` : '\n尚未形成有效报价'}`,
      },
      {
        id: `reply:${r.number}`,
        title: '双语回复草稿',
        kind: 'reply',
        folder: 'replies',
        caption: 'English / Español',
        revision: r,
        text: replyText ?? r.replies['en-US'],
      },
      ...r.sourceRefs.map((s) => ({
        id: `source:${s.sourceVersionId}`,
        title: s.title,
        kind: 'source' as const,
        folder: 'materials',
        caption: `来源 · V${s.version}`,
        text: s.supports.join('\n') || '双击查看固定版本的资料内容',
      })),
    );
  }
  docs.push(
    ...revisions.map((r) => ({
      id: `revision:${r.number}`,
      title: `V${r.number} · ${r.number === inquiry.currentRevision ? '当前版本' : '历史版本'}`,
      kind: 'revision' as const,
      folder: 'history',
      revision: r,
      caption: new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(r.createdAt)),
      text: [
        r.changeSummary.join('\n') || '保存了需求、报价和回复。',
        r.restoredFromRevision
          ? `从 V${r.restoredFromRevision} 恢复${r.restoredNode === 'all' ? '全部节点' : ` ${r.restoredNode} 节点`}；上一个当前版本 V${r.parentRevision}`
          : r.generatedNode
            ? `生成节点：${r.generatedNode}`
            : '',
      ]
        .filter(Boolean)
        .join('\n'),
    })),
  );
  if (!r) {
    for (const [kind, title, folder] of [
      ['requirements', '客户需求与规格', 'analysis'],
      ['risks', '风险与待确认项', 'analysis'],
      ['quote', '方案与报价草稿', 'analysis'],
      ['reply', '双语回复草稿', 'replies'],
    ] as const)
      docs.push({
        id: `${kind}:0`,
        kind,
        title,
        folder,
        text: '',
        caption: '等待生成',
      });
  }
  for (const doc of docs) {
    if (!workflowKinds.includes(doc.kind)) continue;
    doc.hasContent = revisionNodeHasContent(r, doc.kind, replyText);
    if (!doc.hasContent) {
      doc.text = '';
      doc.caption = '等待生成';
    }
  }
  return docs;
}

export function workspaceDocuments({
  inquiry,
  revision,
  revisions,
  messages,
  state,
  replyText,
  sources = {},
  assets = [],
  bundles = [],
}: {
  inquiry: Inquiry;
  revision?: Revision;
  revisions: Revision[];
  messages: Message[];
  state: CanvasState;
  replyText?: string;
  sources?: Record<string, Source>;
  assets?: Asset[];
  bundles?: MaterialBundle[];
}): WorkspaceDocument[] {
  const docs = revisionDocuments(inquiry, revision, messages, revisions, replyText);
  const firstRevision = state.initialRevision ?? inquiry.currentRevision;
  for (const document of revisionDocuments(
    inquiry,
    revisions.find((item) => item.number === firstRevision),
    messages,
    revisions.filter((item) => item.number <= firstRevision),
  )) {
    if (!docs.some((doc) => doc.id === document.id)) docs.push(document);
  }
  docs.push(
    ...(state.results || []).map((result) => ({
      id: `result:${result.revision}`,
      title: result.title,
      kind: 'result' as const,
      folder: 'notes',
      text: result.text,
      caption: `V${result.revision} · 已确认保留`,
      revision: revisions.find((item) => item.number === result.revision),
    })),
  );
  for (const doc of docs) {
    const source =
      doc.kind === 'source' && doc.id.startsWith('source:')
        ? sources[doc.id.slice('source:'.length)]
        : undefined;
    if (source) {
      doc.source = source;
      doc.text = source.content;
    }
  }
  for (const id of revision?.assetRefs || []) {
    const asset = assets.find((item) => `${item.id}:v${item.version}` === id);
    const version = Number(id.match(/:v(\d+)$/)?.[1] || 1);
    const file: WorkspaceFile = {
      id: `asset:${id}`,
      title: asset?.title || id,
      name: asset?.name || id,
      size: asset?.size || 0,
      mediaType: asset?.mediaType || 'application/octet-stream',
      folder: 'materials',
      assetId: asset?.id || id.replace(/:v\d+$/, ''),
      version,
    };
    docs.push({
      id: file.id,
      kind: 'file',
      title: file.title,
      folder: file.folder,
      text: '',
      caption: `已引用 · V${version}`,
      file,
    });
  }
  docs.push(
    ...state.notes.map((note) => ({ ...note, kind: 'note' as const, caption: '工作笔记' })),
    ...state.files.map((file) => ({
      id: file.id,
      title: file.title,
      kind: 'file' as const,
      folder: file.folder,
      text: '',
      caption: '询盘附件',
      file,
    })),
    ...bundles.map((bundle) => ({
      id: `bundle:${bundle.id}`,
      title: `V${bundle.revision} · 材料草稿`,
      kind: 'source' as const,
      folder: 'materials',
      caption: '已整理 · 未发送',
      text: `业务版本 V${bundle.revision}\n英语草稿 V${bundle.draftVersions['en-US'] ?? '—'}\n西语草稿 V${bundle.draftVersions['es-MX'] ?? '—'}\n\n素材：\n${bundle.assetVersionIds.join('\n') || '无'}\n\n资料来源：\n${bundle.sourceVersionIds.join('\n') || '无'}`,
    })),
  );
  for (const doc of docs) {
    if (doc.kind !== 'original' && state.drafts[doc.id] !== undefined) {
      doc.text = state.drafts[doc.id];
      if (workflowKinds.includes(doc.kind)) doc.hasContent = hasMeaningfulText(doc.text);
    }
    if (state.drafts[`title:${doc.id}`]) doc.title = state.drafts[`title:${doc.id}`];
  }
  return docs;
}
async function fileDB() {
  return openDB('navowork-inquiry-files', 1, {
    upgrade(db) {
      db.createObjectStore('files');
    },
  });
}
export async function saveCanvasFile(scope: string, id: string, file: File) {
  const db = await fileDB();
  await db.put('files', file, `${scope}:${id}`);
}
export async function getCanvasFile(scope: string, id: string): Promise<File | undefined> {
  const db = await fileDB();
  return db.get('files', `${scope}:${id}`);
}

import { openDB } from 'idb';
import type { Inquiry, Message, Revision, Source } from '../api/types';

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
  | 'revision';
export interface WorkspaceDocument {
  id: string;
  title: string;
  kind: DocumentKind;
  folder: string;
  text: string;
  caption: string;
  source?: Source;
  file?: WorkspaceFile;
  revision?: Revision;
}
export interface WorkspaceFile {
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
    typeof state.active !== 'string'
  )
    throw new Error('画板草稿格式无法读取');
  return state;
}
export const money = (minor: number | null | undefined) =>
  minor == null
    ? '待确认'
    : `$${(minor / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export function revisionDocuments(
  inquiry: Inquiry,
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
      text: inquiry.originalText,
      caption: inquiry.customer,
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
      text: r.changeSummary.join('\n') || `保存了需求、方案、报价与回复的完整快照。`,
    })),
  );
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

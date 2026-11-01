import { useEffect, useId, useRef, useState, type ReactNode, type CSSProperties } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  History,
  Image,
  LayoutGrid,
  ListTree,
  Mail,
  MessageSquare,
  NotebookPen,
  Paperclip,
  Plus,
  Search,
  ShieldAlert,
  Table2,
  TriangleAlert,
  Upload,
  X,
} from 'lucide-react';
import { api, mode } from '../api';
import type { Asset, Inquiry, MaterialBundle, Message, Revision, Source, WorkbenchData } from '../api/types';
import { ErrorNotice, Loading, Modal } from '../components/ui';
import { CanvasPersistence } from './canvas-persistence';
import { ResizeHandle } from '../components/ResizeHandle';
import { FilePreview, NodeReferenceDocument, OriginalDocument, WorkingDocument } from './InquiryDocument';
import { filterNodeFolders, nodeDirectoryFolders, nodeReferenceDocuments } from './inquiry-node-directory';
import { ConversationResults } from './ConversationResults';
import type { GenerationNode } from './inquiry-generation';
import {
  canvasKey,
  defaultFolders,
  initialCanvas,
  readCanvas,
  progressiveCanvasDocuments,
  revisionDocuments,
  workspaceDocuments,
  inquiryAssetsChangedEvent,
  saveCanvasFile,
  type CanvasState,
  type SavedResult,
  type DocumentKind,
  type WorkspaceDocument,
  type WorkspaceFile,
} from './inquiry-canvas-model';
import '@xyflow/react/dist/style.css';
import './inquiry-canvas.css';

const icons = {
  original: Mail,
  conversation: MessageSquare,
  requirements: ListTree,
  risks: ShieldAlert,
  quote: Table2,
  reply: Mail,
  source: FileText,
  file: Paperclip,
  note: NotebookPen,
  result: FileText,
  revision: History,
};
const kindLabels: Record<DocumentKind, string> = {
  original: '客户原文',
  conversation: '沟通记录',
  requirements: '需求规格',
  risks: '风险清单',
  quote: '方案报价',
  reply: '回复草稿',
  source: '引用资料',
  file: '附件',
  note: '笔记',
  result: '对话成果',
  revision: '版本快照',
};
type PreviewNode = Node<
  {
    doc: WorkspaceDocument;
    base: string;
    scope: string;
    open: (id: string) => void;
    modified: boolean;
    generate?: () => void;
    generating: boolean;
    skipsPending?: boolean;
  },
  'preview'
>;
function PreviewCard({ data, selected }: NodeProps<PreviewNode>) {
  const { doc } = data;
  const Icon =
    doc.kind === 'file' && doc.file?.mediaType.startsWith('image/') ? Image : icons[doc.kind];
  return (
    <article className={`ic-card ic-card-${doc.kind} ${selected ? 'is-selected' : ''}`}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="ic-card-type">
        <span>
          <Icon size={13} />
          {kindLabels[doc.kind]}
        </span>
        <button
          className="nodrag nopan"
          aria-label={`打开 ${doc.title}`}
          title="打开文档"
          onClick={(e) => {
            e.stopPropagation();
            data.open(doc.id);
          }}
        >
          <ArrowUpRight size={14} />
        </button>
      </div>
      <h3>{doc.title}{!!doc.warnings?.length && <span className="ic-node-warning" role="img" aria-label={`${doc.title}有${doc.warnings.length}项待确认`} title={doc.warnings.join('\n')}><TriangleAlert size={16} /></span>}</h3>
      {doc.file ? (
        <FilePreview file={doc.file} base={data.base} scope={data.scope} compact />
      ) : (
        <p
          className={`ic-card-preview ${doc.kind === 'original' || doc.kind === 'reply' ? 'ic-card-letter' : ''}`}
        >
          {doc.text}
        </p>
      )}
      <footer>
        <span>{data.modified ? (mode === 'real' ? '工作草稿' : '本机工作草稿') : doc.caption}</span>
        <span>双击打开</span>
      </footer>
      {data.generate && (
        <button
          className="button ic-node-generate nodrag nopan"
          disabled={data.generating}
          onClick={(e) => {
            e.stopPropagation();
            data.generate?.();
          }}
        >
          {data.skipsPending ? '跳过缺项并生成' : '依据现有资料生成'}
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </article>
  );
}
const nodeTypes = { preview: PreviewCard };
const edgeOptions = {
  type: 'smoothstep',
  style: { stroke: 'var(--navo-color-border-strong, #cbd2dd)', strokeWidth: 1.3 },
  selectable: false,
  deletable: false,
};

function CanvasHelp() {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  return (
    <div
      className="ic-canvas-help"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false);
      }}
    >
      <button
        type="button"
        className="ic-icon"
        aria-label="画板操作说明"
        aria-describedby={open ? tooltipId : undefined}
        onClick={() => setOpen(true)}
      >
        <CircleHelp size={16} />
      </button>
      {open && (
        <div className="ic-canvas-tooltip" id={tooltipId} role="tooltip">
          单击预览 · 双击打开 · 各轮成果统一查看
        </div>
      )}
    </div>
  );
}

interface Props {
  serverState?: CanvasState;
  persist?: (state: CanvasState) => void;
  inquiry: Inquiry;
  revision?: Revision;
  revisions: Revision[];
  messages: Message[];
  scope: string;
  base: string;
  path: string;
  readOnly: boolean;
  generationDisabled?: boolean;
  conversation: ReactNode;
  replyEditor: ReactNode;
  replyText?: string;
  openRequest: { id: string; seq: number } | null;
  saveResultRequest: { result: SavedResult; seq: number } | null;
  onSavedResultsChange: (revisions: number[]) => void;
  onOriginalSaved: () => Promise<void>;
  onInstruction: (text: string) => void;
  onOpenChat: () => void;
  onRevision: (number: number) => void;
  onGenerate?: (node: GenerationNode, text?: string) => void;
  onRestore?: (number: number, target: string) => Promise<number | undefined>;
  canRestore?: boolean;
}
export function InquiryCanvas(props: Props) {
  return (
    <ReactFlowProvider key={props.scope}>
      {mode === 'real' ? (
        <ServerCanvas key={props.scope} {...props} />
      ) : (
        <CanvasWorkspace key={props.scope} {...props} />
      )}
    </ReactFlowProvider>
  );
}
function ServerCanvas(props: Props) {
  const [writer] = useState(() => new CanvasPersistence(`${props.path}/canvas`));
  const [loaded, setLoaded] = useState<CanvasState>();
  const [error, setError] = useState<unknown>();
  const [status, setStatus] = useState('');
  const [retry, setRetry] = useState(0);
  const savedCallback = useRef(props.onSavedResultsChange);
  savedCallback.current = props.onSavedResultsChange;
  useEffect(() => {
    let live = true;
    writer.onStatus = (value) => {
      if (live) setStatus(value);
    };
    writer.onSaved = (state) => {
      window.dispatchEvent(new CustomEvent(inquiryAssetsChangedEvent, { detail: props.scope }));
      if (live) savedCallback.current((state.results || []).map((r) => r.revision));
    };
    setError(undefined);
    api
      .get<{ editVersion: number; state: CanvasState | null }>(writer.path)
      .then((result) => {
        if (!live) return;
        const state = result.state || {
          ...initialCanvas(),
          initialRevision: props.inquiry.currentRevision,
        };
        writer.initialize(result.editVersion, state);
        setLoaded(state);
        writer.onSaved(state);
        setStatus('已与服务端同步');
      })
      .catch((e) => {
        if (live) setError(e);
      });
    const leaving = (event: BeforeUnloadEvent) => {
      if (writer.pending || writer.saving) {
        event.preventDefault();
        event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', leaving);
    return () => {
      live = false;
      window.removeEventListener('beforeunload', leaving);
      void writer.flush();
    };
  }, [writer, retry]);
  if (error) return <ErrorNotice error={error} onRetry={() => setRetry((v) => v + 1)} />;
  if (!loaded) return <Loading label="正在恢复服务端画板" />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, minWidth: 0 }}>
      {writer.error != null && (
        <div role="alert" style={{ padding: '4px 12px', fontSize: 12 }}>
          {status}
          <button className="button button-ghost" onClick={() => writer.retry()}>
            重试保存
          </button>
          <button
            className="button button-ghost"
            onClick={() => {
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(writer.pending, null, 2)], { type: 'application/json' }),
              );
              const link = document.createElement('a');
              link.href = url;
              link.download = 'canvas-recovery.json';
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}
          >
            下载当前草稿
          </button>
        </div>
      )}
      <CanvasWorkspace {...props} serverState={loaded} persist={(state) => writer.enqueue(state)} />
    </div>
  );
}
function CanvasWorkspace({
  serverState,
  persist,
  inquiry,
  revision,
  revisions,
  messages,
  scope,
  base,
  path,
  readOnly,
  generationDisabled,
  conversation,
  replyEditor,
  replyText,
  openRequest,
  saveResultRequest,
  onSavedResultsChange,
  onOriginalSaved,
  onInstruction,
  onOpenChat,
  onRevision,
  onGenerate,
  onRestore,
  canRestore,
}: Props) {
  const [initial] = useState(() => {
    try {
      const saved = serverState || readCanvas(scope);
      const alias = (id: string) => (id.startsWith('result:') ? 'result:hub' : id);
      return {
        state: {
          ...saved,
          tabs: [...new Set(saved.tabs.map(alias))],
          active: alias(saved.active),
          initialRevision: saved.initialRevision ?? inquiry.currentRevision,
        },
        error: '',
      };
    } catch {
      return {
        state: { ...initialCanvas(), initialRevision: inquiry.currentRevision },
        error: '本机画板草稿无法读取，原存储已保留。当前更改暂不保存。',
      };
    }
  });
  const [state, setState] = useState<CanvasState>(initial.state);
  const [storageError, setStorageError] = useState(initial.error);
  const [error, setError] = useState<unknown>();
  const [search, setSearch] = useState('');
  const [directoryOpen, setDirectoryOpen] = useState(
    () => window.matchMedia('(min-width: 601px)').matches,
  );
  const [collapsed, setCollapsed] = useState<string[]>(['history', 'records']);
  const [selected, setSelected] = useState('');
  const [folderModal, setFolderModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const layoutRef = useRef<HTMLDivElement>(null);
  const directoryRef = useRef<HTMLElement>(null);
  const directoryToggleRef = useRef<HTMLButtonElement>(null);
  const measurements = useRef<Record<string, { width: number; height: number }>>({});
  const flow = useReactFlow<PreviewNode>();
  useEffect(() => {
    if (mode === 'real') return;
    onSavedResultsChange((state.results || []).map((result) => result.revision));
  }, [state.results, onSavedResultsChange]);
  const sourceRefs = revision?.sourceRefs ?? [];
  const sources = useQueries({
    queries: sourceRefs.map((source) => ({
      queryKey: ['canvas-source', scope, source.sourceVersionId],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.get<Source>(
          `${base}/sources/${encodeURIComponent(source.sourceId)}/versions/${source.version}`,
          signal,
        ),
    })),
  });
  const assetIds = revision?.assetRefs ?? [];
  const nodeSources = useQuery({
    queryKey: ['inquiry', scope, 'node-sources', inquiry.currentRevision, inquiry.updatedAt],
    queryFn: ({ signal }) => api.get<WorkbenchData>(`${path}/workbench`, signal),
    enabled: mode === 'real',
  });
  const assets = useQuery({
    queryKey: ['assets-for-inquiry', scope],
    queryFn: ({ signal }) => api.get<{ items: Asset[] }>(`${base}/assets`, signal),
    enabled: assetIds.length > 0,
  });
  const bundles = useQuery({
    queryKey: ['materials', scope],
    queryFn: ({ signal }) =>
      api.get<{ items: MaterialBundle[] }>(`${path}/material-bundles`, signal),
  });
  useEffect(() => {
    if (persist) {
      persist(state);
      return;
    }
    if (initial.error) return;
    try {
      localStorage.setItem(canvasKey(scope), JSON.stringify(state));
      setStorageError('');
    } catch {
      setStorageError('本机空间不足或存储不可用，当前修改尚未保存。请保留此页并导出笔记。');
    }
  }, [state, scope, initial.error]);
  const docs = workspaceDocuments({
    inquiry,
    revision,
    revisions,
    messages,
    state,
    replyText,
    sources: Object.fromEntries(
      sourceRefs.flatMap((ref, index) =>
        sources[index]?.data ? [[ref.sourceVersionId, sources[index].data!]] : [],
      ),
    ),
    assets: assets.data?.items,
    bundles: bundles.data?.items,
  });
  docs.push({
    id: 'result:hub',
    title: '对话成果汇总',
    kind: 'result',
    folder: 'analysis',
    text: `已保存 ${revisions.length} 个业务版本。统一查看每轮需求、报价、回复与来源；历史恢复请到版本记录。`,
    caption: '统一成果入口',
  });
  for (const doc of nodeReferenceDocuments(nodeSources.data)) {
    const existing = docs.find((item) => item.id === doc.id);
    if (existing) existing.reference = doc.reference;
    else docs.push(doc);
  }
  useEffect(() => {
    if (mode !== 'real') return;
    const remap = (id: string) =>
      /^(requirements|risks|quote|reply):\d+$/.test(id)
        ? `${id.split(':')[0]}:${revision?.number || 0}`
        : id;
    setState((s) => ({ ...s, tabs: [...new Set(s.tabs.map(remap))], active: remap(s.active) }));
  }, [revision?.number]);
  const assetSyncSignature = JSON.stringify({
    title: inquiry.title,
    updatedAt: inquiry.updatedAt,
    documents: docs.map(({ id, title, text, file, folder }) => ({ id, title, text, file, folder })),
    folders: state.folders,
  });
  useEffect(() => {
    window.dispatchEvent(new CustomEvent(inquiryAssetsChangedEvent, { detail: scope }));
  }, [scope, assetSyncSignature]);
  const folders = [...defaultFolders, ...state.folders];
  const tabs = state.tabs.filter((id) => docs.some((d) => d.id === id));
  const active = state.active === 'canvas' || tabs.includes(state.active) ? state.active : 'canvas';
  const activeDoc = docs.find((d) => d.id === active);
  function open(id: string) {
    if (id.startsWith('result:')) id = 'result:hub';
    const doc = docs.find((document) => document.id === id);
    if (doc?.kind === 'reply' && doc.revision?.number !== revision?.number)
      onRevision(doc.revision!.number);
    setState((s) => ({ ...s, active: id, tabs: s.tabs.includes(id) ? s.tabs : [...s.tabs, id] }));
  }
  async function restore(number: number, target: string) {
    const nextNumber = await onRestore?.(number, target);
    if (!nextNumber) return;
    setState((s) => {
      const drafts = { ...s.drafts };
      const kinds = target === 'all' ? ['requirements', 'risks', 'quote'] : [target];
      for (const kind of kinds) {
        const oldId = `${kind}:${number}`;
        if (drafts[oldId] !== undefined) drafts[`${kind}:${nextNumber}`] = drafts[oldId];
      }
      const id = target === 'all' ? 'canvas' : `${target}:${nextNumber}`;
      return {
        ...s,
        drafts,
        active: id,
        tabs: id === 'canvas' ? s.tabs : [...new Set([...s.tabs, id])],
      };
    });
  }
  useEffect(() => {
    if (openRequest) open(openRequest.id);
  }, [openRequest]);
  function close(id: string) {
    setState((s) => {
      const next = s.tabs.filter((t) => t !== id);
      return {
        ...s,
        tabs: next,
        active: s.active === id ? next[Math.max(0, s.tabs.indexOf(id) - 1)] || 'canvas' : s.active,
      };
    });
  }
  function draft(id: string, value?: string) {
    setState((s) => {
      const drafts = { ...s.drafts };
      if (value === undefined) delete drafts[id];
      else drafts[id] = value;
      return { ...s, drafts };
    });
  }
  function addNote() {
    if (readOnly) return;
    const note = {
      id: `note:${crypto.randomUUID()}`,
      title: '未命名笔记',
      text: '',
      folder: 'notes',
    };
    setState((s) => ({
      ...s,
      notes: [...s.notes, note],
      tabs: [...s.tabs, note.id],
      active: note.id,
    }));
  }
  async function importFiles(files: FileList | null) {
    if (!files?.length || readOnly || uploading) return;
    setUploading(true);
    setError(undefined);
    try {
      for (const file of Array.from(files)) {
        if (file.size > 20 * 1024 * 1024)
          throw new Error(`${file.name} 超过 20 MB，请选择更小的文件。`);
        const entry: WorkspaceFile = {
          id: `file:${crypto.randomUUID()}`,
          name: file.name,
          title: file.name,
          mediaType:
            file.type ||
            (/\.(txt|md|csv)$/i.test(file.name) ? 'text/plain' : 'application/octet-stream'),
          size: file.size,
          folder: 'materials',
        };
        if (mode === 'real') {
          const form = new FormData();
          form.set('file', file);
          const uploaded = await api.post<WorkspaceFile>(`${path}/canvas/files`, form);
          setState((s) => ({ ...s, files: [...s.files, uploaded] }));
        } else {
          await saveCanvasFile(scope, entry.id, file);
          setState((s) => ({ ...s, files: [...s.files, entry] }));
        }
      }
      setState((s) => ({ ...s, active: 'canvas' }));
    } catch (e) {
      setError(e);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }
  // Put the main working documents first; supporting files continue below them.
  const initialIds = new Set(
    revisionDocuments(
      inquiry,
      revisions.find((item) => item.number === state.initialRevision),
      messages,
      revisions.filter((item) => item.number <= (state.initialRevision || 0)),
    ).map((doc) => doc.id),
  );
  const candidates = docs
    .filter((doc) => !doc.directoryOnly)
    .filter((doc, index, visible) =>
      mode === 'real'
        ? doc.kind !== 'revision' &&
          visible.findIndex((d) => d.id === doc.id) === index &&
          (!['requirements', 'risks', 'quote', 'reply'].includes(doc.kind) ||
            doc.id.endsWith(`:${revision?.number || 0}`)) &&
          (doc.kind !== 'result' || doc.id === 'result:hub')
        : initialIds.has(doc.id) ||
          ['file', 'note', 'result'].includes(doc.kind) ||
          doc.id.startsWith('bundle:') ||
          state.positions[doc.id] !== undefined,
    )
    .sort((a, b) => {
      const rank = (kind: DocumentKind) =>
        ({
          original: 0,
          requirements: 1,
          quote: 2,
          conversation: 3,
          risks: 4,
          reply: 5,
          source: 6,
          file: 7,
          note: 8,
          result: 9,
          revision: 10,
        })[kind];
      return rank(a.kind) - rank(b.kind);
    });
  const ordered = progressiveCanvasDocuments(candidates, Boolean(state.results?.length));
  const directoryFolders = nodeDirectoryFolders(ordered, docs, nodeSources.data);
  const visibleFolders = filterNodeFolders(directoryFolders, search);
  const directoryCount = new Set(directoryFolders.flatMap((folder) => folder.items.map(({ doc }) => doc.id))).size;
  const occupied = ordered.flatMap((doc) =>
    state.positions[doc.id] ? [state.positions[doc.id]] : [],
  );
  function defaultPosition() {
    let index = 0;
    let position = { x: 0, y: 68 };
    while (
      occupied.some((p) => Math.abs(p.x - position.x) < 320 && Math.abs(p.y - position.y) < 290)
    ) {
      index += 1;
      position = { x: (index % 3) * 350, y: Math.floor(index / 3) * 320 + 68 };
    }
    occupied.push(position);
    return position;
  }
  const nodes: PreviewNode[] = ordered.map((doc) => ({
    id: doc.id,
    type: 'preview',
    initialWidth: 300,
    initialHeight: 275,
    measured: measurements.current[doc.id],
    position: state.positions[doc.id] || defaultPosition(),
    selected: selected === doc.id,
    data: {
      doc,
      base,
      scope,
      open,
      modified: state.drafts[doc.id] !== undefined,
      generating: readOnly || !!generationDisabled,
      skipsPending: !!inquiry.pendingRunId,
      generate:
        onGenerate && ['requirements', 'risks', 'quote', 'reply'].includes(doc.kind)
          ? () => onGenerate(doc.kind as GenerationNode)
          : undefined,
    },
    ariaLabel: `${doc.title}，预览节点，双击打开`,
  }));
  const edges: Edge[] = [];
  {
    const n = revision?.number || 0;
    const pairs = [
      ['original', `requirements:${n}`],
      [`requirements:${n}`, `quote:${n}`],
      [`quote:${n}`, `reply:${n}`],
      [`requirements:${n}`, `risks:${n}`],
    ];
    for (const [source, target] of pairs)
      if (nodes.some((node) => node.id === source) && nodes.some((node) => node.id === target))
        edges.push({ id: `${source}-${target}`, source, target, ...edgeOptions });
  }
  useEffect(() => {
    if (!saveResultRequest || readOnly) return;
    try {
      if (initial.error) throw new Error(initial.error);
      const result = saveResultRequest.result;
      const id = 'result:hub';
      const position = state.positions[id] || {
        x: Math.max(0, ...nodes.map((node) => node.position.x)) + 350,
        y: 68,
      };
      const next: CanvasState = {
        ...state,
        active: id,
        tabs: [...new Set([...state.tabs, id])],
        results: state.results?.some((saved) => saved.revision === result.revision)
          ? state.results
          : [...(state.results || []), result],
        positions: { ...state.positions, [id]: position },
      };
      if (mode === 'mock') localStorage.setItem(canvasKey(scope), JSON.stringify(next));
      setState(next);
      setSelected(id);
      setError(undefined);
      void flow.setCenter(position.x + 150, position.y + 118, { zoom: 0.9, duration: 300 });
    } catch {
      setError('成果节点未能保存，请恢复浏览器存储后重试。对话内容已保留。');
    }
  }, [saveResultRequest]);
  function focus(doc: WorkspaceDocument) {
    const node = nodes.find((n) => n.id === doc.id);
    if (!node) {
      open(doc.id);
      return;
    }
    setSelected(doc.id);
    setState((s) => ({ ...s, active: 'canvas' }));
    const pos = node.position;
    void flow.setCenter(pos.x + 151, pos.y + 116, { zoom: 0.9, duration: 300 });
  }
  const tabIds = ['canvas', ...tabs];
  function tabKey(event: React.KeyboardEvent, index: number) {
    let next: number;
    if (event.key === 'ArrowRight') next = (index + 1) % tabIds.length;
    else if (event.key === 'ArrowLeft') next = (index + tabIds.length - 1) % tabIds.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabIds.length - 1;
    else return;
    event.preventDefault();
    setState((s) => ({ ...s, active: tabIds[next] }));
    document.getElementById(`ic-tab-${scope}-${tabIds[next]}`)?.focus();
  }
  function exportNote(doc: WorkspaceDocument) {
    const url = URL.createObjectURL(
      new Blob([`# ${doc.title}\n\n${doc.text}`], { type: 'text/markdown;charset=utf-8' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = `${doc.title}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const sourceError =
    activeDoc?.kind === 'source'
      ? sources[sourceRefs.findIndex((ref) => `source:${ref.sourceVersionId}` === activeDoc.id)]
      : undefined;
  return (
    <div className="ic-workspace">
      <div className="ic-toolbar">
        <button
          ref={directoryToggleRef}
          className={`ic-icon ${directoryOpen ? 'is-active' : ''}`}
          aria-label={directoryOpen ? '收起文件目录' : '展开文件目录'}
          aria-expanded={directoryOpen}
          onClick={() => setDirectoryOpen((v) => !v)}
          title="文件目录"
        >
          <ListTree size={16} />
        </button>
        <span className="ic-toolbar-title">询盘资料</span>
        <span className="ic-count">{directoryCount}</span>
        <div className="ic-toolbar-spacer" />
        <button
          className="ic-icon"
          aria-label="打开沟通记录"
          title="沟通与处理记录"
          onClick={onOpenChat}
        >
          <MessageSquare size={15} />
        </button>
        <details className="ic-add-menu">
          <summary aria-label="新建资料" title="新建资料">
            <Plus size={17} />
          </summary>
          <div>
            <button
              disabled={readOnly}
              onClick={(e) => {
                addNote();
                e.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              <NotebookPen size={14} />
              新建笔记
            </button>
            <button
              disabled={readOnly}
              onClick={(e) => {
                setFolderModal(true);
                e.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              <FolderPlus size={14} />
              新建文件夹
            </button>
            <button
              disabled={readOnly || uploading}
              onClick={(e) => {
                fileInput.current?.click();
                e.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              <Upload size={14} />
              {uploading ? '导入中…' : '导入文件'}
            </button>
          </div>
        </details>
        <input
          ref={fileInput}
          hidden
          type="file"
          multiple
          aria-label="导入询盘文件"
          accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.md,.csv,.xlsx,.docx"
          onChange={(e) => void importFiles(e.target.files)}
        />
      </div>
      {storageError && (
        <div role="alert" className="ic-storage-error">
          {storageError}
        </div>
      )}
      <ErrorNotice error={error || assets.error || bundles.error} />
      <div
        ref={layoutRef}
        className="ic-layout"
        style={
          {
            '--ic-directory-width':
              typeof state.directoryWidth === 'number' && Number.isFinite(state.directoryWidth)
                ? `${state.directoryWidth}px`
                : undefined,
          } as CSSProperties
        }
      >
        {directoryOpen && (
          <aside
            ref={directoryRef}
            id={`directory-${inquiry.id}`}
            className="ic-directory"
            aria-label="当前询盘文件目录"
          >
            <label className="ic-search">
              <Search size={13} />
              <input
                value={search}
                aria-label="搜索当前询盘资料"
                placeholder="搜索资料…"
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <div className="ic-directory-root">
              <FolderOpen size={14} />
              <span>当前询盘</span>
            </div>
            <div className="ic-folder-list">
              {visibleFolders.map((folder) => {
                const closed = !search && collapsed.includes(folder.id);
                return (
                  <div className="ic-folder" key={folder.id} data-node-id={folder.node?.id}>
                    <button
                      className="ic-folder-toggle"
                      aria-label={`${folder.title}文件夹`}
                      aria-expanded={!closed}
                      title={folder.title}
                      onClick={() => {
                        setCollapsed((s) => s.includes(folder.id)
                          ? s.filter((v) => v !== folder.id) : [...s, folder.id]);
                        if (closed && folder.node && active === 'canvas') focus(folder.node);
                      }}
                    >
                      {closed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                      {closed ? <Folder size={14} /> : <FolderOpen size={14} />}
                      <span>{folder.title}</span>
                      {!!folder.node?.warnings?.length && <TriangleAlert size={13} className="ic-node-warning" aria-label="存在待确认项" />}
                      <small>{folder.items.length}</small>
                    </button>
                    {!closed && (
                      <div className="ic-folder-items">
                        {folder.items.map(({ doc, title }) => (
                          <button
                            key={doc.id}
                            aria-label={title}
                            className={active === doc.id ? 'is-selected' : ''}
                            title={`${title} · 点击打开`}
                            onClick={() => open(doc.id)}
                          >
                            <FileText size={14} />
                            <span>{title}</span>
                            {state.drafts[doc.id] !== undefined && <i aria-label="有工作草稿" />}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {search && !visibleFolders.length && <p className="ic-no-match">没有找到相关资料</p>}
              {nodeSources.error && <ErrorNotice error={nodeSources.error} onRetry={() => void nodeSources.refetch()} />}
            </div>
            <div className="ic-directory-footer">
              <span className="ic-scope-dot" />
              仅当前询盘
            </div>
          </aside>
        )}
        {directoryOpen && (
          <ResizeHandle
            label="调整文件目录宽度"
            controls={`directory-${inquiry.id}`}
            paneRef={directoryRef}
            containerRef={layoutRef}
            min={140}
            max={360}
            remainingMin={220}
            onResize={(width) => setState((s) => ({ ...s, directoryWidth: width }))}
            onReset={() => setState((s) => ({ ...s, directoryWidth: undefined }))}
            onCollapse={(width) => {
              setState((s) => ({ ...s, directoryWidth: width }));
              setDirectoryOpen(false);
              directoryToggleRef.current?.focus({ preventScroll: true });
            }}
            className="ic-directory-resizer"
          />
        )}
        <div className="ic-main">
          <div className="ic-tabs" role="tablist" aria-label="询盘资料标签页">
            {tabIds.map((id, index) => {
              const doc = docs.find((d) => d.id === id);
              const Icon = doc ? icons[doc.kind] : LayoutGrid;
              return (
                <div key={id} className={`ic-tab-wrap ${active === id ? 'is-active' : ''}`}>
                  <button
                    role="tab"
                    id={`ic-tab-${scope}-${id}`}
                    aria-controls={`ic-panel-${scope}-${id}`}
                    aria-selected={active === id}
                    tabIndex={active === id ? 0 : -1}
                    onClick={() => setState((s) => ({ ...s, active: id }))}
                    onKeyDown={(e) => tabKey(e, index)}
                  >
                    <Icon size={13} />
                    <span>{doc?.title || '询盘画板'}</span>
                  </button>
                  {id !== 'canvas' && (
                    <button
                      className="ic-tab-close"
                      aria-label={`关闭资料标签 ${doc?.title}`}
                      onClick={() => close(id)}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          <div
            className="ic-board"
            role="tabpanel"
            id={`ic-panel-${scope}-canvas`}
            aria-labelledby={`ic-tab-${scope}-canvas`}
            hidden={active !== 'canvas'}
          >
            <ReactFlow<PreviewNode>
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView={!state.viewport}
              fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
              defaultViewport={state.viewport || { x: 30, y: 16, zoom: 0.78 }}
              minZoom={0.15}
              maxZoom={1.75}
              zoomOnDoubleClick={false}
              autoPanOnNodeFocus={false}
              nodesConnectable={false}
              edgesFocusable={false}
              deleteKeyCode={null}
              onNodeDoubleClick={(_, node) => open(node.id)}
              onNodeClick={(_, node) => setSelected(node.id)}
              onPaneClick={() => setSelected('')}
              onNodesChange={(changes) => {
                for (const change of changes) {
                  if (change.type === 'dimensions' && change.dimensions)
                    measurements.current[change.id] = change.dimensions;
                }
                const positions = changes.filter((c) => c.type === 'position' && c.position);
                if (positions.length)
                  setState((s) => ({
                    ...s,
                    positions: {
                      ...s.positions,
                      ...Object.fromEntries(
                        positions.map((c) => (c.type === 'position' ? [c.id, c.position] : [])),
                      ),
                    },
                  }));
              }}
              onMoveEnd={(_, viewport) => setState((s) => ({ ...s, viewport }))}
              proOptions={{ hideAttribution: false }}
              aria-label="当前询盘无限画板"
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={22}
                size={1}
                color="var(--ic-dot)"
              />
              <Panel position="top-right" className="ic-board-tools">
                <button
                  className="ic-arrange"
                  onClick={() => {
                    setState((s) => ({ ...s, positions: {} }));
                    requestAnimationFrame(() => {
                      void flow.fitView({ padding: 0.12, duration: 300 });
                    });
                  }}
                >
                  <LayoutGrid size={12} />
                  整理画板
                </button>
                <CanvasHelp />
              </Panel>
              <Controls showInteractive={false} aria-label="画板缩放工具" />
              <MiniMap
                style={{ width: 110, height: 70 }}
                pannable
                zoomable
                nodeBorderRadius={5}
                nodeColor="var(--ic-minimap-node)"
                maskColor="var(--ic-minimap-mask)"
                ariaLabel="询盘画板小地图"
              />
            </ReactFlow>
          </div>
          <div
            className="ic-document-panel ic-conversation-panel"
            role="tabpanel"
            id={`ic-panel-${scope}-conversation`}
            aria-labelledby={`ic-tab-${scope}-conversation`}
            hidden={active !== 'conversation'}
          >
            {conversation}
          </div>
          <div
            className="ic-document-panel ic-reply-panel"
            role="tabpanel"
            id={`ic-panel-${scope}-reply:${revision?.number || 0}`}
            aria-labelledby={`ic-tab-${scope}-reply:${revision?.number || 0}`}
            hidden={active !== `reply:${revision?.number || 0}`}
          >
            <div className="ic-document-actions">
              {onGenerate && (
                <button
                  className="button button-primary"
                  disabled={readOnly}
                  onClick={() => onGenerate('reply')}
                >
                  依据现有资料生成
                </button>
              )}
              {canRestore && revision && revision.number !== inquiry.currentRevision && (
                <button className="button" onClick={() => void restore(revision.number, 'reply')}>
                  恢复此节点为新版本
                </button>
              )}
            </div>
            {replyEditor}
          </div>
          {tabs
            .filter((id) => id !== 'conversation' && !id.startsWith('reply:'))
            .map((id) => {
              const doc = docs.find((d) => d.id === id)!;
              const original = revisionDocuments(
                inquiry,
                doc.revision || revision,
                messages,
                revisions,
                replyText,
              ).find((d) => d.id === id);
              return (
                <div
                  className="ic-document-panel"
                  key={id}
                  role="tabpanel"
                  id={`ic-panel-${scope}-${id}`}
                  aria-labelledby={`ic-tab-${scope}-${id}`}
                  hidden={active !== id}
                >
                  {!!doc.warnings?.length && <details className="ic-missing-warning">
                    <summary><TriangleAlert size={15} />{doc.warnings.length} 项待确认{doc.skippedMissing ? ' · 已暂时跳过' : ''}</summary>
                    <ul>{doc.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                  </details>}
                  {doc.kind === 'original' ? (
                    <OriginalDocument
                      inquiry={inquiry}
                      path={path}
                      readOnly={readOnly}
                      value={state.drafts[id] ?? inquiry.originalText}
                      onChange={(value) => draft(id, value)}
                      onSaved={onOriginalSaved}
                    />
                  ) : ['requirements', 'risks', 'quote'].includes(doc.kind) ? (
                    <WorkingDocument
                      doc={original!}
                      value={doc.text}
                      readOnly={readOnly}
                      onChange={(value) => draft(id, value)}
                      onInstruction={onInstruction}
                      onGenerate={
                        onGenerate
                          ? (text) => onGenerate(doc.kind as GenerationNode, text)
                          : undefined
                      }
                      onRestore={
                        canRestore &&
                        doc.revision &&
                        doc.revision.number !== inquiry.currentRevision
                          ? () => void restore(doc.revision!.number, doc.kind)
                          : undefined
                      }
                    />
                  ) : doc.evidenceId || doc.reference ? (
                    <NodeReferenceDocument doc={doc} path={path} base={base} />
                  ) : doc.kind === 'note' ? (
                    <div className="ic-document-sheet">
                      <div className="ic-document-eyebrow">WORKING NOTES</div>
                      <input
                        className="ic-note-title"
                        aria-label="笔记标题"
                        value={doc.title}
                        disabled={readOnly}
                        onChange={(e) =>
                          setState((s) => ({
                            ...s,
                            notes: s.notes.map((n) =>
                              n.id === id ? { ...n, title: e.target.value } : n,
                            ),
                          }))
                        }
                      />
                      <div className="ic-document-status">
                        <Check size={13} />
                        {storageError
                          ? '本机保存不可用'
                          : mode === 'real'
                            ? '工作笔记 · 自动保存'
                            : '本机笔记 · 自动保存'}
                      </div>
                      <label className="ic-folder-select">
                        所在文件夹
                        <select
                          aria-label="笔记所在文件夹"
                          value={doc.folder}
                          disabled={readOnly}
                          onChange={(e) =>
                            setState((s) => ({
                              ...s,
                              notes: s.notes.map((n) =>
                                n.id === id ? { ...n, folder: e.target.value } : n,
                              ),
                            }))
                          }
                        >
                          {folders.map((f) => (
                            <option key={f.id} value={f.id}>
                              {f.title}
                            </option>
                          ))}
                        </select>
                      </label>
                      <textarea
                        className="ic-document-text"
                        aria-label="编辑工作笔记"
                        placeholder="记录客户偏好、跟进事项或你的想法…"
                        value={doc.text}
                        readOnly={readOnly}
                        onChange={(e) =>
                          setState((s) => ({
                            ...s,
                            notes: s.notes.map((n) =>
                              n.id === id ? { ...n, text: e.target.value } : n,
                            ),
                          }))
                        }
                      />
                      <div className="ic-document-actions">
                        <span>只属于当前询盘</span>
                        <button className="button" onClick={() => exportNote(doc)}>
                          导出 Markdown
                        </button>
                      </div>
                    </div>
                  ) : doc.kind === 'file' && doc.file ? (
                    <div className="ic-document-sheet">
                      <div className="ic-document-eyebrow">INQUIRY ATTACHMENT</div>
                      <h2>{doc.title}</h2>
                      <p className="ic-document-subtitle">
                        {doc.file.name} · {Math.ceil(doc.file.size / 1024)} KB ·{' '}
                        {doc.file.assetId
                          ? `引用 V${doc.file.version}`
                          : mode === 'real'
                            ? '询盘附件'
                            : '本机附件'}
                      </p>
                      <label className="ic-file-alias">
                        显示名称
                        <input
                          aria-label="附件显示名称"
                          value={state.drafts[`title:${id}`] ?? doc.file.title}
                          disabled={readOnly}
                          onChange={(e) => draft(`title:${id}`, e.target.value)}
                        />
                      </label>
                      <FilePreview file={doc.file} base={base} scope={scope} />
                    </div>
                  ) : doc.kind === 'result' ? (
                    <ConversationResults
                      path={path}
                      revisions={revisions}
                      saved={state.results || []}
                      onRevision={onRevision}
                    />
                  ) : doc.kind === 'revision' ? (
                    <div className="ic-document-sheet">
                      <div className="ic-document-eyebrow">VERSION HISTORY</div>
                      <h2>{doc.title}</h2>
                      <p className="ic-document-subtitle">{doc.caption} · 版本快照只读</p>
                      <pre className="ic-source-content">{doc.text}</pre>
                      {doc.revision && (
                        <button className="button" onClick={() => onRevision(doc.revision!.number)}>
                          <History size={14} />
                          在对话中查看此版本
                        </button>
                      )}
                      {canRestore && doc.revision && (
                        <div className="ic-history-restore">
                          <p>
                            复制旧内容为新的当前草稿，保留全部历史。恢复的业务成果需要重新审核。
                          </p>
                          <button
                            className="button button-primary"
                            onClick={() => void restore(doc.revision!.number, 'all')}
                          >
                            从此版本继续编辑
                          </button>
                          <div className="ic-document-actions">
                            {(['requirements', 'risks', 'quote', 'reply'] as const).map((kind) => (
                              <button
                                className="button"
                                key={kind}
                                onClick={() => void restore(doc.revision!.number, kind)}
                              >
                                仅恢复
                                {
                                  {
                                    requirements: '需求',
                                    risks: '风险',
                                    quote: '报价',
                                    reply: '回复',
                                  }[kind]
                                }
                                节点
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="ic-document-sheet">
                      <div className="ic-document-eyebrow">REFERENCE MATERIAL</div>
                      <h2>{doc.title}</h2>
                      <p className="ic-document-subtitle">{doc.caption} · 固定版本资料</p>
                      {sourceError?.error && (
                        <ErrorNotice
                          error={sourceError.error}
                          onRetry={() => void sourceError.refetch()}
                        />
                      )}
                      <pre className="ic-source-content">{doc.text}</pre>
                      <label className="ic-reference-note">
                        资料备注
                        <textarea
                          aria-label={`编辑${doc.title}备注`}
                          value={state.drafts[`annotation:${id}`] || ''}
                          placeholder="添加当前询盘的资料备注…"
                          readOnly={readOnly}
                          onChange={(e) => draft(`annotation:${id}`, e.target.value)}
                        />
                      </label>
                    </div>
                  )}
                </div>
              );
            })}
          <div className="ic-statusbar">
            <span>
              {active === 'canvas' ? (
                <>
                  <span className="ic-scope-dot" />
                  {nodes.length} 个画布节点 · {revisions.length} 个历史版本
                </>
              ) : (
                <>
                  <FileText size={11} />
                  {activeDoc?.title || '询盘资料'}
                </>
              )}
            </span>
            <span>
              {uploading
                ? '正在导入文件…'
                : active === 'canvas'
                  ? '拖动画布移动 · 滚轮缩放'
                  : readOnly
                    ? '当前只读'
                    : '在标签页内编辑'}
            </span>
          </div>
        </div>
      </div>
      {folderModal && (
        <Modal title="新建询盘文件夹" onClose={() => setFolderModal(false)}>
          <form
            className="iw-form"
            onSubmit={(e) => {
              e.preventDefault();
              const title = String(new FormData(e.currentTarget).get('title') || '').trim();
              if (!title || readOnly) return;
              setState((s) => ({
                ...s,
                folders: [...s.folders, { id: `folder:${crypto.randomUUID()}`, title }],
              }));
              setFolderModal(false);
            }}
          >
            <label>
              文件夹名称
              <input
                name="title"
                autoFocus
                required
                maxLength={40}
                placeholder="例如：供应商资料"
              />
            </label>
            <button className="button button-primary" disabled={readOnly}>
              <FolderPlus size={14} />
              创建文件夹
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}

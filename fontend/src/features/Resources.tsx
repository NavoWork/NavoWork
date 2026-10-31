import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Boxes,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  FileImage,
  FileText,
  FolderOpen,
  Layers3,
  Loader2,
  Package,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import {
  api,
  ApiError,
  type Asset,
  type Capability,
  type ImportPreview,
  type Session,
  type Source,
} from '../api';
import { EmptyState, ErrorNotice, Loading, Modal, StatusBadge } from '../components/ui';
import './resources.css';

type ResourcePage = 'knowledge' | 'assets' | 'capabilities';
type KnowledgeTab = 'knowledge' | 'products';
const titles: Record<ResourcePage, [string, string, string]> = {
  knowledge: ['YOUR SHARED KNOWLEDGE', '知识 Wiki', '把商品与业务经验，变成每次回复的可靠依据。'],
  assets: [
    'READY FOR YOUR NEXT REPLY',
    '资产库',
    '集中管理商品素材与证据文件，保留每一次引用的版本。',
  ],
  capabilities: [
    'ONE WORKSPACE, MANY CAPABILITIES',
    '能力目录',
    '在同一个询盘里，调用完成这件事需要的专业能力。',
  ],
};
const csvTemplate =
  'sku,name,specification,moq,stock,stockObservedAt,minQuantity,maxQuantity,unitPriceMinor,currency,productionDays,dispatchDays,startsAfter,source\nDEMO-BAG,示例帆布袋,未印花,100,800,2026-10-31T00:00:00Z,100,,180,USD,,3,payment_conditions_met,合成测试数据请替换\n';
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}
function sizeLabel(size: number) {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function Resources({ page, session }: { page: ResourcePage; session: Session }) {
  const [tab, setTab] = useState<KnowledgeTab>('knowledge');
  const [query, setQuery] = useState('');
  const [modal, setModal] = useState<'knowledge' | 'import' | 'upload' | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [notice, setNotice] = useState('');
  const base = `/workspaces/${encodeURIComponent(session.workspace.id)}`;
  const scope = ['resources', session.user.id, session.workspace.id];
  const queryClient = useQueryClient();
  const endpoint = page === 'knowledge' ? tab : page;
  const resources = useQuery({
    queryKey: [...scope, endpoint],
    queryFn: ({ signal }) =>
      api.get<{ items: (Source | Asset | Capability)[] }>(`${base}/${endpoint}`, signal),
    staleTime: 15_000,
    retry: false,
  });
  const items = resources.data?.items;
  const filtered = items?.filter(
    (item) =>
      ('title' in item ? item.title : item.name).toLowerCase().includes(query.toLowerCase()) ||
      ('skuScope' in item && item.skuScope.join(' ').toLowerCase().includes(query.toLowerCase())),
  );
  const [kicker, title, description] = titles[page];
  const admin = session.user.role === 'admin';
  useEffect(() => {
    setQuery('');
    setNotice('');
  }, [page, tab]);
  const changed = (message: string) => {
    void queryClient.invalidateQueries({ queryKey: scope });
    setNotice(message);
  };

  return (
    <div className="feature-page resource-page">
      <header className="page-heading">
        <div>
          <div className="section-kicker">{kicker}</div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {page !== 'capabilities' && (
          <button
            className="button button-primary"
            onClick={() =>
              setModal(page === 'assets' ? 'upload' : tab === 'products' ? 'import' : 'knowledge')
            }
          >
            {page === 'assets' || tab === 'products' ? <Upload size={14} /> : <Plus size={15} />}{' '}
            {page === 'assets' ? '上传素材' : tab === 'products' ? '导入商品 CSV' : '新建知识'}
          </button>
        )}
      </header>
      {notice && (
        <div className="resource-notice" role="status">
          <CheckCircle2 size={15} />
          {notice}
          <button className="icon-button" aria-label="关闭提示" onClick={() => setNotice('')}>
            <X size={13} />
          </button>
        </div>
      )}
      <div className="resource-toolbar">
        <div className="resource-tabs">
          {page === 'knowledge' ? (
            <>
              <button
                className={tab === 'knowledge' ? 'selected' : ''}
                onClick={() => setTab('knowledge')}
              >
                <BookOpen size={15} />
                业务知识
              </button>
              <button
                className={tab === 'products' ? 'selected' : ''}
                onClick={() => setTab('products')}
              >
                <Package size={15} />
                商品目录
              </button>
            </>
          ) : (
            <span className="resource-total">
              {page === 'assets' ? '全部素材' : '内置能力'} <span>{items?.length ?? '—'}</span>
            </span>
          )}
        </div>
        <label className="resource-search">
          <Search size={15} />
          <input
            aria-label={`搜索${title}`}
            placeholder={
              page === 'assets'
                ? '搜索素材名称或 SKU'
                : `搜索${page === 'knowledge' ? (tab === 'knowledge' ? '知识' : '商品') : '能力'}`
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      {page === 'knowledge' && (
        <div className="resource-explainer">
          <ShieldCheck size={17} />
          <p>
            {tab === 'knowledge'
              ? '只有已发布版本会用于新的业务处理。更新资料会生成新版本，历史引用始终可追溯。'
              : '先检查 CSV，再确认发布。每个价阶单独一行；未发布的数据不会进入商品目录。'}
          </p>
          <span className="muted">{admin ? '管理员' : '成员 · 发布需管理员'}</span>
        </div>
      )}
      {page === 'capabilities' && (
        <div className="resource-explainer">
          <Layers3 size={18} />
          <p>
            能力共享当前询盘的上下文。关闭必需能力会阻止新运行；每次执行的步骤与结果在询盘中查看。
          </p>
          <span className="muted">{admin ? '可管理能力' : '仅管理员可启停'}</span>
        </div>
      )}
      {resources.isPending ? (
        <Loading label={`正在加载${title}`} />
      ) : resources.isError ? (
        <ErrorNotice error={resources.error} onRetry={() => void resources.refetch()} />
      ) : !filtered?.length ? (
        <EmptyState
          title={
            query
              ? '没有匹配的内容'
              : `还没有${title === '知识 Wiki' ? (tab === 'knowledge' ? '业务知识' : '商品') : title}`
          }
          description={
            query
              ? '试试其他关键词。'
              : page === 'assets'
                ? '上传图片或 PDF，为客户回复准备资料。'
                : '从上方入口添加第一份资料。'
          }
        />
      ) : (
        <>
          {page === 'knowledge' && (
            <div className="source-table">
              <div className="source-table-head">
                <span>名称 / 内容摘要</span>
                <span>版本状态</span>
                <span>更新时间</span>
                <span />
              </div>
              {(filtered as Source[]).map((item) => (
                <button
                  key={`${item.id}:${item.version}`}
                  className="source-row"
                  onClick={() => setSource(item)}
                >
                  <span className="source-summary">
                    <span className="resource-file-icon">
                      {item.kind === 'knowledge' ? (
                        <FileText size={20} strokeWidth={1.5} />
                      ) : (
                        <Package size={20} strokeWidth={1.5} />
                      )}
                    </span>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{item.content.replace(/[#*`]/g, '').slice(0, 85)}</small>
                    </span>
                  </span>
                  <span className="source-version">
                    <StatusBadge status={item.status} />
                    <small>V{item.version}</small>
                  </span>
                  <span className="source-date">{dateLabel(item.updatedAt)}</span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          )}
          {page === 'assets' && (
            <div className="asset-grid">
              {(filtered as Asset[]).map((item) => (
                <button
                  className="asset-card"
                  key={`${item.id}-${item.version}`}
                  onClick={() => setAsset(item)}
                >
                  <div
                    className={`asset-art ${item.mediaType === 'application/pdf' ? 'asset-art-pdf' : ''}`}
                  >
                    <div className="asset-art-frame">
                      {item.mediaType === 'application/pdf' ? (
                        <FileText size={48} strokeWidth={0.85} />
                      ) : (
                        <FileImage size={48} strokeWidth={0.85} />
                      )}
                    </div>
                    <span>
                      {item.mediaType === 'application/pdf' ? 'PDF DOCUMENT' : 'PRODUCT IMAGE'}
                    </span>
                    <span className="asset-version">V{item.version}</span>
                  </div>
                  <div className="asset-info">
                    <strong>{item.title}</strong>
                    <small>
                      {item.skuScope.length ? item.skuScope.join(' / ') : '通用素材'}
                      <span>{sizeLabel(item.size)}</span>
                    </small>
                    <div className="asset-info-footer">
                      <span>
                        {item.locale} · {dateLabel(item.createdAt)}
                      </span>
                      <ArrowRight size={14} />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
          {page === 'capabilities' && (
            <div className="capability-grid">
              {(filtered as Capability[]).map((item, index) => (
                <CapabilityCard
                  key={item.id}
                  item={item}
                  index={index}
                  base={base}
                  admin={admin}
                  onChanged={() => changed('能力配置已保存。')}
                />
              ))}
            </div>
          )}
        </>
      )}
      <footer className="resource-footer">
        <FolderOpen size={13} />
        <span>
          {session.workspace.name} / {title}
        </span>
        <span>
          {page === 'capabilities'
            ? '每次运行保留能力版本与执行记录'
            : '文件与资料仅在有权限的工作空间内使用'}
        </span>
      </footer>
      {modal === 'knowledge' && (
        <KnowledgeEditor
          base={base}
          admin={admin}
          onClose={() => setModal(null)}
          onChanged={changed}
        />
      )}
      {source && (
        <KnowledgeEditor
          key={`${source.id}:${source.version}`}
          base={base}
          source={source}
          admin={admin}
          onClose={() => setSource(null)}
          onChanged={changed}
        />
      )}
      {modal === 'import' && (
        <CsvImport base={base} admin={admin} onClose={() => setModal(null)} onChanged={changed} />
      )}
      {modal === 'upload' && (
        <AssetUpload base={base} onClose={() => setModal(null)} onChanged={changed} />
      )}
      {asset && <AssetPreview base={base} asset={asset} onClose={() => setAsset(null)} />}
    </div>
  );
}

function KnowledgeEditor({
  source,
  base,
  admin,
  onClose,
  onChanged,
}: {
  source?: Source;
  base: string;
  admin: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [record, setRecord] = useState(source);
  const [conflict, setConflict] = useState<Source | null>(null);
  const [title, setTitle] = useState(source?.title || '');
  const [content, setContent] = useState(source?.content || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const lock = useRef(false);
  const formId = useId();
  const readOnly = !!record && record.status !== 'draft';
  const dirty = !record || title !== record.title || content !== record.content;
  async function save(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = record
        ? await api.patch<Source>(
            `${base}/knowledge/${record.sourceId}/versions/${record.version}`,
            { title: title.trim(), content, editVersion: record.editVersion },
          )
        : await api.post<Source>(`${base}/knowledge`, { title: title.trim(), content });
      setRecord(result);
      setConflict(null);
      setTitle(result.title);
      setContent(result.content);
      onChanged('知识草稿已保存，可核对后发布。');
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && e.code === 'METADATA_CONFLICT' && e.details.current)
        setConflict(e.details.current as Source);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function publish() {
    if (!record || dirty || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<Source>(
        `${base}/knowledge/${record.sourceId}/versions/${record.version}/publish`,
        { editVersion: record.editVersion },
      );
      setRecord(result);
      onChanged(`「${result.title}」V${result.version} 已发布。`);
    } catch (e) {
      setError(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function createVersion() {
    if (!record || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<Source>(`${base}/knowledge/${record.sourceId}/versions`, {
        title,
        content,
      });
      setRecord(result);
      setConflict(null);
      onChanged(`已创建 V${result.version} 草稿，历史版本保持不变。`);
    } catch (e) {
      setError(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  const isKnowledge = !record || record.kind === 'knowledge';
  return (
    <Modal title={record ? record.title : '新建业务知识'} onClose={onClose} wide>
      <div className="knowledge-editor">
        <div className="resource-dialog-meta">
          <span>
            <FileText size={14} /> {isKnowledge ? '文本 / Markdown' : '固定商品资料'}
          </span>
          {record && (
            <span>
              <StatusBadge status={record.status} /> V{record.version} · 编辑版本{' '}
              {record.editVersion}
            </span>
          )}
        </div>
        <ErrorNotice error={error} />
        {conflict && (
          <div className="resource-conflict">
            <strong>发现更新版本，本地修改已保留在下方。</strong>
            <p>
              服务端：V{conflict.version} · 编辑版本 {conflict.editVersion} · {conflict.title}
            </p>
            <pre>{conflict.content}</pre>
            {conflict.status === 'draft' ? (
              <button
                className="button"
                onClick={() => {
                  setRecord(conflict);
                  setConflict(null);
                  setError(null);
                }}
              >
                保留本地文本，以最新编辑版本继续
              </button>
            ) : (
              <button className="button" disabled={busy} onClick={() => void createVersion()}>
                将本地修改另存为新草稿
              </button>
            )}
          </div>
        )}
        <form id={formId} className="form-stack" onSubmit={save}>
          <label className="field">
            {isKnowledge ? '知识标题' : '资料名称'}
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
              required
              disabled={readOnly || busy || !isKnowledge}
              placeholder="例如：现货交期与售后说明"
            />
          </label>
          <label className="field">
            正文
            {readOnly || !isKnowledge ? (
              <pre className="knowledge-content">{content}</pre>
            ) : (
              <textarea
                className="knowledge-content-input"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                maxLength={50000}
                required
                disabled={busy}
                placeholder="写下已核实的业务规则，并注明资料来源与适用条件。"
              />
            )}
          </label>
        </form>
        <div className="resource-dialog-footer">
          <span>
            {readOnly
              ? '此版本内容只读，历史引用不会被覆盖。'
              : `${content.length.toLocaleString()} / 50,000 字符${dirty ? ' · 有未保存修改' : ' · 已保存'}`}
          </span>
          <div className="resource-actions">
            {readOnly ? (
              isKnowledge && (
                <button className="button" disabled={busy} onClick={() => void createVersion()}>
                  <Plus size={14} />
                  {busy ? '创建中…' : '创建新版本'}
                </button>
              )
            ) : (
              <>
                <button type="submit" form={formId} className="button" disabled={busy || !dirty}>
                  {busy ? '处理中…' : '保存草稿'}
                </button>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={!record || dirty || busy || !admin}
                  onClick={() => void publish()}
                  title={!admin ? '仅管理员可发布' : dirty ? '请先保存修改' : undefined}
                >
                  <Check size={14} />
                  发布版本
                </button>
              </>
            )}
          </div>
        </div>
        {!admin && (
          <p className="resource-help">
            <CircleHelp size={13} /> 你可以维护草稿，发布需要管理员完成。
          </p>
        )}
      </div>
    </Modal>
  );
}

function CsvImport({
  base,
  admin,
  onClose,
  onChanged,
}: {
  base: string;
  admin: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const lock = useRef(false);
  const ref = useRef<HTMLInputElement>(null);
  async function upload() {
    if (!file || lock.current) return;
    if (file.size > 5 * 1024 * 1024) {
      setError('CSV 文件不能超过 5 MB。');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('请选择 .csv 格式的文件。');
      return;
    }
    lock.current = true;
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append('file', file);
    try {
      setPreview(await api.post<ImportPreview>(`${base}/product-imports`, data));
    } catch (e) {
      setError(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function publish() {
    if (!preview || preview.errors.length || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<ImportPreview>(
        `${base}/product-imports/${preview.id}/publish`,
        {},
      );
      setPreview(result);
      onChanged(`商品导入已发布，共 ${result.validCount} 行。`);
    } catch (e) {
      setError(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  const fields = preview?.rows.length
    ? Object.keys(preview.rows[0]).filter((k) =>
        ['sku', 'name', 'moq', 'stock', 'minQuantity', 'maxQuantity', 'unitPriceMinor'].includes(k),
      )
    : [];
  return (
    <Modal title="导入商品 CSV" onClose={onClose} wide>
      <div className="form-stack">
        <div className="resource-stepper">
          <span className="active">1 选择文件</span>
          <ChevronRight size={13} />
          <span className={preview ? 'active' : ''}>2 核对预览</span>
          <ChevronRight size={13} />
          <span className={preview?.status === 'published' ? 'active' : ''}>3 确认发布</span>
        </div>
        <div className="resource-upload-zone">
          <Upload size={27} strokeWidth={1.2} />
          <h3>{file?.name || '选择商品目录文件'}</h3>
          <p>CSV · 最多 5 MB / 1,000 行 · UTF-8 编码</p>
          <input
            ref={ref}
            className="sr-only"
            type="file"
            accept=".csv,text/csv"
            aria-label="商品 CSV 文件"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setPreview(null);
              setError(null);
            }}
          />
          <button
            className="button"
            disabled={busy || preview?.status === 'published'}
            onClick={() => ref.current?.click()}
          >
            选择 CSV 文件
          </button>
        </div>
        <div className="resource-template-line">
          <button
            className="button button-ghost"
            onClick={() =>
              saveBlob(
                new Blob(['\ufeff', csvTemplate], { type: 'text/csv;charset=utf-8;' }),
                'Navowork-商品导入模板.csv',
              )
            }
          >
            <ArrowDownToLine size={14} />
            下载 CSV 模板
          </button>
          <small className="muted">模板含合成测试行，请替换为已核实资料。</small>
        </div>
        <ErrorNotice error={error} />
        {preview && (
          <section className="import-preview">
            <div className="import-preview-heading">
              <h3>校验结果</h3>
              <span className={preview.errors.length ? 'resource-warning' : 'resource-success'}>
                {preview.totalCount} 行 · {preview.validCount} 行有效 · {preview.errors.length}{' '}
                处错误
              </span>
            </div>
            {preview.errors.length > 0 && (
              <div className="import-errors" role="alert">
                <strong>请修正下列问题后重新上传，当前内容尚未发布。</strong>
                <ul>
                  {preview.errors.map((e, i) => (
                    <li key={i}>
                      <span>
                        第 {e.row} 行 · {e.field}
                      </span>
                      {e.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {preview.rows.length > 0 && (
              <div className="resource-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>行</th>
                      {fields.map((f) => (
                        <th key={f}>{f}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 30).map((row, i) => (
                      <tr key={i}>
                        <td>{i + 2}</td>
                        {fields.map((f) => (
                          <td key={f}>{row[f] || '—'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {preview.rows.length > 30 && (
              <small className="muted">展示前 30 行，发布会使用全部已校验记录。</small>
            )}
            {preview.status === 'published' && (
              <div className="resource-notice">
                <CheckCircle2 size={16} />
                此批次已发布，新运行可查询已发布商品版本。
              </div>
            )}
          </section>
        )}
        <div className="resource-dialog-footer">
          <span>{admin ? '发布前不会改变正式商品目录。' : '发布需要管理员权限。'}</span>
          <div className="resource-actions">
            {preview?.status === 'published' ? (
              <button className="button button-primary" onClick={onClose}>
                完成
              </button>
            ) : (
              <>
                <button className="button" disabled={!file || busy} onClick={() => void upload()}>
                  {busy ? '处理中…' : preview ? '重新校验' : '上传并校验'}
                </button>
                <button
                  className="button button-primary"
                  disabled={
                    !preview || !!preview.errors.length || !preview.validCount || busy || !admin
                  }
                  onClick={() => void publish()}
                >
                  确认发布
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function AssetUpload({
  base,
  onClose,
  onChanged,
}: {
  base: string;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [sku, setSku] = useState('');
  const [locale, setLocale] = useState('en-US');
  const [source, setSource] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const lock = useRef(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || lock.current) return;
    if (file.size > 20 * 1024 * 1024) {
      setError('素材文件不能超过 20 MB。');
      return;
    }
    const types: Record<string, string[]> = {
      'image/jpeg': ['jpg', 'jpeg'],
      'image/png': ['png'],
      'image/webp': ['webp'],
      'application/pdf': ['pdf'],
    };
    if (!types[file.type]?.includes(file.name.split('.').pop()?.toLowerCase() || '')) {
      setError('请选择扩展名与类型一致的 JPEG、PNG、WebP 或 PDF 文件。');
      return;
    }
    lock.current = true;
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append('file', file);
    data.append('title', title.trim());
    data.append('skuScope', sku.trim());
    data.append('locale', locale);
    data.append('source', source.trim());
    try {
      await api.post<Asset>(`${base}/assets`, data);
      onChanged(`「${title}」已上传，可在询盘中引用对应版本。`);
      onClose();
    } catch (err) {
      setError(err);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <Modal title="上传素材" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <p className="muted">
          支持 JPEG、PNG、WebP、PDF，单文件不超过 20 MB。PDF 作为证据附件保存。
        </p>
        <ErrorNotice error={error} />
        <label className="field">
          文件
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            required
            disabled={busy}
            onChange={(e) => {
              const next = e.target.files?.[0] || null;
              setFile(next);
              if (next && !title) setTitle(next.name.replace(/\.[^.]+$/, ''));
            }}
          />
        </label>
        <label className="field">
          素材名称
          <input
            required
            maxLength={120}
            value={title}
            disabled={busy}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：现货帆布袋商品规格"
          />
        </label>
        <div className="resource-form-two">
          <label className="field">
            适用 SKU
            <input
              value={sku}
              disabled={busy}
              onChange={(e) => setSku(e.target.value)}
              placeholder="BAG-STOCK"
            />
            <small>多个 SKU 用英文逗号分隔，留空为通用。</small>
          </label>
          <label className="field">
            语言
            <select value={locale} onChange={(e) => setLocale(e.target.value)} disabled={busy}>
              <option value="en-US">英语 · en-US</option>
              <option value="es-MX">西班牙语 · es-MX</option>
              <option value="zh-CN">中文 · zh-CN</option>
              <option value="und">无语言</option>
            </select>
          </label>
        </div>
        <label className="field">
          资料来源与用途
          <textarea
            required
            value={source}
            disabled={busy}
            maxLength={1000}
            onChange={(e) => setSource(e.target.value)}
            placeholder="注明提供方、取得时间和用途；示意图请明确标注。"
          />
        </label>
        <div className="form-actions">
          <button type="button" className="button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="button button-primary" disabled={busy || !file}>
            {busy ? <Loader2 size={14} className="resource-spin" /> : <Upload size={14} />}{' '}
            {busy ? '上传中…' : '上传素材'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AssetPreview({
  base,
  asset,
  onClose,
}: {
  base: string;
  asset: Asset;
  onClose: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const blob = useRef<Blob | null>(null);
  const ownedUrl = useRef<string | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (ownedUrl.current) URL.revokeObjectURL(ownedUrl.current);
    };
  }, []);
  async function download(preview: boolean) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result =
        blob.current ||
        (await api.download(`${base}/assets/${asset.id}/versions/${asset.version}/download`));
      if (!alive.current) return;
      blob.current = result;
      if (preview) {
        if (ownedUrl.current) URL.revokeObjectURL(ownedUrl.current);
        ownedUrl.current = URL.createObjectURL(result);
        setUrl(ownedUrl.current);
      } else saveBlob(result, asset.name);
    } catch (e) {
      if (alive.current) setError(e);
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  return (
    <Modal title={asset.title} onClose={onClose} wide>
      <div className="asset-preview-dialog">
        <div className="asset-preview-area">
          {url ? (
            asset.mediaType.startsWith('image/') ? (
              <img src={url} alt={asset.title} />
            ) : (
              <iframe sandbox="" src={url} title={`预览 ${asset.title}`} />
            )
          ) : (
            <div>
              <FileImage size={45} strokeWidth={1} />
              <p>
                版本 V{asset.version} · {sizeLabel(asset.size)}
              </p>
              <button className="button" disabled={busy} onClick={() => void download(true)}>
                {busy ? '加载中…' : '加载文件预览'}
              </button>
            </div>
          )}
        </div>
        <ErrorNotice error={error} />
        <dl className="asset-metadata">
          <div>
            <dt>适用 SKU</dt>
            <dd>{asset.skuScope.join(' / ') || '通用素材'}</dd>
          </div>
          <div>
            <dt>语言</dt>
            <dd>{asset.locale}</dd>
          </div>
          <div>
            <dt>文件类型</dt>
            <dd>{asset.mediaType}</dd>
          </div>
          <div>
            <dt>资料来源与用途</dt>
            <dd>{asset.source}</dd>
          </div>
        </dl>
        <div className="resource-dialog-footer">
          <span>引用将绑定此固定文件版本，使用时核对 SKU 范围。</span>
          <button
            className="button button-primary"
            disabled={busy}
            onClick={() => void download(false)}
          >
            <ArrowDownToLine size={14} />
            下载 V{asset.version}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CapabilityCard({
  item,
  index,
  base,
  admin,
  onChanged,
}: {
  item: Capability;
  index: number;
  base: string;
  admin: boolean;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const lock = useRef(false);
  const icons = [Sparkles, Search, Boxes, FileText, ShieldCheck, FolderOpen];
  const Icon = icons[index % icons.length];
  async function toggle() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      await api.patch<Capability>(`${base}/capabilities/${item.id}`, { enabled: !item.enabled });
      onChanged();
    } catch (e) {
      setError(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <article className={`capability-card ${!item.enabled ? 'disabled-capability' : ''}`}>
      <div className="capability-top">
        <span className="capability-icon">
          <Icon size={23} strokeWidth={1.35} />
        </span>
        <span className="badge">{item.required ? '必需能力' : '可选能力'}</span>
      </div>
      <h3>{item.name}</h3>
      <p>{item.description}</p>
      <div className="capability-bottom">
        <span>
          V{item.version} · {item.category}
        </span>
        <label className="capability-switch-label">
          <span>{busy ? '保存中' : item.enabled ? '已启用' : '已停用'}</span>
          <button
            role="switch"
            aria-label={`${item.name}开关`}
            aria-checked={item.enabled}
            className="capability-switch"
            disabled={!admin || busy}
            onClick={() => void toggle()}
            title={!admin ? '仅管理员可更改' : undefined}
          >
            <span />
          </button>
        </label>
      </div>
      <ErrorNotice error={error} />
    </article>
  );
}

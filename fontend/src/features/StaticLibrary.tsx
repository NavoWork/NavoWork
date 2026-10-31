import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Building2,
  Check,
  ChevronRight,
  Code2,
  File,
  FileArchive,
  FileImage,
  FileSpreadsheet,
  FileText,
  Film,
  Folder,
  FolderOpen,
  LayoutGrid,
  List,
  Plus,
  Search,
  Star,
  Upload,
  UserRound,
  X,
} from 'lucide-react';
import { EmptyState, ErrorNotice, Loading, Modal } from '../components/ui';
import { api, mode, type Session } from '../api';
import { useLibraryCollection } from './library-api';
import {
  assetKinds,
  libraryAssets,
  wikiDocuments,
  wikiFolders,
  type AssetKind,
  type AssetSpace,
  type LibraryAsset,
  type WikiDocument,
} from './library-data';
import './library.css';

type SortOrder = 'updated' | 'name';
const spaceLabels = { company: '公司资产库', personal: '个人资产库' };
const typeIcons = {
  image: FileImage,
  video: Film,
  spreadsheet: FileSpreadsheet,
  document: FileText,
  other: File,
};

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function SearchBox({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <div className="library-search">
      <Search size={17} />
      <input
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && (
        <button aria-label="清除搜索" onClick={() => onChange('')}>
          <X size={15} />
        </button>
      )}
    </div>
  );
}
function SortSelect({
  value,
  onChange,
}: {
  value: SortOrder;
  onChange: (value: SortOrder) => void;
}) {
  return (
    <select
      className="library-sort"
      aria-label="排序方式"
      value={value}
      onChange={(e) => onChange(e.target.value as SortOrder)}
    >
      <option value="updated">最近更新</option>
      <option value="name">名称 A–Z</option>
    </select>
  );
}
function Favorite({
  active,
  title,
  onClick,
}: {
  active: boolean;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`library-star ${active ? 'is-starred' : ''}`}
      aria-label={`${active ? '取消收藏' : '收藏'} ${title}`}
      aria-pressed={active}
      title={active ? '取消收藏' : '收藏'}
      onClick={onClick}
    >
      <Star size={16} fill={active ? 'currentColor' : 'none'} />
    </button>
  );
}
function Inline({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
        .map((part, i) =>
          part.startsWith('**') ? (
            <strong key={i}>{part.slice(2, -2)}</strong>
          ) : part.startsWith('`') ? (
            <code key={i}>{part.slice(1, -1)}</code>
          ) : (
            <Fragment key={i}>{part}</Fragment>
          ),
        )}
    </>
  );
}

// A deliberately small, text-only Markdown renderer for the static Wiki. Raw HTML is never executed.
function Markdown({ content }: { content: string }) {
  const lines = content.split('\n');
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = i;
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith('```')) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
      i++;
      blocks.push(
        <pre key={key}>
          <code>{code.join('\n')}</code>
        </pre>,
      );
    } else if (/^#{1,3} /.test(line)) {
      const level = line.match(/^#+/)![0].length;
      const text = line.replace(/^#+ /, '');
      blocks.push(
        level === 1 ? (
          <h1 key={key}>
            <Inline text={text} />
          </h1>
        ) : level === 2 ? (
          <h2 key={key} id={`wiki-section-${key}`}>
            <Inline text={text} />
          </h2>
        ) : (
          <h3 key={key}>
            <Inline text={text} />
          </h3>
        ),
      );
      i++;
    } else if (line.startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith('|')) {
        const row = lines[i++]
          .split('|')
          .slice(1, -1)
          .map((cell) => cell.trim());
        if (!row.every((cell) => /^:?-+:?$/.test(cell))) rows.push(row);
      }
      blocks.push(
        <div className="wiki-table-wrap" key={key}>
          <table>
            <thead>
              <tr>
                {rows[0]?.map((cell, n) => (
                  <th key={n}>
                    <Inline text={cell} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((row, n) => (
                <tr key={n}>
                  {row.map((cell, m) => (
                    <td key={m}>
                      <Inline text={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else if (/^(- |\d+\. )/.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const entries: string[] = [];
      while (i < lines.length && (ordered ? /^\d+\. / : /^- /).test(lines[i]))
        entries.push(lines[i++].replace(/^(- |\d+\. )/, ''));
      const children = entries.map((entry, n) => (
        <li key={n}>
          <Inline text={entry} />
        </li>
      ));
      blocks.push(ordered ? <ol key={key}>{children}</ol> : <ul key={key}>{children}</ul>);
    } else if (line.startsWith('> ')) {
      blocks.push(
        <blockquote key={key}>
          <Inline text={line.slice(2)} />
        </blockquote>,
      );
      i++;
    } else {
      blocks.push(
        <p key={key}>
          <Inline text={line} />
        </p>,
      );
      i++;
    }
  }
  return <div className="wiki-markdown">{blocks}</div>;
}

function WikiReader({ doc, onClose }: { doc: WikiDocument; onClose: () => void }) {
  const [source, setSource] = useState(false);
  const headings = doc.content
    .split('\n')
    .map((line, index) => ({ line, index }))
    .filter((item) => item.line.startsWith('## '));
  return (
    <Modal title={`${doc.title}.md`} onClose={onClose} wide>
      <div className="wiki-reader-toolbar">
        <span>
          <Folder size={14} />
          {doc.folder}
          <span className="library-dot">·</span>
          {doc.updated}
        </span>
        <div className="library-segmented" aria-label="阅读方式">
          <button aria-pressed={!source} onClick={() => setSource(false)}>
            <BookOpen size={14} />
            阅读
          </button>
          <button aria-pressed={source} onClick={() => setSource(true)}>
            <Code2 size={14} />
            原文
          </button>
        </div>
      </div>
      <div className={`wiki-reader ${source ? 'show-source' : ''}`}>
        {source ? (
          <pre className="wiki-source">{doc.content}</pre>
        ) : (
          <>
            <Markdown content={doc.content} />
            {headings.length > 0 && (
              <nav className="wiki-outline" aria-label="本文目录">
                <span>本文目录</span>
                {headings.map(({ line, index }) => (
                  <button
                    key={index}
                    onClick={() =>
                      document.getElementById(`wiki-section-${index}`)?.scrollIntoView({
                        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches
                          ? 'instant'
                          : 'smooth',
                        block: 'start',
                      })
                    }
                  >
                    {line.slice(3)}
                  </button>
                ))}
              </nav>
            )}
          </>
        )}
      </div>
      <div className="library-dialog-footer">
        <span className="library-file-label">Markdown</span>
        <button
          className="button"
          onClick={() =>
            download(
              new Blob([doc.content], { type: 'text/markdown;charset=utf-8' }),
              `${doc.title}.md`,
            )
          }
        >
          <ArrowDownToLine size={15} />
          下载文档
        </button>
      </div>
    </Modal>
  );
}

function WikiCreate({
  folder,
  onClose,
  onCreate,
}: {
  folder: string;
  onClose: () => void;
  onCreate: (doc: WikiDocument) => void | Promise<void>;
}) {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState(wikiFolders.includes(folder) ? folder : wikiFolders[0]);
  const [content, setContent] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <Modal title="新建文档" onClose={onClose} wide>
      <form
        className="form-stack"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy || !title.trim() || !content.trim()) return;
          setBusy(true); setError(undefined);
          try { await onCreate({
            id: crypto.randomUUID(),
            title: title.trim().replace(/\.md$/i, ''),
            folder: category,
            content,
            summary: content
              .replace(/[#*`>]/g, '')
              .trim()
              .slice(0, 72),
            updated: new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }),
            starred: false,
          }); } catch (e) { setError(e); } finally { setBusy(false); }
        }}
      >
        <div className="library-form-row">
          <label className="field">
            文档名称
            <input
              autoFocus
              required
              maxLength={100}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：客户需求确认清单"
            />
          </label>
          <label className="field">
            所属目录
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {wikiFolders.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          Markdown 正文
          <textarea
            className="wiki-editor-input"
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={'# 文档标题\n\n在这里写下值得复用的知识…'}
          />
        </label>
        <div className="library-dialog-footer">
          <span>{mode === 'real' ? '保存到团队知识库，引用时固定资料版本' : '仅在当前页面演示，离开后恢复示例内容'}</span>
          <div className="library-actions">
            <button type="button" className="button button-ghost" onClick={onClose}>
              取消
            </button>
            <button className="button button-primary" disabled={busy || !title.trim() || !content.trim()}>
              {busy ? '保存中…' : '创建文档'}
            </button>
          </div>
        </div>
        <ErrorNotice error={error} />
      </form>
    </Modal>
  );
}

function WikiLibrary({ session }: { session: Session }) {
  const { values: docs, setValues: setDocs, query: remote, path } = useLibraryCollection(session, 'documents', wikiDocuments);
  const [error, setError] = useState<unknown>();
  const [folder, setFolder] = useState('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortOrder>('updated');
  const [selected, setSelected] = useState<WikiDocument | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState('');
  const search = query.trim().toLocaleLowerCase();
  const filtered = docs
    .filter(
      (doc) =>
        (folder === 'all' || (folder === 'starred' ? doc.starred : doc.folder === folder)) &&
        `${doc.title} ${doc.content}`.toLocaleLowerCase().includes(search),
    )
    .sort((a, b) =>
      sort === 'name'
        ? a.title.localeCompare(b.title, 'zh-CN')
        : b.updated.localeCompare(a.updated),
    );
  const currentFolder = folder === 'all' ? '全部文档' : folder === 'starred' ? '我的收藏' : folder;
  return (
    <div className="feature-page library-page">
      <header className="library-heading">
        <div>
          <h1>
            知识库 <span className="library-title-tag">Wiki</span>
          </h1>
          <p>把经验写下来，让知识随手可用。</p>
        </div>
        <div className="library-actions">
          <button className="button" onClick={() => setImporting(true)}>
            <Upload size={15} />
            导入 Markdown
          </button>
          <button className="button button-primary" onClick={() => setCreating(true)}>
            <Plus size={16} />
            新建文档
          </button>
        </div>
      </header>
      {notice && <Notice text={notice} onClose={() => setNotice('')} />}
      <ErrorNotice error={error || remote.error} onRetry={() => { setError(undefined); void remote.refetch(); }} />
      {mode === 'real' && remote.isLoading && <Loading label="正在读取知识库" />}
      <div className="wiki-layout">
        <aside className="wiki-sidebar" aria-label="知识目录">
          <button className={folder === 'all' ? 'is-active' : ''} onClick={() => setFolder('all')}>
            <BookOpen size={17} />
            全部文档<span>{docs.length}</span>
          </button>
          <button
            className={folder === 'starred' ? 'is-active' : ''}
            onClick={() => setFolder('starred')}
          >
            <Star size={17} />
            我的收藏<span>{docs.filter((doc) => doc.starred).length}</span>
          </button>
          <div className="wiki-sidebar-label">目录</div>
          {wikiFolders.map((item) => (
            <button
              className={folder === item ? 'is-active' : ''}
              key={item}
              onClick={() => setFolder(item)}
            >
              <Folder size={17} />
              {item}
              <span>{docs.filter((doc) => doc.folder === item).length}</span>
            </button>
          ))}
        </aside>
        <section className="wiki-main" aria-label="文档列表">
          <div className="library-toolbar">
            <div className="library-section-title">
              {currentFolder}
              <span>{filtered.length}</span>
            </div>
            <div className="library-toolbar-controls">
              <SearchBox label="搜索文档或正文" value={query} onChange={setQuery} />
              <SortSelect value={sort} onChange={setSort} />
            </div>
          </div>
          <div className="wiki-list-header">
            <span>文档名称</span>
            <span>更新时间</span>
            <span />
          </div>
          {filtered.map((doc) => (
            <div className="wiki-row" key={doc.id}>
              <button className="wiki-document" onClick={() => setSelected(doc)}>
                <span className="wiki-file-icon">
                  <FileText size={22} />
                  <small>MD</small>
                </span>
                <span className="wiki-document-text">
                  <strong>
                    {doc.title}
                    <span className="wiki-extension">.md</span>
                  </strong>
                  <span>{doc.summary}</span>
                  <small>
                    <Folder size={12} />
                    {doc.folder}
                  </small>
                </span>
              </button>
              <time dateTime={doc.updated}>{doc.updated.slice(5).replace('-', '/')}</time>
              <Favorite
                active={doc.starred}
                title={doc.title}
                onClick={() => { void (async () => {
                  try {
                    const result = mode === 'real' ? await api.put<{ starred: boolean }>(`${path}/${doc.id}/favorite`, { starred: !doc.starred }) : { starred: !doc.starred };
                    setDocs(current => current.map(item => item.id === doc.id ? { ...item, ...result } : item));
                  } catch (e) { setError(e); }
                })(); }}
              />
            </div>
          ))}
          {!filtered.length && (
            <LibraryEmpty
              title={query ? '没有找到相关文档' : '这里还没有文档'}
              onReset={
                query || folder !== 'all'
                  ? () => {
                      setQuery('');
                      setFolder('all');
                    }
                  : undefined
              }
            />
          )}
          <div className="library-list-footer">
            {filtered.length} 篇文档<span>Markdown</span>
          </div>
        </section>
      </div>
      {selected && <WikiReader doc={selected} onClose={() => setSelected(null)} />}
      {creating && (
        <WikiCreate
          folder={folder}
          onClose={() => setCreating(false)}
          onCreate={async (doc) => {
            const saved = mode === 'real' ? await api.post<WikiDocument>(path, doc) : doc;
            setDocs((current) => [saved, ...current]);
            setCreating(false);
            setFolder(doc.folder);
            setQuery('');
            setNotice(mode === 'real' ? '文档已保存到知识库' : '文档已添加到当前演示');
          }}
        />
      )}
      {importing && (
        <ImportDialog
          kind="wiki"
          destination={wikiFolders.includes(folder) ? folder : wikiFolders[0]}
          onClose={() => setImporting(false)}
          onImport={async (files) => {
            const content = await Promise.all(files.map((file) => file.text()));
            const added = files.map((file, index): WikiDocument => ({
              id: crypto.randomUUID(),
              title: file.name.replace(/\.(md|markdown)$/i, ''),
              folder: wikiFolders.includes(folder) ? folder : wikiFolders[0],
              summary: content[index]
                .replace(/[#*`>]/g, '')
                .trim()
                .slice(0, 72),
              content: content[index],
              updated: new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }),
              starred: false,
            }));
            if (mode === 'real') {
              for (const doc of added) {
                const saved = await api.post<WikiDocument>(path, doc);
                setDocs(current => [saved, ...current]);
              }
            } else setDocs((current) => [...added, ...current]);
            setFolder(added[0].folder);
            setQuery('');
            setImporting(false);
            setNotice(`已导入 ${added.length} 篇文档${mode === 'real' ? '到知识库' : '到当前演示'}`);
          }}
        />
      )}
    </div>
  );
}

function Notice({ text, onClose }: { text: string; onClose: () => void }) {
  return (
    <div className="library-notice" role="status">
      <Check size={16} />
      {text}
      <button aria-label="关闭提示" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}
function LibraryEmpty({ title, onReset }: { title: string; onReset?: () => void }) {
  return (
    <div className="library-empty">
      <EmptyState
        title={title}
        description={onReset ? '换个关键词，或重置筛选后再看看。' : '添加第一份文件，从这里开始。'}
      />
      {onReset && (
        <button className="button" onClick={onReset}>
          重置筛选
        </button>
      )}
    </div>
  );
}

function ImportDialog({
  kind,
  destination,
  onClose,
  onImport,
}: {
  kind: 'wiki' | 'asset';
  destination: string;
  onClose: () => void;
  onImport: (files: File[]) => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const addFiles = (incoming: File[]) => {
    setError('');
    const accepted = incoming.filter(
      (file) =>
        (kind !== 'wiki' || /\.(md|markdown)$/i.test(file.name)) &&
        file.size <= (kind === 'wiki' ? 2 : 100) * 1024 * 1024,
    );
    if (accepted.length !== incoming.length)
      setError(
        kind === 'wiki'
          ? '请选择 2 MB 以内的 .md 或 .markdown 文件。'
          : '单个文件请控制在 100 MB 以内。',
      );
    setFiles((current) =>
      [...current, ...accepted].filter(
        (file, index, all) =>
          all.findIndex(
            (item) =>
              item.name === file.name &&
              item.size === file.size &&
              item.lastModified === file.lastModified,
          ) === index,
      ),
    );
  };
  return (
    <Modal
      title={kind === 'wiki' ? '导入 Markdown' : '添加文件'}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="library-destination">
        <FolderOpen size={16} />
        添加到 <strong>{destination}</strong>
      </p>
      <div
        className={`library-dropzone ${dragging ? 'is-dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!busy) addFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <span className="library-upload-icon">
          <Upload size={25} strokeWidth={1.5} />
        </span>
        <h3>将文件拖到这里</h3>
        <p>
          {kind === 'wiki' ? '支持 .md、.markdown，可多选' : '图片、视频、表格、文档及其他文件'}
        </p>
        <button className="button" disabled={busy} onClick={() => input.current?.click()}>
          选择文件
        </button>
        <input
          ref={input}
          className="sr-only"
          type="file"
          aria-label={kind === 'wiki' ? 'Markdown 文件' : '资产文件'}
          tabIndex={-1}
          multiple
          accept={kind === 'wiki' ? '.md,.markdown' : undefined}
          disabled={busy}
          onChange={(e) => {
            addFiles(Array.from(e.target.files || []));
            e.target.value = '';
          }}
        />
      </div>
      {files.length > 0 && (
        <ul className="library-upload-files">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <FileText size={16} />
              <span>{file.name}</span>
              <button
                disabled={busy}
                aria-label={`移除 ${file.name}`}
                onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
              >
                <X size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="library-error" role="alert">
          {error}
        </p>
      )}
      <div className="library-dialog-footer">
        <span>{mode === 'real' ? '支持多文件上传' : '当前页面资料'}</span>
        <button
          className="button button-primary"
          disabled={!files.length || busy}
          onClick={async () => {
            if (lock.current) return;
            lock.current = true;
            setBusy(true);
            try {
              await onImport(files);
            } catch (e) {
              setError(e instanceof Error ? e.message : '文件读取或上传失败，请重试。');
            } finally {
              lock.current = false;
              setBusy(false);
            }
          }}
        >
          {busy ? '正在添加…' : `添加${files.length ? ` ${files.length} 个文件` : ''}`}
        </button>
      </div>
    </Modal>
  );
}

function AssetArtwork({ asset, large = false }: { asset: LibraryAsset; large?: boolean }) {
  if (asset.url && asset.kind === 'image')
    return (
      <div className="library-art uploaded-image">
        <img src={asset.url} alt={asset.name} />
      </div>
    );
  if (asset.url || asset.downloadPath) {
    const Icon = typeIcons[asset.kind];
    return (
      <div className={`library-art art-${asset.kind}`}>
        <Icon size={large ? 72 : 48} strokeWidth={1.2} />
        <span className="art-file-extension">{asset.name.split('.').pop()?.toUpperCase()}</span>
      </div>
    );
  }
  return (
    <div className={`library-art art-${asset.art}`} aria-hidden="true">
      {(asset.art === 'tote' || asset.art === 'video') && (
        <>
          <div className="art-orbit" />
          <div className="tote-illustration">
            <div className="tote-handle" />
            <div className="tote-body">
              <span>
                EVERYDAY
                <br />
                <b>essentials.</b>
              </span>
              <i />
            </div>
          </div>
          {asset.art === 'video' && (
            <span className="art-duration">
              <Film size={12} />
              00:24
            </span>
          )}
        </>
      )}
      {asset.art === 'backpack' && (
        <>
          <div className="art-orbit" />
          <div className="backpack-illustration">
            <i />
            <div className="backpack-body">
              <span />
              <b>FIELD / 01</b>
            </div>
          </div>
        </>
      )}
      {asset.art === 'brand' && (
        <div className="art-brand">
          <img src="/brand/navowork-mark-black.svg" alt="" />
          <strong>Navowork</strong>
        </div>
      )}
      {asset.art === 'sheet' && (
        <div className="art-sheet">
          <div>
            <FileSpreadsheet size={15} />
            <span>{asset.space === 'company' ? '产品报价表' : '客户报价对比'}</span>
          </div>
          <table>
            <tbody>
              {[
                ['', 'A', 'B', 'C'],
                ['1', '产品', '数量', '单价'],
                ['2', '帆布袋', '500', '$2.40'],
                ['3', '通勤背包', '300', '$8.60'],
                ['4', '收纳包', '800', '$1.80'],
              ].map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {asset.art === 'catalog' && (
        <div className="art-catalog">
          <small>COLLECTION / 2026</small>
          <strong>
            日常之物
            <br />
            自在随行
          </strong>
          <span>产品系列 · 秋冬</span>
          <div />
          <b>N.</b>
        </div>
      )}
      {asset.art === 'slides' && (
        <div className="art-slides">
          <span>Navowork</span>
          <strong>
            让每一份工作
            <br />
            更进一步。
          </strong>
          <i />
          <small>COMPANY INTRODUCTION</small>
        </div>
      )}
      {asset.art === 'archive' && (
        <div className="art-archive">
          <FileArchive size={52} strokeWidth={1} />
          <span>包装设计 / 源文件</span>
        </div>
      )}
      {asset.art === 'notes' && (
        <div className="art-notes">
          <FileText size={24} />
          <strong>客户拜访笔记</strong>
          <i />
          <i />
          <i />
          <i />
        </div>
      )}
    </div>
  );
}

function AssetPreview({ asset, onClose }: { asset: LibraryAsset; onClose: () => void }) {
  const [remote, setRemote] = useState<LibraryAsset>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    if (!asset.downloadPath) return;
    let live = true; let url = '';
    setRemote(undefined); setError(undefined);
    api.download(asset.downloadPath).then(blob => {
      if (!live) return;
      url = URL.createObjectURL(blob);
      setRemote({ ...asset, downloadPath: undefined, url, file: new window.File([blob], asset.name, { type: asset.mime }) });
    }).catch(e => { if (live) setError(e); });
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [asset.id, asset.downloadPath]);
  if (asset.downloadPath) return remote ? <AssetPreview asset={remote} onClose={onClose} /> : <Modal title={asset.name} onClose={onClose}>
    {error ? <ErrorNotice error={error} /> : <Loading label="正在读取原文件" />}
  </Modal>;
  const kindLabel = assetKinds.find((item) => item.id === asset.kind)?.label;
  const pdf = asset.mime === 'application/pdf';
  const canPreview =
    !!asset.url &&
    (['image', 'video'].includes(asset.kind) || pdf || asset.mime?.startsWith('audio/'));
  return (
    <Modal title={asset.name} onClose={onClose} wide>
      <div className="library-preview-meta">
        <span>
          {spaceLabels[asset.space]}
          <ChevronRight size={13} />
          {asset.folder}
        </span>
        <span>
          {kindLabel} · {asset.size}
        </span>
      </div>
      <div className="library-preview-stage">
        {asset.url && asset.kind === 'video' ? (
          <video controls src={asset.url} preload="metadata" aria-label={asset.name} />
        ) : asset.url && asset.mime?.startsWith('audio/') ? (
          <audio controls src={asset.url} aria-label={asset.name} />
        ) : asset.url && pdf ? (
          <iframe title={asset.name} src={asset.url} />
        ) : (
          <AssetArtwork asset={asset} large />
        )}
        {!asset.file && (
          <span className="library-preview-caption">
            {asset.kind === 'video'
              ? '示例视频封面'
              : asset.kind === 'spreadsheet'
                ? '示例表格预览'
                : '示例文件预览'}
          </span>
        )}
        {asset.file && !canPreview && (
          <p className="library-preview-unavailable">此格式暂不支持在线预览，可下载后查看。</p>
        )}
      </div>
      <div className="library-dialog-footer">
        <span>更新于 {asset.updated}</span>
        {asset.file ? (
          <button
            className="button button-primary"
            onClick={() => download(asset.file!, asset.name)}
          >
            <ArrowDownToLine size={15} />
            下载文件
          </button>
        ) : (
          <button className="button" onClick={onClose}>
            关闭预览
          </button>
        )}
      </div>
    </Modal>
  );
}

function detectKind(file: File): AssetKind {
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  if (file.type.startsWith('image/') || /^(png|jpe?g|gif|webp|svg|avif|bmp)$/.test(extension))
    return 'image';
  if (file.type.startsWith('video/') || /^(mp4|mov|webm|m4v)$/.test(extension)) return 'video';
  if (/^(xlsx?|csv|ods|numbers)$/.test(extension)) return 'spreadsheet';
  if (/^(pdf|docx?|pptx?|txt|md|pages|key)$/.test(extension)) return 'document';
  return 'other';
}

function AssetLibrary({ session }: { session: Session }) {
  const { values: assets, setValues: setAssets, query: remote, path } = useLibraryCollection(session, 'assets', libraryAssets);
  const [error, setError] = useState<unknown>();
  const [space, setSpace] = useState<AssetSpace>('personal');
  const [folder, setFolder] = useState('all');
  const [foldersOpen, setFoldersOpen] = useState(false);
  const [kind, setKind] = useState<AssetKind | 'all'>('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortOrder>('updated');
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const [favorites, setFavorites] = useState(false);
  const [selected, setSelected] = useState<LibraryAsset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState('');
  const urls = useRef<string[]>([]);
  useEffect(
    () => () => {
      urls.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );
  const spaceAssets = assets.filter((asset) => asset.space === space);
  const folders = Array.from(new Set(spaceAssets.map((asset) => asset.folder)));
  const search = query.trim().toLocaleLowerCase();
  const filtered = spaceAssets
    .filter(
      (asset) =>
        (folder === 'all' || asset.folder === folder) &&
        (kind === 'all' || asset.kind === kind) &&
        (!favorites || asset.starred) &&
        `${asset.name} ${asset.folder}`.toLocaleLowerCase().includes(search),
    )
    .sort((a, b) =>
      sort === 'name' ? a.name.localeCompare(b.name, 'zh-CN') : b.updated.localeCompare(a.updated),
    );
  const reset = () => {
    setFolder('all');
    setFoldersOpen(false);
    setKind('all');
    setFavorites(false);
    setQuery('');
  };
  const toggleStar = async (id: string) => {
    const asset = assets.find(a => a.id === id); if (!asset) return;
    try {
      const result = mode === 'real' ? await api.put<{ starred: boolean }>(`${path}/${id}/favorite`, { starred: !asset.starred }) : { starred: !asset.starred };
      setAssets(current => current.map(a => a.id === id ? { ...a, ...result } : a));
    } catch (e) { setError(e); }
  };
  return (
    <div className="feature-page library-page asset-library">
      <ErrorNotice error={error || remote.error} onRetry={() => { setError(undefined); void remote.refetch(); }} />
      {mode === 'real' && remote.isLoading && <Loading label="正在读取资产库" />}
      <header className="library-heading">
        <div>
          <h1>资产库</h1>
          <p>文件各归其位，需要时一眼找到。</p>
        </div>
        <button className="button button-primary" onClick={() => setUploading(true)}>
          <Upload size={16} />
          添加文件
        </button>
      </header>
      {notice && <Notice text={notice} onClose={() => setNotice('')} />}
      <div className="asset-space-bar">
        <div className="asset-spaces" aria-label="资产空间">
          {(['personal', 'company'] as const).map((item) => (
            <button
              key={item}
              aria-pressed={space === item}
              onClick={() => {
                setSpace(item);
                reset();
                setNotice('');
              }}
            >
              {item === 'company' ? <Building2 size={17} /> : <UserRound size={17} />}
              {spaceLabels[item]}
              <span>{assets.filter((asset) => asset.space === item).length}</span>
            </button>
          ))}
        </div>
        <SearchBox label="搜索文件" value={query} onChange={setQuery} />
      </div>
      <div className="asset-browser">
        <aside className={`asset-folder-sidebar${foldersOpen ? ' is-open' : ''}`}>
          <h2 className="asset-folder-heading">文件夹</h2>
          <button
            className="asset-folder-toggle"
            aria-expanded={foldersOpen}
            aria-controls="asset-folder-list"
            onClick={() => setFoldersOpen(!foldersOpen)}
          >
            <FolderOpen size={17} />
            <span>文件夹 · {folder === 'all' ? '全部文件' : folder}</span>
            <ChevronRight size={15} />
          </button>
          <nav className="asset-folders" id="asset-folder-list" aria-label="资产文件夹">
            <button
              className="asset-folder-all"
              aria-pressed={folder === 'all'}
              onClick={() => {
                setFolder('all');
                setFoldersOpen(false);
              }}
            >
              <LayoutGrid size={17} />
              <span className="asset-folder-name">全部文件</span>
              <span className="asset-folder-count">{spaceAssets.length}</span>
            </button>
            {folders.map((item) => (
              <button
                key={item}
                aria-pressed={folder === item}
                onClick={() => {
                  setFolder(item);
                  setFoldersOpen(false);
                }}
              >
                <Folder size={17} className="asset-folder-icon" />
                <span className="asset-folder-name">{item}</span>
                <span className="asset-folder-count">
                  {spaceAssets.filter((asset) => asset.folder === item).length}
                </span>
              </button>
            ))}
          </nav>
        </aside>
        <section className="asset-files" aria-label={`${spaceLabels[space]}文件`}>
          <div className="asset-files-heading">
            <div className="library-section-title">
              {folder !== 'all' && (
                <button
                  className="library-back"
                  aria-label="返回全部文件"
                  onClick={() => setFolder('all')}
                >
                  <ArrowLeft size={16} />
                </button>
              )}
              {folder === 'all' ? '全部文件' : folder}
              <span>{filtered.length}</span>
            </div>
            <div className="library-toolbar-controls">
              <button
                className="library-favorite-filter"
                aria-pressed={favorites}
                onClick={() => setFavorites(!favorites)}
              >
                <Star size={15} fill={favorites ? 'currentColor' : 'none'} />
                收藏
              </button>
              <SortSelect value={sort} onChange={setSort} />
              <div className="library-segmented" aria-label="文件视图">
                <button
                  aria-label="网格视图"
                  aria-pressed={view === 'grid'}
                  onClick={() => setView('grid')}
                >
                  <LayoutGrid size={16} />
                </button>
                <button
                  aria-label="列表视图"
                  aria-pressed={view === 'list'}
                  onClick={() => setView('list')}
                >
                  <List size={17} />
                </button>
              </div>
            </div>
          </div>
          <div className="asset-type-filters" aria-label="文件类型">
            {assetKinds.map((item) => (
              <button
                key={item.id}
                aria-pressed={kind === item.id}
                onClick={() => setKind(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {view === 'list' && filtered.length > 0 && (
            <div className="asset-list-header">
              <span>文件名称</span>
              <span>大小</span>
              <span>更新时间</span>
              <span />
            </div>
          )}
          <div className={`library-asset-${view}`}>
            {filtered.map((asset) => {
              const Icon = typeIcons[asset.kind];
              return (
                <div className="library-asset-card" key={asset.id}>
                  <button
                    className="library-asset-open"
                    onClick={() => setSelected(asset)}
                    aria-label={`预览 ${asset.name}`}
                  >
                    {view === 'grid' ? (
                      <div className="library-thumbnail">
                        <AssetArtwork asset={asset} />
                        <span className="asset-extension">
                          {asset.name.split('.').pop()?.toUpperCase()}
                        </span>
                        <span className="asset-open-hint">
                          <ArrowUpRight size={17} />
                        </span>
                      </div>
                    ) : (
                      <span className={`asset-list-icon kind-${asset.kind}`}>
                        <Icon size={22} />
                      </span>
                    )}
                    <span className="library-asset-info">
                      <strong title={asset.name}>{asset.name}</strong>
                      <span>
                        {view === 'grid' ? (
                          <>
                            <Icon size={12} />
                            {asset.size}
                            <span className="library-dot">·</span>
                            {asset.updated.slice(5).replace('-', '/')}
                          </>
                        ) : (
                          asset.folder
                        )}
                      </span>
                    </span>
                  </button>
                  {view === 'list' && (
                    <>
                      <span className="asset-list-size">{asset.size}</span>
                      <time dateTime={asset.updated}>
                        {asset.updated.slice(5).replace('-', '/')}
                      </time>
                    </>
                  )}
                  <Favorite
                    active={asset.starred}
                    title={asset.name}
                    onClick={() => toggleStar(asset.id)}
                  />
                </div>
              );
            })}
          </div>
          {!filtered.length && <LibraryEmpty title="没有找到相关文件" onReset={reset} />}
        </section>
      </div>
      {selected && <AssetPreview asset={selected} onClose={() => setSelected(null)} />}
      {uploading && (
        <ImportDialog
          kind="asset"
          destination={`${spaceLabels[space]} / ${folder === 'all' ? '未分类' : folder}`}
          onClose={() => setUploading(false)}
          onImport={async (files) => {
            if (mode === 'real') {
              for (const file of files) {
                const form = new FormData(); form.set('file', file); form.set('space', space);
                form.set('folder', folder === 'all' ? '未分类' : folder);
                const saved = await api.post<LibraryAsset>(path, form);
                setAssets(current => [saved, ...current]);
              }
              setKind('all'); setFavorites(false); setQuery(''); setUploading(false);
              setNotice(`已保存 ${files.length} 个文件到${spaceLabels[space]}`);
              return;
            }
            const added = files.map((file): LibraryAsset => {
              const url = URL.createObjectURL(file);
              urls.current.push(url);
              return {
                id: crypto.randomUUID(),
                name: file.name,
                kind: detectKind(file),
                space,
                folder: folder === 'all' ? '未分类' : folder,
                size:
                  file.size < 1024 * 1024
                    ? `${Math.max(1, Math.round(file.size / 1024))} KB`
                    : `${(file.size / 1024 / 1024).toFixed(1)} MB`,
                updated: new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }),
                starred: false,
                art: 'notes',
                url,
                mime: file.type,
                file,
              };
            });
            setAssets((current) => [...added, ...current]);
            setKind('all');
            setFavorites(false);
            setQuery('');
            setUploading(false);
            setNotice(`已添加 ${added.length} 个文件到当前演示`);
          }}
        />
      )}
    </div>
  );
}

export function StaticLibrary({ page, session }: { page: 'knowledge' | 'assets'; session: Session }) {
  return page === 'knowledge' ? <WikiLibrary key={session.user.id} session={session} /> : <AssetLibrary key={session.user.id} session={session} />;
}

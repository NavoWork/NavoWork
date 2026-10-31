import { useEffect, useState } from 'react';
import { Check, Download, FileText, LockKeyhole, Send, Save } from 'lucide-react';
import { api } from '../api';
import type { Inquiry } from '../api/types';
import { ErrorNotice, Loading } from '../components/ui';
import { getCanvasFile, type WorkspaceDocument, type WorkspaceFile } from './inquiry-canvas-model';

export function FilePreview({
  file,
  base,
  scope,
  compact = false,
}: {
  file: WorkspaceFile;
  base: string;
  scope: string;
  compact?: boolean;
}) {
  const [url, setUrl] = useState('');
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<unknown>();
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let cancelled = false;
    let objectUrl = '';
    setUrl('');
    setText(null);
    setError(undefined);
    const load = file.assetId
      ? api.download(
          `${base}/assets/${encodeURIComponent(file.assetId)}/versions/${file.version}/download`,
        )
      : getCanvasFile(scope, file.id);
    load
      .then(async (blob) => {
        if (cancelled) return;
        if (!blob) throw new Error('文件内容未保存在此浏览器中，请重新导入。');
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
        if (file.mediaType.startsWith('text/')) {
          const content = await blob.slice(0, 200000).text();
          if (!cancelled) setText(content);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [file.id, file.assetId, file.version, file.mediaType, base, scope, retry]);
  if (compact)
    return url && file.mediaType.startsWith('image/') ? (
      <img className="ic-file-thumbnail" src={url} alt={file.title} draggable={false} />
    ) : url && file.mediaType === 'application/pdf' ? (
      <iframe
        className="ic-file-thumbnail ic-pdf-thumbnail"
        title={`${file.title} PDF 节点预览`}
        src={`${url}#page=1&view=FitH&toolbar=0&navpanes=0`}
        tabIndex={-1}
      />
    ) : text !== null ? (
      <p className="ic-card-preview">{text}</p>
    ) : (
      <div className="ic-file-placeholder">
        <FileText size={32} />
        <span>
          {file.mediaType === 'application/pdf'
            ? 'PDF'
            : file.name.split('.').pop()?.toUpperCase() || 'FILE'}
        </span>
        <small>
          {error ? '内容暂不可用 · 双击查看详情' : `${Math.ceil(file.size / 1024)} KB · 双击预览`}
        </small>
      </div>
    );
  return (
    <div className="ic-file-view">
      {error ? (
        <ErrorNotice error={error} onRetry={() => setRetry((v) => v + 1)} />
      ) : !url ? (
        <Loading label="正在读取文件" />
      ) : (
        <>
          <a className="button" href={url} download={file.name}>
            <Download size={14} />
            下载原文件
          </a>
          {file.mediaType.startsWith('image/') ? (
            <img className="ic-full-image" src={url} alt={file.title} />
          ) : file.mediaType === 'application/pdf' ? (
            <iframe title={`${file.title} PDF 预览`} src={url} />
          ) : text !== null ? (
            <>
              <pre className="ic-source-content">{text}</pre>
              {file.size > 200000 && <small>仅预览前 200 KB，完整内容可下载原文件。</small>}
            </>
          ) : (
            <div className="ic-file-placeholder">
              <FileText size={40} />
              <p>此格式可下载后打开。</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function OriginalDocument({
  inquiry,
  path,
  readOnly,
  value,
  onChange,
  onSaved,
}: {
  inquiry: Inquiry;
  path: string;
  readOnly: boolean;
  value: string;
  onChange: (value?: string) => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const locked = readOnly || inquiry.currentRevision > 0;
  async function save() {
    if (locked || busy || !value.trim()) return;
    setBusy(true);
    setError(undefined);
    setSaved(false);
    try {
      await api.patch(path, { originalText: value, metadataVersion: inquiry.metadataVersion });
      await onSaved();
      onChange(undefined);
      setSaved(true);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="ic-document-sheet">
      <div className="ic-document-eyebrow">CUSTOMER INQUIRY</div>
      <h2>客户原始询盘</h2>
      <p className="ic-document-subtitle">{inquiry.customer}</p>
      <div className="ic-document-status">
        {locked ? (
          <>
            <LockKeyhole size={13} />
            原文留档 · 补充内容请在沟通页提交
          </>
        ) : value !== inquiry.originalText ? (
          '原文有修改，保存后用于首次处理'
        ) : (
          <>
            <Check size={13} />
            已保存原文
          </>
        )}
      </div>
      <label className="sr-only" htmlFor={`original-${inquiry.id}`}>
        编辑客户原始询盘
      </label>
      <textarea
        id={`original-${inquiry.id}`}
        className="ic-document-text ic-original-text"
        value={locked ? inquiry.originalText : value}
        readOnly={locked}
        disabled={busy}
        maxLength={20000}
        onChange={(e) => {
          onChange(e.target.value);
          setSaved(false);
        }}
      />
      <ErrorNotice error={error} />
      {!locked && (
        <div className="ic-document-actions">
          <span>{saved ? '原文已保存' : '仅修改当前询盘'}</span>
          <button
            className="button button-primary"
            disabled={busy || !value.trim() || value === inquiry.originalText}
            onClick={() => void save()}
          >
            <Save size={13} />
            {busy ? '保存中…' : '保存原文'}
          </button>
        </div>
      )}
    </div>
  );
}

export function WorkingDocument({
  doc,
  value,
  onChange,
  readOnly,
  onInstruction,
}: {
  doc: WorkspaceDocument;
  value: string;
  onChange: (text?: string) => void;
  readOnly: boolean;
  onInstruction: (instruction: string) => void;
}) {
  return (
    <div className="ic-document-sheet">
      <div className="ic-document-eyebrow">
        {doc.kind === 'quote'
          ? 'PROPOSAL & QUOTATION'
          : doc.kind === 'risks'
            ? 'RISKS & FOLLOW-UPS'
            : 'CUSTOMER REQUIREMENTS'}
      </div>
      <h2>{doc.title}</h2>
      <p className="ic-document-subtitle">
        基于 V{doc.revision?.number} 整理，编辑后可交给助手更新业务版本。
      </p>
      <div className="ic-document-status">
        <FileText size={13} />
        {value !== doc.text ? '本机工作草稿 · 尚未生成新业务版本' : '版本内容 · 可编辑为工作草稿'}
      </div>
      <textarea
        className="ic-document-text"
        aria-label={`编辑${doc.title}`}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
      />
      <div className="ic-document-actions">
        <button
          className="button button-ghost"
          disabled={readOnly || value === doc.text}
          onClick={() => onChange(undefined)}
        >
          还原版本内容
        </button>
        <button
          className="button button-primary"
          disabled={readOnly || !value.trim()}
          onClick={() =>
            onInstruction(
              `请根据以下「${doc.title}」工作草稿重新核对需求、方案、报价和回复，保留未确认项：\n\n${value}`,
            )
          }
        >
          <Send size={13} />
          交给助手更新版本
        </button>
      </div>
    </div>
  );
}

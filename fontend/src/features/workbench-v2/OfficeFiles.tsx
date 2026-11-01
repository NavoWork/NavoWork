import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../api';
import { ErrorNotice } from '../../components/ui';
import './office-files.css';

interface FileVersion {
  documentId: string;
  version: number;
  sha256: string;
  name: string;
  format: string;
  downloadUrl: string;
  fieldMapping?: {
    status: string;
    coverageComplete: boolean;
    reason?: string;
    changedFields?: string[];
  };
}
interface Cell {
  address: string;
  value: string | number | boolean | null;
  display: string | number | boolean | null;
  formula: boolean;
}
interface OfficeDocument extends FileVersion {
  preview: {
    format: string;
    notice: string;
    paragraphs?: { index: number; text: string; bold: boolean; italic: boolean }[];
    tables?: { index: number; rows: string[][] }[];
    images?: { index: number; url: string }[];
    sheets?: { name: string; rows: Cell[][] }[];
  };
  versions: FileVersion[];
}
interface Files {
  sources: { fileId: string; name: string }[];
  documents: FileVersion[];
  images: { fileId: string; name: string }[];
}
type Edit = Record<string, unknown>;

/** Structured preview is rendered with React text nodes; source HTML is never executed. */
export function OfficeFiles({
  path,
  revision,
  disabled,
  onChanged,
}: {
  path: string;
  revision: number;
  disabled: boolean;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const [files, setFiles] = useState<Files>({ sources: [], documents: [], images: [] });
  const [document, setDocument] = useState<OfficeDocument>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState('');
  const [pending, setPending] = useState<Record<string, Edit>>({});
  const [sheet, setSheet] = useState('');
  const [image, setImage] = useState('');
  const [bold, setBold] = useState(false);
  const [paragraphStyle, setParagraphStyle] = useState('Normal');
  const [copyRange, setCopyRange] = useState('A1:B2');
  const [copyTarget, setCopyTarget] = useState('D1');
  const [selectedCell, setSelectedCell] = useState<Cell>();
  const [cellText, setCellText] = useState('');
  const [formula, setFormula] = useState(false);
  const [notice, setNotice] = useState('');
  const endpoint = `${path}/workbench/office`;

  async function refresh() {
    setFiles(await api.get<Files>(endpoint));
  }
  useEffect(() => {
    setDocument(undefined);
    setPending({});
  }, [endpoint]);
  useEffect(() => { void refresh().catch(setError); }, [endpoint, revision]);
  async function open(id: string, version?: number) {
    const value = await api.get<OfficeDocument>(
      `${endpoint}/${id}${version ? `/versions/${version}` : ''}`,
    );
    setDocument(value);
    setPending({});
    setSheet(value.preview.sheets?.[0]?.name || '');
    setSelectedCell(undefined);
  }
  async function operate(action: () => Promise<void>) {
    setBusy(true);
    setError(undefined);
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function createCopy() {
    const created = await api.post<FileVersion>(endpoint, { fileId: source });
    await refresh();
    await open(created.documentId);
  }
  async function save() {
    if (!document) return;
    const updated = await api.put<FileVersion>(`${endpoint}/${document.documentId}`, {
      baseVersion: document.version,
      baseHash: document.sha256,
      operations: Object.values(pending),
    });
    await refresh();
    await open(updated.documentId);
    setNotice(
      updated.fieldMapping?.status === 'mapped'
        ? `已保存 V${updated.version}，已更新对应业务字段并触发相关成果检查；请查看跨文件同步结果。`
        : `已保存 V${updated.version}。原件保持不变；${updated.fieldMapping?.reason || '业务影响待复核。'}`,
    );
    await queryClient.invalidateQueries({ queryKey: ['case-propagation', path] });
    onChanged();
  }
  function stage(key: string, value: Edit) {
    setPending((old) => ({ ...old, [key]: value }));
  }
  const currentSheet = document?.preview.sheets?.find((item) => item.name === sheet);
  const readonly =
    disabled ||
    busy ||
    (!!document &&
      document.version !== Math.max(...document.versions.map((version) => version.version)));
  const queueCell = () => {
    if (!selectedCell) return;
    const value = formula
      ? cellText
      : cellText === ''
        ? null
        : /^-?\d+(\.\d+)?$/.test(cellText)
          ? Number(cellText)
          : cellText;
    stage(`cell:${sheet}:${selectedCell.address}`, {
      op: 'set_cell',
      sheet,
      cell: selectedCell.address,
      value,
      formula,
      bold,
    });
    setSelectedCell({ ...selectedCell, value, formula });
  };

  return (
    <section className="office-files" aria-label="文件编辑与预览">
      <details>
        <summary>
          文件编辑与预览 <small>DOCX / XLSX · 独立工作副本</small>
        </summary>
        <ErrorNotice error={error} onRetry={() => setError(undefined)} />
        <div className="office-toolbar">
          <select
            aria-label="选择 Office 原件"
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="">选择已上传文件或已生成成果</option>
            {files.sources.map((file) => (
              <option key={file.fileId} value={file.fileId}>
                {file.name}
              </option>
            ))}
          </select>
          <button
            className="button"
            disabled={!source || disabled || busy}
            onClick={() => void operate(createCopy)}
          >
            创建工作副本
          </button>
          <select
            aria-label="打开工作副本"
            value={document?.documentId || ''}
            onChange={(event) => event.target.value && void operate(() => open(event.target.value))}
          >
            <option value="">打开工作副本</option>
            {files.documents.map((file) => (
              <option key={file.documentId} value={file.documentId}>
                {file.name} · V{file.version}
              </option>
            ))}
          </select>
        </div>
        {!files.sources.length && (
          <p className="office-hint">在“资料”上传 DOCX/XLSX 后，即可创建可编辑的工作副本。</p>
        )}
        {notice && <p role="status">{notice}</p>}
        {document && (
          <>
            <div className="office-toolbar">
              <strong>{document.name}</strong>
              <select
                aria-label="文件版本"
                value={document.version}
                onChange={(event) =>
                  void operate(() => open(document.documentId, Number(event.target.value)))
                }
              >
                {document.versions.map((version) => (
                  <option key={version.version} value={version.version}>
                    V{version.version}
                  </option>
                ))}
              </select>
              <a className="button" href={document.downloadUrl}>
                下载 {document.format.toUpperCase()} V{document.version}
              </a>
              <a className="button" href={`${document.downloadUrl.replace(/\/download$/, '')}/pdf`}>
                内容预览 PDF
              </a>
              <button
                className="button button-primary"
                disabled={readonly || !Object.keys(pending).length}
                onClick={() => void operate(save)}
              >
                保存新版本 ({Object.keys(pending).length})
              </button>
              {!!Object.keys(pending).length && (
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void operate(() => open(document.documentId, document.version))}
                >
                  放弃修改
                </button>
              )}
            </div>
            <p className="office-hint">{document.preview.notice}</p>
            {document.fieldMapping?.status === 'registered' && (
              <p className="office-hint">
                此文件已登记规格字段映射。修改对应值后，保存会自动更新业务规格及受影响成果。
              </p>
            )}
            {document.fieldMapping?.reason && (
              <p role="alert" className="office-hint">
                {document.fieldMapping.reason}
              </p>
            )}
            {readonly && !disabled && (
              <p className="office-hint">历史版本仅供查看，请打开最新版本后编辑。</p>
            )}
            {document.format === 'docx' ? (
              <div className="office-page" key={`${document.documentId}:${document.version}`}>
                <div className="office-toolbar">
                  <label>
                    <input
                      type="checkbox"
                      checked={bold}
                      onChange={(event) => setBold(event.target.checked)}
                    />
                    加粗新修改
                  </label>
                  <select
                    aria-label="段落样式"
                    value={paragraphStyle}
                    onChange={(event) => setParagraphStyle(event.target.value)}
                  >
                    <option value="Normal">正文</option>
                    <option value="Title">标题</option>
                    <option value="Heading 1">一级标题</option>
                    <option value="Heading 2">二级标题</option>
                  </select>
                </div>
                {document.preview.paragraphs?.map((paragraph) => (
                  <textarea
                    key={`${document.version}:${paragraph.index}`}
                    aria-label={`段落 ${paragraph.index + 1}`}
                    rows={Math.max(1, Math.min(8, paragraph.text.split('\n').length))}
                    disabled={readonly}
                    defaultValue={paragraph.text}
                    style={{
                      fontWeight: paragraph.bold ? 'bold' : undefined,
                      fontStyle: paragraph.italic ? 'italic' : undefined,
                    }}
                    onChange={(event) =>
                      stage(`paragraph:${paragraph.index}`, {
                        op: 'set_paragraph',
                        index: paragraph.index,
                        text: event.target.value,
                        bold,
                        style: paragraphStyle,
                      })
                    }
                  />
                ))}
                {document.preview.tables?.map((table) => (
                  <table key={table.index}>
                    <tbody>
                      {table.rows.map((row, r) => (
                        <tr key={r}>
                          {row.map((cell, c) => (
                            <td key={c}>
                              <textarea
                                aria-label={`表 ${table.index + 1} 行 ${r + 1} 列 ${c + 1}`}
                                disabled={readonly}
                                defaultValue={cell}
                                onChange={(event) =>
                                  stage(`table:${table.index}:${r}:${c}`, {
                                    op: 'set_table_cell',
                                    table: table.index,
                                    row: r,
                                    column: c,
                                    text: event.target.value,
                                  })
                                }
                              />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}
                <textarea
                  aria-label="追加段落"
                  placeholder="追加新段落"
                  disabled={readonly}
                  onChange={(event) =>
                    event.target.value
                      ? stage('append', {
                          op: 'append_paragraph',
                          text: event.target.value,
                          bold,
                          style: paragraphStyle,
                        })
                      : setPending(({ append: _append, ...rest }) => rest)
                  }
                />
                <button
                  className="button"
                  disabled={readonly}
                  onClick={() => stage('add-table', { op: 'add_table', rows: 2, columns: 2 })}
                >
                  插入 2×2 表格
                </button>
                <div className="office-toolbar">
                  <select
                    aria-label="选择插入图片"
                    value={image}
                    onChange={(event) => setImage(event.target.value)}
                  >
                    <option value="">选择已上传图片</option>
                    {files.images.map((file) => (
                      <option key={file.fileId} value={file.fileId}>
                        {file.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button"
                    disabled={!image || readonly}
                    onClick={() =>
                      stage('add-image', { op: 'add_picture', fileId: image, width: 3 })
                    }
                  >
                    插入图片
                  </button>
                </div>
                <div className="office-images">
                  {document.preview.images?.map((picture) => (
                    <figure key={picture.index}>
                      <img src={picture.url} alt={`文档图片 ${picture.index + 1}`} />
                      <button
                        className="button"
                        disabled={!image || readonly}
                        onClick={() =>
                          stage(`replace:${picture.index}`, {
                            op: 'replace_picture',
                            index: picture.index,
                            fileId: image,
                          })
                        }
                      >
                        替换为已选图片
                      </button>
                    </figure>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="office-toolbar">
                  {document.preview.sheets?.map((item) => (
                    <button
                      key={item.name}
                      className={`button ${item.name === sheet ? 'button-primary' : ''}`}
                      onClick={() => {
                        setSheet(item.name);
                        setSelectedCell(undefined);
                      }}
                    >
                      {item.name}
                    </button>
                  ))}
                </div>
                {selectedCell && (
                  <div className="office-toolbar">
                    <strong>
                      {sheet}!{selectedCell.address}
                    </strong>
                    <input
                      aria-label="单元格内容"
                      disabled={readonly}
                      value={cellText}
                      onChange={(event) => setCellText(event.target.value)}
                    />
                    <label>
                      <input
                        type="checkbox"
                        disabled={readonly}
                        checked={formula}
                        onChange={(event) => setFormula(event.target.checked)}
                      />
                      公式
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={bold}
                        onChange={(event) => setBold(event.target.checked)}
                      />
                      加粗
                    </label>
                    <button className="button" disabled={readonly} onClick={queueCell}>
                      应用单元格修改
                    </button>
                  </div>
                )}
                <div className="office-toolbar">
                  <input
                    aria-label="复制区域"
                    value={copyRange}
                    onChange={(event) => setCopyRange(event.target.value)}
                  />
                  <input
                    aria-label="粘贴目标单元格"
                    value={copyTarget}
                    onChange={(event) => setCopyTarget(event.target.value)}
                  />
                  <button
                    className="button"
                    disabled={readonly}
                    onClick={() =>
                      stage(`copy:${sheet}`, {
                        op: 'copy_range',
                        sheet,
                        sourceRange: copyRange,
                        cell: copyTarget,
                      })
                    }
                  >
                    复制粘贴区域
                  </button>
                </div>
                <div className="office-grid">
                  <table>
                    <tbody>
                      {currentSheet?.rows.map((row, r) => (
                        <tr key={r}>
                          <th>{r + 1}</th>
                          {row.map((cell) => {
                            const changed = pending[`cell:${sheet}:${cell.address}`];
                            return (
                              <td key={cell.address}>
                                <button
                                  disabled={readonly}
                                  aria-label={`${sheet} ${cell.address}`}
                                  className={changed ? 'office-cell changed' : 'office-cell'}
                                  title={cell.formula ? String(cell.value) : cell.address}
                                  onClick={() => {
                                    setSelectedCell(cell);
                                    setCellText(String(changed?.value ?? cell.value ?? ''));
                                    setFormula(Boolean(changed?.formula ?? cell.formula));
                                  }}
                                >
                                  {String(changed?.value ?? cell.display ?? '') || '\u00a0'}
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {currentSheet && (
                  <div className="office-toolbar">
                    <button
                      className="button"
                      disabled={readonly}
                      onClick={() =>
                        stage(`row:${sheet}`, {
                          op: 'insert_blank_rows',
                          sheet,
                          index: currentSheet.rows.length + 1,
                        })
                      }
                    >
                      添加空行
                    </button>
                    <button
                      className="button"
                      disabled={readonly}
                      onClick={() =>
                        stage(`column:${sheet}`, {
                          op: 'insert_blank_cols',
                          sheet,
                          index: (currentSheet.rows[0]?.length || 0) + 1,
                        })
                      }
                    >
                      添加空列
                    </button>
                    <button
                      className="button"
                      disabled={readonly || !selectedCell}
                      onClick={() =>
                        stage(`delete-row:${sheet}`, {
                          op: 'delete_rows',
                          sheet,
                          index: Number(selectedCell?.address.match(/[0-9]+/)?.[0] || 1),
                        })
                      }
                    >
                      删除选中行
                    </button>
                    <button
                      className="button"
                      disabled={readonly || !selectedCell}
                      onClick={() => {
                        const letters = selectedCell?.address.match(/[A-Z]+/)?.[0] || 'A';
                        const column = [...letters].reduce(
                          (n, letter) => n * 26 + letter.charCodeAt(0) - 64,
                          0,
                        );
                        stage(`delete-column:${sheet}`, {
                          op: 'delete_cols',
                          sheet,
                          index: column,
                        });
                      }}
                    >
                      删除选中列
                    </button>
                    <small>含公式的工作表不执行结构变更。</small>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </details>
    </section>
  );
}

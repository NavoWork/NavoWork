import { Save, RefreshCw } from 'lucide-react';
import type { WorkspaceDocument } from './inquiry-canvas-model';

/** A compact shared view of the versioned node output, including actual artwork. */
export function InquiryStageDocument({ doc, originalText, disabled, prompt, onPromptChange, onChange, onSave, onGenerate }: {
  doc: WorkspaceDocument; originalText: string; disabled: boolean;
  prompt: string; onPromptChange: (text?: string) => void;
  onChange: (text?: string) => void; onSave?: (text: string) => void;
  onGenerate?: (prompt?: string) => void;
}) {
  const isImage = doc.kind === 'design';
  return <div className="ic-document-sheet ic-stage-document">
    <div className="ic-stage-heading"><h2>{doc.title}</h2>
      {!isImage && onGenerate && <button className="button" disabled={disabled} onClick={() => onGenerate()}>依据现有资料生成</button>}
    </div>
    <p className="ic-document-subtitle">{doc.caption} · 本地 mock</p>
    {isImage ? <div className="ic-design-editor">
      <div>{doc.imageUrl ? <figure className="ic-design-image">
        <img src={doc.imageUrl} alt="当前询盘的产品设计概念图" />
        <figcaption>本地 mock 预览 <a href={doc.imageUrl} download>下载图片</a></figcaption>
      </figure> : <p className="ic-stage-empty">填写 Prompt 后生成图片预览</p>}</div>
      <div className="ic-design-controls">
      {doc.imagePrompt && <details className="ic-image-current-prompt"><summary>查看当前图片的生成 prompt</summary><p>{doc.imagePrompt}</p></details>}
      <label className="ic-prompt-label" htmlFor={`image-prompt-${doc.id}`}>图片生成 Prompt</label>
      <textarea id={`image-prompt-${doc.id}`} className="ic-document-text ic-image-prompt" aria-label="图片生成 Prompt"
        value={prompt} readOnly={disabled} maxLength={6000} placeholder="描述希望生成的产品、材质、颜色及修改要求"
        onChange={(event) => onPromptChange(event.target.value)} />
      <p className="ic-document-subtitle">本地 mock 使用预置图片演示重新生成，保存修改后的 prompt 和新图片版本。</p>
      <div className="ic-document-actions">
        <button className="button button-ghost" disabled={disabled || prompt === (doc.imagePrompt || '')} onClick={() => onPromptChange(undefined)}>恢复当前图片 Prompt</button>
        {onGenerate && <button className="button button-primary" disabled={disabled || !prompt.trim()} onClick={() => onGenerate(prompt)}><RefreshCw size={14} />{disabled ? '处理中…' : doc.imageUrl ? '重新生成图片（Mock）' : '生成图片（Mock）'}</button>}
      </div>
      </div>
    </div> : <>
      {!!doc.comparisons?.length && <div className="ic-competitor-grid">
        {doc.comparisons.map((item) => <article key={item.name}>
          <h3>{item.name}</h3><strong>{item.price}</strong>
          <p>{item.material}</p><p>{item.features}</p>
        </article>)}
      </div>}
      <textarea className="ic-document-text" aria-label={`编辑${doc.title}`} value={doc.text} readOnly={disabled}
        placeholder="填写节点内容，未知信息可保留待确认" maxLength={50000} onChange={(event) => onChange(event.target.value)} />
      <div className="ic-document-actions">
        <button className="button button-ghost" disabled={disabled || doc.text === originalText} onClick={() => onChange(undefined)}>撤销未提交编辑</button>
        <button className="button button-primary" disabled={disabled || !doc.text.trim() || doc.text === originalText || !onSave} onClick={() => onSave?.(doc.text)}><Save size={14} />{disabled ? '处理中…' : '保存修改'}</button>
      </div>
    </>}
  </div>;
}

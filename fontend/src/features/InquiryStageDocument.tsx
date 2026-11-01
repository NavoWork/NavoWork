import type { WorkspaceDocument } from './inquiry-canvas-model';

/** A compact shared view of the versioned node output, including actual artwork. */
export function InquiryStageDocument({ doc, disabled, onGenerate }: {
  doc: WorkspaceDocument; disabled: boolean; onGenerate?: () => void;
}) {
  return <div className="ic-document-sheet ic-stage-document">
    <div className="ic-stage-heading"><h2>{doc.title}</h2>
      {onGenerate && <button className="button button-primary" disabled={disabled} onClick={onGenerate}>依据现有资料生成</button>}
    </div>
    {!doc.hasContent && !doc.text ? <p className="ic-stage-empty">等待生成</p> : <>
      {doc.imageUrl && <figure className="ic-design-image">
        <img src={doc.imageUrl} alt="当前询盘的产品设计概念图" />
        <figcaption>预置演示图 <a href={doc.imageUrl} download>下载图片</a></figcaption>
      </figure>}
      {!!doc.comparisons?.length && <div className="ic-competitor-grid">
        {doc.comparisons.map((item) => <article key={item.name}>
          <h3>{item.name}</h3><strong>{item.price}</strong>
          <p>{item.material}</p><p>{item.features}</p>
        </article>)}
      </div>}
      <div className="ic-stage-text">{doc.comparisons?.length ? doc.text.slice(doc.text.indexOf('设计建议')) : doc.text}</div>
    </>}
  </div>;
}

import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  LayoutGrid,
  TriangleAlert,
} from 'lucide-react';
import type { Revision, SourceRef } from '../api/types';
import { EmptyState } from '../components/ui';
import { MaterialsPanel } from './inquiry-materials';
import type { DraftState } from './inquiry-replies';
import { money } from './inquiry-canvas-model';

export function InquiryResult({
  revision,
  draftState,
  draftsPending,
  base,
  path,
  scope,
  readOnly,
  busy,
  history,
  selectedAssets,
  onSelectAssets,
  onSource,
  openDocument,
  onAccept,
  onSave,
  saved,
  deferred,
  onDefer,
}: {
  revision: Revision;
  draftState: DraftState;
  draftsPending: boolean;
  base: string;
  path: string;
  scope: string;
  readOnly: boolean;
  busy: boolean;
  history: boolean;
  selectedAssets: string[] | null;
  onSelectAssets: (ids: string[] | null) => void;
  onSource: (source: SourceRef) => void;
  openDocument: (id: string) => void;
  onAccept: () => void;
  onSave: () => void;
  saved: boolean;
  deferred: boolean;
  onDefer: () => void;
}) {
  const canWrite = !readOnly && !busy;
  const errors = revision.checks.filter((check) => check.status === 'error').length;
  const openRisks = revision.risks.filter((risk) => risk.status !== 'resolved');
  return (
    <section className="iw-answer-result" aria-label={`V${revision.number} 本轮成果`}>
      <header className="iw-answer-result-head">
        <span>
          <FileText size={15} />
          本轮成果
        </span>
        <span className="iw-version">V{revision.number}</span>
      </header>
      <p className="iw-answer-summary">
        {revision.quote
          ? `${revision.quote.quantity.toLocaleString()} 件 · 商品小计 ${money(revision.quote.goodsSubtotalMinor)}`
          : '已整理客户需求与方案'}
        {' · '}
        {openRisks.length ? `${openRisks.length} 项待确认` : '暂无待确认项'}
      </p>
      <div className={`iw-answer-check ${errors ? 'has-errors' : ''}`}>
        {errors ? <TriangleAlert size={13} /> : <Check size={13} />}
        <span>
          {errors
            ? `${errors} 项内容核对未通过，请先调整答案`
            : '已完成内容核对，请确认答案是否符合预期'}
        </span>
      </div>
      <details className="iw-result-section">
        <summary>
          需求与风险
          <ChevronRight size={14} />
        </summary>
        <div className="iw-result-section-body">
          <div className="iw-section-heading">
            <span className="iw-kicker">CUSTOMER REQUIREMENTS</span>
            <h3>客户要什么</h3>
          </div>
          <dl className="iw-facts">
            {[
              ['产品', revision.requirements.requestedProduct],
              [
                '需求数量',
                revision.requirements.quantity == null
                  ? null
                  : `${revision.requirements.quantity} 件`,
              ],
              ['规格', revision.requirements.specification],
              ['目的地', revision.requirements.destination],
              ['期望到货', revision.requirements.requestedArrival],
              ['定制要求', revision.requirements.customization],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd className={!value ? 'unknown' : ''}>{value || '待确认'}</dd>
              </div>
            ))}
          </dl>
          {revision.requirements.missingFields.length > 0 && (
            <div className="iw-note">
              待补信息：{revision.requirements.missingFields.join('、')}
            </div>
          )}
          <div className="iw-section-heading">
            <span className="iw-kicker">OPEN QUESTIONS</span>
            <h3>核对后，再向前一步</h3>
          </div>
          <div className="iw-risk-list">
            {revision.risks.length ? (
              revision.risks.map((r) => (
                <article key={r.id}>
                  <TriangleAlert size={16} />
                  <div>
                    <div>
                      <strong>{r.message}</strong>
                      <span>
                        {r.status === 'resolved'
                          ? '已解决'
                          : r.severity === 'error'
                            ? '阻断'
                            : '待确认'}
                      </span>
                    </div>
                    <p>{r.suggestedAction}</p>
                  </div>
                </article>
              ))
            ) : (
              <p className="iw-muted">此版本没有返回风险项。</p>
            )}
          </div>
          <div className="iw-inline-note">
            <BookOpen size={14} />
            客户要求与商家事实分开保留，备选方案需要客户确认。
          </div>
        </div>
      </details>
      <details className="iw-result-section">
        <summary>
          方案与报价
          <ChevronRight size={14} />
        </summary>
        <div className="iw-result-section-body">
          <div className="iw-section-heading">
            <span className="iw-kicker">PROPOSAL & QUOTATION</span>
            <h3>把方案的边界说清楚</h3>
          </div>
          <div className="iw-proposal">
            <div>
              <span>客户原要求</span>
              <strong>{revision.proposal.requestedSku || '尚未确定 SKU'}</strong>
            </div>
            <ArrowRight size={16} />
            <div>
              <span>当前方案</span>
              <strong>{revision.proposal.selectedSku || '等待选择方案'}</strong>
            </div>
            <span className="iw-proposal-state">
              {revision.proposal.status === 'accepted'
                ? '已记录客户接受'
                : revision.proposal.status === 'proposed'
                  ? '备选 · 待客户确认'
                  : '需求待准备'}
            </span>
          </div>
          {revision.proposal.differences.map((d) => (
            <p className="iw-note" key={d}>
              {d}
            </p>
          ))}
          {revision.quote ? (
            <>
              <div className="iw-quote-card">
                <div className="iw-quote-top">
                  <span>商品小计 · USD</span>
                  <span>草稿报价</span>
                </div>
                <strong className="iw-quote-amount">
                  {money(revision.quote.goodsSubtotalMinor)}
                </strong>
                <p>
                  {revision.quote.quantity.toLocaleString()} 件 ×{' '}
                  {money(revision.quote.unitPriceMinor)} / 件
                </p>
                <dl className="iw-costs">
                  <div>
                    <dt>运费</dt>
                    <dd>{money(revision.quote.freightMinor)}</dd>
                  </div>
                  <div>
                    <dt>税费</dt>
                    <dd>{money(revision.quote.taxMinor)}</dd>
                  </div>
                  <div>
                    <dt>最终总额</dt>
                    <dd>{money(revision.quote.totalMinor)}</dd>
                  </div>
                </dl>
              </div>
              <dl className="iw-facts">
                <div>
                  <dt>生产时间</dt>
                  <dd>
                    {revision.quote.timing.productionDays == null
                      ? '待确认'
                      : `${revision.quote.timing.productionDays} 天`}
                  </dd>
                </div>
                <div>
                  <dt>出库时间</dt>
                  <dd>
                    {revision.quote.timing.dispatchDays == null
                      ? '待确认'
                      : `${revision.quote.timing.dispatchDays} 天`}
                  </dd>
                </div>
                <div>
                  <dt>起算条件</dt>
                  <dd>
                    {revision.quote.timing.startsAfter === 'payment_conditions_met'
                      ? '付款条件满足后'
                      : revision.quote.timing.startsAfter}
                  </dd>
                </div>
                <div>
                  <dt>运输 / 到货</dt>
                  <dd>
                    {revision.quote.timing.transitDays == null
                      ? '待确认，不承诺到货日期'
                      : `${revision.quote.timing.transitDays} 天运输`}
                  </dd>
                </div>
              </dl>
            </>
          ) : (
            <EmptyState
              title="本版本没有有效报价"
              description="需要有效商品、数量和价格依据后才能形成报价。"
            />
          )}
          {revision.proposal.status === 'proposed' && (
            <button className="button" disabled={!canWrite} onClick={onAccept}>
              <Check size={14} />
              记录客户接受该方案
            </button>
          )}
        </div>
      </details>
      <details className="iw-result-section">
        <summary>
          客户回复
          <ChevronRight size={14} />
        </summary>
        <div className="iw-result-section-body">
          <div className="iw-section-heading">
            <span className="iw-kicker">CUSTOMER REPLY</span>
            <h3>双语回复草稿</h3>
            <p>在画板标签页中打开并编辑，修改会同步到这里。</p>
          </div>
          <div className="iw-reply-preview">
            {draftState.texts?.['en-US'] ?? revision.replies['en-US']}
          </div>
          <button className="button" onClick={() => openDocument(`reply:${revision.number}`)}>
            <FileText size={14} />
            打开回复草稿编辑
          </button>
        </div>
      </details>
      <details className="iw-result-section">
        <summary>
          资料依据
          <ChevronRight size={14} />
        </summary>
        <div className="iw-result-section-body">
          <div className="iw-section-heading">
            <span className="iw-kicker">EVIDENCE, NOT ASSUMPTIONS</span>
            <h3>每一项结论，都有出处</h3>
            <p>此版本使用的固定来源，更新资料不会改写历史依据。</p>
          </div>
          <div className="iw-sources">
            {revision.sourceRefs.map((s) => (
              <button key={s.sourceVersionId} onClick={() => onSource(s)}>
                <span className="iw-source-icon">
                  <FileText size={18} />
                </span>
                <div>
                  <strong>{s.title}</strong>
                  <p>
                    V{s.version} ·{' '}
                    {s.locator.row
                      ? `第 ${s.locator.row} 行`
                      : s.locator.section || s.locator.field || '原始资料'}
                  </p>
                </div>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>
          {!revision.sourceRefs.length && (
            <EmptyState
              title="暂无引用来源"
              description="查阅已发布资料后，固定版本引用会展示在这里。"
            />
          )}
          <div className="iw-section-heading">
            <h3>本次审校记录</h3>
          </div>
          {revision.checks.map((c, index) => (
            <div className="iw-check" key={index}>
              {c.status === 'passed' ? <Check size={14} /> : <TriangleAlert size={14} />}
              <span>{c.label}</span>
              <small>
                {c.status === 'passed' ? '通过' : c.status === 'error' ? '错误' : '待确认'}
              </small>
            </div>
          ))}
          <p className="iw-muted">规则版本：{revision.ruleSetVersion}</p>
          <MaterialsPanel
            base={base}
            path={path}
            scope={scope}
            revision={revision}
            readOnly={readOnly || busy}
            pending={draftsPending}
            draftVersions={draftState.versions}
            selectedAssets={history ? null : selectedAssets}
            onSelect={onSelectAssets}
          />
        </div>
      </details>
      <div className="iw-answer-save">
        <p>
          本轮内容已随业务版本保存。画布的“对话成果汇总”统一展示各轮成果；恢复和继续编辑请进入版本记录。
        </p>
        <div className="iw-answer-actions">
          <button
            className={`button ${saved ? '' : 'button-primary'}`}
            disabled={busy || draftsPending}
            onClick={onSave}
          >
            {saved ? <Check size={14} /> : <LayoutGrid size={14} />}
            查看成果汇总
          </button>
        </div>
      </div>
    </section>
  );
}

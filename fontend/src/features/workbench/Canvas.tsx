import {
  ArrowDownRight,
  ArrowRight,
  Check,
  CircleHelp,
  ExternalLink,
  LockKeyhole,
  Pencil,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import {
  calculate,
  canApprove,
  editSnapshot,
  log,
  poDifferences,
  specFields,
  usd,
  type ArtifactKind,
  type Snapshot,
  type WorkbenchState,
} from './model';
import type { Dispatch, SetStateAction } from 'react';
import { BrandMark } from '../../components/BrandMark';

type Props = {
  kind: ArtifactKind;
  snapshot: Snapshot;
  state: WorkbenchState;
  setState: Dispatch<SetStateAction<WorkbenchState>>;
  readOnly: boolean;
  onSource: (id: string) => void;
  onPropose: () => void;
  onApprove: () => void;
};
export function ArtifactCanvas({
  kind,
  snapshot,
  state,
  setState,
  readOnly,
  onSource,
  onPropose,
  onApprove,
}: Props) {
  const result = calculate(snapshot.costs);
  const updateCost = (key: keyof Snapshot['costs'], value: number) =>
    setState((s) => editSnapshot(s, { costs: { ...s.current.costs, [key]: value } }));
  if (kind === 'cost')
    return (
      <>
        <div className="tw-sheet-heading tw-cost-intro">
          <div>
            <span className="tw-eyebrow">01 / COST BREAKDOWN</span>
            <h2>每一项成本，都有依据。</h2>
            <p>供应商 A · CNY 成本 → USD 报价</p>
          </div>
          <span className="tw-chip">
            <Pencil size={11} /> {readOnly ? '历史快照' : '可直接编辑'}
          </span>
        </div>
        <div className="tw-table-scroll">
          <table className="tw-sheet">
            <thead>
              <tr>
                <th className="tw-row-number">#</th>
                <th>成本项目</th>
                <th>金额 / 件</th>
                <th>依据</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  {
                    key: 'base',
                    name: '工厂基础报价',
                    source: 'supplier-a',
                    label: '供应商 A · B2',
                    note: '产品基础成本',
                  },
                  {
                    key: 'packaging',
                    name: snapshot.packaging,
                    source: snapshot.packaging === '定制彩盒' ? 'packaging-quote' : 'supplier-a',
                    label: snapshot.packaging === '定制彩盒' ? '彩盒补充报价' : '供应商 A · B3',
                    note: '独立包装费用',
                  },
                  {
                    key: 'local',
                    name: '本地运杂费分摊',
                    source: 'assumptions',
                    label: '内部估算 · 待核实',
                    note: '演示估算费用',
                  },
                ] as const
              ).map((row, i) => (
                <tr key={row.key}>
                  <td className="tw-row-number">0{i + 1}</td>
                  <td>
                    <strong>{row.name}</strong>
                    <small>{row.note}</small>
                  </td>
                  <td>
                    <label className="tw-money-input">
                      <span>¥</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        aria-label={row.name}
                        value={
                          Number.isFinite(snapshot.costs[row.key]) ? snapshot.costs[row.key] : ''
                        }
                        disabled={readOnly}
                        onChange={(e) =>
                          updateCost(row.key, e.target.value === '' ? -1 : Number(e.target.value))
                        }
                      />
                    </label>
                  </td>
                  <td>
                    <button className="tw-source-link" onClick={() => onSource(row.source)}>
                      {row.label}
                      <ExternalLink size={10} />
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="tw-total-row">
                <td className="tw-row-number">Σ</td>
                <td>单件 FOB 估算成本</td>
                <td>¥{result?.total.toFixed(2) ?? '—'}</td>
                <td>CNY / 件</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="tw-parameters">
          <label>
            汇率 <span>CNY / USD</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              aria-label="人民币每美元汇率"
              value={snapshot.costs.exchangeRate}
              disabled={readOnly}
              onChange={(e) => updateCost('exchangeRate', Number(e.target.value))}
            />
          </label>
          <label>
            目标毛利率 <span>%</span>
            <input
              type="number"
              min="0"
              max="99.99"
              step="0.1"
              aria-label="目标毛利率"
              value={snapshot.costs.margin}
              disabled={readOnly}
              onChange={(e) => updateCost('margin', Number(e.target.value))}
            />
          </label>
          <label>
            采购数量 <span>件</span>
            <input
              type="number"
              min="1"
              max="10000000"
              step="1"
              aria-label="采购数量"
              value={snapshot.costs.quantity}
              disabled={readOnly}
              onChange={(e) => updateCost('quantity', Number(e.target.value))}
            />
          </label>
        </div>
        <div className="tw-quote-summary">
          <div>
            <span>
              建议报价 <span className="tw-summary-label">USD / 件</span>
            </span>
            <strong data-testid="unit-price">{result ? usd(result.unitPrice) : '待修正'}</strong>
            <small>向上取到美分 · {snapshot.approved ? '内部已审核（演示）' : '待内部审核'}</small>
          </div>
          <div>
            <span>
              订单总额 <span className="tw-summary-label">USD</span>
            </span>
            <strong data-testid="total-price">{result ? usd(result.totalPrice) : '—'}</strong>
            <small>{snapshot.costs.quantity.toLocaleString()} 件 × 舍入后单价</small>
          </div>
        </div>
        <div className="tw-formula">
          <span>ƒx</span>
          <code>(基础成本 + 包装 + 本地费用) ÷ 汇率 ÷ (1 − 毛利率)</code>
          <CircleHelp size={13} />
        </div>
        {!result && (
          <div role="alert" className="tw-warning">
            请填写有效成本、正汇率、0–99.99% 毛利率和正整数数量。
          </div>
        )}
        <div className="tw-context-action">
          <div>
            <ArrowDownRight size={17} />
            <span>
              <strong>客户改变包装了？</strong>
              <small>检查规格、成本、报价和询价单的联动影响。</small>
            </span>
          </div>
          <button
            className="button"
            disabled={readOnly || snapshot.packaging === '定制彩盒'}
            onClick={onPropose}
          >
            改为定制彩盒 <ArrowRight size={13} />
          </button>
        </div>
        <p className="tw-footnote">
          成本与汇率为演示假设。手工修改需重新核对来源；实际 FOB 费用项目以企业规则为准。
        </p>
      </>
    );
  if (kind === 'spec')
    return (
      <>
        <div className="tw-sheet-heading">
          <div>
            <span className="tw-eyebrow">SOURCE → FACT → ARTIFACT</span>
            <h2>需求与规格</h2>
            <p>保留未知，不把客户要求当作生产批准。</p>
          </div>
          <span className="tw-chip amber">待完善</span>
        </div>
        <div className="tw-table-scroll">
          <table className="tw-sheet tw-spec-sheet">
            <thead>
              <tr>
                <th>字段</th>
                <th>当前值</th>
                <th>事实状态</th>
              </tr>
            </thead>
            <tbody>
              {specFields.map(([key, label]) => {
                const computed = key === 'quantity' || key === 'packaging';
                const value =
                  key === 'quantity'
                    ? `${snapshot.costs.quantity} 件`
                    : key === 'packaging'
                      ? snapshot.packaging
                      : snapshot.specs[key];
                const fromEmail = ['product', 'terms', 'destination', 'arrival'].includes(key);
                const original = (
                  {
                    product: '定制背包',
                    terms: 'FOB Ningbo · Incoterms® 2020',
                    destination: 'Hamburg, Germany',
                    arrival: '期望 45 天内到港，未承诺',
                  } as Record<string, string>
                )[key];
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td>
                      {computed ? (
                        <span>{value}</span>
                      ) : (
                        <input
                          aria-label={label}
                          placeholder="Unknown · 待确认"
                          value={value || ''}
                          disabled={readOnly}
                          onChange={(e) =>
                            setState((s) =>
                              editSnapshot(s, {
                                specs: { ...s.current.specs, [key]: e.target.value },
                              }),
                            )
                          }
                        />
                      )}
                    </td>
                    <td>
                      {value ? (
                        <button
                          className="tw-source-link"
                          onClick={() =>
                            onSource(
                              fromEmail && value === original
                                ? 'inquiry'
                                : key === 'packaging'
                                  ? snapshot.packaging === '定制彩盒'
                                    ? 'change-email'
                                    : 'supplier-a'
                                  : 'manual',
                            )
                          }
                        >
                          {fromEmail && value === original
                            ? '客户提出'
                            : computed
                              ? '候选值'
                              : '人工填写 · 待确认'}
                          <ExternalLink size={10} />
                        </button>
                      ) : (
                        <span className="tw-unknown">未知</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="tw-footnote">
          数量在成本表内统一编辑，包装通过变更审核更新；手工填值不代表客户或工厂批准。
        </p>
      </>
    );
  if (kind === 'comparison')
    return (
      <>
        <div className="tw-sheet-heading">
          <div>
            <span className="tw-eyebrow">02 / SUPPLIER COMPARISON</span>
            <h2>同一口径，比较两份报价。</h2>
            <p>原始普通包装方案 · 两家报价均为演示数据</p>
          </div>
        </div>
        <table className="tw-sheet">
          <thead>
            <tr>
              <th>比较项</th>
              <th>
                供应商 A <span className="tw-chip">当前选用</span>
              </th>
              <th>供应商 B</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['基础单价', '¥44.00', '¥46.00'],
              ['普通包装', '¥2.00', '¥2.00'],
              ['本地费用估算', '¥4.00', '¥4.00'],
              ['FOB 成本估算', '¥50.00', '¥52.00'],
              ['建议报价', '$8.69', '$9.03'],
              ['预计生产时间', '28 天', '23 天'],
              ['MOQ / 工艺范围', '待确认', '待确认'],
            ].map((row) => (
              <tr key={row[0]}>
                {row.map((cell) => (
                  <td key={cell}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="tw-warning">
          <TriangleAlert size={16} />
          彩盒方案需单独核价。供应商 B 的彩盒成本未知，不能直接与新报价比较。
        </div>
        <div className="tw-inline-actions">
          <button className="button" onClick={() => onSource('supplier-a')}>
            查看 A 原始报价 <ExternalLink size={12} />
          </button>
          <button className="button" onClick={() => onSource('supplier-b')}>
            查看 B 原始报价 <ExternalLink size={12} />
          </button>
        </div>
      </>
    );
  if (kind === 'production' || kind === 'pi') {
    const diffs = poDifferences(state);
    return (
      <>
        <div className="tw-sheet-heading">
          <div>
            <span className="tw-eyebrow">03 / ORDER HANDOVER</span>
            <h2>{kind === 'pi' ? 'PO / PI 对照' : '准备好资料，再进入生产。'}</h2>
            <p>文件生成、商业批准与实际开工分别记录。</p>
          </div>
          <span className="tw-chip amber">
            <LockKeyhole size={11} /> 未放行
          </span>
        </div>
        <div className="tw-po-inputs">
          <label>
            PO 数量（演示录入）
            <input
              type="number"
              min="1"
              aria-label="PO 数量"
              value={state.po.quantity}
              disabled={readOnly}
              onChange={(e) =>
                setState((s) => ({ ...s, po: { ...s.po, quantity: Number(e.target.value) } }))
              }
            />
          </label>
          <label>
            PO 单价 · USD
            <input
              type="number"
              min="0"
              step="0.01"
              aria-label="PO 单价"
              value={state.po.price}
              disabled={readOnly}
              onChange={(e) =>
                setState((s) => ({ ...s, po: { ...s.po, price: Number(e.target.value) } }))
              }
            />
          </label>
        </div>
        <div className={`tw-warning ${diffs.length ? '' : 'green'}`}>
          {diffs.length ? <TriangleAlert size={16} /> : <Check size={16} />}
          <span>
            {diffs.length
              ? diffs.join('；')
              : '数量、单价与当前报价一致；仍需客户原始 PO 及批准证据。'}
          </span>
        </div>
        <div className="tw-gate-list">
          {[
            {
              label: '内部报价审核',
              note: snapshot.approved ? '当前版本已完成演示审核' : '需审核当前报价版本',
              pass: snapshot.approved,
            },
            {
              label: 'PO 与报价一致',
              note: diffs.length ? '请处理数量或价格差异' : '仅校验演示录入字段',
              pass: !diffs.length,
            },
            { label: '客户规格与样品批准', note: '缺少客户批准证据', pass: false },
            { label: '供应商生产确认', note: '产能、交期、MOQ 尚未确认', pass: false },
            { label: '生产负责人放行', note: '需真实责任方确认', pass: false },
          ].map((g) => (
            <div key={g.label}>
              {g.pass ? <ShieldCheck size={18} /> : <LockKeyhole size={17} />}
              <span>
                <strong>{g.label}</strong>
                <small>{g.note}</small>
              </span>
              <span className={`tw-chip ${g.pass ? 'success' : 'amber'}`}>
                {g.pass ? '通过' : '待确认'}
              </span>
            </div>
          ))}
        </div>
        {kind === 'production' && (
          <div className="tw-timeline">
            <h3>T&A 计划草稿</h3>
            {['客户规格 / 样品批准', '物料与包装采购', '生产与过程检验', '出货检验 / 订舱'].map(
              (t, i) => (
                <div key={t}>
                  <span>0{i + 1}</span>
                  <strong>{t}</strong>
                  <small>日期待责任方确认</small>
                </div>
              ),
            )}
          </div>
        )}
        <div className="tw-warning">
          <LockKeyhole size={16} />
          可导出带待确认项的草稿；当前不满足正式签发或生产放行条件。
        </div>
      </>
    );
  }
  return (
    <>
      <div className="tw-document">
        <div className="tw-document-brand">
          <BrandMark />
          <strong className="tw-document-name">Navowork</strong>
          <small>EXPORT OPERATIONS</small>
          <span className="tw-document-stamp">
            DRAFT
            <br />V{snapshot.version}
          </span>
        </div>
        <h2>{kind === 'quote' ? 'QUOTATION' : 'REQUEST FOR QUOTATION'}</h2>
        <p>{kind === 'quote' ? '定制背包 · 客户报价草稿' : '定制背包 · 供应商询价草稿'}</p>
        <div className="tw-document-meta">
          <div>
            <small>PREPARED FOR</small>
            <strong>{kind === 'quote' ? 'Michael Weber' : '供应商 A · 采购对接人'}</strong>
            <span>{kind === 'quote' ? 'Hamburg, Germany' : '联系人 / 邮箱待确认'}</span>
          </div>
          <div>
            <small>REFERENCE</small>
            <strong>BAG-2026-DE-001</strong>
            <span>{snapshot.specs.terms || '贸易条款待确认'}</span>
          </div>
        </div>
        <table className="tw-sheet">
          <thead>
            <tr>
              <th>产品 / 包装</th>
              <th>数量</th>
              <th>单价</th>
              <th>金额</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                {snapshot.specs.product}
                <small>{snapshot.packaging}</small>
              </td>
              <td>{snapshot.costs.quantity.toLocaleString()}</td>
              <td>{kind === 'quote' && result ? usd(result.unitPrice) : '待回复'}</td>
              <td>{kind === 'quote' && result ? usd(result.totalPrice) : '待回复'}</td>
            </tr>
          </tbody>
        </table>
        <div className="tw-document-terms">
          <strong>{kind === 'quote' ? '条款与待确认项' : '请供应商确认'}</strong>
          <p>01　面料、尺寸、LOGO 工艺与最终样品需确认。</p>
          <p>
            02　
            {kind === 'quote'
              ? '预计生产 28 天，需供应商最终确认；不承诺到港日。'
              : '请回复包装单价、MOQ、样品费用与交期影响。'}
          </p>
          <p>03　付款条件与报价有效期待确认。</p>
          <p>04　本文件为演示草稿，未向外部发送。</p>
        </div>
      </div>
      {kind === 'quote' && (
        <div className="tw-inline-actions">
          <button
            className="button button-primary"
            disabled={readOnly || snapshot.approved || !canApprove(state)}
            onClick={onApprove}
          >
            <ShieldCheck size={14} />
            {snapshot.approved ? '内部报价已审核（演示）' : '审核当前报价'}
          </button>
          <span className="tw-footnote">审核不代表客户确认或生产放行。</span>
        </div>
      )}
    </>
  );
}

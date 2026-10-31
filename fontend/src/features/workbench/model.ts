export type ArtifactKind = 'spec' | 'comparison' | 'cost' | 'quote' | 'rfq' | 'pi' | 'production';
export type WorkMode = 'build' | 'review' | 'deliver';
export interface CostInputs {
  base: number;
  packaging: number;
  local: number;
  exchangeRate: number;
  margin: number;
  quantity: number;
}
export interface Snapshot {
  version: number;
  costs: CostInputs;
  specs: Record<string, string>;
  packaging: string;
  approved: boolean;
  createdAt: string;
  note: string;
}
export interface Evidence {
  id: string;
  name: string;
  locator: string;
  content: string;
  kind: 'email' | 'sheet' | 'file';
}
export interface WorkbenchState {
  schema: 1;
  current: Snapshot;
  history: Snapshot[];
  proposal: null | { costKnown: boolean; accepted: string[] };
  sources: Evidence[];
  activity: { text: string; at: string }[];
  po: { quantity: number; price: number };
}
export const caseId = 'BAG-2026-DE-001';
export const artifacts: { id: ArtifactKind; title: string; english: string; format: string }[] = [
  { id: 'spec', title: '需求与规格表', english: 'REQUIREMENT & SPECIFICATION', format: 'XLSX' },
  { id: 'comparison', title: '供应商比较表', english: 'SUPPLIER COMPARISON', format: 'XLSX' },
  { id: 'cost', title: '可计算成本表', english: 'COSTING SHEET', format: 'XLSX' },
  { id: 'quote', title: '客户报价单', english: 'QUOTATION', format: 'DOCX' },
  { id: 'rfq', title: '供应商询价单', english: 'REQUEST FOR QUOTATION', format: 'DOCX' },
  { id: 'pi', title: '形式发票 PI', english: 'PROFORMA INVOICE', format: 'DOCX' },
  { id: 'production', title: '生产资料包', english: 'PRODUCTION PACK', format: 'DOCX' },
];
export const specFields = [
  ['product', '产品'],
  ['quantity', '数量'],
  ['material', '面料 / 克重'],
  ['dimensions', '尺寸'],
  ['color', '颜色'],
  ['logo', 'LOGO 工艺'],
  ['packaging', '包装'],
  ['terms', '贸易条款'],
  ['destination', '目的地'],
  ['arrival', '期望到港时间'],
  ['sample', '样品批准'],
  ['waterproof', '防水指标'],
] as const;
export const demoSources: Evidence[] = [
  {
    id: 'inquiry',
    name: 'Michael_背包询盘.eml',
    kind: 'email',
    locator: '邮件正文 · 第 1–3 段',
    content:
      'From: Michael Weber <michael@example.com>\nSubject: Inquiry — 3,000 custom backpacks\n\nPlease quote 3,000 custom backpacks with our logo, FOB Ningbo (Incoterms® 2020). We would like them to arrive in Hamburg within 45 days if possible. Please confirm material, dimensions, logo process and sample arrangements.\n\n演示材料：邮件未提供尺寸、面料克重、防水等级或已确认船期。',
  },
  {
    id: 'supplier-a',
    name: '供应商A_背包报价.xlsx',
    kind: 'sheet',
    locator: '报价表 · B2:B5',
    content:
      '合成演示报价\nB2 基础单价：CNY 44 / 件\nB3 普通包装：CNY 2 / 件\nB4 预计生产时间：28 天，需最终确认\nB5 MOQ：待供应商确认\n\n本地运杂费分摊 CNY 4 为内部估算，不是供应商报价。',
  },
  {
    id: 'supplier-b',
    name: '供应商B_背包报价.pdf',
    kind: 'file',
    locator: '第 1 页 · 价格表',
    content:
      '合成演示报价\n基础单价：CNY 46 / 件\n普通包装：CNY 2 / 件\n预计生产时间：23 天，需最终确认\nMOQ、工艺范围、运输与到港时间：待确认。',
  },
  {
    id: 'assumptions',
    name: '内部核价假设.txt',
    kind: 'file',
    locator: '演示假设 · 待企业核实',
    content:
      '本地运杂费：CNY 4 / 件\n汇率：7.20 CNY / USD\n目标毛利率：20%（非成本加成率）\n美元单价向上舍入到美分；总价用舍入后单价乘数量。\n以上仅为演示假设。FOB Ningbo 不构成 45 天内到港的承诺。',
  },
];
export const changeSources: Evidence[] = [
  {
    id: 'change-email',
    name: 'Michael_包装变更.eml',
    kind: 'email',
    locator: '邮件正文 · 第 1 段',
    content:
      'From: Michael Weber <michael@example.com>\nSubject: Packaging update\n\nPlease change the standard box to a custom printed color box. Keep the other conditions unchanged. Please send an updated quotation.\n\n演示材料：客户提出变更，尚未批准新报价或生产。',
  },
  {
    id: 'packaging-quote',
    name: '供应商A_彩盒补充报价.eml',
    kind: 'email',
    locator: '邮件正文 · 包装单价',
    content:
      '合成演示供应商回复\n定制彩盒包装价格：CNY 5 / 件，替代原 CNY 2 普通包装。其他已核实费用暂不变。\nMOQ、样品与生产交期影响待另行确认；此回复不代表生产放行。',
  },
];
export function calculate(costs: CostInputs) {
  const { base, packaging, local, exchangeRate, margin, quantity } = costs;
  if (
    Object.values(costs).some((v) => !Number.isFinite(v)) ||
    base < 0 ||
    packaging < 0 ||
    local < 0 ||
    exchangeRate <= 0 ||
    margin < 0 ||
    margin >= 100 ||
    !Number.isInteger(quantity) ||
    quantity < 1 ||
    quantity > 10000000
  )
    return null;
  const total = Math.round((base + packaging + local) * 100) / 100;
  const cents = Math.ceil((total / exchangeRate / (1 - margin / 100)) * 100 - 1e-9);
  if (!Number.isSafeInteger(cents * quantity)) return null;
  return { total, unitPrice: cents / 100, totalPrice: (cents * quantity) / 100 };
}
export function initialState(): WorkbenchState {
  const current: Snapshot = {
    version: 1,
    costs: { base: 44, packaging: 2, local: 4, exchangeRate: 7.2, margin: 20, quantity: 3000 },
    specs: {
      product: '定制背包',
      material: '',
      dimensions: '',
      color: '',
      logo: '',
      terms: 'FOB Ningbo · Incoterms® 2020',
      destination: 'Hamburg, Germany',
      arrival: '期望 45 天内到港，未承诺',
      sample: '',
      waterproof: '',
    },
    packaging: '普通纸盒',
    approved: false,
    createdAt: new Date().toISOString(),
    note: '根据演示询盘建立初始草稿',
  };
  return {
    schema: 1,
    current,
    history: [],
    proposal: null,
    sources: demoSources,
    activity: [
      { text: '已载入演示询盘与两家供应商报价；未知规格保留为空。', at: current.createdAt },
    ],
    po: { quantity: 3000, price: 8.69 },
  };
}
export function log(state: WorkbenchState, text: string): WorkbenchState {
  return {
    ...state,
    activity: [...state.activity, { text, at: new Date().toISOString() }].slice(-80),
  };
}
export function editSnapshot(
  state: WorkbenchState,
  patch: Partial<Pick<Snapshot, 'costs' | 'specs'>>,
): WorkbenchState {
  const current = state.current;
  const history = current.approved ? [...state.history, structuredClone(current)] : state.history;
  return {
    ...state,
    history,
    current: {
      ...current,
      ...patch,
      approved: false,
      version: current.approved ? current.version + 1 : current.version,
      note: '人工编辑草稿，需重新审核',
      createdAt: new Date().toISOString(),
    },
  };
}
export function proposeChange(state: WorkbenchState): WorkbenchState {
  return log(
    {
      ...state,
      proposal: { costKnown: true, accepted: ['spec', 'cost', 'quote', 'rfq'] },
      sources: [
        ...state.sources,
        ...changeSources.filter((source) => !state.sources.some((s) => s.id === source.id)),
      ],
    },
    '已按演示包装变更生成 4 份成果的候选修订；当前版本保持不变。',
  );
}
export function applyChange(state: WorkbenchState): WorkbenchState {
  if (
    !state.proposal?.costKnown ||
    !['spec', 'cost', 'quote', 'rfq'].every((id) => state.proposal?.accepted.includes(id))
  )
    return state;
  return log(
    {
      ...state,
      history: [...state.history, structuredClone(state.current)],
      current: {
        ...state.current,
        costs: { ...state.current.costs, packaging: 5 },
        packaging: '定制彩盒',
        version: state.current.version + 1,
        approved: false,
        createdAt: new Date().toISOString(),
        note: `包装变更：${state.current.packaging} → 定制彩盒；包装成本 ¥${state.current.costs.packaging} → ¥5`,
      },
      proposal: null,
    },
    '已应用包装变更，建立新的草稿版本；报价、交期与生产批准仍需单独确认。',
  );
}
export function canApprove(state: WorkbenchState) {
  return calculate(state.current.costs) !== null && !state.proposal;
}
export function poDifferences(state: WorkbenchState) {
  const quote = calculate(state.current.costs);
  return [
    state.po.quantity !== state.current.costs.quantity ? 'PO 数量与当前报价不一致' : '',
    !quote || Math.round(state.po.price * 100) !== Math.round(quote.unitPrice * 100)
      ? 'PO 单价与当前报价不一致'
      : '',
  ].filter(Boolean);
}
export const storageKey = (scope: string) => `easywork:trade-workbench:v1:${scope}`;
export const usd = (amount: number) =>
  `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

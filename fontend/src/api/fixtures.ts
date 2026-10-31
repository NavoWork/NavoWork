import type {
  Asset,
  Capability,
  Draft,
  Inquiry,
  Message,
  Revision,
  Session,
  Source,
} from './types';
export const demoSession: Session = {
  user: { id: 'user_demo', name: 'Alex', role: 'admin' },
  workspace: { id: 'ws_demo', name: 'NavoWork 工作空间' },
};
export const sources: Source[] = [
  {
    id: 'product-stock',
    sourceId: 'product-stock',
    title: '现货帆布袋 · 商品资料',
    version: 1,
    kind: 'product',
    status: 'published',
    content:
      'SKU BAG-STOCK；MOQ 100 件；库存 800 件，记录于 2026-10-31；付款条件满足后 3 天出库，运输时间未确认。',
    editVersion: 1,
    updatedAt: '2026-10-31T02:00:00Z',
  },
  {
    id: 'price-stock',
    sourceId: 'price-stock',
    title: '现货商品价表 · USD',
    version: 1,
    kind: 'price',
    status: 'published',
    content:
      'BAG-STOCK：USD 1.80/件；报价有效期 7 天；不含运费、税费；最终总额未知。',
    editVersion: 1,
    updatedAt: '2026-10-31T02:00:00Z',
  },
  {
    id: 'delivery-policy',
    sourceId: 'delivery-policy',
    title: '交付与承诺规则',
    version: 1,
    kind: 'knowledge',
    status: 'published',
    content:
      '# 交付规则\n\n出库时间不等于到货时间。运输时间、认证证据、运费、税费未确认时必须明确披露，不得承诺。',
    editVersion: 1,
    updatedAt: '2026-10-31T02:00:00Z',
  },
  {
    id: 'reply-style',
    sourceId: 'reply-style',
    title: '客户沟通语气指南',
    version: 1,
    kind: 'knowledge',
    status: 'draft',
    content: '# 语气指南\n\n回复要清楚、简洁，先回应客户需求，再列待确认事项。',
    editVersion: 1,
    updatedAt: '2026-10-31T01:00:00Z',
  },
];
const common = {
  workspaceId: 'ws_demo',
  requestedLocales: ['en-US', 'es-MX'] as const,
  metadataVersion: 1,
  activeRunId: null,
};
const historicalInquiries: Inquiry[] = [
  {
    ...common,
    requestedLocales: [...common.requestedLocales],
    id: 'inq_mx026',
    title: '墨西哥帆布袋试单',
    customer: 'Sofía · Casa Verde',
    originalText:
      'We need 1,000 custom canvas bags with our logo, delivered to Mexico City in 10 days. Could you quote a 300-unit stock alternative for our trial order? Please share certification evidence if available.',
    destination: '墨西哥',
    businessStatus: 'active',
    currentRevision: 2,
    nextAction: '核对 300 件现货方案，确认运输与认证资料',
    updatedAt: '2026-10-31T05:40:00Z',
  },
  {
    ...common,
    requestedLocales: [...common.requestedLocales],
    id: 'inq_de014',
    title: '德国陶瓷杯采购询盘',
    customer: 'Lukas · Nord Studio',
    originalText:
      'Please quote 600 ceramic coffee cups with a matte finish for delivery to Hamburg. We need packaging details and your lead time.',
    destination: '德国',
    businessStatus: 'todo',
    currentRevision: 0,
    nextAction: '读懂客户原文，确认规格与交付要求',
    updatedAt: '2026-10-31T05:10:00Z',
  },
  {
    ...common,
    requestedLocales: [...common.requestedLocales],
    id: 'inq_us008',
    title: '美国环保购物袋补单',
    customer: 'Emma · Field & Form',
    originalText:
      'We would like to reorder 300 stock canvas bags. Please confirm the freight cost to Los Angeles.',
    destination: '美国',
    businessStatus: 'waiting',
    currentRevision: 1,
    waiting: {
      waitingFor: '供应商',
      waitingReason: '等待洛杉矶运输费用',
      nextAction: '收到运费后更新回复',
    },
    nextAction: '等待供应商确认洛杉矶运费',
    updatedAt: '2026-10-31T04:20:00Z',
  },
  {
    ...common,
    requestedLocales: [...common.requestedLocales],
    id: 'inq_uk012',
    title: '英国展会礼品袋方案',
    customer: 'Oliver · Common Ground',
    originalText: 'Please send a draft for 300 stock canvas bags for our exhibition.',
    destination: '英国',
    businessStatus: 'done',
    currentRevision: 1,
    closeReason: '本次处理完成',
    nextAction: '已结束，可查看历史与导出草稿材料',
    updatedAt: '2026-10-30T08:35:00Z',
  },
];
// Every new workspace starts from the received inquiry. Completed records are
// retained only as explicit contract-test fixtures below.
export const inquiries: Inquiry[] = historicalInquiries.map((inquiry) => ({
  ...inquiry,
  businessStatus: 'todo',
  currentRevision: 0,
  waiting: undefined,
  closeReason: undefined,
  nextAction: '整理客户需求，确认规格与交付缺项',
}));

export function sampleRevision(inquiryId: string, number: number, quantity = 300): Revision {
  const amount = quantity === 600 ? 108000 : 54000;
  return {
    inquiryId,
    number,
    runId: `seed_${inquiryId}_${number}`,
    requirements: {
      requestedProduct: '帆布袋',
      specification: inquiryId === 'inq_mx026' ? '定制 Logo 帆布袋' : '现货帆布袋',
      quantity: inquiryId === 'inq_mx026' ? 1000 : 300,
      destination:
        inquiryId === 'inq_us008' ? '美国' : inquiryId === 'inq_uk012' ? '英国' : '墨西哥',
      requestedArrival: inquiryId === 'inq_mx026' ? '客户期望 10 天内到货' : null,
      customization: inquiryId === 'inq_mx026' ? '印制客户 Logo' : null,
      certificationRequests: inquiryId === 'inq_mx026' ? ['认证证据待提供'] : [],
      missingFields: ['运输时效', '运费与税费', '认证证据'],
      evidenceRefs: ['originalText'],
    },
    proposal: {
      proposalId: `proposal_${number}`,
      version: number,
      requestedSku: inquiryId === 'inq_mx026' ? 'BAG-CUSTOM' : 'BAG-STOCK',
      selectedSku: 'BAG-STOCK',
      differences:
        inquiryId === 'inq_mx026'
          ? ['现货不印 Logo，区别于原定制要求', `建议先采购 ${quantity} 件试单；等待客户确认`]
          : [],
      status: 'proposed',
    },
    quote: {
      sku: 'BAG-STOCK',
      quantity,
      currency: 'USD',
      unitPriceMinor: 180,
      goodsSubtotalMinor: amount,
      freightMinor: null,
      taxMinor: null,
      totalMinor: null,
      quoteStatus: 'draft',
      sourceVersionIds: ['product-stock-v1', 'price-stock-v1'],
      timing: {
        dispatchDays: 3,
        startsAfter: '付款条件满足后',
        transitDays: null,
        arrivalGuaranteed: false,
      },
    },
    replies: {
      'en-US': `Dear customer,\n\n${inquiryId === 'inq_mx026' ? 'As an alternative to your original custom order, we propose' : 'For your inquiry, we propose'} ${quantity} unprinted stock canvas bags (BAG-STOCK) at USD 1.80 each. The goods subtotal is USD ${(amount / 100).toFixed(2)}. Please confirm whether this alternative is acceptable.\n\nDispatch is estimated at 3 days after payment conditions are met. This is not an arrival guarantee. Freight, taxes, transit time and the final total remain unconfirmed. Certification evidence has not been provided.\n\nBest regards`,
      'es-MX': `Estimado cliente:\n\n${inquiryId === 'inq_mx026' ? 'Como alternativa al pedido personalizado, proponemos' : 'Para su consulta, proponemos'} ${quantity} bolsas de lona sin impresión (BAG-STOCK) a USD 1.80 por unidad. El subtotal de mercancía es USD ${(amount / 100).toFixed(2)}. Por favor confirme si acepta esta alternativa.\n\nLa salida se estima en 3 días después de cumplir las condiciones de pago; no garantiza la llegada. Flete, impuestos, tránsito y total final están por confirmar. No se ha proporcionado evidencia de certificación.\n\nSaludos cordiales`,
    },
    risks: [
      {
        id: 'arrival-unconfirmed',
        severity: 'warning',
        category: 'delivery',
        message:
          inquiryId === 'inq_mx026'
            ? '3 天出库不代表 10 天内到货'
            : '出库时间不等于到货时间，运输时效未确认',
        suggestedAction: '向供应商确认目的地运输方案及运输时效',
        status: 'open',
        evidenceRefs: ['delivery-policy-v1'],
      },
      {
        id: 'customization-difference',
        severity: 'warning',
        category: 'proposal',
        message:
          inquiryId === 'inq_mx026'
            ? '现货方案与原始定制需求不同，尚未获客户接受'
            : '方案仍待客户确认',
        suggestedAction: '请客户明确确认现货无印刷方案',
        status: 'open',
        evidenceRefs: ['product-stock-v1'],
      },
      {
        id: 'certification-unconfirmed',
        severity: 'warning',
        category: 'evidence',
        message: '认证证据未提供',
        suggestedAction: '补充有效证据，回复中保留待确认说明',
        status: 'open',
        evidenceRefs: [],
      },
    ],
    checks: [
      { label: '数量与商品小计一致', status: 'passed' },
      { label: '未知运费与税费已披露', status: 'passed' },
      { label: '客户确认与认证资料', status: 'warning' },
    ],
    sourceRefs: sources
      .filter((s) => s.status === 'published')
      .map((s) => ({
        sourceVersionId: `${s.id}-v1`,
        sourceId: s.id,
        title: s.title,
        version: 1,
        locator: { row: s.kind === 'price' ? 3 : undefined, section: '资料正文' },
        supports: s.kind === 'price' ? ['/quote/unitPriceMinor'] : ['/quote/timing'],
        contentHash: 'mock-fixture-v1',
      })),
    assetRefs: [],
    ruleSetVersion: 'demo-rules-1',
    createdAt: number === 1 ? '2026-10-31T03:00:00Z' : '2026-10-31T05:40:00Z',
    changeSummary:
      number === 1
        ? ['建立询盘分析与备选方案']
        : ['从定制需求提出 300 件现货试单方案', '保留运输、认证及最终费用待确认项'],
  };
}
export const capabilities: Capability[] = [
  ['understand', '需求理解', '提取客户要求，保留未知与缺项。', '理解'],
  ['retrieve', '商品与资料查询', '检索已发布资料，返回可追溯的依据。', '知识'],
  ['calculate', '报价计算', '由服务端计算金额并校验起订量、库存。', '报价'],
  ['compose', '双语回复', '基于同一业务事实生成英语与西班牙语草稿。', '沟通'],
  ['review', '风险审校', '核对金额、交期承诺、资料与版本。', '审校'],
  ['bundle', '材料整理', '整理指定版本的草稿及资料清单。', '交付'],
].map(([id, name, description, category]) => ({
  id,
  name,
  description,
  category,
  version: '1.0.0',
  enabled: true,
  required: id !== 'bundle',
}));
export const assets: Asset[] = [
  {
    id: 'asset_sample',
    title: '帆布袋资料说明',
    name: '帆布袋资料说明',
    version: 1,
    skuScope: ['BAG-STOCK'],
    locale: 'zh-CN',
    mediaType: 'application/pdf',
    source: '产品资料',
    size: 24600,
    createdAt: '2026-10-31T02:00:00Z',
  },
];
export function seed(withHistory = false) {
  const initialInquiries = withHistory ? historicalInquiries : inquiries;
  const revisions: Record<string, Revision[]> = {};
  const drafts: Record<string, Draft> = {};
  const messages: Record<string, Message[]> = {};
  for (const i of initialInquiries) {
    revisions[i.id] = Array.from({ length: i.currentRevision }, (_, n) => {
      const r = sampleRevision(i.id, n + 1);
      if (i.id === 'inq_mx026' && n === 0) {
        r.quote = null;
        r.proposal = { ...r.proposal, selectedSku: null, differences: [], status: 'requested' };
        r.replies = {
          'en-US':
            'Thank you for your inquiry. We are reviewing the requested custom bags and the stock alternative. Price, transport and certification evidence are being checked.',
          'es-MX':
            'Gracias por su consulta. Estamos revisando las bolsas personalizadas y la alternativa disponible. El precio, transporte y evidencia de certificación están por confirmar.',
        };
        r.checks = [{ label: '原始需求已记录，方案与报价待准备', status: 'warning' }];
        r.changeSummary = ['记录原始需求、交付冲突与待确认资料，尚无有效报价'];
      }
      return r;
    });
    messages[i.id] = [
      {
        id: `msg_${i.id}`,
        inquiryId: i.id,
        role: 'user',
        text: i.originalText,
        createdAt: i.updatedAt,
      },
    ];
    for (const r of revisions[i.id])
      for (const locale of ['en-US', 'es-MX'] as const)
        drafts[`${i.id}:${r.number}:${locale}`] = {
          inquiryId: i.id,
          revision: r.number,
          locale,
          draftVersion: 1,
          text: r.replies[locale],
          reviewStatus: 'needs_review',
          updatedAt: r.createdAt,
        };
  }
  return {
    session: null as Session | null,
    inquiries: structuredClone(initialInquiries),
    revisions,
    drafts,
    messages,
    sources: structuredClone(sources),
    capabilities: structuredClone(capabilities),
    assets: structuredClone(assets),
  };
}

(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.SealSeekDemo = api;
}(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var PRODUCT_IDS = ['BAG-CUSTOM', 'BAG-STOCK'];
  var SCENARIO_PROMPTS = [
    '墨西哥客户要1000个定制帆布袋，希望10天内收到，并询问认证。帮我分析需求，准备英文和西语回复。',
    '客户改成先试单300件，希望7天内收到。给我现货备选方案，生成报价和供货核对清单。',
    '客户接受现货无印花方案。请明确3天是出库时间，不保证7天到货，更新报价和客户回复。'
  ];
  var DATA = {
    name: 'EasyWork 出海工作台',
    version: 'demo-1.0.0',
    isDemo: true,
    scenarioPrompts: SCENARIO_PROMPTS,
    products: [
      { id: 'BAG-CUSTOM', sku: 'BAG-CUSTOM', name: '定制帆布袋', title: '定制帆布袋', material: '棉帆布', dimensions: '38 × 42 cm', color: '自然米白', customization: true, moq: 500, stock: null, currency: 'USD', productionDays: 14, dispatchDays: null, certifications: [], unitPrice: '2.40', priceTiers: [{ min: 500, max: 999, cents: 240, price: '2.40' }, { min: 1000, max: null, cents: 200, price: '2.00' }], sourceIds: ['wiki-product', 'wiki-pricing'], description: '支持单色印花，确认稿件与付款条件满足后生产14天。', isDemo: true },
      { id: 'BAG-STOCK', sku: 'BAG-STOCK', name: '现货无印花帆布袋', title: '现货无印花帆布袋', material: '棉帆布', dimensions: '38 × 42 cm', color: '自然米白', customization: false, moq: 100, stock: 800, currency: 'USD', productionDays: null, dispatchDays: 3, certifications: [], unitPrice: '1.80', priceTiers: [{ min: 100, max: null, cents: 180, price: '1.80' }], sourceIds: ['wiki-product', 'wiki-pricing'], description: '无印花现货，满足付款条件后3天内出库，运输时间另行确认。', isDemo: true }
    ],
    wiki: [
      { id: 'wiki-product', title: '帆布袋 · 商品与供货事实', category: '商品知识', tags: ['商品', 'MOQ', '库存'], version: '1.0', source: '商家资料 · 合成演示数据', sourceUrl: null, body: '定制款 BAG-CUSTOM：棉帆布，38 × 42 cm，500件起订，支持单色印花。现货款 BAG-STOCK：同尺寸无印花，100件起订，可用库存800件。两款均未提供认证证明。以上是演示设定，不是真实库存或供应承诺。', updatedAt: '2026-10-30', isDemo: true },
      { id: 'wiki-pricing', title: '报价规则 · 阶梯价格与费用范围', category: '商务规则', tags: ['报价', 'USD', '价格'], version: '1.0', source: '商家报价政策 · 合成演示数据', sourceUrl: null, body: '定制款500–999件为USD 2.40/件，1000件起为USD 2.00/件；现货款USD 1.80/件。用整数分计算商品小计。运费和税费未知时保留待确认，商品小计不得称为最终总额。演示报价有效期7天。', updatedAt: '2026-10-30', isDemo: true },
      { id: 'wiki-delivery', title: '交期说明 · 出库不等于到货', category: '供货知识', tags: ['交期', '出库', '运输'], version: '1.0', source: '商家履约说明 · 合成演示数据', sourceUrl: null, body: '定制款在稿件及付款条件确认后生产14天。现货款在付款条件满足后3天内出库。运输、清关与最终到货时间尚未确认。不能把3天出库改写成3天或7天保证到货。', updatedAt: '2026-10-30', isDemo: true },
      { id: 'wiki-claims', title: '对外声明 · 证据与风险检查', category: '规则知识', tags: ['认证', '声明', '平台'], version: '1.0', source: '平台公开说明＋项目检查规则', sourceUrl: 'https://seller.alibaba.com/pages/seller_onboarding_rules.html', body: '对外的规格、认证和保证性宣传应有资料支持。当前商品未提供认证证明，应明确“认证资料待确认”，不能生成“已认证”声明。此处是有限的演示规则检查，不代表全面法律或国家认证审查。', updatedAt: '2026-10-30', isDemo: true },
      { id: 'wiki-localization', title: '客户回复 · 英语与墨西哥西语', category: '表达指南', tags: ['英语', '西语', '客户回复'], version: '1.0', source: '本项目商务表达指南', sourceUrl: null, body: '先回应具体采购要求，再说明有依据的限制与备选，最后给出一个明确的下一步。英语与西语保持数量、价格、交期、缺失信息一致；币种写清USD。现货备选尚未接受时，不得写成客户已经确认。', updatedAt: '2026-10-30', isDemo: true }
    ],
    assets: [
      { id: 'asset-stock', title: '现货帆布袋 · 产品素材', name: '现货帆布袋', type: 'image', language: '通用', sku: 'BAG-STOCK', description: '自然米白无印花款。以示意图表示现有产品素材，供回复材料复用。', version: '1.0', source: '原创产品示意 · 演示素材', sourceIds: ['BAG-STOCK', 'wiki-product'], visual: 'stock-bag', tags: ['产品图', '现货'], isDemo: true },
      { id: 'asset-custom', title: '定制帆布袋 · 印花示意', name: '定制帆布袋', type: 'image', language: '通用', sku: 'BAG-CUSTOM', description: '单色印花位置示意。不是实际生成的商品摄影或客户确认稿。', version: '1.0', source: '原创产品示意 · 演示素材', sourceIds: ['BAG-CUSTOM', 'wiki-product'], visual: 'custom-bag', tags: ['产品图', '定制'], isDemo: true },
      { id: 'asset-size', title: '38 × 42 cm · 规格资料卡', name: '尺寸资料卡', type: 'document', language: 'EN / ES', sku: 'ALL', description: '可复用规格信息与尺寸示意，关联商品事实，帮助同一用户准备资料。', version: '1.0', source: '商品资料模板 · 演示素材', sourceIds: ['wiki-product'], visual: 'size-guide', tags: ['尺寸图', '资料卡'], isDemo: true },
      { id: 'asset-quote-template', title: '客户报价 · 双语模板', name: '双语报价模板', type: 'template', language: 'EN / ES', sku: 'ALL', description: '区分商品小计与最终总额，保留费用和运输条件待确认项。', version: '1.0', source: '本项目报价模板', sourceIds: ['wiki-pricing', 'wiki-delivery'], visual: 'quote-template', tags: ['报价', '模板'], isDemo: true }
    ],
    capabilities: [
      { id: 'inquiry-skill', name: '理解询盘', title: '理解询盘', type: 'Skill', description: '提取客户要求，查找缺失项和供货冲突。', version: '1.0', scope: '需求理解', inputs: ['客户原文', '商品资料'], outputs: ['需求摘要', '澄清问题'], tags: ['运营', '业务'], simulated: true },
      { id: 'reply-skill', name: '双语商务回复', title: '双语商务回复', type: 'Skill', description: '按同一份事实组织英语和墨西哥西语回复。', version: '1.0', scope: '客户沟通', inputs: ['需求与事实', '当前方案'], outputs: ['英文回复', '西语回复'], tags: ['业务'], simulated: true },
      { id: 'quote-skill', name: '报价与方案', title: '报价与方案', type: 'Skill', description: '组织备选方案、报价和供货核对项，保留待确认条件。', version: '1.0', scope: '商务方案', inputs: ['商品方案', '数量'], outputs: ['报价草案', '供货核对清单'], tags: ['业务', '采购'], simulated: true },
      { id: 'product-mcp', name: '商品与库存查询', title: '商品与库存查询', type: 'MCP', description: '展示连接商品和库存工具的产品体验。本Demo读取本地演示资料。', version: '1.0', scope: '商品资料', inputs: ['SKU / 商品条件'], outputs: ['商品事实', '来源引用'], tags: ['采购', '数据连接'], simulated: true },
      { id: 'quote-cli', name: '报价计算与导出', title: '报价计算与导出', type: 'CLI', description: '展示确定性计算能力；本Demo实际采用浏览器整数分计算，不启动命令行。', version: '1.0', scope: '业务计算', inputs: ['SKU', '数量', '价格表'], outputs: ['商品小计', '费用范围'], tags: ['采购', '工具'], simulated: true },
      { id: 'compliance-skill', name: '声明与条款检查', title: '声明与条款检查', type: 'Skill', description: '核对认证证据、交期措辞与报价缺失项，给出定位和修改建议。', version: '1.0', scope: '规则检查', inputs: ['业务产物', '规则资料'], outputs: ['风险标记', '文字批注'], tags: ['合规'], simulated: true },
      { id: 'asset-skill', name: '准备客户资料', title: '准备客户资料', type: 'Skill', description: '复用正确SKU的产品图、规格卡和报价素材，整理客户沟通材料。', version: '1.0', scope: '素材准备', inputs: ['当前商品', '资产引用'], outputs: ['资料组合', '素材引用'], tags: ['美工', '业务'], simulated: true }
    ]
  };

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function money(cents) { return (cents / 100).toFixed(2); }
  function count(value) { return Number(value).toLocaleString('en-US'); }
  function findProduct(sku) { return DATA.products.find(function (p) { return p.sku === sku; }); }
  function sourceIdsFor(sku) { return [sku, 'wiki-product', 'wiki-pricing', 'wiki-delivery', 'wiki-claims', 'wiki-localization']; }
  function makeRisk(id, title, message, suggestion, category, sources, severity) {
    return { id: id, title: title, message: message, suggestion: suggestion, category: category, severity: severity || 'warning', sourceIds: sources, field: id };
  }

  function calculateQuote(sku, quantity, optionStatus) {
    var product = findProduct(sku);
    if (!product) return { ok: false, message: '这个SKU不在演示商品目录中，请选择现货或定制帆布袋。' };
    if (!Number.isSafeInteger(quantity) || quantity <= 0 || quantity > 100000) return { ok: false, message: '数量必须是1到100000之间的整数，请重新输入。' };
    if (quantity < product.moq) return { ok: false, message: product.name + '的起订量是' + product.moq + '件，当前' + quantity + '件不足起订量。' };
    if (product.stock !== null && quantity > product.stock) return { ok: false, message: '现货可用库存为' + product.stock + '件，' + quantity + '件超出库存。请减少数量，或明确改为定制方案。' };
    var tier = product.priceTiers.find(function (p) { return quantity >= p.min && (p.max === null || quantity <= p.max); });
    if (!tier) return { ok: false, message: '没有匹配到这一数量的价格阶梯，不能自动补造价格。' };
    return { ok: true, quote: { quantity: quantity, sku: sku, productName: product.name, unitPrice: money(tier.cents), goodsSubtotal: money(quantity * tier.cents), currency: 'USD', freight: null, tax: null, total: null, dispatchDays: product.dispatchDays, productionDays: product.productionDays, transitDays: null, arrivalGuaranteed: false, optionStatus: optionStatus || 'proposed', validityDays: 7, paymentTerms: null, startsAfter: sku === 'BAG-STOCK' ? '付款条件满足后' : '稿件及付款条件满足后', sourceIds: [sku, 'wiki-pricing', 'wiki-delivery'], calculation: quantity + ' × ' + money(tier.cents) + ' = ' + money(quantity * tier.cents), calculationMode: 'browser-integer-cents' } };
  }

  function buildSnapshot(input) {
    input = input || {};
    var revision = Number.isInteger(input.revision) ? input.revision : 1;
    var stage = Number.isInteger(input.stage) ? input.stage : 1;
    var quantity = input.quantity === undefined ? 1000 : input.quantity;
    var sku = input.sku || 'BAG-CUSTOM';
    var optionStatus = input.optionStatus || 'requested';
    var arrivalDays = input.arrivalDays === undefined ? 10 : input.arrivalDays;
    var customization = input.customization === undefined ? true : input.customization;
    var certificationRequested = input.certificationRequested !== false;
    var product = findProduct(sku);
    var quote = null;
    var risks = [];
    var requirements = { quantity: quantity, requestedSku: 'BAG-CUSTOM', selectedSku: sku, sku: sku, optionStatus: optionStatus, arrivalDays: arrivalDays, customization: customization, certificationRequested: certificationRequested, destination: '墨西哥', market: 'MX', freightConfirmed: false, transportConfirmed: false };
    if (stage >= 2) {
      var calculation = calculateQuote(sku, quantity, optionStatus);
      if (calculation.ok) quote = calculation.quote;
      else risks.push(makeRisk('invalid-quote', '无法生成有效报价', calculation.message, '调整数量或商品方案后重新计算。', 'terms', ['wiki-product', 'wiki-pricing'], 'error'));
    }
    if (certificationRequested) risks.push(makeRisk('certification', '认证资料待确认', '当前商品资料未提供认证证明，客户提出认证问题仍需补充依据。', '回复中保留“认证资料待确认”，不要写成已取得认证。', 'platform', ['wiki-claims', 'wiki-product']));
    if (sku === 'BAG-CUSTOM' && product && product.productionDays > arrivalDays) risks.push(makeRisk('leadtime', '生产与到货要求冲突', '定制生产需要14天，无法据此承诺' + arrivalDays + '天内到货。', '向客户澄清可接受时间，或提出有资料依据的现货方案。', 'terms', ['wiki-delivery']));
    else risks.push(makeRisk('arrival', '运输与到货时间待确认', (sku === 'BAG-STOCK' ? '3天是出库时间' : '14天是生产时间') + '，运输时效尚未提供，不能保证' + arrivalDays + '天内到货。', '明确区分生产、出库与到货，并确认目的地和运输方案。', 'terms', ['wiki-delivery']));
    if (sku === 'BAG-CUSTOM' && quantity < 500) risks.push(makeRisk('requested-moq', '定制数量未达起订量', quantity + '件低于定制款500件起订量。', '增加定制数量，或提出无印花现货备选。', 'terms', ['wiki-product']));
    if (sku === 'BAG-STOCK' && customization && quantity < 500) risks.push(makeRisk('original-moq', '原定制要求未达起订量', quantity + '件低于定制款500件起订量；现货是无印花备选。', '请客户确认是否接受无印花现货，保留原始定制要求。', 'terms', ['wiki-product']));
    if (sku === 'BAG-STOCK' && optionStatus === 'proposed') risks.push(makeRisk('acceptance', '备选方案等待客户接受', '已提出现货方案，但不能把提出备选写成客户已经同意。', '请客户确认现货无印花方案。', 'terms', ['wiki-localization']));
    if (quote) {
      risks.push(makeRisk('costs', '运费与税费未包含', 'USD ' + quote.goodsSubtotal + '是商品小计，最终总额、运费和税费待确认。', '报价中将商品小计与最终总额分开显示。', 'terms', ['wiki-pricing']));
      risks.push(makeRisk('payment', '付款条件待确认', '出库计时以付款条件满足为前提，但具体付款条款还未约定。', '在确认报价前补充付款方式与相关条件。', 'terms', ['wiki-pricing', 'wiki-delivery']));
    }

    var replyEn, replyEs, summary;
    if (sku === 'BAG-STOCK') {
      var openingEn = optionStatus === 'accepted' ? 'Thank you for confirming the unprinted stock option.' : 'For your trial order, we can propose unprinted stock bags. Please confirm whether this alternative is acceptable.';
      var openingEs = optionStatus === 'accepted' ? 'Gracias por confirmar la opción de bolsas sin impresión en existencia.' : 'Para su pedido de prueba, podemos proponer bolsas sin impresión en existencia. Confirme si acepta esta alternativa.';
      var moqEn = customization && quantity < 500 ? ' The custom option requires at least 500 units, so ' + count(quantity) + ' units do not meet its minimum order.' : '';
      var moqEs = customization && quantity < 500 ? ' La opción personalizada requiere al menos 500 unidades; ' + count(quantity) + ' unidades no cumplen ese mínimo.' : '';
      var priceEn = quote ? ' For ' + count(quantity) + ' units at USD ' + quote.unitPrice + ' each, the goods subtotal is USD ' + quote.goodsSubtotal + '.' : ' A valid quotation is pending confirmation of the quantity and available supply.';
      var priceEs = quote ? ' Para ' + count(quantity) + ' unidades a USD ' + quote.unitPrice + ' cada una, el subtotal de la mercancía es de USD ' + quote.goodsSubtotal + '.' : ' La cotización queda pendiente de confirmar la cantidad y la disponibilidad.';
      replyEn = openingEn + moqEn + priceEn + ' Dispatch is within 3 days after payment conditions are met; this is not an arrival guarantee. Freight, taxes and transit time remain to be confirmed.' + (certificationRequested ? ' Certification evidence has not been provided.' : '') + ' Please confirm the delivery address and postal code so we can clarify shipping conditions.';
      replyEs = openingEs + moqEs + priceEs + ' La salida del almacén se realiza dentro de los 3 días posteriores al cumplimiento de las condiciones de pago; esto no garantiza la fecha de llegada. El flete, los impuestos y el tiempo de tránsito quedan por confirmar.' + (certificationRequested ? ' No se ha proporcionado documentación de certificación.' : '') + ' Confirme la dirección y el código postal para aclarar las condiciones de envío.';
      summary = (optionStatus === 'accepted' ? '客户已接受' : '已提出') + quantity + '件现货无印花方案' + (optionStatus === 'accepted' ? '。' : '，等待客户确认。') + (quote ? '商品小计 USD ' + quote.goodsSubtotal + '。' : '数量与供货条件需重新确认。') + '3天出库，运费与到货时间待确认。';
    } else {
      replyEn = 'Thank you for your inquiry for ' + count(quantity) + ' custom canvas bags. Production takes 14 days after artwork and payment conditions are confirmed.' + (arrivalDays < 14 ? ' We therefore cannot commit to arrival within ' + arrivalDays + ' days.' : ' Transit time and the final arrival date still need to be confirmed.') + (quote ? ' At USD ' + quote.unitPrice + ' per unit, the goods subtotal is USD ' + quote.goodsSubtotal + '; freight, taxes and the final total remain unconfirmed.' : '') + (certificationRequested ? ' Certification evidence has not been provided.' : '') + ' Please confirm your destination, specifications and whether a later arrival would work.';
      replyEs = 'Gracias por su consulta sobre ' + count(quantity) + ' bolsas de lona personalizadas. La producción tarda 14 días después de confirmar el diseño y las condiciones de pago.' + (arrivalDays < 14 ? ' Por ello, no podemos comprometernos a la llegada dentro de ' + arrivalDays + ' días.' : ' El tiempo de tránsito y la fecha final de llegada aún deben confirmarse.') + (quote ? ' A USD ' + quote.unitPrice + ' por unidad, el subtotal de la mercancía es de USD ' + quote.goodsSubtotal + '; el flete, los impuestos y el total final quedan por confirmar.' : '') + (certificationRequested ? ' No se ha proporcionado documentación de certificación.' : '') + ' Confirme el destino, las especificaciones y si puede aceptar una fecha posterior.';
      summary = '客户需要' + quantity + '件定制帆布袋，希望' + arrivalDays + '天内收到。' + (arrivalDays < 14 ? '生产需要14天，存在交期冲突。' : '运输时效仍待确认。') + (quote ? '商品小计 USD ' + quote.goodsSubtotal + '。' : '') + (certificationRequested ? '认证证据待补充。' : '');
    }

    var checks = [
      { id: 'fact-check', title: '商品事实一致', status: 'passed', message: '数量、SKU与来源资料保持关联。', sourceIds: ['wiki-product'] },
      { id: 'claim-check', title: '声明与认证检查', status: certificationRequested ? 'warning' : 'passed', message: certificationRequested ? '回复保留认证证据缺失提示。' : '未生成未经证实的认证声明。', sourceIds: ['wiki-claims'] },
      { id: 'time-check', title: '交期含义检查', status: 'warning', message: '保留生产/出库与到货的区别，运输时间待确认。', sourceIds: ['wiki-delivery'] },
      { id: 'money-check', title: '报价金额检查', status: quote ? 'passed' : stage >= 2 ? 'warning' : 'pending', message: quote ? quote.calculation + '（USD，整数分计算）' : '尚未生成有效报价。', sourceIds: ['wiki-pricing'] }
    ];
    var checklist = [
      { id: 'supply', text: sku === 'BAG-STOCK' ? '核对' + quantity + '件现货的实际可用库存' : '核对定制规格与生产条件', capability: '采购能力', done: false },
      { id: 'material', text: '选择对应SKU的产品素材与尺寸资料', capability: '美工能力', done: false },
      { id: 'terms', text: '补充运费、税费、运输和付款条件', capability: '业务能力', done: false },
      { id: 'evidence', text: certificationRequested ? '补充认证证据或向客户明确资料缺失' : '检查对外声明与商品资料是否一致', capability: '合规能力', done: false }
    ];
    return { id: 'revision-' + revision, revision: revision, stage: stage, label: 'V' + revision, isDemo: true, generationMode: 'simulated', requirements: requirements, quote: quote, replyEn: replyEn, replyEs: replyEs, summary: summary, risks: risks, checks: checks, checklist: checklist, changes: [], sourceIds: sourceIdsFor(sku), selectedAssetIds: sku === 'BAG-STOCK' ? ['asset-stock', 'asset-size'] : ['asset-custom', 'asset-size'], timestamp: new Date().toISOString() };
  }

  function capabilitiesForRun(mode, producesQuote) {
    var ids = mode === 'analysis' ? ['inquiry-skill', 'product-mcp'] : ['product-mcp'];
    if (mode !== 'analysis' || producesQuote) ids = ids.concat(['quote-skill', 'quote-cli']);
    return ids.concat(['reply-skill', 'compliance-skill']);
  }

  function makeLogs(mode, revision, producesQuote) {
    var ids = capabilitiesForRun(mode, producesQuote);
    return ids.map(function (id, index) {
      var capability = DATA.capabilities.find(function (c) { return c.id === id; });
      return { id: 'r' + revision + '-log-' + index, capabilityId: id, name: capability.name, type: capability.type, status: 'completed', revision: revision, simulated: true, mode: 'simulated', label: '演示步骤', message: id === 'quote-cli' ? '金额由浏览器整数分计算；CLI调用仅作交互模拟。' : id === 'product-mcp' ? '读取本地演示商品资料；没有连接真实MCP服务。' : '使用预置规则和文本模板模拟能力执行，没有模型调用。' };
    });
  }

  function createEmptyState() {
    return { revision: 0, stage: 0, quantity: 1000, sku: 'BAG-CUSTOM', optionStatus: 'requested', arrivalDays: 10, customization: true, certificationRequested: true, language: 'es-MX', messages: [], enabled: DATA.capabilities.map(function (c) { return c.id; }), versions: [], logs: [], savedAssets: [], positions: {}, selected: [], currentSnapshot: null, isDemo: true, generationMode: 'simulated' };
  }

  function createInitialState() {
    var state = createEmptyState();
    var seed = clone(state); seed.revision = 1; seed.stage = 1;
    var snap = buildSnapshot(seed);
    state.revision = 1; state.stage = 1;
    state.messages = [{ role: 'user', text: SCENARIO_PROMPTS[0], time: '演示记录' }, { role: 'assistant', text: '已载入演示案例 V1。' + snap.summary + '你可以继续修改数量、查看来源，或选择画板内容准备下一步。', time: '演示记录' }];
    state.versions = [snap]; state.currentSnapshot = clone(snap); state.logs = makeLogs('analysis', 1);
    return state;
  }

  function extractQuantity(text) {
    var matched = text.match(/([+-]?\d[\d,]*(?:\.\d+)?)\s*(?:个|件|只|pcs\b|pieces?\b|units?\b|bags?\b)/i);
    if (!matched) matched = text.match(/(?:数量|quantity)\s*(?:改为|改成|调整为|为|是|to|is|:|：)?\s*([+-]?\d[\d,]*(?:\.\d+)?)/i);
    return matched ? Number(matched[1].replace(/,/g, '')) : null;
  }

  function extractArrival(text, fallback) {
    var matched = text.match(/(?:希望|要求|需要|最晚|within)\s*(\d+)\s*(?:天|days)/i) || text.match(/(\d+)\s*天(?:内)?\s*(?:收到|到货|要用|使用)/);
    return matched ? Number(matched[1]) : fallback;
  }

  function getCurrentSnapshot(state) {
    if (state.currentSnapshot) return clone(state.currentSnapshot);
    if (state.versions && state.versions.length) return clone(state.versions[state.versions.length - 1]);
    return null;
  }

  function failure(state, notice, code) {
    return { ok: false, state: state, snapshot: getCurrentSnapshot(state), mode: 'clarify', notice: notice, code: code || 'UNSUPPORTED_INPUT' };
  }

  function applyInstruction(state, instruction) {
    var text = String(instruction || '').trim();
    if (!text) return failure(state, '请输入需求，或使用下方的演示建议。', 'EMPTY_INPUT');
    if (text.length > 5000) return failure(state, '演示输入请控制在5000字以内。', 'INPUT_TOO_LONG');
    var quantity = extractQuantity(text);
    if (quantity !== null && (!Number.isSafeInteger(quantity) || quantity < 1 || quantity > 100000)) return failure(state, '数量必须是1到100000之间的整数，不能是零、负数或小数。', 'INVALID_QUANTITY');
    var stockClauses = (text.match(/[^。！？!?；;\n]+[！？!?]?/g) || []).filter(function (clause) { return /现货|无印花|\bstock\b|\bunprinted\b/i.test(clause); });
    var stockDeclined = stockClauses.some(function (clause) {
      return /(?:不(?:能|会|想|再)?|未|尚未|没有|还没|暂不).{0,4}(?:接受|同意|确认|采用|选用|使用)|拒绝|取消|不要|\b(?:reject(?:ed)?|declin(?:e|ed)|not|never|cannot|can.t|won.t|hasn.t|haven.t|doesn.t|don.t)\b.{0,20}\b(?:accept(?:ed)?|confirm(?:ed)?|use|stock|unprinted)\b/i.test(clause);
    });
    if (stockDeclined) return failure(state, '这条输入没有明确接受现货。这个演示不会擅自确认方案；请明确改为多少件定制，或调整需求后继续。', 'REQUIRES_CLARIFICATION');
    var stockUnconfirmed = stockClauses.some(function (clause) {
      return /[？?]|是否|能否|可否|有没有|是不是|吗|么|待确认|等待.{0,8}确认|(?:请|让|询问|问一下|要求|希望|需要).{0,12}(?:客户|买家|对方)?.{0,8}(?:接受|同意|确认)|\b(?:ask|asking|whether|if|please|pending|awaiting)\b.{0,40}\b(?:accept(?:ed)?|confirm(?:ed)?|use)\b/i.test(clause);
    });
    if (stockUnconfirmed) return failure(state, '这里仍在询问或等待客户确认，尚不能标记为已接受。客户明确同意后，可输入“客户接受现货无印花方案”；当前版本保持不变。', 'REQUIRES_CLARIFICATION');
    var confirmStock = /(?:接受|同意|确认|采用|就用|选用).{0,8}(?:现货|无印花)|(?:现货|无印花).{0,8}(?:可以|接受|同意)|(?:accept|confirm|use).{0,20}(?:stock|unprinted)/i.test(text);
    var wantsStock = /现货|无印花|stock|unprinted/i.test(text);
    var explicitCustom = /(?:改成|改为|换成|选择|需要|要|采用|用).{0,10}定制|(?:custom).{0,10}(?:option|bags)|(?:choose|use).{0,12}custom/i.test(text) && !wantsStock;
    var analysis = /分析|理解询盘|analyse|analyze/i.test(text) && !/报价|quote|quotation/i.test(text);
    var known = quantity !== null || confirmStock || wantsStock || explicitCustom || analysis || /报价|重新计算|更新回复|更新报价|quote|quotation/i.test(text);
    if (!known) return failure(state, '这是交互原型，支持询盘分析、修改数量、提出现货备选和接受现货。试试“改成600件，更新报价”，或点击演示建议；这里不会调用通用AI模型。');

    var next = clone(state);
    if (quantity !== null) next.quantity = quantity;
    next.arrivalDays = extractArrival(text, next.arrivalDays || 10);
    if (!Number.isSafeInteger(next.arrivalDays) || next.arrivalDays <= 0 || next.arrivalDays > 365) return failure(state, '请提供1到365天之间的期望到货时间。', 'INVALID_ARRIVAL');
    var mode = analysis && (!state.stage || !wantsStock) ? 'analysis' : confirmStock ? 'confirm' : 'quote';
    if (confirmStock) {
      next.sku = 'BAG-STOCK'; next.optionStatus = 'accepted'; next.customization = false; next.stage = 3;
    } else if (explicitCustom) {
      next.sku = 'BAG-CUSTOM'; next.optionStatus = 'requested'; next.customization = true; next.stage = mode === 'analysis' ? 1 : 2;
    } else if (wantsStock || (next.sku === 'BAG-CUSTOM' && next.quantity < 500 && mode !== 'analysis')) {
      next.sku = 'BAG-STOCK'; next.optionStatus = 'proposed'; next.stage = 2;
    } else if (mode === 'analysis') {
      next.stage = Math.max(1, next.stage || 0);
    } else {
      next.stage = next.optionStatus === 'accepted' ? 3 : 2;
    }
    var required = capabilitiesForRun(mode, next.stage >= 2);
    var enabled = Array.isArray(state.enabled) ? state.enabled : [];
    var missing = required.filter(function (id) { return enabled.indexOf(id) === -1; });
    if (missing.length) {
      var names = missing.map(function (id) { return DATA.capabilities.find(function (c) { return c.id === id; }).name; });
      return failure(state, '这一步需要启用「' + names.join('」「') + '」。请到能力市场启用后重试，当前版本保持不变。', 'CAPABILITY_DISABLED');
    }
    if (next.stage >= 2) {
      var calculated = calculateQuote(next.sku, next.quantity, next.optionStatus);
      if (!calculated.ok) return failure(state, calculated.message, 'BUSINESS_VALIDATION_FAILED');
    }
    next.revision = (Number(state.revision) || 0) + 1;
    var snapshot = buildSnapshot(next);
    var fields = [['quantity', '数量'], ['sku', '商品方案'], ['optionStatus', '方案状态'], ['arrivalDays', '期望到货'], ['customization', '定制要求']];
    snapshot.changes = fields.filter(function (f) { return state[f[0]] !== next[f[0]]; }).map(function (f) { return { field: f[0], label: f[1], before: state[f[0]], after: next[f[0]] }; });
    var beforeQuote = getCurrentSnapshot(state);
    if (snapshot.quote && (!beforeQuote || !beforeQuote.quote || beforeQuote.quote.goodsSubtotal !== snapshot.quote.goodsSubtotal)) snapshot.changes.push({ field: 'goodsSubtotal', label: '商品小计', before: beforeQuote && beforeQuote.quote ? beforeQuote.quote.goodsSubtotal : null, after: snapshot.quote.goodsSubtotal });
    next.versions = (state.versions || []).map(clone).concat([clone(snapshot)]);
    next.currentSnapshot = clone(snapshot);
    next.messages = (state.messages || []).map(clone).concat([{ role: 'user', text: text, time: '刚刚' }, { role: 'assistant', text: '演示已更新到 V' + next.revision + '。' + snapshot.summary + ' 相关回复、报价和核对项已同步；生成内容采用本地模板，未调用真实模型。', time: '刚刚' }]);
    next.logs = (state.logs || []).map(clone).concat(makeLogs(mode, next.revision, next.stage >= 2));
    next.isDemo = true; next.generationMode = 'simulated';
    return { ok: true, state: next, snapshot: clone(snapshot), mode: mode, notice: 'V' + next.revision + ' 已更新 · 演示数据与模拟生成' };
  }

  return { DATA: DATA, createInitialState: createInitialState, createEmptyState: createEmptyState, buildSnapshot: buildSnapshot, applyInstruction: applyInstruction, calculateQuote: calculateQuote, getCurrentSnapshot: getCurrentSnapshot, clone: clone };
}));

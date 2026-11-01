"""Business source definitions, independent of the application's computed artifacts.

All identities, supplier allocations, observations and events are simulated.
Legacy seeds remain untouched; this is a separate, internally consistent story.
"""
from copy import deepcopy

DATE = '2026-11-01'
CUSTOMER = 'Nordlicht Outdoor GmbH (SIMULATED)'
SKU = 'BP-DE-3000-DEMO'
SPEC = {
    'product': 'SIMULATED commuter backpack BP-DE-3000-DEMO', 'quantity': '3000',
    'dimensions': 'W30 x H45 x D15 cm; +/-1 cm', 'color': 'dark grey / orange pull accents',
    'fabric': '600D recycled polyester; 300 gsm; supplier claim, report pending',
    'lining': '210D polyester, dark grey', 'filling': '8 mm EVA back panel',
    'zipper': 'YKK #5 nylon; supplier claim, authenticity pending',
    'buckle': 'black acetal; no brand certification claim', 'webbing': '25 mm PP',
    'structure': '15.6 inch padded laptop sleeve; two side pockets; front zip pocket',
    'logo': 'embroidered 60 x 25 mm; front center; position per TP-NL-V1',
    'packaging': 'standard polybag + hangtag', 'cartonQty': '20',
    'cartonSize': '60 x 45 x 50 cm, standard folded packing only',
    'inspection': 'project sampling proposal: n=125; critical 0, major <=7, minor <=10; not ISO certification',
    'destination': 'Hamburg, Germany', 'incoterm': 'FOB', 'incotermsVersion': '2020',
    'namedPlace': 'Ningbo', 'paymentTerms': '30% deposit, 70% before shipment',
    'delivery': '28 days after sample approval and deposit; transit excluded; estimate',
}
SPEC_V2 = {**SPEC, 'logo': 'embroidered 60 x 25 mm; down 10 mm vs TP-NL-V1; darker thread',
           'packaging': 'CB-02-DEMO color box, 47 x 32 x 17 cm; physical fit trial pending',
           'cartonQty': '2', 'cartonSize': '50 x 35 x 38 cm; 1500 cartons; packed weight unknown',
           'delivery': '31 days after sample approval and deposit; transit excluded; estimate'}

# This new simulated supplier allocation does not claim to have existed in the old flat quote.
BOM = [
    ['material', 'Shell fabric', '600D polyester / 300 gsm', .6, 'm', 'Factory A demo', 20, .05, 'NL-ALLOC-V1'],
    ['material', 'Lining', '210D polyester', .45, 'm', 'Factory A demo', 8, 0, 'NL-ALLOC-V1'],
    ['material', 'EVA padding', '8 mm', .2, 'm2', 'Factory A demo', 12, 0, 'NL-ALLOC-V1'],
    ['accessory', 'Zipper', 'YKK #5 supplier claim', .75, 'm', 'Factory A demo', 8, 0, 'NL-ALLOC-V1'],
    ['accessory', 'Buckles', 'black acetal', 2, 'pc', 'Factory A demo', 1, 0, 'NL-ALLOC-V1'],
    ['accessory', 'Webbing', '25 mm PP', 1, 'm', 'Factory A demo', 2, 0, 'NL-ALLOC-V1'],
    ['accessory', 'Embroidery', '60 x 25 mm', 1, 'pc', 'Factory A demo', 2, 0, 'NL-ALLOC-V1'],
    ['labor', 'Sewing and assembly', 'per finished bag', 1, 'pc', 'Factory A demo', 10, 0, 'NL-ALLOC-V1'],
    ['overhead', 'Factory allocation', 'per finished bag', 1, 'pc', 'Factory A demo', 3.4, 0, 'NL-ALLOC-V1'],
    ['packaging', 'Standard packaging', 'polybag + hangtag', 1, 'set', 'Factory A demo', 2, 0, 'NL-ALLOC-V1'],
    ['domesticFreight', 'Local allocation', 'domestic handling only', 1, 'pc', 'Seller demo', 4, 0, 'NL-FIN-V1'],
]
COLUMNS = ['category', 'item', 'spec', 'quantityPerPiece', 'unit', 'supplier', 'unitPriceCny', 'wastage', 'sourceId']


def doc(key, title, role, category, sections, *, audience='internal', stage='reference', folder=None):
    return dict(key=key, title=title, role=role, category=category, sections=sections,
                audience=audience, stage=stage, folder=folder or f'Nordlicht/{category:02d} 核心文件')


DOCUMENTS = [
    doc('01_customer_profile', '客户档案 Customer profile', 'internal_note', 1, [
        ('客户主体', [('公司', CUSTOMER), ('联系人', 'Michael Weber; buyer@nordlicht.example.invalid'),
         ('市场/渠道', 'Germany; simulated retailer inquiry'), ('资信核验', 'UNKNOWN; no registry, payment or credit check performed')])]),
    doc('02_customer_RFQ', '客户询盘 RFQ', 'customer_request', 2, [
        ('客户原始要求', [('买方', CUSTOMER), ('产品', SKU), ('数量', '3000 pcs'), ('用途', 'Urban commuter backpack'),
         ('结构', '15.6 inch laptop sleeve, two side pockets, front pocket'), ('材料要求', '600D recycled polyester; supplier evidence required'),
         ('贸易条件', 'FOB Ningbo Incoterms 2020'), ('到货愿望', 'Hamburg within 45 days if feasible; not a guaranteed arrival'),
         ('待确认', 'dimensions, material weight, logo size, packaging, inspection, sample time')])], audience='customer', stage='initial'),
    doc('03_inquiry_assessment', '询盘评估 Inquiry assessment', 'internal_note', 3, [
        ('评估', [('路径', 'ODM customization; existing commuter bag plus logo and packing changes'),
         ('已知', '3000 pcs; Germany; FOB Ningbo; customer requests delivery feasibility'),
         ('缺项', 'registered buyer identity, certifications, exact packing, transit estimate'),
         ('下一步', 'Confirm priceable specification and request supplier line allocation; no formal release')])]),
    doc('04_requirements', '产品需求确认 Priceable requirements', 'customer_request', 4, [
        ('核价规格基线', [(k, v) for k, v in SPEC.items()]),
        ('确认范围', [('版本', 'TP-NL-V1, initial priceable baseline only'), ('边界', 'No sample approval; no manufacturing release')])], stage='initial'),
    doc('05_techpack_V1', '产品规格书 Tech Pack TP-NL-V1', 'customer_request', 5, [
        ('TP-NL-V1 规格', [(k, v) for k, v in SPEC.items()]),
        ('待验证', [('合规', 'REACH/AZO and recycled content reports UNKNOWN; no passed claim'),
         ('附件', 'logo-demo.svg, product-reference.png; both illustrative, not engineering drawings')])], stage='initial'),
    doc('05_techpack_V2', '产品规格书 Tech Pack TP-NL-V2', 'customer_request', 5, [
        ('完整修订规格候选（批准见独立证据）', [(k, v) for k, v in SPEC_V2.items()])], stage='followup'),
    doc('06_packing_V2', '包装与验货 Packing and inspection V2', 'supplier_confirmation', 6, [
        ('彩盒方案 CB-02-DEMO', [('折叠产品', '45 x 30 x 15 cm bag; fit trial still required'),
         ('零售彩盒', '47 x 32 x 17 cm outside dimensions'), ('装箱', '2 boxes per carton; 50 x 35 x 38 cm outside'),
         ('体积预检', '2 x 47 x 32 x 17 cm fits nominal carton; internal clearance and strength require physical test'),
         ('箱数', '1500 cartons for 3000 pcs; previous 20/carton applies only to standard folded packing'),
         ('重量', 'UNKNOWN until packed sample weighing'), ('验货', SPEC['inspection']),
         ('包装成本/交期', 'CNY 5/pc replaces CNY 2/pc; MOQ 1000; 31 days after sample and deposit; estimate')])], stage='followup'),
    doc('07_customer_confirmation', '客户需求确认记录 Confirmation scope', 'customer_approval', 7, [
        ('模拟确认记录', [('对象', 'TP-NL-V2 + CB-02-DEMO only'), ('确认内容', 'logo moved down 10 mm; 60 x 25 mm; 2 color boxes per carton'),
         ('不含', 'No acceptance of unrelated quotation versions; no physical sample or payment confirmation'),
         ('证据', 'customer-spec-v2.eml; simulated; record approval separately against actual application version')])], stage='followup'),
    doc('08_supplier_terms', '供应商报价条件 Supplier terms', 'supplier_quote', 8, [
        ('Factory A 价格与范围', [('报价', 'FA-NL-V1 / FA-NL-V2; see native supplier XLSX'),
         ('制造', 'CNY 44/pc including logo; supporting allocation NL-ALLOC-V1'),
         ('包装', 'V1 CNY 2 polybag; V2 CNY 5 color box, replacement not addition'),
         ('本地费用', 'CNY 4/pc domestic handling; export customs and inspection excluded'),
         ('MOQ/有效期', '1000 pcs; 2026-11-30'), ('生产估计', 'V1 28 days; V2 31 days after sample approval and deposit'),
         ('未定费用', 'inspection and export customs UNKNOWN; quotation remains conditional'),
         ('属性', 'All allocations and supplier confirmations here are newly simulated sources')])], stage='initial'),
    doc('10_quotation_V1', '客户条件报价 QT-NL-V1', 'internal_note', 10, [
        ('对客报价草稿', [('Buyer', CUSTOMER), ('Product', SKU), ('Quantity', '3000 pcs'), ('Unit price', 'USD 8.69'),
         ('Total', 'USD 26070.00'), ('Terms', 'FOB Ningbo Incoterms 2020; conditional scope'),
         ('Payment', SPEC['paymentTerms']), ('Valid until', '2026-11-30'),
         ('Exclusions', 'Export customs and inspection pending; ocean freight, insurance, import taxes excluded'),
         ('Status', 'SIMULATED DRAFT; not sent; not customer accepted')])], audience='customer'),
    doc('10_quotation_V2', '客户条件报价 QT-NL-V2', 'internal_note', 10, [
        ('彩盒报价草稿', [('Buyer', CUSTOMER), ('Product', SKU), ('Quantity', '3000 pcs'), ('Unit price', 'USD 9.21'),
         ('Total', 'USD 27630.00'), ('Packing', 'CB-02-DEMO; 2/carton; 1500 cartons'),
         ('Terms', 'FOB Ningbo Incoterms 2020; conditional, pending excluded charges'),
         ('Payment', SPEC['paymentTerms']), ('Valid until', '2026-11-30'),
         ('Production', '31 days after approved sample and deposit; estimated; transit excluded'),
         ('Exclusions', 'Export customs and inspection pending; ocean freight, insurance and import taxes excluded'),
         ('Status', 'SIMULATED DRAFT; not sent; no approval inferred')])], audience='customer'),
    doc('11_sample_request', '打样申请 Sample request', 'internal_note', 11, [
        ('打样要求', [('Sample', 'SMP-NL-001; development sample, 2 pcs'), ('Baseline', 'TP-NL-V1'),
         ('费用', 'USD 60 sample fee + USD 35 courier estimate; not paid'), ('预计用时', '7 calendar days after artwork confirmation; estimated'),
         ('验收', 'appearance, dimensions, function, workmanship and packaging'), ('状态', 'Instruction only; no physical sample claimed')])]),
    doc('12_sample_feedback', '样品反馈及修改 Sample feedback', 'sample_inspection', 12, [
        ('SMP-NL-001 模拟反馈', [('通过', 'zipper and laptop sleeve'), ('修改', 'move logo down 10 mm; darker thread'),
         ('包装', 'switch to CB-02-DEMO; requires supplier cost and packing review'),
         ('结论', 'Conditional feedback; no final sample approval'), ('修订目标', 'TP-NL-V2; request sample SMP-NL-002')])], stage='followup'),
    doc('13_sample_confirmation', '最终样品确认 Final sample confirmation', 'customer_approval', 13, [
        ('独立后续事件', [('Sample', 'SMP-NL-002; simulated physical sample event'), ('Scope', 'TP-NL-V2 and CB-02-DEMO only'),
         ('Decision', 'Simulated unconditional sample approval'), ('Source', 'customer-sample-v2.eml'),
         ('仍待确认', 'contract acceptance; payment verification; supplier release; internal production release'),
         ('系统登记', 'File existence does not create an approval; bind to the actual current application artifact')])], stage='followup'),
    doc('14a_PO_matching', '客户采购订单 PO-NL-001', 'customer_po', 14, [
        ('模拟买方文件', [('Buyer', CUSTOMER), ('Seller', 'NavoWork Demo Trading'), ('PO', 'PO-NL-001; 2026-11-01'),
         ('Product', SKU), ('Quantity', '3000'), ('Unit price', 'USD 9.21'), ('Total', 'USD 27630.00'),
         ('Baseline', 'TP-NL-V2; QT-NL-V2 commercial terms'), ('Packing', 'CB-02-DEMO; 2/carton; 1500 cartons'),
         ('Incoterms', 'FOB Ningbo Incoterms 2020'), ('Payment', SPEC['paymentTerms']),
         ('Delivery', '31 calendar days after sample approval and deposit, estimate; no arrival guarantee'),
         ('Pending', 'seller acceptance and excluded export/customs/inspection charges remain unresolved')])], audience='customer', stage='followup'),
    doc('14b_PI_draft', '形式发票 PI-NL-001 draft', 'internal_note', 14, [
        ('未签署 PI 草稿', [('Buyer', CUSTOMER), ('Seller', 'NavoWork Demo Trading'), ('PO reference', 'PO-NL-001'),
         ('Product', SKU), ('Quantity', '3000'), ('Unit price', 'USD 9.21'), ('Total', 'USD 27630.00'),
         ('Deposit due', 'USD 8289.00; receipt UNKNOWN'), ('Balance due', 'USD 19341.00 before shipment'),
         ('Terms', 'FOB Ningbo Incoterms 2020'), ('Pending', 'packing fit trial, contract acceptance, excluded costs'),
         ('Status', 'Draft permitted before sample approval; not a payment receipt or production release')])], audience='customer'),
    doc('14c_SC_draft', '销售合同 SC-NL-001 draft', 'internal_note', 14, [
        ('合同候选', [('Parties', CUSTOMER + ' / NavoWork Demo Trading'), ('Commercial reference', 'QT-NL-V2 / PO-NL-001 / PI-NL-001'),
         ('Goods', '3000 x BP-DE-3000-DEMO'), ('Amount', 'USD 27630.00'), ('Payment', SPEC['paymentTerms']),
         ('Technical attachment', 'TP-NL-V2; CB-02-DEMO'), ('Outstanding', 'export/customs/inspection charges; acceptance; dispute terms; dates'),
         ('Signature', 'UNSIGNED DRAFT; no contract conclusion or real transaction')])], audience='customer'),
    doc('15_order_annex', '最终订单技术附件 Candidate order annex V2', 'internal_note', 15, [
        ('版本关联', [('Product', SKU), ('Spec', 'TP-NL-V2 candidate; logo down 10 mm vs V1'),
         ('Sample', 'SMP-NL-002 only if its simulated evidence is separately recorded'),
         ('Packing', '47 x 32 x 17 cm CB-02-DEMO; 2/carton; carton 50 x 35 x 38 cm; fit test pending'),
         ('QC', SPEC['inspection']), ('Certification', 'Reports pending; no passed claim'),
         ('Release', 'Not authorized; source file and synchronized drafts do not mean production release')])]),
    doc('po_conflict', '冲突采购订单 PO-NL-CONFLICT', 'customer_po', 0, [
        ('保留买方原文差异', [('Buyer', CUSTOMER), ('Product', SKU), ('Quantity', '3200'), ('Unit price', 'USD 9.21'),
         ('Total', 'USD 29472.00'), ('Incoterms', 'FOB Shanghai Incoterms 2020'),
         ('Payment', '30% deposit, 70% against BL copy'), ('Packing', '20 color boxes/carton; carton 60 x 45 x 50 cm'),
         ('Delivery', 'guaranteed Hamburg arrival within 45 days'),
         ('预期处理', 'Compare quantity, total, named port, payment, packing volume and delivery guarantee; do not rewrite buyer PO')])], stage='negative', folder='Nordlicht/差异核对'),
    doc('competitor_a', '竞品来源快照 Aster Daypack', 'internal_note', 0, [
        ('Archived simulated retail page', [('Source URL', 'https://aster.example.invalid/daypack-22'), ('Observed at', DATE),
         ('Scope', 'Fictional EU retail listing; no real browsing or market-share evidence'), ('Product', 'Aster Daypack 22'),
         ('Fabric', 'recycled polyester'), ('Features', 'front zip pocket; laptop sleeve'), ('Retail price', 'EUR 69'),
         ('Limit', 'Retail price does not establish our cost, certification or manufacturing feasibility')])], folder='研究/虚构竞品快照'),
    doc('competitor_b', '竞品来源快照 Fjord Metro', 'internal_note', 0, [
        ('Archived simulated retail page', [('Source URL', 'https://fjord.example.invalid/metro-20'), ('Observed at', DATE),
         ('Scope', 'Fictional EU retail listing, not supplier pricing'), ('Product', 'Fjord Metro 20'),
         ('Fabric', 'coated polyester'), ('Features', 'roll top; two bottle pockets'), ('Retail price', 'EUR 79'),
         ('Limit', 'No waterproof rating, certification or own cost established')])], folder='研究/虚构竞品快照'),
]

EMAILS = [
    ('customer-colorbox', 'customer_change', 'buyer@nordlicht.example.invalid', 'Customer requests color box',
     'Please change from standard polybag to CB-02-DEMO printed color box for BP-DE-3000-DEMO, 3000 pcs. Keep the logo 60 x 25 mm. Please review cost, MOQ, carton quantity and lead time. This is a request, not factory feasibility confirmation.'),
    ('factory-colorbox', 'supplier_confirmation', 'quote@factory-a.example.invalid', 'FA-NL-V2 color box conditions',
     'SIMULATED supplier confirmation. Manufacturing CNY 44/pc, replacement packaging CNY 5/pc, domestic handling CNY 4/pc. MOQ 1000 pcs. Estimate 31 days after sample approval and deposit. Box 47 x 32 x 17 cm, 2 boxes/carton, outer carton 50 x 35 x 38 cm; fit and strength trial pending. Export customs and inspection excluded and not yet priced.'),
    ('customer-spec-v2', 'customer_approval', 'buyer@nordlicht.example.invalid', 'Scope: TP-NL-V2 specification',
     'SIMULATED. We accept TP-NL-V2 specifications: embroidered logo 60 x 25 mm moved down 10 mm, darker thread, CB-02-DEMO, 2 boxes/carton. This approves the specification scope only. No physical sample, quotation version, payment or production release is approved by this email.'),
    ('customer-sample-v2', 'customer_approval', 'buyer@nordlicht.example.invalid', 'Scope: SMP-NL-002 only',
     'SIMULATED physical sample event. We reviewed sample SMP-NL-002 against TP-NL-V2 and CB-02-DEMO and approve this sample without further changes. This does not verify payment, contract acceptance or internal production release.'),
    ('negotiation', 'customer_change', 'buyer@nordlicht.example.invalid', 'Could you reduce the price by 5 percent?',
     'Please review whether QT-NL-V2 could be reduced by 5 percent for 3000 pcs. We have not accepted a new price or changed specifications. Please state any revised margin and exclusions for internal review.'),
    ('pi-before-sample', 'customer_request', 'buyer@nordlicht.example.invalid', 'Please prepare a PI before final sample',
     'Please prepare a draft PI based on QT-NL-V1, 3000 pcs at USD 8.69, FOB Ningbo Incoterms 2020, 30 percent deposit and 70 percent before shipment. The final physical sample is still pending. This is a PI preparation request, not a payment receipt or production authorization.'),
    ('finance-assumptions', 'internal_note', 'finance@navowork.example.invalid', 'Demo costing assumptions NL-FIN-V1',
     'SIMULATED internal assumptions: exchange rate 7.20 CNY per USD, target gross margin 20%, quantity 3000. Round unit USD price upward to cents before multiplying quantity. CNY 4 domestic handling allocation does not include export customs or inspection; these costs are unknown. Quotes remain conditional. No internal price approval is created.'),
    ('oem-inquiry', 'customer_request', 'buyer@oem.example.invalid', 'OEM Tech Pack review only',
     'We supply the attached TP-NL-V1 complete priceable baseline for 3000 commuter backpacks. Review specification, BOM and quote scope. Do not redesign or require competitor research or concept generation. Manufacturing certification and sampling are still pending.'),
    ('new-design-inquiry', 'customer_request', 'buyer@studio.example.invalid', 'Co-design commuter bag concept',
     'We are a fictional studio exploring 1500 commuter bags for Germany. Budget is a target, USD 12 per bag, not an approved supplier price. Compare two archived product snapshots and propose a direction. Size, fabric consumption, BOM and factory prices are unknown. No sample is approved.'),
    ('moq-inquiry', 'customer_request', 'buyer@casa-verde.example.invalid', '300-piece trial tote order',
     'We request 300 natural cotton totes, 38 x 42 cm, single color logo, delivery to Mexico City. Please confirm feasibility. Do not silently increase quantity. This is a new fictional trial case, distinct from the old wiki 600-piece update.'),
    ('unknown-inquiry', 'customer_request', 'buyer@harbor.example.invalid', 'Need some bags urgently',
     'We need some bags with a logo for an event in London as soon as possible. Quantity, product type, size, material, deadline and budget are not provided. Please ask clarification questions; do not invent costs or dates.'),
]

SCENARIOS = [
    dict(id='inq_assets_odm', title='资产 Demo · Nordlicht ODM 报价与彩盒变更', path='ODM',
         customer=CUSTOMER, initial=['02_customer_RFQ', '04_requirements', '05_techpack_V1', '08_supplier_terms', 'supplier_A_V1', 'supplier_B_V1', 'bom_V1', '09_costing_editable', 'finance-assumptions', 'product-reference', 'logo-demo-png'],
         events=[('colorbox', ['customer-colorbox', 'factory-colorbox', 'supplier_A_V2', '06_packing_V2', 'bom_V2']), ('sample_feedback', ['12_sample_feedback']), ('spec_approval', ['customer-spec-v2', '05_techpack_V2']), ('sample_approval', ['customer-sample-v2'])],
         prompt='按现款 ODM 处理：先核对规格、BOM 与费用范围，汇率 7.20、毛利率 20%、数量 3000。生成条件报价草稿和打样准备资料，明确报关/检验费用未知。'),
    dict(id='inq_assets_oem', title='资产 Demo · OEM 来资料直接核价', path='OEM', customer=CUSTOMER,
         initial=['oem-inquiry', '05_techpack_V1', 'bom_V1', 'supplier_A_V1', 'finance-assumptions'], events=[],
         prompt='校验完整 OEM 核价资料，检查未知项并生成条件报价；无需竞品研究或重新设计。'),
    dict(id='inq_assets_design', title='资产 Demo · 新款竞品与设计探索', path='co-design', customer='Studio Buyer (SIMULATED)',
         initial=['new-design-inquiry', 'competitor_a', 'competitor_b', 'product-reference', 'logo-demo-png'], events=[],
         prompt='先基于两份模拟竞品快照比较设计方向，保留来源、日期和适用范围；成本未知，不做正式报价。需要概念图时调用当前实际图像引擎。'),
    dict(id='inq_assets_moq', title='资产 Demo · Casa Verde 数量低于 MOQ', path='MOQ exception', customer='Casa Verde (SIMULATED)',
         initial=['moq-inquiry', 'supplier_M_MOQ'], events=[], prompt='客户只要 300 件，供应商 MOQ 500。列出差异与澄清问题，不改客户数量，不把工厂 MOQ 当客户接受数量。'),
    dict(id='inq_assets_unknown', title='资产 Demo · Harbor 缺项澄清', path='clarification', customer='Harbor Promotions (SIMULATED)',
         initial=['unknown-inquiry'], events=[], prompt='列出产品、数量、规格、预算、交期的澄清问题，给英文回复草稿；没有核价来源，不报价。'),
    dict(id='inq_assets_order', title='资产 Demo · PO 独立进入与差异核对', path='W2 PO', customer=CUSTOMER,
         initial=['14a_PO_matching', '10_quotation_V2', '06_packing_V2'],
         events=[('conflicting_po', ['po_conflict']), ('negotiation', ['negotiation']), ('sample_approval', ['customer-sample-v2'])],
         prompt='直接从客户 PO 进入 W2，对照候选报价及技术资料检查差异，生成 PI 草稿。无客户接受证据时标为待协商依据，缺少样品不阻断 PI 草稿，禁止量产放行。'),
    dict(id='inq_assets_pi_first', title='资产 Demo · 样品前先准备 PI', path='W2 PI first', customer=CUSTOMER,
         initial=['pi-before-sample', '10_quotation_V1', '05_techpack_V1'], events=[],
         prompt='客户要求样品批准前先准备 PI 草稿；按请求记录条件与未完成项，不宣称样品批准、已收定金、已签约或量产。'),
]


def bom_rows(version=1, missing=False):
    rows = deepcopy(BOM)
    if version == 2:
        rows[9][1:3] = ['Color box CB-02-DEMO', '47 x 32 x 17 cm; 2/carton']
        rows[9][6] = 5
        rows[9][8] = 'FA-NL-V2'
    if missing:
        rows[6][6] = None
    return rows

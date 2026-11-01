export type WikiDocument = {
  sourceVersionId?: string;
  version?: number;
  id: string;
  title: string;
  folder: string;
  summary: string;
  updated: string;
  starred: boolean;
  content: string;
};

export const wikiFolders = ['业务流程', '产品资料', '客户沟通', '团队协作'];

export const wikiDocuments: WikiDocument[] = [
  {
    "id": "01-demo-route",
    "title": "业务流程｜从询盘到交付的工作顺序",
    "folder": "业务流程",
    "summary": "每次只处理当前指令涉及的环节。先读取当前询盘和已收到的材料，列明缺项，再生成对应成果。",
    "updated": "2026-11-01",
    "starred": false,
    "content": "# 从询盘到交付\n每次只处理当前指令涉及的环节。先读取当前询盘和已收到的材料，列明缺项，再生成对应成果。\n\n1. 询盘：提取产品、数量、规格、目标价、目的地和交期；信息不足时准备澄清问题。\n2. 产品：确认面料、尺寸、工艺、LOGO、结构与包装，制作规格书和工厂询价清单。\n3. 报价：收到供应商原件后比较 MOQ、成本、周期；按明确汇率与毛利率核价。\n4. 打样：制作打样要求，记录样品编号、反馈和修改，单独取得最终样确认。\n5. 订单：核对 PO 与已确认报价，准备 PI 和技术附件，保留所有差异。\n6. 生产：分别确认规格、报价、样品、双方订单、付款保障和供应商排期，再检查放行条件。\n7. 验货与交付：依据当前规格整理检查项、异常和整改要求，交付信息以实际证据为准。\n\n资产库中的文件按本轮指令选用。尚未收到的后续确认不能用于消除当前缺项；已生成草稿不能视为批准。\n"
  },
  {
    "id": "02-bag-spec",
    "title": "包袋产品｜规格与工艺确认清单",
    "folder": "产品资料",
    "summary": "款号、产品类型、数量、主面料成分与克重、里料、尺寸及公差、颜色、LOGO工艺与位置、拉链扣具、内袋结构、包装与验货标准。",
    "updated": "2026-11-01",
    "starred": true,
    "content": "# 包袋规格确认\n## 必须明确的字段\n款号、产品类型、数量、主面料成分与克重、里料、尺寸及公差、颜色、LOGO工艺与位置、拉链扣具、内袋结构、包装与验货标准。\n\n背包需补充电脑隔层适配、肩带承重、侧袋结构和底部加固。帆布袋需补充面料盎司、提手长度、缝线和印刷色数。\n\n## 规格书约定\n每个字段保留来源与版本。图纸提供形状与尺寸参考，照片不能证明材质成分、精确尺寸或认证。\n包装单独记录内包装、装箱数量、外箱尺寸、唛头和图稿版本。未经客户明确同意，不采用后续彩盒方案替换当前包装。\n\n客户规格确认与实物样批准分别记录，客户说“价格可以”不等于已接受尺寸、LOGO或包装。\n"
  },
  {
    "id": "03-cost",
    "title": "核价规则｜汇率、毛利率与费用分摊",
    "folder": "业务流程",
    "summary": "单件总成本 CNY = 工厂基础价 + 单件包装 + 国内费用分摊。",
    "updated": "2026-11-01",
    "starred": true,
    "content": "# 成本与报价\n单件总成本 CNY = 工厂基础价 + 单件包装 + 国内费用分摊。\n报价 USD/件 = 总成本 ÷ 汇率(CNY/USD) ÷ (1 - 毛利率)。单价向上舍入至美分，再乘数量得到商品小计。\n毛利率20%不等于成本加成20%。MOQ按当前客户确认数量检查，数量不足先询问供应商或客户。\n\n## 成本依据\n基础价、包装、MOQ、有效期和周期来自供应商当前报价。国内费用由内部费用记录支持；汇率和目标毛利由操作者明确提供。\n供应商报价不自动确认汇率与毛利率。缺少成本字段保留待确认，不能用零补齐。\n\n## 费用边界\nFOB商品小计不包含未约定的海运、保险、目的国税费。打样与快递单列，不合并进大货金额。\n报价单必须列币种、数量、单价、小计、付款、贸易术语、指定地点、有效期、生产起算条件。\n"
  },
  {
    "id": "04-trade",
    "title": "报价条款｜FOB与交期表达",
    "folder": "客户沟通",
    "summary": "使用完整表达：FOB Ningbo, Incoterms 2020。指定装运港改变时重新复核国内费用和责任范围。",
    "updated": "2026-11-01",
    "starred": false,
    "content": "# FOB 与交期\n使用完整表达：FOB Ningbo, Incoterms 2020。指定装运港改变时重新复核国内费用和责任范围。\n生产周期、出库安排、海运时间和到港日期分别记录。客户期望45天到汉堡是目标，未经船期核实不能写成承诺。\n\n英文：Estimated production lead time starts after final sample/artwork approval and payment conditions are met. Arrival is subject to a separately confirmed shipping schedule.\n西语：El plazo estimado de producción comienza después de aprobar la muestra y el arte final y de cumplir las condiciones de pago. La fecha de llegada requiere confirmar el transporte.\n\n付款比例、报价有效期、样品费用及补充条款以双方当前约定为准。草稿发送前复核所有金额、单位、版本与缺项。\n"
  },
  {
    "id": "05-change",
    "title": "变更处理｜影响分析与版本维护",
    "folder": "业务流程",
    "summary": "先保留客户变更原件，核对当前生效规格与报价，再列直接和下游影响。",
    "updated": "2026-11-01",
    "starred": false,
    "content": "# 变更处理\n先保留客户变更原件，核对当前生效规格与报价，再列直接和下游影响。\n包装变化可能影响规格书、工厂询价、成本、报价、样品、PO和生产资料。数量变化还需重查MOQ与费用分摊。\n\n1. 记录变化字段、旧值、新要求与来源；未知的新成本和周期保留待确认。\n2. 用工厂新报价重新核算，生成候选草稿版本，保留旧版。\n3. 已存在的受影响成果关联实际修订；尚未开展的后续环节注明下一次生成时使用新版。\n4. 所有影响处理完毕后再激活新基准；样品、客户规格和内部报价批准分别重新核对适用版本。\n\n客户提出变更不等于接受额外费用、交期延长或授权生产。\n"
  },
  {
    "id": "06-sample",
    "title": "样品反馈｜修改、条件接受与最终确认",
    "folder": "产品资料",
    "summary": "每次反馈绑定样品编号、规格版本、寄样批次和客户来件。",
    "updated": "2026-11-01",
    "starred": false,
    "content": "# 样品反馈与确认\n每次反馈绑定样品编号、规格版本、寄样批次和客户来件。\n反馈分类：完整接受、部分接受、条件接受、拒绝。‘Looks good, but…’、需改LOGO或包装、待复样等都保留未关闭条件。\n\n## 修改清单\n逐项记录位置、现象、客户要求、责任人、拟修改内容和复验依据。尺寸测量、工厂检查和客户最终批准分别归档。\n图片不能替代精确尺寸测量，内部测量通过不能替代客户接受。最终样批准必须覆盖指定样品与当前规格。\n\n## 检查范围\n尺寸公差、面料颜色、缝线、拉链、肩带、电脑隔层、印绣花、包装适配与唛头。AQL、功能测试和市场认证要求按双方约定和实际报告记录。\n最终样已接受仍不意味着合同已签、订金已到账或量产已放行。\n"
  },
  {
    "id": "07-order",
    "title": "订单与生产｜PO核对、PI与放行条件",
    "folder": "业务流程",
    "summary": "对照明确版本的报价，检查买卖方、SKU、单位、数量、单价、行金额、总额、币种、贸易术语、港口、付款、交期和规格引用。",
    "updated": "2026-11-01",
    "starred": true,
    "content": "# PO、PI 与生产\n## PO核对\n对照明确版本的报价，检查买卖方、SKU、单位、数量、单价、行金额、总额、币种、贸易术语、港口、付款、交期和规格引用。\n保留买方原文及差异定位。FOB Shanghai与FOB Ningbo不是同一条款，不能静默归一。内部批准报价不等于客户已接受。\n\n## PI准备\n可在样品未批准时整理PI草稿，未知字段列为待确认；冲突保留双方值。草稿必须保留所用报价、PO、规格版本和待签署状态。\n\n## 六项放行条件\n客户最终规格确认、当前样品批准、内部商业报价批准、买卖双方确认同一订单、付款保障核验、供应商排期确认。\n同时不得有未关闭的重大变更。每项分别核对来源与适用版本，上传付款凭据不自动记作到账。\n\n## 核心业务档案\n核心业务资料包含需求、Tech Pack V3、报价V3、样品S03、PO R2、PI/SC与技术附件。它们属于同一档案快照，仅在用户选择对应资料时使用。\n样品S03的接受不覆盖其他样品；内部价格批准不覆盖生产放行。PI/SC待签署、订金证据缺失或内部放行未记录时，生产保持阻断。\n"
  },
  {
    "id": "08-assets",
    "title": "资料规范｜知识复用与原件引用",
    "folder": "团队协作",
    "summary": "知识库保存通用规则；资产库存放原件。具体客户要求、成本与确认以本项目收到并引用的证据为准。",
    "updated": "2026-11-01",
    "starred": false,
    "content": "# 资料与版本\n知识库保存通用规则；资产库存放原件。具体客户要求、成本与确认以本项目收到并引用的证据为准。\n\n文件按询盘、规格、报价、样品、订单、生产与验货分类。引用时固定文件版本和来源，后续上传不改变已完成工作的依据。\n历史订单可供参考，不能自动继承其价格、交期、付款或批准。个人资产转入公司空间需由所有者明确操作。\n\n可以将本次成果归档到资产库，将可复用经验保存为知识草稿。知识草稿审核发布后，才成为团队正式规则。\n"
  }
];

export type AssetKind = 'image' | 'video' | 'spreadsheet' | 'document' | 'other';
export type AssetSpace = 'company' | 'personal';
export type LibraryAsset = {
  downloadPath?: string;
  version?: number;
  id: string;
  name: string;
  kind: AssetKind;
  space: AssetSpace;
  folder: string;
  size: string;
  updated: string;
  starred: boolean;
  art:
    'tote' | 'backpack' | 'brand' | 'video' | 'sheet' | 'catalog' | 'slides' | 'archive' | 'notes';
  url?: string;
  mime?: string;
  file?: File;
  content?: string;
  unavailable?: string;
  inquiry?: {
    id: string;
    title: string;
    documentId: string;
    folderId: string;
    folderTitle: string;
  };
};
export const assetKinds: { id: AssetKind | 'all'; label: string }[] = [
  { id: 'all', label: '全部' },
  { id: 'image', label: '图片' },
  { id: 'video', label: '视频' },
  { id: 'spreadsheet', label: '表格' },
  { id: 'document', label: '文档' },
  { id: 'other', label: '其他' },
];
// Embedded text originals remain readable and downloadable in local preview mode.
const localDocuments = [
  {
    "id": "local-inquiry",
    "name": "de-inquiry.eml",
    "kind": "document",
    "space": "company",
    "folder": "客户往来",
    "size": "1.0 KB",
    "updated": "2026-11-01",
    "starred": true,
    "art": "notes",
    "mime": "text/plain",
    "content": "From: Michael Weber <procurement@nordlicht.example>\nTo: Alex <alex@navowork.example>\nSubject: BAG-2026-DE-001 / 3,000 custom backpacks\nDate: Sat, 31 Oct 2026 09:00:00 +0800\nMessage-ID: <sources-de-inquiry.eml@demo.example>\nContent-Type: text/plain; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\nMIME-Version: 1.0\n\nDear Alex,\nWe are Nordlicht Outdoor GmbH, Germany. Please quote 3,000 custom backpacks,\nstyle BP-DE-3000, for our outdoor retail stores. Target price: USD 9.50 per piece.\nPlease use black 600D polyester, 210D lining, a padded 15.6-inch laptop sleeve,\n45 x 30 x 15 cm dimensions, and our white embroidered logo, 50 x 20 mm.\nOne plain kraft box per bag, 20 bags per export carton. FOB Ningbo, Incoterms 2020.\nWe would like them in Hamburg within 45 days if possible; please assess feasibility.\nPlease quote sample cost, production lead time and 30% deposit / 70% before shipment.\nProduct drawing and requested specifications are attached. No sample is approved yet.\nBest regards, Michael Weber / procurement@nordlicht.example\n"
  },
  {
    "id": "local-offer_a1",
    "name": "quote-a1.txt",
    "kind": "document",
    "space": "company",
    "folder": "供应商与样品",
    "size": "0.6 KB",
    "updated": "2026-11-01",
    "starred": true,
    "art": "notes",
    "mime": "text/plain",
    "content": "SUPPLIER QUOTATION A1\nSupplier: 工厂 A｜宁波远行箱包\nProduct: backpack BP-DE-3000\nBase factory cost: CNY 44 per piece. Packaging: CNY 2 per piece, charged separately.\nMOQ: 1000 pieces. Estimated production lead time: 28 days after final sample/artwork and payment conditions.\nSupplier currency: CNY. Valid until: 2026-11-14. No international freight or import tax included.\nPacking: plain kraft box.\nThe workbook Supplier_Quotes.xlsx / Factory A V1 contains the same supplier quotation.\nDomestic charges CNY 4/piece are an internal allocation, not part of the supplier's factory quote.\nProduction starts only after the agreed prerequisites are confirmed.\n"
  },
  {
    "id": "local-offer_b1",
    "name": "quote-b1.txt",
    "kind": "document",
    "space": "company",
    "folder": "供应商与样品",
    "size": "0.6 KB",
    "updated": "2026-11-01",
    "starred": false,
    "art": "notes",
    "mime": "text/plain",
    "content": "SUPPLIER QUOTATION B1\nSupplier: 工厂 B｜绍兴行旅箱包\nProduct: backpack BP-DE-3000\nBase factory cost: CNY 46 per piece. Packaging: CNY 2 per piece, charged separately.\nMOQ: 1000 pieces. Estimated production lead time: 23 days after final sample/artwork and payment conditions.\nSupplier currency: CNY. Valid until: 2026-11-14. No international freight or import tax included.\nPacking: plain kraft box.\nThe workbook Supplier_Quotes.xlsx / Factory B V1 contains the same supplier quotation.\nDomestic charges CNY 4/piece are an internal allocation, not part of the supplier's factory quote.\nProduction starts only after the agreed prerequisites are confirmed.\n"
  },
  {
    "id": "local-change",
    "name": "customer-packaging-change.eml",
    "kind": "document",
    "space": "company",
    "folder": "客户往来",
    "size": "0.8 KB",
    "updated": "2026-11-01",
    "starred": false,
    "art": "notes",
    "mime": "text/plain",
    "content": "From: Michael Weber <procurement@nordlicht.example>\nTo: Alex <alex@navowork.example>\nSubject: Please revise packaging / no production authorization\nDate: Sat, 31 Oct 2026 09:00:00 +0800\nMessage-ID: <sources-customer-packaging-change.eml@demo.example>\nContent-Type: text/plain; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\nMIME-Version: 1.0\n\nDear Alex,\nFor BAG-2026-DE-001, please change the packaging from a plain kraft box to a custom\nCMYK printed color box, 48 x 33 x 18 cm. Please keep the quantity at 3,000 backpacks,\nthe material, dimensions, logo and other product requirements unchanged.\nPlease provide the additional cost and lead-time impact before we approve the revision.\nThis request is not authorization to start production.\nMichael Weber / Nordlicht Outdoor GmbH\n"
  },
  {
    "id": "local-sample_check",
    "name": "sample-inspection.txt",
    "kind": "document",
    "space": "company",
    "folder": "供应商与样品",
    "size": "0.6 KB",
    "updated": "2026-11-01",
    "starred": false,
    "art": "notes",
    "mime": "text/plain",
    "content": "SAMPLE INSPECTION / SMP-DE-CB02\nSpecification: BP-DE-3000 final color-box specification; seal DEMO-SEAL-02.\nDimensions 45 x 30 x 15 cm, tolerance +/-1 cm: within specified tolerance.\nBlack 600D shell / 210D lining; 15.6-inch sleeve; 2 mesh pockets: matches supplied specification.\nWhite embroidered logo 50 x 20 mm; CB-02 color box 48 x 33 x 18 cm: within specified tolerance.\nWorkmanship, zipper travel, straps and packaging fit: inspection completed.\nInspection standard: General II, major AQL2.5/minor4.0/critical0 as agreed, not a certification claim.\nCustomer approval must be recorded separately using customer-final-approval.eml.\n"
  },
  {
    "id": "local-customer_ok",
    "name": "customer-final-approval.eml",
    "kind": "document",
    "space": "company",
    "folder": "客户往来",
    "size": "1.0 KB",
    "updated": "2026-11-01",
    "starred": false,
    "art": "notes",
    "mime": "text/plain",
    "content": "From: Michael Weber <procurement@nordlicht.example>\nTo: Alex <alex@navowork.example>\nSubject: Final spec, sample and buyer PO confirmation\nDate: Sat, 31 Oct 2026 09:00:00 +0800\nMessage-ID: <sources-customer-final-approval.eml@demo.example>\nContent-Type: text/plain; charset=\"utf-8\"\nContent-Transfer-Encoding: 8bit\nMIME-Version: 1.0\n\nI approve the final BP-DE-3000 specification with the CB-02 color box, 3,000 pieces, black 600D polyester and 210D lining, 45 x 30 x 15 cm, white embroidered logo 50 x 20 mm.\nI approve sample SMP-DE-CB02 with seal DEMO-SEAL-02, the product and packaging artwork and the agreed inspection standard.\nI accept quotation QT-DE-001-V2: USD 9.21 per piece, USD 27,630 goods total, FOB Ningbo Incoterms 2020, 30% deposit and 70% before shipment. Validity 2026-11-14.\nPlease retain our PO-DE-001-V2 as the buyer-confirmed order. This email confirms specification, sample and buyer order; it does not prove seller acceptance, bank receipt or production start.\n"
  }
];
export const libraryAssets: LibraryAsset[] = localDocuments.map(({ content, ...document }) => ({
  ...document,
  kind: 'document',
  space: 'company',
  art: 'notes',
  url: `data:text/plain;charset=utf-8,${encodeURIComponent(content)}`,
}));

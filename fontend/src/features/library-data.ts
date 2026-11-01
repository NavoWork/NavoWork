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
    id: 'getting-started',
    title: '团队知识库使用指南',
    folder: '团队协作',
    summary: '从这里开始，找到团队常用的流程、资料与经验。',
    updated: '2026-10-31',
    starred: true,
    content:
      '# 团队知识库使用指南\n\n这里收录团队工作中反复用到的知识。每篇文档都是一份 Markdown 文件，按主题整理，随时查阅。\n\n## 目录导航\n\n- **业务流程**：询盘处理、报价与交付的工作规范。\n- **产品资料**：产品规格、材质及常见工艺。\n- **客户沟通**：邮件模板、需求确认与沟通经验。\n- **团队协作**：新人入门、资料整理与协作约定。\n\n## 如何使用\n\n1. 从左侧目录选择主题，也可以搜索文档名称或正文。\n2. 点击文档阅读全文，在“原文”中查看 Markdown。\n3. 将经常使用的文档加入收藏，下次快速找到。\n\n## 文档约定\n\n使用清晰的标题，一篇文档解决一个具体问题。操作步骤用列表，规格对比用表格。\n\n> 图片、视频、表格等原始文件统一放在资产库；知识库记录说明和使用方法。',
  },
  {
    id: 'inquiry',
    title: '从询盘到报价的标准流程',
    folder: '业务流程',
    summary: '需求确认、供应商询价与报价复核的完整步骤。',
    updated: '2026-10-30',
    starred: true,
    content:
      '# 从询盘到报价的标准流程\n\n收到客户询盘后，先补齐关键条件，再开始询价和报价。\n\n## 需求确认\n\n- 产品名称、规格、材质和用途。\n- 数量、包装方式及是否需要定制。\n- 目的地、贸易条款与期望到货时间。\n\n## 供应商询价\n\n向供应商发送同一份规格说明，确认单价、起订量、打样周期和生产周期。价格必须标明币种与有效期。\n\n## 报价复核\n\n| 检查项 | 确认内容 |\n| --- | --- |\n| 产品 | 规格与客户需求一致 |\n| 价格 | 单价、费用、币种完整 |\n| 交付 | 区分生产、出库和运输时间 |\n| 条款 | 付款、有效期与贸易条款明确 |\n\n## 发送与跟进\n\n先回答客户最关心的问题，再给出报价和需要确认的事项。保存本次报价，便于后续对照。',
  },
  {
    id: 'delivery',
    title: '交付与承诺规则',
    folder: '业务流程',
    summary: '明确交期、运输与费用，避免未经确认的承诺。',
    updated: '2026-10-29',
    starred: false,
    content:
      '# 交付与承诺规则\n\n## 时间口径\n\n**出库时间不等于到货时间。** 生产周期、出库安排和运输时效需要分别说明。\n\n## 发送前确认\n\n- 库存信息是否仍然有效。\n- 生产周期从哪个条件满足后开始计算。\n- 运输方案、运费及税费是否已确认。\n- 客户要求的认证是否有对应文件。\n\n## 待确认事项\n\n无法确认的信息，列入待确认清单并明确下一步。\n\n> 没有核实的库存、认证和交期，不写成确定承诺。',
  },
  {
    id: 'canvas',
    title: '帆布袋材质与工艺说明',
    folder: '产品资料',
    summary: '常见克重、尺寸、印刷方式与打样注意事项。',
    updated: '2026-10-28',
    starred: true,
    content:
      '# 帆布袋材质与工艺说明\n\n## 常见材质\n\n| 材质 | 特点 | 常见用途 |\n| --- | --- | --- |\n| 纯棉帆布 | 手感柔软，纹理自然 | 品牌周边、零售包装 |\n| 涤棉帆布 | 耐磨，易于打理 | 日常通勤、活动物料 |\n| 再生棉 | 颜色与纹理存在批次差异 | 环保主题项目 |\n\n## 印刷方式\n\n- **丝网印刷**：适合色块清晰、颜色较少的图案。\n- **热转印**：适合细节丰富、颜色较多的图案。\n- **刺绣**：适合简洁标识，需要确认针数与位置。\n\n## 打样前确认\n\n1. 成品尺寸、提手长度和面料克重。\n2. 图案尺寸、位置与颜色参考。\n3. 包装、洗标及其他配件。\n\n> 尺寸与颜色以确认样为准。',
  },
  {
    id: 'backpack',
    title: '定制背包规格清单',
    folder: '产品资料',
    summary: '面料、容量、配件与品牌定制的确认清单。',
    updated: '2026-10-27',
    starred: false,
    content:
      '# 定制背包规格清单\n\n## 基础规格\n\n- 容量、长宽高及目标重量。\n- 主面料、里料与防水要求。\n- 电脑隔层、侧袋和内部收纳。\n\n## 配件确认\n\n确认拉链、扣具、肩带和提手的材质与颜色，有指定品牌时提前说明。\n\n## 品牌定制\n\n提供标识矢量文件和色值。明确刺绣、印刷或织标的位置与尺寸。\n\n## 样品验收\n\n根据确认清单逐项核对外观、尺寸、功能及包装，记录修改意见后再进入生产。',
  },
  {
    id: 'tone',
    title: '客户沟通语气指南',
    folder: '客户沟通',
    summary: '清楚、简洁地回应需求，让下一步行动更明确。',
    updated: '2026-10-26',
    starred: false,
    content:
      '# 客户沟通语气指南\n\n## 基本原则\n\n回复要**清楚、简洁、有下一步**。先回应客户需求，再列待确认事项。\n\n## 推荐结构\n\n1. 一句话回应本次需求。\n2. 给出关键结果或可选方案。\n3. 说明仍需确认的条件。\n4. 明确需要客户提供的信息。\n\n## 表达示例\n\n> We can prepare a quotation for 500 canvas bags. Could you share your preferred size, print artwork, and delivery address?\n\n## 避免的表达\n\n不要用模糊的“尽快”代替时间安排；不要将预计时间写成保证；不要重复客户已经提供的信息。',
  },
  {
    id: 'followup',
    title: '报价跟进邮件模板',
    folder: '客户沟通',
    summary: '首次跟进、方案调整与样品确认的常用写法。',
    updated: '2026-10-25',
    starred: false,
    content:
      '# 报价跟进邮件模板\n\n## 首次跟进\n\nHi Alex,\n\nHave you had a chance to review the quotation? I would be happy to clarify the specifications or discuss other options.\n\n## 方案调整\n\nBased on your target budget, we can review the material, packaging, and quantity together. Please let us know which requirements are essential.\n\n## 样品确认\n\nBefore we arrange the sample, please confirm the artwork, dimensions, and shipping address. We will share the sample schedule after these details are confirmed.\n\n> 使用前替换客户称呼与项目细节，不直接发送未核实的条件。',
  },
  {
    id: 'naming',
    title: '文件命名与归档约定',
    folder: '团队协作',
    summary: '统一文件名称和目录，让团队更容易找到资料。',
    updated: '2026-10-24',
    starred: false,
    content:
      '# 文件命名与归档约定\n\n## 文件命名\n\n使用 `项目-主题-日期` 的格式，例如 `秋季新品-产品目录-20261031.pdf`。\n\n## 选择归属\n\n- 团队共用的品牌素材、产品文件放在**公司资产库**。\n- 个人收集的参考、草稿与工作笔记放在**个人资产库**。\n- 可以复用的流程和经验写成 Markdown，整理到知识库。\n\n## 整理习惯\n\n每次更新时使用清楚的文件名，避免“最终版2”“最新最终版”等难以识别的命名。',
  },
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
export const libraryAssets: LibraryAsset[] = [
  {
    id: 'a1',
    name: '帆布袋 · 自然色.png',
    kind: 'image',
    space: 'company',
    folder: '产品素材',
    size: '2.4 MB',
    updated: '2026-10-31',
    starred: true,
    art: 'tote',
  },
  {
    id: 'a2',
    name: '轻量通勤背包.jpg',
    kind: 'image',
    space: 'company',
    folder: '产品素材',
    size: '3.8 MB',
    updated: '2026-10-30',
    starred: false,
    art: 'backpack',
  },
  {
    id: 'a3',
    name: '帆布袋工艺展示.mp4',
    kind: 'video',
    space: 'company',
    folder: '产品素材',
    size: '24.6 MB',
    updated: '2026-10-29',
    starred: false,
    art: 'video',
  },
  {
    id: 'a4',
    name: '2026 产品报价表.xlsx',
    kind: 'spreadsheet',
    space: 'company',
    folder: '销售资料',
    size: '186 KB',
    updated: '2026-10-28',
    starred: true,
    art: 'sheet',
  },
  {
    id: 'a5',
    name: '秋冬产品目录.pdf',
    kind: 'document',
    space: 'company',
    folder: '销售资料',
    size: '8.2 MB',
    updated: '2026-10-27',
    starred: false,
    art: 'catalog',
  },
  {
    id: 'a6',
    name: 'Navowork 品牌标识.svg',
    kind: 'image',
    space: 'company',
    folder: '品牌文件',
    size: '32 KB',
    updated: '2026-10-26',
    starred: true,
    art: 'brand',
  },
  {
    id: 'a7',
    name: '公司介绍.pptx',
    kind: 'document',
    space: 'company',
    folder: '品牌文件',
    size: '5.6 MB',
    updated: '2026-10-25',
    starred: false,
    art: 'slides',
  },
  {
    id: 'a8',
    name: '包装印刷源文件.zip',
    kind: 'other',
    space: 'company',
    folder: '品牌文件',
    size: '16.4 MB',
    updated: '2026-10-24',
    starred: false,
    art: 'archive',
  },
  {
    id: 'p1',
    name: '客户报价对比.xlsx',
    kind: 'spreadsheet',
    space: 'personal',
    folder: '工作文件',
    size: '96 KB',
    updated: '2026-10-31',
    starred: true,
    art: 'sheet',
  },
  {
    id: 'p2',
    name: '帆布袋配色参考.png',
    kind: 'image',
    space: 'personal',
    folder: '灵感参考',
    size: '1.8 MB',
    updated: '2026-10-30',
    starred: false,
    art: 'tote',
  },
  {
    id: 'p3',
    name: '客户拜访笔记.docx',
    kind: 'document',
    space: 'personal',
    folder: '工作文件',
    size: '48 KB',
    updated: '2026-10-29',
    starred: false,
    art: 'notes',
  },
  {
    id: 'p4',
    name: '产品拍摄参考.mov',
    kind: 'video',
    space: 'personal',
    folder: '灵感参考',
    size: '12.8 MB',
    updated: '2026-10-28',
    starred: false,
    art: 'video',
  },
];

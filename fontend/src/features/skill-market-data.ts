import {
  BookOpen, Calculator, FileSearch, FileSpreadsheet, MessagesSquare,
  PackageSearch, ShieldCheck, ShoppingBag, Workflow, type LucideIcon,
} from 'lucide-react';

export type MarketTab = 'skills' | 'plugins' | 'suites';
export interface MarketItem {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  category: string;
  tags: string[];
  includes: string[];
}
export const marketTabs: { id: MarketTab; label: string }[] = [
  { id: 'skills', label: '业务技能' },
  { id: 'plugins', label: '工作工具' },
  { id: 'suites', label: '业务流程' },
];
export const marketItems: Record<MarketTab, MarketItem[]> = {
  skills: [
    { id: 'requirements', name: '询盘需求整理', icon: FileSearch, category: '客户询盘',
      description: '从当前客户原文提取产品、数量、规格与交期，保存需求并整理澄清问题。',
      tags: ['需求提取', '来源引用'], includes: ['读取当前询盘与原件', '更新结构化需求', '保留未知字段与待确认项'] },
    { id: 'specification', name: '产品规格书', icon: PackageSearch, category: '产品确认',
      description: '整理面料、尺寸、LOGO、结构和包装，制作可继续编辑的规格草稿。',
      tags: ['Tech Pack', '规格版本'], includes: ['检索产品知识', '核对规格与包装', '保存规格和询价草稿'] },
    { id: 'supplier-costing', name: '供应商比较与核价', icon: Calculator, category: '成本与报价',
      description: '读取供应商原件，比较MOQ、周期与费用，按明确汇率和毛利率计算成本。',
      tags: ['供应商报价', 'MOQ', '成本核算'], includes: ['登记有来源的供应商报价', '比较成本与周期', '按十进制规则计算并保留缺项'] },
    { id: 'quotation', name: '客户报价与回复', icon: MessagesSquare, category: '成本与报价',
      description: '依据当前核价结果整理报价条款，并起草一致的客户回复。',
      tags: ['报价草稿', '多语言回复'], includes: ['生成报价草稿', '区分商品小计与最终费用', '更新客户回复与待确认条款'] },
    { id: 'sample-feedback', name: '样品反馈与修改', icon: PackageSearch, category: '打样确认',
      description: '按样品编号和规格版本整理反馈，区分完整接受、部分接受、条件接受和拒绝。',
      tags: ['样品反馈', '修改清单'], includes: ['读取客户来件与测量记录', '整理未关闭条件', '保存样品反馈与修改草稿'] },
    { id: 'po-check', name: 'PO逐项核对', icon: FileSearch, category: '订单合同',
      description: '核对采购订单与当前报价的数量、金额、港口、付款和规格引用，保留双方差异。',
      tags: ['PO核对', '商业条款'], includes: ['读取PO和明确报价版本', '逐字段核对并保留原文', '输出差异与待确认项'] },
    { id: 'pi-prepare', name: 'PI草稿准备', icon: FileSpreadsheet, category: '订单合同',
      description: '从PO、报价和规格整理形式发票，将签署、样品与付款前提单独列明。',
      tags: ['PI', '订单草稿'], includes: ['核对PO商业基准', '制作PI结构化草稿', '列出执行前提和未知字段'] },
    { id: 'production', name: '生产资料准备', icon: Workflow, category: '备料生产',
      description: '根据当前确认版本整理生产要求、节点计划和放行缺口。',
      tags: ['生产资料', '放行检查'], includes: ['读取当前规格与订单', '整理生产资料草稿', '检查六项放行条件'] },
    { id: 'check-quality', name: '验货与整改整理', icon: ShieldCheck, category: '验货交付',
      description: '对照规格和验货标准整理检查项，记录缺陷、整改与待复验内容。',
      tags: ['QC', '整改要求'], includes: ['读取规格与质量资料', '保存检查清单和整改草稿', '保留未核实的验货结果'] },
    { id: 'knowledge-assets', name: '知识与资产协作', icon: BookOpen, category: '业务资料',
      description: '搜索知识和资产，按本轮指令引用原件，将成果归档或沉淀为知识草稿。',
      tags: ['知识检索', '资产引用', '归档'], includes: ['搜索并读取授权资料', '将选定资产引用到项目', '归档业务成果与知识草稿'] },
  ],
  plugins: [
    { id: 'source-reader', name: '原件读取', icon: FileSearch, category: '资料工具',
      description: '读取邮件、PDF、文本和表格资料，为业务处理保留可核对的依据。',
      tags: ['EML', 'PDF', 'Excel'], includes: ['读取已引用原件', '提取正文和表格内容', '保留文件与版本来源'] },
    { id: 'document-workbench', name: '成果与版本工具', icon: FileSpreadsheet, category: '文件工具',
      description: '保存各环节成果草稿，保留修改历史并导出当前版本。',
      tags: ['业务草稿', '版本记录'], includes: ['保存结构化成果', '保留历史版本', '导出已保存的文件'] },
    { id: 'knowledge-connector', name: '知识与资产检索', icon: BookOpen, category: '资料工具',
      description: '检索团队规则和公司资产，把匹配资料带入当前工作。',
      tags: ['知识库', '资产库'], includes: ['按业务主题检索', '读取固定资料版本', '保存知识草稿和资产'] },
  ],
  suites: [
    { id: 'inquiry-expert', name: '询盘到报价', icon: ShoppingBag, category: '询盘到报价',
      description: '从客户需求出发，逐步完成规格、供应商比较、核价和报价回复。',
      tags: ['询盘', '规格', '报价'], includes: ['询盘需求整理', '产品规格书', '供应商比较与核价', '客户报价与回复'] },
    { id: 'order-expert', name: '样品到订单', icon: FileSpreadsheet, category: '样品与订单',
      description: '将样品意见转为修改清单，核对商业条款并准备PI与订单技术资料。',
      tags: ['打样', 'PO', 'PI'], includes: ['样品反馈与修改', 'PO逐项核对', 'PI草稿准备'] },
    { id: 'fulfillment-expert', name: '生产与验货准备', icon: Workflow, category: '订单执行',
      description: '整理生产资料、核查放行条件，并准备验货与整改要求。',
      tags: ['生产资料', 'QC', '归档'], includes: ['生产资料准备', '验货与整改整理', '知识与资产协作'] },
  ],
};

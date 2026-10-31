import {
  BookOpen,
  Calculator,
  FileSearch,
  FileSpreadsheet,
  Globe2,
  Languages,
  Mail,
  MessagesSquare,
  PackageSearch,
  Search,
  ShieldCheck,
  ShoppingBag,
  Truck,
  Users,
  Workflow,
  type LucideIcon,
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
  { id: 'skills', label: 'Skill' },
  { id: 'plugins', label: '插件' },
  { id: 'suites', label: '专家套件' },
];

export const marketItems: Record<MarketTab, MarketItem[]> = {
  skills: [
    {
      id: 'inquiry-analysis',
      name: '询盘需求解析',
      description: '从客户原文中提取商品、数量、规格与交期，整理需求和待确认事项。',
      icon: FileSearch,
      category: '询盘处理',
      tags: ['需求提取', '多语言'],
      includes: ['提取关键采购信息', '整理客户需求清单', '标记缺失与待确认信息'],
    },
    {
      id: 'product-matching',
      name: '商品匹配',
      description: '结合商品资料与采购需求，筛选合适的 SKU，并整理可替代方案。',
      icon: PackageSearch,
      category: '商品方案',
      tags: ['SKU 匹配', '替代方案'],
      includes: ['检索匹配商品', '对比规格与起订量', '整理候选与替代方案'],
    },
    {
      id: 'quote-calculation',
      name: '报价计算',
      description: '汇总商品成本、数量与利润要求，生成清晰的报价明细和价格说明。',
      icon: Calculator,
      category: '报价方案',
      tags: ['成本核算', '阶梯报价'],
      includes: ['核算单价与订单金额', '比较不同数量的价格', '列出报价条件与待确认费用'],
    },
    {
      id: 'business-reply',
      name: '商务回复撰写',
      description: '根据客户需求与已确认方案，起草结构清楚、语气自然的商务邮件。',
      icon: MessagesSquare,
      category: '客户沟通',
      tags: ['邮件草稿', '商务表达'],
      includes: ['组织回复结构', '生成商务邮件草稿', '整理下一步沟通事项'],
    },
    {
      id: 'business-translation',
      name: '外贸多语言翻译',
      description: '处理询盘、商品说明与商务邮件，保持规格、金额和行业术语一致。',
      icon: Languages,
      category: '客户沟通',
      tags: ['多语言', '术语一致'],
      includes: ['翻译客户询盘', '转换商品与规格说明', '检查金额、单位和术语'],
    },
    {
      id: 'reply-review',
      name: '回复质量检查',
      description: '检查报价、交付承诺与资料引用，帮助发现遗漏和需要复核的内容。',
      icon: ShieldCheck,
      category: '业务复核',
      tags: ['内容复核', '风险提示'],
      includes: ['核对回复与客户需求', '检查报价和交期表述', '标记需要人工复核的内容'],
    },
  ],
  plugins: [
    {
      id: 'mail-connector',
      name: '邮件连接器',
      description: '将客户往来邮件带入工作空间，集中整理询盘内容与回复草稿。',
      icon: Mail,
      category: '沟通工具',
      tags: ['邮件', '询盘同步'],
      includes: ['导入客户邮件', '整理往来记录', '关联询盘与回复草稿'],
    },
    {
      id: 'spreadsheet',
      name: '表格工具',
      description: '读取商品表、供应商价表与订单明细，减少重复整理和复制粘贴。',
      icon: FileSpreadsheet,
      category: '办公工具',
      tags: ['Excel', 'CSV'],
      includes: ['读取商品与报价表格', '整理订单数据', '导出结构化明细'],
    },
    {
      id: 'web-search',
      name: '网页检索',
      description: '查找客户、市场与商品相关的公开资料，保留来源供进一步核对。',
      icon: Globe2,
      category: '信息检索',
      tags: ['公开资料', '来源追溯'],
      includes: ['检索公开网页', '提取相关业务信息', '整理资料来源'],
    },
    {
      id: 'knowledge-connector',
      name: '知识库连接器',
      description: '关联团队的业务知识和产品文档，为处理询盘提供可引用的资料。',
      icon: BookOpen,
      category: '知识管理',
      tags: ['团队知识', '文档检索'],
      includes: ['连接团队资料', '检索业务知识', '关联引用文档'],
    },
    {
      id: 'crm-connector',
      name: '客户管理连接器',
      description: '汇集客户档案、沟通记录与跟进事项，让每次联系都有上下文。',
      icon: Users,
      category: '客户管理',
      tags: ['CRM', '客户档案'],
      includes: ['读取客户档案', '关联沟通记录', '整理后续跟进事项'],
    },
    {
      id: 'logistics',
      name: '物流查询',
      description: '集中查看运输节点与物流状态，为交付沟通准备清楚的信息。',
      icon: Truck,
      category: '订单履约',
      tags: ['物流追踪', '交付信息'],
      includes: ['查询运输节点', '整理物流状态', '准备交付进展说明'],
    },
  ],
  suites: [
    {
      id: 'inquiry-expert',
      name: '询盘报价专家',
      description: '从读懂客户需求到准备报价与回复，将一条询盘的关键工作串联起来。',
      icon: ShoppingBag,
      category: '询盘到报价',
      tags: ['询盘处理', '报价方案', '客户回复'],
      includes: ['询盘需求解析', '商品匹配', '报价计算', '商务回复撰写', '回复质量检查'],
    },
    {
      id: 'customer-expert',
      name: '客户开发专家',
      description: '整理客户背景、寻找沟通切入点，准备有针对性的开发信与跟进计划。',
      icon: Search,
      category: '客户开发',
      tags: ['客户调研', '开发信', '跟进计划'],
      includes: ['客户背景调研', '采购需求分析', '开发信撰写', '多语言沟通', '跟进计划整理'],
    },
    {
      id: 'fulfillment-expert',
      name: '订单履约专家',
      description: '汇总订单要求、交付节点与沟通记录，协助推进订单并及时发现待办事项。',
      icon: Workflow,
      category: '订单交付',
      tags: ['订单核对', '交付跟进', '异常沟通'],
      includes: ['订单信息核对', '交付节点整理', '物流状态查询', '异常沟通草稿', '履约待办清单'],
    },
  ],
};

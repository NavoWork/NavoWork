import { api } from '../api';
import type { Inquiry, Run } from '../api/types';

const nodeLabels = { customer: '客户与询盘评估', requirements: '客户需求与规格', competitor: '竞品分析', design: '产品设计图', risks: '风险与待确认项', quote: '方案与报价', reply: '双语回复', sample: '打样资料', order: 'PO与PI', production: '生产资料' };
export type GenerationNode = keyof typeof nodeLabels;
export type NodeSimulationInput = { editedText?: string; imagePrompt?: string };
const agentNodes: Partial<Record<GenerationNode, string>> = {
  customer: 'inquiry', requirements: 'requirements', quote: 'costing',
  sample: 'sample', order: 'order', production: 'production',
};

export function generateInquiryNode(path: string, inquiry: Inquiry, node: GenerationNode, instruction?: string, input?: NodeSimulationInput) {
  const agentNode = agentNodes[node];
  return api.post<Run>(`${path}/workbench/simulations`, {
    node: agentNode || node,
    ...input,
    baseRevision: inquiry.currentRevision,
    contextScope: 'inquiry',
    ...(inquiry.pendingRunId ? { skipPendingRunId: inquiry.pendingRunId } : {}),
    instruction: instruction || `使用本地模拟资料生成「${nodeLabels[node]}」草稿，保留缺项和待确认内容。`,
  });
}

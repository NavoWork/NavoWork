import { api } from '../api';
import type { Inquiry, Run } from '../api/types';

export const knowledgeQuoteInstruction = '请根据当前产品、规格和数量，自动检索知识库中维护的工厂资料，读取最新有效版本，核对适用条件并比较成本。使用工作空间汇率和目标毛利率，生成成本表与客户报价草稿供我审查，保留工厂资料的版本和核价依据。已有资料不要让我重复导入或录入；确实缺项时只指出知识库中需要维护的具体内容。';

export async function createKnowledgeQuoteRun(path: string, base: string, inquiry: Inquiry) {
  const pending = inquiry.pendingRunId ? await api.get<Run>(`${base}/runs/${inquiry.pendingRunId}`) : null;
  return api.post<Run>(`${path}/runs`, {
    action: 'prepare_quote', knowledgeQuote: true, generationTarget: 'quote',
    baseRevision: inquiry.currentRevision, instruction: knowledgeQuoteInstruction,
    ...(pending?.status === 'needs_input' ? {
      replyToRunId: pending.id,
      answers: pending.clarification?.questions.map(question => ({ questionId: question.id, value: '工厂资料在知识库中维护，请重新检索最新有效版本，按当前需求自动核价并生成待审查草稿。' })),
    } : {}),
  });
}

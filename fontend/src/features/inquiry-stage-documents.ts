import type { Revision, WorkbenchArtifact } from '../api/types';
import type { DocumentKind, WorkspaceDocument } from './inquiry-canvas-model';

export const stageDocuments: { kind: DocumentKind; title: string; artifacts: string[] }[] = [
  { kind: 'competitor', title: '竞品分析', artifacts: ['competitor_analysis', 'design_brief'] },
  { kind: 'design', title: '产品设计图', artifacts: ['concept_image'] },
  { kind: 'sample', title: '打样与确认', artifacts: ['sample'] },
  { kind: 'order', title: '订单与合同', artifacts: ['order', 'payment'] },
  { kind: 'production', title: '生产准备', artifacts: ['production', 'ta', 'qc'] },
];

const lines = (values: unknown[]) => values.filter(Boolean).join('\n');
const dollars = (value: unknown) => value == null ? '待确认' : `USD ${value}`;
export function stageHasContent(revision: Revision | undefined, kind: DocumentKind): boolean {
  const key = stageDocuments.find((stage) => stage.kind === kind)?.artifacts[0];
  const artifact = key ? revision?.nodeArtifacts?.[key] : undefined;
  return Boolean(artifact && !artifact.content.missingFields?.includes('not_present_in_source_revision'));
}
export function artifactText(artifact?: WorkbenchArtifact): string {
  if (!artifact) return '';
  const c = artifact.content;
  switch (artifact.kind) {
    case 'competitor_analysis':
      return lines([
        ...(c.comparisons || []).map((item: any) => `${item.name} · ${item.price}\n${item.material}\n${item.features}`),
        !(c.comparisons?.length) && (c.observations || []).map((item: any) => `${item.competitor} · ${item.attribute}\n${item.excerpt}`).join('\n\n'),
        '\n设计建议', ...(c.suggestions || []).map((item: any) => `• ${item.text}`),
        '\n模拟竞品快照 · 零售价仅用于定位参考',
      ]);
    case 'design_brief':
      return lines(['设计简报', ...(c.competitorSuggestions || []).map((item: any) => `• ${item.text}`), '最终结构与工艺按客户规格核对。']);
    case 'concept_image':
      return lines([c.prompt, '预置演示图 · 仅用于设计沟通', '尺寸、Logo 与工艺以规格和打样确认结果为准。']);
    case 'sample':
      return lines([`样品编号：${c.sampleRef || '待登记'}`, `轮次：${c.round || 1} · 产前样`, `样品费：${dollars(c.feeUsd)}；快递费：${dollars(c.courierUsd)}`,
        `检查项：${Object.entries(c.checks || {}).map(([key, value]) => `${({ appearance: '外观', dimensions: '尺寸', function: '功能', workmanship: '做工', packaging: '包装' } as Record<string, string>)[key] || key} ${value === 'passed' ? '通过' : '待核对'}`).join(' / ')}`,
        `封样位置：${c.sealedSample?.location || '待登记'}`, '模拟样品记录 · 等待人工确认']);
    case 'order':
      return lines([`PO：${c.po?.number || '待登记'}`, `PI：${c.pi?.number || '待登记'}`, `数量：${c.po?.quantity || '待确认'} 件`,
        `单价：${dollars(c.po?.unitPriceUsd)}；总额：${dollars(c.po?.totalUsd)}`, `${c.po?.incoterm || 'FOB'} ${c.po?.namedPlace || 'Ningbo'}`, `付款：${c.po?.paymentTerms || '30% 定金，70% 出货前付清'}`, '买卖双方确认及收款核验待完成']);
    case 'payment':
      return lines(['付款计划', ...(c.schedule || []).map((item: any) => `${item.milestone === 'deposit' ? '定金' : '尾款'}：${dollars(item.amountUsd)} · ${Number(item.ratio) * 100}%`), '模拟计划 · 未核验实际收款']);
    case 'production':
      return lines([`产品：${c.product || '见当前规格'}`, `数量：${c.quantity || '见订单'} 件`, `生产周期：${c.productionDays || '待确认'} 天`, `包装：${c.packaging || '见当前规格'}`, `检验：${c.qcStandard || '待确认'}`, '生产包草稿 · 待工厂确认和人工放行']);
    case 'ta':
      return lines(['T&A 进度计划', ...(c.tasks || []).map((item: any) => `第 ${item.day} 天 · ${item.task} · ${item.owner}`)]);
    case 'qc':
      return lines([`检验标准：${c.standard || '待确认'}`, ...(c.checks || []).map((item: any) => `• ${typeof item === 'string' ? item : JSON.stringify(item)}`), c.requirements]);
    default: return JSON.stringify(c, null, 2);
  }
}

export function additionalStageDocuments(revision?: Revision): WorkspaceDocument[] {
  return stageDocuments.map(({ kind, title, artifacts }) => {
    const primary = revision?.nodeArtifacts?.[artifacts[0]];
    return {
      id: `${kind}:${revision?.number || 0}`, kind, title, folder: 'analysis', revision,
      text: artifacts.map((key) => artifactText(revision?.nodeArtifacts?.[key])).filter(Boolean).join('\n\n'),
      caption: primary ? `V${primary.version} · ${kind === 'design' ? '预置演示图' : '待核对'}` : '等待生成',
      hasContent: stageHasContent(revision, kind),
      imageUrl: kind === 'design' ? primary?.content.downloadUrl : undefined,
      comparisons: kind === 'competitor' ? primary?.content.comparisons : undefined,
    };
  });
}

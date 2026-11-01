import { describe, expect, it } from 'vitest';
import type { Inquiry, Revision } from '../api/types';
import {
  initialCanvas,
  workflowKinds,
  progressiveCanvasDocuments,
  workspaceDocuments,
  type CanvasState,
} from './inquiry-canvas-model';

const inquiry: Inquiry = {
  id: 'inquiry-test',
  workspaceId: 'workspace-test',
  title: '测试询盘',
  customer: 'Buyer',
  originalText: 'Please quote custom bags.',
  requestedLocales: ['en-US'],
  businessStatus: 'active',
  metadataVersion: 1,
  currentRevision: 0,
  activeRunId: null,
  updatedAt: '2026-11-01T00:00:00Z',
  nextAction: '',
};

function revision(patch: Partial<Revision> = {}): Revision {
  return {
    inquiryId: inquiry.id,
    number: 1,
    runId: 'run-test',
    requirements: {
      requestedProduct: null,
      specification: null,
      quantity: null,
      destination: null,
      requestedArrival: null,
      customization: null,
      certificationRequests: [],
      missingFields: [],
      evidenceRefs: [],
    },
    proposal: {
      proposalId: 'proposal-test',
      version: 1,
      requestedSku: null,
      selectedSku: null,
      differences: [],
      status: 'proposed',
    },
    quote: null,
    replies: { 'en-US': '', 'es-MX': '' },
    risks: [],
    checks: [],
    sourceRefs: [],
    assetRefs: [],
    ruleSetVersion: 'workbench-v2',
    createdAt: inquiry.updatedAt,
    changeSummary: [],
    ...patch,
  };
}

function documents(current?: Revision, state: CanvasState = initialCanvas()) {
  return workspaceDocuments({
    inquiry: { ...inquiry, currentRevision: current?.number || 0 },
    revision: current,
    revisions: current ? [current] : [],
    messages: [],
    state,
  }).filter(
    (doc) =>
      !workflowKinds.includes(doc.kind) ||
      doc.id.endsWith(`:${current?.number || 0}`),
  );
}

const businessNodes = (docs: ReturnType<typeof documents>) =>
  progressiveCanvasDocuments(docs).map((doc) => doc.kind);

describe('progressive inquiry canvas', () => {
  it('keeps skipped empty nodes visible with warnings while revealing the next node', () => {
    const docs = workspaceDocuments({ inquiry: { ...inquiry, nodeWarnings: {
      requirements: [{ question: '请补充尺寸。', runId: 'run-skip', skipped: true }],
    } }, revisions: [], messages: [], state: initialCanvas() });
    const nodes = progressiveCanvasDocuments(docs);
    expect(nodes.map((node) => node.kind)).toEqual(['original', 'requirements', 'competitor']);
    const requirements = nodes.find((node) => node.kind === 'requirements')!;
    expect(requirements.text).toBe('');
    expect(requirements.hasContent).toBe(false);
    expect(requirements.warnings).toEqual(['请补充尺寸。']);
  });
  it('starts with the original inquiry and one genuinely empty requirements node', () => {
    const docs = documents();
    expect(businessNodes(docs)).toEqual(['original', 'requirements']);
    expect(docs.find((doc) => doc.kind === 'requirements')?.text).toBe('');
    expect(docs.find((doc) => doc.kind === 'conversation')).toBeDefined();
  });

  it('does not treat a revision with no business fields as completed requirements', () => {
    expect(businessNodes(documents(revision()))).toEqual(['original', 'requirements']);
  });

  it('reveals competitor analysis after requirements without treating the copied SKU as a quote', () => {
    const current = revision();
    current.requirements.requestedProduct = 'Custom backpack';
    current.proposal.selectedSku = 'Custom backpack';
    const docs = documents(current);
    expect(businessNodes(docs)).toEqual(['original', 'requirements', 'competitor']);
    expect(docs.find((doc) => doc.kind === 'quote')?.text).toBe('');
  });

  it('reveals each research, image and downstream stage in order and restores saved drafts', () => {
    const state = initialCanvas();
    for (let index = 0; index < workflowKinds.length; index++) {
      const visible = businessNodes(documents(undefined, state));
      expect(visible).toEqual(['original', ...workflowKinds.slice(0, index + 1)]);
      state.drafts[`${workflowKinds[index]}:0`] = `已保存的${workflowKinds[index]}内容`;
    }
    const restored = JSON.parse(JSON.stringify(state)) as CanvasState;
    expect(businessNodes(documents(undefined, restored))).toEqual(['original', ...workflowKinds]);
    expect(businessNodes(documents(undefined, restored))).toHaveLength(10);
  });

  it('renders artwork only from the saved image artifact, not from a design brief', () => {
    const current = revision();
    current.requirements.requestedProduct = 'Recycled backpack';
    const artifact = (kind: string, content: Record<string, unknown>) => ({ itemId: kind, kind, title: kind, version: 1, status: 'draft', content });
    current.nodeArtifacts = {
      competitor_analysis: artifact('competitor_analysis', { comparisons: [{ name: 'Aster', price: 'EUR 69', material: 'recycled polyester', features: 'laptop sleeve' }] }),
      design_brief: artifact('design_brief', { competitorSuggestions: [] }),
    };
    expect(businessNodes(documents(current))).toEqual(['original', 'requirements', 'competitor', 'design']);
    expect(documents(current).find(doc => doc.kind === 'design')?.hasContent).toBe(false);
    current.nodeArtifacts.concept_image = artifact('concept_image', { downloadUrl: '/api/v1/workspaces/ws_demo/exports/image/download', prompt: 'Navy backpack' });
    const visible = progressiveCanvasDocuments(documents(current));
    expect(visible.find(doc => doc.kind === 'design')?.imageUrl).toContain('/exports/image/download');
    expect(visible.map(doc => doc.kind)).toEqual(['original', 'requirements', 'competitor', 'design', 'quote']);
  });

  it('ignores empty fields, waiting labels and legacy placeholder prose', () => {
    for (const value of [
      '  \n',
      '产品：\n数量：待确认\n规格：待补充',
      '尚未生成。选择现有原件和知识库依据，生成此节点的第一份草稿。',
    ]) {
      const state = initialCanvas();
      state.drafts['requirements:0'] = value;
      expect(businessNodes(documents(undefined, state))).toEqual(['original', 'requirements']);
    }
  });

  it('keeps existing downstream content, attachments and user notes visible', () => {
    const state = initialCanvas();
    state.drafts['reply:0'] = 'Dear Buyer, please confirm the dimensions.';
    state.notes.push({ id: 'note:1', title: '笔记', text: '客户补充要求', folder: 'notes' });
    state.files.push({
      id: 'file:1',
      name: 'spec.pdf',
      title: '规格附件',
      mediaType: 'application/pdf',
      size: 100,
      folder: 'materials',
    });
    expect(businessNodes(documents(undefined, state))).toEqual([
      'original',
      'requirements',
      'reply',
      'file',
      'note',
    ]);
  });

  it('keeps result navigation off the board until the user saves a result', () => {
    const docs = documents();
    docs.push({
      id: 'result:hub',
      title: '对话成果汇总',
      kind: 'result',
      folder: 'analysis',
      text: '已保存 0 个版本',
      caption: '',
    });
    expect(businessNodes(docs)).toEqual(['original', 'requirements']);
    expect(progressiveCanvasDocuments(docs, true).map((doc) => doc.kind)).toEqual([
      'original',
      'requirements',
      'result',
    ]);
  });
});

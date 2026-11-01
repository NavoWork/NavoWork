import { describe, expect, it } from 'vitest';
import type { Inquiry, Revision } from '../api/types';
import {
  initialCanvas,
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
      !['requirements', 'quote', 'risks', 'reply'].includes(doc.kind) ||
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
    expect(nodes.map((node) => node.kind)).toEqual(['original', 'requirements', 'quote']);
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

  it('reveals an empty quote after requirements, without treating its copied SKU as a quote', () => {
    const current = revision();
    current.requirements.requestedProduct = 'Custom backpack';
    current.proposal.selectedSku = 'Custom backpack';
    const docs = documents(current);
    expect(businessNodes(docs)).toEqual(['original', 'requirements', 'quote']);
    expect(docs.find((doc) => doc.kind === 'quote')?.text).toBe('');
  });

  it('reveals only one new empty node as drafts gain content and survive restoration', () => {
    const state = initialCanvas();
    state.drafts['requirements:0'] = '产品：定制背包';
    expect(businessNodes(documents(undefined, state))).toEqual([
      'original',
      'requirements',
      'quote',
    ]);
    state.drafts['quote:0'] = '建议使用再生涤纶，报价待供应商确认。';
    expect(businessNodes(documents(undefined, state))).toEqual([
      'original',
      'requirements',
      'risks',
      'quote',
    ]);
    state.drafts['risks:0'] = '需确认到港时间。';
    const restored = JSON.parse(JSON.stringify(state)) as CanvasState;
    expect(businessNodes(documents(undefined, restored))).toEqual([
      'original',
      'requirements',
      'risks',
      'quote',
      'reply',
    ]);
    expect(documents(undefined, restored).find((doc) => doc.kind === 'reply')?.text).toBe('');
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
      'note',
      'file',
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

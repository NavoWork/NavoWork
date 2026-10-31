import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { sampleRevision } from '../api/fixtures';
import type { RequirementDetail } from '../api/types';
import { InquiryResult } from './InquiryResult';
import { resultSnapshot, revisionDocuments } from './inquiry-canvas-model';

describe('Agent requirement details', () => {
  it.each<[string, RequirementDetail, RequirementDetail]>([
    ['text', '品牌推广礼品', '印客户LOGO'],
    ['structured fields', { purpose: '品牌推广项目', budget: null, dimensions: { width: 0, confirmed: false } }, { requirement: '产品需带客户LOGO', logo_artwork: null }],
    ['lists', ['品牌推广项目', { material: '棉布', colors: ['蓝色', '白色'] }], [{ method: '丝印' }, null]],
  ])('renders %s in results, canvas previews and saved summaries', (_, specification, customization) => {
    const revision = sampleRevision('inq_uk012', 1);
    revision.requirements.specification = specification;
    revision.requirements.customization = customization;
    revision.quote = null;
    const client = new QueryClient();
    try {
      const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(InquiryResult, {
        revision, draftState: { revision: 1, versions: {}, pending: false }, draftsPending: false,
        base: '/workspaces/ws_demo', path: '/inquiries/inq_uk012', scope: 'structured-requirements',
        readOnly: false, busy: false, history: false, selectedAssets: null,
        onSelectAssets() {}, onSource() {}, openDocument() {}, onAccept() {}, onSave() {}, onDefer() {},
        saved: false, deferred: false,
      })));
      const preview = revisionDocuments({ customer: 'Emma', originalText: '', currentRevision: 1 }, revision, [], [])
        .find(doc => doc.kind === 'requirements')!.text;
      for (const text of [html, preview, resultSnapshot(revision).text]) {
        expect(text).toContain('品牌推广');
        expect(text).not.toContain('[object Object]');
      }
      if (!Array.isArray(specification) && typeof specification === 'object') {
        expect(html).toContain('产品用途：品牌推广项目');
        expect(html).toContain('预算：待确认');
        expect(html).toContain('width：0');
        expect(html).toContain('confirmed：否');
      }
    } finally {
      client.clear();
    }
  });
});

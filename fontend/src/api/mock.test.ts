import 'fake-indexeddb/auto';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { mockRequest, resetMockForTests, setMockFault } from './mock';
import type {
  Asset,
  Draft,
  ExportResult,
  Inquiry,
  MaterialBundle,
  Message,
  Page,
  Revision,
  Run,
  RunContext,
  Session,
} from './types';
const w = '/workspaces/ws_demo';
const i = `${w}/inquiries/inq_mx026`;
const get = <T>(path: string) => mockRequest(path) as Promise<T>;
const post = <T>(path: string, body: unknown, key?: string) =>
  mockRequest(path, { method: 'POST', body, idempotencyKey: key }) as Promise<T>;
const put = <T>(path: string, body: unknown) =>
  mockRequest(path, { method: 'PUT', body }) as Promise<T>;
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-10-31T08:00:00Z'));
  await resetMockForTests();
  await post('/auth/session', { name: 'Tester' });
});
afterEach(() => vi.useRealTimers());
describe('Mock contract boundaries', () => {
  it('freezes invocation context on its run, user message and output revision', async () => {
    const context: RunContext = {
      skills: [{ id: 'reply-review', name: '回复质量检查', instructions: ['检查报价和交期表述'] }],
      knowledge: [{ id: 'delivery', title: '交付与承诺规则', folder: '业务流程', content: '交期需要核实', updated: '2026-10-31' }],
    };
    const run = await post<Run>(`${i}/runs`, {
      baseRevision: 2, action: 'revise', instruction: '请核对600件报价', context,
    });
    expect(run.context).toEqual(context);
    const snapshot = structuredClone(context);
    context.knowledge[0].content = '修改后的文档';
    context.skills[0].instructions.push('新指令');
    const messages = await get<{ items: Message[] }>(`${i}/messages`);
    expect(messages.items.find((message) => message.runId === run.id)?.context).toEqual(snapshot);
    vi.setSystemTime(new Date('2026-10-31T08:00:08Z'));
    expect((await get<Run>(`${w}/runs/${run.id}`)).context).toEqual(snapshot);
    expect((await get<Revision>(`${i}/revisions/3`)).context).toEqual(snapshot);
    expect((await get<Revision>(`${i}/revisions/2`)).context).toBeUndefined();
    expect((await get<{ items: Message[] }>(`${w}/inquiries/inq_de014/messages`)).items.some((message) => message.context)).toBe(false);
  });
  it('rejects incomplete or duplicated invocation context without creating a run or message', async () => {
    for (const context of [
      null,
      { skills: [], knowledge: [{ id: 'missing-content' }] },
      { skills: [{ id: 'x', name: 'x', instructions: 'not-an-array' }], knowledge: [] },
      { skills: [{ id: 'x', name: 'x', instructions: ['a'] }, { id: 'x', name: 'x', instructions: ['a'] }], knowledge: [] },
    ]) {
      await expect(post(`${i}/runs`, { baseRevision: 2, action: 'revise', context })).rejects.toMatchObject({ code: 'INVALID_INPUT' });
    }
    expect((await get<Inquiry>(i)).activeRunId).toBeNull();
    expect((await get<{ items: Message[] }>(`${i}/messages`)).items.some((message) => message.context)).toBe(false);
  });
  it('counts all states independently of searched pages and rejects foreign workspaces', async () => {
    expect(await get(`${w}/inquiries/summary`)).toEqual({
      todo: 1,
      active: 1,
      waiting: 1,
      done: 1,
    });
    const list = await get<Page<Inquiry>>(`${w}/inquiries?q=德国&limit=1`);
    expect(list.matchedCount).toBe(1);
    expect(list.items[0].businessStatus).toBe('todo');
    expect(await get(`${w}/inquiries/summary`)).toEqual({
      todo: 1,
      active: 1,
      waiting: 1,
      done: 1,
    });
    await expect(get('/workspaces/another/inquiries/inq_mx026')).rejects.toMatchObject({
      code: 'NOT_FOUND',
    });
  });
  it('creates only once for repeated key and preserves independent original input', async () => {
    const body = {
      title: 'New cups',
      customer: 'Chris',
      originalText: 'Quote 420 porcelain cups for Oslo.',
    };
    const first = await post<Inquiry>(`${w}/inquiries`, body, 'create-key');
    const replay = await post<Inquiry>(`${w}/inquiries`, body, 'create-key');
    expect(replay.id).toBe(first.id);
    expect(replay.originalText).toBe(body.originalText);
    expect(replay.currentRevision).toBe(0);
    await expect(
      post(`${w}/inquiries`, { ...body, title: 'Changed' }, 'create-key'),
    ).rejects.toMatchObject({ code: 'IDEMPOTENCY_CONFLICT' });
    expect((await get<Page<Inquiry>>(`${w}/inquiries`)).matchedCount).toBe(5);
  });
  it('requires reason and optimistic metadata for status transitions and locks closed writes', async () => {
    await expect(
      post(`${i}/status-transitions`, { from: 'active', to: 'waiting', metadataVersion: 1 }),
    ).rejects.toMatchObject({ code: 'INVALID_INPUT' });
    const closed = await post<Inquiry>(`${i}/status-transitions`, {
      from: 'active',
      to: 'done',
      metadataVersion: 1,
      closeReason: '客户取消',
    });
    expect(closed.businessStatus).toBe('done');
    await expect(post(`${i}/runs`, { baseRevision: 2, action: 'revise' })).rejects.toMatchObject({
      code: 'INQUIRY_CLOSED',
    });
    await expect(
      post(`${i}/status-transitions`, { from: 'done', to: 'active', metadataVersion: 1 }),
    ).rejects.toMatchObject({ code: 'METADATA_CONFLICT' });
    expect(
      (
        await post<Inquiry>(`${i}/status-transitions`, {
          from: 'done',
          to: 'active',
          metadataVersion: 2,
        })
      ).businessStatus,
    ).toBe('active');
  });
  it('reconciles durable background runs into their original inquiry only', async () => {
    const run = await post<Run>(
      `${i}/runs`,
      { baseRevision: 2, action: 'revise', instruction: '修改为600件' },
      'run-key',
    );
    expect(
      (
        await post<Run>(
          `${i}/runs`,
          { baseRevision: 2, action: 'revise', instruction: '修改为600件' },
          'run-key',
        )
      ).id,
    ).toBe(run.id);
    await expect(post(`${i}/runs`, { baseRevision: 2, action: 'revise' })).rejects.toMatchObject({
      code: 'RUN_IN_PROGRESS',
    });
    expect((await get<Inquiry>(`${w}/inquiries/inq_de014`)).currentRevision).toBe(0);
    vi.setSystemTime(new Date('2026-10-31T08:00:08Z'));
    expect((await get<Run>(`${w}/runs/${run.id}`)).status).toBe('succeeded');
    expect((await get<Revision>(`${i}/revisions/3`)).quote?.goodsSubtotalMinor).toBe(108000);
    expect((await get<Inquiry>(`${w}/inquiries/inq_de014`)).currentRevision).toBe(0);
  });
  it('cancellation prevents late commits and allows new work', async () => {
    const run = await post<Run>(`${i}/runs`, {
      baseRevision: 2,
      action: 'revise',
      instruction: '600件',
    });
    expect((await post<Run>(`${w}/runs/${run.id}/cancel`, {})).status).toBe('cancelled');
    vi.setSystemTime(new Date('2026-10-31T08:01:00Z'));
    expect((await get<Inquiry>(i)).currentRevision).toBe(2);
    expect((await get<Run>(`${w}/runs/${run.id}`)).status).toBe('cancelled');
  });
  it('does not fabricate analysis for new original input or overwrite old outputs on failure', async () => {
    const created = await post<Inquiry>(`${w}/inquiries`, {
      title: 'Other product',
      customer: 'Other',
      originalText: 'Please quote office chairs.',
    });
    const run = await post<Run>(`${w}/inquiries/${created.id}/runs`, {
      baseRevision: 0,
      action: 'analyze',
    });
    const failed = await post<Run>(`${i}/runs`, {
      baseRevision: 2,
      action: 'revise',
      instruction: '900件',
    });
    vi.setSystemTime(new Date('2026-10-31T08:00:08Z'));
    expect((await get<Run>(`${w}/runs/${run.id}`)).status).toBe('needs_input');
    expect((await get<Inquiry>(`${w}/inquiries/${created.id}`)).currentRevision).toBe(0);
    expect((await get<Run>(`${w}/runs/${failed.id}`)).status).toBe('failed');
    expect((await get<Inquiry>(i)).currentRevision).toBe(2);
  });
  it('retains competing draft updates, separates locales and invalidates review', async () => {
    const path = `${i}/revisions/2/reply-drafts/en-US`;
    const draft = await get<Draft>(`${i}/revisions/2/reply-drafts?locale=en-US`);
    const spanish = await get<Draft>(`${i}/revisions/2/reply-drafts?locale=es-MX`);
    const changed = await put<Draft>(path, {
      text: draft.text + '\nThank you.',
      baseDraftVersion: 1,
    });
    expect(changed.draftVersion).toBe(2);
    expect(changed.reviewStatus).toBe('needs_review');
    expect(
      (await get<Draft>(`${i}/revisions/2/reply-drafts?locale=en-US&draftVersion=1`)).text,
    ).toBe(draft.text);
    await expect(
      put(path, { text: 'Stale replacement', baseDraftVersion: 1 }),
    ).rejects.toMatchObject({ code: 'DRAFT_CONFLICT' });
    expect((await get<Draft>(`${i}/revisions/2/reply-drafts?locale=es-MX`)).text).toBe(
      spanish.text,
    );
    setMockFault('draft-conflict');
    await expect(put(path, { text: 'Local text', baseDraftVersion: 2 })).rejects.toMatchObject({
      code: 'DRAFT_CONFLICT',
    });
    expect((await get<Draft>(`${i}/revisions/2/reply-drafts?locale=en-US`)).draftVersion).toBe(3);
  });
  it('blocks wrong amounts and safely escapes exported draft content without changing status', async () => {
    const path = `${i}/revisions/2/reply-drafts/en-US`;
    const draft = await get<Draft>(`${i}/revisions/2/reply-drafts?locale=en-US`);
    await put(path, { text: draft.text.replace('540.00', '999.00'), baseDraftVersion: 1 });
    await expect(
      post(`${i}/exports`, { revision: 2, draftVersions: { 'en-US': 2, 'es-MX': 1 } }),
    ).rejects.toMatchObject({ code: 'REVIEW_BLOCKED' });
    await put(path, { text: draft.text + '\n<script>alert(1)</script>', baseDraftVersion: 2 });
    const output = await post<ExportResult>(`${i}/exports`, {
      revision: 2,
      draftVersions: { 'en-US': 3, 'es-MX': 1 },
    });
    expect(output.html).toContain('&lt;script&gt;');
    expect(output.html).not.toContain('<script>');
    expect((await get<Inquiry>(i)).businessStatus).toBe('active');
  });
  it('enforces administrator publish privileges and preserves published source versions', async () => {
    await post('/auth/session', { name: 'Member', role: 'member' });
    expect((await get<Session>('/me')).user.role).toBe('member');
    const source = await post<{ id: string }>(`${w}/knowledge`, { title: 'x', content: 'y' });
    await expect(
      post(`${w}/knowledge/${source.id}/versions/1/publish`, { editVersion: 1 }),
    ).rejects.toMatchObject({ code: 'FORBIDDEN' });
    await post('/auth/session', { name: 'Admin' });
    await expect(
      mockRequest(`${w}/knowledge/delivery-policy/versions/1`, {
        method: 'PATCH',
        body: { content: 'overwrite', editVersion: 1 },
      }),
    ).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  });
  it('locks accepted 600-unit proposal to its matching amount and does not revert to 300', async () => {
    const revise = await post<Run>(`${i}/runs`, {
      baseRevision: 2,
      action: 'revise',
      instruction: '改为600件',
    });
    vi.setSystemTime(new Date('2026-10-31T08:00:08Z'));
    await get(`${w}/runs/${revise.id}`);
    const rev = await get<Revision>(`${i}/revisions/3`);
    const acceptance = await post<Run>(`${i}/runs`, {
      baseRevision: 3,
      action: 'accept_proposal',
      instruction: '客户确认接受600件现货方案',
      acceptanceEvidence: '客户确认接受600件现货方案',
      proposalRef: { proposalId: rev.proposal.proposalId, version: rev.proposal.version },
    });
    vi.setSystemTime(new Date('2026-10-31T08:00:16Z'));
    await get(`${w}/runs/${acceptance.id}`);
    const accepted = await get<Revision>(`${i}/revisions/4`);
    expect(accepted.proposal.status).toBe('accepted');
    expect(accepted.quote?.quantity).toBe(600);
    expect(accepted.quote?.goodsSubtotalMinor).toBe(108000);
    expect(accepted.replies['en-US']).toContain('1080.00');
    expect(accepted.replies['en-US']).toContain('recorded your acceptance');
  });
  it('rejects SKU-mismatched asset references and freezes matched assets into a new revision', async () => {
    const form = new FormData();
    form.append(
      'file',
      new File(['%PDF-1.4\nMock document'], 'spec.pdf', { type: 'application/pdf' }),
    );
    form.append('title', 'Wrong SKU specification');
    form.append('skuScope', 'CUP-CERAMIC');
    const wrong = await post<Asset>(`${w}/assets`, form);
    await expect(
      post(`${i}/runs`, { baseRevision: 2, action: 'revise', assetVersionIds: [`${wrong.id}:v1`] }),
    ).rejects.toMatchObject({ code: 'BUSINESS_VALIDATION_FAILED' });
    const run = await post<Run>(`${i}/runs`, {
      baseRevision: 2,
      action: 'revise',
      assetVersionIds: ['asset_sample:v1'],
    });
    vi.setSystemTime(new Date('2026-10-31T08:00:08Z'));
    await get(`${w}/runs/${run.id}`);
    expect((await get<Revision>(`${i}/revisions/3`)).assetRefs).toEqual(['asset_sample:v1']);
    expect((await get<Revision>(`${i}/revisions/2`)).assetRefs).toEqual([]);
  });
  it('freezes material versions and blocks invalid bundles while allowing historical draft exports', async () => {
    const bundle = await post<MaterialBundle>(`${i}/material-bundles`, {
      revision: 2,
      draftVersions: { 'en-US': 1, 'es-MX': 1 },
      assetVersionIds: [],
    });
    expect(bundle.sourceVersionIds).toContain('price-stock-v1');
    const original = await get<Draft>(`${i}/revisions/2/reply-drafts?locale=en-US`);
    await put(`${i}/revisions/2/reply-drafts/en-US`, {
      text: original.text.replace('540.00', '999.00'),
      baseDraftVersion: 1,
    });
    await expect(
      post(`${i}/material-bundles`, { revision: 2, draftVersions: { 'en-US': 2, 'es-MX': 1 } }),
    ).rejects.toMatchObject({ code: 'REVIEW_BLOCKED' });
    const output = await post<ExportResult>(`${i}/exports`, { bundleId: bundle.id });
    expect(output.html).toContain('540.00');
    expect(output.html).not.toContain('999.00');
    expect(
      (await get<{ items: MaterialBundle[] }>(`${i}/material-bundles`)).items[0].draftVersions[
        'en-US'
      ],
    ).toBe(1);
  });
  it('returns diagnostic API errors without silent fallback when disconnected', async () => {
    setMockFault('network');
    await expect(get(`${w}/inquiries`)).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 });
    setMockFault('none');
    expect((await get<Page<Inquiry>>(`${w}/inquiries`)).matchedCount).toBe(4);
  });
});

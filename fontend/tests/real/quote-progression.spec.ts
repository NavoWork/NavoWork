import { createHash } from 'node:crypto';
import { expect, test } from '@playwright/test';

const base = '/api/v1/workspaces/ws_demo';

for (const mobile of [false, true]) {
  test(`知识库核价直接执行、审查草稿并提示资料更新（${mobile ? '手机' : '桌面'}）`, async ({ page }, info) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.getByLabel('账号邮箱').fill('demo@navowork.local');
    await page.getByLabel('密码').fill('ChangeMe123!');
    await page.getByRole('button', { name: '登录工作空间' }).click();
    await expect(page.getByRole('navigation', { name: '主导航', includeHidden: true })).toBeAttached();
    const created = await page.request.post(`${base}/inquiries`, { data: {
      title: '知识库自动核价验证', customer: 'Knowledge quote test', requestedLocales: ['en-US'],
      originalText: 'Please quote 3,000 custom backpacks, FOB Ningbo.',
    } });
    expect(created.ok()).toBeTruthy();
    const inquiry = await created.json();
    const path = `${base}/inquiries/${inquiry.id}`;
    expect((await page.request.post(`${path}/artifacts`, { data: { kind: 'spec', title: '背包规格书', content: { product: 'Backpack', quantity: 3000 } } })).ok()).toBeTruthy();
    await page.goto(`/inquiries/${inquiry.id}`);
    const work = page.locator('.inquiry-mount:not([hidden])');
    await expect(work.getByRole('button', { name: '自动核价', exact: true })).toBeVisible();
    await expect(work.getByText('自动读取知识库中的工厂资料，匹配当前需求并核价，你只需审查结果。')).toBeVisible();
    let runWrites = 0;
    let manualWrites = 0;
    page.on('request', request => {
      if (request.method() !== 'POST') return;
      if (request.url().endsWith(`${path}/runs`)) runWrites++;
      if (/\/(evidence|supplier-offers)$/.test(request.url())) manualWrites++;
    });
    const dispatch = page.waitForRequest(request => request.method() === 'POST' && request.url().endsWith(`${path}/runs`));
    await work.getByRole('button', { name: '自动核价', exact: true }).click();
    const body = (await dispatch).postDataJSON();
    expect(body.knowledgeQuote).toBe(true);
    expect(body.generationTarget).toBe('quote');
    expect(body.instruction).toContain('知识库');
    expect(body).not.toHaveProperty('selectedSupplierOfferId');
    expect(body).not.toHaveProperty('costInputs');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    // This test server has no model configured: report that honestly, without demanding duplicate input.
    await expect(work.getByRole('alert')).toContainText('知识库自动核价需要连接 Agent');
    await expect(work.getByRole('button', { name: '自动核价', exact: true })).toBeEnabled();
    await expect(page.getByLabel('生成报价的供应商')).toHaveCount(0);
    expect(runWrites).toBe(1);
    expect(manualWrites).toBe(0);

    const source = await (await page.request.post(`${base}/knowledge`, { data: {
      title: '背包工厂 A · 核价资料', content: '背包 CNY44/件，包装2，本地费用4，MOQ1000，交期28天。',
    } })).json();
    const factorySource = { sourceId: source.sourceId, sourceVersionId: `${source.sourceId}:v1`, title: source.title, version: 1, status: 'draft', contentHash: createHash('sha256').update(source.content).digest('hex') };
    const cost = { input: { base: '44', packaging: '2', local: '4', exchangeRate: '7.2', margin: '20', quantity: 3000 }, result: { unitPriceUsd: '8.69' }, factorySource };
    expect((await page.request.post(`${path}/artifacts`, { data: { kind: 'cost', title: '成本核算表', content: cost } })).ok()).toBeTruthy();
    await page.reload();
    await work.getByLabel('业务流程').getByRole('button', { name: /成本报价/ }).click();
    await work.getByRole('button', { name: '审查报价', exact: true }).click();
    await expect(work.locator('.ba-document')).toContainText('背包工厂 A');
    await expect(work.locator('.ba-document')).toContainText('8.69');
    await page.screenshot({ path: info.outputPath('knowledge-quote-review.png'), fullPage: true });
    expect((await page.request.post(`${base}/knowledge/${source.sourceId}/versions`, { data: { content: '背包价格调整为52，其他口径不变。' } })).ok()).toBeTruthy();
    await work.getByRole('link', { name: '维护工厂资料' }).click();
    await expect(page).toHaveURL(/\/knowledge$/);
    await page.goto(`/inquiries/${inquiry.id}`);
    await expect(work.getByRole('button', { name: '重新核价', exact: true })).toBeVisible();
    await expect(work.getByLabel('业务流程').getByRole('button', { name: /成本报价/ })).toContainText('资料已变更 · 待重算');
    await expect(work.getByText(/当前报价依据为 V1/)).toBeVisible();
    await page.screenshot({ path: info.outputPath('knowledge-updated.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(manualWrites).toBe(0);
  });
}

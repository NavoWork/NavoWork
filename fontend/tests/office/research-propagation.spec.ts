import { test, expect } from '@playwright/test';

test('curated competitor sources, adopted ideas and deterministic propagation are visible in one case', async ({
  page,
}, info) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const created = await page.request.post(`${base}/inquiries`, {
    data: {
      title: 'Research and synchronization acceptance',
      customer: 'Research Buyer',
      originalText: 'Review canvas backpacks at quantity 100.',
    },
  });
  expect(created.ok()).toBeTruthy();
  const inquiry = await created.json();
  const path = `${base}/inquiries/${inquiry.id}`;
  const evidence = await page.request.post(`${path}/evidence`, {
    data: {
      title: 'Curated competitor catalogue',
      sourceRole: 'internal_note',
      text: 'Example Brand: recycled canvas backpack with two zipped pockets. Retail price USD 35, EU catalogue, 2026.',
    },
  });
  expect(evidence.ok()).toBeTruthy();
  const costSource = await page.request.post(`${path}/evidence`, {
    data: {
      title: 'Factory costing scope',
      sourceRole: 'supplier_quote',
      text: 'Unit material cost CNY 72; one-time setup CNY 720; MOQ 1.',
    },
  });
  const sourceId = (await costSource.json()).id;
  await page.goto(`/inquiries/${inquiry.id}`);
  await page.getByRole('button', { name: /02 需求与规格/ }).click();
  await page.getByText('竞品、概念图与 BOM 识别', { exact: true }).click();
  await page.getByLabel('竞品资料', { exact: true }).selectOption((await evidence.json()).id);
  await expect(page.getByLabel('来源定位', { exact: true }).locator('option')).toHaveCount(1);
  await page.getByLabel('竞品名称', { exact: true }).fill('Example Brand');
  await page.getByLabel('比较维度', { exact: true }).fill('Material and pocket structure');
  await page.getByLabel('观察日期', { exact: true }).fill('2026-01-01');
  await page.getByLabel('适用范围', { exact: true }).fill('EU catalogue, recycled canvas models');
  await page.getByRole('button', { name: '加入比较', exact: true }).click();
  await page
    .getByLabel('候选设计建议', { exact: true })
    .fill('Consider two zipped pockets after factory review.');
  await page.getByRole('button', { name: '保存竞品比较与设计简报', exact: true }).click();
  await expect(page.getByText('竞品比较 V1 · 待复核', { exact: true })).toBeVisible();
  await page.getByLabel('采纳建议 1', { exact: true }).check();
  await page.getByRole('button', { name: '记录采纳的设计方向', exact: true }).click();
  await expect(page.getByText(/已采纳方向：Consider two zipped pockets/)).toBeVisible();
  const fields = {
    product: 'Canvas bag',
    quantity: '100',
    incoterm: 'FOB',
    incotermsVersion: '2020',
    namedPlace: 'Ningbo',
    paymentTerms: '30% deposit',
  };
  const specResponse = await page.request.put(`${path}/workbench/artifacts/spec`, {
    data: { baseVersion: 0, content: { fields } },
  });
  expect(specResponse.ok()).toBeTruthy();
  const costResponse = await page.request.put(`${path}/workbench/artifacts/cost`, {
    data: {
      baseVersion: 0,
      content: {
        quantity: 100,
        exchangeRate: '7.2',
        margin: '0.2',
        lines: [
          { category: 'material', label: 'Material', amountCny: '72', scope: 'per_unit', sourceId },
          { category: 'tooling', label: 'Setup', amountCny: '720', scope: 'per_order', sourceId },
        ],
      },
    },
  });
  expect(costResponse.ok(), await costResponse.text()).toBeTruthy();
  const quoteResponse = await page.request.put(`${path}/workbench/artifacts/quotation`, {
    data: {
      baseVersion: 0,
      content: {
        product: 'Canvas bag',
        incoterm: 'FOB',
        incotermsVersion: '2020',
        namedPlace: 'Ningbo',
        paymentTerms: '30% deposit',
        validUntil: '2999-12-31',
      },
    },
  });
  expect(quoteResponse.ok()).toBeTruthy();
  const oldExportResponse = await page.request.post(
    `${path}/workbench/artifacts/quotation/export`,
    { data: { format: 'xlsx' } },
  );
  expect(oldExportResponse.ok()).toBeTruthy();
  const oldExport = await oldExportResponse.json();
  // Exercise the actual PRD journey: a registered cell inside a native DOCX
  // changes business fields and dependent files without a second chat request.
  const sourceExport = await page.request.post(`${path}/workbench/artifacts/spec/export`, {
    data: { format: 'docx' },
  });
  expect(sourceExport.ok()).toBeTruthy();
  const copied = await page.request.post(`${path}/workbench/office`, {
    data: { fileId: (await sourceExport.json()).exportId },
  });
  expect(copied.ok()).toBeTruthy();
  const working = await copied.json();
  const locator = working.source.templateMapping.fields['fields.quantity'];
  await page.reload();
  await page.getByText('文件编辑与预览', { exact: false }).first().click();
  await page.getByLabel('打开工作副本', { exact: true }).selectOption(working.documentId);
  await expect(page.getByText(/此文件已登记规格字段映射/)).toBeVisible();
  const quantityCell = page.getByLabel(`表 1 行 ${locator.row + 1} 列 2`, { exact: true });
  await expect(quantityCell).toHaveValue('100');
  await quantityCell.fill('200');
  await page.getByRole('button', { name: /保存新版本/ }).click();
  await expect(page.getByRole('status')).toContainText('已更新对应业务字段');
  await expect(quantityCell).toHaveValue('200');
  const view = await (await page.request.get(`${path}/workbench`)).json();
  expect(view.artifacts.cost.content.unitPriceUsd).toBe('13.13');
  expect(view.artifacts.quotation.content.totalUsd).toBe('2626.00');
  const historical = await page.request.get(oldExport.downloadUrl);
  expect(historical.headers()['x-artifact-freshness']).toBe('stale');
  await page.reload();
  await page.getByText(/跨文件同步 ·/).click();
  await expect(page.getByText('cost · 已同步', { exact: true })).toBeVisible();
  await expect(page.getByText('quotation · 已同步', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('research-and-propagation.png'), fullPage: true });
});

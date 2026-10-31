import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('new inquiry opens the node workbench and only generates the requested node', async ({
  page,
}, info) => {
  const base = '/api/v1/workspaces/ws_demo';
  const created = await page.request.post(`${base}/inquiries`, {
    data: {
      title: '浏览器联调 · 通勤背包',
      customer: 'Browser Buyer',
      originalText: 'Please quote 3,000 custom backpacks, FOB Ningbo, delivery to Hamburg.',
      destination: 'Hamburg, Germany',
      customerContext: { channel: 'email', email: 'buyer@example.test' },
    },
  });
  expect(created.ok()).toBeTruthy();
  const inquiry = await created.json();
  const path = `${base}/inquiries/${inquiry.id}`;
  await page.goto(`/inquiries/${inquiry.id}`);
  const work = page.locator('.wbv2');
  await expect(work).toBeVisible();
  await expect(work.locator('.wbv2-stage')).toHaveCount(6);
  await expect(work.getByText('Browser Buyer', { exact: true }).first()).toBeVisible();
  await expect(work.getByText('Agent 尚未完成询盘评估')).toHaveCount(0);

  const spec = await page.request.put(`${path}/workbench/artifacts/spec`, {
    data: {
      baseVersion: 0,
      content: {
        fields: {
          product: 'custom commuter backpack',
          quantity: '3000',
          dimensions: '30 x 45 x 15 cm',
          fabric: '600D recycled polyester',
          logo: 'embroidered logo 60 x 25 mm',
          packaging: 'recycled polybag + hangtag',
          inspection: 'AQL 2.5',
          destination: 'Hamburg, Germany',
          incoterm: 'FOB',
          incotermsVersion: '2020',
          namedPlace: 'Ningbo',
        },
      },
    },
  });
  expect(spec.ok()).toBeTruthy();
  await page.reload();
  await work.locator('.wbv2-stage').nth(1).click();
  await expect(work.getByLabel('产品')).toHaveValue('custom commuter backpack');
  await expect(work.getByLabel('验货标准')).toHaveValue('AQL 2.5');
  await page.screenshot({ path: info.outputPath('workbench-v2.png'), fullPage: true });

  const state = await (await page.request.get(`${path}/workbench`)).json();
  expect(state.case.currentRevision).toBe(1);
  expect(Object.keys(state.artifacts)).toEqual(['spec']);
  expect(state.stages.find((stage: { key: string }) => stage.key === 'costing').status).toBe(
    'empty',
  );
});

test('Wiki, assets, favorites and the skill market are persisted', async ({ page }) => {
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('文档名称').fill('服务端知识测试');
  await dialog.getByLabel('Markdown 正文').fill('# 规格确认\n请保留客户书面确认。');
  await dialog.getByRole('button', { name: '创建文档' }).click();
  await expect(page.locator('.wiki-row').filter({ hasText: '服务端知识测试' })).toBeVisible();
  await page.getByRole('button', { name: '收藏 服务端知识测试', exact: true }).click();
  await expect(
    page.getByRole('button', { name: '取消收藏 服务端知识测试', exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('button', { name: '取消收藏 服务端知识测试', exact: true }),
  ).toBeVisible();

  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByRole('button', { name: '添加文件', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('资产文件').setInputFiles({
    name: 'personal-proof.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('A persisted personal file'),
  });
  await dialog.getByRole('button', { name: '添加 1 个文件' }).click();
  await expect(page.getByText('personal-proof.txt', { exact: true }).first()).toBeVisible();
  await page.reload();
  await page.getByText('personal-proof.txt', { exact: true }).first().dblclick();
  await expect(page.getByRole('dialog').getByRole('button', { name: '下载文件' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  expect((await download).suggestedFilename()).toBe('personal-proof.txt');
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: '技能市场', exact: true }).click();
  await expect(page.getByText('客户与询盘评估', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: /插件/ }).click();
  await expect(page.getByText('邮件连接器', { exact: true })).toBeVisible();
  await expect(page.getByText('规划中').first()).toBeVisible();
});

test('workbench keeps downstream nodes empty until the user advances them', async ({ page }) => {
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (
    await page.request.post(`${base}/inquiries`, {
      data: {
        title: '空白项目',
        customer: 'Empty Buyer',
        originalText: 'We may need some bags. Please advise.',
      },
    })
  ).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  await page.goto(`/inquiries/${inquiry.id}`);
  const work = page.locator('.wbv2');
  await expect(work).toBeVisible();
  const state = await (await page.request.get(`${path}/workbench`)).json();
  expect(state.case.currentRevision).toBe(0);
  expect(state.artifacts).toEqual({});
  expect(state.stages.find((stage: { key: string }) => stage.key === 'requirements').status).toBe(
    'empty',
  );
  await work.locator('.wbv2-stage').nth(1).click();
  await expect(work.getByText('尚未生成规格')).toBeVisible();
  await work.locator('.wbv2-stage').nth(2).click();
  await expect(work.getByText('尚未生成客户报价')).toBeVisible();
  await expect(work.getByPlaceholder('告诉 Agent 下一步要完成什么…')).toBeVisible();
});

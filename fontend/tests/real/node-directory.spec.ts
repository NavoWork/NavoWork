import { expect, test } from '@playwright/test';

test('node folders expose their data and original files without duplicate revision entries', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (await page.request.post(`${base}/inquiries`, { data: { demoScenarioId: 'de-backpack' } })).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  const upload = await page.request.post(`${path}/evidence`, { multipart: {
    sourceRole: 'supplier_quote', file: { name: 'factory-original.txt', mimeType: 'text/plain', buffer: Buffer.from('Original factory conditions\n' + 'Line item. '.repeat(500) + '\nEND OF ORIGINAL: delivery 28 days') },
  } });
  expect(upload.ok()).toBeTruthy();
  await page.goto(`/inquiries/${inquiry.id}`);
  const directory = page.getByRole('complementary', { name: '当前询盘文件目录' });
  await expect(directory.locator('[data-node-id]')).toHaveCount(2);
  await expect(directory.getByRole('button', { name: '客户需求与规格文件夹', exact: true })).toHaveCount(1);
  await expect(directory.getByRole('button', { name: '需求与方案', exact: true })).toHaveCount(0);
  await directory.getByRole('button', { name: 'factory-original.txt', exact: true }).click();
  await expect(page.getByRole('tabpanel').filter({ visible: true })).toContainText('END OF ORIGINAL: delivery 28 days');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载原件', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('factory-original.txt');
  // Two business versions must still produce one current node folder.
  for (let version = 0; version < 2; version++) {
    const response = await page.request.put(`${path}/workbench/artifacts/spec`, { data: {
      baseVersion: version, title: '需求规格', content: { fields: { product: `Backpack version ${version + 1}`, quantity: '3000' } },
    } });
    expect(response.ok(), await response.text()).toBeTruthy();
  }
  await page.reload();
  await expect(directory.locator('[data-node-id="quote:2"]')).toBeVisible();
  const nodeIds = await page.locator('.react-flow__node:visible').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-id')).sort());
  const folderIds = await directory.locator('[data-node-id]').evaluateAll((folders) => folders.map((folder) => folder.getAttribute('data-node-id')).sort());
  expect(folderIds).toEqual(nodeIds);
  const quote = directory.locator('[data-node-id="quote:2"]');
  await expect(quote.getByRole('button', { name: 'factory-original.txt', exact: true })).toBeVisible();
  await expect(directory.getByRole('button', { name: '需求数据', exact: true })).toHaveCount(1);
  await directory.getByRole('button', { name: '需求数据', exact: true }).click();
  await expect(page.getByRole('tabpanel').filter({ visible: true }).getByLabel('需求产品', { exact: true })).toHaveValue('Backpack version 2');
  const search = directory.getByLabel('搜索当前询盘资料');
  await search.fill('factory-original');
  await expect(directory.getByRole('button', { name: '方案与报价草稿文件夹', exact: true })).toBeVisible();
  await expect(directory.locator('.ic-folder')).toHaveCount(1);
  await search.fill('');
  await directory.getByRole('button', { name: '版本记录文件夹', exact: true }).click();
  await expect(directory.getByRole('button', { name: 'V1 · 历史版本', exact: true })).toBeVisible();
  await expect(directory.getByRole('button', { name: 'V2 · 当前版本', exact: true })).toBeVisible();
});

import { expect, test } from '@playwright/test';

test('real workspace runs a quotation job and displays five saved artifacts', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('heading', { name: '把手上的事，向前推进。' })).toBeVisible();
  await page.goto('/workbench');
  await expect(page.getByRole('heading', { name: '包袋出口工作流' })).toBeVisible();
  const source = await page.evaluate(async () => {
    const response = await fetch('/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag/evidence', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sourceRole: 'supplier_quote', title: '浏览器联调供应商报价', text: 'Backpack RMB44 + packaging RMB2' }),
    });
    return response.json();
  });
  await page.reload();
  await page.getByRole('button', { name: /3a 核价与报价/ }).click();
  await page.getByPlaceholder('供应商名称').fill('联调工厂');
  await page.locator('select').filter({ has: page.locator(`option[value="${source.id}"]`) }).first().selectOption(source.id);
  const costs = page.locator('.rw-costs input');
  for (const [index, value] of ['44', '2', '4', '7.2', '20', '3000'].entries()) await costs.nth(index).fill(value);
  await page.getByRole('button', { name: '保存供应商报价' }).click();
  await page.getByRole('button', { name: '运行当前节点' }).click();
  await expect(page.locator('.rw-card').getByText('客户报价单', { exact: false }).first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator('.rw-card').getByText('供应商报价对比', { exact: false }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: '检查生产资料门禁' })).toBeVisible();
});

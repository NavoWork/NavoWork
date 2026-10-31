import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';

test('uploaded supplier file stays available and missing model never becomes a completed quote', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await page.getByRole('button', { name: /德国客户 · 定制背包/ }).first().click();
  const work = page.locator('.inquiry-mount:not([hidden])');
  await work.getByLabel('导入询盘文件').setInputFiles(resolve('../test/inputs/BAG-2026-DE-001/factory-A-quote.xlsx'));
  await expect(work.locator('.ic-card-file')).toContainText('factory-A-quote.xlsx');
  await expect(work.getByRole('status').filter({ hasText: '已保存到服务端' })).toBeVisible();
  await work.getByLabel('补充要求或客户反馈').fill('读取供应商文件并准备报价，汇率7.20，毛利20%');
  const created = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/inquiries/inq_demo_bag/runs'));
  await work.getByRole('button', { name: '开始处理', exact: true }).click();
  const task = await (await created).json();
  await expect(work.locator('.iw-run')).toContainText('宿主未配置模型', { timeout: 30000 });
  await expect(work.locator('.iw-run')).toHaveAttribute('data-status', 'failed');
  await expect(work.getByLabel('本次生成的文件')).toHaveCount(0);
  const run = await page.evaluate(async id => (await fetch(`/api/v1/workspaces/ws_demo/runs/${id}`)).json(), task.id);
  expect(run.error.code).toBe('MODEL_NOT_CONFIGURED');
  expect(run.agentVerification.liveExecuted).toBe(false);
  await page.reload();
  await expect(work.locator('.ic-card-file')).toContainText('factory-A-quote.xlsx');
  await expect(work.locator('.iw-run')).toContainText('宿主未配置模型');
});

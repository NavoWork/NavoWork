import { test, expect, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

async function login(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('heading', { name: /我的工作/ })).toBeVisible();
}
async function openWorkbench(page: Page) {
  await page.goto('/workbench');
  await expect(page.getByTestId('unit-price')).toHaveText('$8.69');
}
async function changePackaging(page: Page) {
  await page.getByRole('button', { name: '改为定制彩盒', exact: true }).click();
  await expect(page.getByRole('heading', { name: '一个变化，四份成果。' })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  await login(page);
});

test('目标入口不要求订单表单，保留用户原文', async ({ page }) => {
  const goal = 'Please quote 250 glass bottles for Tokyo.';
  await page.getByRole('button', { name: '新建工作', exact: true }).click();
  await page.getByLabel('客户原文').fill(goal);
  await expect(page.getByLabel('客户原文')).toHaveValue(goal);
  await page.getByRole('button', { name: '创建并打开工作' }).click();
  await expect(page.locator('.iw-original')).toContainText(goal);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('成本重算、来源回读、持久化与无效输入阻断', async ({ page }) => {
  await openWorkbench(page);
  await page.getByLabel('工厂基础报价').fill('46');
  await expect(page.getByTestId('unit-price')).toHaveText('$9.03');
  await page.getByRole('button', { name: '供应商 A · B2', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('CNY 44');
  await page.keyboard.press('Escape');
  await page.reload();
  await expect(page.getByLabel('工厂基础报价')).toHaveValue('46');
  await page.getByLabel('人民币每美元汇率').fill('0');
  await expect(page.getByTestId('unit-price')).toHaveText('待修正');
  await page.getByRole('button', { name: '导出交付包', exact: true }).click();
  await expect(page.getByRole('button', { name: /下载草稿包/ })).toBeDisabled();
});

test('包装变更受缺失价格和依赖门禁保护，并保留可回看的旧版', async ({ page }) => {
  await openWorkbench(page);
  await changePackaging(page);
  await expect(page.locator('.tw-diff-list')).toContainText('$9.21');
  await page.getByLabel(/使用已载入的供应商彩盒报价/).uncheck();
  await expect(page.getByRole('button', { name: '应用变更，生成 V2' })).toBeDisabled();
  await expect(page.locator('.tw-diff-list')).toContainText('暂不能核价');
  await page.getByLabel(/使用已载入的供应商彩盒报价/).check();
  await page.getByLabel('接受需求与规格表变更', { exact: true }).uncheck();
  await expect(page.getByRole('button', { name: '应用变更，生成 V2' })).toBeDisabled();
  await page.getByLabel('接受需求与规格表变更', { exact: true }).check();
  await page.getByRole('button', { name: '应用变更，生成 V2' }).click();
  await expect(page.getByTestId('unit-price')).toHaveText('$9.21');
  await expect(page.getByTestId('total-price')).toHaveText('$27,630.00');
  await page.getByRole('button', { name: '版本记录 V2' }).click();
  await page.locator('.tw-history-list').getByRole('button').last().click();
  await expect(page.getByTestId('unit-price')).toHaveText('$8.69');
  await expect(page.getByLabel('工厂基础报价')).toBeDisabled();
  await page.getByRole('button', { name: '返回当前 V2' }).click();
  await expect(page.getByTestId('unit-price')).toHaveText('$9.21');
  await page.reload();
  await expect(page.getByTestId('unit-price')).toHaveText('$9.21');
  await page.getByRole('button', { name: '返回工作台', exact: true }).click();
  await expect(page.getByRole('heading', { name: /我的工作/ })).toBeVisible();
  await page.goto('/workbench');
  await expect(page.getByRole('button', { name: '版本记录 V2' })).toBeVisible();
  await expect(page.getByTestId('unit-price')).toHaveText('$9.21');
});

test('内部报价审核与生产批准分离，已审版本修改后重新审核', async ({ page }) => {
  await openWorkbench(page);
  await page.getByRole('tab', { name: /客户报价单/ }).click();
  await page.getByRole('button', { name: '审核当前报价', exact: true }).click();
  await expect(page.getByRole('button', { name: '确认内部报价', exact: true })).toBeDisabled();
  await page.getByLabel(/我已核对成本/).check();
  await page.getByRole('button', { name: '确认内部报价', exact: true }).click();
  await page
    .locator('.tw-artifact-tree')
    .getByRole('button', { name: /生产资料包/ })
    .click();
  await expect(page.locator('.tw-gate-list')).toContainText('当前版本已完成演示审核');
  await expect(page.locator('.tw-gate-list')).toContainText('缺少客户批准证据');
  await expect(
    page.getByText('当前不满足正式签发或生产放行条件。', { exact: false }),
  ).toBeVisible();
  await page.getByLabel('PO 单价').fill('10');
  await expect(page.getByText('PO 单价与当前报价不一致', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: /可计算成本表/ }).click();
  await page.getByLabel('工厂基础报价').fill('45');
  await expect(page.getByRole('button', { name: '版本记录 V2' })).toBeVisible();
  await page.getByRole('tab', { name: /客户报价单/ }).click();
  await expect(page.getByRole('button', { name: '审核当前报价', exact: true })).toBeEnabled();
});

test('真实导入材料、重载后可读，交付包与 PDF 预览可用', async ({ page }) => {
  await openWorkbench(page);
  await page.locator('.tw-resources input[type=file]').setInputFiles({
    name: 'customer-note.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Customer asks to review dimensions. No production approval.'),
  });
  await expect(page.getByRole('status')).toContainText('已导入 1 份材料');
  await page.reload();
  await page.getByRole('button', { name: 'customer-note.txt', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('No production approval.');
  const sourceDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载原始文件', exact: true }).click();
  const original = await sourceDownload;
  expect(await readFile((await original.path())!, 'utf8')).toContain('No production approval.');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '导出交付包', exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /下载草稿包/ }).click();
  const pack = await downloadPromise;
  expect(pack.suggestedFilename()).toBe('BAG-2026-DE-001-V1-DRAFT.zip');
  const bytes = await readFile((await pack.path())!);
  expect(bytes.subarray(0, 2).toString()).toBe('PK');
  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: '打印当前成果 / PDF' }).click();
  const preview = await popupPromise;
  await expect(preview.getByRole('heading', { name: '可计算成本表' })).toBeVisible();
  await expect(preview.locator('table')).toContainText('8.69');
  await preview.close();
});

test('390px 下所有面板无页面横向溢出，弹窗可键盘关闭', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.wh-status-grid .stat-card')).toHaveCount(4);
  await expect(page.getByRole('button', { name: '待办询盘 1', exact: true })).toBeVisible();
  await expect(page.locator('.wh-work-table tbody tr')).toHaveCount(4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'docs/screenshots/trade-home-mobile.png' });
  await openWorkbench(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'docs/screenshots/trade-workbench-mobile.png' });
  await page.getByRole('button', { name: '资料与成果', exact: true }).click();
  await page.getByRole('button', { name: 'Michael_背包询盘.eml', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('3,000');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: '执行助手', exact: true }).click();
  await expect(page.getByLabel('当前工作目标')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('桌面展示和任意目标不被误执行为包装变更', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator('.wh-work-table tbody tr')).toHaveCount(4);
  await page.screenshot({ path: 'docs/screenshots/trade-home-desktop.png' });
  await openWorkbench(page);
  await page.getByLabel('当前工作目标').fill('不要把包装换成彩盒，只检查运费');
  await page.getByRole('button', { name: '提交工作目标', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('目标已保留在执行日志');
  await expect(page.getByTestId('unit-price')).toHaveText('$8.69');
  await page.getByRole('button', { name: '关闭提示', exact: true }).click();
  await page.screenshot({ path: 'docs/screenshots/trade-workbench-desktop.png' });
});

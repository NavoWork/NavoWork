import { test, expect, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('heading', { name: /今天，从一个好机会开始/ })).toBeVisible();
}
const csvHeader =
  'sku,name,specification,moq,stock,stockObservedAt,minQuantity,maxQuantity,unitPriceMinor,currency,productionDays,dispatchDays,startsAfter,source\n';
const csvRow =
  'QA-BAG,测试商品导入,未印花,100,800,2026-10-31T00:00:00Z,100,,180,USD,,3,payment_conditions_met,合成测试数据\n';
test.beforeEach(async ({ page }) => {
  await login(page);
});

test('业务知识保存、发布与创建新版保留旧版内容', async ({ page }) => {
  await page.getByRole('button', { name: '知识 Wiki', exact: true }).click();
  await page.getByRole('button', { name: '新建知识', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('知识标题').fill('测试供货说明');
  await dialog.getByLabel('正文').fill('第一版：付款后 3 天出库，运输时间未知。');
  await expect(dialog.getByRole('button', { name: '发布版本' })).toBeDisabled();
  await dialog.getByRole('button', { name: '保存草稿' }).click();
  await expect(dialog.getByRole('button', { name: '发布版本' })).toBeEnabled();
  await dialog.getByRole('button', { name: '发布版本' }).click();
  await expect(dialog.locator('.status-published')).toBeVisible();
  await expect(dialog.locator('.knowledge-content')).toContainText('第一版');
  await dialog.getByRole('button', { name: '创建新版本' }).click();
  await expect(dialog.locator('.status-draft')).toBeVisible();
  await dialog.getByLabel('正文').fill('第二版：出库前需再次确认库存。');
  await dialog.getByRole('button', { name: '保存草稿' }).click();
  await expect(dialog.getByRole('button', { name: '保存草稿' })).toBeDisabled();
  await dialog.getByRole('button', { name: '关闭弹窗' }).click();
  await expect(page.locator('.source-row').filter({ hasText: '测试供货说明' })).toHaveCount(2);
  await page
    .locator('.source-row')
    .filter({ hasText: '测试供货说明' })
    .filter({ hasText: '已发布' })
    .click();
  await expect(page.getByRole('dialog').locator('.knowledge-content')).toContainText(
    '第一版：付款后 3 天出库',
  );
  await expect(page.getByRole('dialog').locator('.knowledge-content')).not.toContainText('第二版');
});

test('CSV 错误可定位且禁止发布，修正后通过预览再发布', async ({ page }) => {
  await page.getByRole('button', { name: '知识 Wiki', exact: true }).click();
  await page.getByRole('button', { name: '商品目录', exact: true }).click();
  await page.getByRole('button', { name: '导入商品 CSV', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('商品 CSV 文件').setInputFiles({
    name: 'invalid.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(csvHeader + csvRow.replace(',180,USD,', ',-20,USD,')),
  });
  await dialog.getByRole('button', { name: '上传并校验' }).click();
  await expect(dialog.locator('.import-errors')).toContainText('unitPriceMinor');
  await expect(dialog.getByRole('button', { name: '确认发布' })).toBeDisabled();
  await dialog.getByLabel('商品 CSV 文件').setInputFiles({
    name: 'valid.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(csvHeader + csvRow),
  });
  await dialog.getByRole('button', { name: '上传并校验' }).click();
  await expect(dialog.locator('.import-preview-heading')).toContainText('0 处错误');
  await dialog.getByRole('button', { name: '确认发布' }).click();
  await expect(dialog.getByText('此批次已发布，新运行可查询已发布商品版本。')).toBeVisible();
  await dialog.getByRole('button', { name: '完成', exact: true }).click();
  await expect(page.locator('.source-row').filter({ hasText: '测试商品导入' })).toBeVisible();
});

test('上传图片的固定版本支持授权预览和下载', async ({ page }) => {
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByRole('button', { name: '上传素材', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6sZsAAAAASUVORK5CYII=',
    'base64',
  );
  await dialog
    .getByLabel('文件', { exact: true })
    .setInputFiles({ name: 'qa-image.png', mimeType: 'image/png', buffer: png });
  await dialog.getByLabel('素材名称', { exact: true }).fill('测试商品照片');
  await dialog.getByLabel('适用 SKU', { exact: false }).fill('BAG-STOCK');
  await dialog.getByLabel('资料来源与用途').fill('UI 回归测试生成，用于验证文件流程。');
  await dialog.getByRole('button', { name: '上传素材', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.locator('.asset-card').filter({ hasText: '测试商品照片' }).click();
  await page.getByRole('dialog').getByRole('button', { name: '加载文件预览' }).click();
  await expect(page.getByRole('img', { name: '测试商品照片' })).toBeVisible();
  await expect
    .poll(() =>
      page
        .getByRole('img', { name: '测试商品照片' })
        .evaluate((e: HTMLImageElement) => e.naturalWidth),
    )
    .toBe(1);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 V1', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('qa-image.png');
  expect(await download.failure()).toBeNull();
});

test('停用必需能力阻止运行，用户输入保留', async ({ page }) => {
  await page.getByRole('button', { name: '能力目录', exact: true }).click();
  const toggle = page.getByRole('switch', { name: '报价计算开关' });
  await expect(toggle).toBeChecked();
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await page.locator('.tab-bar').getByRole('button', { name: '工作台', exact: true }).click();
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await page.getByLabel(/补充要求或客户反馈/).fill('改为600件，请更新报价');
  await page.getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('必需能力已停用');
  await expect(page.getByLabel(/补充要求或客户反馈/)).toHaveValue('改为600件，请更新报价');
  await expect(page.getByRole('button', { name: '版本记录 V2', exact: true })).toBeVisible();
});

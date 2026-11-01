import { readFile } from 'node:fs/promises';
import { test, expect, type Page } from '@playwright/test';

const current = (page: Page) => page.locator('.inquiry-mount:not([hidden])');
const inquiryFolder = (page: Page, title = '墨西哥帆布袋试单') =>
  page.getByRole('button', { name: `询盘文件夹 ${title}`, exact: true });

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('直接进入资产库可查看各询盘分类、完整来源、双语回复和版本快照', async ({ page }) => {
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await inquiryFolder(page).click();
  const categories = page.getByLabel('墨西哥帆布袋试单资料分类');
  await expect(categories.getByRole('button')).toHaveText([
    '客户询盘2',
    '需求与方案3',
    '客户回复1',
    '资料与附件3',
    '工作笔记0',
    '版本记录2',
  ]);
  await categories.getByRole('button', { name: '资料与附件' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(3);
  await page.getByRole('button', { name: '预览 现货帆布袋 · 商品资料.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('SKU BAG-STOCK；MOQ 100 件；库存 800 件');
  await page.keyboard.press('Escape');
  await categories.getByRole('button', { name: '客户回复' }).click();
  await page.getByRole('button', { name: '预览 双语回复草稿 · V2.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('English');
  await expect(page.getByRole('dialog')).toContainText('Español · México');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  const download = await downloadPromise;
  expect(await readFile((await download.path())!, 'utf8')).toContain('USD 540.00');
  await page.keyboard.press('Escape');
  await categories.getByRole('button', { name: '版本记录' }).click();
  await page.getByRole('button', { name: '预览 V2 · 当前版本.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('内容核对');
  await page.getByRole('link', { name: '返回询盘：墨西哥帆布袋试单', exact: true }).click();
  await expect(current(page).getByRole('tab', { name: '询盘画板', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByLabel('资产空间').getByRole('button', { name: '公司资产库' }).click();
  await expect(inquiryFolder(page)).toHaveCount(0);
  await expect(page.locator('.library-asset-card')).toHaveCount(8);
});

test('笔记、分类、草稿和附件自动归档，修改与刷新不重复且不同询盘隔离', async ({ page }) => {
  await page.goto('/inquiries/inq_mx026');
  let work = current(page);
  await work
    .locator('.ic-directory')
    .getByRole('button', { name: '客户需求与规格', exact: true })
    .press('Enter');
  await work.getByLabel('需求规格', { exact: true }).fill('客户确认需要牛皮纸包装。');
  await work.getByLabel('新建资料', { exact: true }).click();
  await work.getByRole('button', { name: '新建文件夹', exact: true }).click();
  await page.getByLabel('文件夹名称', { exact: true }).fill('客户包装');
  await page.getByRole('button', { name: '创建文件夹', exact: true }).click();
  await work.getByLabel('新建资料', { exact: true }).click();
  await work.getByRole('button', { name: '新建笔记', exact: true }).click();
  await work.getByLabel('笔记标题', { exact: true }).fill('包装跟进');
  await work.getByLabel('编辑工作笔记', { exact: true }).fill('周一确认牛皮纸包装。');
  await work.getByLabel('笔记所在文件夹', { exact: true }).selectOption({ label: '客户包装' });
  await work.locator('input[type="file"]').setInputFiles([
    {
      name: '客户要求.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('必须使用牛皮纸，不要塑料。'),
    },
    {
      name: '包装参考.png',
      mimeType: 'image/png',
      buffer: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6sZsAAAAASUVORK5CYII=',
        'base64',
      ),
    },
  ]);
  await expect(work.locator('.ic-directory')).toContainText('资料与附件5');
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await inquiryFolder(page).click();
  let categories = page.getByLabel('墨西哥帆布袋试单资料分类');
  await categories.getByRole('button', { name: '客户包装' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(1);
  await page.getByRole('button', { name: '预览 包装跟进.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('周一确认牛皮纸包装。');
  await page.getByRole('link', { name: '返回询盘：墨西哥帆布袋试单', exact: true }).click();
  work = current(page);
  const packagingFolder = work
    .locator('.ic-directory')
    .getByRole('button', { name: '客户包装', exact: false });
  if ((await packagingFolder.getAttribute('aria-expanded')) === 'false')
    await packagingFolder.click();
  await work
    .locator('.ic-directory')
    .getByRole('button', { name: '包装跟进', exact: true })
    .press('Enter');
  await work.getByLabel('编辑工作笔记', { exact: true }).fill('已确认牛皮纸包装，周三寄样。');
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await inquiryFolder(page).click();
  categories = page.getByLabel('墨西哥帆布袋试单资料分类');
  await categories.getByRole('button', { name: '客户包装' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(1);
  await page.getByRole('button', { name: '预览 包装跟进.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('已确认牛皮纸包装，周三寄样。');
  await page.keyboard.press('Escape');
  await categories.getByRole('button', { name: '需求与方案' }).click();
  await page.getByRole('button', { name: '预览 客户需求与规格 · V2.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('客户确认需要牛皮纸包装。');
  await page.keyboard.press('Escape');
  await page.reload();
  await inquiryFolder(page).click();
  categories = page.getByLabel('墨西哥帆布袋试单资料分类');
  await categories.getByRole('button', { name: '资料与附件' }).click();
  await page.getByRole('button', { name: '预览 客户要求.txt', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('必须使用牛皮纸，不要塑料。');
  const downloading = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  const download = await downloading;
  expect(await readFile((await download.path())!, 'utf8')).toBe('必须使用牛皮纸，不要塑料。');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '预览 包装参考.png', exact: true }).click();
  await expect
    .poll(() =>
      page
        .getByRole('dialog')
        .getByRole('img', { name: '包装参考.png' })
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBe(1);
  await page.keyboard.press('Escape');
  await inquiryFolder(page, '德国陶瓷杯采购询盘').click();
  await expect(page.getByRole('button', { name: '预览 包装跟进.md', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '预览 客户要求.txt', exact: true })).toHaveCount(0);
});

test('保存后的双语回复及时同步，手机上询盘分类和文档预览不溢出', async ({ page }) => {
  await page.goto('/inquiries/inq_mx026');
  const work = current(page);
  await work
    .locator('.ic-directory')
    .getByRole('button', { name: '双语回复草稿', exact: true })
    .press('Enter');
  await work
    .getByLabel('English 回复草稿')
    .fill('Confirmed kraft packaging. Shipment timing still needs confirmation.');
  await work.getByRole('button', { name: 'Español · México', exact: true }).click();
  await work
    .getByLabel('Español · México 回复草稿')
    .fill('Embalaje de papel confirmado. El transporte sigue pendiente.');
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await inquiryFolder(page).click();
  await page
    .getByLabel('墨西哥帆布袋试单资料分类')
    .getByRole('button', { name: '客户回复' })
    .click();
  await page.getByRole('button', { name: '预览 双语回复草稿 · V2.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Confirmed kraft packaging.');
  await expect(page.getByRole('dialog')).toContainText('Embalaje de papel confirmado.');
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole('button', { name: '文件夹 · 墨西哥帆布袋试单 / 客户回复', exact: true })
    .click();
  await page
    .getByLabel('墨西哥帆布袋试单资料分类')
    .getByRole('button', { name: '需求与方案' })
    .click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '预览 客户需求与规格 · V2.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('墨西哥帆布袋试单');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

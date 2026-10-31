import { test, expect, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  await login(page);
});

test('Wiki 按目录和正文搜索，阅读、原文与下载内容一致', async ({ page }) => {
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await expect(page.locator('.wiki-row')).toHaveCount(8);
  await page.getByLabel('知识目录').getByRole('button', { name: '业务流程' }).click();
  await expect(page.locator('.wiki-row')).toHaveCount(2);
  await page.getByRole('textbox', { name: '搜索文档或正文' }).fill('出库时间不等于到货时间');
  await expect(page.locator('.wiki-row')).toHaveCount(1);
  await page.locator('.wiki-document').click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.locator('.wiki-markdown strong').first()).toHaveText(
    '出库时间不等于到货时间。',
  );
  await dialog.getByRole('button', { name: '原文', exact: true }).click();
  await expect(dialog.locator('.wiki-source')).toContainText('# 交付与承诺规则');
  const downloading = page.waitForEvent('download');
  await dialog.getByRole('button', { name: '下载文档' }).click();
  const file = await downloading;
  expect(file.suggestedFilename()).toBe('交付与承诺规则.md');
  expect(await file.failure()).toBeNull();
  await page.keyboard.press('Escape');
  await page.getByRole('textbox', { name: '搜索文档或正文' }).fill('不存在的内容');
  await expect(page.getByText('没有找到相关文档')).toBeVisible();
  await page.getByRole('button', { name: '重置筛选' }).click();
  await expect(page.locator('.wiki-row')).toHaveCount(8);
});

test('Wiki 收藏、新建和导入只作用于当前静态页面', async ({ page }) => {
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '收藏 交付与承诺规则', exact: true }).click();
  await page.getByLabel('知识目录').getByRole('button', { name: '我的收藏' }).click();
  await expect(page.locator('.wiki-row')).toHaveCount(4);
  await page.getByRole('button', { name: '新建文档' }).click();
  let dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: '创建文档' })).toBeDisabled();
  await dialog.getByLabel('文档名称').fill('测试知识');
  await dialog.getByLabel('Markdown 正文').fill('# 测试知识\n\n## 清单\n\n- 一条记录');
  await dialog.getByLabel('所属目录').selectOption('团队协作');
  await dialog.getByRole('button', { name: '创建文档' }).click();
  await expect(page.locator('.wiki-row').filter({ hasText: '测试知识' })).toBeVisible();
  await page.getByRole('button', { name: '导入 Markdown', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Markdown 文件').setInputFiles({
    name: 'invalid.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('invalid'),
  });
  await expect(dialog.getByRole('alert')).toContainText('.md');
  await expect(dialog.getByRole('button', { name: '添加', exact: true })).toBeDisabled();
  await dialog.getByLabel('Markdown 文件').setInputFiles({
    name: '导入文档.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 导入文档\n\n<script>alert(1)</script>'),
  });
  await dialog.getByRole('button', { name: '添加 1 个文件' }).click();
  await page.locator('.wiki-document').filter({ hasText: '导入文档' }).click();
  await expect(page.getByRole('dialog').locator('.wiki-markdown')).toContainText(
    '<script>alert(1)</script>',
  );
  await expect(page.getByRole('dialog').locator('script')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await page.reload();
  await expect(page.locator('.wiki-row')).toHaveCount(8);
  await expect(page.locator('.wiki-row').filter({ hasText: '测试知识' })).toHaveCount(0);
});

test('资产按公司和个人隔离，目录、类型、收藏和视图联动', async ({ page }) => {
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(8);
  await page.getByLabel('文件类型').getByRole('button', { name: '视频', exact: true }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(1);
  await page.getByRole('button', { name: '预览 帆布袋工艺展示.mp4' }).click();
  await expect(page.getByRole('dialog').getByText('示例视频封面')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('textbox', { name: '搜索文件' }).fill('不存在');
  await expect(page.getByText('没有找到相关文件')).toBeVisible();
  await page.getByLabel('资产空间').getByRole('button', { name: '个人资产库' }).click();
  await expect(page.getByRole('textbox', { name: '搜索文件' })).toHaveValue('');
  await expect(page.locator('.library-asset-card')).toHaveCount(4);
  await page.getByRole('button', { name: '列表视图' }).click();
  await expect(page.locator('.library-asset-list .library-asset-card')).toHaveCount(4);
  await page.getByRole('button', { name: '收藏', exact: true }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(1);
  await page.getByRole('button', { name: '预览 客户报价对比.xlsx' }).click();
  await expect(page.getByRole('dialog').locator('table')).toContainText('$2.40');
  await page.keyboard.press('Escape');
  await page.getByLabel('资产空间').getByRole('button', { name: '公司资产库' }).click();
  await page.getByLabel('资产文件夹').getByRole('button', { name: '品牌文件' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(3);
  await page.getByRole('button', { name: '返回全部文件' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(8);
});

test('添加图片和任意文件到个人空间，可预览与下载且公司空间不受影响', async ({ page }) => {
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByLabel('资产空间').getByRole('button', { name: '个人资产库' }).click();
  await page.getByRole('button', { name: '添加文件', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('个人资产库 / 未分类');
  await dialog.getByLabel('资产文件').setInputFiles([
    {
      name: 'qa-image.png',
      mimeType: 'image/png',
      buffer: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6sZsAAAAASUVORK5CYII=',
        'base64',
      ),
    },
    {
      name: '设计文件.fig',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('test file'),
    },
  ]);
  await dialog.getByRole('button', { name: '添加 2 个文件' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(6);
  await page.getByRole('button', { name: '预览 qa-image.png' }).click();
  await expect
    .poll(() =>
      page
        .getByRole('dialog')
        .getByRole('img', { name: 'qa-image.png' })
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBe(1);
  const downloading = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  const file = await downloading;
  expect(file.suggestedFilename()).toBe('qa-image.png');
  expect(await file.failure()).toBeNull();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '预览 设计文件.fig' }).click();
  await expect(page.getByRole('dialog')).toContainText('此格式暂不支持在线预览');
  await page.keyboard.press('Escape');
  await page.getByLabel('资产空间').getByRole('button', { name: '公司资产库' }).click();
  await expect(page.locator('.library-asset-card')).toHaveCount(8);
  await expect(page.getByRole('button', { name: '预览 qa-image.png' })).toHaveCount(0);
});

test('移动端与深色下目录、弹窗、视图切换没有页面横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('combobox', { name: '外观主题' }).selectOption('dark');
  await page.getByRole('button', { name: '打开导航' }).click();
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await expect(page.locator('.wiki-layout')).toHaveCSS('background-color', 'rgb(25, 27, 32)');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('.wiki-document').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '打开导航' }).click();
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '列表视图' }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('停用必需能力阻止运行，用户输入保留', async ({ page }) => {
  // 技能市场仅展示静态内容，直接准备后端能力停用场景。
  await page.evaluate(async () => {
    const url = '/src/api/index.ts';
    const { api } = await import(url);
    const { items } = await api.get('/workspaces/ws_demo/capabilities');
    const quote = items.find((item: { name: string }) => item.name === '报价计算');
    await api.patch(`/workspaces/ws_demo/capabilities/${quote.id}`, { enabled: false });
  });
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('button', { name: '工作台', exact: true })
    .click();
  await page.goto('/inquiries');
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

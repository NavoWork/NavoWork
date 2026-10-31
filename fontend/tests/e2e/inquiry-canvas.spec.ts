import { test, expect, type Page, type Locator } from '@playwright/test';

const current = (page: Page) => page.locator('.inquiry-mount:not([hidden])');
async function openInquiry(page: Page, id = 'inq_mx026') {
  await page.goto(`/inquiries/${id}`);
  await expect(current(page).locator('.react-flow__node')).not.toHaveCount(0);
}
const paneWidth = async (pane: Locator) => (await pane.boundingBox())!.width;
async function dragDivider(page: Page, divider: Locator, delta: number) {
  const box = (await divider.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + delta, y, { steps: 10 });
  await page.mouse.up();
}
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('画板只预览，双击打开唯一标签，编辑草稿同步预览并可恢复', async ({ page }) => {
  await openInquiry(page);
  const work = current(page);
  const node = work.locator('.react-flow__node[data-id="original"]');
  await node.click();
  await expect(work.getByLabel('编辑客户原始询盘')).toBeHidden();
  await node.dblclick();
  await expect(work.getByRole('tab', { name: '客户原始询盘', exact: true })).toBeVisible();
  await expect(work.getByLabel('编辑客户原始询盘')).toHaveAttribute('readonly', '');
  const directoryItem = work
    .locator('.ic-directory')
    .getByRole('button', { name: '客户需求与规格', exact: true });
  await directoryItem.dblclick();
  const field = work.getByLabel('编辑客户需求与规格');
  const text = `${await field.inputValue()}\n客户确认杯口尺寸需复核。`;
  await field.fill(text);
  await work.getByRole('tab', { name: '询盘画板', exact: true }).click();
  await expect(work.locator('.ic-card-requirements')).toContainText('客户确认杯口尺寸需复核');
  await directoryItem.dblclick();
  await expect(work.getByRole('tab', { name: '客户需求与规格', exact: true })).toHaveCount(1);
  await work.getByRole('button', { name: '关闭资料标签 客户需求与规格', exact: true }).click();
  await directoryItem.press('Enter');
  await expect(field).toHaveValue(text);
  await field.fill('请重新核对定制规格和最终数量。');
  await work.getByRole('button', { name: '交给助手更新版本', exact: true }).click();
  await expect(work.getByRole('heading', { name: 'AI 对话', exact: true })).toBeVisible();
  await expect(work.getByLabel('补充要求或客户反馈')).toHaveValue(/请重新核对定制规格和最终数量/);
});

test('文件夹与笔记保存、刷新恢复，并按当前询盘隔离', async ({ page }) => {
  await openInquiry(page);
  let work = current(page);
  await work.getByLabel('新建资料', { exact: true }).click();
  await work.getByRole('button', { name: '新建文件夹', exact: true }).click();
  await page.getByLabel('文件夹名称', { exact: true }).fill('供应商跟进');
  await page.getByRole('button', { name: '创建文件夹', exact: true }).click();
  await work.getByLabel('新建资料', { exact: true }).click();
  await work.getByRole('button', { name: '新建笔记', exact: true }).click();
  await work.getByLabel('笔记标题', { exact: true }).fill('客户包装偏好');
  await work.getByLabel('编辑工作笔记', { exact: true }).fill('周一确认牛皮纸包装，避免塑料。');
  await work.getByLabel('笔记所在文件夹', { exact: true }).selectOption({ label: '供应商跟进' });
  await page.reload();
  work = current(page);
  await expect(work.getByLabel('编辑工作笔记')).toHaveValue('周一确认牛皮纸包装，避免塑料。');
  await expect(work.getByLabel('笔记所在文件夹')).toHaveValue(/folder:/);
  await work.getByRole('tab', { name: '询盘画板', exact: true }).click();
  await expect(work.locator('.ic-card-note')).toContainText('客户包装偏好');
  await openInquiry(page, 'inq_de014');
  await expect(current(page).locator('.ic-directory')).not.toContainText('客户包装偏好');
});

test('原始询盘在首次处理前通过接口保存，预览和刷新一致', async ({ page }) => {
  await openInquiry(page, 'inq_de014');
  const work = current(page);
  await work.locator('.react-flow__node[data-id="original"]').dblclick();
  const text = 'Please quote 650 matte ceramic cups, with kraft packaging, delivered to Hamburg.';
  await work.getByLabel('编辑客户原始询盘').fill(text);
  await work.getByRole('button', { name: '保存原文', exact: true }).click();
  await expect(work.getByText('原文已保存', { exact: true })).toBeVisible();
  await work.getByRole('tab', { name: '询盘画板', exact: true }).click();
  await expect(work.locator('.ic-card-original')).toContainText(text);
  await page.reload();
  await expect(current(page).locator('.ic-card-original')).toContainText(text);
});

test('回复在标签页保存，返回画板预览当前草稿，关闭标签后继续保存', async ({ page }) => {
  await openInquiry(page);
  const work = current(page);
  await work
    .locator('.ic-directory')
    .getByRole('button', { name: '双语回复草稿', exact: true })
    .press('Enter');
  const field = work.getByLabel('English 回复草稿');
  await expect(field).toBeVisible();
  const text = `Updated packing details.\n${await field.inputValue()}`;
  await field.fill(text);
  await work.getByRole('button', { name: '关闭资料标签 双语回复草稿', exact: true }).click();
  await expect(work.locator('.ic-card-reply')).toContainText('Updated packing details.');
  await expect(work.locator('.iw-draft-status')).toContainText('已保存 · 草稿 V2');
  await page.reload();
  await expect(current(page).locator('.ic-card-reply')).toContainText('Updated packing details.');
});

test('文件导入后画板预览图片，双击标签预览原文件，刷新恢复文件内容', async ({ page }) => {
  await openInquiry(page);
  let work = current(page);
  await work.getByLabel('导入询盘文件').setInputFiles({
    name: '包装参考.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=',
      'base64',
    ),
  });
  await expect(work.locator('.ic-card-file img')).toBeAttached();
  await work
    .locator('.ic-directory')
    .getByRole('button', { name: '包装参考.png', exact: true })
    .press('Enter');
  await expect(work.locator('.ic-full-image')).toBeVisible();
  await expect(work.getByRole('link', { name: '下载原文件' })).toHaveAttribute(
    'download',
    '包装参考.png',
  );
  await work.getByLabel('附件显示名称').fill('客户包装参考');
  await page.reload();
  work = current(page);
  await expect(work.getByRole('heading', { name: '客户包装参考', exact: true })).toBeVisible();
  await expect(work.locator('.ic-full-image')).toBeVisible();
});

test('两条边界可拖拽，刷新与收起后保留宽度，双击恢复默认', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await openInquiry(page);
  const work = current(page);
  const directory = work.locator('.ic-directory');
  const assistant = work.locator('.iw-assistant');
  const directoryDivider = work.getByRole('separator', { name: '调整文件目录宽度' });
  const assistantDivider = work.getByRole('separator', { name: '调整 AI 面板宽度' });
  const directoryDefault = await paneWidth(directory);
  const assistantDefault = await paneWidth(assistant);

  await dragDivider(page, directoryDivider, 70);
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault + 70, 0);
  await dragDivider(page, assistantDivider, -90);
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantDefault + 90, 0);
  const assistantSaved = await paneWidth(assistant);
  await page.reload();
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault + 70, 0);
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantSaved, 0);

  await work.getByRole('button', { name: '收起文件目录', exact: true }).click();
  await expect(directoryDivider).toBeHidden();
  await work.getByRole('button', { name: '展开文件目录', exact: true }).click();
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault + 70, 0);
  await work.getByRole('button', { name: '收起 AI 面板', exact: true }).click();
  await expect(assistantDivider).toBeHidden();
  await work.getByRole('button', { name: '展开 AI 面板', exact: true }).click();
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantSaved, 0);

  await openInquiry(page, 'inq_de014');
  await expect
    .poll(() => paneWidth(current(page).locator('.ic-directory')))
    .toBeCloseTo(directoryDefault, 0);
  await expect
    .poll(() => paneWidth(current(page).locator('.iw-assistant')))
    .toBeCloseTo(assistantDefault, 0);
  await openInquiry(page);
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault + 70, 0);
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantSaved, 0);
  await directoryDivider.dblclick();
  await assistantDivider.dblclick();
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault, 0);
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantDefault, 0);
  await expect(page.locator('html')).not.toHaveClass(/nw-resizing-panels/);
});

test('目录缩到最小后继续左拖收起，再展开恢复拖拽前宽度', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await openInquiry(page);
  const work = current(page);
  const directory = work.locator('.ic-directory');
  const divider = work.getByRole('separator', { name: '调整文件目录宽度' });
  const assistantWidth = await paneWidth(work.locator('.iw-assistant'));
  await dragDivider(page, divider, 60);
  const expandedWidth = await paneWidth(directory);
  const boardWidth = await paneWidth(work.locator('.ic-main'));
  const box = (await divider.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - (expandedWidth - 120), y, { steps: 8 });
  await expect(directory).toBeVisible();
  await expect.poll(() => paneWidth(directory)).toBe(140);
  await page.mouse.move(x - (expandedWidth - 90), y, { steps: 4 });
  await page.mouse.up();
  await expect(directory).toBeHidden();
  await expect(divider).toBeHidden();
  await expect(page.locator('html')).not.toHaveClass(/nw-resizing-panels/);
  const expand = work.getByRole('button', { name: '展开文件目录', exact: true });
  await expect(expand).toBeFocused();
  await expect(expand).toHaveAttribute('aria-expanded', 'false');
  await expect
    .poll(() => paneWidth(work.locator('.ic-main')))
    .toBeCloseTo(boardWidth + expandedWidth + 8, 0);
  await expect.poll(() => paneWidth(work.locator('.iw-assistant'))).toBeCloseTo(assistantWidth, 0);
  await expand.click();
  await expect(directory).toBeVisible();
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(expandedWidth, 0);
  await page.reload();
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(expandedWidth, 0);
});

test('分隔线支持键盘调整，极限宽度和窗口缩小不会挤掉主区域', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await openInquiry(page);
  const work = current(page);
  const directory = work.locator('.ic-directory');
  const assistant = work.locator('.iw-assistant');
  const directoryDivider = work.getByRole('separator', { name: '调整文件目录宽度' });
  const assistantDivider = work.getByRole('separator', { name: '调整 AI 面板宽度' });
  const directoryDefault = await paneWidth(directory);
  const assistantDefault = await paneWidth(assistant);
  await directoryDivider.press('ArrowRight');
  await expect.poll(() => paneWidth(directory)).toBeCloseTo(directoryDefault + 16, 0);
  await assistantDivider.press('Shift+ArrowLeft');
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantDefault + 40, 0);
  await directoryDivider.press('Home');
  await assistantDivider.press('Home');
  await expect.poll(() => paneWidth(directory)).toBe(140);
  await expect.poll(() => paneWidth(assistant)).toBe(280);
  await directoryDivider.press('End');
  await assistantDivider.press('End');
  await expect.poll(() => paneWidth(assistant)).toBeLessThanOrEqual(720);
  await expect.poll(() => paneWidth(directory)).toBeLessThanOrEqual(360);
  await page.setViewportSize({ width: 1000, height: 900 });
  await expect.poll(() => paneWidth(work.locator('.iw-data-pane'))).toBeGreaterThanOrEqual(380);
  await expect.poll(() => paneWidth(work.locator('.ic-main'))).toBeGreaterThanOrEqual(220);
  await expect.poll(() => paneWidth(assistant)).toBeGreaterThanOrEqual(280);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await directoryDivider.press('Enter');
  await assistantDivider.press('Enter');
  await expect.poll(() => paneWidth(directory)).toBe(172);
  await page.setViewportSize({ width: 1512, height: 982 });
  await expect.poll(() => paneWidth(assistant)).toBeCloseTo(assistantDefault, 0);
});

test('节点拖拽与缩放刷新恢复，深色及手机布局可用', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await openInquiry(page);
  let work = current(page);
  const node = work.locator('.react-flow__node[data-id="original"]');
  const before = await node.boundingBox();
  await page.mouse.move(before!.x + 75, before!.y + 45);
  await page.mouse.down();
  await page.mouse.move(before!.x + 120, before!.y + 85, { steps: 8 });
  await page.mouse.up();
  await work.locator('.react-flow__controls-zoomin').click();
  const transform = await node.getAttribute('style');
  await page.reload();
  work = current(page);
  await expect(work.locator('.react-flow__node[data-id="original"]')).toHaveAttribute(
    'style',
    transform!,
  );
  await page.screenshot({ path: 'docs/screenshots/inquiry-canvas-desktop.png', fullPage: true });
  await page.getByLabel('外观主题').selectOption('dark');
  await page.screenshot({ path: 'docs/screenshots/inquiry-canvas-dark.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(current(page).getByRole('tab', { name: '询盘画板', exact: true })).toBeVisible();
  await expect(current(page).getByRole('separator', { name: '调整文件目录宽度' })).toBeHidden();
  await expect(current(page).getByRole('separator', { name: '调整 AI 面板宽度' })).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: 'docs/screenshots/inquiry-canvas-mobile.png', fullPage: true });
});

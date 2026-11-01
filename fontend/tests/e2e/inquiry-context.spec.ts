import { test, expect, type Page } from '@playwright/test';
import type { Message, Revision, Run } from '../../src/api/types';

const work = (page: Page) => page.locator('.inquiry-mount:not([hidden])');
const composer = (page: Page) => work(page).locator('.iw-context-composer');
const input = (page: Page) => composer(page).getByLabel('补充要求或客户反馈');
async function open(page: Page, id = 'inq_mx026') {
  await page.goto(`/inquiries/${id}`);
  await expect(input(page)).toBeEnabled();
}
async function get<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (path) => {
    const url = '/src/api/index.ts';
    const { api } = await import(url);
    return api.get(path);
  }, path) as Promise<T>;
}
async function selectContext(page: Page) {
  await composer(page).getByRole('button', { name: '选择技能', exact: true }).click();
  await composer(page).getByRole('option', { name: '回复质量检查', exact: true }).click();
  await composer(page).getByRole('button', { name: '引用知识库', exact: true }).click();
  await composer(page).getByRole('option', { name: '交付与承诺规则', exact: true }).click();
}
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('快捷输入、键盘选择和移除保留正文，Esc 关闭，中文输入与换行不发送', async ({ page }) => {
  await open(page, 'inq_de014');
  await input(page).fill('请核对 /reply-review');
  await expect(composer(page).getByRole('dialog', { name: '选择技能' })).toBeVisible();
  await expect(composer(page).getByRole('option')).toHaveCount(1);
  await input(page).press('Enter');
  await expect(input(page)).toHaveValue('请核对 ');
  await expect(composer(page).getByLabel('移除技能 回复质量检查', { exact: true })).toBeVisible();
  await input(page).fill('请核对 @出库时间不等于到货时间');
  await input(page).press('ArrowDown');
  await input(page).press('Enter');
  await expect(input(page)).toHaveValue('请核对 ');
  await expect(composer(page).getByLabel('移除知识 交付与承诺规则', { exact: true })).toBeVisible();
  await composer(page).getByLabel('移除技能 回复质量检查', { exact: true }).click();
  await expect(composer(page).getByLabel('移除技能 回复质量检查', { exact: true })).toHaveCount(0);
  await expect(input(page)).toHaveValue('请核对 ');
  await input(page).fill('/找不到的技能');
  await input(page).press('Enter');
  await expect(composer(page).getByRole('status')).toContainText('没有找到匹配内容');
  await input(page).press('Escape');
  await expect(composer(page).getByRole('dialog')).toHaveCount(0);
  await input(page).press('ArrowRight');
  await expect(composer(page).getByRole('dialog')).toHaveCount(0);
  await input(page).fill('请核对规格');
  await input(page).press('End');
  await input(page).press('Shift+Enter');
  await expect(input(page)).toHaveValue('请核对规格\n');
  await input(page).dispatchEvent('keydown', { key: 'Enter', isComposing: true });
  await expect(input(page)).toHaveValue('请核对规格\n');
  await expect(work(page).getByRole('region', { name: 'AI 处理进度' })).toHaveCount(0);
});

test('选择按询盘保存，发送后消息、运行和版本保留快照，刷新后仍可回看', async ({ page }) => {
  await open(page);
  await selectContext(page);
  await input(page).fill('核对600件报价和交期');
  await page.reload();
  await expect(input(page)).toHaveValue('核对600件报价和交期');
  await expect(composer(page).getByLabel('移除知识 交付与承诺规则', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 960 });
  await composer(page).getByRole('button', { name: '选择技能', exact: true }).click();
  await page.screenshot({ path: '../tmp/inquiry-context-desktop.png' });
  await composer(page).getByLabel('关闭选择器', { exact: true }).click();
  await open(page, 'inq_de014');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(0);
  await expect(input(page)).toHaveValue('');
  await open(page);
  await work(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(work(page).locator('.iw-message.user').last()).toContainText('回复质量检查');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(0);
  await expect(input(page)).toHaveValue('');
  await expect(work(page).getByRole('region', { name: 'V3 本轮成果', exact: true })).toBeVisible({
    timeout: 15000,
  });
  const messages = await get<{ items: Message[] }>(
    page,
    '/workspaces/ws_demo/inquiries/inq_mx026/messages',
  );
  const message = messages.items.find((message) => message.text === '核对600件报价和交期')!;
  expect(message.context?.skills[0].id).toBe('reply-review');
  expect(message.context?.knowledge[0].content).toContain('出库时间不等于到货时间');
  const run = await get<Run>(page, `/workspaces/ws_demo/runs/${message.runId}`);
  const revision = await get<Revision>(page, '/workspaces/ws_demo/inquiries/inq_mx026/revisions/3');
  expect(run.context).toEqual(message.context);
  expect(revision.context).toEqual(message.context);
  await page.reload();
  const saved = work(page).locator('.iw-message.user').last();
  await saved.getByText('交付与承诺规则', { exact: true }).click();
  await expect(saved.locator('pre')).toContainText('出库时间不等于到货时间');
  await work(page).getByText('运行详情', { exact: true }).click();
  await expect(work(page).locator('.iw-run-details')).toContainText('回复质量检查');
});

test('本机存储失败时保留输入与选择并提示，恢复后可以重新暂存', async ({ page }) => {
  await open(page);
  await selectContext(page);
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Object.assign(window, {
      restoreContextStorage: () => {
        Storage.prototype.setItem = original;
      },
    });
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith('easywork:view:'))
        throw new DOMException('Storage full', 'QuotaExceededError');
      original.call(this, key, value);
    };
  });
  await input(page).fill('需要保留的草稿');
  await expect(composer(page).getByRole('alert')).toContainText('草稿暂存失败');
  await expect(input(page)).toHaveValue('需要保留的草稿');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(2);
  await expect(composer(page).getByText('草稿已暂存', { exact: true })).toHaveCount(0);
  await page.evaluate(() =>
    (window as unknown as { restoreContextStorage: () => void }).restoreContextStorage(),
  );
  await input(page).fill('需要保留的草稿，存储已恢复');
  await expect(composer(page).getByText('草稿已暂存', { exact: true })).toBeVisible();
  await page.reload();
  await expect(input(page)).toHaveValue('需要保留的草稿，存储已恢复');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(2);
});

test('新建与导入知识可以立即引用，移动端深色选择器保持在视口内', async ({ page }) => {
  await open(page, 'inq_de014');
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档', exact: true }).click();
  await page.getByRole('dialog').getByLabel('文档名称').fill('陶瓷杯验收标准');
  await page
    .getByRole('dialog')
    .getByLabel('Markdown 正文')
    .fill('# 陶瓷杯验收标准\n\n每批抽检20件，检查杯口和釉面。');
  await page.getByRole('dialog').getByRole('button', { name: '创建文档', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: '导入 Markdown', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByLabel('Markdown 文件')
    .setInputFiles({
      name: '包装规则.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# 包装规则\n\n杯子需独立防震包装。'),
    });
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '添加 1 个文件', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await open(page, 'inq_de014');
  await input(page).fill('@釉面');
  await expect(
    composer(page).getByRole('option', { name: '陶瓷杯验收标准', exact: true }),
  ).toBeVisible();
  await input(page).press('Enter');
  await expect(composer(page).getByLabel('移除知识 陶瓷杯验收标准', { exact: true })).toBeVisible();
  await input(page).fill('@防震');
  await input(page).press('Enter');
  await expect(composer(page).getByLabel('移除知识 包装规则', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('combobox', { name: '外观主题' }).selectOption('dark');
  await work(page).getByRole('button', { name: 'AI 助手', exact: true }).click();
  await composer(page).getByRole('button', { name: '引用知识库', exact: true }).click();
  await composer(page).getByRole('textbox', { name: '搜索知识库', exact: true }).fill('包装规则');
  await expect(
    composer(page).getByRole('option', { name: '包装规则', exact: true }),
  ).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const box = await composer(page).getByRole('dialog').boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: '../tmp/inquiry-context-mobile.png' });
});

test('提交失败保留选择，运行失败可以恢复同一份上下文重试', async ({ page }) => {
  await open(page);
  await selectContext(page);
  await input(page).fill('核对600件报价');
  await page.evaluate(async () => {
    const url = '/src/api/index.ts';
    const { api } = await import(url);
    await api.patch('/workspaces/ws_demo/capabilities/calculate', { enabled: false });
  });
  await work(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(work(page).getByRole('alert')).toContainText('必需能力已停用');
  await expect(input(page)).toHaveValue('核对600件报价');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(2);
  await page.evaluate(async () => {
    const url = '/src/api/index.ts';
    const { api, setMockFault } = await import(url);
    await api.patch('/workspaces/ws_demo/capabilities/calculate', { enabled: true });
    setMockFault('run-failure');
  });
  await work(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(work(page).getByRole('button', { name: '恢复指令并重试', exact: true })).toBeEnabled(
    { timeout: 15000 },
  );
  await work(page).getByRole('button', { name: '恢复指令并重试', exact: true }).click();
  await expect(input(page)).toHaveValue('核对600件报价');
  await expect(composer(page).locator('.iw-context-chip')).toHaveCount(2);
  await work(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(work(page).getByRole('region', { name: 'V3 本轮成果', exact: true })).toBeVisible({
    timeout: 15000,
  });
});

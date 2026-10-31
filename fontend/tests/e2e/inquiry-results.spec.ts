import { test, expect, type Page } from '@playwright/test';

const workspace = (page: Page) => page.locator('.inquiry-mount:not([hidden])');
const result = (page: Page, version: number) =>
  workspace(page).getByRole('region', { name: `V${version} 本轮成果`, exact: true });
async function open(page: Page, id = 'inq_mx026') {
  await page.goto(`/inquiries/${id}`);
  await expect(workspace(page).locator('.react-flow__node')).not.toHaveCount(0);
}
async function revise(page: Page, instruction: string, version: number) {
  await workspace(page).getByLabel('补充要求或客户反馈').fill(instruction);
  await workspace(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(result(page, version)).toBeVisible({ timeout: 15000 });
  await expect(
    result(page, version).getByRole('button', { name: '添加到画板', exact: true }),
  ).toBeEnabled();
}
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('移除业务结果标签，旧视图偏好也能直接回到对话', async ({ page }) => {
  await page.evaluate(() =>
    localStorage.setItem(
      'easywork:view:usr_demo:ws_demo:inq_mx026',
      JSON.stringify({ input: '', revision: null, lastRunId: '', rightPane: 'results', tab: 3 }),
    ),
  );
  await open(page);
  await expect(workspace(page).getByRole('tab', { name: '业务结果', exact: true })).toHaveCount(0);
  await expect(workspace(page).getByRole('tablist', { name: 'AI 面板' })).toHaveCount(0);
  await expect(
    workspace(page).getByRole('heading', { name: 'AI 对话', exact: true }),
  ).toBeVisible();
  await expect(result(page, 2)).toContainText('这个答案可以吗');
  await expect(workspace(page).getByLabel('补充要求或客户反馈')).toBeEnabled();
});

test('生成结果经确认只添加一个节点，刷新保留快照和去重，稍后仍能添加', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await open(page);
  const work = workspace(page);
  const before = await work.locator('.react-flow__node').count();
  await revise(page, '改为600件，请更新报价', 3);
  await expect(work.locator('.react-flow__node')).toHaveCount(before);
  await expect(work.locator('.react-flow__node[data-id="result:3"]')).toHaveCount(0);
  const response = work.locator('.iw-message.assistant').last().locator('..');
  await expect(response.getByRole('region', { name: 'V3 本轮成果', exact: true })).toBeVisible();
  await result(page, 3).getByRole('button', { name: '添加到画板', exact: true }).click();
  const node = work.locator('.react-flow__node[data-id="result:3"]');
  await expect(node).toBeVisible();
  await expect(work.locator('.react-flow__node')).toHaveCount(before + 1);
  await expect(
    result(page, 3).getByRole('button', { name: '已添加到画板', exact: true }),
  ).toBeDisabled();
  await node.dblclick();
  await expect(work.locator('.ic-document-panel:not([hidden])')).toContainText('1,080.00');
  await expect(work.locator('.ic-document-panel:not([hidden])')).toContainText('Español');
  await page.reload();
  await expect(work.locator('.ic-document-panel:not([hidden])')).toContainText('1,080.00');
  await expect(
    result(page, 3).getByRole('button', { name: '已添加到画板', exact: true }),
  ).toBeDisabled();
  await revise(page, '改回300件，请更新报价', 4);
  await expect(work.locator('.react-flow__node')).toHaveCount(before + 1);
  await result(page, 4).getByRole('button', { name: '暂不添加', exact: true }).click();
  await expect(result(page, 4)).toContainText('已留在对话中');
  await page.reload();
  await expect(result(page, 4)).toContainText('已留在对话中');
  await expect(work.locator('.react-flow__node[data-id="result:4"]')).toHaveCount(0);
  await work.getByRole('tab', { name: 'V3 · 对话成果', exact: true }).click();
  await expect(work.locator('.ic-document-panel:not([hidden])')).toContainText('1,080.00');
  await result(page, 4).getByRole('button', { name: '添加到画板', exact: true }).click();
  await expect(work.locator('.react-flow__node[data-id="result:4"]')).toBeVisible();
  await expect(work.locator('.react-flow__node')).toHaveCount(before + 2);
  await open(page, 'inq_de014');
  await expect(workspace(page).locator('.ic-card-result')).toHaveCount(0);
});

test('保存失败时不增加节点或显示成功，恢复存储后可重试', async ({ page }) => {
  await open(page);
  const work = workspace(page);
  await expect(
    result(page, 2).getByRole('button', { name: '添加到画板', exact: true }),
  ).toBeEnabled();
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Object.assign(window, {
      restoreCanvasStorage: () => {
        Storage.prototype.setItem = original;
      },
    });
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith('navowork:inquiry-canvas:'))
        throw new DOMException('blocked', 'SecurityError');
      original.call(this, key, value);
    };
  });
  await result(page, 2).getByRole('button', { name: '添加到画板', exact: true }).click();
  await expect(
    work.getByText('成果节点未能保存，请恢复浏览器存储后重试。对话内容已保留。', { exact: true }),
  ).toBeVisible();
  await expect(work.locator('.ic-card-result')).toHaveCount(0);
  await expect(
    result(page, 2).getByRole('button', { name: '添加到画板', exact: true }),
  ).toBeEnabled();
  await page.evaluate(() =>
    (window as unknown as { restoreCanvasStorage: () => void }).restoreCanvasStorage(),
  );
  await result(page, 2).getByRole('button', { name: '添加到画板', exact: true }).click();
  await expect(work.locator('.ic-card-result')).toHaveCount(1);
  await expect(
    result(page, 2).getByRole('button', { name: '已添加到画板', exact: true }),
  ).toBeDisabled();
});

test('失败与取消的回复不提供新的成果或保存入口', async ({ page }) => {
  await open(page);
  await page.getByRole('button', { name: '工作空间设置', exact: true }).click();
  await page.getByLabel('异常场景演示').selectOption('run-failure');
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await workspace(page).getByLabel('补充要求或客户反馈').fill('更新600件报价');
  await workspace(page).getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(workspace(page).locator('.iw-run')).toContainText('模拟模型超时', {
    timeout: 15000,
  });
  await expect(result(page, 3)).toHaveCount(0);
  await expect(
    workspace(page)
      .locator('.iw-message.assistant')
      .last()
      .locator('..')
      .locator('.iw-answer-result'),
  ).toHaveCount(0);
  await expect(workspace(page).locator('.ic-card-result')).toHaveCount(0);
  await page.getByRole('button', { name: '工作空间设置', exact: true }).click();
  await page.getByLabel('异常场景演示').selectOption('none');
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await open(page, 'inq_de014');
  await workspace(page).getByRole('button', { name: '开始处理', exact: true }).click();
  await workspace(page).getByRole('button', { name: '取消本次运行', exact: true }).click();
  await expect(workspace(page).locator('.iw-run')).toContainText('已取消');
  await expect(workspace(page).locator('.iw-answer-result')).toHaveCount(0);
  await expect(
    workspace(page).getByRole('button', { name: '添加到画板', exact: true }),
  ).toHaveCount(0);
});

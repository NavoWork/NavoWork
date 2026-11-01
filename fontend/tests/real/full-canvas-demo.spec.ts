import { expect, test } from '@playwright/test';

test('German backpack grows ten saved nodes with sourced competitors and local artwork', async ({ page }) => {
  test.setTimeout(120000);
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (await page.request.post(`${base}/inquiries`, { data: { demoScenarioId: 'de-backpack' } })).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  let liveCalls = 0;
  await page.route('**/workbench/agent', async route => { liveCalls++; await route.abort(); });
  await page.route('**/workbench/research/concepts', async route => { liveCalls++; await route.abort(); });
  const phases = ['正在理解客户需求', '正在查阅相关资料', '正在执行本次业务分析', '正在准备双语回复', '正在核对关键细节', '正在保存本轮成果'];
  const sequence = ['requirements', 'competitor', 'design', 'quote', 'risks', 'reply', 'sample', 'order', 'production'];
  await page.goto(`/inquiries/${inquiry.id}`);
  await expect(page.locator('.react-flow__node')).toHaveCount(2);
  for (const [index, kind] of sequence.entries()) {
    await page.getByRole('button', { name: '整理画板', exact: true }).click();
    const node = page.locator(`.react-flow__node[data-id="${kind}:${index}"]`);
    const response = page.waitForResponse(r => r.url().endsWith('/workbench/simulations') && r.request().method() === 'POST');
    await node.getByRole('button', { name: '依据现有资料生成', exact: true }).click();
    const run = await (await response).json();
    expect(run.executionMode).toBe('simulation');
    const activity = page.getByRole('region', { name: 'AI 处理进度' });
    if (kind === 'competitor' || kind === 'design') {
      for (const phase of phases) await expect(activity.getByText(phase, { exact: true })).toBeVisible();
    }
    await expect(activity.getByText('本轮处理已完成', { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.locator(`.react-flow__node[data-id="${kind}:${index + 1}"]`)).toBeAttached();
    await expect(page.locator('.react-flow__node')).toHaveCount(Math.min(index + 3, 10));
  }
  expect(liveCalls).toBe(0);
  await page.reload();
  await expect(page.locator('.react-flow__node')).toHaveCount(10);
  await page.getByRole('button', { name: '整理画板', exact: true }).click();
  const image = page.locator('.ic-card-design img');
  await expect(image).toBeInViewport();
  await expect(page.locator('.ic-card-original')).toBeInViewport();
  await expect(page.locator('.ic-card-production')).toBeInViewport();
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
  const directory = page.getByRole('complementary', { name: '当前询盘文件目录' });
  await expect(directory.locator('[data-node-id]')).toHaveCount(10);
  await expect(directory.locator('[data-node-id="competitor:9"]')).toContainText('Aster Daypack');
  await expect(directory.locator('[data-node-id="production:9"]')).toContainText('QC 检查表');
  await page.screenshot({ path: 'test-results/full-canvas-board.png' });
  await page.getByRole('button', { name: '打开 竞品分析', exact: true }).click();
  await expect(page.locator('.ic-competitor-grid')).toContainText('EUR 69');
  await expect(page.locator('.ic-competitor-grid')).toContainText('EUR 79');
  await page.getByRole('tab', { name: '询盘画板', exact: true }).click();
  await page.getByRole('button', { name: '打开 产品设计图', exact: true }).click();
  await expect(page.locator('.ic-design-image img')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.locator('.ic-design-image').getByRole('link', { name: '下载图片', exact: true }).click();
  expect((await download).suggestedFilename()).toContain('.png');
  const revisions = await (await page.request.get(path + '/revisions')).json();
  const artifacts = revisions.items.at(-1).nodeArtifacts;
  expect(artifacts.concept_image.content.imageApiCalled).toBe(false);
  expect(artifacts.competitor_analysis.content.sources).toHaveLength(2);
  expect(artifacts.ta.content.tasks).toHaveLength(6);
  await page.screenshot({ path: 'test-results/full-canvas-design.png' });
});

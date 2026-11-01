import { expect, test } from '@playwright/test';

test('node generation simulates all six phases, persists content and keeps chat on its live route', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (await page.request.post(`${base}/inquiries`, { data: { demoScenarioId: 'de-backpack' } })).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  let liveRequests = 0;
  // Never send a provider-backed chat during acceptance; verify the selected route only.
  await page.route(`**${path}/workbench/agent`, async (route) => {
    liveRequests++;
    expect(route.request().postDataJSON().simulationNode).toBeUndefined();
    await route.fulfill({ status: 422, json: { error: { code: 'TEST_CHAT_ROUTE', message: 'Chat route verified without executing a model' } } });
  });
  await page.goto(`/inquiries/${inquiry.id}`);
  const dispatched = page.waitForResponse(r => r.url().endsWith('/workbench/simulations') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '依据现有资料生成', exact: true }).click();
  const run = await (await dispatched).json();
  expect(run.executionMode).toBe('simulation');
  const activity = page.getByRole('region', { name: 'AI 处理进度' });
  for (const title of ['正在理解客户需求', '正在查阅相关资料', '正在执行本次业务分析', '正在准备双语回复', '正在核对关键细节', '正在保存本轮成果']) {
    await expect(activity.getByText(title, { exact: true })).toBeVisible();
  }
  await expect(activity.getByText('本轮处理已完成', { exact: true })).toBeVisible();
  await expect(activity.locator('.iw-run-steps .is-complete')).toHaveCount(6);
  await expect(page.locator('.react-flow__node[data-id="quote:1"]')).toBeVisible();
  expect(liveRequests).toBe(0);
  const stored = await (await page.request.get(`${base}/runs/${run.id}`)).json();
  expect(stored.agentVerification.modelApiCalled).toBe(false);
  await page.reload();
  await expect(page.locator('.react-flow__node[data-id="requirements:1"]')).toContainText('recycled polyester');
  await expect(page.locator('.react-flow__node[data-id="quote:1"]')).toBeVisible();
  const chat = page.locator('.iw-assistant');
  await chat.getByLabel('补充要求或客户反馈').fill('请解释客户需求');
  await chat.getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect.poll(() => liveRequests).toBe(1);
});

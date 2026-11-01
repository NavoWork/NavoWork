import { expect, test } from '@playwright/test';

test('one inquiry chat preserves drafts and messages across both views without conversation management', async ({ page }) => {
  const conversationRequests: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/conversations')) conversationRequests.push(request.url());
  });
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const response = await page.request.post(`${base}/inquiries`, {
    data: { title: 'Single inquiry chat', customer: 'Test Buyer', originalText: 'Please quote 100 test bags.' },
  });
  expect(response.ok()).toBeTruthy();
  const inquiry = await response.json();
  const path = `${base}/inquiries/${inquiry.id}`;
  const session = await (await page.request.get('/api/v1/me')).json();
  await page.evaluate(({ scope }) => {
    localStorage.setItem(`easywork:active-chat:${scope}`, JSON.stringify('old_chat'));
    localStorage.setItem(`easywork:chat-draft:${scope}:old_chat`, JSON.stringify({ text: '旧对话未发送草稿', selection: { skillIds: [], knowledge: [] } }));
  }, { scope: `${session.user.id}:${session.workspace.id}:${inquiry.id}` });
  await page.goto(`/inquiries/${inquiry.id}`);
  const chat = page.locator('.iw-assistant:visible');
  const input = chat.getByLabel('补充要求或客户反馈');
  await expect(chat.locator('.iw-message')).toHaveCount(1);
  await expect(input).toHaveValue('旧对话未发送草稿');
  await expect(chat.getByRole('button', { name: '新建 AI 对话' })).toHaveCount(0);
  await expect(chat.getByRole('button', { name: '历史对话' })).toHaveCount(0);
  await expect(chat.getByText('仅当前询盘', { exact: true }).first()).toBeVisible();
  await input.fill('同一询盘连续处理');
  await page.getByRole('button', { name: '业务流程', exact: true }).click();
  await expect(input).toHaveValue('同一询盘连续处理');
  await page.reload();
  await expect(input).toHaveValue('同一询盘连续处理');
  await expect(chat.getByRole('button', { name: '新建 AI 对话' })).toHaveCount(0);
  const dispatch = page.waitForResponse(response => response.url().endsWith('/workbench/agent') && response.request().method() === 'POST');
  await chat.getByRole('button', { name: '开始处理', exact: true }).click();
  const dispatched = await dispatch;
  expect(dispatched.ok()).toBeTruthy();
  expect(dispatched.request().postDataJSON()).not.toHaveProperty('conversationId');
  const run = await dispatched.json();
  await expect(chat.locator('.iw-message.user').filter({ hasText: '同一询盘连续处理' })).toBeVisible();
  await page.getByRole('button', { name: '资料画板', exact: true }).click();
  await expect(chat.getByRole('region', { name: 'AI 处理进度' })).toBeVisible();
  expect((await (await page.request.get(`${base}/runs/${run.id}`)).json()).status).toBe('queued');
  expect((await page.request.post(`${base}/runs/${run.id}/cancel`)).ok()).toBeTruthy();
  await page.reload();
  await expect(input).toBeEnabled();
  await expect(chat.locator('.iw-message.user').filter({ hasText: '同一询盘连续处理' })).toBeVisible();
  await input.fill('保留这个询盘的草稿');
  const second = await (await page.request.post(`${base}/inquiries`, {
    data: { title: 'Separate inquiry', customer: 'Other Buyer', originalText: 'Please quote 200 cups.' },
  })).json();
  await page.goto(`/inquiries/${second.id}`);
  await expect(input).toHaveValue('');
  await expect(chat.locator('.iw-message')).toHaveCount(1);
  await expect(chat.locator('.iw-message')).not.toContainText('同一询盘连续处理');
  await page.goto(`/inquiries/${inquiry.id}`);
  await expect(input).toHaveValue('保留这个询盘的草稿');
  const messages = (await (await page.request.get(`${path}/messages`)).json()).items;
  expect(messages.some((message: { runId?: string }) => message.runId === run.id)).toBe(true);
  expect(conversationRequests).toEqual([]);
});

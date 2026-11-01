import { expect, test, type Page } from '@playwright/test';

const base = '/api/v1/workspaces/ws_demo';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

async function createInquiry(page: Page, title: string) {
  const response = await page.request.post(`${base}/inquiries`, {
    data: {
      title,
      customer: 'Merge Buyer',
      originalText: 'Please quote 3000 backpacks, FOB Ningbo.',
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('team Wiki is immediately available in @ references and submits its fixed source version', async ({
  page,
}) => {
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档' }).click();
  const dialog = page.getByRole('dialog');
  const title = `合并引用检查-${Date.now()}`;
  await dialog.getByLabel('文档名称').fill(title);
  await dialog.getByLabel('Markdown 正文').fill('# 包装要求\n使用牛皮纸包装。');
  await dialog.getByRole('button', { name: '创建文档' }).click();
  await expect(page.locator('.wiki-row').filter({ hasText: title })).toBeVisible();
  const documents = await (await page.request.get(`${base}/library/documents`)).json();
  const document = documents.items.find((item: { title: string }) => item.title === title);
  expect(document.sourceVersionId).toBeTruthy();
  const inquiry = await createInquiry(page, '合并引用询盘');
  await page.goto(`/inquiries/${inquiry.id}`);
  const work = page.locator('.inquiry-mount:not([hidden])');
  await expect(work.getByRole('tab', { name: '询盘画板', exact: true })).toBeVisible();
  const input = work.getByLabel('补充要求或客户反馈');
  await expect(input).toBeEnabled();
  await input.fill(`@${title}`);
  await work.getByRole('option', { name: title, exact: true }).click();
  await expect(work.getByLabel(`移除知识 ${title}`, { exact: true })).toBeVisible();
  await work.getByRole('button', { name: '选择技能', exact: true }).click();
  await work.getByRole('option', { name: '客户与询盘评估', exact: true }).click();
  await input.fill('请提取客户需求');
  // Stop at the dispatch boundary so the test does not need a model or create a live run.
  await page.route(`**/inquiries/${inquiry.id}/runs`, (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'TEST_OFFLINE', message: '测试服务暂不可用' } }),
    }),
  );
  const request = page.waitForRequest(
    (req) => req.method() === 'POST' && req.url().endsWith(`/inquiries/${inquiry.id}/runs`),
  );
  await work.getByRole('button', { name: '开始处理', exact: true }).click();
  const payload = (await request).postDataJSON();
  expect(payload.sourceVersionIds).toContain(document.sourceVersionId);
  expect(payload.instruction).toContain('客户与询盘评估');
  expect(payload.context.skills[0].id).toBe('inquiry-assessment');
  await expect(work.getByText('测试服务暂不可用')).toBeVisible();
  await expect(input).toHaveValue('请提取客户需求');
  await expect(work.getByLabel(`移除知识 ${title}`, { exact: true })).toBeVisible();
});

test('server canvas notes and attachments survive reload and appear in the personal library', async ({
  page,
}) => {
  const inquiry = await createInquiry(page, `合并资料同步-${Date.now()}`);
  await page.goto(`/inquiries/${inquiry.id}?view=canvas`);
  const work = page.locator('.inquiry-mount:not([hidden])');
  await expect(work.getByRole('tab', { name: '询盘画板', exact: true })).toBeVisible();
  await work.getByLabel('新建资料', { exact: true }).click();
  await work.getByRole('button', { name: '新建笔记', exact: true }).click();
  await work.getByLabel('笔记标题', { exact: true }).fill('合并后的工作笔记');
  await work.getByLabel('编辑工作笔记', { exact: true }).fill('客户确认使用牛皮纸包装。');
  await work.locator('input[type="file"]').setInputFiles({
    name: 'merge-attachment.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Persisted merge attachment'),
  });
  await expect
    .poll(async () => {
      const canvas = await (
        await page.request.get(`${base}/inquiries/${inquiry.id}/canvas`)
      ).json();
      return {
        notes: canvas.state?.notes.map((note: { title: string }) => note.title),
        files: canvas.state?.files.length,
      };
    })
    .toEqual({ notes: ['合并后的工作笔记'], files: 1 });
  await page.reload();
  await expect(work.locator('.ic-directory')).toContainText('合并后的工作笔记');
  await expect(work.locator('.ic-directory')).toContainText('merge-attachment.txt');
  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByRole('button', { name: `询盘文件夹 ${inquiry.title}`, exact: true }).click();
  await page.getByRole('button', { name: '预览 合并后的工作笔记.md', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('客户确认使用牛皮纸包装。');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '预览 merge-attachment.txt', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Persisted merge attachment');
  const download = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  expect((await download).suggestedFilename()).toBe('merge-attachment.txt');
});

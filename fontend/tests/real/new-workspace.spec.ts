import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
});

test('new inquiry opens the node workbench and only generates the requested node', async ({
  page,
}, info) => {
  const base = '/api/v1/workspaces/ws_demo';
  const created = await page.request.post(`${base}/inquiries`, {
    data: {
      title: '浏览器联调 · 通勤背包',
      customer: 'Browser Buyer',
      originalText: 'Please quote 3,000 custom backpacks, FOB Ningbo, delivery to Hamburg.',
      destination: 'Hamburg, Germany',
      customerContext: { channel: 'email', email: 'buyer@example.test' },
    },
  });
  expect(created.ok()).toBeTruthy();
  const inquiry = await created.json();
  const path = `${base}/inquiries/${inquiry.id}`;
  await page.goto(`/inquiries/${inquiry.id}`);
  const work = page.locator('.wbv2');
  await expect(work).toBeVisible();
  await expect(work.locator('.wbv2-stage')).toHaveCount(6);
  await expect(work.getByText('Browser Buyer', { exact: true }).first()).toBeVisible();
  await expect(work.getByText('Agent 尚未完成询盘评估')).toHaveCount(0);

  const spec = await page.request.put(`${path}/workbench/artifacts/spec`, {
    data: {
      baseVersion: 0,
      content: {
        fields: {
          product: 'custom commuter backpack',
          quantity: '3000',
          dimensions: '30 x 45 x 15 cm',
          fabric: '600D recycled polyester',
          logo: 'embroidered logo 60 x 25 mm',
          packaging: 'recycled polybag + hangtag',
          inspection: 'AQL 2.5',
          destination: 'Hamburg, Germany',
          incoterm: 'FOB',
          incotermsVersion: '2020',
          namedPlace: 'Ningbo',
        },
      },
    },
  });
  expect(spec.ok()).toBeTruthy();
  await page.reload();
  await expect(work.locator('.wbv2-original')).toContainText(inquiry.originalText);
  await expect(work.getByRole('button', { name: '让 Agent 分析' })).toBeVisible();
  await page.getByRole('button', { name: '资料画板', exact: true }).click();
  await expect(page.getByRole('tab', { name: '询盘画板', exact: true })).toBeVisible();
  await expect(page.getByLabel('补充要求或客户反馈')).toBeVisible();
  await expect(work).toHaveCount(0);
  await page.getByRole('button', { name: '业务流程', exact: true }).click();
  await expect(work).toBeVisible();
  await work.locator('.wbv2-stage').nth(1).click();
  await expect(work.getByLabel('产品')).toHaveValue('custom commuter backpack');
  await expect(work.getByLabel('验货标准')).toHaveValue('AQL 2.5');
  await page.screenshot({ path: info.outputPath('workbench-v2.png'), fullPage: true });

  const state = await (await page.request.get(`${path}/workbench`)).json();
  expect(state.case.currentRevision).toBe(1);
  expect(Object.keys(state.artifacts)).toEqual(['spec']);
  expect(state.stages.find((stage: { key: string }) => stage.key === 'costing').status).toBe(
    'empty',
  );
});

test('Wiki, assets, favorites and the skill market are persisted', async ({ page }) => {
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('文档名称').fill('服务端知识测试');
  await dialog.getByLabel('Markdown 正文').fill('# 规格确认\n请保留客户书面确认。');
  await dialog.getByRole('button', { name: '创建文档' }).click();
  await expect(page.locator('.wiki-row').filter({ hasText: '服务端知识测试' })).toBeVisible();
  await page.getByRole('button', { name: '收藏 服务端知识测试', exact: true }).click();
  await expect(
    page.getByRole('button', { name: '取消收藏 服务端知识测试', exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('button', { name: '取消收藏 服务端知识测试', exact: true }),
  ).toBeVisible();

  await page.getByRole('button', { name: '资产库', exact: true }).click();
  await page.getByRole('button', { name: '添加文件', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('资产文件').setInputFiles({
    name: 'personal-proof.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('A persisted personal file'),
  });
  await dialog.getByRole('button', { name: '添加 1 个文件' }).click();
  await expect(page.getByText('personal-proof.txt', { exact: true }).first()).toBeVisible();
  await page.reload();
  await page.getByText('personal-proof.txt', { exact: true }).first().dblclick();
  await expect(page.getByRole('dialog').getByRole('button', { name: '下载文件' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: '下载文件' }).click();
  expect((await download).suggestedFilename()).toBe('personal-proof.txt');
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: '技能市场', exact: true }).click();
  await expect(page.getByText('客户与询盘评估', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: /插件/ }).click();
  await expect(page.getByText('邮件连接器', { exact: true })).toBeVisible();
  await expect(page.getByText('规划中').first()).toBeVisible();
});

test('workbench keeps downstream nodes empty until the user advances them', async ({ page }) => {
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (
    await page.request.post(`${base}/inquiries`, {
      data: {
        title: '空白项目',
        customer: 'Empty Buyer',
        originalText: 'We may need some bags. Please advise.',
      },
    })
  ).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  await page.goto(`/inquiries/${inquiry.id}`);
  const work = page.locator('.wbv2');
  await expect(work).toBeVisible();
  const state = await (await page.request.get(`${path}/workbench`)).json();
  expect(state.case.currentRevision).toBe(0);
  expect(state.artifacts).toEqual({});
  expect(state.stages.find((stage: { key: string }) => stage.key === 'requirements').status).toBe(
    'empty',
  );
  await work.locator('.wbv2-stage').nth(1).click();
  await expect(work.getByText('尚未生成规格')).toBeVisible();
  await work.locator('.wbv2-stage').nth(2).click();
  await expect(work.getByText('尚未生成客户报价')).toBeVisible();
  await expect(work.getByLabel('补充要求或客户反馈')).toBeVisible();
});

test('assistant retains a rejected draft, then shows real run phases and cancellation', async ({
  page,
}, info) => {
  const base = '/api/v1/workspaces/ws_demo';
  const title = `业务对话引用-${Date.now()}`;
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('文档名称').fill(title);
  await dialog.getByLabel('Markdown 正文').fill('# 交期要求\n报价前确认生产与运输时间。');
  await dialog.getByRole('button', { name: '创建文档' }).click();
  await expect(page.locator('.wiki-row').filter({ hasText: title })).toBeVisible();
  const documents = await (await page.request.get(`${base}/library/documents`)).json();
  const document = documents.items.find((item: { title: string }) => item.title === title);
  expect(document.sourceVersionId).toBeTruthy();
  const response = await page.request.post(`${base}/inquiries`, {
    data: {
      title: '对话动效回归',
      customer: 'Motion Buyer',
      originalText: 'Please quote 100 bags.',
    },
  });
  expect(response.ok()).toBeTruthy();
  const inquiry = await response.json();
  const run = {
    id: 'run_ui_regression',
    inquiryId: inquiry.id,
    status: 'queued',
    phase: 'understanding',
    createdAt: new Date().toISOString(),
    baseRevision: 0,
    completedPhases: [] as string[],
  };
  let accept = false;
  await page.route(`**/inquiries/${inquiry.id}/workbench/agent`, (route) =>
    route.fulfill({
      status: accept ? 200 : 503,
      contentType: 'application/json',
      body: JSON.stringify(
        accept ? run : { error: { code: 'TEST_OFFLINE', message: '服务暂不可用，请重试' } },
      ),
    }),
  );
  await page.route(`**/runs/${run.id}`, (route) => route.fulfill({ json: run }));
  await page.route(`**/runs/${run.id}/events`, (route) => route.fulfill({ json: { items: [] } }));
  await page.route(`**/runs/${run.id}/cancel`, (route) => {
    run.status = 'cancelled';
    return route.fulfill({ json: run });
  });
  await page.goto(`/inquiries/${inquiry.id}`);
  const assistant = page.locator('.wbv2-agent');
  const input = assistant.getByLabel('补充要求或客户反馈');
  await assistant.getByRole('button', { name: '查看客户原始询盘', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Please quote 100 bags.');
  await page.keyboard.press('Escape');
  await assistant.getByRole('button', { name: '选择技能', exact: true }).click();
  await assistant.getByRole('option', { name: '客户与询盘评估', exact: true }).click();
  await input.fill(`@${title}`);
  await assistant.getByRole('option', { name: title, exact: true }).click();
  await input.fill('请检查客户交期要求');
  await page.reload();
  await expect(input).toHaveValue('请检查客户交期要求');
  await expect(assistant.getByLabel(`移除知识 ${title}`, { exact: true })).toBeVisible();
  await expect(assistant.getByLabel('移除技能 客户与询盘评估', { exact: true })).toBeVisible();
  const dispatched = page.waitForRequest(
    (req) =>
      req.method() === 'POST' && req.url().endsWith(`/inquiries/${inquiry.id}/workbench/agent`),
  );
  await assistant.getByRole('button', { name: '开始处理', exact: true }).click();
  const payload = (await dispatched).postDataJSON();
  expect(payload.node).toBe('inquiry');
  expect(payload.sourceVersionIds).toContain(document.sourceVersionId);
  expect(payload.context.skills[0].id).toBe('inquiry-assessment');
  expect(payload.instruction).toContain('客户与询盘评估');
  await expect(assistant).toContainText('服务暂不可用，请重试');
  await expect(input).toHaveValue('请检查客户交期要求');
  accept = true;
  await assistant.getByRole('button', { name: '开始处理', exact: true }).click();
  await expect(input).toHaveValue('');
  await expect(assistant.getByLabel(`移除知识 ${title}`, { exact: true })).toHaveCount(0);
  const activity = assistant.getByRole('region', { name: 'AI 处理进度' });
  await expect(activity).toContainText('正在准备，马上开始');
  await expect(assistant.getByRole('button', { name: '开始处理', exact: true })).toBeDisabled();
  run.status = 'running';
  run.phase = 'retrieving';
  run.completedPhases = ['understanding'];
  await expect(activity).toContainText('正在查阅相关资料');
  await expect(activity.getByText('查阅资料', { exact: true }).locator('..')).toHaveAttribute(
    'aria-current',
    'step',
  );
  await page.screenshot({ path: info.outputPath('restored-run-animation.png'), fullPage: true });
  await activity.getByRole('button', { name: '取消本次运行' }).click();
  await expect(activity).toHaveAttribute('data-status', 'cancelled');
  await input.fill('下一轮要求');
  await expect(assistant.getByRole('button', { name: '开始处理', exact: true })).toBeEnabled();
});

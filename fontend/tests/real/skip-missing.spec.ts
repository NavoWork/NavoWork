import { expect, test } from '@playwright/test';

test('skipping unanswered questions keeps node warnings after refresh and reveals the next draft', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (await page.request.post(`${base}/inquiries`, { data: {
    title: 'Skip incomplete inquiry', customer: 'Buyer', originalText: 'Please quote backpacks.',
  } })).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  const run = await (await page.request.post(`${path}/workbench/agent`, { data: { node: 'requirements', instruction: '整理需求', baseRevision: 0 } })).json();
  let skipped = false;
  const questions = [{ id: 'dimensions', question: '请补充背包尺寸。' }];
  // UI-only transport fixture; the checkpoint resume and persistence are covered by backend tests.
  await page.route(`**${path}`, async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), activeRunId: null,
      pendingRunId: skipped ? undefined : run.id, latestRunId: run.id,
      nodeWarnings: { requirements: [{ question: questions[0].question, runId: run.id, skipped }] },
    } });
  });
  await page.route(`**${base}/runs/${run.id}`, async (route) => {
    await route.fulfill({ json: { ...run, node: 'requirements', status: skipped ? 'succeeded' : 'needs_input',
      clarification: skipped ? undefined : { questions }, skippedQuestions: skipped ? [questions[0].question] : [],
    } });
  });
  await page.route(`**${path}/runs`, async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({ replyToRunId: run.id, baseRevision: 0, skipMissing: true });
    skipped = true;
    await route.fulfill({ json: { ...run, status: 'succeeded', skippedQuestions: [questions[0].question] } });
  });
  await page.goto(`/inquiries/${inquiry.id}`);
  const node = page.locator('.react-flow__node[data-id="requirements:0"]');
  await expect(node.getByRole('img', { name: '客户需求与规格有1项待确认' })).toBeVisible();
  await page.getByRole('button', { name: '跳过缺失项，继续生成', exact: true }).click();
  await expect(page.getByText('草稿已保存，仍有待确认项', { exact: true })).toBeVisible();
  await expect(page.locator('.react-flow__node:visible')).toHaveCount(3);
  await page.reload();
  await expect(node.getByRole('img', { name: '客户需求与规格有1项待确认' })).toBeVisible();
  await page.getByRole('complementary', { name: '当前询盘文件目录' }).getByRole('button', { name: '需求数据', exact: true }).click();
  await page.getByText('1 项待确认 · 已暂时跳过', { exact: true }).click();
  await expect(page.locator('.ic-missing-warning')).toContainText('请补充背包尺寸。');
  await page.request.post(`${base}/runs/${run.id}/cancel`);
});

test('a quote node can continue past pending requirements and reveal the next node', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const inquiry = await (await page.request.post(`${base}/inquiries`, { data: { demoScenarioId: 'us-tote' } })).json();
  const path = `${base}/inquiries/${inquiry.id}`;
  await page.request.put(`${path}/workbench/artifacts/spec`, { data: { baseVersion: 0, content: { fields: { product: 'Cotton tote', quantity: '5000' } } } });
  const revisions = await (await page.request.get(`${path}/revisions`)).json();
  const current = revisions.items[0];
  const waiting = await (await page.request.post(`${path}/workbench/agent`, { data: { node: 'requirements', instruction: '整理需求', baseRevision: 1 } })).json();
  const nextId = 'quote-after-pending';
  const questions = [{ id: 'logo', question: '请补充印刷位置。' }];
  let generated = false;
  const completed = { ...current, number: 2, generatedNode: 'quote', quote: {
    sku: 'TOTE', quantity: 5000, currency: 'USD', unitPriceMinor: 365, goodsSubtotalMinor: 1825000,
    freightMinor: null, taxMinor: null, totalMinor: null, quoteStatus: 'draft', sourceVersionIds: [],
    timing: { dispatchDays: null, productionDays: 21, startsAfter: 'sample and deposit', transitDays: null, arrivalGuaranteed: false },
  } };
  // Network fixtures cover the UI transition; backend checkpoint and actual quote persistence have a separate integration test.
  await page.route(`**${path}`, async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), activeRunId: null, currentRevision: generated ? 2 : 1,
      pendingRunId: generated ? undefined : waiting.id, latestRunId: generated ? nextId : waiting.id,
      nodeWarnings: { requirements: [{ question: questions[0].question, runId: waiting.id, skipped: generated }] },
    } });
  });
  await page.route(`**${path}/revisions`, async (route) => {
    await route.fulfill({ json: { items: generated ? [current, completed] : [current] } });
  });
  await page.route(`**${base}/runs/${waiting.id}`, (route) => route.fulfill({ json: { ...waiting, status: 'needs_input', clarification: { questions } } }));
  const finished = { ...waiting, id: nextId, node: 'costing', status: 'succeeded', outputRevision: 2, skippedQuestions: [questions[0].question] };
  await page.route(`**${base}/runs/${nextId}`, (route) => route.fulfill({ json: finished }));
  await page.route(`**${path}/workbench/simulations`, async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({ node: 'costing', baseRevision: 1, skipPendingRunId: waiting.id });
    generated = true;
    await route.fulfill({ json: finished });
  });
  await page.goto(`/inquiries/${inquiry.id}`);
  await page.locator('.react-flow__node[data-id="quote:1"]').getByRole('button', { name: '跳过缺项并生成', exact: true }).click();
  await expect(page.locator('.react-flow__node[data-id="quote:2"]')).toContainText('3.65');
  await expect(page.locator('.react-flow__node[data-id="risks:2"]')).toBeVisible();
  await page.reload();
  await expect(page.locator('.react-flow__node[data-id="quote:2"]')).toContainText('3.65');
  await expect(page.locator('.react-flow__node[data-id="risks:2"]')).toBeVisible();
  await page.request.post(`${base}/runs/${waiting.id}/cancel`);
});

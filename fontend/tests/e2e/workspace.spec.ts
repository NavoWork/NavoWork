import { test, expect, type Page } from '@playwright/test';
async function login(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.getByRole('heading', { name: /今天，从一个好机会开始/ })).toBeVisible();
}
async function home(page: Page) {
  await page.locator('.tab-bar').getByRole('button', { name: '工作台', exact: true }).click();
}
async function openMexico(page: Page) {
  await page.getByRole('button', { name: '墨西哥帆布袋试单', exact: true }).click();
  await expect(page.getByRole('heading', { name: '墨西哥帆布袋试单', exact: true })).toBeVisible();
}
async function snapshot(page: Page, path: string) {
  return page.evaluate(async (p) => {
    const url = '/src/api/index.ts';
    const { api } = await import(url);
    return api.get(p);
  }, path);
}
test.beforeEach(async ({ page }) => {
  await login(page);
});
test('首页筛选与搜索保持全集计数，弹窗可用 Escape 关闭', async ({ page }) => {
  await expect(page.locator('.inquiry-table tbody tr')).toHaveCount(4);
  await page.getByLabel('搜索询盘或客户').fill('陶瓷');
  await expect(page.locator('.inquiry-table tbody tr')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '进行中 1', exact: true })).toBeVisible();
  await page.getByLabel('搜索询盘或客户').fill('');
  await page.getByRole('button', { name: '待办询盘 1', exact: true }).click();
  await expect(page.locator('.inquiry-table tbody tr')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '德国陶瓷杯采购询盘', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '新建询盘', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
test('创建保留独立原文，Mock 对未见原文诚实返回需补充', async ({ page }) => {
  await page.getByRole('button', { name: '新建询盘', exact: true }).first().click();
  await page.getByLabel('询盘名称').fill('日本玻璃瓶订单');
  await page.getByLabel('客户名称').fill('Tokyo Glass');
  await page.getByLabel('客户原文').fill('We need 250 glass bottles delivered to Tokyo.');
  await page.getByRole('button', { name: '创建并打开询盘' }).click();
  await expect(page.getByRole('heading', { name: '日本玻璃瓶订单', exact: true })).toBeVisible();
  await expect(page.locator('.iw-original')).toContainText('250 glass bottles');
  await expect(page.locator('.iw-original')).not.toContainText('canvas');
  await page.getByRole('button', { name: '开始处理', exact: true }).click();
  await expect(page.locator('.iw-run')).toContainText('需补充信息', { timeout: 12000 });
  await expect(page.getByRole('button', { name: '版本记录 暂无' })).toBeVisible();
});
test('唯一 Tab、未发送文字隔离、关闭及刷新恢复', async ({ page }) => {
  await openMexico(page);
  await page.getByRole('textbox', { name: /补充要求或客户反馈/ }).fill('墨西哥专属未发送文字');
  await home(page);
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '德国陶瓷杯采购询盘', exact: true })
    .click();
  await page.getByRole('textbox', { name: /补充要求或客户反馈/ }).fill('德国专属未发送文字');
  await page
    .locator('.tab-bar')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toHaveValue(
    '墨西哥专属未发送文字',
  );
  await home(page);
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await expect(
    page.locator('.tab-bar').getByRole('button', { name: '墨西哥帆布袋试单', exact: true }),
  ).toHaveCount(1);
  await page.getByRole('button', { name: '关闭 墨西哥帆布袋试单', exact: true }).click();
  await home(page);
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toHaveValue(
    '墨西哥专属未发送文字',
  );
  await page.reload();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toHaveValue(
    '墨西哥专属未发送文字',
  );
});
test('三阶段只导航，来源可回读，历史只读', async ({ page }) => {
  await openMexico(page);
  const before = await snapshot(page, '/workspaces/ws_demo/inquiries/inq_mx026');
  for (const name of ['准备方案', '完成回复', '读懂询盘'])
    await page.getByRole('button', { name: new RegExp(name) }).click();
  const after = await snapshot(page, '/workspaces/ws_demo/inquiries/inq_mx026');
  expect(after.currentRevision).toBe(before.currentRevision);
  expect(after.activeRunId).toBeNull();
  await page.getByRole('tab', { name: '资料依据' }).click();
  await page.getByRole('button', { name: /现货商品价表/ }).click();
  await expect(page.getByRole('dialog')).toContainText('USD 1.80');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: /版本记录/ }).click();
  await page.locator('.iw-history-list').getByRole('button').last().click();
  await expect(page.getByText('正在查看 V1 历史快照，内容只读。')).toBeVisible();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toBeDisabled();
});
test('运行中切换、关闭、刷新后结果只写入原询盘', async ({ page }) => {
  await openMexico(page);
  await page.getByRole('textbox', { name: /补充要求或客户反馈/ }).fill('改为600件，请更新报价');
  await page.getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(page.locator('.iw-run')).toBeVisible();
  await home(page);
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '德国陶瓷杯采购询盘', exact: true })
    .click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toBeEnabled();
  await page.getByRole('button', { name: '关闭 墨西哥帆布袋试单', exact: true }).click();
  await page.reload();
  await home(page);
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await expect(page.getByRole('button', { name: '版本记录 V3' })).toBeVisible({ timeout: 15000 });
  await page.getByRole('tab', { name: '方案与报价' }).click();
  await expect(page.locator('.inquiry-mount:not([hidden]) .iw-quote-amount')).toContainText(
    '1,080.00',
  );
  const germany = await snapshot(page, '/workspaces/ws_demo/inquiries/inq_de014');
  expect(germany.currentRevision).toBe(0);
});
test('已结束只读，显式重开后可继续处理', async ({ page }) => {
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '英国展会礼品袋方案', exact: true })
    .click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toBeDisabled();
  await page.getByRole('button', { name: '重新打开', exact: true }).click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toBeEnabled();
});
test('390px 主线无水平溢出，表单键盘焦点受限于弹窗', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.overview-grid')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: 'docs/screenshots/home-mobile.png', fullPage: true });
  await openMexico(page);
  await page.getByRole('tab', { name: '方案与报价' }).click();
  await expect(page.locator('.iw-quote-amount')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: 'docs/screenshots/inquiry-mobile.png', fullPage: true });
  await page.getByRole('button', { name: '对话', exact: true }).click();
  await expect(page.getByRole('textbox', { name: /补充要求或客户反馈/ })).toBeVisible();
  await page.getByRole('button', { name: '打开导航' }).click();
  await page.getByRole('button', { name: '新建询盘', exact: true }).first().click();
  for (let i = 0; i < 12; i++) await page.keyboard.press('Tab');
  expect(await page.evaluate(() => !!document.activeElement?.closest('[role=dialog]'))).toBe(true);
});

test('桌面展示截图与退出登录', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator('.inquiry-table tbody tr')).toHaveCount(4);
  await page.screenshot({ path: 'docs/screenshots/home-desktop.png', fullPage: true });
  await openMexico(page);
  await page.getByRole('tab', { name: '方案与报价' }).click();
  await expect(page.locator('.iw-quote-amount')).toBeVisible();
  await expect(page.getByRole('button', { name: '导出草稿材料', exact: true })).toBeEnabled();
  await page.screenshot({ path: 'docs/screenshots/inquiry-desktop.png', fullPage: true });
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('heading', { name: '开始今天的工作' })).toBeVisible();
});

test('浏览器存储被禁用与异常链接不会使页面崩溃', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new DOMException('blocked', 'SecurityError');
    };
  });
  await page.reload();
  await expect(
    page.getByText('浏览器无法保存界面偏好，关闭或刷新前请确认修改已同步。'),
  ).toBeVisible();
  // Vite rejects malformed HTTP paths before serving the app; exercise client-side history.
  await page.evaluate(() => {
    history.pushState({}, '', '/inquiries/%E0%A4%A');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expect(page.getByText('询盘链接格式不正确，请从工作台重新打开。')).toBeVisible();
  await expect(page.getByRole('heading', { name: /今天，从一个好机会开始/ })).toBeVisible();
});

import { test, expect, type Page } from '@playwright/test';

const rows = (page: Page) => page.locator('.wh-work-table tbody tr');
const workbench = (page: Page) =>
  page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('button', { name: '工作台', exact: true });

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(rows(page)).toHaveCount(4);
});

test('只保留工作台，四张卡片筛选完整列表且搜索不改变统计口径', async ({ page }) => {
  await expect(page.getByRole('button', { name: '全部询盘', exact: true })).toHaveCount(0);
  const cases = [
    ['待办询盘', '德国陶瓷杯采购询盘'],
    ['进行中', '墨西哥帆布袋试单'],
    ['待确认', '美国环保购物袋补单'],
    ['已结束', '英国展会礼品袋方案'],
  ];
  for (const [status, title] of cases) {
    const card = page.getByRole('button', { name: `${status} 1`, exact: true });
    await card.click();
    await expect(card).toHaveAttribute('aria-pressed', 'true');
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page)).toContainText(title);
  }
  await page.getByLabel('搜索询盘或客户').fill('英国');
  await expect(rows(page)).toHaveCount(1);
  await page.getByRole('button', { name: '待办询盘 1', exact: true }).click();
  await expect(page.getByText('没有找到匹配的工作', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '已结束 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '全部', exact: true }).click();
  await expect(rows(page)).toHaveCount(1);
  await expect(page.getByLabel('搜索询盘或客户')).toHaveValue('英国');
  await page.getByRole('button', { name: '清除搜索', exact: true }).click();
  await expect(rows(page)).toHaveCount(4);
});

test('旧列表链接保留查询与锚点，详情直达以及关闭标签返回都可用', async ({ page }) => {
  await page.goto('/inquiries?q=%E5%B8%86%E5%B8%83&status=active#work-list');
  await expect(page).toHaveURL('/?q=%E5%B8%86%E5%B8%83&status=active#work-list');
  await expect(rows(page)).toHaveCount(1);
  await rows(page).getByRole('button', { name: '墨西哥帆布袋试单', exact: true }).click();
  await expect(page).toHaveURL('/inquiries/inq_mx026');
  await expect(page.getByRole('heading', { name: '墨西哥帆布袋试单', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '关闭 墨西哥帆布袋试单', exact: true }).click();
  await expect(page).toHaveURL(/\?q=%E5%B8%86%E5%B8%83&status=active/);
  await expect(page.getByLabel('搜索询盘或客户')).toHaveValue('帆布');
  await expect(rows(page)).toHaveCount(1);
  await page.goto('/inquiries/inq_uk012');
  await expect(
    page.getByRole('heading', { name: '英国展会礼品袋方案', exact: true }),
  ).toBeVisible();
});

test('加载更多后打开详情，返回恢复查询、已加载记录和滚动位置', async ({ page }) => {
  await page.evaluate(async () => {
    const url = '/src/api/index.ts';
    const { api } = await import(url);
    for (let index = 1; index <= 23; index++) {
      await api.post('/workspaces/ws_demo/inquiries', {
        title: `批量工作 ${index}`,
        customer: 'Pagination Customer',
        originalText: `Please quote item ${index}.`,
      });
    }
  });
  await page.goto('/?status=todo&q=批量');
  await expect(rows(page)).toHaveCount(20);
  await expect(page.getByRole('heading', { name: '我的工作 23', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '加载更多', exact: true }).click();
  await expect(rows(page)).toHaveCount(23);
  await expect(page.getByRole('button', { name: '加载更多', exact: true })).toHaveCount(0);
  const last = rows(page).last().getByRole('button');
  await last.scrollIntoViewIfNeeded();
  const position = await page.locator('.content-scroll').evaluate((element) => element.scrollTop);
  expect(position).toBeGreaterThan(300);
  const title = await last.innerText();
  await last.click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await workbench(page).click();
  await expect(page.getByLabel('搜索询盘或客户')).toHaveValue('批量');
  await expect(page.getByRole('button', { name: '待办询盘 24', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(rows(page)).toHaveCount(23);
  await expect
    .poll(() => page.locator('.content-scroll').evaluate((element) => element.scrollTop))
    .toBeGreaterThan(position - 10);
});

test('新建与重开后列表和统计同步，输入草稿在页面切换后保留', async ({ page }) => {
  const goal = 'Please quote 250 glass bottles for Tokyo.';
  await page.getByLabel('描述新的工作目标').fill(goal);
  await rows(page).getByRole('button', { name: '英国展会礼品袋方案', exact: true }).click();
  await page.getByRole('button', { name: '重新打开', exact: true }).click();
  await expect(page.getByLabel(/补充要求或客户反馈/)).toBeEnabled();
  await workbench(page).click();
  await expect(page.getByLabel('描述新的工作目标')).toHaveValue(goal);
  await expect(page.getByRole('button', { name: '已结束 0', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '进行中 2', exact: true })).toBeVisible();
  await page.getByLabel('描述新的工作目标').press('Control+Enter');
  await expect(page.getByLabel('客户原文')).toHaveValue(goal);
  await page.getByRole('button', { name: '创建并打开工作', exact: true }).click();
  const current = page.locator('.inquiry-mount:not([hidden])');
  await current.getByRole('button', { name: '查看客户原始询盘', exact: true }).click();
  await expect(current.getByLabel('编辑客户原始询盘')).toHaveValue(goal);
  await workbench(page).click();
  await expect(page.getByLabel('描述新的工作目标')).toHaveValue('');
  await expect(rows(page)).toHaveCount(5);
  await expect(page.getByRole('button', { name: '待办询盘 2', exact: true })).toBeVisible();
});

test('请求失败可重试，筛选无匹配时可以清除条件', async ({ page }) => {
  async function fault(value: string) {
    await page.getByRole('button', { name: '工作空间设置', exact: true }).click();
    await page.getByLabel('异常场景演示').selectOption(value);
    await page.getByRole('button', { name: '完成', exact: true }).click();
  }
  await fault('network');
  await page.getByLabel('搜索询盘或客户').fill('墨西哥');
  await expect(page.locator('.wh-work-panel .error-notice')).toBeVisible();
  await fault('none');
  await page.locator('.wh-work-panel').getByRole('button', { name: '重试', exact: true }).click();
  await expect(rows(page)).toHaveCount(1);
  await page.getByLabel('搜索询盘或客户').fill('不存在的客户');
  await expect(page.getByText('没有找到匹配的工作', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '清除筛选', exact: true }).click();
  await expect(rows(page)).toHaveCount(4);
});

import { test, expect, type Page } from '@playwright/test';

const theme = (page: Page) => page.getByRole('combobox', { name: '外观主题' });
async function expectTheme(page: Page, value: 'light' | 'dark') {
  await expect(page.locator('html')).toHaveAttribute('data-theme', value);
  await expect(page.locator('#app-favicon')).toHaveAttribute(
    'href',
    `/brand/navowork-favicon-${value}.svg`,
  );
  await expect(
    page.locator('.sidebar .brand-mark, .login-story .brand-mark').locator(`.navo-logo-${value}`),
  ).toBeVisible();
}
async function login(page: Page) {
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await expect(page.locator('.topbar')).toBeVisible();
}

test('首屏在 React 加载前恢复深色主题及 favicon', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('navowork:theme', 'dark'));
  await page.route('**/src/main.tsx*', (route) => route.abort());
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(17, 17, 17)');
  await expect(page.locator('#app-favicon')).toHaveAttribute(
    'href',
    '/brand/navowork-favicon-dark.svg',
  );
  await expect(page.locator('#root')).toBeEmpty();
});

test('跟随系统、手动覆盖、刷新与退出登录后保留主题', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await expect(theme(page)).toHaveValue('system');
  await expectTheme(page, 'dark');
  await theme(page).selectOption('light');
  await expectTheme(page, 'light');
  await page.reload();
  await expectTheme(page, 'light');
  await expect(theme(page)).toHaveValue('light');
  await login(page);
  await expectTheme(page, 'light');
  await theme(page).selectOption('dark');
  await expectTheme(page, 'dark');
  await page.getByRole('button', { name: '退出登录' }).click();
  await expectTheme(page, 'dark');
  await theme(page).selectOption('system');
  await page.emulateMedia({ colorScheme: 'light' });
  await expectTheme(page, 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expectTheme(page, 'dark');
});

test('跨标签同步主题，清除偏好恢复跟随系统', async ({ page, context }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/');
  const other = await context.newPage();
  await other.goto('/');
  await theme(other).selectOption('dark');
  await expectTheme(page, 'dark');
  await expect(theme(page)).toHaveValue('dark');
  await other.evaluate(() => localStorage.removeItem('navowork:theme'));
  await expect(theme(page)).toHaveValue('system');
  await expectTheme(page, 'light');
  await other.close();
});

test('本地存储不可读写时仍可切换主题并使用工作台', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.addInitScript(() => {
    localStorage.setItem('navowork:theme', 'not-a-theme');
    const get = Storage.prototype.getItem;
    Storage.prototype.getItem = function (key) {
      if (key === 'navowork:theme') throw new DOMException('Blocked', 'SecurityError');
      return get.call(this, key);
    };
    const set = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'navowork:theme') throw new DOMException('Blocked', 'QuotaExceededError');
      return set.call(this, key, value);
    };
  });
  await page.goto('/');
  await expectTheme(page, 'light');
  await theme(page).selectOption('dark');
  await expectTheme(page, 'dark');
  await expect(page.getByRole('status')).toContainText('主题仅在当前页面生效');
  await login(page);
  await expectTheme(page, 'dark');
});

test('深色覆盖工作台、弹窗和延迟加载资源，切换不丢失报价输入', async ({ page }) => {
  await page.goto('/');
  await theme(page).selectOption('dark');
  await login(page);
  await page.getByRole('button', { name: '演示体验报价工作流' }).click();
  await page.getByLabel('工厂基础报价').fill('46');
  await expect(page.getByTestId('unit-price')).toHaveText('$9.03');
  await expect(page.locator('.tw-canvas')).toHaveCSS('background-color', 'rgb(25, 27, 32)');
  await theme(page).selectOption('light');
  await expect(page.getByLabel('工厂基础报价')).toHaveValue('46');
  await expect(page.getByTestId('unit-price')).toHaveText('$9.03');
  await theme(page).selectOption('dark');
  await page.getByRole('button', { name: '供应商 A · B2', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCSS('background-color', 'rgb(34, 37, 44)');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '知识库', exact: true }).click();
  await page.getByRole('button', { name: '新建文档', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCSS('background-color', 'rgb(34, 37, 44)');
  await page.keyboard.press('Escape');
  await page.goto('/inquiries');
  await page.getByRole('button', { name: '墨西哥帆布袋试单', exact: true }).click();
  await expect(page.locator('.iw-stage-bar')).toHaveCSS('background-color', 'rgb(25, 27, 32)');
});

test('移动端可切换主题和打开侧栏，无页面横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await theme(page).selectOption('dark');
  await login(page);
  await expect(theme(page)).toBeVisible();
  await page.getByRole('button', { name: '打开导航' }).click();
  await expect(page.locator('.sidebar .navo-logo-dark')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '演示体验报价工作流' }).click();
  await theme(page).selectOption('light');
  await expect(page.getByTestId('unit-price')).toHaveText('$8.69');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

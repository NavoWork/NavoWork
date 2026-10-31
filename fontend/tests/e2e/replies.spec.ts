import { test, expect, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
async function openReply(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '进入演示工作空间' }).click();
  await page
    .locator('.inquiry-table')
    .getByRole('button', { name: '墨西哥帆布袋试单', exact: true })
    .click();
  await page.getByRole('tab', { name: '客户回复', exact: true }).click();
  await expect(page.getByLabel('English 回复草稿')).toBeVisible();
  await expect(page.locator('.iw-draft-status')).toContainText('已保存');
}
async function fault(page: Page, value: string) {
  await page.getByRole('button', { name: '工作空间设置', exact: true }).click();
  await page.getByLabel('异常场景演示').selectOption(value);
  await page.getByRole('button', { name: '完成', exact: true }).click();
}
async function saved(page: Page, version: number) {
  await expect(page.locator('.iw-draft-status')).toContainText(`已保存 · 草稿 V${version}`);
}
test.beforeEach(async ({ page }) => {
  await openReply(page);
});
test('英西回复独立自动保存，切语言及刷新恢复服务端草稿', async ({ page }) => {
  const english = await page.getByLabel('English 回复草稿').inputValue();
  await page.getByLabel('English 回复草稿').fill(`${english}\nEnglish follow-up note.`);
  await page.getByRole('button', { name: 'Español · México', exact: true }).click();
  const spanish = await page.getByLabel('Español · México 回复草稿').inputValue();
  expect(spanish).not.toContain('English follow-up');
  await page.getByLabel('Español · México 回复草稿').fill(`${spanish}\nNota de seguimiento.`);
  await saved(page, 2);
  await page.reload();
  await expect(page.getByLabel('Español · México 回复草稿')).toHaveValue(
    `${spanish}\nNota de seguimiento.`,
  );
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await expect(page.getByLabel('English 回复草稿')).toHaveValue(
    `${english}\nEnglish follow-up note.`,
  );
  await saved(page, 2);
});
test('网络保存失败保留输入且不显示成功，恢复后可显式重试', async ({ page }) => {
  const original = await page.getByLabel('English 回复草稿').inputValue();
  await fault(page, 'network');
  await page.getByLabel('English 回复草稿').fill(`${original}\nUnsent local note.`);
  await expect(page.locator('.iw-draft-status')).toContainText('保存失败 · 尚未保存到服务端');
  await expect(page.getByLabel('English 回复草稿')).toHaveValue(`${original}\nUnsent local note.`);
  await expect(page.getByRole('button', { name: '导出草稿材料', exact: true })).toBeDisabled();
  await fault(page, 'none');
  await page.locator('.iw-reply-editor').getByRole('button', { name: '重试', exact: true }).click();
  await saved(page, 2);
});
test('草稿冲突保留本地文字，比较后显式基于服务端最新版本保存', async ({ page }) => {
  const original = await page.getByLabel('English 回复草稿').inputValue();
  await fault(page, 'draft-conflict');
  const changed = `${original}\nMy conflict resolution note.`;
  await page.getByLabel('English 回复草稿').fill(changed);
  await expect(page.locator('.iw-draft-status')).toContainText('草稿冲突');
  await expect(page.getByLabel('English 回复草稿')).toHaveValue(changed);
  await page.getByRole('button', { name: '比较本地与服务端版本' }).click();
  await expect(page.getByRole('dialog')).toContainText('其他编辑者的模拟修改');
  await expect(page.getByRole('dialog')).toContainText('My conflict resolution note.');
  await page.getByRole('button', { name: '保留本地修改并保存', exact: true }).click();
  await saved(page, 3);
  await page.reload();
  await expect(page.getByLabel('English 回复草稿')).toHaveValue(changed);
});
test('人工改错金额使审校和唯一导出入口阻断', async ({ page }) => {
  const original = await page.getByLabel('English 回复草稿').inputValue();
  await page.getByLabel('English 回复草稿').fill(original.replace('540.00', '999.00'));
  await saved(page, 2);
  await page.getByRole('button', { name: '复核当前草稿', exact: true }).click();
  await expect(page.locator('.iw-review-result')).toContainText('需要修改后再导出');
  await expect(page.locator('.iw-review-result')).toContainText('商品小计与报价不一致');
  await page.getByRole('button', { name: '导出草稿材料', exact: true }).click();
  await expect(page.locator('.iw-page > .error-notice')).toContainText('商品小计与报价不一致');
  await expect(page.getByRole('button', { name: '下载 HTML', exact: true })).toHaveCount(0);
});
test('通过复核后下载指定业务及草稿版本的 HTML，业务状态保持进行中', async ({ page }, testInfo) => {
  const original = await page.getByLabel('English 回复草稿').inputValue();
  await page.getByLabel('English 回复草稿').fill(`${original}\nReviewed material marker.`);
  await saved(page, 2);
  await page.getByRole('button', { name: '复核当前草稿', exact: true }).click();
  await expect(page.locator('.iw-review-result')).toContainText('复核通过');
  await page.getByRole('button', { name: '导出草稿材料', exact: true }).click();
  await expect(page.locator('.iw-export-status')).toContainText('指定版本的草稿材料已准备好');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 HTML', exact: true }).click();
  const download = await downloadPromise;
  const output = testInfo.outputPath('draft.html');
  await download.saveAs(output);
  const html = await readFile(output, 'utf8');
  expect(html).toContain('Reviewed material marker.');
  expect(html).toContain('540.00');
  expect(html).toContain('V2');
  expect(html).not.toContain('<script>');
  await expect(page.locator('.iw-title')).toContainText('进行中');
});
test('切到历史版本不会把当前未保存文字呈现为历史正文', async ({ page }) => {
  const original = await page.getByLabel('English 回复草稿').inputValue();
  await fault(page, 'network');
  await page.getByLabel('English 回复草稿').fill(`${original}\nLOCAL-UNSAVED-CURRENT`);
  await expect(page.locator('.iw-draft-status')).toContainText('保存失败');
  await fault(page, 'none');
  await page.getByRole('button', { name: /版本记录/ }).click();
  await page.locator('.iw-history-list').getByRole('button').last().click();
  await expect(page.getByLabel('English 回复草稿')).not.toHaveValue(/LOCAL-UNSAVED-CURRENT/);
  await expect(page.getByLabel('English 回复草稿')).toHaveAttribute('readonly', '');
  await page.getByRole('button', { name: '回到当前版本', exact: true }).click();
  await expect(page.getByLabel('English 回复草稿')).toHaveValue(
    `${original}\nLOCAL-UNSAVED-CURRENT`,
  );
  await saved(page, 2);
});
test('素材先待提交，运行成功才写入版本；材料清单锁定指定草稿版本', async ({ page }) => {
  await page.getByRole('tab', { name: '资料依据', exact: true }).click();
  await page.getByRole('button', { name: '选择引用素材', exact: true }).click();
  await page.getByRole('dialog').getByRole('checkbox').check();
  await page.getByRole('button', { name: '确认选择 1 份素材', exact: true }).click();
  await expect(page.locator('.iw-materials')).toContainText('当前版本尚未改变');
  await expect(page.getByRole('button', { name: '版本记录 V2', exact: true })).toBeVisible();
  await page.getByLabel(/补充要求或客户反馈/).fill('附上所选资料，保持300件现货方案');
  await page.getByRole('button', { name: '处理反馈', exact: true }).click();
  await expect(page.getByRole('button', { name: '版本记录 V3', exact: true })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.locator('.iw-asset-refs')).toContainText('asset_sample:v1');
  await page.getByRole('button', { name: '整理材料草稿', exact: true }).click();
  await expect(page.locator('.iw-material-list')).toContainText('V3 材料草稿');
  await expect(page.locator('.iw-material-list')).toContainText(
    '英语草稿 V1 · 西语草稿 V1 · 1 份素材',
  );
  await expect(page.locator('.iw-material-list')).toContainText('已整理 · 未发送');
  await expect(page.locator('.iw-title')).toContainText('进行中');
});

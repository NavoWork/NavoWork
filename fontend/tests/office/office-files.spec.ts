import { expect, test } from '@playwright/test';
import { zip } from '../../src/features/workbench/export';

const xml = (name: string, value: string) => ({ name, data: new TextEncoder().encode(value) });
const docx = () =>
  zip([
    xml(
      '[Content_Types].xml',
      '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
    ),
    xml(
      '_rels/.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    ),
    xml(
      'word/_rels/document.xml.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
    ),
    xml(
      'word/styles.xml',
      '<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>',
    ),
    xml(
      'word/document.xml',
      '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Original canvas bag specification</w:t></w:r></w:p><w:sectPr/></w:body></w:document>',
    ),
  ]);
const xlsx = () =>
  zip([
    xml(
      '[Content_Types].xml',
      '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    ),
    xml(
      '_rels/.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    ),
    xml(
      'xl/workbook.xml',
      '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="BOM" sheetId="1" r:id="rId1"/></sheets></workbook>',
    ),
    xml(
      'xl/_rels/workbook.xml.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    ),
    xml(
      'xl/worksheets/sheet1.xml',
      '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="n"><v>2</v></c><c r="B1" t="n"><v>3</v></c><c r="C1"><f>A1*B1</f><v>6</v></c></row></sheetData></worksheet>',
    ),
  ]);

test('real inline Office editor saves native files, previews current values, and retains history', async ({
  page,
}, info) => {
  await page.goto('/');
  await page.getByLabel('账号邮箱').fill('demo@navowork.local');
  await page.getByLabel('密码').fill('ChangeMe123!');
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  const base = '/api/v1/workspaces/ws_demo';
  const response = await page.request.post(`${base}/inquiries`, {
    data: {
      title: 'Office browser acceptance',
      customer: 'Office Buyer',
      originalText: 'Please review a canvas bag specification.',
    },
  });
  expect(response.ok()).toBeTruthy();
  const inquiry = await response.json();
  const path = `${base}/inquiries/${inquiry.id}`;
  const office = `${path}/workbench/office`;
  for (const [name, data, mime] of [
    [
      'spec.docx',
      docx(),
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ],
    ['cost.xlsx', xlsx(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  ] as const) {
    const uploaded = await page.request.post(`${path}/evidence`, {
      multipart: { file: { name, mimeType: mime, buffer: Buffer.from(data) } },
    });
    expect(uploaded.ok()).toBeTruthy();
  }
  await page.goto(`/inquiries/${inquiry.id}`);
  await page.getByText('文件编辑与预览', { exact: false }).first().click();
  await page.getByLabel('选择 Office 原件').selectOption({ label: 'spec.docx' });
  await page.getByRole('button', { name: '创建工作副本' }).click();
  await expect(page.getByLabel('段落 1', { exact: true })).toHaveValue(
    'Original canvas bag specification',
  );
  await page
    .getByLabel('段落 1', { exact: true })
    .fill('Reviewed recycled canvas bag specification');
  await page.getByRole('button', { name: /保存新版本/ }).click();
  await expect(page.getByRole('status')).toContainText('V2');
  await expect(page.getByLabel('段落 1', { exact: true })).toHaveValue(
    'Reviewed recycled canvas bag specification',
  );
  const listing = await (await page.request.get(office)).json();
  const saved = listing.documents.find((item: { name: string }) => item.name === 'spec.docx');
  const savedView = await (await page.request.get(`${office}/${saved.documentId}`)).json();
  expect(savedView.preview.paragraphs[0].text).toBe('Reviewed recycled canvas bag specification');
  expect((await page.request.get(saved.downloadUrl)).headers()['content-type']).toContain(
    'wordprocessingml',
  );
  await page.getByLabel('文件版本').selectOption('1');
  await expect(page.getByLabel('段落 1', { exact: true })).toHaveValue(
    'Original canvas bag specification',
  );
  await expect(page.getByLabel('段落 1', { exact: true })).toBeDisabled();
  await page.getByLabel('选择 Office 原件').selectOption({ label: 'cost.xlsx' });
  await page.getByRole('button', { name: '创建工作副本' }).click();
  await page.getByRole('button', { name: 'BOM A1', exact: true }).click();
  await page.getByLabel('单元格内容', { exact: true }).fill('5');
  await page.getByRole('button', { name: '应用单元格修改' }).click();
  await page.getByRole('button', { name: /保存新版本/ }).click();
  await expect(page.getByRole('button', { name: 'BOM C1', exact: true })).toHaveText('15');
  await expect(page.getByText('跨文件同步 · 2 次变更', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('office-inline-editor.png'), fullPage: true });
  const errors = page.locator('.office-files .error-notice');
  await expect(errors).toHaveCount(0);
});

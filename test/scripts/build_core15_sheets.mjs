import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const moduleDir = process.env.CODEX_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const resolveBundled = createRequire(path.join(moduleDir, '__core15__.cjs'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(resolveBundled.resolve('@oai/artifact-tool')).href);
const content = JSON.parse((await fs.readFile(path.join(root, 'scripts/core15_content.json'), 'utf8')).replace(/^\uFEFF/, ''));
const out = path.join(root, 'core15');
const qa = path.join(root, '.qa/core15');
await fs.mkdir(out, { recursive: true });
await fs.mkdir(qa, { recursive: true });

function base(title, name, lastRow) {
  const wb = Workbook.create();
  const s = wb.worksheets.add(name);
  s.showGridLines = false;
  s.getRange(`A1:C${lastRow}`).format = { font: { name: 'Arial', size: 10, color: '#263A49' }, verticalAlignment: 'center' };
  s.getRange('A:A').format.columnWidth = 32;
  s.getRange('B:B').format.columnWidth = 24;
  s.getRange('C:C').format.columnWidth = 56;
  s.getRange(`1:${lastRow}`).format.rowHeight = 25;
  s.getRange('A2').values = [[title]];
  s.getRange('A2:C2').format.font = { name: 'Arial', size: 15, bold: true, color: '#17324D' };
  s.getRange('2:2').format.rowHeight = 29;
  s.getRange('A3').values = [['SIMULATED MOCK - BAG-2026-DE-001 - 2026-10-31']];
  s.getRange('A3:C3').format.font = { name: 'Arial', size: 9, color: '#8A3B12' };
  return [wb, s];
}

function band(s, r, labels) {
  s.getRange(`A${r}:C${r}`).values = [labels];
  s.getRange(`A${r}:C${r}`).format = { fill: '#234A6B', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center', verticalAlignment: 'center' };
}

async function save(wb, sheet, filename, end) {
  wb.recalculate();
  const inspection = await wb.inspect({ kind: 'table', sheetId: sheet.name, range: `A1:C${end}`, include: 'values,formulas', tableMaxRows: end, tableMaxCols: 3, maxChars: 12000 });
  await fs.writeFile(path.join(qa, filename + '.inspect.ndjson'), inspection.ndjson);
  const errors = await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'formula error scan' });
  await fs.writeFile(path.join(qa, filename + '.errors.ndjson'), errors.ndjson);
  const image = await wb.render({ sheetName: sheet.name, range: `A1:C${end}`, scale: 1.4, format: 'png' });
  await fs.writeFile(path.join(qa, filename + '.png'), new Uint8Array(await image.arrayBuffer()));
  const file = await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(out, filename));
  const sidecar = path.join(out, filename + '.inspect.ndjson');
  try { await fs.rename(sidecar, path.join(qa, filename + '.export-inspect.ndjson')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}

const [supplierWb, supplier] = base('Supplier Quotation V3', 'Supplier Quote V3', 27);
band(supplier, 6, ['Field', 'Value', 'Scope / source']);
supplier.getRange('A7:C24').values = [
  ['Supplier', 'Factory A (fictional)', 'All identities and terms are simulated'],
  ['Case', 'BAG-2026-DE-001', 'core15_closeout_2026-10-31'],
  ['Offer reference', 'FA-WB26-V3', 'E02 supplier final confirmation'],
  ['Product', 'WB-26 navy backpack', 'Tech Pack V3 / Sample S03'],
  ['Quantity (pieces)', 3000, 'One style / one navy color'],
  ['Manufacturing (CNY/pc)', 44, 'Includes woven 60 x 18 mm logo'],
  ['Custom box (CNY/pc)', 5, '46 x 33 x 8 cm; folded backpack'],
  ['Factory subtotal (CNY/pc)', null, 'Manufacturing + retail box; local charges excluded'],
  ['Currency', 'CNY', 'Price unit: per piece'],
  ['MOQ (pieces)', 3000, 'Custom box MOQ also 3000 pieces'],
  ['Production estimate (days)', 28, 'Calendar days; conditional, not guaranteed arrival'],
  ['Start conditions', 'Sample + deposit + release', 'All three prerequisites must be satisfied'],
  ['Specification', 'Tech Pack V3', '44 x 30 x 14 cm in use; tolerance +/-1 cm'],
  ['Logo', '60 x 18 mm woven', 'Front center; tolerance +/-1 mm'],
  ['Packing', '5 pcs / carton', 'Outer carton 48 x 35 x 42 cm'],
  ['Validity through', new Date('2026-11-30T00:00:00Z'), 'Date-only validity; 2026-11-30'],
  ['Excluded local allocation', 'CNY 4.00 / pc estimate', 'Seller assumption, not a factory charge'],
  ['Evidence', 'E02', 'evidence/ supplier final confirmation email'],
];
supplier.getRange('B14').formulas = [['=SUM(B12:B13)']];
supplier.getRange('B12:B14').setNumberFormat('"CNY "0.00');
supplier.getRange('B11').setNumberFormat('#,##0');
supplier.getRange('B16:B17').setNumberFormat('#,##0');
supplier.getRange('B22').setNumberFormat('yyyy-mm-dd');
supplier.getRange('A7:A24').format.font.bold = true;
supplier.getRange('A25').values = [['No production start or payment receipt is recorded.']];
supplier.getRange('A25:C25').format.font.color = '#8A3B12';
supplier.getRange('B11:B13').format.fill = '#FFF3DA';
await save(supplierWb, supplier, content.categories.find(c => c.id === 8).filename, 25);

const [costWb, cost] = base('Product Costing V3', 'Costing V3', 33);
band(cost, 5, ['Result', 'Value', 'Basis']);
cost.getRange('A6:C10').values = [
  ['Customer unit price (USD)', null, 'Gross margin pricing; round up to cents'],
  ['Customer order total (USD)', null, 'Rounded unit price x quantity'],
  ['Deposit due (USD)', null, 'Amount due only; receipt not evidenced'],
  ['Balance due (USD)', null, 'Order total less deposit due'],
  ['Implied gross margin', null, 'Margin after unit-price rounding'],
];
band(cost, 14, ['Cost input', 'CNY per piece', 'Source']);
cost.getRange('A15:C18').values = [
  ['Manufacturing incl. woven logo', 44, 'E02; Supplier Quote V3 B12'],
  ['Custom printed color box', 5, 'E02; Supplier Quote V3 B13'],
  ['Allocated local charges', 4, 'E05; simulated seller estimate'],
  ['Total unit cost', null, 'All three required cost inputs'],
];
band(cost, 21, ['Commercial input', 'Value', 'Source / meaning']);
cost.getRange('A22:C25').values = [
  ['Quantity (pieces)', 3000, 'Original inquiry.eml; customer order scope'],
  ['FX CNY per USD', 7.2, 'E05; fixed simulation assumption'],
  ['Target gross margin', 0.2, 'E05; margin, not markup'],
  ['Deposit fraction', 0.3, 'Customer terms; amount due, not received'],
];
cost.getRange('B18').formulas = [['=IF(OR(COUNT(B15:B17)<3,MIN(B15:B17)<0),"INPUT REQUIRED",SUM(B15:B17))']];
cost.getRange('B6').formulas = [['=IF(OR(NOT(ISNUMBER(B18)),NOT(ISNUMBER(B23)),B23<=0,NOT(ISNUMBER(B24)),B24<0,B24>=1),"INPUT REQUIRED",ROUNDUP(B18/B23/(1-B24),2))']];
cost.getRange('B7').formulas = [['=IF(OR(NOT(ISNUMBER(B6)),NOT(ISNUMBER(B22)),B22<=0,MOD(B22,1)<>0),"INPUT REQUIRED",ROUND(B6*B22,2))']];
cost.getRange('B8').formulas = [['=IF(OR(NOT(ISNUMBER(B7)),NOT(ISNUMBER(B25)),B25<0,B25>1),"INPUT REQUIRED",ROUND(B7*B25,2))']];
cost.getRange('B9').formulas = [['=IF(OR(NOT(ISNUMBER(B7)),NOT(ISNUMBER(B8))),"INPUT REQUIRED",B7-B8)']];
cost.getRange('B10').formulas = [['=IF(OR(NOT(ISNUMBER(B6)),B6=0),"INPUT REQUIRED",1-B18/B23/B6)']];
cost.getRange('B6:B9').setNumberFormat('"USD "#,##0.00');
cost.getRange('B10').setNumberFormat('0.00%');
cost.getRange('B15:B18').setNumberFormat('"CNY "0.00');
cost.getRange('B22').setNumberFormat('#,##0');
cost.getRange('B23').setNumberFormat('0.00');
cost.getRange('B24:B25').setNumberFormat('0.0%');
cost.getRange('B15:B17').format.fill = '#FFF3DA';
cost.getRange('B22:B25').format.fill = '#FFF3DA';
cost.getRange('A6:A10').format.font.bold = true;
cost.getRange('A18:C18').format.font.bold = true;
cost.getRange('A28:C31').values = [
  ['Pricing approval', 'V3 only (simulated)', 'E06; Quotation V3 price approval only'],
  ['Production release', 'Blocked', 'Deposit receipt + internal release pending'],
  ['Arrival target', '45 days to Hamburg', 'Customer request; not a confirmed arrival date'],
  ['Editable cells', 'Amber input cells', 'Missing or invalid inputs show INPUT REQUIRED'],
];

// Exercise input-dependent behavior, then restore the saved V3 scenario.
const liveChecks = [];
const value = cell => cost.getRange(cell).values[0][0];
for (const [inputCell, inputValue, outputCell, expected] of [
  ['B16', 2, 'B6', 8.69], ['B16', null, 'B6', 'INPUT REQUIRED'],
  ['B23', 0, 'B6', 'INPUT REQUIRED'], ['B24', 1, 'B6', 'INPUT REQUIRED'],
]) {
  const original = value(inputCell);
  cost.getRange(inputCell).values = [[inputValue]];
  costWb.recalculate();
  const actual = value(outputCell);
  if (typeof expected === 'number' ? Math.abs(actual - expected) > 1e-9 : actual !== expected) throw new Error(`Recalculation failed ${inputCell}: ${actual}`);
  liveChecks.push({ inputCell, inputValue, outputCell, expected, actual });
  cost.getRange(inputCell).values = [[original]];
}
costWb.recalculate();
for (const [cell, expected] of [['B6', 9.21], ['B7', 27630], ['B8', 8289], ['B9', 19341], ['B18', 53]]) {
  if (Math.abs(value(cell) - expected) > 1e-8) throw new Error(`${cell} expected ${expected}, got ${value(cell)}`);
}
await fs.writeFile(path.join(qa, 'costing-live-checks.json'), JSON.stringify(liveChecks, null, 2));
await save(costWb, cost, content.categories.find(c => c.id === 9).filename, 31);
console.log('Created two XLSX fixtures; recalculation and missing/invalid-input checks passed.');

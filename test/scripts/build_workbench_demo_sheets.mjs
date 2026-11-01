import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const bundle = process.env.CODEX_NODE_MODULES || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const requireBundled = createRequire(path.join(bundle, '_resolve.cjs'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(requireBundled.resolve('@oai/artifact-tool')).href);
const pack = path.join(repo, 'test/workbench_demo');
const qa = path.join(repo, 'test/.qa/workbench_demo');
const { columns, sheets } = JSON.parse(await fs.readFile(path.join(pack, 'sheet_content.json'), 'utf8'));
await fs.mkdir(qa, { recursive: true });
const checks = [];

function style(sheet, range, widths, header = 1) {
  sheet.showGridLines = false;
  sheet.getRange(range).format = { font: { name: 'Arial', size: 10, color: '#263A49' }, verticalAlignment: 'center' };
  sheet.getRange(range).format.rowHeight = 27;
  for (const [col, width] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidth = width;
  const end = range.split(':')[1].replace(/[0-9]/g, '');
  sheet.getRange(`A${header}:${end}${header}`).format = { fill: '#234A6B', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center' };
}

for (const item of sheets) {
  const wb = Workbook.create();
  const s = wb.worksheets.add(item.type === 'bom' ? 'BOM' : item.type.startsWith('costing') ? 'Costing' : 'Supplier');
  let region;
  if (item.type === 'bom') {
    // Exact backend BOM row schema starts at A1; no decorative rows before headers.
    s.getRange('A1:J1').values = [[...columns, 'lineCostCny']];
    s.getRange(`A2:I${item.rows.length + 1}`).values = item.rows;
    item.rows.forEach((_, i) => {
      const r = i + 2;
      s.getRange(`J${r}`).formulas = [[item.key === 'bom_missing_price'
        ? `=IF(AND(ISNUMBER(D${r}),ISNUMBER(G${r}),ISNUMBER(H${r})),ROUND(D${r}*G${r}*(1+H${r}),4),"INPUT REQUIRED")`
        : `=ROUND(D${r}*G${r}*(1+H${r}),4)`]];
    });
    const total = item.rows.length + 2;
    s.getRange(`I${total}`).values = [['TOTAL']];
    s.getRange(`J${total}`).formulas = [[item.key === 'bom_missing_price'
      ? `=IF(COUNT(J2:J${total-1})=${item.rows.length},ROUND(SUM(J2:J${total-1}),4),"INPUT REQUIRED")`
      : `=ROUND(SUM(J2:J${total-1}),4)`]];
    s.getRange(`A${total+2}`).values = [['SIMULATED. NL-ALLOC-V1 / TP-NL-V1 or V2. Export customs and inspection NOT priced.']];
    s.getRange(`D2:D${total-1}`).setNumberFormat('0.000');
    s.getRange(`G2:G${total-1}`).setNumberFormat('0.00');
    s.getRange(`H2:H${total-1}`).setNumberFormat('0.0%');
    s.getRange(`J2:J${total}`).setNumberFormat('0.00');
    region = `A1:J${total+2}`;
    style(s, region, { A: 19, B: 25, C: 38, D: 21, E: 10, F: 21, G: 18, H: 13, I: 20, J: 18 });
    s.getRange(`D2:D${total-1}`).format.fill = '#FFF3DA';
    s.getRange(`G2:H${total-1}`).format.fill = '#FFF3DA';
    s.freezePanes.freezeRows(1);
    wb.recalculate();
    const expected = item.key === 'bom_V1' ? 50 : item.key === 'bom_V2' ? 53 : 'INPUT REQUIRED';
    if (s.getRange(`J${total}`).values[0][0] !== expected) throw new Error(`${item.key} invalid total ${JSON.stringify(s.getRange(`J${total}`).values)}`);
    checks.push({ key: item.key, expected, actual: s.getRange(`J${total}`).values[0][0] });
    if (item.key === 'bom_V1') {
      s.getRange('G11').values = [[5]]; wb.recalculate();
      const changed = s.getRange(`J${total}`).values[0][0];
      if (changed !== 53) throw new Error('BOM packaging change did not recalculate');
      checks.push({ key: 'packaging_2_to_5', actual: changed, expected: 53 });
      s.getRange('G11').values = [[2]];
    }
  } else if (item.type === 'supplier') {
    const [manufacture, packing, local, moq, days] = item.values;
    s.getRange('A1:C14').values = [
      ['Field', 'Value', 'Scope'], ['Supplier', item.title, 'SIMULATED supplier identity'],
      ['Manufacturing CNY/pc', manufacture, 'Includes logo'], ['Packaging CNY/pc', packing, 'Replaces previous packaging'],
      ['Local handling CNY/pc', local, 'Domestic only; customs and inspection excluded'],
      ['Scope subtotal CNY/pc', null, 'Conditional scope; not complete export cost'],
      ['MOQ pcs', moq, 'Do not replace customer requested quantity'], ['Production estimate days', days, 'After sample approval and deposit; transit excluded'],
      ['Valid until', new Date('2026-11-30T00:00:00Z'), 'Date only'], ['Currency', 'CNY', 'Per piece'],
      ['Payment', '30% / 70% before shipment', 'No funds received'],
      ['Specification', item.key === 'supplier_A_V2' ? 'TP-NL-V2 / CB-02-DEMO' : 'TP-NL-V1 / standard packing', 'B is not color-box comparable'],
      ['Missing charges', 'customs and inspection', 'UNKNOWN; do not zero-fill'],
      ['Source', item.key, 'New simulated quote; not an old supplier email extraction'],
    ];
    s.getRange('B6').formulas = [['=SUM(B3:B5)']];
    s.getRange('B3:B6').setNumberFormat('0.00');
    s.getRange('B9').setNumberFormat('yyyy-mm-dd');
    region = 'A1:C14';
    style(s, region, { A: 29, B: 39, C: 65 });
  } else {
    s.getRange('A1:C19').values = [
      ['Metric', 'Value', 'Basis'], ['Unit price USD', null, 'Ceiling to cents before order total'],
      ['Order total USD', null, 'Rounded unit price x quantity'], ['Deposit due USD', null, '30%; receipt unknown'],
      ['Balance due USD', null, 'Before shipment; due only'], ['Cost scope CNY/pc', null, 'Excludes unpriced inspection / customs'],
      ['Manufacturing CNY/pc', 44, 'NL-ALLOC-V1'], ['Packaging CNY/pc', 2, 'Change to 5 for color box'],
      ['Domestic handling CNY/pc', 4, 'NL-FIN-V1; not export charges'], ['FX CNY per USD', 7.2, 'Simulated finance assumption'],
      ['Target gross margin', .2, 'Margin, not markup'], ['Quantity pcs', 3000, 'Positive integer'],
      ['Deposit ratio', .3, 'Contract draft assumption'], ['Excluded charges', 'UNKNOWN', 'Inspection, customs; conditional quote'],
      ['Sample / contract / deposit', 'PENDING', 'PI draft does not authorize production'],
      ['Source', 'NL-ALLOC-V1 / NL-FIN-V1', 'SIMULATED sources, 2026-11-01'],
      ['Scope', 'INTERNAL COSTS', 'Do not include in customer-facing asset bundle'],
      ['Version', 'TP-NL-V1 baseline', 'Changing inputs creates a working scenario, not customer acceptance'],
      ['Quote status', 'CONDITIONAL DRAFT', 'No external sending or approval'],
    ];
    s.getRange('B6').formulas = [['=IF(COUNT(B7:B9)=3,SUM(B7:B9),"INPUT REQUIRED")']];
    s.getRange('B2').formulas = [['=IF(AND(ISNUMBER(B6),ISNUMBER(B10),B10>0,ISNUMBER(B11),B11>=0,B11<1,ISNUMBER(B12),B12>0,MOD(B12,1)=0),ROUNDUP(B6/B10/(1-B11),2),"INPUT REQUIRED")']];
    s.getRange('B3').formulas = [['=IF(ISNUMBER(B2),B2*B12,"INPUT REQUIRED")']];
    s.getRange('B4').formulas = [['=IF(AND(ISNUMBER(B3),ISNUMBER(B13),B13>=0,B13<=1),ROUND(B3*B13,2),"INPUT REQUIRED")']];
    s.getRange('B5').formulas = [['=IF(AND(ISNUMBER(B3),ISNUMBER(B4)),B3-B4,"INPUT REQUIRED")']];
    region = 'A1:C19'; style(s, region, { A: 31, B: 36, C: 73 });
    s.getRange('B2:B10').setNumberFormat('#,##0.00');
    s.getRange('B11').setNumberFormat('0.0%'); s.getRange('B12').setNumberFormat('#,##0'); s.getRange('B13').setNumberFormat('0.0%');
    s.getRange('B7:B13').format.fill = '#FFF3DA';
    s.getRange('B2:B6').conditionalFormats.add('containsText', { text: 'INPUT REQUIRED', format: { fill: '#FEE2E2', font: { color: '#991B1B', bold: true } } });
    for (const [cell, value, expected] of [['B8', 5, 9.21], ['B8', null, 'INPUT REQUIRED'], ['B8', 0, 8.34], ['B10', 0, 'INPUT REQUIRED'], ['B11', 1, 'INPUT REQUIRED'], ['B12', 0, 'INPUT REQUIRED']]) {
      s.getRange('B8').values = [[2]]; s.getRange('B10').values = [[7.2]]; s.getRange('B11').values = [[.2]]; s.getRange('B12').values = [[3000]];
      s.getRange(cell).values = [[value]]; wb.recalculate();
      const actual = s.getRange('B2').values[0][0];
      if (actual !== expected) throw new Error(`${cell}=${value}: ${actual} != ${expected}`);
      checks.push({ key: `costing_${cell}_${value}`, expected, actual });
    }
    s.getRange('B8').values = [[2]]; s.getRange('B10').values = [[7.2]]; s.getRange('B11').values = [[.2]]; s.getRange('B12').values = [[3000]];
    if (item.type === 'costing_simple') {
      // The current app editor intentionally supports a small numeric formula subset.
      // Keep the guarded Excel version separately; this fully populated variant edits in the app.
      s.getRange('B6').formulas = [['=SUM(B7:B9)']];
      s.getRange('B2').formulas = [['=ROUNDUP(B6/B10/(1-B11),2)']];
      s.getRange('B3').formulas = [['=B2*B12']];
      s.getRange('B4').formulas = [['=ROUND(B3*B13,2)']];
      s.getRange('B5').formulas = [['=B3-B4']];
      s.getRange('C18').values = [['App editor variant; validate all inputs before using edited results']];
    }
  }
  wb.recalculate();
  const scan = await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 20 }, summary: 'formula errors' });
  await fs.writeFile(path.join(qa, `${item.key}.errors.ndjson`), scan.ndjson);
  const view = await wb.render({ sheetName: s.name, range: region, scale: 1.25, format: 'png' });
  const bytes = new Uint8Array(await view.arrayBuffer());
  await fs.writeFile(path.join(qa, `${item.key}.png`), bytes);
  if (item.key === 'bom_V1' || item.key === 'bom_missing_price') {
    await fs.writeFile(path.join(pack, 'assets', item.key === 'bom_V1' ? 'bom_image_clear.png' : 'bom_image_missing.png'), bytes);
  }
  const exported = await SpreadsheetFile.exportXlsx(wb);
  await exported.save(path.join(pack, 'assets', `${item.key}.xlsx`));
  // Artifact-tool versions may emit an inspection sidecar. Keep it outside the business corpus.
  const sidecar = path.join(pack, 'assets', `${item.key}.xlsx.inspect.ndjson`);
  try { await fs.rename(sidecar, path.join(qa, `${item.key}.export-inspect.ndjson`)); }
  catch (e) { if (e.code !== 'ENOENT') throw e; }
}
await fs.writeFile(path.join(qa, 'sheet-recalculation.json'), JSON.stringify(checks, null, 2));
console.log(JSON.stringify({ workbooks: sheets.length, recalculationChecks: checks.length }));

import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const out = new URL('../inputs/BAG-2026-DE-001/factory-A-quote.xlsx', import.meta.url);
const wb = Workbook.create();
const ws = wb.worksheets.add('Factory A Quote');
ws.showGridLines = false;
ws.mergeCells('A1:C1');
ws.getRange('A1').values = [['Factory A - Backpack quotation']];
ws.mergeCells('A2:C2');
ws.getRange('A2').values = [['SIMULATED SOURCE - Not a commercial offer']];
ws.getRange('A3:C16').values = [
  ['Field', 'Value', 'Source note'],
  ['Supplier', 'Factory A (fictional)', 'Email domain factory-a.invalid'],
  ['Quote reference', 'FA-2609-31', 'Simulated quotation reference'],
  ['Issue date', '2026-10-06', 'Date only'],
  ['Validity through', '2026-11-30', 'Date only'],
  ['Currency', 'CNY', 'Chinese yuan'],
  ['Product / quantity scope', 'Custom backpack / 3,000 pieces', 'Model pending'],
  ['Base manufacturing price', 44, 'Per piece; woven logo included'],
  ['Standard packaging', 2, 'Per piece; ordinary paper box'],
  ['Estimated local allocation', 4, 'Per piece; demo estimate'],
  ['Estimated cost basis', null, 'Base + box + estimated local allocation'],
  ['MOQ', 1000, 'Pieces per style; color split to reconfirm'],
  ['Estimated production time', 28, 'Calendar days after approved sample; not a guarantee'],
  ['Custom color box', 'Not priced in this quotation', 'Requires separate written confirmation'],
];
ws.getRange('B13').formulas = [['=SUM(B10:B12)']];
ws.getRange('A1:C1').format = { fill: '#FFFFFF', font: { name: 'Arial', size: 15, bold: true, color: '#17324D' }, verticalAlignment: 'center' };
ws.getRange('A2:C2').format = { fill: '#FCE8D5', font: { name: 'Arial', size: 10, bold: true, color: '#8A3B12' }, verticalAlignment: 'center' };
ws.getRange('A3:C3').format = { fill: '#234A6B', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, verticalAlignment: 'center' };
ws.getRange('A4:C16').format = { font: { name: 'Arial', size: 10, color: '#24364B' }, verticalAlignment: 'center', wrapText: true };
ws.getRange('A4:A16').format.font = { name: 'Arial', size: 10, bold: true, color: '#24364B' };
ws.getRange('B10:B13').format.numberFormat = '"CNY "0.00';
ws.getRange('B10:B13').format.horizontalAlignment = 'right';
ws.getRange('A3:C16').format.borders = { insideHorizontal: { style: 'thin', color: '#D6DEE8' }, bottom: { style: 'thin', color: '#D6DEE8' } };
ws.getRange('A:A').format.columnWidth = 31;
ws.getRange('B:B').format.columnWidth = 40;
ws.getRange('C:C').format.columnWidth = 48;
ws.getRange('1:1').format.rowHeight = 27;
ws.getRange('2:2').format.rowHeight = 22;
ws.getRange('3:16').format.rowHeight = 29;
ws.freezePanes.freezeRows(3);
wb.recalculate();
const preview = await wb.render({ sheetName: 'Factory A Quote', autoCrop: 'all', scale: 1, format: 'png' });
await fs.writeFile(new URL('../.qa/factory-A-quote.png', import.meta.url), new Uint8Array(await preview.arrayBuffer()));
const inspection = await wb.inspect({ kind: 'table', sheetId: 'Factory A Quote', range: 'A3:C16', include: 'values,formulas', tableMaxRows: 16, tableMaxCols: 3, maxChars: 5000 });
console.log(inspection.ndjson);
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(fileURLToPath(out));

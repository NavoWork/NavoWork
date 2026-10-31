import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve('demo/competition_v1');
const pack = JSON.parse(await fs.readFile(path.join(root, 'pack.json'), 'utf8'));
const book = Workbook.create();
const summary = book.worksheets.add('Internal Costing');
const sources = pack.offers.map(o => book.worksheets.add(o.sheet));
for (const sheet of [summary, ...sources]) {
  sheet.showGridLines = false;
  sheet.getRange('A1:K25').format.font.name = 'Arial';
  sheet.getRange('A1:K25').format.font.size = 11;
  sheet.getRange('A1:K25').format.rowHeight = 25;
  sheet.getRange('A1:K25').format.columnWidth = 17;
}
summary.getRange('A2').values = [['Simulated quotation comparison']];
summary.getRange('A2').format.font.size = 16;
summary.getRange('A3').values = [['Competition fixtures. PRD section 6; local costs, FX and margins are internal assumptions.']];
summary.getRange('A5:K5').values = [['Offer', 'Base CNY/pc', 'Pack CNY/pc', 'Local CNY/pc', 'Cost CNY/pc', 'CNY/USD', 'Margin', 'USD/pc', 'Quantity', 'Goods USD', 'Lead days']];
summary.getRange('A5:K5').format.fill = '#253858';
summary.getRange('A5:K5').format.font.color = '#ffffff';
summary.getRange('A5:K5').format.font.bold = true;
summary.getRange('A6:A9').format.columnWidth = 22;
for (const [index, offer] of pack.offers.entries()) {
  const sheet = sources[index];
  sheet.getRange('A2').values = [[`${offer.sheet} / simulated source quote`]];
  sheet.getRange('A2').format.font.size = 16;
  sheet.getRange('A4:B4').values = [['Supplier field', 'Quoted value']];
  sheet.getRange('A4:B4').format.fill = '#253858';
  sheet.getRange('A4:B4').format.font.color = '#ffffff';
  sheet.getRange('A5:B15').values = [
    ['Source ID', offer.key.toUpperCase()], ['Base CNY per piece', Number(offer.baseCny)],
    ['Packaging CNY per piece', Number(offer.packagingCny)], ['MOQ pieces', offer.moq],
    ['Estimated production days', offer.leadDays], ['Valid until', '2026-11-14'],
    ['Product', offer.key === 'mx1' ? 'CT-MX-0600 canvas bag' : 'BP-DE-3000 backpack'],
    ['Packaging', offer.key === 'a2' ? 'CMYK color box, CB-02' : offer.key === 'mx1' ? 'Paper band' : 'Plain kraft box'],
    ['Starts after', 'Final sample/artwork + payment conditions'],
    ['Currency / scope', 'CNY / factory and packaging, no sea freight'],
    ['Approval status', 'Simulated supplier statement; requires human review'],
  ];
  sheet.getRange('A4:A15').format.columnWidth = 30;
  sheet.getRange('B4:B15').format.columnWidth = 62;
  sheet.getRange('B6:B7').setNumberFormat('0.00');
  sheet.getRange('B8:B9').setNumberFormat('#,##0');
  const r = index + 6;
  summary.getRange(`A${r}:K${r}`).values = [[offer.sheet, null, null, Number(offer.localCny), null, 7.2, offer.key === 'mx1' ? .25 : .2, null, offer.key === 'mx1' ? 600 : 3000, null, null]];
  summary.getRange(`B${r}:C${r}`).formulas = [[`='${sheet.name}'!B6`, `='${sheet.name}'!B7`]];
  summary.getRange(`E${r}`).formulas = [[`=SUM(B${r}:D${r})`]];
  summary.getRange(`H${r}`).formulas = [[`=ROUNDUP(E${r}/F${r}/(1-G${r}),2)`]];
  summary.getRange(`J${r}`).formulas = [[`=H${r}*I${r}`]];
  summary.getRange(`K${r}`).formulas = [[`='${sheet.name}'!B9`]];
}
summary.getRange('B6:F9').setNumberFormat('0.00');
summary.getRange('G6:G9').setNumberFormat('0%');
summary.getRange('H6:H9').setNumberFormat('0.00');
summary.getRange('I6:I9').setNumberFormat('#,##0');
summary.getRange('J6:J9').setNumberFormat('#,##0.00');
summary.getRange('D6:D9').format.fill = '#fff3cc';
summary.getRange('F6:G9').format.fill = '#fff3cc';
summary.getRange('I6:I9').format.fill = '#fff3cc';
summary.getRange('A12').values = [['Change in A quotation (USD/pc)']];
summary.getRange('D12').formulas = [['=H8-H6']];
summary.getRange('D12').setNumberFormat('0.00');
summary.getRange('A13').values = [['Change in goods total (USD)']];
summary.getRange('D13').formulas = [['=J8-J6']];
summary.getRange('D13').setNumberFormat('#,##0.00');
summary.getRange('A16').values = [['FOB Ningbo, Incoterms 2020. Goods only; freight, insurance and import tax require separate confirmation.']];
summary.getRange('A17').values = [['Yellow cells: internal assumptions. Supplier sources do not confirm our exchange rate or target margin.']];
summary.getRange('A18').values = [['MX quantity 300 is below MOQ 500; the 600-piece scenario requires customer quantity confirmation.']];
book.recalculate();
console.log((await book.inspect({kind:'table',range:'Internal Costing!H6:K9',include:'values',tableMaxRows:4,tableMaxCols:4})).ndjson);
await fs.mkdir('demo/.previews', {recursive:true});
for (const sheet of [summary, ...sources]) {
  const preview = await book.render({ sheetName: sheet.name, range: sheet === summary ? 'A1:K19' : 'A1:C17', scale: 1 });
  await fs.writeFile(`demo/.previews/${sheet.name.replaceAll(' ','-')}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(book);
await file.save(path.join(root,'sources/Supplier_Quotes.xlsx'));
console.log('Saved Supplier_Quotes.xlsx');

import {
  artifacts,
  calculate,
  caseId,
  specFields,
  usd,
  type ArtifactKind,
  type Snapshot,
  type WorkbenchState,
} from './model';

const escape = (value: unknown) =>
  String(value).replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[char]!,
  );
const encode = (text: string) => new TextEncoder().encode(text);
// Uncompressed ZIP keeps browser exports dependency-free. All names use UTF-8.
export function zip(files: { name: string; data: Uint8Array }[]): Uint8Array<ArrayBuffer> {
  const parts: Uint8Array[] = [],
    central: Uint8Array[] = [];
  let offset = 0;
  for (const file of files) {
    const name = encode(file.name);
    let crc = 0xffffffff;
    for (const byte of file.data) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
    crc = (crc ^ 0xffffffff) >>> 0;
    const header = new Uint8Array(30 + name.length),
      h = new DataView(header.buffer);
    h.setUint32(0, 0x04034b50, true);
    h.setUint16(4, 20, true);
    h.setUint16(6, 0x800, true);
    h.setUint16(12, 0x21, true);
    h.setUint32(14, crc, true);
    h.setUint32(18, file.data.length, true);
    h.setUint32(22, file.data.length, true);
    h.setUint16(26, name.length, true);
    header.set(name, 30);
    const directory = new Uint8Array(46 + name.length),
      d = new DataView(directory.buffer);
    d.setUint32(0, 0x02014b50, true);
    d.setUint16(4, 20, true);
    d.setUint16(6, 20, true);
    d.setUint16(8, 0x800, true);
    d.setUint16(14, 0x21, true);
    d.setUint32(16, crc, true);
    d.setUint32(20, file.data.length, true);
    d.setUint32(24, file.data.length, true);
    d.setUint16(28, name.length, true);
    d.setUint32(42, offset, true);
    directory.set(name, 46);
    parts.push(header, file.data);
    central.push(directory);
    offset += header.length + file.data.length;
  }
  const centralSize = central.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22),
    e = new DataView(end.buffer);
  e.setUint32(0, 0x06054b50, true);
  e.setUint16(8, files.length, true);
  e.setUint16(10, files.length, true);
  e.setUint32(12, centralSize, true);
  e.setUint32(16, offset, true);
  const result = new Uint8Array(offset + centralSize + end.length);
  let cursor = 0;
  for (const part of [...parts, ...central, end]) {
    result.set(part, cursor);
    cursor += part.length;
  }
  return result;
}
type Row = (string | number)[];
export function artifactRows(kind: ArtifactKind, snapshot: Snapshot): Row[] {
  const price = calculate(snapshot.costs),
    c = snapshot.costs;
  const metadata: Row[] = [
    [artifacts.find((a) => a.id === kind)!.title, `V${snapshot.version} · 演示草稿`],
    ['Case', caseId],
    ['客户', 'Michael Weber · Germany'],
    [
      '状态',
      snapshot.approved ? '内部报价已审核（演示），未对外发送；生产未放行' : '草稿 · 待人工审核',
    ],
    ['数量', c.quantity],
    ['贸易条款', snapshot.specs.terms],
    ['包装', snapshot.packaging],
  ];
  const pending: Row[] = [
    ['待确认', '面料、尺寸、LOGO 工艺、样品批准、MOQ、生产交期与到港可行性'],
    ['注意', '所有数据均为演示数据。FOB Ningbo 不代表承诺 45 天到港。'],
  ];
  let content: Row[];
  switch (kind) {
    case 'spec':
      content = specFields.map(([key, title]) => [
        title,
        key === 'quantity'
          ? c.quantity
          : key === 'packaging'
            ? snapshot.packaging
            : snapshot.specs[key] || 'Unknown / 待确认',
        ['product', 'quantity', 'terms', 'destination', 'arrival'].includes(key)
          ? '客户询盘.eml · 正文'
          : key === 'packaging'
            ? '报价表 / 包装变更邮件'
            : '人工输入或尚无证据',
      ]);
      break;
    case 'cost':
      content = [
        ['项目', '数值', '单位 / 来源'],
        ['基础成本', c.base, 'CNY/件 · 供应商A B2 / 人工核对'],
        ['包装', c.packaging, 'CNY/件 · 包装报价 / 人工核对'],
        ['本地费用', c.local, 'CNY/件 · 内部估算'],
        ['合计', price?.total ?? '无效', 'CNY/件'],
        ['汇率', c.exchangeRate, 'CNY/USD · 内部假设'],
        ['目标毛利率', c.margin, '% · 内部假设'],
        ['建议单价', price?.unitPrice ?? '无效', 'USD/件'],
        ['总价', price?.totalPrice ?? '无效', 'USD'],
        ['公式', 'CEILING((基础成本 + 包装 + 本地费用) / 汇率 / (1 - 毛利率), 0.01)'],
      ];
      break;
    case 'comparison':
      content = [
        ['项目', '供应商 A', '供应商 B'],
        ['基础报价 CNY/件', 44, 46],
        ['普通包装 CNY/件', 2, 2],
        ['原报价建议 USD/件', 8.69, 9.03],
        ['预计生产天数（待确认）', 28, 23],
        ['比较范围', '原普通包装报价', '彩盒成本尚缺，不能与新版直接比较'],
        ['来源', '供应商A_背包报价.xlsx · B2:B5', '供应商B_背包报价.pdf · 第1页'],
      ];
      break;
    case 'rfq':
      content = [
        ['主题', '请确认定制背包与包装变更成本'],
        ['包装要求', snapshot.packaging],
        ['请回复', '包装价格、MOQ、样品费用、工艺范围、交期影响'],
        ['未知规格', '面料、尺寸与 LOGO 工艺需客户澄清'],
        ['交付状态', '询价草稿 · 未发送'],
      ];
      break;
    case 'production':
      content = [
        ['生产状态', 'BLOCKED · 草稿，不可用于开工'],
        ['客户规格批准', '缺少批准证据'],
        ['样品批准', '缺少批准证据'],
        ['供应商生产确认', '缺少确认'],
        ['T&A 计划', '以真实批准日为 T0；采购、样品、生产、验货、订舱日期均待确认'],
        ['QC 关注点', '材料、尺寸、LOGO、包装与批准样品一致性'],
      ];
      break;
    default:
      content = [
        ['产品', snapshot.specs.product],
        ['单价 USD', price?.unitPrice ?? '无效'],
        ['总价 USD', price?.totalPrice ?? '无效'],
        ['生产时间', '预计 28 天，需供应商最终确认'],
        ['付款条件', '待双方确认'],
        ['有效期', '待内部确认'],
        ['交付状态', kind === 'pi' ? 'PI 草稿 · 需核对 PO，不代表正式签发' : '报价草稿 · 未发送'],
      ];
  }
  return [...metadata, [], ...content, [], ...pending];
}
function officeFile(kind: ArtifactKind, snapshot: Snapshot) {
  const rows = artifactRows(kind, snapshot);
  const isSheet = ['spec', 'cost', 'comparison'].includes(kind);
  const file = isSheet ? 'xl/workbook.xml' : 'word/document.xml';
  const contentType = isSheet
    ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'
    : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml';
  const files = [
    {
      name: '[Content_Types].xml',
      data: encode(
        `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/${file}" ContentType="${contentType}"/>${isSheet ? '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' : ''}</Types>`,
      ),
    },
    {
      name: '_rels/.rels',
      data: encode(
        `<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="${file}"/></Relationships>`,
      ),
    },
  ];
  if (isSheet) {
    files.push({
      name: file,
      data: encode(
        '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="工作成果" sheetId="1" r:id="rId1"/></sheets></workbook>',
      ),
    });
    files.push({
      name: 'xl/_rels/workbook.xml.rels',
      data: encode(
        '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
      ),
    });
    files.push({
      name: 'xl/worksheets/sheet1.xml',
      data: encode(
        `<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="1" width="28" customWidth="1"/><col min="2" max="3" width="65" customWidth="1"/></cols><sheetData>${rows.map((row, i) => `<row r="${i + 1}">${row.map((value, j) => `<c r="${String.fromCharCode(65 + j)}${i + 1}"${typeof value === 'number' ? `><v>${value}</v>` : ` t="inlineStr"><is><t xml:space="preserve">${escape(value)}</t></is>`}</c>`).join('')}</row>`).join('')}</sheetData></worksheet>`,
      ),
    });
  } else {
    files.push({
      name: file,
      data: encode(
        `<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${rows.map((row, i) => `<w:p><w:r><w:rPr>${i === 0 ? '<w:b/><w:sz w:val="32"/>' : '<w:sz w:val="22"/>'}</w:rPr><w:t xml:space="preserve">${escape(row.join('    '))}</w:t></w:r></w:p>`).join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1200" w:right="1200" w:bottom="1200" w:left="1200"/></w:sectPr></w:body></w:document>`,
      ),
    });
  }
  return { name: `${kind}-V${snapshot.version}.${isSheet ? 'xlsx' : 'docx'}`, data: zip(files) };
}
export function emailDraft(snapshot: Snapshot) {
  const price = calculate(snapshot.costs);
  return `To: Michael Weber <michael@example.com>\r\nSubject: DRAFT - Custom backpack quotation V${snapshot.version}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nX-Unsent: 1\r\n\r\nDEMO DRAFT - NOT SENT. Attach the reviewed quotation manually.\r\n\r\nDear Michael,\r\n\r\nPlease review our draft quotation for ${snapshot.costs.quantity} units of ${snapshot.specs.product || 'product to be confirmed'}.\r\nUnit price: ${price ? usd(price.unitPrice) : 'Pending'}; ${snapshot.specs.terms || 'trade terms pending'}.\r\nPackaging: ${snapshot.packaging}.\r\nTotal: ${price ? usd(price.totalPrice) : 'Pending'}.\r\nSpecifications, sample approval, payment terms and production lead time remain subject to confirmation. Arrival within 45 days is not guaranteed.\r\n\r\nKind regards\r\nExport team\r\n`;
}
export function buildExport(state: WorkbenchState, selected: ArtifactKind[]) {
  const files = selected.map((kind) => officeFile(kind, state.current));
  files.push({ name: 'quotation-draft.eml', data: encode(emailDraft(state.current)) });
  files.push({
    name: 'evidence-and-version.json',
    data: encode(
      JSON.stringify(
        {
          caseId,
          snapshot: state.current,
          sources: state.sources,
          pending: ['客户规格与样品批准', '供应商生产确认', 'MOQ / 交期', '付款条件'],
          poComparison: state.po,
          activity: state.activity,
          demo: true,
          sent: false,
        },
        null,
        2,
      ),
    ),
  });
  return zip(files);
}
export function download(
  data: Uint8Array<ArrayBuffer> | string,
  name: string,
  type = 'application/zip',
) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function printArtifact(kind: ArtifactKind, snapshot: Snapshot) {
  const win = window.open('', '_blank');
  if (!win) return false;
  win.document.write(
    `<html lang="zh-CN"><head><meta charset="utf-8"/><title>${escape(kind)} V${snapshot.version}</title><style>body{font:14px sans-serif;margin:48px;color:#111111;background:#FFFFFF;color-scheme:light}table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #ddd;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:24px}p{color:#666}@media print{button{display:none}}</style></head><body><img src="${new URL('/brand/navowork-mark-black.svg', window.location.origin).href}" width="80" height="50" alt="Navowork"/><h1>${escape(artifacts.find((a) => a.id === kind)!.title)}</h1><p>Navowork · 演示草稿 · V${snapshot.version}</p><button onclick="window.print()">打印 / 保存为 PDF</button><table>${artifactRows(
      kind,
      snapshot,
    )
      .map((row) => `<tr>${row.map((cell) => `<td>${escape(cell)}</td>`).join('')}</tr>`)
      .join('')}</table></body></html>`,
  );
  win.document.close();
  return true;
}

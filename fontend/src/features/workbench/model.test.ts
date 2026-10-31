import { describe, expect, it } from 'vitest';
import { inflateRawSync } from 'node:zlib';
import {
  applyChange,
  artifacts,
  calculate,
  canApprove,
  editSnapshot,
  initialState,
  poDifferences,
  proposeChange,
} from './model';
import { buildExport } from './export';

function crc32(data: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function readZip(input: Uint8Array): Map<string, Buffer> {
  const zip = Buffer.from(input);
  const minEocdOffset = Math.max(0, zip.length - 22 - 0xffff);
  let eocdOffset = -1;
  for (let offset = zip.length - 22; offset >= minEocdOffset; offset -= 1) {
    if (zip.readUInt32LE(offset) === 0x06054b50) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) throw new Error('ZIP end-of-central-directory record not found');
  const disk = zip.readUInt16LE(eocdOffset + 4);
  const centralDisk = zip.readUInt16LE(eocdOffset + 6);
  const diskEntries = zip.readUInt16LE(eocdOffset + 8);
  const entryCount = zip.readUInt16LE(eocdOffset + 10);
  const centralSize = zip.readUInt32LE(eocdOffset + 12);
  const centralOffset = zip.readUInt32LE(eocdOffset + 16);
  const commentLength = zip.readUInt16LE(eocdOffset + 20);
  if (disk !== 0 || centralDisk !== 0 || diskEntries !== entryCount)
    throw new Error('Multi-disk ZIP archives are unsupported');
  if (eocdOffset + 22 + commentLength !== zip.length)
    throw new Error('Invalid ZIP end-of-central-directory bounds');
  if (centralOffset + centralSize !== eocdOffset)
    throw new Error('Invalid ZIP central-directory bounds');

  const files = new Map<string, Buffer>();
  let offset = centralOffset;
  for (let index = 0; index < entryCount; index += 1) {
    if (offset + 46 > zip.length || zip.readUInt32LE(offset) !== 0x02014b50)
      throw new Error('Invalid ZIP central-directory entry');
    const flags = zip.readUInt16LE(offset + 8);
    const method = zip.readUInt16LE(offset + 10);
    const expectedCrc = zip.readUInt32LE(offset + 16);
    const compressedSize = zip.readUInt32LE(offset + 20);
    const uncompressedSize = zip.readUInt32LE(offset + 24);
    const filenameLength = zip.readUInt16LE(offset + 28);
    const extraLength = zip.readUInt16LE(offset + 30);
    const entryCommentLength = zip.readUInt16LE(offset + 32);
    const localOffset = zip.readUInt32LE(offset + 42);
    const entryEnd = offset + 46 + filenameLength + extraLength + entryCommentLength;
    if (entryEnd > zip.length) throw new Error('Truncated ZIP central-directory entry');
    if (flags & 1) throw new Error('Encrypted ZIP entries are unsupported');
    const name = zip.toString('utf8', offset + 46, offset + 46 + filenameLength);
    if (localOffset + 30 > zip.length || zip.readUInt32LE(localOffset) !== 0x04034b50)
      throw new Error(`Invalid ZIP local header for ${name}`);
    const localNameLength = zip.readUInt16LE(localOffset + 26);
    const localExtraLength = zip.readUInt16LE(localOffset + 28);
    const localName = zip.toString('utf8', localOffset + 30, localOffset + 30 + localNameLength);
    if (localName !== name) throw new Error(`ZIP filename mismatch for ${name}`);
    const dataOffset = localOffset + 30 + localNameLength + localExtraLength;
    const dataEnd = dataOffset + compressedSize;
    if (dataEnd > zip.length) throw new Error(`Truncated ZIP entry ${name}`);
    const compressed = zip.subarray(dataOffset, dataEnd);
    let contents: Buffer;
    if (method === 0) contents = Buffer.from(compressed);
    else if (method === 8) contents = inflateRawSync(compressed);
    else throw new Error(`Unsupported ZIP compression method ${method} for ${name}`);
    if (contents.length !== uncompressedSize || crc32(contents) !== expectedCrc)
      throw new Error(`ZIP size or CRC mismatch for ${name}`);
    files.set(name, contents);
    offset = entryEnd;
  }
  if (offset !== centralOffset + centralSize) throw new Error('Invalid ZIP central-directory size');
  return files;
}

describe('PRD deterministic costing and version boundaries', () => {
  it('calculates A, B and the packaging change with upward cent rounding', () => {
    const state = initialState();
    expect(calculate(state.current.costs)).toEqual({
      total: 50,
      unitPrice: 8.69,
      totalPrice: 26070,
    });
    expect(calculate({ ...state.current.costs, base: 46 })?.unitPrice).toBe(9.03);
    const next = applyChange(proposeChange(state));
    expect(calculate(next.current.costs)).toEqual({
      total: 53,
      unitPrice: 9.21,
      totalPrice: 27630,
    });
    expect(
      Math.round(
        (calculate(next.current.costs)!.unitPrice - calculate(state.current.costs)!.unitPrice) *
          100,
      ),
    ).toBe(52);
    expect(next.history[0].costs.packaging).toBe(2);
    expect(next.current.version).toBe(2);
    expect(next.current.approved).toBe(false);
    expect(next.history[0]).not.toBe(state.current);
  });
  it('rejects invalid values and does not approve a pending proposal', () => {
    const state = initialState();
    for (const invalid of [
      { exchangeRate: 0 },
      { margin: 100 },
      { margin: -1 },
      { quantity: 0 },
      { quantity: 1.5 },
      { base: -3 },
      { packaging: NaN },
      { local: Infinity },
    ]) {
      expect(calculate({ ...state.current.costs, ...invalid })).toBeNull();
    }
    expect(canApprove(proposeChange(state))).toBe(false);
  });
  it('keeps the existing version when the supplier price or a dependent acceptance is missing', () => {
    const proposed = proposeChange(initialState());
    proposed.proposal!.costKnown = false;
    expect(applyChange(proposed)).toBe(proposed);
    proposed.proposal!.costKnown = true;
    proposed.proposal!.accepted = ['cost', 'quote'];
    expect(applyChange(proposed)).toBe(proposed);
  });
  it('edits an approved version as a new draft and preserves its approval snapshot', () => {
    const state = initialState();
    state.current.approved = true;
    const next = editSnapshot(state, { costs: { ...state.current.costs, base: 48 } });
    expect(next.current.version).toBe(2);
    expect(next.current.approved).toBe(false);
    expect(next.history[0].approved).toBe(true);
    expect(next.history[0].costs.base).toBe(44);
    expect(state.current.costs.base).toBe(44);
  });
  it('flags PO discrepancies after repricing and does not infer an external confirmation', () => {
    const next = applyChange(proposeChange(initialState()));
    expect(poDifferences(next)).toEqual(['PO 单价与当前报价不一致']);
    next.po.price = 9.21;
    expect(poDifferences(next)).toEqual([]);
    next.po.quantity = 1000;
    expect(poDifferences(next)).toEqual(['PO 数量与当前报价不一致']);
  });
});

it('exports valid Office ZIP containers with one consistent snapshot, real worksheets, and unsent mail', () => {
  const state = applyChange(proposeChange(initialState()));
  state.current.specs.product = 'Backpack <sample> & "logo"';
  state.current.specs.terms = 'FCA Shanghai';
  const files = readZip(
    buildExport(
      state,
      artifacts.map((a) => a.id),
    ),
  );
  for (const artifact of artifacts) {
    const filename = `${artifact.id}-V2.${artifact.format.toLowerCase()}`;
    const officeFile = files.get(filename);
    expect(officeFile, `missing exported artifact ${filename}`).toBeDefined();
    const officeFiles = readZip(officeFile!);
    const worksheet = artifact.format === 'XLSX' ? 'xl/worksheets/sheet1.xml' : 'word/document.xml';
    const xmlBytes = officeFiles.get(worksheet);
    expect(xmlBytes, `missing Office document part ${worksheet}`).toBeDefined();
    const xml = xmlBytes!.toString('utf8');
    expect(xml).toContain('V2');
    expect(xml).toContain('定制彩盒');
    expect(xml).toContain('FCA Shanghai');
    expect(xml).not.toContain('已发送');
    if (artifact.id === 'cost' || artifact.id === 'quote') expect(xml).toContain('9.21');
    if (artifact.id === 'spec' || artifact.id === 'quote')
      expect(xml).toContain('&lt;sample&gt; &amp; &quot;logo&quot;');
    if (artifact.id === 'production') expect(xml).toContain('BLOCKED');
  }
  const evidence = files.get('evidence-and-version.json');
  const mail = files.get('quotation-draft.eml');
  expect(evidence).toBeDefined();
  expect(mail).toBeDefined();
  const exported = JSON.parse(evidence!.toString('utf8'));
  expect(exported.snapshot.costs.packaging).toBe(5);
  expect(exported.sent).toBe(false);
  expect(mail!.toString('utf8')).toContain('FCA Shanghai');
  expect(mail!.toString('utf8')).toContain('X-Unsent: 1');
});

import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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
  const dir = mkdtempSync(join(tmpdir(), 'trade-export-'));
  try {
    const state = applyChange(proposeChange(initialState()));
    state.current.specs.product = 'Backpack <sample> & "logo"';
    state.current.specs.terms = 'FCA Shanghai';
    writeFileSync(
      join(dir, 'pack.zip'),
      buildExport(
        state,
        artifacts.map((a) => a.id),
      ),
    );
    execFileSync('unzip', ['-t', join(dir, 'pack.zip')]);
    execFileSync('unzip', ['-q', join(dir, 'pack.zip'), '-d', join(dir, 'files')]);
    for (const artifact of artifacts) {
      const path = join(dir, 'files', `${artifact.id}-V2.${artifact.format.toLowerCase()}`);
      execFileSync('unzip', ['-t', path]);
      const xml = execFileSync(
        'unzip',
        ['-p', path, artifact.format === 'XLSX' ? 'xl/worksheets/sheet1.xml' : 'word/document.xml'],
        { encoding: 'utf8' },
      );
      expect(xml).toContain('V2');
      expect(xml).toContain('定制彩盒');
      expect(xml).toContain('FCA Shanghai');
      expect(xml).not.toContain('已发送');
      if (artifact.id === 'cost' || artifact.id === 'quote') expect(xml).toContain('9.21');
      if (artifact.id === 'spec' || artifact.id === 'quote')
        expect(xml).toContain('&lt;sample&gt; &amp; &quot;logo&quot;');
      if (artifact.id === 'production') expect(xml).toContain('BLOCKED');
    }
    const exported = JSON.parse(
      readFileSync(join(dir, 'files', 'evidence-and-version.json'), 'utf8'),
    );
    expect(exported.snapshot.costs.packaging).toBe(5);
    expect(exported.sent).toBe(false);
    expect(readFileSync(join(dir, 'files', 'quotation-draft.eml'), 'utf8')).toContain(
      'FCA Shanghai',
    );
    expect(readFileSync(join(dir, 'files', 'quotation-draft.eml'), 'utf8')).toContain(
      'X-Unsent: 1',
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

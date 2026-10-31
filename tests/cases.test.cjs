const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../cases.js');
const D = require('../domain.js');

test('dashboard seeds cover all statuses with separate business states', () => {
  const p = C.createPortfolio();
  assert.deepEqual(p.openIds, []);
  assert.deepEqual(p.cases.map(c => c.status), ['todo', 'active', 'waiting', 'done']);
  const first = p.cases[0], other = p.cases[1], before = JSON.stringify(other.state);
  first.state = D.applyInstruction(first.state, D.DATA.scenarioPrompts[0]).state;
  first.state.savedAssets.push({ id: 'local-draft' });
  first.state.enabled.pop();
  assert.equal(JSON.stringify(other.state), before);
  assert.equal(p.cases[2].state.optionStatus, 'proposed');
  assert.equal(p.cases[3].state.optionStatus, 'accepted');
  assert.equal(p.cases[3].state.currentSnapshot.quote.total, null);
  assert.ok(p.cases[3].state.currentSnapshot.risks.length > 0);
});

test('legacy migration preserves existing versions and drafts without sharing references', () => {
  const legacy = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  legacy.savedAssets.push({ id: 'legacy-draft', title: '旧资料' });
  const p = C.createPortfolio(legacy);
  assert.equal(p.cases[0].state.revision, 2);
  assert.equal(p.cases[0].state.currentSnapshot.quote.goodsSubtotal, '540.00');
  assert.equal(p.cases[0].state.savedAssets[0].id, 'legacy-draft');
  assert.deepEqual(new Set(p.cases.map(c => c.status)), new Set(C.STATUSES));
  legacy.savedAssets[0].title = 'changed';
  assert.equal(p.cases[0].state.savedAssets[0].title, '旧资料');
});

test('opening a todo keeps its status, deduplicates tabs, and closing retains its data', () => {
  const p = C.createPortfolio();
  const [a, b, c] = p.cases;
  C.openCase(p, a.id); C.openCase(p, b.id); C.openCase(p, c.id); C.openCase(p, b.id);
  assert.deepEqual(p.openIds, [a.id, b.id, c.id]);
  assert.equal(a.status, 'todo');
  assert.equal(p.activeId, b.id);
  C.closeCase(p, b.id);
  assert.equal(p.activeId, c.id);
  assert.strictEqual(C.getCase(p, b.id), b);
  C.closeCase(p, a.id); C.closeCase(p, c.id);
  assert.equal(p.activeId, null);
  assert.equal(p.cases.length, 4);
  assert.equal(C.openCase(p, 'missing'), null);
});

test('creating two inquiries gives unique identities, empty independent states, and distinct codes', () => {
  const p = C.createPortfolio();
  const a = C.createCase(p, { title: '客户 A', customer: 'A' });
  const b = C.createCase(p, { title: '客户 B', customer: 'B' });
  assert.notEqual(a.id, b.id);
  assert.notEqual(a.code, b.code);
  assert.equal(p.activeId, b.id);
  assert.equal(a.status, 'todo');
  assert.equal(a.state.revision, 0);
  a.state.messages.push({ role: 'user', text: '私人草稿' });
  assert.deepEqual(b.state.messages, []);
  assert.equal(p.cases.length, 6);
});

test('status changes and reopening never clear unresolved business risks', () => {
  const p = C.createPortfolio();
  const item = p.cases[2], before = JSON.stringify(item.state);
  C.updateStatus(p, item.id, 'done');
  assert.equal(item.status, 'done');
  assert.match(item.nextAction, /不代表成交或风险解除/);
  assert.equal(JSON.stringify(item.state), before);
  C.updateStatus(p, item.id, 'active');
  assert.equal(item.status, 'active');
  assert.equal(C.updateStatus(p, item.id, 'invalid'), null);
  assert.equal(item.status, 'active');
});

test('serialized portfolios restore tab identity, business state and drafts', () => {
  const p = C.createPortfolio();
  C.openCase(p, p.cases[2].id);
  p.cases[2].state.composerDraft = '请确认运输费用';
  const loaded = C.normalizePortfolio(JSON.stringify(p));
  assert.equal(loaded.activeId, p.activeId);
  assert.deepEqual(loaded.openIds, p.openIds);
  assert.equal(loaded.cases[2].state.composerDraft, '请确认运输费用');
  assert.equal(loaded.cases[2].state.currentSnapshot.quote.goodsSubtotal, '540.00');
  loaded.cases[2].state.messages.push({ role: 'user', text: 'new' });
  assert.notEqual(loaded.cases[2].state.messages.length, p.cases[2].state.messages.length);
});

test('corrupt caches recover valid cases, repair identifiers and discard dangling tab IDs', () => {
  const p = C.createPortfolio();
  p.cases[1].id = p.cases[0].id;
  p.cases[2].id = '<script>';
  p.cases[3].state = { versions: [null] };
  p.cases.push(null);
  p.openIds = ['mx-026', 'missing', 'mx-026'];
  p.activeId = 'missing';
  const loaded = C.normalizePortfolio(p);
  assert.equal(loaded.cases.length, 4);
  assert.equal(new Set(loaded.cases.map(c => c.id)).size, 4);
  assert.ok(loaded.cases.every(c => /^[A-Za-z0-9_-]+$/.test(c.id)));
  assert.deepEqual(loaded.openIds, ['mx-026']);
  assert.equal(loaded.activeId, 'mx-026');
  assert.equal(loaded.cases[3].state.revision, 0);
  assert.equal(loaded.cases[3].status, 'todo');
  assert.equal(loaded.cases[1].state.revision, 1);
  assert.equal(C.normalizePortfolio('{broken').cases.length, 4);
  assert.equal(C.normalizePortfolio({ schema: C.SCHEMA, cases: [] }).cases.length, 4);
});

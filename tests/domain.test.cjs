'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const D = require('../domain.js');

test('seed V1 is explicitly simulated and identifies unsupported promises', () => {
  const s = D.createInitialState();
  assert.equal(s.revision, 1);
  assert.equal(s.currentSnapshot.quote, null);
  assert.equal(s.currentSnapshot.generationMode, 'simulated');
  assert.ok(s.currentSnapshot.risks.some(r => r.id === 'leadtime'));
  assert.ok(s.currentSnapshot.risks.some(r => r.id === 'certification'));
  assert.ok(s.logs.every(l => l.simulated === true));
  assert.match(s.currentSnapshot.replyEn, /cannot commit/);
});

test('a reset case can execute initial analysis as V1', () => {
  const empty = D.createEmptyState();
  const result = D.applyInstruction(empty, D.DATA.scenarioPrompts[0]);
  assert.equal(result.ok, true);
  assert.equal(result.mode, 'analysis');
  assert.equal(result.state.revision, 1);
  assert.equal(result.state.versions.length, 1);
  assert.equal(result.snapshot.quote, null);
  assert.equal(empty.revision, 0);
});

test('two iterations preserve requested customization until explicit acceptance', () => {
  const first = D.createInitialState();
  const serialized = JSON.stringify(first);
  const second = D.applyInstruction(first, D.DATA.scenarioPrompts[1]);
  assert.equal(second.ok, true);
  assert.equal(second.state.revision, 2);
  assert.equal(second.state.sku, 'BAG-STOCK');
  assert.equal(second.state.customization, true);
  assert.equal(second.state.optionStatus, 'proposed');
  assert.equal(second.snapshot.quote.goodsSubtotal, '540.00');
  assert.ok(second.snapshot.risks.some(r => r.id === 'original-moq'));
  assert.ok(second.snapshot.risks.some(r => r.id === 'acceptance'));
  assert.equal(JSON.stringify(first), serialized);
  const third = D.applyInstruction(second.state, D.DATA.scenarioPrompts[2]);
  assert.equal(third.ok, true);
  assert.equal(third.state.revision, 3);
  assert.equal(third.state.optionStatus, 'accepted');
  assert.equal(third.state.customization, false);
  assert.equal(third.state.arrivalDays, 7);
  assert.equal(third.snapshot.quote.dispatchDays, 3);
  assert.equal(third.snapshot.quote.total, null);
  assert.equal(third.snapshot.quote.freight, null);
  assert.equal(third.snapshot.quote.tax, null);
  assert.equal(third.snapshot.quote.arrivalGuaranteed, false);
  assert.equal(third.snapshot.risks.some(r => r.id === 'acceptance'), false);
  assert.match(third.snapshot.replyEs, /USD 540\.00/);
  assert.match(third.snapshot.replyEn, /not an arrival guarantee/);
  assert.equal(third.state.versions[0].requirements.quantity, 1000);
  assert.equal(third.state.versions[1].requirements.optionStatus, 'proposed');
});

test('different quantity recomputes the current quote and both replies', () => {
  const state = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  const result = D.applyInstruction(state, '改为600件，重新计算报价');
  assert.equal(result.ok, true);
  assert.equal(result.snapshot.quote.quantity, 600);
  assert.equal(result.snapshot.quote.goodsSubtotal, '1080.00');
  assert.match(result.snapshot.replyEn, /USD 1080\.00/);
  assert.match(result.snapshot.replyEs, /USD 1080\.00/);
  assert.equal(state.quantity, 300);
  assert.equal(result.state.versions[1].quote.goodsSubtotal, '540.00');
});

test('stock overage fails without changing current version', () => {
  const state = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  const result = D.applyInstruction(state, '改成900件现货，更新报价');
  assert.equal(result.ok, false);
  assert.equal(result.code, 'BUSINESS_VALIDATION_FAILED');
  assert.match(result.notice, /800/);
  assert.equal(result.state, state);
  assert.equal(result.state.revision, 2);
});

test('disabled capability blocks a dependent run, but asset capability is optional', () => {
  const state = D.createInitialState();
  state.enabled = state.enabled.filter(id => id !== 'quote-cli');
  const failed = D.applyInstruction(state, D.DATA.scenarioPrompts[1]);
  assert.equal(failed.ok, false);
  assert.equal(failed.code, 'CAPABILITY_DISABLED');
  assert.match(failed.notice, /报价计算与导出/);
  const other = D.createInitialState();
  other.enabled = other.enabled.filter(id => id !== 'asset-skill');
  assert.equal(D.applyInstruction(other, D.DATA.scenarioPrompts[1]).ok, true);
});

test('invalid quantities and below-MOQ stock never produce a quote', () => {
  for (const text of ['改成0件', '改成-300件', '改成3.5件', '数量改为000', '改成100001件']) {
    const state = D.createInitialState();
    const result = D.applyInstruction(state, text);
    assert.equal(result.ok, false, text);
    assert.equal(result.state.revision, 1);
  }
  const result = D.applyInstruction(D.createInitialState(), '改成50件现货');
  assert.equal(result.ok, false);
  assert.match(result.notice, /起订量/);
});

test('unknown input is clarified and stock rejection cannot become acceptance', () => {
  const state = D.createInitialState();
  const unknown = D.applyInstruction(state, '帮我订一张机票');
  assert.equal(unknown.ok, false);
  assert.match(unknown.notice, /不会调用通用AI/);
  const denied = D.applyInstruction(state, '不接受现货，继续讨论');
  assert.equal(denied.ok, false);
  assert.equal(denied.state.optionStatus, 'requested');
});

test('integer-cents price tiers and MOQ rules are deterministic', () => {
  assert.equal(D.calculateQuote('BAG-CUSTOM', 500, 'requested').quote.goodsSubtotal, '1200.00');
  assert.equal(D.calculateQuote('BAG-CUSTOM', 999, 'requested').quote.goodsSubtotal, '2397.60');
  assert.equal(D.calculateQuote('BAG-CUSTOM', 1000, 'requested').quote.goodsSubtotal, '2000.00');
  assert.equal(D.calculateQuote('BAG-STOCK', 100, 'proposed').quote.goodsSubtotal, '180.00');
  assert.equal(D.calculateQuote('BAG-STOCK', 801, 'proposed').ok, false);
  assert.equal(D.calculateQuote('BAG-CUSTOM', 499, 'requested').ok, false);
});

test('every source reference exists and no generated assertion invents certification', () => {
  const ids = new Set([...D.DATA.products.map(x => x.id), ...D.DATA.wiki.map(x => x.id), ...D.DATA.assets.map(x => x.id)]);
  let state = D.createEmptyState();
  for (const prompt of D.DATA.scenarioPrompts) {
    const r = D.applyInstruction(state, prompt);
    assert.equal(r.ok, true);
    state = r.state;
    for (const id of r.snapshot.sourceIds) assert.ok(ids.has(id), id);
    for (const risk of r.snapshot.risks) for (const id of risk.sourceIds) assert.ok(ids.has(id), id);
    assert.doesNotMatch(r.snapshot.replyEn, /we are certified|has been certified|guarantee arrival/i);
    assert.ok(state.logs.every(x => x.simulated));
  }
});


test('custom analysis handles MOQ and does not borrow stock dispatch facts', () => {
  const low = D.applyInstruction(D.createEmptyState(), '分析300件定制帆布袋的询盘，希望20天内收到');
  assert.equal(low.ok, true);
  assert.ok(low.snapshot.risks.some(r => r.id === 'requested-moq'));
  const regular = D.buildSnapshot({ revision: 2, stage: 2, quantity: 500, sku: 'BAG-CUSTOM', optionStatus: 'requested', arrivalDays: 20, customization: true });
  assert.equal(regular.quote.goodsSubtotal, '1200.00');
  assert.equal(regular.quote.dispatchDays, null);
  assert.ok(regular.risks.find(r => r.id === 'arrival').message.includes('14天是生产时间'));
  assert.equal(regular.risks.some(r => r.message.includes('3天是出库')), false);
});

test('not-yet-accepted wording cannot be parsed as an acceptance', () => {
  const state = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  for (const text of ['客户尚未接受现货', '客户没有接受现货', '客户取消现货', 'Customer does not accept the stock option']) {
    const result = D.applyInstruction(state, text);
    assert.equal(result.ok, false, text);
    assert.equal(result.state.optionStatus, 'proposed');
  }
});

test('stock rejection, questions and requests for customer confirmation preserve the proposal', () => {
  const state = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  const before = JSON.stringify(state);
  for (const text of [
    '现货暂时不能接受',
    '现货方案客户还没有确认',
    '请问客户是否接受现货？',
    '客户接受现货吗',
    '请客户确认现货方案',
    '让买家确认现货后再更新',
    'Has the customer accepted the stock option?',
    'Please ask the customer to accept the stock option',
    'The stock option has not been accepted'
  ]) {
    const result = D.applyInstruction(state, text);
    assert.equal(result.ok, false, text);
    assert.equal(result.code, 'REQUIRES_CLARIFICATION', text);
    assert.equal(result.state, state, text);
    assert.equal(result.state.optionStatus, 'proposed', text);
    assert.equal(JSON.stringify(state), before, text);
  }
  const accepted = D.applyInstruction(state, '客户已接受现货无印花方案，更新报价和回复');
  assert.equal(accepted.ok, true);
  assert.equal(accepted.state.optionStatus, 'accepted');
  assert.equal(accepted.state.stage, 3);
});

test('analysis that generates a quote requires quotation capabilities and logs their use', () => {
  const proposal = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
  for (const capability of ['quote-cli', 'quote-skill']) {
    const state = D.clone(proposal);
    state.enabled = state.enabled.filter(id => id !== capability);
    const before = JSON.stringify(state);
    const blocked = D.applyInstruction(state, '重新分析600件，其他条件不变');
    assert.equal(blocked.ok, false, capability);
    assert.equal(blocked.code, 'CAPABILITY_DISABLED', capability);
    assert.equal(blocked.state, state);
    assert.equal(blocked.snapshot.quote.goodsSubtotal, '540.00');
    assert.equal(JSON.stringify(state), before);
  }
  const result = D.applyInstruction(proposal, '重新分析600件，其他条件不变');
  assert.equal(result.ok, true);
  assert.equal(result.mode, 'analysis');
  assert.equal(result.snapshot.quote.goodsSubtotal, '1080.00');
  const currentLogs = result.state.logs.filter(log => log.revision === result.state.revision);
  assert.ok(currentLogs.some(log => log.capabilityId === 'quote-cli'));
  assert.ok(currentLogs.some(log => log.capabilityId === 'quote-skill'));
  assert.ok(currentLogs.every(log => log.simulated === true));
  const initial = D.createEmptyState();
  initial.enabled = initial.enabled.filter(id => id !== 'quote-cli' && id !== 'quote-skill');
  const analysisOnly = D.applyInstruction(initial, D.DATA.scenarioPrompts[0]);
  assert.equal(analysisOnly.ok, true);
  assert.equal(analysisOnly.snapshot.quote, null);
});

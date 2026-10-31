(function (root, factory) {
  'use strict';
  var domain = typeof module === 'object' && module.exports ? require('./domain.js') : root.SealSeekDemo;
  var api = factory(domain);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.EasyWorkCases = api;
}(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this, function (D) {
  'use strict';
  var SCHEMA = 'easywork-portfolio-v1';
  var STATUSES = ['todo', 'active', 'waiting', 'done'];
  var STATUS_LABELS = { todo: '待办', active: '进行中', waiting: '待客户确认', done: '已结束' };
  var sequence = 0;

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function record(value) { return value && typeof value === 'object' && !Array.isArray(value); }
  function text(value, fallback, max) {
    return typeof value === 'string' && value.trim() ? value.replace(/[\u0000-\u001f]/g, '').trim().slice(0, max || 100) : fallback;
  }
  function now() { return new Date().toISOString(); }
  function identifier(value) { return typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value); }
  function uniqueId(cases) {
    var id;
    do { id = 'inq-' + Date.now().toString(36) + '-' + (++sequence).toString(36); }
    while (cases.some(function (item) { return item.id === id; }));
    return id;
  }
  function validState(state) {
    if (!record(state) || !Array.isArray(state.versions) || !Array.isArray(state.enabled) || !Array.isArray(state.messages)) return false;
    if (!Number.isSafeInteger(state.revision) || state.revision < 0 || !Number.isInteger(state.stage) || state.stage < 0 || state.stage > 3) return false;
    if (!Number.isSafeInteger(state.quantity) || state.quantity < 1 || state.quantity > 100000 || !['BAG-CUSTOM', 'BAG-STOCK'].includes(state.sku)) return false;
    if (!state.versions.every(function (v) {
      return record(v) && Number.isSafeInteger(v.revision) && v.revision > 0 && v.revision <= state.revision && record(v.requirements) && Array.isArray(v.risks) && v.risks.every(record) && Array.isArray(v.checklist) && v.checklist.every(record);
    })) return false;
    return state.revision === 0 ? state.versions.length === 0 : state.versions.some(function (v) { return v.revision === state.revision; });
  }
  function cleanState(value) {
    if (!validState(value)) return D.createEmptyState();
    var result = Object.assign(D.createEmptyState(), clone(value));
    result.enabled = result.enabled.filter(function (id) { return D.DATA.capabilities.some(function (cap) { return cap.id === id; }); });
    result.messages = result.messages.filter(function (m) { return record(m) && typeof m.role === 'string'; });
    ['logs', 'savedAssets', 'selected', 'linkedAssets', 'linkedWiki'].forEach(function (key) {
      result[key] = Array.isArray(result[key]) ? result[key].filter(function (item) { return item !== null; }) : [];
    });
    ['positions', 'reviewed', 'assetRefsByRevision'].forEach(function (key) { if (!record(result[key])) result[key] = {}; });
    result.versions.sort(function (a, b) { return a.revision - b.revision; });
    result.currentSnapshot = result.versions.length ? clone(result.versions[result.versions.length - 1]) : null;
    result.isDemo = true;
    result.generationMode = 'simulated';
    return result;
  }
  function nextAction(status, state) {
    if (status === 'done') return '查看已整理材料；结束本次工作不代表成交或风险解除';
    if (status === 'waiting') return '跟进客户对现货方案与交期的确认';
    if (status === 'todo' || !state.revision) return '分析询盘，核对采购数量与期望交期';
    if (state.stage < 2) return '处理交期冲突，准备可供选择的方案';
    return '复核报价与回复，补充运输及认证信息';
  }
  function makeCase(id, title, code, customer, status, state) {
    return { id: id, title: title, code: code, customer: customer, market: '墨西哥', status: status, nextAction: nextAction(status, state), updatedAt: now(), state: cleanState(state), isDemo: true };
  }
  function createPortfolio(legacyState) {
    var original = cleanState(legacyState);
    var migrated = original.revision > 0;
    var waiting = D.applyInstruction(D.createInitialState(), D.DATA.scenarioPrompts[1]).state;
    var completed = D.applyInstruction(waiting, D.DATA.scenarioPrompts[2]).state;
    return {
      schema: SCHEMA,
      activeId: 'mx-026',
      openIds: [],
      cases: [
        makeCase('mx-026', '墨西哥帆布袋试单', 'MX-026', 'MESA · 墨西哥', migrated ? 'active' : 'todo', original),
        makeCase('mx-027', 'Norte 企业礼赠询盘', 'MX-027', 'Norte · 墨西哥', migrated ? 'todo' : 'active', migrated ? D.createEmptyState() : D.createInitialState()),
        makeCase('mx-028', 'Luna 门店现货试单', 'MX-028', 'Luna · 墨西哥', 'waiting', waiting),
        makeCase('mx-029', 'Casa 帆布袋回复材料', 'MX-029', 'Casa · 墨西哥', 'done', completed)
      ]
    };
  }
  function normalizePortfolio(value, legacyState) {
    if (typeof value === 'string') { try { value = JSON.parse(value); } catch (_) { value = null; } }
    if (!record(value) || value.schema !== SCHEMA || !Array.isArray(value.cases)) return createPortfolio(legacyState);
    var cases = [];
    value.cases.forEach(function (item, index) {
      if (!record(item)) return;
      var stateValid = validState(item.state);
      var state = cleanState(item.state);
      var id = identifier(item.id) && !cases.some(function (c) { return c.id === item.id; }) ? item.id : uniqueId(cases);
      var status = stateValid && STATUSES.includes(item.status) ? item.status : state.revision ? 'active' : 'todo';
      var result = makeCase(id, text(item.title, '帆布袋询盘 ' + (index + 1)), text(item.code, 'MX-' + (26 + index), 40), text(item.customer, '待补充客户', 80), status, state);
      result.nextAction = stateValid ? text(item.nextAction, nextAction(status, state), 240) : nextAction(status, state);
      result.updatedAt = typeof item.updatedAt === 'string' && Number.isFinite(Date.parse(item.updatedAt)) ? item.updatedAt : now();
      cases.push(result);
    });
    if (!cases.length) return createPortfolio(legacyState);
    var ids = cases.map(function (item) { return item.id; });
    var openIds = Array.isArray(value.openIds) ? value.openIds.filter(function (id, index, all) { return ids.includes(id) && all.indexOf(id) === index; }) : [];
    return { schema: SCHEMA, cases: cases, openIds: openIds, activeId: ids.includes(value.activeId) ? value.activeId : openIds[openIds.length - 1] || ids[0] };
  }
  function getCase(portfolio, id) { return portfolio.cases.find(function (item) { return item.id === id; }) || null; }
  function openCase(portfolio, id) {
    var item = getCase(portfolio, id);
    if (!item) return null;
    if (!portfolio.openIds.includes(id)) portfolio.openIds.push(id);
    portfolio.activeId = id;
    return item;
  }
  function closeCase(portfolio, id) {
    var index = portfolio.openIds.indexOf(id);
    if (index === -1) return null;
    portfolio.openIds.splice(index, 1);
    if (portfolio.activeId === id) portfolio.activeId = portfolio.openIds[Math.min(index, portfolio.openIds.length - 1)] || null;
    return getCase(portfolio, id);
  }
  function createCase(portfolio, details) {
    details = details || {};
    var nextCode = Math.max(25, ...portfolio.cases.map(function (item) { var m = /^MX-(\d+)$/.exec(item.code); return m ? Number(m[1]) : 25; })) + 1;
    var item = makeCase(uniqueId(portfolio.cases), text(details.title, '新的帆布袋询盘'), 'MX-' + String(nextCode).padStart(3, '0'), text(details.customer, '待补充客户', 80), 'todo', D.createEmptyState());
    portfolio.cases.push(item);
    openCase(portfolio, item.id);
    return item;
  }
  function updateStatus(portfolio, id, status) {
    var item = getCase(portfolio, id);
    if (!item || !STATUSES.includes(status)) return null;
    item.status = status;
    item.nextAction = nextAction(status, item.state);
    item.updatedAt = now();
    return item;
  }
  return { SCHEMA: SCHEMA, STATUSES: STATUSES, STATUS_LABELS: STATUS_LABELS, createPortfolio: createPortfolio, normalizePortfolio: normalizePortfolio, createCase: createCase, getCase: getCase, openCase: openCase, closeCase: closeCase, updateStatus: updateStatus };
}));

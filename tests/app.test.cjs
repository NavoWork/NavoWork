const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const D = require('../domain.js');
const C = require('../cases.js');

// Exercise the actual event handlers with shared storage and controllable run delays.
// This harness checks state transitions; browser layout/accessibility is verified separately.
function mount(seed, standalone=false, options={}) {
  const handlers = {}, downloads = [], runTimers = [];
  const store = options.store || (options.authenticated === false ? {} : {'easywork-demo-session-v1':JSON.stringify({name:'测试用户'})});
  if (seed) store['sealseek-overseas-demo-20261030-v1'] = JSON.stringify({...seed, schema:'demo-ui-v1'});
  const decode = s => s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
  let markup='', elements={};
  const app = {get innerHTML(){return markup;},set innerHTML(value){markup=value;elements={};}};
  function element(id) {
    if(elements[id])return elements[id];
    const tag=markup.match(new RegExp('<([a-z]+)\\b([^>]*\\bid="'+id+'"[^>]*)>'));
    if(!tag)return null;
    const opening=tag[0],start=tag.index+opening.length,end=markup.indexOf('</'+tag[1]+'>',start);
    let inner=tag[1]==='input'?'':markup.slice(start,end);
    if(id==='inquiry-list')inner=markup.slice(start,markup.indexOf('</div><div class="result-meta">',start));
    const value=tag[1]==='textarea'?decode(inner):decode((opening.match(/\bvalue="([^"]*)"/)||[])[1]||'');
    return elements[id]={id,value,innerHTML:inner,scrollTop:0,scrollHeight:0,style:{},classList:{add(){},remove(){}},focus(){},matches(){return false;}};
  }
  const fakeDocument = {
    body: {dataset:{},appendChild(){}},
    getElementById(id){return id==='app'?app:element(id);},
    querySelector(s){return s === '#app' ? app : /^#[\w-]+$/.test(s)?element(s.slice(1)):null;},
    addEventListener(type,handler){(handlers[type] ||= []).push(handler);},
    createElement(){return {click(){},remove(){}};}
  };
  let timerId=0;
  const sandbox = {window:{SealSeekDemo:D,EasyWorkCases:C},document:fakeDocument,Blob,URL:{createObjectURL(blob){downloads.push(blob);return 'blob:test';},revokeObjectURL(){}},
    localStorage:{getItem(k){return store[k]||null;},setItem(k,v){store[k]=v;},removeItem(k){delete store[k];}},
    setTimeout(fn,delay){if(options.manualRuns&&delay===280)runTimers.push(fn);else queueMicrotask(fn);return ++timerId;},clearTimeout(){},navigator:{},console};
  if (standalone) {
    const html=fs.readFileSync(path.join(__dirname,'../dist/demo.html'),'utf8');
    assert.doesNotMatch(html,/<script[^>]+src=/);
    assert.doesNotMatch(html,/<link[^>]+stylesheet/);
    for (const block of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) vm.runInNewContext(block[1],sandbox);
  } else vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8'),sandbox);
  function dispatch(type,event){for(const h of handlers[type]||[])h(event);}
  function clickNow(action,data={}){const b={dataset:{action,...data},disabled:false};dispatch('click',{target:{closest(){return b;}}});}
  const settle=()=>new Promise(r=>setImmediate(r));
  return { app, downloads, store, element, portfolio(){return JSON.parse(store['easywork-portfolio-v1']);}, state(){return JSON.parse(store['sealseek-overseas-demo-20261030-v1']);},
    clickNow,
    async click(action,data={}){clickNow(action,data);await settle();},
    async input(id,value){const target=element(id);assert.ok(target,'Expected visible input #'+id);target.value=value;dispatch('input',{target});await settle();},
    async submit(id,values={}){for(const [field,value] of Object.entries(values)){const el=element(field);assert.ok(el,'Expected form field #'+field);el.value=value;}dispatch('submit',{target:{id},preventDefault(){}});await settle();},
    async change(id,value){dispatch('change',{target:{id,value}});await settle();},
    async finishRun(){let steps=0;while(runTimers.length){assert.ok(++steps<20,'Run did not settle');runTimers.shift()();await settle();}},
    pendingRunSteps(){return runTimers.length;},
    rowIds(){const list=element('inquiry-list');assert.ok(list,'Expected dashboard inquiry list');return [...list.innerHTML.matchAll(/class="inquiry-row"[^>]*data-id="([^"]+)"/g)].map(m=>m[1]);},
    statCounts(){return Object.fromEntries([...markup.matchAll(/class="stat-card[^>]*data-status="([^"]+)"[\s\S]*?class="stat-count">(\d+)<\/strong>/g)].map(m=>[m[1],Number(m[2])]));}
  };
}
function scenario(){let s=D.createInitialState();s=D.applyInstruction(s,D.DATA.scenarioPrompts[1]).state;s=D.applyInstruction(s,D.DATA.scenarioPrompts[2]).state;return s;}

test('export uses the chosen version and its SKU assets, not current version assets',async()=>{
  const s=scenario();s.assetRefsByRevision={1:['asset-custom'],2:['asset-stock'],3:['asset-quote-template']};
  const ui=mount(s);await ui.click('view-version',{revision:'1'});await ui.click('export');
  const old=await ui.downloads[0].text();assert.match(old,/V1/);assert.match(old,/定制帆布袋 · 印花示意/);assert.doesNotMatch(old,/现货帆布袋 · 产品素材/);assert.doesNotMatch(old,/USD 540\.00/);
  await ui.click('latest');await ui.click('export');const current=await ui.downloads[1].text();
  assert.match(current,/USD 540\.00/);assert.match(current,/现货帆布袋 · 产品素材/);assert.match(current,/客户报价 · 双语模板/);assert.match(current,/最终总额<\/td><td>待确认/);
});
test('asset references reject a conflicting SKU and allow a matching SKU',async()=>{
  const ui=mount(scenario());await ui.click('attach-asset',{id:'asset-custom'});assert.equal(ui.state().linkedAssets?.includes('asset-custom')||false,false);
  await ui.click('attach-asset',{id:'asset-stock'});assert.equal(ui.state().assetRefsByRevision[3].includes('asset-stock'),true);
});
test('stage navigation does not execute business decisions or create versions',async()=>{
  const s=scenario();const ui=mount(s);await ui.click('open-case',{id:'mx-026'});
  const before=ui.state();for(const stage of ['1','2','3'])await ui.click('stage',{stage});
  assert.equal(ui.state().revision,before.revision);assert.equal(ui.state().optionStatus,before.optionStatus);
  assert.match(ui.app.innerHTML,/客户回复/);
});
test('case tabs keep draft, revisions and quantities isolated after switching and closing',async()=>{
  const ui=mount(scenario());const initial=ui.portfolio(),a=initial.cases[0],b=initial.cases[1];
  await ui.click('open-case',{id:a.id});await ui.click('suggest',{text:'把现货数量改成600件，其他条件不变。'});
  assert.equal(ui.state().quantity,600);
  await ui.click('open-case',{id:b.id});assert.equal(ui.state().quantity,b.state.quantity);
  await ui.click('close-case',{id:b.id});assert.equal(ui.portfolio().activeId,a.id);assert.equal(ui.state().quantity,600);
  await ui.click('close-case',{id:a.id});assert.equal(ui.portfolio().openIds.length,0);
  await ui.click('open-case',{id:b.id});assert.equal(ui.state().revision,b.state.revision);
  assert.equal(ui.portfolio().cases.find(c=>c.id===a.id).state.quantity,600);
});
test('ended cases reject business mutations and can explicitly reopen',async()=>{
  const ui=mount();const done=ui.portfolio().cases.find(c=>c.status==='done');
  await ui.click('open-case',{id:done.id});const revision=ui.state().revision;
  await ui.click('suggest',{text:'把数量改成600件'});await ui.click('check-item',{key:'fact-check'});await ui.click('assemble');
  assert.equal(ui.state().revision,revision);assert.equal(ui.state().reviewed?.['fact-check'],undefined);assert.deepEqual(ui.state().savedAssets,done.state.savedAssets);
  await ui.click('reopen-case');await ui.click('suggest',{text:'把数量改成600件'});assert.equal(ui.state().quantity,600);
});
test('opening the same inquiry twice creates only one tab and export identifies the inquiry',async()=>{
  const ui=mount(scenario());const id=ui.portfolio().cases[0].id;await ui.click('open-case',{id});await ui.click('open-case',{id});
  assert.equal(ui.portfolio().openIds.filter(x=>x===id).length,1);await ui.click('export');
  assert.match(await ui.downloads[0].text(),new RegExp(ui.portfolio().cases[0].code));
});

test('login lands on dashboard, logout preserves inquiries, and refresh returns to dashboard',async()=>{
  const ui=mount(undefined,false,{authenticated:false});
  assert.match(ui.app.innerHTML,/id="login-form"/);
  assert.doesNotMatch(ui.app.innerHTML,/class="dashboard-stats"/);
  await ui.submit('login-form',{'login-name':'小林'});
  assert.match(ui.app.innerHTML,/小林，开始今天的工作/);
  assert.deepEqual(ui.statCounts(),{todo:1,active:1,waiting:1,done:1});
  const id=ui.portfolio().cases[0].id;
  await ui.click('open-case',{id});
  await ui.input('chat-input','登录后保留的询盘草稿');
  await ui.click('logout');
  assert.equal(ui.store['easywork-demo-session-v1'],undefined);
  assert.match(ui.app.innerHTML,/id="login-form"/);
  assert.equal(ui.portfolio().cases.find(c=>c.id===id).state.workspaceUI.draft,'登录后保留的询盘草稿');
  const loggedOut=mount(undefined,false,{store:ui.store});
  assert.match(loggedOut.app.innerHTML,/id="login-form"/);
  await loggedOut.submit('login-form',{'login-name':'小林'});
  assert.match(loggedOut.app.innerHTML,/class="dashboard-stats"/);
  await loggedOut.click('open-case',{id});
  assert.equal(loggedOut.element('chat-input').value,'登录后保留的询盘草稿');
  const refreshed=mount(undefined,false,{store:ui.store});
  assert.match(refreshed.app.innerHTML,/class="dashboard-stats"/);
  assert.equal(refreshed.element('chat-input'),null);
  assert.deepEqual(refreshed.portfolio().openIds,[id]);
});

test('new inquiry form opens an empty case without importing the previous case business data',async()=>{
  const ui=mount(scenario()),id=ui.portfolio().cases[0].id;
  await ui.click('open-case',{id});
  await ui.click('suggest',{text:'把现货数量改成600件，其他条件不变。'});
  await ui.input('chat-input','上一位客户的私有草稿');
  await ui.click('result-tab',{result:'reply'});
  await ui.input('reply-editor','上一位客户的西语回复草稿');
  await ui.click('assemble');
  const before=ui.portfolio().cases.find(c=>c.id===id).state;
  await ui.click('new-case');
  await ui.submit('case-form',{'case-title':'新客户独立询盘','case-customer':'Nuevo Trading'});
  const p=ui.portfolio(),created=p.cases.find(c=>c.id===p.activeId);
  assert.equal(p.cases.length,5);
  assert.notEqual(created.id,id);
  assert.equal(created.title,'新客户独立询盘');
  assert.equal(created.customer,'Nuevo Trading');
  assert.equal(created.status,'todo');
  assert.equal(created.state.revision,0);
  assert.equal(created.state.quantity,1000);
  assert.deepEqual(created.state.versions,[]);
  assert.deepEqual(created.state.messages,[]);
  assert.deepEqual(created.state.savedAssets,[]);
  assert.equal(created.state.replyDrafts,undefined);
  assert.equal(created.state.workspaceUI.draft,'');
  assert.deepEqual(p.cases.find(c=>c.id===id).state,before);
  assert.deepEqual(p.openIds,[id,created.id]);
  await ui.click('open-case',{id});
  assert.equal(ui.state().quantity,600);
  assert.equal(ui.element('chat-input').value,'上一位客户的私有草稿');
});

test('in-flight generation blocks tab switching, closing, logout and status changes without crossing cases',async()=>{
  const ui=mount(scenario(),false,{manualRuns:true}),[a,b]=ui.portfolio().cases;
  await ui.click('open-case',{id:b.id});
  await ui.click('open-case',{id:a.id});
  const beforeB=ui.portfolio().cases.find(c=>c.id===b.id).state;
  const beforeTabs=ui.portfolio().openIds;
  await ui.click('suggest',{text:'把现货数量改成600件，其他条件不变。'});
  assert.equal(ui.pendingRunSteps(),1);
  assert.match(ui.app.innerHTML,/class="run-steps"/);
  await ui.click('open-case',{id:b.id});
  await ui.click('close-case',{id:a.id});
  await ui.click('logout');
  await ui.click('new-case');
  await ui.change('case-status','done');
  assert.ok(ui.store['easywork-demo-session-v1']);
  assert.equal(ui.portfolio().activeId,a.id);
  assert.deepEqual(ui.portfolio().openIds,beforeTabs);
  assert.equal(ui.portfolio().cases.find(c=>c.id===a.id).status,'active');
  assert.equal(ui.portfolio().cases.length,4);
  assert.doesNotMatch(ui.app.innerHTML,/id="login-form"|id="case-form"/);
  await ui.finishRun();
  const after=ui.portfolio();
  assert.equal(after.cases.find(c=>c.id===a.id).state.quantity,600);
  assert.equal(after.cases.find(c=>c.id===a.id).state.revision,a.state.revision+1);
  assert.deepEqual(after.cases.find(c=>c.id===b.id).state,beforeB);
  assert.doesNotMatch(ui.app.innerHTML,/class="run-steps"/);
});

test('refreshing while B is active preserves B workspace and reply drafts when returning to A and back',async()=>{
  const ui=mount(scenario()),a=ui.portfolio().cases[0],b=ui.portfolio().cases[2];
  await ui.click('open-case',{id:a.id});
  await ui.click('stage',{stage:'2'});
  await ui.input('chat-input','仅属于 A 的草稿');
  await ui.click('open-case',{id:b.id});
  await ui.click('stage',{stage:'3'});
  await ui.click('language',{lang:'en-US'});
  assert.equal(ui.portfolio().cases.find(c=>c.id===b.id).state.workspaceUI.language,'en-US','Language changes must persist without requiring a later edit');
  await ui.input('reply-editor','B-only English revision 2 draft');
  await ui.input('chat-input','仅属于 B 的草稿');
  await ui.click('view-version',{revision:'1'});
  const expectedUI={draft:'仅属于 B 的草稿',language:'en-US',workPhase:3,result:'reply',viewRevision:1,pendingContext:[]};
  assert.deepEqual(ui.portfolio().cases.find(c=>c.id===b.id).state.workspaceUI,expectedUI,'History selection must persist before refresh');
  const refreshed=mount(undefined,false,{store:ui.store});
  assert.match(refreshed.app.innerHTML,/class="dashboard-stats"/);
  assert.deepEqual(refreshed.portfolio().cases.find(c=>c.id===b.id).state.workspaceUI,expectedUI,'Booting the dashboard must not overwrite the active case workspace');
  await refreshed.click('open-case',{id:a.id});
  assert.equal(refreshed.element('chat-input').value,'仅属于 A 的草稿');
  assert.equal(refreshed.state().workspaceUI.workPhase,2);
  assert.equal(refreshed.state().workspaceUI.language,'es-MX');
  assert.equal(refreshed.state().workspaceUI.viewRevision,null);
  assert.equal(refreshed.state().replyDrafts,undefined);
  await refreshed.click('open-case',{id:b.id});
  assert.deepEqual(refreshed.state().workspaceUI,expectedUI);
  assert.equal(refreshed.element('chat-input').value,'仅属于 B 的草稿');
  assert.match(refreshed.app.innerHTML,/正在查看 V1 历史/);
  await refreshed.click('latest');
  assert.equal(refreshed.state().workspaceUI.viewRevision,null,'Returning to latest must persist');
  assert.equal(refreshed.element('reply-editor').value,'B-only English revision 2 draft');
  assert.equal(refreshed.state().replyDrafts[2]['en-US'],'B-only English revision 2 draft');
});

test('dashboard cards, filtered rows and empty states track actual inquiry status changes',async()=>{
  const ui=mount();
  assert.deepEqual(ui.statCounts(),{todo:1,active:1,waiting:1,done:1});
  const cases=ui.portfolio().cases;
  for(const status of ['todo','active','waiting','done']){
    await ui.click('dashboard-filter',{status});
    assert.deepEqual(ui.rowIds(),cases.filter(c=>c.status===status).map(c=>c.id));
  }
  const todo=cases.find(c=>c.status==='todo'),waiting=cases.find(c=>c.status==='waiting');
  await ui.click('open-case',{id:todo.id});
  await ui.change('case-status','waiting');
  await ui.click('nav',{view:'dashboard'});
  assert.deepEqual(ui.statCounts(),{todo:0,active:1,waiting:2,done:1});
  await ui.click('dashboard-filter',{status:'todo'});
  assert.deepEqual(ui.rowIds(),[]);
  assert.match(ui.app.innerHTML,/这里暂时没有询盘/);
  await ui.click('dashboard-filter',{status:'waiting'});
  assert.deepEqual(new Set(ui.rowIds()),new Set([todo.id,waiting.id]));
  await ui.input('dashboard-search','Luna');
  assert.deepEqual(ui.rowIds(),[waiting.id]);
  await ui.click('dashboard-filter',{status:'all'});
  assert.deepEqual(ui.rowIds(),cases.map(c=>c.id));
});

test('standalone bundle boots and exports the same version without external runtime files',async()=>{
  const ui=mount(scenario(),true);assert.match(ui.app.innerHTML,/EasyWork/);await ui.click('export');
  const report=await ui.downloads[0].text();assert.match(report,/USD 540\.00/);assert.match(report,/Español/);assert.match(report,/最终总额<\/td><td>待确认/);
  if(process.env.DEMO_REPORT_OUTPUT) fs.writeFileSync(process.env.DEMO_REPORT_OUTPUT,report);
});

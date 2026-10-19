const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function setup(){
  const elements=new Map(),buttons=new Map(),calls=[],answers=[];
  const $=key=>{if(!elements.has(key))elements.set(key,{innerHTML:'',textContent:'',value:key==='#monitor-hours'?'24':'all'});return elements.get(key);};
  const transactions=Array.from({length:11},(_,i)=>({id:'r'+i,created:'2026-10-19',user:'worker',project:'P',photos:1,state:'evidence_review',erp:'review',telegram:'ok',ageMinutes:1}));
  const api=async(path,body)=>{
    calls.push([path,body]);
    if(path.startsWith('/api/admin/monitor?'))return {summary:{total:11,ok:0,pending:0,stuck:0,review:11,failed:0},transactions};
    if(path==='/api/admin/notifications/pending')return {deliveries:[],topics:[{key:'incident_topic'}]};
    return {ok:true};
  };
  const context={window:{campoUi:{$,esc:String,heading:()=>'',api,toast:()=>{}}},
    prompt:()=>answers.shift(),setInterval:()=>1,clearInterval:()=>{},
    document:{hidden:false,querySelectorAll(selector){
      const html=selector==='[data-evidence]'?$('#monitor-table').innerHTML:selector==='[data-delivery],[data-topic]'?$('#monitor-notifications').innerHTML:'';
      const values=[...html.matchAll(/data-(evidence|topic|delivery)="([^"]+)"/g)].map(m=>({dataset:{[m[1]]:m[2]}}));
      buttons.set(selector,values);return values;
    }}};
  vm.runInNewContext(fs.readFileSync('frontend/monitor.js','utf8'),context);
  await context.window.campoMonitor.render();
  return {$,buttons,calls,answers};
}

test('evidence reconciliation remains usable after changing monitor page',async()=>{
  const t=await setup();
  t.$('#monitor-next').onclick();
  const button=t.buttons.get('[data-evidence]')[0];
  assert.equal(button.dataset.evidence,'r10');
  assert.equal(typeof button.onclick,'function');
  t.answers.push('Verificado','');await button.onclick();
  assert.equal(t.calls.find(c=>c[0]==='/api/admin/monitor/evidence')[1].id,'r10');
});

test('topic recovery accepts a numeric topic id and requires verification note',async()=>{
  const t=await setup();
  t.answers.push('Tema comprobado','33');
  await t.buttons.get('[data-delivery],[data-topic]')[0].onclick();
  const body=t.calls.find(c=>c[0]==='/api/admin/notifications/resolve')[1];
  assert.equal(body.topicId,33);assert.equal(body.verified,true);
});

test('audit loader fetches subsequent pages for filtering and full export',async()=>{
  const source=fs.readFileSync('frontend/admin.js','utf8');
  const fragment=source.slice(source.indexOf('    const loadAudit='),source.indexOf('    const load=async()=>'));
  const calls=[];
  const context={api:async path=>{calls.push(path);return path.endsWith('=0')?{entries:[{id:1}],nextOffset:500}:{entries:[{id:2}],nextOffset:null};}};
  vm.runInNewContext(fragment+'\nglobalThis.loadAudit=loadAudit;',context);
  const data=await context.loadAudit();
  assert.equal(data.entries.length,2);assert.deepEqual(calls,['/api/admin/audit?offset=0','/api/admin/audit?offset=500']);
});

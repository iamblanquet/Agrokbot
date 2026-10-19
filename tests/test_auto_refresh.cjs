const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function refreshFixture(fail=false){
  const state={user:'worker',catalog:{old:true},reports:[]},writes=[];
  const storage={write:async(store,value,key)=>{if(fail)throw Error('Almacenamiento lleno');writes.push({store,value,key});},purgeDeliveredPhotos:async()=>{}};
  const context={window:{campoStorage:storage},Date};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/sync.js'),'utf8'),context);
  const api=async p=>p==='/api/catalog'?{projects:[{id:'p'}],tasks:[{id:'t'}],employees:[{id:'e'}]}:p==='/api/reports'?{reports:[],topics:[]}:{};
  return {state,writes,refresh:()=>context.window.campoSync.refresh({state,api})};
}
test('field data and timestamp are committed together without clearing queue',async()=>{
  const t=refreshFixture();await t.refresh();assert.equal(t.writes.length,1);assert.equal(t.writes[0].key,'snapshot:worker');
  assert.equal(t.writes[0].store,'meta');assert.ok(t.state.catalog.offlineSavedAt);assert.equal(t.state.catalog.employees.length,1);
});
test('failed local save retains previous catalog and never claims download success',async()=>{
  const t=refreshFixture(true);await assert.rejects(t.refresh(),/Almacenamiento/);assert.equal(t.state.catalog.old,true);assert.equal(t.state.catalog.offlineSavedAt,undefined);
});
test('focus, visibility and push wake open app without extra user action',()=>{
  const handlers={},state={user:'worker'},calls=[];
  const context={state,online:()=>true,$:()=>({hidden:false}),Date,
    sync:()=>calls.push('sync'),window:{addEventListener:(event,fn)=>handlers[event]=fn},
    document:{hidden:false,addEventListener:(event,fn)=>handlers[event]=fn},
    navigator:{serviceWorker:{addEventListener:(event,fn)=>handlers[event]=fn}}};
  const source=fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8');
  vm.runInNewContext(source.slice(source.indexOf('let lastAutomaticSync='),source.indexOf("document.querySelectorAll('[data-view]')",source.indexOf('let lastAutomaticSync='))),context);
  handlers.focus();handlers.visibilitychange();assert.equal(calls.length,1);
  handlers.message({data:{type:'campo-refresh-catalog'}});assert.equal(calls.length,2);
  state.syncing=true;handlers.message({data:{type:'campo-refresh-catalog'}});assert.equal(calls.length,2);
});

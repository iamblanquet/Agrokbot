const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

async function run({offline=false, reject=false, failPhoto=false, completed=false}={}) {
  const calls=[], queue=new Map();
  const item={id:'report',state:'pending',photos:[{id:'photo',data:'data:image/jpeg;base64,AAAA'}],payload:{id:'report',photos:['photo']}};
  queue.set(item.id,item);
  const storage={purgeDeliveredPhotos:async()=>{},write:async(store,value)=>{if(store==='queue')queue.set(value.id,value);},delete:async(id)=>queue.delete(id)};
  const context={window:{campoStorage:storage},Date};
  vm.createContext(context);
  vm.runInContext(readFileSync(require('node:path').join(__dirname,'../frontend/sync.js'),'utf8'),context);
  const state={user:'dev',local:[item],reports:[]};
  const api=async(path,body)=>{
    calls.push(path);
    if(path==='/api/me')return {user:'dev'};
    if(path==='/api/reports'){
      if(body&&completed)throw Object.assign(new Error('La tarea ya está finalizada'),{status:409,code:'task_completed'});
      return body?{id:'report',state:reject?'erp_review':'photos_pending'}:{reports:[],topics:[]};
    }
    if(path==='/api/photos'&&failPhoto)throw Object.assign(new Error('sin conexión'),{status:503});
    return {};
  };
  await context.window.campoSync.sync({state,api,online:()=>!offline,banner:()=>{},updateChrome:()=>{},reloadLocal:async()=>{state.local=[...queue.values()];},render:()=>{}});
  return {calls,queue};
}
test('offline conserva fotos y reporte sin solicitudes', async()=>{
  const {calls,queue}=await run({offline:true});assert.equal(calls.length,0);assert.equal(queue.size,1);
});
test('crea asiento antes de enviar fotografía',async()=>{
  const {calls,queue}=await run();assert.ok(calls.indexOf('/api/reports')<calls.indexOf('/api/photos'));assert.equal(queue.size,0);
});
test('fallo de carga conserva el pendiente para reintentar',async()=>{
  const {queue}=await run({failPhoto:true});assert.equal(queue.get('report').state,'pending');assert.equal(queue.get('report').photos.length,1);
});
test('asiento incierto conserva fotos y bloquea su carga',async()=>{
  const {calls,queue}=await run({reject:true});assert.ok(!calls.includes('/api/photos'));assert.equal(queue.get('report').state,'invalid');
});

test('completed task rejects stale offline report without losing its photos',async()=>{
  const {calls,queue}=await run({completed:true});
  assert.equal(queue.get('report').state,'invalid');
  assert.equal(queue.get('report').photos.length,1);
  assert.ok(!calls.includes('/api/photos'));
});

test('limpieza IndexedDB borra solo reportes publicados del usuario',async()=>{
  const deleted=[];
  const context={window:{},db:{transaction:()=>{
    const tx={objectStore:store=>({delete:key=>deleted.push([store,key])})};
    queueMicrotask(()=>tx.oncomplete());return tx;
  }}};
  vm.createContext(context);
  vm.runInContext(readFileSync(require('node:path').join(__dirname,'../frontend/storage.js'),'utf8'),context);
  vm.runInContext('campoStorageDatabase.current=db',context);
  await context.window.campoStorage.purgeDeliveredPhotos('dev',[
    {id:'ready',state:'published'},{id:'pending',state:'photos_pending'},
    {id:'failed',state:'telegram_failed'},{id:'demo',state:'demo_published'}
  ]);
  assert.deepEqual(deleted,[['meta','photos:dev:ready'],['queue','ready']]);
});

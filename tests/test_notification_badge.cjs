const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
test('morning push wakes open clients to refresh',async()=>{
  const handlers={},messages=[],pending=[];
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/sw.js'),'utf8'),{
    self:{addEventListener:(name,fn)=>handlers[name]=fn,registration:{showNotification:async()=>{}}},
    clients:{matchAll:async()=>[{postMessage:message=>messages.push(message)}]}
  });
  handlers.push({data:{json:()=>({refreshCatalog:true})},waitUntil:p=>pending.push(p)});
  await Promise.all(pending);assert.equal(messages[0].type,'campo-refresh-catalog');
});
test('push includes app icon and cached monochrome badge',async()=>{
  const handlers={},notifications=[];
  const source=fs.readFileSync(path.join(__dirname,'../public/sw.js'),'utf8');
  vm.runInNewContext(source,{self:{addEventListener:(name,handler)=>handlers[name]=handler,
    registration:{showNotification:async(title,options)=>notifications.push({title,options})}}});
  for(const data of [{title:'PRUEBA',body:'Aviso'},null]){
    let pending;
    handlers.push({data:data?{json:()=>data}:null,waitUntil:p=>pending=p});
    await pending;
  }
  for(const {options} of notifications){
    assert.equal(options.icon,'/icon-192.png');
    assert.equal(options.badge,'/agrokool-mark-white.png');
    assert.ok(fs.existsSync(path.join(__dirname,'../public',options.badge)));
  }
  assert.match(source,/const SHELL = .*'\/agrokool-mark-white.png'/);
});

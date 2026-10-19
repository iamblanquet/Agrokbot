const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');

test('restarted worker serves every feature asset offline without another install',async()=>{
  const handlers={};
  const cached={cached:true};
  vm.runInNewContext(fs.readFileSync('public/sw.js','utf8'),{
    self:{addEventListener:(n,f)=>handlers[n]=f,location:{origin:'https://campo.test'}},
    URL,fetch:()=>Promise.reject(new Error('offline')),caches:{match:async()=>cached}
  });
  for(const path of ['/app.js','/journal.js','/journal.css','/incidents.js']){
    let response;
    handlers.fetch({request:{url:'https://campo.test'+path,method:'GET',mode:'cors'},respondWith:p=>response=p});
    assert.ok(response,path+' must be intercepted');
    assert.equal(await response,cached);
  }
});

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/admin.js'),'utf8');
function setup(permission='granted',subscription={endpoint:'own'},failure=false){
  const button={},status={},calls=[];
  const context={$:id=>id==='#admin-test-push'?button:status,window:{Notification:{}},Notification:{permission},
    navigator:{serviceWorker:{getRegistration:async()=>({pushManager:{getSubscription:async()=>subscription}})}},
    api:async(...args)=>{calls.push(args);assert.equal(button.disabled,true);if(failure)throw Error('Falló el envío');return {message:'Aceptada por proveedor'};}};
  vm.runInNewContext(source.slice(source.indexOf("    $('#admin-test-push').onclick="),source.indexOf("    let editingUser=")),context);
  return {button,status,calls};
}
test('admin button sends own device endpoint and displays acceptance',async()=>{
  const t=setup();await t.button.onclick();assert.equal(t.calls.length,1);assert.equal(t.calls[0][0],'/api/admin/notifications/test');assert.equal(t.calls[0][1].endpoint,'own');assert.equal(t.status.textContent,'Aceptada por proveedor');assert.equal(t.button.disabled,false);
});
test('missing permissions or subscription do not send',async()=>{
  for(const t of [setup('denied'),setup('default'),setup('granted',null)]){await t.button.onclick();assert.equal(t.calls.length,0);assert.match(t.status.textContent,/campana/);assert.equal(t.button.disabled,false);}
});
test('failed send is displayed and button becomes usable again',async()=>{
  const t=setup('granted',{endpoint:'own'},true);await t.button.onclick();assert.equal(t.status.textContent,'Falló el envío');assert.equal(t.button.disabled,false);
});

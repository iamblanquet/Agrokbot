const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(){
  const calls=[];
  const context={window:{campoRestorePush:async()=>calls.push('restore')},navigator:{serviceWorker:{getRegistration:async()=>({pushManager:{getSubscription:async()=>({endpoint:'device'})}})}}};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../frontend/auth.js'),'utf8'),context);
  const args={state:{local:[],user:'old'},api:async(path)=>{calls.push(path);return {user:'new'};},storage:{get:async()=>null,write:async()=>{},clear:async()=>calls.push('clear')},showLogin:()=>{},toast:()=>{},reloadLocal:async()=>{},showApp:()=>{},sync:async()=>{}};
  return {auth:context.window.campoAuth,args,calls};
}
test('logout detaches device before destroying session',async()=>{
  const t=setup();await t.auth.logout(t.args);assert.deepEqual(t.calls,['/api/notifications/unsubscribe','/api/logout','clear']);assert.equal(t.args.state.user,null);
});
test('login restores push only after new account is established',async()=>{
  const t=setup();await t.auth.login(t.args);assert.equal(t.args.state.user,'new');assert.deepEqual(t.calls,['/api/login','restore']);
});
test('pending reports prevent logout and subscription detachment',async()=>{
  const t=setup();t.args.state.local=[{}];await t.auth.logout(t.args);assert.deepEqual(t.calls,[]);
});

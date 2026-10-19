const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/app.js'),'utf8');
function setup({permission='granted',subscription={endpoint:'test'},registered=true,fail=false}={}){
  const bell={dataset:{},setAttribute(k,v){this[k]=v;}};
  let calls=0;
  const context={state:{user:'tester'},$:id=>id==='#app'?{hidden:false}:bell,
    window:{PushManager:{},Notification:{}},Notification:{permission},Date,
    navigator:{serviceWorker:{getRegistration:async()=>({pushManager:{getSubscription:async()=>subscription}})}},
    updateNotificationNotice(){},api:async()=>{calls++;if(fail)throw Error('offline');return {subscribed:registered};}};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('let notificationRequestBusy='),source.indexOf('function updateNotificationNotice(')),context);
  return {bell,context,calls:()=>calls,refresh:()=>vm.runInContext('refreshNotificationState(true)',context)};
}
test('reload restores active bell from browser and own server subscription',async()=>{
  const t=setup();await t.refresh();assert.equal(t.bell.dataset.notificationState,'active');assert.equal(t.bell['aria-pressed'],'true');
});
test('permission alone does not imply active subscription',async()=>{
  for(const options of [{subscription:null},{registered:false}]){const t=setup(options);await t.refresh();assert.equal(t.bell.dataset.notificationState,'inactive');}
});
test('denied permission is blocked and does not call server',async()=>{
  const t=setup({permission:'denied'});await t.refresh();assert.equal(t.bell.dataset.notificationState,'blocked');assert.equal(t.calls(),0);
});
test('offline status is unknown rather than deactivated',async()=>{
  const t=setup({fail:true});await t.refresh();assert.equal(t.bell.dataset.notificationState,'unknown');
});
test('a new page instance recovers state without requesting permission',async()=>{
  for(let i=0;i<2;i++){const t=setup();await t.refresh();assert.equal(t.bell.dataset.notificationState,'active');}
});

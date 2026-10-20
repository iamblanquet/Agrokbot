const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(hash=''){
  const context={window:{},location:{hash,search:''},URLSearchParams};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../frontend/auth.js'),'utf8'),context);
  return context.window.campoAuth;
}
test('Mini App automatically sends signed data through normal login flow',async()=>{
  const auth=setup('#tgWebAppData='+encodeURIComponent('user=x&hash=signed'));
  let body;const els={};
  assert.equal(await auth.setupTelegram({showLogin(){},login:async b=>{body=b;},$:s=>els[s]??={}}),true);
  assert.equal(body.initData,'user=x&hash=signed');
});
test('ordinary PWA keeps PIN and failed Telegram authentication exposes PIN fallback',async()=>{
  assert.equal(await setup().setupTelegram({}),false);
  const els={};
  await setup('#tgWebAppData=invalid').setupTelegram({showLogin(){},login:async()=>{throw Error('No vinculado');},$:s=>els[s]??={}});
  assert.equal(els['#login-error'].textContent,'No vinculado');
});
test('Telegram auto login cannot clear pending reports belonging to another account',async()=>{
  const calls=[];let cleared=false;
  await assert.rejects(setup().login({
    body:{initData:'signed'},state:{},api:async path=>{calls.push(path);return {user:'new'};},
    storage:{get:async()=> 'previous',all:async()=>[{}],clear:async()=>{cleared=true;}}
  }),/pendientes/);
  assert.equal(cleared,false);
  assert.deepEqual(calls,['/api/login','/api/logout']);
});

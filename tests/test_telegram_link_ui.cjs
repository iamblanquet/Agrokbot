const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/app.js'),'utf8').split('const $ =')[0];
function setup(api){
  const elements={};
  const el=id=>elements[id]??=( {hidden:false,disabled:false,textContent:''} );
  const ctx={document:{querySelector:el},window:{campoApi:api,addEventListener(){}},confirm:()=>true};
  vm.runInNewContext(source,ctx);
  return {ctx,el};
}
test('Telegram account renders linked state and handles offline without stale identity',async()=>{
  let offline=false;
  const t=setup(async()=>{if(offline)throw Error('Sin conexión');return {linked:true,telegram:{username:'ana',telegram_id:'123'}};});
  await t.ctx.refreshTelegramAccount();
  assert.equal(t.el('#telegram-account-status').textContent,'Vinculado: @ana');
  assert.equal(t.el('#telegram-link-create').hidden,true);
  assert.equal(t.el('#telegram-link-remove').hidden,false);
  offline=true;await t.ctx.refreshTelegramAccount();
  assert.equal(t.el('#telegram-account-status').textContent,'Sin conexión');
  assert.equal(t.el('#telegram-link-remove').hidden,true);
});
test('Telegram link creation exposes expiring link and restores button on error',async()=>{
  let fail=false;
  const t=setup(async()=>{if(fail)throw Error('Falló');return {url:'https://t.me/example?start=link_test'};});
  const button=t.el('#telegram-link-create');
  await button.onclick();
  assert.equal(t.el('#telegram-link-open').hidden,false);
  assert.match(t.el('#telegram-link-open').href,/^https:\/\/t.me\//);
  assert.equal(button.disabled,false);
  fail=true;await button.onclick();
  assert.equal(button.disabled,false);
  assert.equal(t.el('#telegram-account-status').textContent,'Falló');
});

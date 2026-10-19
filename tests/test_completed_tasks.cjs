const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('public/app.js','utf8');
const helper=source.slice(source.indexOf('function taskCompleted('),source.indexOf('async function openCapture('));

test('completed task cannot open a capture even through a direct call',async()=>{
  for(const task of [{progressBps:10000,status:'IN_PROGRESS'},{progressBps:9000,status:'FINISHED'},{status:'COMPLETED'}]){
    const notices=[];
    const context={taskById:()=>task,toast:m=>notices.push(m)};
    vm.runInNewContext(helper+source.slice(source.indexOf('async function openCapture('),source.indexOf("$('#close-dialog').onclick"))+'\nglobalThis.open=openCapture;',context);
    await context.open('task');
    assert.match(notices[0],/no admite reportes adicionales/);
  }
});

test('submit is blocked if task completed while the form remained open',async()=>{
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);};
  const context={$,state:{currentTask:{id:'task',progressBps:9000}},taskById:()=>({id:'task',progressBps:10000})};
  vm.runInNewContext(helper+source.slice(source.indexOf("$('#report-form').onsubmit="),source.indexOf('async function refresh()')),context);
  await $('#report-form').onsubmit({preventDefault(){}});
  assert.match($('#form-error').textContent,/no admite reportes adicionales/);
  assert.equal($('#report-form button[type=submit]').disabled,false);
});

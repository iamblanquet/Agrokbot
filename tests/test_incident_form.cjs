const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8');
function capture(enabled,description='Fuga de agua'){
  const fields={
    '#report-author':{value:'Ana'},'#report-title':{value:''},'#work-stopped':{checked:false},
    '#report-incident':{checked:enabled},'#incident-description':{value:description},
    '#incident-priority':{value:'high'},'#incident-stops':{checked:true},
    '#work-quantity':{value:'2'},'#work-unit':{value:'ha'}
  };
  const context={$:id=>fields[id],document:{querySelector:()=>null,querySelectorAll:()=>[]},Date,state:{reachable:false},online:()=>false};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function captureDetails(){'),source.indexOf('function fileData(')),context);
  return vm.runInContext('captureDetails()',context);
}
test('incidence remains in offline report details without changing quantity',()=>{
  const result=capture(true);assert.equal(result.offline,true);assert.equal(result.quantity,2);
  assert.equal(result.incident.description,'Fuga de agua');assert.equal(result.incident.stopsWork,true);
});
test('unchecked incident is omitted even if text was entered',()=>{assert.equal(capture(false).incident,undefined);});
test('checked incidence requires description',()=>{assert.throws(()=>capture(true,' '),/Describe la incidencia/);});

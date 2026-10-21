const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('public/app.js','utf8');
function fixture(projects){
  const main={innerHTML:''}, filter={};
  const state={catalog:{projects,tasks:[]},config:{erpMode:'live'},local:[],selected:null,search:'',taskFilter:'all'};
  const context={state,$:s=>s==='#main'?main:s==='#project-filter'?filter:null,esc:s=>String(s??''),pct:n=>`${n/100} %`,heading:()=>'',projectById:id=>projects.find(p=>p.id===id),initProjectSlider(){},renderTaskTable(){}};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function projectCompleted('),source.indexOf('function initProjectSlider(')),context);
  return {context,state,main,filter,render:()=>context.renderProjects(),ids:()=>Array.from(context.visibleProjects(),p=>p.id)};
}
const projects=[{id:'a',name:'Activo',progressBps:1200},{id:'b',name:'Terminado',status:'FINISHED',progressBps:9000},{id:'c',name:'Al cien',progressBps:'10000'},{id:'d',name:'Cancelado',status:'CANCELLED',progressBps:10000}];

test('active default excludes finished and cancelled without deleting catalog',()=>{
  const f=fixture(projects);f.render();
  assert.deepEqual(f.ids(),['a']);
  assert.equal(f.filter.value,'active');
  assert.equal(f.state.catalog.projects.length,4);
  assert.equal(f.state.selected,'a');
});
test('finished and all filters retain history and reset task controls',()=>{
  const f=fixture(projects);f.render();
  f.state.search='old';f.state.taskPage=8;f.state.taskFilter='active';
  f.filter.onchange({target:{value:'done'}});
  assert.deepEqual(f.ids(),['b','c']);
  assert.equal(f.state.selected,'b');
  assert.equal(f.state.taskPage,1);assert.equal(f.state.search,'');assert.equal(f.state.taskFilter,'all');
  f.filter.onchange({target:{value:'all'}});
  assert.deepEqual(f.ids(),['a','b','c','d']);
  assert.equal(f.state.selected,'b');
});
test('when selected project completes refresh selects next visible project',()=>{
  const rows=[{id:'a',progressBps:1000},{id:'b',progressBps:0}];
  const f=fixture(rows);f.render();rows[0].progressBps=10000;f.render();
  assert.equal(f.state.selected,'b');
  rows[1].status='COMPLETED';f.render();
  assert.equal(f.state.selected,null);
  assert.match(f.main.innerHTML,/No hay proyectos con este filtro/);
  assert.match(f.main.innerHTML,/id="project-filter"/);
  assert.doesNotMatch(f.main.innerHTML,/id="task-table"/);
  f.filter.onchange({target:{value:'done'}});assert.equal(f.state.selected,'a');
});
test('empty offline catalog keeps filter and clear guidance',()=>{
  const f=fixture([]);f.render();
  assert.match(f.main.innerHTML,/Aún no hay proyectos descargados/);
  assert.match(f.main.innerHTML,/id="project-filter"/);
  assert.equal(f.state.selected,null);
});
test('task averages never determine whether entire project is finished',()=>{
  const f=fixture([{id:'a',progressBps:5000}]);
  f.state.catalog.tasks=[{projectId:'a',progressBps:10000}];f.render();
  assert.deepEqual(f.ids(),['a']);
  assert.match(f.main.innerHTML,/En seguimiento/);
});

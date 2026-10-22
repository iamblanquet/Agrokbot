const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');

test('tracked application and documentation use collaborator terminology',()=>{
  const oldTerm=new RegExp('\\bemple'+'ad[oa]s?\\b','i');
  const files=execFileSync('git',['ls-files'],{encoding:'utf8'}).trim().split(/\r?\n/);
  for(const file of files.filter(f=>/\.(py|js|cjs|html|css|md)$/.test(f))){
    assert.doesNotMatch(fs.readFileSync(file,'utf8'),oldTerm,file);
  }
});

test('terminology change preserves integration and offline identifiers',()=>{
  const app=fs.readFileSync('public/app.js','utf8');
  const html=fs.readFileSync('public/index.html','utf8');
  assert.match(app,/heading\('Colaboradores'/);
  assert.match(app,/<span class="emp-stat-label">Total de colaboradores<\/span>/);
  assert.doesNotMatch(app,/Total cuadrilla/);
  assert.match(app,/\/api\/employees\/delete/);
  assert.match(html,/data-view="employees"/);
  assert.match(html,/Guardar colaborador/);
  assert.match(fs.readFileSync('frontend/admin.js','utf8'),/employeeNumber/);
});

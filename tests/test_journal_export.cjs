const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../frontend/journal.js'), 'utf8');
function run(rows, filters = {}) {
  const button = {}, link = {click(){}, remove(){}};
  let blob;
  const context = {
    self: {rows, filters}, find: id => id === '#journal-export' ? button : {textContent:'Proyecto'},
    label: x => x, Blob, Date, URL: {createObjectURL: b => {blob=b;return 'blob:test';}, revokeObjectURL(){}},
    document: {createElement:()=>link, body:{append(){}}}, setTimeout: fn => fn()
  };
  const start = source.indexOf('      const f = self.filters;', source.indexOf('const draw ='));
  const end = source.indexOf('      // Franja de estadísticas', start);
  vm.runInNewContext(source.slice(start,end), context);
  button.onclick();
  return {button, blob};
}
test('combined task, status and responsible filters determine CSV rows', async () => {
  const base = {taskName:'Tarea', status:'IN_PROGRESS', responsible:'Ana', author:'Luis', attachments:[]};
  const result = run([{...base,id:'yes'}, {...base,id:'no',responsible:'Luis'}], {task:'Tarea',status:'IN_PROGRESS',author:'Ana'});
  const csv = await result.blob.text();
  assert.match(csv, /"yes"/); assert.doesNotMatch(csv, /"no"/);
});
test('exports all matches and escapes formulas, quotes and multiline notes', async () => {
  const rows = Array.from({length:25}, (_,i)=>({id:String(i),taskName:'=1+1',attachments:[],notes:'Texto "citado"\nOtra línea'}));
  const {blob} = run(rows);
  const csv = await blob.text();
  assert.match(csv, /"24"/); assert.match(csv, /"'=1\+1"/);
  assert.match(csv, /Texto ""citado""\nOtra línea/);
});
test('empty results and invalid dates disable download', () => {
  assert.equal(run([]).button.disabled,true);
  assert.equal(run([{id:'1'}], {from:'2026-10-20',to:'2026-10-01'}).blob,undefined);
});

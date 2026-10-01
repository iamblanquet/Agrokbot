'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = value => `${new Intl.NumberFormat('es-MX', {maximumFractionDigits:2}).format((value || 0) / 100)} %`;
const prettyDate = value => new Date(value).toLocaleString('es-MX', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
const today = () => {const d = new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const state = {user:null, catalog:{projects:[],tasks:[]}, config:{erpMode:'demo',telegramMode:'demo'}, reports:[], local:[], topics:[], view:'projects', selected:null, topic:null, search:'', taskFilter:'all', reportFilter:'all', simulation:false, reachable:navigator.onLine, syncing:false, currentTask:null,  install:null};
let toastTimer;

function openDatabase(){return window.campoStorage.open();}
function removeDemoCatalog(){return window.campoStorage.removeDemoCatalog();}
function dbGet(store,key){return window.campoStorage.get(store,key);}
function dbAll(){return window.campoStorage.all();}
function dbWrite(store,value,key){return window.campoStorage.write(store,value,key);}
function dbDelete(id){return window.campoStorage.delete(id);}
function dbClear(){return window.campoStorage.clear();}
async function reloadLocal(){state.local=await window.campoStorage.reloadLocal(state.user);}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5500);}
function banner(message,reauth=false){$('#global-banner').hidden=!message;$('#global-banner').textContent=message;if(reauth){const button=document.createElement('button');button.textContent='Iniciar sesión';button.onclick=()=>showLogin();$('#global-banner').append(button);}}
function online(){return !state.simulation && navigator.onLine;}
async function api(path,body){
  if(!online()){const e=new Error('Sin conexión. Tus reportes permanecen en este dispositivo.');e.offline=true;throw e;}
  try{
    const data=await window.campoApi(path,body);
    state.reachable=true;
    return data;
  }catch(error){
    state.reachable=false;
    updateChrome();
    throw error;
  }
}
function showLogin(){ $('#app').hidden=true;$('#login').hidden=false;$('#username').value=state.user || ''; }
function showApp(){ $('#login').hidden=true;$('#app').hidden=false;$('#profile-user').textContent=state.user;$('#avatar').textContent=state.user.slice(0,1).toUpperCase();if(state.isAdmin&&!$('[data-view="admin"]')){const b=document.createElement('button');b.className='nav-item';b.dataset.view='admin';b.textContent='⚙ Administración';b.onclick=()=>{state.view='admin';render();};document.querySelector('nav')?.append(b);}render(); }
function updateChrome(){
  const connected=online()&&state.reachable;
  $('#network').className=`connection ${connected?'online':'offline'}`;
  $('#network').textContent=state.simulation?'Prueba sin señal':connected?'Con conexión':'Sin conexión';
  $('#pending-count').textContent=state.local.length;
  $('#sync').disabled=state.syncing || !online();
  $('#sync span').textContent=state.syncing?'Sincronizando…':'Sincronizar';
  $('#cache-note').textContent=state.catalog.fetchedAt?`${state.catalog.projects.length} proyectos disponibles en este dispositivo.`:'Conecta para descargar tus proyectos.';
  $('#last-sync').textContent=state.catalog.fetchedAt?`DATOS DESCARGADOS · ${prettyDate(state.catalog.fetchedAt)}`:'DATOS AÚN NO DESCARGADOS';
  document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===state.view));
  $('#breadcrumb-current').textContent=({projects:'Proyectos',employees:'Empleados',reports:'Mis reportes',telegram:'Temas de Telegram',settings:'Conexiones'})[state.view];
}
function statusInfo(value){return ({pending:['Pendiente de sincronizar','amber'],conflict:['No registrado: conflicto','amber'],invalid:['No registrado: datos rechazados','red'],erp_sending:['Registrando en ERP','blue'],erp_review:['Verificar en ERP','red'],erp_rejected:['Rechazado por ERP','red'],telegram_pending:['ERP guardado · envío pendiente','blue'],telegram_sending:['Enviando a Telegram','blue'],telegram_failed:['ERP guardado · envío fallido','amber'],telegram_review:['ERP guardado · verificar envío','amber'],published:['Publicado en Telegram','green'],demo_published:['Publicado · simulación','green']})[value] || [value,''];}
function badge(value){const [label,color]=statusInfo(value);return `<span class="status ${color}">${esc(label)}</span>`;}
function taskStatus(task){return task.progressBps===10000?'<span class="status green">Finalizada</span>':task.progressBps>0?'<span class="status amber">En progreso</span>':'<span class="status">Sin iniciar</span>';}
function heading(title,subtitle,action=''){return `<div class="page-heading"><div><p class="eyebrow">SEGUIMIENTO OPERATIVO</p><h1>${title}</h1><p>${subtitle}</p></div>${action||`<span class="date-label">${new Date().toLocaleDateString('es-MX',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</span>`}</div>`;}
window.campoUi={ $, esc, heading, api, toast };
function taskById(id){return state.catalog.tasks.find(t=>t.id===id);}
function projectById(id){return state.catalog.projects.find(p=>p.id===id);}
function render(){updateChrome();({projects:renderProjects,employees:renderEmployees,reports:renderReports,telegram:renderTelegram,settings:renderSettings,admin:()=>window.campoAdmin?.render?.()})[state.view]();}
function renderProjects(){
  const projects=state.catalog.projects,tasks=state.catalog.tasks;
  if(!state.selected||!projectById(state.selected))state.selected=projects[0]?.id;
  $('#main').innerHTML=heading('Cada avance cuenta.','Consulta tus proyectos y registra el trabajo de hoy.')+`
    <section class="stats" aria-label="Resumen"><div class="stat"><span class="stat-label">Proyectos disponibles</span><strong>${projects.length.toString().padStart(2,'0')}</strong><small>en tu espacio</small></div><div class="stat"><span class="stat-label">Tareas por completar</span><strong>${tasks.filter(t=>t.progressBps<10000).length.toString().padStart(2,'0')}</strong><small>en seguimiento</small></div><div class="stat"><span class="stat-label">Reportes en este dispositivo</span><strong class="${state.local.length?'amber':''}">${state.local.length.toString().padStart(2,'0')}</strong><small>por sincronizar</small></div></section>
    <div class="section-heading"><h2>Mis proyectos</h2><span>${state.config.erpMode==='demo'?'Datos de demostración':'Catálogo del ERP'}</span></div>
    <section class="project-grid">${projects.map(p=>{const pt=tasks.filter(t=>t.projectId===p.id);const avg=pt.length?Math.round(pt.reduce((a,t)=>a+t.progressBps,0)/pt.length):0;const loc=p.operationLocationName?`${esc(p.operationLocationName)} · `:'' ;const line=esc(p.businessLine?.name||p.company?.name||'Operaciones');return `<button class="project-card ${state.selected===p.id?'selected':''}" data-project="${esc(p.id)}" aria-pressed="${state.selected===p.id}"><div class="project-meta"><span class="project-code">${esc(p.folio||p.code)}</span><span class="chip">${pt.length&&pt.every(t=>t.progressBps===10000)?'Completado':'En seguimiento'}</span></div><h3>${esc(p.name)}</h3><p class="subline">${loc}${line} · ${pt.length} tareas</p><div class="progress-label"><span>Promedio simple de tareas</span><strong>${pct(avg)}</strong></div><progress max="10000" value="${avg}" aria-label="Avance medio"></progress><div class="project-foot"><span>${pt.filter(t=>t.progressBps===10000).length} de ${pt.length} tareas completas</span><span class="selected-label">${state.selected===p.id?'Seleccionado':'Ver tareas <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>'}</span></div></button>`;}).join('')}</section>
    ${!projects.length?'<div class="empty"><h3>Aún no hay proyectos descargados</h3><p>Conecta al servidor y pulsa Sincronizar.</p></div>':`<section class="task-panel"><div class="task-panel-head"><div><h2>Tareas del proyecto</h2><p>${esc(projectById(state.selected)?.name)}</p></div><div class="filters"><input id="task-search" type="search" placeholder="Buscar tarea…" aria-label="Buscar tarea" value="${esc(state.search)}"><select id="task-filter" aria-label="Filtrar estado"><option value="all">Todos los estados</option><option value="active">Por completar</option><option value="done">Finalizadas</option></select></div></div><div id="task-table"></div></section>`}`;
  document.querySelectorAll('[data-project]').forEach(el=>el.onclick=()=>{state.selected=el.dataset.project;state.search='';renderProjects();});
  if($('#task-filter')){$('#task-filter').value=state.taskFilter;$('#task-filter').onchange=e=>{state.taskFilter=e.target.value;renderTaskTable();};$('#task-search').oninput=e=>{state.search=e.target.value;renderTaskTable();};renderTaskTable();}
}
function renderTaskTable(){
  const tasks=state.catalog.tasks.filter(t=>t.projectId===state.selected&&(state.taskFilter==='all'||(state.taskFilter==='done'?t.progressBps===10000:t.progressBps<10000))&&`${t.name} ${t.code}`.toLowerCase().includes(state.search.toLowerCase()));
  $('#task-table').innerHTML=tasks.length?`<div class="table-wrap"><table><thead><tr><th>TAREA / ACTIVIDAD</th><th class="person-column">RESPONSABLE</th><th>AVANCE</th><th class="status-column">ESTADO</th><th><span class="muted">ACCIÓN</span></th></tr></thead><tbody>${tasks.map(t=>{const wp=t.workPackage?.name?`${esc(t.workPackage.name)} · `:'' ;const act=esc(t.activity?.name||'');return `<tr><td class="task-name"><strong>${esc(t.name)}</strong><small><span class="task-code">${esc(t.code)}</span> ${wp}${act}</small></td><td class="person-column"><span class="person"><span class="person-circle">${esc((t.responsibleName||'—').split(' ').map(s=>s[0]).slice(0,2).join(''))}</span>${esc(t.responsibleName||'Sin asignar')}</span></td><td class="task-progress"><span>${pct(t.progressBps)}</span><progress max="10000" value="${Number(t.progressBps)||0}" aria-label="Avance de ${esc(t.code)}"></progress></td><td class="status-column">${taskStatus(t)}</td><td class="task-action"><button class="btn subtle" data-capture="${esc(t.id)}">Reportar</button></td></tr>`;}).join('')}</tbody></table></div><div class="table-caption">${tasks.length} tareas · Los reportes se publican en el tema de este proyecto después de sincronizar.</div>`:'<div class="empty"><h3>No hay tareas con este filtro</h3><p>Prueba otro estado o nombre.</p></div>';
  document.querySelectorAll('[data-capture]').forEach(el=>el.onclick=()=>openCapture(el.dataset.capture));
}
function combinedReports(){const localIds=new Set(state.local.map(r=>r.id));return [...state.local,...state.reports.filter(r=>!localIds.has(r.id))].sort((a,b)=>b.created.localeCompare(a.created));}
function renderReports(){
  const items=combinedReports().filter(r=>state.reportFilter==='all'||(state.reportFilter==='pending'?['pending','conflict','invalid'].includes(r.state):['published','demo_published'].includes(r.state)));
  $('#main').innerHTML=heading('Mis reportes','Del trabajo en campo al registro de tu equipo.')+`<div class="view-tools"><select id="report-filter" aria-label="Filtrar reportes"><option value="all">Todos los reportes</option><option value="pending">En este dispositivo</option><option value="published">Publicados</option></select><button id="export-reports" class="btn small">Exportar pendientes</button><span class="muted">${state.local.length} pendientes en este dispositivo</span></div><div class="report-list">${items.map(r=>{const p=r.payload,t=taskById(p.taskId||r.task_id),project=projectById(t?.projectId||r.project_id);return `<article class="report-card"><div class="report-card-head"><div><h3>${esc(t?.code||'Tarea')} · ${esc(t?.name||p.taskId||r.task_id)}</h3><span class="muted">${esc(project?.name||'Proyecto')}</span></div>${badge(r.state)}</div><p>${esc(p.notes)}</p>${crewSummary(p.crew)}${fieldSummary(p)}<div class="photo-grid" data-report-photos="${esc(r.id)}"></div><div class="report-meta"><strong>Avance: ${pct(p.progressBps)}</strong><span>Operación: ${esc(p.operationDate)}</span><span>Capturado: ${prettyDate(r.created)}</span><span>Ref. ${esc(r.id.slice(0,8))}</span></div>${r.error?`<div class="report-error">${esc(r.error)}</div>`:''}<div class="report-actions">${r.state==='telegram_failed'?`<button class="btn small" data-retry="${esc(r.id)}">Reintentar envío</button>`:''}</div></article>`;}).join('')||'<div class="empty"><h3>Tu primer reporte empieza en una tarea</h3><p>Selecciona un proyecto y pulsa Reportar.</p></div>'}</div>`;
  fillReportPhotos(items);
  $('#report-filter').value=state.reportFilter;$('#report-filter').onchange=e=>{state.reportFilter=e.target.value;renderReports();};
  $('#export-reports').onclick=exportPending;
  document.querySelectorAll('[data-retry]').forEach(el=>el.onclick=async()=>{try{await api('/api/retry-telegram',{id:el.dataset.retry});toast('Envío puesto en cola.');await sync();}catch(e){toast(e.message);}});
}
function renderTelegram(){
  const topics=state.topics;
  if(!topics.some(t=>t.project_id===state.topic))state.topic=topics[0]?.project_id;
  const reports=state.reports.filter(r=>r.project_id===state.topic&&['published','demo_published'].includes(r.state)).slice().reverse();
  $('#main').innerHTML=heading('Un proyecto. Un tema.',state.config.telegramMode==='demo'?'Vista de demostración: no se envía ningún mensaje a Telegram.':'Reportes enviados por el bot al supergrupo configurado.')+`<div class="telegram-layout"><aside class="topic-list"><h3>AGROKOOL · Operaciones</h3>${topics.map(t=>`<button class="topic-btn ${t.project_id===state.topic?'active':''}" data-topic="${esc(t.project_id)}"># ${esc(t.title)}<small>Tema ${esc(t.thread_id)}</small></button>`).join('')||'<p class="muted">Los temas se crean al publicar el primer reporte de cada proyecto.</p>'}</aside><section class="messages">${reports.map(r=>`<article class="message-bubble"><strong>Campo · Bot de reportes</strong><pre>${esc(r.message)}</pre><div class="photo-grid" data-report-photos="${esc(r.id)}"></div><small>${prettyDate(r.created)} · ${r.state==='demo_published'?'Simulación':'Enviado'}</small></article>`).join('')||'<div class="empty"><h3>Aquí aparecerán tus reportes</h3><p>Registra un avance y sincroniza para ver el tema de tu proyecto.</p></div>'}</section></div>`;
  fillReportPhotos(reports);
  document.querySelectorAll('[data-topic]').forEach(el=>el.onclick=()=>{state.topic=el.dataset.topic;renderTelegram();});
}
function renderSettings(){
   $('#main').innerHTML=heading('Conexiones','Estado de tus datos, acceso y herramientas de prueba.')+`<div class="settings-grid"><section class="setting-card"><h2>Registro de proyectos</h2><span class="status ${state.config.erpMode==='demo'?'amber':'green'}">${state.config.erpMode==='demo'?'ERP de demostración':'ERP real'}</span><p>${state.config.erpMode==='demo'?'Los avances se guardan en la base de datos local del prototipo. No se modifica el ERP real.':'Los avances confirmados se registran en la API externa del ERP.'}</p><p>El avance mostrado por proyecto es el promedio simple de sus tareas, no el cálculo ponderado del ERP.</p></section><section class="setting-card"><h2>Bot de Telegram</h2><span class="status ${state.config.telegramMode==='demo'?'amber':'green'}">${state.config.telegramMode==='demo'?'Envíos simulados':'Envíos reales'}</span><p>Un tema por proyecto. Los reportes de tareas se publican dentro del tema cuando el ERP confirma el registro.</p><p>${state.config.telegramMode==='demo'?'La pestaña Temas de Telegram permite probar el resultado sin un bot.':state.config.telegramConfigured?'Bot y grupo configurados en el servidor.':'Falta configurar el bot y el grupo en el servidor.'}</p></section><section class="setting-card"><h2>Prueba sin señal</h2><p>Suspende las conexiones de la aplicación para probar la captura local. Desactiva la prueba y sincroniza para enviarla.</p><label><input id="simulate" type="checkbox" ${state.simulation?'checked':''}> Simular modo offline</label><p class="storage-info">Esta opción simula la desconexión. La PWA también admite pérdida real de red después de su primera carga.</p></section><section class="setting-card"><h2>Este dispositivo</h2><p>${state.catalog.projects.length} proyectos descargados · ${state.local.length} reportes pendientes.</p><p id="storage-status">Comprobando almacenamiento…</p><button id="persist-storage" class="btn small">Proteger almacenamiento local</button><p class="storage-info">No borres los datos del navegador mientras tengas pendientes. Puedes exportarlos desde Mis reportes.</p></section><section class="setting-card wide"><h2>Acceso y alcance</h2><p>Sesión de ${esc(state.user)}. Las cuentas de campo solo reciben tareas cuyo empleado o asignación coincide con su relación ERP.</p><div class="settings-table"><div><small>Instalación</small><strong>Menú del navegador &gt; Instalar / Añadir a inicio</strong></div><div><small>Acceso desde teléfono o Telegram</small><strong>Requiere una dirección HTTPS</strong></div></div><p class="storage-info">La sesión inicial requiere conexión. Al volver a conectar, se verifican nuevamente los permisos antes de enviar pendientes.</p><button id="settings-logout" class="btn small">Cerrar sesión</button></section></div>`;
  $('#simulate').onchange=async e=>{state.simulation=e.target.checked;await dbWrite('meta',state.simulation,'simulation');state.reachable=!state.simulation;updateChrome();banner(state.simulation?'Prueba sin señal activa. Los nuevos reportes se guardarán en este dispositivo.':'');if(!state.simulation)await sync();};
  $('#settings-logout').onclick=logout;
  $('#persist-storage').onclick=async()=>{const granted=await navigator.storage?.persist?.();toast(granted?'Almacenamiento persistente habilitado.':'El navegador decide si concede almacenamiento persistente. Conserva una copia de tus pendientes.');updateStorage();};
  updateStorage();
}
async function updateStorage(){const persisted=await navigator.storage?.persisted?.();if($('#storage-status'))$('#storage-status').textContent=persisted?'Almacenamiento persistente habilitado.':'Almacenamiento local del navegador. El sistema puede eliminarlo si falta espacio.';}
async function openCapture(taskId){
  const task=taskById(taskId);
  if(!task){toast('La tarea no está en el catálogo. Sincroniza para actualizarlo.');return;}
  if(state.local.some(r=>r.payload.taskId===taskId&&r.state==='pending')){toast('Ya hay un reporte confirmado pendiente. Sincronízalo sin modificarlo.');return;}
  if(state.reports.some(r=>r.task_id===taskId&&['erp_review','erp_sending'].includes(r.state))){toast('Hay un registro de esta tarea por verificar en el ERP.');return;}
  state.currentTask={...task};
  $('#report-heading').textContent='Registrar avance';
  const project=projectById(task.projectId);const wp=task.workPackage?.name?` · ${esc(task.workPackage.name)}`:'';const act=task.activity?.name?` · ${esc(task.activity.name)}`:'';
  $('#report-task').innerHTML=`<strong>${esc(task.code)} · ${esc(task.name)}</strong><small>${esc(project?.name||'Proyecto')}${wp}${act} · Avance actual: ${pct(state.currentTask.progressBps)}</small>`;
  $('#operation-date').value=today();$('#operation-date').max=today();
  $('#progress-value').value=task.progressBps/100;
  $('#progress-value').min=state.currentTask.progressBps/100;$('#notes').value='';$('#form-error').textContent='';
  state.crew=[];state.crewSearch='';state.crewFilter='all';renderCrew();
  const profile=await dbGet('meta',`author:${state.user}`)||{};
  const details=null;
  const erpResponsible=(task.responsibleName&&task.responsibleName!=='Sin asignar')?task.responsibleName.trim():'';
  const authorEl=$('#report-author'),hintEl=$('#author-hint');
  if(erpResponsible){
    authorEl.value=erpResponsible;
    authorEl.readOnly=true;
    authorEl.title='Responsable asignado a la tarea en el ERP';
    if(hintEl)hintEl.textContent='(Asignado en ERP)';
  }else{
    authorEl.value=details?.author||profile.author||'';
    authorEl.readOnly=false;
    authorEl.title='';
    if(hintEl)hintEl.textContent='(Manual)';
  }
  $('#work-quantity').value=details?.quantity??'';$('#work-unit').value=details?.unit||'ha';
  $('#work-stopped').checked=Boolean(details?.stoppage);
  document.querySelectorAll('[name="stop-reason"]').forEach(el=>el.checked=el.value===details?.stoppage?.reason);
  $('#stop-other').value=details?.stoppage?.description||'';state.beforeStop=null;updateStoppage();
  state.draftId=crypto.randomUUID();state.photos=[];state.photoBusy=false;
  $('#report-photos').value='';$('#report-photos').disabled=false;$('#report-form button[type=submit]').disabled=false;$('#photo-status').textContent='';renderPhotoPreviews();
  $('#machinery-rows').innerHTML='';for(const machine of details?.machinery||[])addMachine(machine);
  $('#report-dialog').showModal();
}
$('#close-dialog').onclick=()=>$('#report-dialog').close();
$('#discard-report')?.addEventListener('click',()=>$('#report-dialog').close());
$('#report-form').onsubmit=async event=>{
  event.preventDefault();const button=$('#report-form button[type=submit]');button.disabled=true;
  try{
    const progress=Math.round(Number($('#progress-value').value)*100), notes=$('#notes').value.trim();
    if(!notes)throw new Error('Describe el trabajo realizado.');
    if(!Number.isInteger(progress)||progress<state.currentTask.progressBps||progress>10000)throw new Error('El avance debe estar entre el valor actual y 100 %.');
    // Confirmed captures retain their original payload and photo bytes.
    if(state.photoBusy)throw new Error('Espera a que terminen de prepararse las fotos.');
    const id=state.draftId;
    const details=captureDetails();
    const report={id,photos:structuredClone(state.photos),user:state.user,state:'pending',created:new Date().toISOString(),payload:{id,taskId:state.currentTask.id,progressBps:progress,baseProgressBps:state.currentTask.progressBps,operationDate:$('#operation-date').value,notes,crew:structuredClone(state.crew),details,photos:state.photos.map(p=>p.id)}};
    if(!confirm('¿Confirmar este reporte? Después no podrás modificar sus datos ni fotos. Cualquier corrección se registrará como una aclaración separada.'))return;
    if(await dbGet('queue',id))throw new Error('Este reporte ya fue confirmado. Cierra el formulario.');
    await dbWrite('meta',{author:details.author,title:details.title},`author:${state.user}`);
    await dbWrite('queue',report);await reloadLocal();$('#report-dialog').close();toast('Reporte guardado en este dispositivo.');render();if(online())await sync();
  }catch(error){$('#form-error').textContent=error.message||'No se pudo guardar. Revisa el almacenamiento del dispositivo.';}finally{button.disabled=false;}
};
async function refresh(){return window.campoSync.refresh({state,api});}
async function sync(){return window.campoSync.sync({state,api,online,banner,updateChrome,reloadLocal,render});}
async function login(body){return window.campoAuth.login({body,state,api,storage:window.campoStorage,reloadLocal,showApp,sync});}
$('#username').hidden=true;$('#username').required=false;document.querySelector('label[for="username"]')?.setAttribute('hidden','');$('#login-form').onsubmit=async event=>{event.preventDefault();const button=$('#login-form button[type=submit]');button.disabled=true;$('#login-error').textContent='';try{await login({user:'',password:$('#password').value});$('#password').value='';}catch(error){$('#login-error').textContent=error.message;}finally{button.disabled=false;}};
async function logout(){return window.campoAuth.logout({state,api,storage:window.campoStorage,showLogin,toast});}
function exportPending(){const blob=new Blob([JSON.stringify({exportedAt:new Date().toISOString(),user:state.user,reports:state.local},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`campo-pendientes-${today()}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}
$('#logout').onclick=logout;$('#sync').onclick=()=>sync();
document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>{state.view=el.dataset.view;render();});
window.addEventListener('offline',()=>{state.reachable=false;updateChrome();banner('Sin conexión. Puedes capturar avances; se guardarán en este dispositivo.');});
window.addEventListener('online',()=>{state.reachable=true;if(state.user)sync();});
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();state.install=event;$('#install').hidden=false;});
$('#install').onclick=async()=>{if(state.install){await state.install.prompt();state.install=null;$('#install').hidden=true;}};
// Poll delivery receipts while online; never sends new operational reports from a timer.
setInterval(async()=>{if(!state.user||!online()||state.syncing||$('#app').hidden||document.hidden)return;try{const data=await api('/api/reports');if(JSON.stringify(data.reports)!==JSON.stringify(state.reports)){state.reports=data.reports;state.topics=data.topics;await dbWrite('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);if(['reports','telegram'].includes(state.view))render();}}catch(error){if(error.status===401)banner(error.message,true);}},5000);
async function setupTelegram(){return window.campoAuth.setupTelegram({showLogin,login,$});}
async function boot(){return window.campoAuth.boot({state,storage:window.campoStorage,showLogin,showApp,reloadLocal,sync,setupTelegram,banner,$});}
boot();


const crewRoles = {operator:'Operadores',technician:'Técnicos',assistant:'Auxiliares'};
function crewSummary(crew){return crew?.length?`<div class="crew-summary"><strong>Personal en campo · ${crew.length} personas</strong>${Object.entries(crewRoles).map(([role,label])=>{const names=crew.filter(e=>e.role===role).map(e=>esc(e.name));return names.length?`<div>${label}: ${names.join(', ')}</div>`:'';}).join('')}</div>`:'';}
async function refreshEmployees(){
  const result=await api('/api/employees');state.catalog.employees=result.employees;
  await dbWrite('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);
}
function renderEmployees(){
  $('#main').innerHTML=heading('Empleados','Registra tu cuadrilla y asigna los roles que puede desempeñar.', '<button id="new-employee" class="btn primary"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>Nuevo empleado</button>')+`
    <p class="muted">La gestión requiere conexión. El catálogo descargado permite seleccionar personal al reportar sin señal.</p>
    <div class="view-tools"><input id="employee-search" type="search" placeholder="Buscar por nombre…" aria-label="Buscar empleados" value="${esc(state.employeeSearch||'')}"><button id="refresh-employees" class="btn small">Actualizar catálogo</button></div><div id="employee-list"></div>`;
  $('#employee-search').oninput=e=>{state.employeeSearch=e.target.value;renderEmployeeList();};
  $('#new-employee').onclick=()=>openEmployee();
  $('#refresh-employees').onclick=async()=>{try{await refreshEmployees();renderEmployeeList();toast('Catálogo actualizado.');}catch(error){toast(error.message);}};
  renderEmployeeList();
}
function renderEmployeeList(){
  const all=state.catalog.employees||[],items=all.filter(e=>e.name.toLocaleLowerCase('es').includes((state.employeeSearch||'').toLocaleLowerCase('es')));
  $('#employee-list').innerHTML=items.length?`
    <div class="table-wrap">
      <table class="employee-table">
        <thead>
          <tr>
            <th class="person-column">EMPLEADO</th>
            <th>ROLES HABILITADOS</th>
            <th class="status-column">ESTADO</th>
            <th style="text-align:right"><span class="muted">ACCIONES</span></th>
          </tr>
        </thead>
        <tbody>
          ${items.map(e=>`
            <tr>
              <td class="person-column">
                <span class="person">
                  <span class="person-circle">${esc(e.name.split(' ').map(s=>s[0]).slice(0,2).join(''))}</span>
                  <strong>${esc(e.name)}</strong>
                </span>
              </td>
              <td>
                <div class="role-tags">
                  ${e.roles.map(r=>`<span class="chip role-chip role-${esc(r)}">${esc(crewRoles[r]||r)}</span>`).join('')}
                </div>
              </td>
              <td class="status-column"><span class="status green">Habilitado</span></td>
              <td class="table-action" style="text-align:right">
                <div class="action-btn-group">
                  <button class="btn small subtle" data-edit-employee="${esc(e.id)}" title="Editar empleado">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>Editar
                  </button>
                  <button class="btn small danger" data-delete-employee="${esc(e.id)}" title="Eliminar empleado">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>Eliminar
                  </button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <div class="table-caption">${items.length} empleado(s) registrado(s) en tu cuadrilla de campo.</div>
  `:`<div class="empty"><h3>${all.length?'No hay coincidencias':'Aún no hay empleados'}</h3><p>${all.length?'Prueba otro nombre.':'Pulsa Nuevo empleado para registrar a la primera persona de tu cuadrilla.'}</p></div>`;
  document.querySelectorAll('[data-edit-employee]').forEach(el=>el.onclick=()=>openEmployee(all.find(e=>e.id===el.dataset.editEmployee)));
  document.querySelectorAll('[data-delete-employee]').forEach(el=>el.onclick=()=>{state.deletingEmployee=all.find(e=>e.id===el.dataset.deleteEmployee);$('#delete-employee-description').textContent=`¿Eliminar a ${state.deletingEmployee.name} del catálogo?`;$('#delete-employee-error').textContent='';$('#delete-employee-dialog').showModal();});
}
function openEmployee(employee=null){
  if(!online()){toast('Conecta a internet para gestionar empleados.');return;}
  state.editingEmployee=employee;$('#employee-heading').textContent=employee?'Editar empleado':'Nuevo empleado';$('#employee-name').value=employee?.name||'';$('#employee-error').textContent='';
  document.querySelectorAll('[name="employee-role"]').forEach(el=>el.checked=employee?.roles.includes(el.value)||false);$('#employee-dialog').showModal();
}
$('#close-employee').onclick=()=>$('#employee-dialog').close();
$('#employee-form').onsubmit=async event=>{
  event.preventDefault();const button=$('#employee-form button[type=submit]');button.disabled=true;
  try{
    const roles=[...document.querySelectorAll('[name="employee-role"]:checked')].map(el=>el.value),name=$('#employee-name').value.trim();
    if(!name||!roles.length)throw new Error('Escribe el nombre y selecciona al menos un rol.');
    const saved=await api('/api/employees/save',{...(state.editingEmployee||{}),name,roles});
    state.catalog.employees=[...(state.catalog.employees||[]).filter(e=>e.id!==saved.id),saved];
    $('#employee-dialog').close();renderEmployeeList();toast('Empleado guardado.');
    await refreshEmployees();renderEmployeeList();
  }catch(error){if($('#employee-dialog').open)$('#employee-error').textContent=error.message;else toast(error.message);}finally{button.disabled=false;}
};
$('#cancel-delete-employee').onclick=()=>$('#delete-employee-dialog').close();
$('#confirm-delete-employee').onclick=async()=>{
  const button=$('#confirm-delete-employee');button.disabled=true;
  try{await api('/api/employees/delete',{id:state.deletingEmployee.id,version:state.deletingEmployee.version});state.catalog.employees=(state.catalog.employees||[]).filter(e=>e.id!==state.deletingEmployee.id);$('#delete-employee-dialog').close();renderEmployeeList();toast('Empleado eliminado del catálogo.');await refreshEmployees();renderEmployeeList();}catch(error){if($('#delete-employee-dialog').open)$('#delete-employee-error').textContent=error.message;else toast(error.message);}finally{button.disabled=false;}
};
function renderCrew(){
  const container = $('#crew-picker');
  if (!container) return;
  const allEmployees = state.catalog.employees || [];
  state.crewSearch = typeof state.crewSearch === 'string' ? state.crewSearch : '';
  state.crewFilter = state.crewFilter || 'all';

  container.innerHTML = `
    <div class="crew-section-header">
      <div class="section-heading">
        <h3>
          <svg class="section-title-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
          </svg>
          Personal en campo (Cuadrilla)
        </h3>
        <span class="crew-count-chip" id="crew-count-chip">${state.crew.length} asignado(s)</span>
      </div>
      <p class="muted">Selecciona a los integrantes de la cuadrilla mediante la lista desplegable y asigna su rol de hoy.</p>
    </div>

    ${!allEmployees.length ? '<p class="error">No hay empleados registrados en el catálogo. Regístralos en la sección Empleados.</p>' : ''}

    <div class="crew-droplist-container" id="crew-droplist-container">
      <!-- Droplist Input Trigger -->
      <div class="crew-droplist-trigger" id="crew-droplist-trigger" tabindex="0" role="combobox" aria-expanded="false" aria-haspopup="listbox">
        <div class="crew-droplist-trigger-content">
          <span class="crew-droplist-trigger-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </span>
          <span class="crew-droplist-trigger-text" id="crew-droplist-trigger-text">Seleccionar personal de cuadrilla...</span>
        </div>
        <span class="crew-droplist-trigger-chevron">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </span>
      </div>

      <!-- Droplist Dropdown Panel -->
      <div class="crew-droplist-dropdown" id="crew-droplist-dropdown" hidden>
        <div class="crew-droplist-header">
          <div class="crew-droplist-search-bar">
            <span class="crew-droplist-search-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </span>
            <input type="search" id="crew-droplist-search-input" placeholder="Buscar por nombre..." autocomplete="off">
          </div>

          <div class="crew-droplist-filters">
            <button type="button" class="crew-filter-tab active" data-crew-filter="all">Todos</button>
            <button type="button" class="crew-filter-tab" data-crew-filter="operator">Operadores</button>
            <button type="button" class="crew-filter-tab" data-crew-filter="technician">Técnicos</button>
            <button type="button" class="crew-filter-tab" data-crew-filter="assistant">Auxiliares</button>
          </div>
        </div>

        <div class="crew-droplist-list" id="crew-droplist-list" role="listbox"></div>

        <div class="crew-droplist-footer">
          <span class="crew-droplist-footer-summary" id="crew-droplist-footer-summary">${state.crew.length} seleccionado(s)</span>
          <div class="crew-droplist-footer-btns">
            <button type="button" class="btn small subtle" id="crew-droplist-clear-btn">Limpiar</button>
            <button type="button" class="btn small primary" id="crew-droplist-done-btn">Listo</button>
          </div>
        </div>
      </div>

      <!-- Selected Employees Chips (Below Dropdown) -->
      <div class="crew-selected-tray" id="crew-selected-tray"></div>
    </div>
  `;

  attachCrewDroplistEvents();
  renderCrewDroplistItems();
  updateCrewDroplistStatus();
}

function attachCrewDroplistEvents() {
  const trigger = $('#crew-droplist-trigger');
  const dropdown = $('#crew-droplist-dropdown');
  const searchInput = $('#crew-droplist-search-input');
  const clearBtn = $('#crew-droplist-clear-btn');
  const doneBtn = $('#crew-droplist-done-btn');

  if (!trigger || !dropdown) return;

  const toggleDropdown = (open) => {
    const shouldOpen = open !== undefined ? open : dropdown.hidden;
    dropdown.hidden = !shouldOpen;
    trigger.classList.toggle('active', shouldOpen);
    trigger.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    if (shouldOpen && searchInput) {
      setTimeout(() => searchInput.focus(), 50);
    }
  };

  trigger.onclick = (e) => {
    e.stopPropagation();
    toggleDropdown();
  };

  trigger.onkeydown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleDropdown();
    } else if (e.key === 'Escape') {
      toggleDropdown(false);
    }
  };

  if (searchInput) {
    searchInput.oninput = (e) => {
      state.crewSearch = e.target.value;
      renderCrewDroplistItems();
    };
    searchInput.onclick = (e) => e.stopPropagation();
  }

  document.querySelectorAll('.crew-filter-tab').forEach(tab => {
    tab.onclick = (e) => {
      e.stopPropagation();
      state.crewFilter = tab.dataset.crewFilter;
      document.querySelectorAll('.crew-filter-tab').forEach(t => t.classList.toggle('active', t === tab));
      renderCrewDroplistItems();
    };
  });

  if (clearBtn) {
    clearBtn.onclick = (e) => {
      e.stopPropagation();
      state.crew = [];
      updateCrewDroplistStatus();
      renderCrewDroplistItems();
    };
  }

  if (doneBtn) {
    doneBtn.onclick = (e) => {
      e.stopPropagation();
      toggleDropdown(false);
    };
  }

  dropdown.onclick = (e) => e.stopPropagation();
}

function renderCrewDroplistItems() {
  const listContainer = $('#crew-droplist-list');
  if (!listContainer) return;

  const allEmployees = state.catalog.employees || [];
  const search = (typeof state.crewSearch === 'string' ? state.crewSearch : '').trim().toLocaleLowerCase('es');
  const roleFilter = state.crewFilter || 'all';

  const filtered = allEmployees.filter(emp => {
    const matchesSearch = !search || emp.name.toLocaleLowerCase('es').includes(search);
    const matchesRole = roleFilter === 'all' || emp.roles.includes(roleFilter);
    return matchesSearch && matchesRole;
  });

  if (!filtered.length) {
    listContainer.innerHTML = `<div class="crew-droplist-empty">${search ? 'No se encontraron empleados con ese nombre.' : 'No hay empleados en esta categoría.'}</div>`;
    return;
  }

  listContainer.innerHTML = filtered.map(emp => {
    const assigned = state.crew.find(c => c.id === emp.id);
    const isSelected = Boolean(assigned);
    const primaryRole = emp.roles[0] || 'operator';
    const initials = emp.name.split(' ').map(s => s[0]).slice(0, 2).join('');

    return `
      <label class="crew-check-item ${isSelected ? 'is-selected' : ''}" data-item-id="${esc(emp.id)}">
        <input type="checkbox" class="crew-check-input" data-emp-id="${esc(emp.id)}" ${isSelected ? 'checked' : ''}>
        <span class="crew-item-avatar">${esc(initials)}</span>
        <div class="crew-item-details">
          <span class="crew-item-name">${esc(emp.name)}</span>
          <span class="crew-item-sub">${emp.roles.map(r => crewRoles[r] || r).join(', ')}</span>
        </div>
        <span class="crew-item-badge role-${esc(primaryRole)}">${esc(crewRoles[primaryRole] || primaryRole)}</span>
      </label>
    `;
  }).join('');

  listContainer.querySelectorAll('.crew-check-input').forEach(chk => {
    chk.onchange = (e) => {
      e.stopPropagation();
      const empId = chk.dataset.empId;
      const emp = allEmployees.find(emp => emp.id === empId);
      if (!emp) return;

      if (chk.checked) {
        if (state.crew.length >= 30) {
          toast('Puedes seleccionar hasta 30 personas por reporte.');
          chk.checked = false;
          return;
        }
        const chosenRole = emp.roles[0] || 'operator';
        state.crew = state.crew.filter(c => c.id !== empId);
        state.crew.push({ id: emp.id, version: emp.version, name: emp.name, role: chosenRole });
      } else {
        state.crew = state.crew.filter(c => c.id !== empId);
      }
      updateCrewDroplistStatus();
      renderCrewDroplistItems();
    };
  });
}

function updateCrewDroplistStatus() {
  const countChip = $('#crew-count-chip');
  if (countChip) countChip.textContent = `${state.crew.length} asignado(s)`;

  const footerSummary = $('#crew-droplist-footer-summary');
  if (footerSummary) footerSummary.textContent = `${state.crew.length} seleccionado(s)`;

  const triggerText = $('#crew-droplist-trigger-text');
  if (triggerText) {
    if (!state.crew.length) {
      triggerText.textContent = 'Seleccionar personal de cuadrilla...';
      triggerText.classList.remove('has-selection');
    } else if (state.crew.length === 1) {
      const c = state.crew[0];
      triggerText.textContent = `${c.name} (${crewRoles[c.role] || c.role})`;
      triggerText.classList.add('has-selection');
    } else {
      const opCount = state.crew.filter(c => c.role === 'operator').length;
      const techCount = state.crew.filter(c => c.role === 'technician').length;
      const auxCount = state.crew.filter(c => c.role === 'assistant').length;
      const parts = [];
      if (opCount) parts.push(`${opCount} op.`);
      if (techCount) parts.push(`${techCount} téc.`);
      if (auxCount) parts.push(`${auxCount} aux.`);
      triggerText.textContent = `${state.crew.length} seleccionados (${parts.join(', ')})`;
      triggerText.classList.add('has-selection');
    }
  }

  const tray = $('#crew-selected-tray');
  if (tray) {
    if (!state.crew.length) {
      tray.innerHTML = '';
    } else {
      tray.innerHTML = state.crew.map(c => {
        const initials = c.name.split(' ').map(s => s[0]).slice(0, 2).join('');
        return `
          <div class="crew-selected-pill">
            <span class="crew-pill-avatar">${esc(initials)}</span>
            <span class="crew-pill-name">${esc(c.name)}</span>
            <span class="crew-pill-role role-${esc(c.role)}">${esc(crewRoles[c.role] || c.role)}</span>
            <button type="button" class="crew-pill-remove" data-remove-crew-id="${esc(c.id)}" title="Quitar de la cuadrilla" aria-label="Quitar ${esc(c.name)}">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        `;
      }).join('');

      tray.querySelectorAll('[data-remove-crew-id]').forEach(btn => {
        btn.onclick = (e) => {
          e.stopPropagation();
          state.crew = state.crew.filter(c => c.id !== btn.dataset.removeCrewId);
          updateCrewDroplistStatus();
          renderCrewDroplistItems();
        };
      });
    }
  }
}

// Global click handler to close droplist dropdown when clicking outside
document.addEventListener('click', (e) => {
  const container = $('#crew-droplist-container');
  const dropdown = $('#crew-droplist-dropdown');
  const trigger = $('#crew-droplist-trigger');
  if (container && dropdown && !dropdown.hidden && !container.contains(e.target)) {
    dropdown.hidden = true;
    trigger?.classList.remove('active');
    trigger?.setAttribute('aria-expanded', 'false');
  }
});


function addMachine(machine={}){
  if(document.querySelectorAll('.machine-row').length>=5){toast('Puedes registrar hasta cinco máquinas.');return;}
  const row=document.createElement('div');row.className='machine-row';const id=crypto.randomUUID();
  row.innerHTML=`<div><label for="machine-${id}">Máquina</label><input id="machine-${id}" data-machine="name" maxlength="80" required placeholder="Nombre o identificación" value="${esc(machine.name||'')}"></div><div><label for="hours-${id}">Horas</label><input id="hours-${id}" data-machine="hours" type="number" min="0" max="24" step="0.01" required value="${esc(machine.hours??'')}"></div><div><label for="liters-${id}">Combustible (L)</label><input id="liters-${id}" data-machine="liters" type="number" min="0" max="100000" step="0.01" required value="${esc(machine.liters??'')}"></div><button type="button" class="icon-btn" aria-label="Quitar máquina"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>`;
  row.querySelector('button').onclick=()=>row.remove();$('#machinery-rows').append(row);
}
$('#add-machine').onclick=()=>addMachine();
function captureDetails(){
  const author=$('#report-author').value.trim();
  if(!author)throw new Error('Escribe el nombre del responsable.');
  const title=($('#report-title')?.value||'').trim();
  const previous=null;
  const stopped=$('#work-stopped').checked,reason=document.querySelector('[name="stop-reason"]:checked')?.value;
  if(stopped&&!reason)throw new Error('Selecciona el motivo del paro.');
  if(stopped&&reason==='Otro'&&!$('#stop-other').value.trim())throw new Error('Describe el motivo del paro.');
  return {...(stopped?{stoppage:{reason,description:reason==='Otro'?$('#stop-other').value.trim():''}}:{}),author,title,quantity:Number($('#work-quantity').value),unit:$('#work-unit').value,
    capturedAt:previous?.capturedAt||new Date().toISOString(),timezoneOffset:previous?.timezoneOffset??new Date().getTimezoneOffset(),offline:previous?.offline??(!online()||!state.reachable),
    machinery:[...document.querySelectorAll('.machine-row')].map(row=>({name:row.querySelector('[data-machine="name"]').value.trim(),hours:Number(row.querySelector('[data-machine="hours"]').value),liters:Number(row.querySelector('[data-machine="liters"]').value)}))};
}
function fileData(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('No se pudo leer la foto.'));reader.readAsDataURL(file);});}
async function preparePhoto(file){
  if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>20000000)throw new Error('Usa fotos JPG, PNG o WebP de hasta 20 MB.');
  const source=await fileData(file),picture=new Image();picture.src=source;
  try{await picture.decode();}catch{throw new Error('No se pudo abrir una de las fotos. Usa JPG, PNG o WebP.');}
  if(!picture.width||!picture.height||Math.max(picture.width,picture.height)/Math.min(picture.width,picture.height)>20)throw new Error('La proporción de la foto no es compatible con Telegram.');
  const scale=Math.min(1,1600/Math.max(picture.width,picture.height)),canvas=document.createElement('canvas');
  canvas.width=Math.max(1,Math.round(picture.width*scale));canvas.height=Math.max(1,Math.round(picture.height*scale));
  const context=canvas.getContext('2d');context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(picture,0,0,canvas.width,canvas.height);
  let data=canvas.toDataURL('image/jpeg',0.82);
  if(data.length>1900000)data=canvas.toDataURL('image/jpeg',0.6);
  if(data.length>1900000)throw new Error('La foto sigue siendo demasiado grande. Elige una imagen más pequeña.');
  return {id:crypto.randomUUID(),data};
}
$('#report-photos').onchange=async event=>{
  const files=[...event.target.files];if(!files.length)return;
  if(state.photos.length+files.length>6){$('#photo-status').textContent='Puedes adjuntar hasta seis fotos. Quita alguna antes de añadir más.';event.target.value='';return;}
  const draft=state.draftId;state.photoBusy=true;event.target.disabled=true;$('#photo-status').textContent='Preparando fotografías…';$('#report-form button[type=submit]').disabled=true;
  try{const prepared=[];for(const file of files)prepared.push(await preparePhoto(file));if(draft===state.draftId){state.photos.push(...prepared);renderPhotoPreviews();$('#photo-status').textContent=`${state.photos.length} foto(s) listas. Guarda el reporte para conservarlas.`;}}
  catch(error){if(draft===state.draftId)$('#photo-status').textContent=error.message;}
  finally{if(draft===state.draftId){state.photoBusy=false;event.target.disabled=false;event.target.value='';$('#report-form button[type=submit]').disabled=false;}}
};
function renderPhotoPreviews(){
  const container = $('#photo-previews');
  const statusEl = $('#photo-status');
  const sub = $('#photo-dropzone-subtitle');
  if(!container) return;
  const photos = state.photos || [];

  if(!photos.length){
    container.innerHTML = '';
    if(statusEl) statusEl.innerHTML = '';
    if(sub) sub.textContent = 'Ninguna foto seleccionada (toca para adjuntar)';
    return;
  }

  if(statusEl){
    statusEl.innerHTML = `
      <div class="photo-status-bar">
        <span class="photo-status-chip">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          ${photos.length} de 6 evidencias listas
        </span>
        <span class="photo-status-hint">Toca una foto para ampliarla</span>
      </div>
    `;
  }

  container.innerHTML = photos.map((p, i) => `
    <div class="photo-preview-item" data-photo-id="${esc(p.id)}">
      <div class="photo-preview-thumb" data-zoom-photo="${esc(p.id)}" title="Toca para ampliar foto ${i + 1}">
        <img src="${esc(p.data)}" alt="Evidencia ${i + 1}" loading="lazy">
        <div class="photo-zoom-hint">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="11" y1="8" x2="11" y2="14"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </div>
      </div>
      <span class="photo-index-tag">Foto ${i + 1}</span>
      <button type="button" class="photo-delete-badge" data-remove-photo="${esc(p.id)}" aria-label="Quitar foto ${i + 1}" title="Quitar foto ${i + 1}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  `).join('');

  container.querySelectorAll('[data-remove-photo]').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      state.photos = state.photos.filter(p => p.id !== btn.dataset.removePhoto);
      renderPhotoPreviews();
    };
  });

  container.querySelectorAll('[data-zoom-photo]').forEach(thumb => {
    thumb.onclick = () => {
      const p = photos.find(p => p.id === thumb.dataset.zoomPhoto);
      if(p){
        $('#full-photo').src = p.data;
        $('#photo-dialog').showModal();
      }
    };
  });

  if(sub){
    sub.textContent = photos.length < 6
      ? `${photos.length} de 6 fotos seleccionadas (toca para cambiar o añadir)`
      : `Máximo de 6 fotos alcanzado`;
  }
}
function fieldSummary(payload){
  const d=payload.details;if(!d)return '';
  const captured=new Date(new Date(d.capturedAt).getTime()-d.timezoneOffset*60000).toISOString().replace('T',' ').slice(0,19);
  const crewStr = payload.crew?.length ? payload.crew.map(c => `${esc(c.name)} (${esc(crewRoles[c.role] || c.role)})`).join(', ') : 'Sin personal asignado';
  return `<div class="crew-summary">${d.stoppage?`<div class="stoppage-summary">Día sin actividad (Paro) · ${esc(d.stoppage.reason)}${d.stoppage.description?`: ${esc(d.stoppage.description)}`:''}</div>`:''}<div>Responsable: ${esc(d.author)}${d.title?` — ${esc(d.title)}`:''}</div><div>Captura: ${esc(captured)} · ${d.offline?'Sin Internet':'Con Internet'}</div><div>Avance de jornada: ${esc(d.quantity)} ${esc(d.unit)}</div><div>Cuadrilla: ${crewStr}</div><div>Maquinaria: ${d.machinery.length?d.machinery.map(m=>`${esc(m.name)}: ${esc(m.hours)} hrs (${esc(m.liters)} L)`).join(' · '):'Sin maquinaria'}</div><div>Evidencias fotográficas: ${payload.photos?.length||0}</div></div>`;
}
async function fillReportPhotos(reports){
  for(const report of reports){
    if(!report.payload.photos?.length)continue;
    const photos=report.photos||await dbGet('meta',`photos:${state.user}:${report.id}`)||[];
    const container=document.querySelector(`[data-report-photos="${report.id}"]`);if(!container)continue;
    container.innerHTML=report.payload.photos.map((id,i)=>{const saved=photos.find(p=>p.id===id);const url=saved?.data||`/api/photos/${encodeURIComponent(id)}`;return `<button type="button" class="photo-open" aria-label="Ampliar evidencia ${i+1}"><img src="${esc(url)}" alt="Evidencia ${i+1}" loading="lazy"></button>`;}).join('');
    container.querySelectorAll('.photo-open').forEach(button=>button.onclick=()=>{$('#full-photo').src=button.querySelector('img').src;$('#photo-dialog').showModal();});
  }
}

$('#close-photo').onclick=()=>{$('#photo-dialog').close();$('#full-photo').removeAttribute('src');};

function updateStoppage(){
  const stopped=$('#work-stopped').checked;
  $('#stop-reasons').hidden=!stopped;
  document.querySelectorAll('[name="stop-reason"]').forEach(el=>{el.required=stopped;el.disabled=!stopped;});
  const other=stopped&&document.querySelector('[name="stop-reason"]:checked')?.value==='Otro';
  $('#stop-other-wrap').hidden=!other;$('#stop-other').required=other;$('#stop-other').disabled=!other;
  if(stopped){
    if(!state.beforeStop)state.beforeStop={quantity:$('#work-quantity').value,progress:$('#progress-value').value};
    $('#work-quantity').value='0';$('#progress-value').value=state.currentTask.progressBps/100;
  }else if(state.beforeStop){$('#work-quantity').value=state.beforeStop.quantity;$('#progress-value').value=state.beforeStop.progress;state.beforeStop=null;}
  $('#work-quantity').readOnly=stopped;$('#progress-value').readOnly=stopped;
}
$('#work-stopped').onchange=updateStoppage;
document.querySelectorAll('[name="stop-reason"]').forEach(el=>el.onchange=updateStoppage);

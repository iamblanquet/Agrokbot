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
function showApp(){ $('#login').hidden=true;$('#app').hidden=false;$('#profile-user').textContent=state.user;$('#avatar').textContent=state.user.slice(0,1).toUpperCase();if(state.isAdmin&&!$('[data-view="admin"]')){const b=document.createElement('button');b.className='nav-item';b.dataset.view='admin';b.innerHTML='<span class="nav-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg></span><span class="nav-text-full">Administración</span><span class="nav-text-short">Ajustes</span>';b.onclick=()=>{state.view='admin';render();};document.querySelector('nav')?.append(b);}if(state.isAdmin&&!$('[data-view="monitor"]')){const m=document.createElement('button');m.className='nav-item';m.dataset.view='monitor';m.innerHTML='<span class="nav-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg></span><span>Monitoreo</span>';m.onclick=()=>{state.view='monitor';render();};document.querySelector('nav')?.append(m);}render(); }
function updateChrome(){
  if(!$('[data-view="incidents"]')){
    const button=document.createElement('button');button.className='nav-item';button.dataset.view='incidents';button.innerHTML='<span class="nav-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></span><span>Incidencias</span>';
    button.onclick=()=>{state.view='incidents';render();};document.querySelector('nav')?.append(button);
  }
  $('[data-view="incidents"]').hidden=!(state.isAdmin||state.canManageIncidents);
  updateNotificationNotice();
  refreshNotificationState();
  if(!$('[data-view="journal"]')){
    const button=document.createElement('button');button.className='nav-item';button.dataset.view='journal';button.innerHTML='<span class="nav-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg></span><span class="nav-text-full">Bitácora ERP</span><span class="nav-text-short">Bitácora</span>';
    button.onclick=()=>{state.view='journal';render();};document.querySelector('nav')?.append(button);
  }
  if($('[data-view="journal"]'))$('[data-view="journal"]').hidden=false;
  if($('[data-view="admin"]'))$('[data-view="admin"]').hidden=!state.isAdmin;
  if($('[data-view="monitor"]'))$('[data-view="monitor"]').hidden=!state.isAdmin;
  const connected=online()&&state.reachable;
  $('#network').className=`connection ${connected?'online':'offline'}`;
  $('#network').textContent=state.simulation?'Prueba sin señal':connected?'Con conexión':'Sin conexión';
  $('#pending-count').textContent=state.local.length;
  $('#sync').disabled=state.syncing || !online();
  $('#sync span').textContent=state.syncing?'Sincronizando…':'Sincronizar';
  const saved=state.catalog.offlineSavedAt;
  const savedDay=saved?new Date(saved).toLocaleDateString('en-CA',{timeZone:'America/Mexico_City'}):'';
  const currentDay=new Date().toLocaleDateString('en-CA',{timeZone:'America/Mexico_City'});
  $('#cache-note').textContent=saved?`${state.catalog.projects.length} proyectos guardados para uso sin conexión.${savedDay!==currentDay?' Datos de un día anterior: se actualizarán al conectar.':''}`:'Conecta para confirmar la descarga automática de tus datos.';
  $('#last-sync').textContent=saved?`DATOS GUARDADOS · ${prettyDate(saved)}`:'DESCARGA AÚN NO CONFIRMADA';
  document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===state.view));
  $('#breadcrumb-current').textContent=({projects:'Proyectos',employees:'Empleados',reports:'Mis reportes',telegram:'Temas de Telegram',settings:'Notificaciones',admin:'Administración',monitor:'Monitoreo',incidents:'Incidencias',journal:'Bitácora ERP'})[state.view];
}
function statusInfo(value){return ({pending:['Pendiente de sincronizar','amber'],conflict:['No registrado: conflicto','amber'],invalid:['No registrado: datos rechazados','red'],erp_sending:['Registrando en ERP','blue'],erp_review:['Verificar en ERP','red'],erp_rejected:['Rechazado por ERP','red'],telegram_pending:['ERP guardado · envío pendiente','blue'],telegram_sending:['Enviando a Telegram','blue'],telegram_failed:['ERP guardado · envío fallido','amber'],telegram_review:['ERP guardado · verificar envío','amber'],published:['Publicado en Telegram','green'],demo_published:['Publicado · simulación','green']})[value] || [value,''];}
function badge(value){const [label,color]=({photos_pending:['ERP guardado · fotos pendientes','blue'],photos_review:['ERP guardado · verificar fotos','amber'],evidence_review:['Publicado · evidencias ERP por conciliar','amber']})[value]||statusInfo(value);return `<span class="status ${color}">${esc(label)}</span>`;}
function taskStatus(task){return task.progressBps===10000?'<span class="status green">Finalizada</span>':task.progressBps>0?'<span class="status amber">En progreso</span>':'<span class="status">Sin iniciar</span>';}
function heading(title,subtitle,action=''){return `<div class="page-heading"><div><p class="eyebrow">SEGUIMIENTO OPERATIVO</p><h1>${title}</h1><p>${subtitle}</p></div>${action||`<span class="date-label">${new Date().toLocaleDateString('es-MX',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</span>`}</div>`;}
window.campoUi={ $, esc, heading, api, toast };
function taskById(id){return state.catalog.tasks.find(t=>t.id===id);}
function projectById(id){return state.catalog.projects.find(p=>p.id===id);}
function render(){updateChrome();if(state.view==='incidents'){$('#breadcrumb-current').textContent='Incidencias';if(!(state.isAdmin||state.canManageIncidents)){$('#main').textContent='No tienes permiso para gestionar incidencias.';return;}if($('#incident-list'))return;return window.campoIncidents.render();}if(state.view==='journal'){$('#breadcrumb-current').textContent='Bitácora ERP';if($('#journal'))return;return window.campoJournal.render();}({projects:renderProjects,employees:renderEmployees,reports:renderReports,telegram:renderTelegram,settings:renderSettings,admin:()=>window.campoAdmin?.render?.(),monitor:()=>window.campoMonitor?.render?.()})[state.view]();}
function renderProjects(){
  const projects=state.catalog.projects,tasks=state.catalog.tasks;
  if(!state.selected||!projectById(state.selected))state.selected=projects[0]?.id;

  const projectCardsHtml=projects.map(p=>{
    const pt=tasks.filter(t=>t.projectId===p.id);
    const avg=pt.length?Math.round(pt.reduce((a,t)=>a+t.progressBps,0)/pt.length):0;
    const loc=p.operationLocationName?`${esc(p.operationLocationName)} · `:'' ;
    const line=esc(p.businessLine?.name||p.company?.name||'Operaciones');
    return `<button class="project-card ${state.selected===p.id?'selected':''}" data-project="${esc(p.id)}" aria-pressed="${state.selected===p.id}">
      <div class="project-meta">
        <span class="project-code">${esc(p.folio||p.code)}</span>
        <span class="chip">${pt.length&&pt.every(t=>t.progressBps===10000)?'Completado':'En seguimiento'}</span>
      </div>
      <h3>${esc(p.name)}</h3>
      <p class="subline">${loc}${line} · ${pt.length} tareas</p>
      <div class="progress-label"><span>Promedio simple de tareas</span><strong>${pct(avg)}</strong></div>
      <progress max="10000" value="${avg}" aria-label="Avance medio"></progress>
      <div class="project-foot">
        <span>${pt.filter(t=>t.progressBps===10000).length} de ${pt.length} tareas completas</span>
        <span class="selected-label">${state.selected===p.id?'Seleccionado':'Ver tareas <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>'}</span>
      </div>
    </button>`;
  }).join('');

  const sliderHtml=`
    <div class="section-heading project-section-heading">
      <div class="project-heading-info">
        <h2>Mis proyectos</h2>
        <span class="project-count-badge">${projects.length} ${projects.length===1?'proyecto':'proyectos'}</span>
      </div>
      <div class="project-slider-nav-wrap">
        ${projects.length>1?`
        <div class="slider-arrow-controls" aria-label="Navegación de proyectos">
          <button class="slider-nav-btn prev" data-slider-action="prev" aria-label="Proyecto anterior" title="Proyecto anterior">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
          </button>
          <span class="slider-counter" id="proj-slider-counter">1 / ${projects.length}</span>
          <button class="slider-nav-btn next" data-slider-action="next" aria-label="Siguiente proyecto" title="Siguiente proyecto">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        </div>`:''}
        <span class="catalog-badge">${state.config.erpMode==='demo'?'Datos de demostración':'Catálogo del ERP'}</span>
      </div>
    </div>
    <div class="project-slider-wrapper">
      ${projects.length>1?`
      <button class="project-floating-arrow prev" data-slider-action="prev" aria-label="Proyecto anterior" title="Proyecto anterior">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
      </button>`:''}
      <section class="project-slider-track" id="project-slider-track" tabindex="0" role="region" aria-label="Carrusel de proyectos">
        ${projectCardsHtml}
      </section>
      ${projects.length>1?`
      <button class="project-floating-arrow next" data-slider-action="next" aria-label="Siguiente proyecto" title="Siguiente proyecto">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
      </button>`:''}
    </div>
    ${projects.length>1?`
    <div class="project-slider-dots" id="project-slider-dots" role="tablist" aria-label="Indicadores de proyectos">
      ${projects.map((p,i)=>`
        <button class="slider-dot ${state.selected===p.id?'active':(i===0&&!state.selected?'active':'')}" data-slide-index="${i}" aria-label="Ir a proyecto ${i+1}: ${esc(p.name)}" title="${esc(p.name)}"></button>
      `).join('')}
    </div>`:''}
  `;

  $('#main').innerHTML=heading('Cada avance cuenta.','Consulta tus proyectos y registra el trabajo de hoy.')+`
    <section class="stats" aria-label="Resumen"><div class="stat"><span class="stat-label">Proyectos disponibles</span><strong>${projects.length.toString().padStart(2,'0')}</strong><small>en tu espacio</small></div><div class="stat"><span class="stat-label">Tareas por completar</span><strong>${tasks.filter(t=>t.progressBps<10000).length.toString().padStart(2,'0')}</strong><small>en seguimiento</small></div><div class="stat"><span class="stat-label">Reportes en este dispositivo</span><strong class="${state.local.length?'amber':''}">${state.local.length.toString().padStart(2,'0')}</strong><small>por sincronizar</small></div></section>
    ${!projects.length?'<div class="empty"><h3>Aún no hay proyectos descargados</h3><p>Conecta al servidor y pulsa Sincronizar.</p></div>':sliderHtml+`<section class="task-panel"><div class="task-panel-head"><div><h2>Tareas del proyecto</h2><p>${esc(projectById(state.selected)?.name)}</p></div><div class="filters"><input id="task-search" type="search" placeholder="Buscar tarea…" aria-label="Buscar tarea" value="${esc(state.search)}"><select id="task-filter" aria-label="Filtrar estado"><option value="all">Todos los estados</option><option value="active">Por completar</option><option value="done">Finalizadas</option></select></div></div><div id="task-table"></div></section>`}`;

  if(projects.length){
    initProjectSlider();
  }

  if($('#task-filter')){$('#task-filter').value=state.taskFilter;$('#task-filter').onchange=e=>{state.taskFilter=e.target.value;state.taskPage=1;renderTaskTable();};$('#task-search').oninput=e=>{state.search=e.target.value;state.taskPage=1;renderTaskTable();};renderTaskTable();}
}

function initProjectSlider(){
  const track=$('#project-slider-track');
  if(!track)return;
  const cards=Array.from(track.querySelectorAll('.project-card'));
  if(!cards.length)return;

  function getCardStep(){
    if(cards.length>1){
      const step=cards[1].offsetLeft-cards[0].offsetLeft;
      if(step>0)return step;
    }
    return cards[0].offsetWidth+14;
  }

  function updateSliderUi(){
    const scrollLeft=track.scrollLeft;
    const maxScroll=Math.max(0,track.scrollWidth-track.clientWidth);
    const isAtStart=scrollLeft<=4;
    const isAtEnd=scrollLeft>=maxScroll-6||maxScroll<=2;

    const step=getCardStep()||1;
    const activeIdx=Math.min(cards.length-1,Math.max(0,Math.round(scrollLeft/step)));

    document.querySelectorAll('#project-slider-dots .slider-dot').forEach((dot,i)=>{
      dot.classList.toggle('active',i===activeIdx);
    });

    const counter=$('#proj-slider-counter');
    if(counter){
      const isDesktop=track.clientWidth>=768;
      if(isDesktop&&cards.length>=2){
        const endIdx=Math.min(cards.length,activeIdx+2);
        counter.textContent=`${activeIdx+1}–${endIdx} / ${cards.length}`;
      }else{
        counter.textContent=`${activeIdx+1} / ${cards.length}`;
      }
    }

    document.querySelectorAll('[data-slider-action="prev"]').forEach(btn=>{
      btn.disabled=isAtStart;
    });
    document.querySelectorAll('[data-slider-action="next"]').forEach(btn=>{
      btn.disabled=isAtEnd;
    });
  }

  function slide(direction){
    const step=getCardStep();
    track.scrollBy({left:direction*step,behavior:'smooth'});
  }

  document.querySelectorAll('[data-slider-action]').forEach(btn=>{
    btn.onclick=(e)=>{
      e.preventDefault();
      e.stopPropagation();
      slide(btn.dataset.sliderAction==='next'?1:-1);
    };
  });

  document.querySelectorAll('#project-slider-dots .slider-dot').forEach(dot=>{
    dot.onclick=(e)=>{
      e.preventDefault();
      const idx=parseInt(dot.dataset.slideIndex,10);
      const targetCard=cards[idx];
      if(targetCard){
        track.scrollTo({left:targetCard.offsetLeft-track.offsetLeft,behavior:'smooth'});
      }
    };
  });

  cards.forEach(card=>{
    card.onclick=()=>{
      const projId=card.dataset.project;
      if(state.selected===projId)return;
      state.selected=projId;
      state.search='';
      state.taskPage=1;
      cards.forEach(c=>{
        const isSel=c.dataset.project===state.selected;
        c.classList.toggle('selected',isSel);
        c.setAttribute('aria-pressed',isSel?'true':'false');
        const label=c.querySelector('.selected-label');
        if(label){
          label.innerHTML=isSel?'Seleccionado':'Ver tareas <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
        }
      });
      const titleEl=document.querySelector('.task-panel-head p');
      if(titleEl)titleEl.textContent=projectById(state.selected)?.name||'';
      const searchInput=$('#task-search');
      if(searchInput)searchInput.value='';
      renderTaskTable();
    };
  });

  let ticking=false;
  track.onscroll=()=>{
    if(!ticking){
      window.requestAnimationFrame(()=>{
        updateSliderUi();
        ticking=false;
      });
      ticking=true;
    }
  };

  track.onkeydown=(e)=>{
    if(e.key==='ArrowRight'){
      e.preventDefault();
      slide(1);
    }else if(e.key==='ArrowLeft'){
      e.preventDefault();
      slide(-1);
    }
  };

  window.addEventListener('resize',updateSliderUi,{passive:true});

  const selectedIndex=cards.findIndex(c=>c.dataset.project===state.selected);
  if(selectedIndex>0){
    const target=cards[selectedIndex];
    const targetLeft=target.offsetLeft-track.offsetLeft;
    if(targetLeft<track.scrollLeft||targetLeft>=track.scrollLeft+track.clientWidth-20){
      track.scrollTo({left:targetLeft,behavior:'instant'});
    }
  }

  updateSliderUi();
}
function renderTaskTable(){
  const tasks=state.catalog.tasks.filter(t=>t.projectId===state.selected&&(state.taskFilter==='all'||(state.taskFilter==='done'?t.progressBps===10000:t.progressBps<10000))&&`${t.name} ${t.code}`.toLowerCase().includes(state.search.toLowerCase()));
  const pageSize=10;
  const totalPages=Math.max(1,Math.ceil(tasks.length/pageSize));
  state.taskPage=Math.min(Math.max(1,state.taskPage||1),totalPages);
  const start=(state.taskPage-1)*pageSize;
  const pageTasks=tasks.slice(start,start+pageSize);
  $('#task-table').innerHTML=tasks.length?`<div class="table-wrap"><table><thead><tr><th>TAREA / ACTIVIDAD</th><th class="person-column">RESPONSABLE</th><th>AVANCE</th><th class="status-column">ESTADO</th><th><span class="muted">ACCIÓN</span></th></tr></thead><tbody>${pageTasks.map(t=>{const wp=t.workPackage?.name?`${esc(t.workPackage.name)} · `:'' ;const act=esc(t.activity?.name||'');return `<tr><td class="task-name"><strong>${esc(t.name)}</strong><small><span class="task-code">${esc(t.code)}</span> ${wp}${act}</small></td><td class="person-column"><span class="person"><span class="person-circle">${esc((t.responsibleName||'—').split(' ').map(s=>s[0]).slice(0,2).join(''))}</span>${esc(t.responsibleName||'Sin asignar')}</span></td><td class="task-progress"><span>${pct(t.progressBps)}</span><progress max="10000" value="${Number(t.progressBps)||0}" aria-label="Avance de ${esc(t.code)}"></progress></td><td class="status-column">${taskStatus(t)}</td><td class="task-action">${taskCompleted(t)?'<span class="muted">Finalizada</span>':`<button class="btn subtle" data-capture="${esc(t.id)}">Reportar</button>`}</td></tr>`;}).join('')}</tbody></table></div><div class="table-caption table-pagination-bar"><span>Mostrando ${start+1}–${Math.min(tasks.length,start+pageTasks.length)} de ${tasks.length} tareas · Página ${state.taskPage} de ${totalPages}</span><div class="pagination-btns"><button type="button" class="btn subtle small" id="task-page-prev" ${state.taskPage<=1?'disabled':''}>&lt; Anterior</button><button type="button" class="btn subtle small" id="task-page-next" ${state.taskPage>=totalPages?'disabled':''}>Siguiente &gt;</button></div></div>`:'<div class="empty"><h3>No hay tareas con este filtro</h3><p>Prueba otro estado o nombre.</p></div>';
  document.querySelectorAll('[data-capture]').forEach(el=>el.onclick=()=>openCapture(el.dataset.capture));
  if($('#task-page-prev'))$('#task-page-prev').onclick=()=>{if(state.taskPage>1){state.taskPage--;renderTaskTable();}};
  if($('#task-page-next'))$('#task-page-next').onclick=()=>{if(state.taskPage<totalPages){state.taskPage++;renderTaskTable();}};
}
function combinedReports(){const localIds=new Set(state.local.map(r=>r.id));return [...state.local,...state.reports.filter(r=>!localIds.has(r.id))].sort((a,b)=>b.created.localeCompare(a.created));}
function renderReports(){
  const items=combinedReports().filter(r=>state.reportFilter==='all'||(state.reportFilter==='pending'?['pending','conflict','invalid'].includes(r.state):['published','demo_published'].includes(r.state)));
  const pageSize=8;
  const totalPages=Math.max(1,Math.ceil(items.length/pageSize));
  state.reportPage=Math.min(Math.max(1,state.reportPage||1),totalPages);
  const start=(state.reportPage-1)*pageSize;
  const pageItems=items.slice(start,start+pageSize);
  $('#main').innerHTML=heading('Mis reportes','Del trabajo en campo al registro de tu equipo.')+`<div class="view-tools"><select id="report-filter" aria-label="Filtrar reportes"><option value="all">Todos los reportes</option><option value="pending">En este dispositivo</option><option value="published">Publicados</option></select><button id="export-reports" class="btn small">Exportar pendientes</button><span class="muted">${state.local.length} pendientes en este dispositivo</span></div><div class="report-list">${pageItems.map(r=>{const p=r.payload,t=taskById(p.taskId||r.task_id),project=projectById(t?.projectId||r.project_id);return `<article class="report-card"><div class="report-card-head"><div><h3>${esc(t?.code||'Tarea')} · ${esc(t?.name||p.taskId||r.task_id)}</h3><span class="muted">${esc(project?.name||'Proyecto')}</span></div>${badge(r.state)}</div><p>${esc(p.notes)}</p>${crewSummary(p.crew)}${fieldSummary(p)}<div class="photo-grid" data-report-photos="${esc(r.id)}"></div><div class="report-meta"><strong>Avance: ${pct(p.progressBps)}</strong><span>Operación: ${esc(p.operationDate)}</span><span>Capturado: ${prettyDate(r.created)}</span><span>Ref. ${esc(r.id.slice(0,8))}</span></div>${r.error?`<div class="report-error">${esc(r.error)}</div>`:''}<div class="report-actions">${r.state==='telegram_failed'?`<button class="btn small" data-retry="${esc(r.id)}">Reintentar envío</button>`:''}</div></article>`;}).join('')||'<div class="empty"><h3>Tu primer reporte empieza en una tarea</h3><p>Selecciona un proyecto y pulsa Reportar.</p></div>'}</div>${items.length?`<div class="table-caption table-pagination-bar"><span>Mostrando ${start+1}–${Math.min(items.length,start+pageItems.length)} de ${items.length} reporte(s) · Página ${state.reportPage} de ${totalPages}</span><div class="pagination-btns"><button type="button" class="btn subtle small" id="report-page-prev" ${state.reportPage<=1?'disabled':''}>&lt; Anterior</button><button type="button" class="btn subtle small" id="report-page-next" ${state.reportPage>=totalPages?'disabled':''}>Siguiente &gt;</button></div></div>`:''}`;
  fillReportPhotos(pageItems);
  $('#report-filter').value=state.reportFilter;$('#report-filter').onchange=e=>{state.reportFilter=e.target.value;state.reportPage=1;renderReports();};
  $('#export-reports').onclick=exportPending;
  if($('#report-page-prev'))$('#report-page-prev').onclick=()=>{if(state.reportPage>1){state.reportPage--;renderReports();}};
  if($('#report-page-next'))$('#report-page-next').onclick=()=>{if(state.reportPage<totalPages){state.reportPage++;renderReports();}};
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
  $('#main').innerHTML=heading('Notificaciones','Administra los avisos de este dispositivo.')+'<div class="settings-grid"></div>';
  const alerts=document.createElement('section'); alerts.className='setting-card';
  alerts.innerHTML='<h2>Avisos de reportes</h2><p>Lunes a sábado, 21:00 · Ciudad de México. Tareas programadas sin reporte recibido. En iPhone instala primero la PWA en inicio.</p><button id="enable-alerts" class="btn small">Activar avisos</button> <button id="disable-alerts" class="btn small">Desactivar</button><p id="alerts-status" role="status"></p>';
  $('#main .settings-grid').append(alerts);
  $('#enable-alerts').onclick=async()=>{try{
    if(!('PushManager' in window)||!('Notification' in window))throw Error('Este navegador no admite notificaciones push.');
    if(await Notification.requestPermission()!=='granted')throw Error('Permiso de notificaciones no concedido.');
    const reg=await navigator.serviceWorker.ready;
    const key=(await api('/api/notifications/key')).publicKey;
    const bytes=Uint8Array.from(atob(key.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-key.length%4)%4)),c=>c.charCodeAt(0));
    const sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
    await api('/api/notifications/subscribe',sub.toJSON());
    $('#alerts-status').textContent='Avisos activados para esta cuenta y dispositivo.';
  }catch(e){$('#alerts-status').textContent=e.message;}};
  $('#disable-alerts').onclick=async()=>{try{
    const reg=await navigator.serviceWorker.ready,sub=await reg.pushManager.getSubscription();
    if(sub){await api('/api/notifications/unsubscribe',{endpoint:sub.endpoint});await sub.unsubscribe();}
    $('#alerts-status').textContent='Avisos desactivados.';
  }catch(e){$('#alerts-status').textContent=e.message;}};

  const status=$('#alerts-status');
  if(!('PushManager' in window)||!('Notification' in window)){
    status.textContent='Este navegador no admite avisos push. En iPhone, instala la PWA en inicio.';
    $('#enable-alerts').disabled=true; $('#disable-alerts').disabled=true;
  }else{
    status.textContent=Notification.permission==='denied'?'Notificaciones bloqueadas: habilítalas en los permisos del navegador.':'Pulsa Activar avisos para asociar este dispositivo a tu cuenta.';
  }
}
async function updateStorage(){const persisted=await navigator.storage?.persisted?.();if($('#storage-status'))$('#storage-status').textContent=persisted?'Almacenamiento persistente habilitado.':'Almacenamiento local del navegador. El sistema puede eliminarlo si falta espacio.';}
function taskCompleted(task){return Boolean(task)&&(['FINISHED','COMPLETED'].includes(task.status)||Number(task.progressBps)>=10000);}
async function openCapture(taskId){
  const task=taskById(taskId);
  if(!task){toast('La tarea no está en el catálogo. Sincroniza para actualizarlo.');return;}
  if(taskCompleted(task)){toast('La tarea ya está finalizada; no admite reportes adicionales.');return;}
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
  $('#report-incident').checked=false;$('#incident-fields').hidden=true;$('#incident-fields').disabled=true;
  $('#incident-description').value='';$('#incident-priority').value='normal';$('#incident-stops').checked=false;
  document.querySelectorAll('[name="stop-reason"]').forEach(el=>el.checked=el.value===details?.stoppage?.reason);
  $('#stop-other').value=details?.stoppage?.description||'';state.beforeStop=null;updateStoppage();
  state.draftId=crypto.randomUUID();state.photos=[];state.photoBusy=false;
  $('#report-photos').value='';$('#report-photos').disabled=false;$('#report-form button[type=submit]').disabled=false;$('#photo-status').textContent='';renderPhotoPreviews();
  $('#machinery-rows').innerHTML='';for(const machine of details?.machinery||[])addMachine(machine);
  $('#report-dialog').showModal();
}
$('#close-dialog').onclick=()=>$('#report-dialog').close();
$('#discard-report')?.addEventListener('click',()=>$('#report-dialog').close());
$('#report-dialog')?.addEventListener('click',e=>{if(e.target===$('#report-dialog'))$('#report-dialog').close();});
$('#report-form').onsubmit=async event=>{
  event.preventDefault();const button=$('#report-form button[type=submit]');button.disabled=true;
  try{
    if(taskCompleted(state.currentTask)||taskCompleted(taskById(state.currentTask.id)))throw new Error('La tarea ya está finalizada; no admite reportes adicionales.');
    const progress=Math.round(Number($('#progress-value').value)*100), notes=$('#notes').value.trim();
    if(!notes)throw new Error('Describe el trabajo realizado.');
    if(!Number.isInteger(progress)||progress<state.currentTask.progressBps||progress>10000)throw new Error('El avance debe estar entre el valor actual y 100 %.');
    // Confirmed captures retain their original payload and photo bytes.
    if(state.photoBusy)throw new Error('Espera a que terminen de prepararse las fotos.');
    const id=state.draftId;
    const details=captureDetails();
    const report={id,photos:structuredClone(state.photos),user:state.user,state:'pending',created:new Date().toISOString(),attempts:0,lastAttemptAt:null,lastError:null,nextRetryAt:null,payload:{id,taskId:state.currentTask.id,progressBps:progress,baseProgressBps:state.currentTask.progressBps,operationDate:$('#operation-date').value,notes,crew:structuredClone(state.crew),details,photos:state.photos.map(p=>p.id)}};
    if(!confirm('¿Confirmar este reporte? Después no podrás modificar sus datos ni fotos. Cualquier corrección se registrará como una aclaración separada.'))return;
    if(await dbGet('queue',id))throw new Error('Este reporte ya fue confirmado. Cierra el formulario.');
    await dbWrite('meta',{author:details.author,title:details.title},`author:${state.user}`);
    await dbWrite('queue',report);await reloadLocal();$('#report-dialog').close();toast('Reporte guardado en este dispositivo.');render();if(online())await sync();
  }catch(error){$('#form-error').textContent=error.message||'No se pudo guardar. Revisa el almacenamiento del dispositivo.';}finally{button.disabled=false;}
};
async function refresh(){return window.campoSync.refresh({state,api});}
async function sync(){return window.campoSync.sync({state,api,online,banner,updateChrome,reloadLocal,render});}
async function login(body){return window.campoAuth.login({body,state,api,storage:window.campoStorage,reloadLocal,showApp,sync});}
$('#username').hidden=true;$('#username').required=false;document.querySelector('label[for="username"]')?.setAttribute('hidden','');
const pinDots = document.querySelectorAll('.pin-dot');
function syncPinDots() {
  const pwdVal = $('#password')?.value || '';
  pinDots.forEach((dot, idx) => {
    dot.classList.toggle('filled', idx < pwdVal.length);
  });
}

$('#login-form').onsubmit=async event=>{
  event.preventDefault();
  const button=$('#login-form button[type=submit]');
  button.disabled=true;
  $('#login-error').innerHTML='';
  try{
    await login({user:'',password:$('#password').value});
    $('#password').value='';
    syncPinDots();
  }catch(error){
    $('#login-error').innerHTML=`<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;"><path fill-rule="evenodd" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" clip-rule="evenodd"/></svg> <span>${esc(error.message)}</span>`;
    syncPinDots();
  }finally{
    button.disabled=false;
  }
};

const togglePwdBtn=$('#toggle-password-visibility');
if(togglePwdBtn){
  togglePwdBtn.onclick=()=>{
    const pwd=$('#password');
    if(pwd.type==='password'){
      pwd.type='text';
      togglePwdBtn.innerHTML='<svg id="eye-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
    }else{
      pwd.type='password';
      togglePwdBtn.innerHTML='<svg id="eye-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    }
  };
}

const forgotPinBtn=$('#forgot-pin-btn');
if(forgotPinBtn){
  forgotPinBtn.onclick=(e)=>{
    e.preventDefault();
    toast('Solicita a tu supervisor o administrador que consulte o reasigne tu PIN de acceso.');
  };
}

// Wire Numeric Touchpanel
document.querySelectorAll('.numpad-btn[data-val]').forEach(key => {
  key.addEventListener('click', (e) => {
    e.preventDefault();
    const pwd = $('#password');
    if (pwd && pwd.value.length < 8) {
      pwd.value += key.getAttribute('data-val');
      syncPinDots();
      $('#login-error').textContent = '';
    }
  });
});

const clearKey = $('#btn-clear');
if (clearKey) {
  clearKey.addEventListener('click', (e) => {
    e.preventDefault();
    const pwd = $('#password');
    if (pwd) {
      pwd.value = '';
      syncPinDots();
      $('#login-error').textContent = '';
    }
  });
}

const backKey = $('#btn-backspace');
if (backKey) {
  backKey.addEventListener('click', (e) => {
    e.preventDefault();
    const pwd = $('#password');
    if (pwd) {
      pwd.value = pwd.value.slice(0, -1);
      syncPinDots();
      $('#login-error').textContent = '';
    }
  });
}

const pwdField = $('#password');
if (pwdField) {
  pwdField.addEventListener('input', syncPinDots);
}
async function logout(){return window.campoAuth.logout({state,api,storage:window.campoStorage,showLogin,toast});}
function exportPending(){const blob=new Blob([JSON.stringify({exportedAt:new Date().toISOString(),user:state.user,reports:state.local},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`campo-pendientes-${today()}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}
$('#logout').onclick=logout;$('#sync').onclick=()=>sync();
let notificationRequestBusy=false;
let notificationCheckBusy=false, notificationCheckedUser=null, notificationCheckedAt=0, notificationRevision=0;
function paintNotificationState(value){
  const bell=$('#notifications-bell');
  bell.dataset.notificationState=value;
  const labels={active:'Notificaciones activadas',inactive:'Activar notificaciones',blocked:'Notificaciones bloqueadas',checking:'Comprobando notificaciones',unknown:'No se pudo verificar la suscripción',unsupported:'Notificaciones no disponibles'};
  bell.title=labels[value];bell.setAttribute('aria-label',labels[value]);
  if(value==='active'){bell.title=`Avisos activos para ${state.user} en este dispositivo`;bell.setAttribute('aria-label',bell.title);}
  bell.setAttribute('aria-pressed',String(value==='active'));
}
async function refreshNotificationState(force=false){
  updateNotificationNotice();
  if(!state.user||$('#app').hidden||notificationCheckBusy||notificationRequestBusy)return;
  if(!force&&notificationCheckedUser===state.user&&Date.now()-notificationCheckedAt<60000)return;
  const user=state.user, revision=notificationRevision;notificationCheckBusy=true;notificationCheckedUser=user;notificationCheckedAt=Date.now();
  paintNotificationState('checking');
  try{
    if(!('PushManager' in window)||!('Notification' in window)){paintNotificationState('unsupported');return;}
    if(Notification.permission!=='granted'){paintNotificationState(Notification.permission==='denied'?'blocked':'inactive');return;}
    const reg=await navigator.serviceWorker.getRegistration();
    const sub=reg&&await reg.pushManager.getSubscription();
    if(state.user!==user||$('#app').hidden||revision!==notificationRevision)return;
    if(!sub){paintNotificationState('inactive');return;}
    const result=await api('/api/notifications/status',{endpoint:sub.endpoint});
    if(state.user===user&&!$('#app').hidden&&revision===notificationRevision)paintNotificationState(result.subscribed?'active':'inactive');
  }catch(_){if(state.user===user&&revision===notificationRevision)paintNotificationState('unknown');}
  finally{notificationCheckBusy=false;if(revision!==notificationRevision||state.user!==user)refreshNotificationState(true);}
}
function updateNotificationNotice(message){
  const notice=$('#notification-permission-notice');
  if(!notice)return;
  let dismissed=false;
  try{dismissed=localStorage.getItem('campo-notification-permission-pending')==='true';}catch(_){}
  const permission='Notification' in window?Notification.permission:'unsupported';
  notice.textContent=message || (permission==='denied'
    ? 'Notificaciones bloqueadas. Para activarlas, abre los permisos de este sitio en tu navegador y cambia Notificaciones a Permitir. Después toca la campana.'
    : permission==='default' && dismissed ? 'Los avisos aún no están activados. Toca la campana para volver a solicitar el permiso.' : '');
  notice.hidden=!notice.textContent;
}
async function activateNotificationsDirectly(){
  if(notificationRequestBusy)return;
  notificationRequestBusy=true;
  notificationRevision++;
  const bell=$('#notifications-bell');bell.disabled=true;
  try{
    if(!('PushManager' in window)||!('Notification' in window))throw Error('Este navegador no admite avisos push. En iPhone, instala la PWA en la pantalla de inicio.');
    const permission=Notification.permission==='granted'?'granted':await Notification.requestPermission();
    if(permission!=='granted'){
      try{localStorage.setItem('campo-notification-permission-pending','true');}catch(_){}
      updateNotificationNotice();return;
    }
    const reg=await navigator.serviceWorker.ready;
    const key=(await api('/api/notifications/key')).publicKey;
    const bytes=Uint8Array.from(atob(key.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-key.length%4)%4)),c=>c.charCodeAt(0));
    const sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
    await api('/api/notifications/subscribe',sub.toJSON());
    try{localStorage.removeItem('campo-notification-permission-pending');}catch(_){}
    updateNotificationNotice();toast('Avisos activados para esta cuenta y dispositivo.');
  }catch(e){updateNotificationNotice(e.message);}
  finally{notificationRequestBusy=false;bell.disabled=false;await refreshNotificationState(true);}
}
$('#notifications-bell').onclick=activateNotificationsDirectly;
window.campoRestorePush=async()=>{
  if('Notification' in window&&Notification.permission==='granted')await activateNotificationsDirectly();
};
window.addEventListener('focus',()=>refreshNotificationState(true));
let lastAutomaticSync=0;
function automaticSync(force=false){
  if(!state.user||!online()||state.syncing||$('#app').hidden||document.hidden)return;
  if(!force&&Date.now()-lastAutomaticSync<30000)return;
  lastAutomaticSync=Date.now();sync();
}
window.addEventListener('focus',()=>automaticSync());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)automaticSync();});
if('serviceWorker' in navigator)navigator.serviceWorker.addEventListener('message',event=>{
  if(event.data?.type==='campo-refresh-catalog')automaticSync(true);
});
document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>{state.view=el.dataset.view;render();});
window.addEventListener('offline',()=>{state.reachable=false;updateChrome();banner('Sin conexión. Puedes capturar avances; se guardarán en este dispositivo.');});
window.addEventListener('online',()=>{state.reachable=true;if(state.user)sync();});
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();state.install=event;$('#install').hidden=false;});
$('#install').onclick=async()=>{if(state.install){await state.install.prompt();state.install=null;$('#install').hidden=true;}};
// Poll delivery receipts while online; never sends new operational reports from a timer.
setInterval(async()=>{if(!state.user||!online()||state.syncing||$('#app').hidden||document.hidden)return;try{if(state.local.some(row=>row.state==='pending')){await sync();return;}const data=await api('/api/reports');if(JSON.stringify(data.reports)!==JSON.stringify(state.reports)){state.reports=data.reports;state.topics=data.topics;await dbWrite('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);if(['reports','telegram'].includes(state.view))render();}}catch(error){if(error.status===401)banner(error.message,true);}},5000);
async function setupTelegram(){return window.campoAuth.setupTelegram({showLogin,login,$});}
async function boot(){return window.campoAuth.boot({state,storage:window.campoStorage,showLogin,showApp,reloadLocal,sync,setupTelegram,banner,$});}
boot();


const crewRoles = {operator:'Operadores',technician:'Técnicos',assistant:'Auxiliares'};
function crewSummary(crew){return crew?.length?`<div class="crew-summary"><strong>Personal en campo · ${crew.length} personas</strong>${Object.entries(crewRoles).map(([role,label])=>{const names=crew.filter(e=>e.role===role).map(e=>esc(e.name));return names.length?`<div>${label}: ${names.join(', ')}</div>`:'';}).join('')}</div>`:'';}
async function refreshEmployees(){
  const result=await api('/api/employees');state.catalog.employees=result.employees;
  await dbWrite('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);
}
function empInitials(name){
  const parts=String(name||'').trim().split(/\s+/).filter(Boolean);
  const filtered=parts.length>1?parts.filter(w=>!['de','del','la','las','los','y'].includes(w.toLowerCase())):parts;
  const source=filtered.length?filtered:parts;
  return source.map(s=>s[0]).slice(0,2).join('').toUpperCase()||'EM';
}
function renderEmployees(){
  state.employeeRoleFilter=state.employeeRoleFilter||'all';
  $('#main').innerHTML=heading('Empleados','Directorio de cuadrilla y asignación de roles operativos en campo.', '<button id="new-employee" class="btn primary emp-new-btn"><span class="emp-new-btn-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg></span><span>Nuevo empleado</span></button>')+`
    <section class="employees-panel">
      <div id="employees-stats" class="employees-stats"></div>
      <div class="employees-toolbar">
        <div class="employees-search-row">
          <div class="emp-search-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input id="employee-search" type="search" placeholder="Buscar integrante por nombre…" aria-label="Buscar empleados" value="${esc(state.employeeSearch||'')}">
          </div>
          <button id="refresh-employees" class="btn small subtle emp-refresh-btn" title="Actualizar catálogo">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            <span>Actualizar</span>
          </button>
        </div>
        <div class="emp-role-filters" id="emp-role-filters">
          <button type="button" class="emp-filter-pill ${state.employeeRoleFilter==='all'?'active':''}" data-emp-role="all">Todos</button>
          <button type="button" class="emp-filter-pill ${state.employeeRoleFilter==='operator'?'active':''}" data-emp-role="operator">Operadores</button>
          <button type="button" class="emp-filter-pill ${state.employeeRoleFilter==='technician'?'active':''}" data-emp-role="technician">Técnicos</button>
          <button type="button" class="emp-filter-pill ${state.employeeRoleFilter==='assistant'?'active':''}" data-emp-role="assistant">Auxiliares</button>
        </div>
      </div>
      <div id="employee-list"></div>
    </section>`;
  $('#employee-search').oninput=e=>{state.employeeSearch=e.target.value;state.employeePage=1;renderEmployeeList();};
  $('#new-employee').onclick=()=>openEmployee();
  $('#refresh-employees').onclick=async()=>{try{await refreshEmployees();renderEmployeeList();toast('Catálogo actualizado.');}catch(error){toast(error.message);}};
  document.querySelectorAll('[data-emp-role]').forEach(btn=>{
    btn.onclick=()=>{
      state.employeeRoleFilter=btn.dataset.empRole;
      state.employeePage=1;
      document.querySelectorAll('[data-emp-role]').forEach(b=>b.classList.toggle('active',b.dataset.empRole===state.employeeRoleFilter));
      renderEmployeeList();
    };
  });
  renderEmployeeList();
}
function renderEmployeeList(){
  const all=state.catalog.employees||[];
  const roleFilter=state.employeeRoleFilter||'all';
  const search=(state.employeeSearch||'').toLocaleLowerCase('es').trim();
  const items=all.filter(e=>{
    const matchName=!search||e.name.toLocaleLowerCase('es').includes(search);
    const matchRole=roleFilter==='all'||(Array.isArray(e.roles)&&e.roles.includes(roleFilter));
    return matchName&&matchRole;
  });
  const statsEl=$('#employees-stats');
  if(statsEl){
    const countRole=r=>all.filter(e=>Array.isArray(e.roles)&&e.roles.includes(r)).length;
    statsEl.innerHTML=`
      <article class="emp-stat-card">
        <span class="emp-stat-label">Total cuadrilla</span>
        <strong class="emp-stat-value">${all.length}</strong>
      </article>
      <article class="emp-stat-card emp-stat-operator">
        <span class="emp-stat-label">Operadores</span>
        <strong class="emp-stat-value">${countRole('operator')}</strong>
      </article>
      <article class="emp-stat-card emp-stat-technician">
        <span class="emp-stat-label">Técnicos</span>
        <strong class="emp-stat-value">${countRole('technician')}</strong>
      </article>
      <article class="emp-stat-card emp-stat-assistant">
        <span class="emp-stat-label">Auxiliares</span>
        <strong class="emp-stat-value">${countRole('assistant')}</strong>
      </article>
    `;
  }
  const pageSize=10;
  const totalPages=Math.max(1,Math.ceil(items.length/pageSize));
  state.employeePage=Math.min(Math.max(1,state.employeePage||1),totalPages);
  const start=(state.employeePage-1)*pageSize;
  const pageItems=items.slice(start,start+pageSize);
  $('#employee-list').innerHTML=items.length?`
    <div class="table-wrap emp-table-wrap">
      <table class="employee-table">
        <thead>
          <tr>
            <th class="person-column">INTEGRANTE</th>
            <th class="roles-column">ROLES HABILITADOS</th>
            <th class="status-column">ESTADO</th>
            <th style="text-align:right"><span class="muted">ACCIONES</span></th>
          </tr>
        </thead>
        <tbody>
          ${pageItems.map(e=>{
            const roleBadges=e.roles.map(r=>`<span class="chip role-chip role-${esc(r)}">${esc(crewRoles[r]||r)}</span>`).join('');
            return `
            <tr>
              <td class="person-column">
                <div class="person emp-person-cell">
                  <div class="person-avatar-wrap">
                    <span class="person-circle">${esc(empInitials(e.name))}</span>
                    <span class="person-status-dot" title="Habilitado"></span>
                  </div>
                  <div class="person-info">
                    <strong class="person-name">${esc(e.name)}</strong>
                    <div class="person-mobile-meta">
                      ${roleBadges}
                    </div>
                  </div>
                </div>
              </td>
              <td class="roles-column">
                <div class="role-tags">
                  ${roleBadges}
                </div>
              </td>
              <td class="status-column"><span class="status green">Habilitado</span></td>
              <td class="table-action" style="text-align:right">
                <div class="action-btn-group emp-actions">
                  <button class="btn small subtle emp-btn-edit" data-edit-employee="${esc(e.id)}" title="Editar empleado" aria-label="Editar ${esc(e.name)}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                    <span class="emp-btn-label">Editar</span>
                  </button>
                  <button class="btn small danger emp-btn-delete" data-delete-employee="${esc(e.id)}" title="Eliminar empleado" aria-label="Eliminar ${esc(e.name)}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    <span class="emp-btn-label">Eliminar</span>
                  </button>
                </div>
              </td>
            </tr>
          `;}).join('')}
        </tbody>
      </table>
    </div>
    <div class="table-caption table-pagination-bar">
      <span>Mostrando ${start+1}–${Math.min(items.length,start+pageItems.length)} de ${items.length} integrante(s) · Página ${state.employeePage} de ${totalPages}</span>
      <div class="pagination-btns">
        <button type="button" class="btn subtle small" id="emp-page-prev" ${state.employeePage<=1?'disabled':''}>&lt; Anterior</button>
        <button type="button" class="btn subtle small" id="emp-page-next" ${state.employeePage>=totalPages?'disabled':''}>Siguiente &gt;</button>
      </div>
    </div>
  `:`<div class="empty"><h3>${all.length?'No hay coincidencias':'Aún no hay empleados'}</h3><p>${all.length?'Prueba otro nombre o filtro de rol.':'Pulsa Nuevo empleado para registrar a la primera persona de tu cuadrilla.'}</p></div>`;
  if($('#emp-page-prev'))$('#emp-page-prev').onclick=()=>{if(state.employeePage>1){state.employeePage--;renderEmployeeList();}};
  if($('#emp-page-next'))$('#emp-page-next').onclick=()=>{if(state.employeePage<totalPages){state.employeePage++;renderEmployeeList();}};
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
  const incident=$('#report-incident').checked?{description:$('#incident-description').value.trim(),priority:$('#incident-priority').value,stopsWork:$('#incident-stops').checked}:null;
  if(incident&&!incident.description)throw new Error('Describe la incidencia.');
  return {...(incident?{incident}:{}),...(stopped?{stoppage:{reason,description:reason==='Otro'?$('#stop-other').value.trim():''}}:{}),author,title,quantity:Number($('#work-quantity').value),unit:$('#work-unit').value,
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
$('#report-incident').onchange=()=>{const active=$('#report-incident').checked;$('#incident-fields').hidden=!active;$('#incident-fields').disabled=!active;};
document.querySelectorAll('[name="stop-reason"]').forEach(el=>el.onchange=updateStoppage);

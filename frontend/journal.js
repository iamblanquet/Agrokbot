'use strict';
window.campoJournal = {
  project:'', rows:[], projects:[], fetched:'', page:1, selected:null,
  filters:{from:'',to:'',task:'',author:'',status:''},
  async render(){
    const {$,esc,heading,api}=window.campoUi;
    const self=this;
    $('#main').innerHTML=heading('Bitácora ERP','Historial del ERP · Solo consulta')+`<section id="journal" class="journal"><div class="journal-tools"><label>Proyecto<select id="journal-project"><option value="">Selecciona un proyecto</option></select></label><button id="journal-refresh" class="btn primary">Actualizar desde ERP</button></div><p id="journal-message" role="status"></p><p id="journal-time" class="muted"></p><div class="journal-filters"><label>Desde<input id="journal-from" type="date"></label><label>Hasta<input id="journal-to" type="date"></label><label>Tarea<select id="journal-task"></select></label><label>Autor<select id="journal-author"></select></label><label>Estado<select id="journal-status"></select></label><button id="journal-clear" class="btn">Limpiar filtros</button></div><div id="journal-results"></div><div class="journal-pagination"><button id="journal-prev" class="btn">Anterior</button><span id="journal-count" aria-live="polite"></span><button id="journal-next" class="btn">Siguiente</button></div><section id="journal-detail" tabindex="-1"></section></section>`;
    const root=$('#journal'), find=s=>root.querySelector(s), active=()=>root.isConnected;
    const label=s=>({IN_PROGRESS:'En progreso',FINISHED:'Finalizado',CREATED:'Creado',CANCELLED:'Cancelado'})[s]||s||'Sin estado';
    const progress=n=>typeof n==='number'?`${(n/100).toLocaleString('es-MX')} %`:'Sin avance informado';
    const fill=(id,values,all)=>{find(id).innerHTML=`<option value="">${all}</option>`+[...new Set(values.filter(Boolean))].sort().map(v=>`<option value="${esc(v)}">${esc(id==='#journal-status'?label(v):v)}</option>`).join('');};
    const controls=()=>{
      fill('#journal-task',self.rows.map(r=>r.taskName),'Todas las tareas');
      fill('#journal-author',self.rows.map(r=>r.author),'Todos los autores');
      fill('#journal-status',self.rows.map(r=>r.status),'Todos los estados');
      for(const key of Object.keys(self.filters))find('#journal-'+key).value=self.filters[key];
    };
    const detail=row=>{
      self.selected=row.id;
      const base={project:self.project,log:row.id};
      const url=(a,kind)=>'/api/admin/journal/'+kind+'?'+new URLSearchParams({...base,attachment:a.id});
      find('#journal-detail').innerHTML=`<article class="journal-detail"><div class="journal-tools"><h2>Detalle del asiento</h2><button id="journal-close" class="btn">Cerrar detalle</button></div><dl><dt>Referencia ERP</dt><dd>${esc(row.id)}</dd><dt>Fecha operativa</dt><dd>${esc((row.operationDate||'').slice(0,10)||'Sin fecha')}</dd><dt>Actividad / tarea</dt><dd>${esc(row.activityName)} / ${esc(row.taskCode)} · ${esc(row.taskName)}</dd><dt>Autor</dt><dd>${esc(row.author)}</dd><dt>Responsable de tarea</dt><dd>${esc(row.responsible||'No informado')}</dd><dt>Avance / estado</dt><dd>${esc(progress(row.progressBps))} · ${esc(label(row.status))}</dd><dt>Origen</dt><dd>${esc(row.source||'No informado')}</dd></dl><h3>Observaciones</h3><p class="journal-notes">${esc(row.notes||'Sin observaciones')}</p><h3>Evidencias (${row.attachments.length})</h3><div class="journal-gallery">${row.attachments.map(a=>`<figure><img src="${esc(url(a,'preview'))}" alt="${esc(a.originalFileName||'Evidencia')}" loading="lazy"><figcaption>${esc(a.originalFileName||'Fotografía')}<p class="journal-image-error" hidden>No se pudo cargar la vista previa. Intenta actualizar o descargar el original.</p><a class="btn small" href="${esc(url(a,'file'))}">Descargar original</a></figcaption></figure>`).join('')||'<p>Este asiento no tiene fotografías.</p>'}</div></article>`;
      find('#journal-close').onclick=()=>{self.selected=null;find('#journal-detail').innerHTML='';};
      find('#journal-detail').querySelectorAll('img').forEach(img=>img.onerror=()=>{img.hidden=true;img.parentElement.querySelector('.journal-image-error').hidden=false;});
    };
    const draw=()=>{
      const f=self.filters;
      const invalid=f.from&&f.to&&f.from>f.to;
      const rows=invalid?[]:self.rows.filter(r=>{const d=(r.operationDate||'').slice(0,10);return (!f.from||d>=f.from)&&(!f.to||(d&&d<=f.to))&&(!f.task||r.taskName===f.task)&&(!f.author||r.author===f.author)&&(!f.status||r.status===f.status);});
      const pages=Math.max(1,Math.ceil(rows.length/20));self.page=Math.max(1,Math.min(self.page,pages));
      find('#journal-count').textContent=`${rows.length} registros · Página ${self.page} de ${pages}`;
      find('#journal-prev').disabled=self.page===1;find('#journal-next').disabled=self.page===pages;
      find('#journal-time').textContent=self.fetched?'Última consulta: '+new Date(self.fetched).toLocaleString('es-MX'):'';
      find('#journal-results').innerHTML=invalid?'<p role="alert">La fecha inicial debe ser anterior o igual a la final.</p>':rows.length?`<div class="journal-list">${rows.slice((self.page-1)*20,self.page*20).map(r=>`<article class="journal-card"><div><small>${esc((r.operationDate||'').slice(0,10)||'Sin fecha')} · ${esc(label(r.status))}</small><h3>${esc(r.taskName)}</h3><p>${esc(r.author)} · ${esc(progress(r.progressBps))}</p><p class="muted">${r.attachments.length} fotografía(s)</p></div><button class="btn" data-entry="${esc(r.id)}">Ver detalle</button></article>`).join('')}</div>`:`<p class="empty">${self.project?'No hay registros para los filtros seleccionados.':'Selecciona un proyecto para consultar su bitácora.'}</p>`;
      find('#journal-results').querySelectorAll('[data-entry]').forEach(button=>button.onclick=()=>{detail(self.rows.find(r=>r.id===button.dataset.entry));find('#journal-detail').focus();find('#journal-detail').scrollIntoView({behavior:'smooth',block:'start'});});
    };
    let requestId=0;
    const load=async()=>{
      const id=++requestId;self.selected=null;self.rows=[];self.fetched='';find('#journal-detail').innerHTML='';controls();draw();
      if(!self.project){find('#journal-message').textContent='';return;}
      find('#journal-message').textContent='Consultando asientos en el ERP…';find('#journal-refresh').disabled=true;
      try{
        const data=await api('/api/admin/journal/entries?'+new URLSearchParams({project:self.project}));
        if(!active()||id!==requestId)return;
        self.rows=data.entries;self.fetched=new Date().toISOString();self.page=1;controls();draw();find('#journal-message').textContent='Consulta actualizada.';
      }catch(error){if(active()&&id===requestId)find('#journal-message').textContent='No se pudo consultar el ERP: '+error.message;}
      finally{if(active()&&id===requestId)find('#journal-refresh').disabled=false;}
    };
    for(const key of Object.keys(self.filters))find('#journal-'+key).onchange=e=>{self.filters[key]=e.target.value;self.page=1;draw();};
    find('#journal-clear').onclick=()=>{for(const key of Object.keys(self.filters))self.filters[key]='';controls();draw();};
    find('#journal-prev').onclick=()=>{self.page--;draw();};find('#journal-next').onclick=()=>{self.page++;draw();};
    find('#journal-refresh').onclick=load;
    find('#journal-project').onchange=e=>{self.project=e.target.value;self.filters={from:'',to:'',task:'',author:'',status:''};load();};
    controls();draw();
    find('#journal-message').textContent='Consultando proyectos en el ERP…';
    try{
      const data=await api('/api/admin/journal/projects');if(!active())return;
      self.projects=data.projects;
      find('#journal-project').innerHTML='<option value="">Selecciona un proyecto</option>'+data.projects.map(p=>`<option value="${esc(p.id)}">${esc(p.folio||p.code||'')} · ${esc(p.name)}</option>`).join('');
      if(!data.projects.some(p=>p.id===self.project)){self.project='';self.rows=[];self.fetched='';}
      find('#journal-project').value=self.project;find('#journal-message').textContent=data.projects.length?'':'No hay proyectos disponibles.';
      if(self.project)await load();else draw();
    }catch(error){if(active()){self.rows=[];self.fetched='';draw();find('#journal-message').textContent='La bitácora necesita conexión al ERP: '+error.message;}}
  }
};

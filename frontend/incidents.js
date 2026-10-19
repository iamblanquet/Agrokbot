'use strict';
window.campoIncidents={async render(){
  const {$,esc,heading,api}=window.campoUi;
  $('#main').innerHTML=heading('Incidencias','Seguimiento vinculado al diario ERP. Requiere conexión.')+`<section class="admin-panel"><label for="incident-filter">Estado</label><select id="incident-filter"><option value="">Todos</option><option value="open">Abierta</option><option value="in_progress">En atención</option><option value="resolved">Resuelta</option></select><button id="incident-refresh" class="btn">Actualizar</button><p id="incident-error" role="status"></p><div id="incident-list">Cargando…</div></section>`;
  const list=$('#incident-list'),error=$('#incident-error'),filter=$('#incident-filter');
  const labels={open:'Abierta',in_progress:'En atención',resolved:'Resuelta'};
  let rows=[];
  const draw=()=>{
    list.innerHTML=rows.filter(r=>!filter.value||r.status===filter.value).map(r=>`<article class="admin-panel"><h3>${esc(r.payload.task)}</h3><p>${esc(r.payload.project)} · ${esc(r.payload.author)} · ${esc(r.payload.operationDate)}</p><p>${esc(labels[r.status])} · Prioridad: ${esc(r.payload.priority)} · Detiene actividad: ${r.payload.stopsWork?'Sí':'No'}</p><p style="white-space:pre-wrap">${esc(r.payload.description)}</p><small>Ref: ${esc(r.id)} · Asiento ERP: ${esc(r.erp_log_id)} · Aviso Telegram: ${esc(r.telegramState)}</small><details><summary>Historial (${r.events.length})</summary>${r.events.map(e=>`<p>${esc(e.created)} · ${esc(e.actor)} · ${esc(labels[e.status])}<br>${esc(e.note)}</p>`).join('')}</details><form data-incident="${esc(r.id)}"><label>Nuevo estado<select name="status">${Object.entries(labels).map(([v,l])=>`<option value="${v}" ${v===r.status?'selected':''}>${l}</option>`).join('')}</select></label><label>Comentario de seguimiento<textarea name="note" required maxlength="1000"></textarea></label><button class="btn primary" type="submit">Guardar seguimiento</button></form></article>`).join('')||'<p>No hay incidencias en este estado.</p>';
    list.querySelectorAll('form[data-incident]').forEach(form=>form.onsubmit=async event=>{
      event.preventDefault();const button=form.querySelector('button');button.disabled=true;error.textContent='';
      const row=rows.find(r=>r.id===form.dataset.incident);
      try{await api('/api/incidents/update',{id:row.id,version:row.version,status:form.elements.status.value,note:form.elements.note.value});await load();}
      catch(e){error.textContent=e.message;button.disabled=false;}
    });
  };
  const load=async()=>{try{const data=await api('/api/incidents');rows=data.incidents;error.textContent='';draw();}catch(e){error.textContent=e.message;list.textContent='No se pudo consultar el seguimiento.';}};
  filter.onchange=draw;$('#incident-refresh').onclick=load;await load();
}};

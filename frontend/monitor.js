'use strict';

// Monitoreo de transacciones ERP <-> Telegram (solo administrador, solo lectura salvo reintento).
window.campoMonitor = {
  async render(){
    const { $, esc, heading, api, toast } = window.campoUi;
    $('#main').innerHTML=heading('Monitoreo de integraciones','Reportes enviados al ERP y publicados en Telegram.')+`<div id="monitor-root">
      <section class="monitor-stats" id="monitor-stats"></section>
      <div class="view-tools monitor-tools">
        <select id="monitor-state" aria-label="Filtrar por estado"><option value="all">Todos los estados</option><option value="failed">Con error</option><option value="review">Por verificar</option><option value="pending">En proceso</option><option value="stuck">Atorados</option><option value="ok">Publicados</option></select>
        <select id="monitor-hours" aria-label="Periodo"><option value="24">Últimas 24 horas</option><option value="168">Últimos 7 días</option><option value="720">Últimos 30 días</option></select>
        <button id="monitor-refresh" class="btn small" type="button">Actualizar</button>
        <small id="monitor-updated" class="muted"></small>
      </div>
      <p id="monitor-error" class="error" role="alert"></p>
      <div id="monitor-table"></div>
      <section><h3>Conectividad y avisos pendientes</h3>
        <button id="monitor-health" class="btn small" type="button">Comprobar conectividad</button>
        <p id="monitor-health-result"></p><div id="monitor-notifications"></div>
      </section></div>`;
    const label={ok:['green','Correcto'],pending:['blue','En proceso'],waiting:['','—'],review:['amber','Verificar'],failed:['red','Error'],unknown:['','?']};
    const pill=v=>{const [c,t]=label[v]||label.unknown;return `<span class="status ${c}">${t}</span>`;};
    const when=iso=>{const d=new Date(iso);return isNaN(d)?esc(iso):d.toLocaleString('es-MX',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});};
    let page=1, transactions=[];
    const PAGE_SIZE=10;

    function bindEvidence(){
        document.querySelectorAll('[data-evidence]').forEach(b=>b.onclick=async()=>{
          const note=prompt('Nota de conciliación (solo lectura del ERP, sin reenviar ni borrar fotos):');if(!note?.trim())return;
          const erpLogId=prompt('ID del asiento original; deja vacío para comprobar la referencia guardada:');if(erpLogId===null)return;
          try{await api('/api/admin/monitor/evidence',{id:b.dataset.evidence,note:note.trim(),erpLogId:erpLogId.trim()||null});await load();toast('Evidencias verificadas.');}catch(e){toast(e.message);}
        });
    }
    const drawTable=()=>{
      if(!$('#monitor-table'))return;
      if(!transactions.length){
        $('#monitor-table').innerHTML='<div class="empty"><h3>Sin transacciones</h3><p>No hay reportes que coincidan con el filtro.</p></div>';
        return;
      }
      const totalPages=Math.max(1,Math.ceil(transactions.length/PAGE_SIZE));
      page=Math.min(Math.max(1,page),totalPages);
      const start=(page-1)*PAGE_SIZE;
      const pageRows=transactions.slice(start,start+PAGE_SIZE);

      $('#monitor-table').innerHTML=`<div class="admin-table"><div class="monitor-row admin-head"><span>FECHA</span><span>USUARIO</span><span>PROYECTO</span><span>ERP</span><span>TELEGRAM</span><span>DETALLE</span><span></span></div>${pageRows.map(t=>`<div class="monitor-row"><span>${when(t.created)}<small>${t.ageMinutes<1?'menos de 1 min':t.ageMinutes+' min abierta(s)'}</small></span><span>${esc(t.user)}</span><span>${esc(t.project)}<small>${t.photos?t.photos+' foto(s)':'sin fotos'}</small></span><span>${pill(t.erp)}</span><span>${pill(t.telegram)}${t.stuck?' <span class="status amber">Atorado</span>':''}</span><span class="mono">${esc(t.error||'')}${t.erpLogId?`<small>ERP: ${esc(t.erpLogId)}</small>`:''}<small>Ref: ${esc(t.id.slice(0,8))}</small></span><span>${t.state==='telegram_failed'?`<button class="btn small" data-retry="${esc(t.id)}">Reintentar</button>`:''}${t.state==='evidence_review'?`<button class="btn small" data-evidence="${esc(t.id)}">Conciliar evidencias</button>`:''}${['erp_review','telegram_review'].includes(t.state)?`<button class="btn small" data-resolve="${esc(t.id)}">Resolver</button>`:''}</span></div>`).join('')}</div>
      <div class="table-caption table-pagination-bar">
        <span>Mostrando ${start+1}–${Math.min(transactions.length,start+pageRows.length)} de ${transactions.length} transacción(es) · Página ${page} de ${totalPages}</span>
        <div class="pagination-btns">
          <button type="button" class="btn subtle small" id="monitor-prev" ${page<=1?'disabled':''}>&lt; Anterior</button>
          <button type="button" class="btn subtle small" id="monitor-next" ${page>=totalPages?'disabled':''}>Siguiente &gt;</button>
        </div>
      </div>`;

      if($('#monitor-prev'))$('#monitor-prev').onclick=()=>{if(page>1){page--;drawTable();}};
      if($('#monitor-next'))$('#monitor-next').onclick=()=>{if(page<totalPages){page++;drawTable();}};
      document.querySelectorAll('#monitor-table [data-retry]').forEach(b=>b.onclick=async()=>{try{await api('/api/admin/monitor/retry',{id:b.dataset.retry});toast('Envío puesto en cola.');await load();}catch(e){toast(e.message);}});
      document.querySelectorAll('#monitor-table [data-resolve]').forEach(b=>b.onclick=async()=>{const decision=prompt('Escribe CONFIRMAR para validar el resultado o RECHAZAR para dejarlo como no enviado.');if(!decision)return;const normalized=decision.trim().toLowerCase();if(!['confirmar','rechazar'].includes(normalized)){toast('Decisión inválida.');return;}const note=prompt('Describe la evidencia o motivo de la resolución:');if(!note?.trim())return;const transaction=transactions.find(t=>t.id===b.dataset.resolve);const erpLogId=normalized==='confirmar'&&transaction?.state==='erp_review'?prompt('Identificador del asiento ERP original (se verificará su clientReportId):'):null;if(normalized==='confirmar'&&transaction?.state==='erp_review'&&!erpLogId)return;try{await api('/api/admin/monitor/resolve',{erpLogId,id:b.dataset.resolve,decision:normalized==='confirmar'?'confirm':'reject',note:note.trim()});toast('Resolución registrada en la bitácora.');await load();}catch(e){toast(e.message);}});
      bindEvidence();
    };

    const loadNotifications=async()=>{
      const data=await api('/api/admin/notifications/pending');
      $('#monitor-notifications').innerHTML=(data.deliveries||[]).map(d=>`<p><code>${esc(d.id)}</code> · ${esc(d.state)} · ${esc(d.error||'')} <button class="btn small" data-delivery="${esc(d.id)}">Resolver</button></p>`).join('')+
        (data.topics||[]).map(t=>`<p>Tema pendiente: ${esc(t.key)} <button class="btn small" data-topic="${esc(t.key)}">Resolver tema</button></p>`).join('');
      document.querySelectorAll('[data-delivery],[data-topic]').forEach(b=>b.onclick=async()=>{
        const note=prompt('Verifica primero en Telegram/proveedor y describe lo comprobado:');if(!note?.trim())return;
        let body={note:note.trim(),verified:true};
        if(b.dataset.topic){
          const value=prompt('ID del tema existente. Escribe 0 solo si verificaste que NO se creó:');if(value===null||! /^[0-9]+$/.test(value))return;
          body={...body,topic:b.dataset.topic,topicId:Number(value)};
        }else{
          const decision=prompt('Escribe ENVIADO si verificaste la entrega o REINTENTAR si verificaste que NO se envió:');
          if(!['ENVIADO','REINTENTAR'].includes(decision?.trim().toUpperCase()))return;
          body={...body,id:b.dataset.delivery,decision:decision.trim().toUpperCase()==='ENVIADO'?'sent':'retry'};
        }
        try{await api('/api/admin/notifications/resolve',body);await loadNotifications();toast('Resolución registrada.');}catch(e){toast(e.message);}
      });
    };
    $('#monitor-health').onclick=async()=>{
      $('#monitor-health-result').textContent='Comprobando…';
      try{const data=await api('/api/admin/health');$('#monitor-health-result').textContent='ERP: '+data.checks.erp+' · Telegram: '+data.checks.telegram+' · '+Object.entries(data.workers).map(([k,v])=>k+': '+(v.stale?'sin actividad reciente':'activo')).join(' · ')+'. Conectividad no equivale a entrega confirmada.';}catch(e){$('#monitor-health-result').textContent=e.message;}
    };
    const load=async()=>{
      if(!$('#monitor-root'))return;
      try{
        const data=await api(`/api/admin/monitor?state=${encodeURIComponent($('#monitor-state').value)}&hours=${$('#monitor-hours').value}`);
        const s=data.summary;
        transactions=data.transactions||[];
        $('#monitor-stats').innerHTML=[['TOTAL',s.total,'reportes en el periodo',''],['PUBLICADOS',s.ok,'ERP y Telegram',''],['EN PROCESO',s.pending,s.stuck?`${s.stuck} atorado(s)`:'sin atorados',s.stuck?'warn':''],['POR VERIFICAR',s.review,'resultado ambiguo',s.review?'warn':''],['CON ERROR',s.failed,'requieren acción',s.failed?'bad':'']]
          .map(([a,b,c,k])=>`<div class="monitor-stat ${k}"><small>${a}</small><strong>${b}</strong><span>${c}</span></div>`).join('');
        drawTable();
        await loadNotifications();
        $('#monitor-updated').textContent='Actualizado '+new Date().toLocaleTimeString('es-MX');
        $('#monitor-error').textContent='';
      }catch(e){$('#monitor-error').textContent=e.message;}
    };
    $('#monitor-state').onchange=()=>{page=1;load();};
    $('#monitor-hours').onchange=()=>{page=1;load();};
    $('#monitor-refresh').onclick=load;
    await load();
    const timer=setInterval(()=>{if(!$('#monitor-root'))return clearInterval(timer);if(!document.hidden)load();},30000);
  }
};

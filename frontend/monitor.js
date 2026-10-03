'use strict';

// Monitoreo de transacciones ERP ↔ Telegram (solo administrador, solo lectura salvo reintento).
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
      <div id="monitor-table"></div></div>`;
    const label={ok:['green','Correcto'],pending:['blue','En proceso'],waiting:['','—'],review:['amber','Verificar'],failed:['red','Error'],unknown:['','?']};
    const pill=v=>{const [c,t]=label[v]||label.unknown;return `<span class="status ${c}">${t}</span>`;};
    const when=iso=>{const d=new Date(iso);return isNaN(d)?esc(iso):d.toLocaleString('es-MX',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});};
    const load=async()=>{
      if(!$('#monitor-root'))return;
      try{
        const data=await api(`/api/admin/monitor?state=${encodeURIComponent($('#monitor-state').value)}&hours=${$('#monitor-hours').value}`);
        const s=data.summary;
        $('#monitor-stats').innerHTML=[['TOTAL',s.total,'reportes en el periodo',''],['PUBLICADOS',s.ok,'ERP y Telegram',''],['EN PROCESO',s.pending,s.stuck?`${s.stuck} atorado(s)`:'sin atorados',s.stuck?'warn':''],['POR VERIFICAR',s.review,'resultado ambiguo',s.review?'warn':''],['CON ERROR',s.failed,'requieren acción',s.failed?'bad':'']]
          .map(([a,b,c,k])=>`<div class="monitor-stat ${k}"><small>${a}</small><strong>${b}</strong><span>${c}</span></div>`).join('');
        $('#monitor-table').innerHTML=data.transactions.length?`<div class="admin-table"><div class="monitor-row admin-head"><span>FECHA</span><span>USUARIO</span><span>PROYECTO</span><span>ERP</span><span>TELEGRAM</span><span>DETALLE</span><span></span></div>${data.transactions.map(t=>`<div class="monitor-row"><span>${when(t.created)}</span><span>${esc(t.user)}</span><span>${esc(t.project)}<small>${t.photos?t.photos+' foto(s)':'sin fotos'}</small></span><span>${pill(t.erp)}</span><span>${pill(t.telegram)}${t.stuck?' <span class="status amber">Atorado</span>':''}</span><span class="mono">${esc(t.error||'')}${t.erpLogId?`<small>ERP: ${esc(t.erpLogId)}</small>`:''}<small>Ref: ${esc(t.id.slice(0,8))}</small></span><span>${t.state==='telegram_failed'?`<button class="btn small" data-retry="${esc(t.id)}">Reintentar</button>`:''}</span></div>`).join('')}</div>`:'<div class="empty"><h3>Sin transacciones</h3><p>No hay reportes que coincidan con el filtro.</p></div>';
        $('#monitor-updated').textContent='Actualizado '+new Date().toLocaleTimeString('es-MX');
        $('#monitor-error').textContent='';
        document.querySelectorAll('#monitor-table [data-retry]').forEach(b=>b.onclick=async()=>{try{await api('/api/admin/monitor/retry',{id:b.dataset.retry});toast('Envío puesto en cola.');await load();}catch(e){toast(e.message);}});
      }catch(e){$('#monitor-error').textContent=e.message;}
    };
    $('#monitor-state').onchange=load;$('#monitor-hours').onchange=load;$('#monitor-refresh').onclick=load;
    await load();
    const timer=setInterval(()=>{if(!$('#monitor-root'))return clearInterval(timer);if(!document.hidden)load();},30000);
  }
};

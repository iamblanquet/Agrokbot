'use strict';

// Pantalla administrativa: el catálogo visible se obtiene siempre del ERP.
// El PIN es el único dato que el administrador captura manualmente.
window.campoAdmin = {
  async render(){
    const { $, esc, heading, api, toast } = window.campoUi;
    $('#main').innerHTML =
      heading('Administración', 'Usuarios de campo, permisos operativos, conexión ERP y avisos push.') +
      `<div class="admin-dashboard">
        <section class="admin-stats" aria-label="Indicadores de administración">
          <div class="admin-stat stat-total">
            <small>USUARIOS TOTALES</small>
            <strong id="admin-total">0</strong>
            <span>Registrados en sistema</span>
          </div>
          <div class="admin-stat stat-active">
            <small>USUARIOS ACTIVOS</small>
            <strong id="admin-active">0</strong>
            <span>Con acceso habilitado</span>
          </div>
          <div class="admin-stat stat-available">
            <small>EMPLEADOS DISPONIBLES</small>
            <strong id="admin-available">0</strong>
            <span>Sincronizados desde ERP</span>
          </div>
          <div class="admin-stat stat-assigned">
            <small>ASIGNACIONES ERP</small>
            <strong id="admin-assigned">0</strong>
            <span>Cuentas vinculadas</span>
          </div>
        </section>

        <!-- Gestión de Usuarios de Campo -->
        <section class="admin-panel admin-users-section">
          <div class="admin-card-header">
            <div class="admin-card-title-group">
              <span class="admin-card-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></span>
              <div>
                <h3>Usuarios de campo y asignaciones ERP</h3>
                <p class="muted">Asigna un PIN numérico de 4 a 8 dígitos a cada responsable dado de alta en el ERP.</p>
              </div>
            </div>
          </div>

          <div class="admin-user-editor-box">
            <form id="admin-user-form" class="admin-form">
              <div>
                <label for="admin-assignment">Empleado ERP</label>
                <select id="admin-assignment" required><option value="">Cargando empleados de la API…</option></select>
              </div>
              <div>
                <label for="admin-pin">PIN de acceso</label>
                <input id="admin-pin" required inputmode="numeric" pattern="[0-9]{4,8}" placeholder="4 a 8 dígitos">
              </div>
              <div class="admin-form-actions">
                <button id="admin-submit" class="btn primary" type="submit"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>Guardar usuario</button>
                <button id="admin-cancel-edit" class="btn" type="button" hidden>Cancelar edición</button>
              </div>
            </form>
            <p id="admin-selected" class="admin-selected-hint muted"></p>
            <p id="admin-error" class="error"></p>
          </div>

          <div class="admin-toolbar">
            <div class="admin-search-wrap">
              <svg class="admin-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input id="admin-search" type="search" placeholder="Buscar por usuario, nombre o número de empleado…">
            </div>
            <select id="admin-status" aria-label="Filtrar por estado">
              <option value="all">Todos los estados</option>
              <option value="active">Activos</option>
              <option value="inactive">Inactivos</option>
            </select>
          </div>

          <div id="admin-users">Cargando usuarios…</div>
        </section>

        <!-- Cuadrícula de Herramientas Operativas, Permisos y Configuración -->
        <div class="admin-tools-grid">
          <!-- Conexión ERP -->
          <section class="admin-panel admin-tool-card">
            <div class="admin-card-header">
              <div class="admin-card-title-group">
                <span class="admin-card-icon icon-gold"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg></span>
                <div>
                  <h3>Conexión ERP</h3>
                  <p class="muted">Solo administradores pueden actualizar esta credencial. Nunca se muestra completa.</p>
                </div>
              </div>
              <span id="erp-key-status" class="admin-status-pill">Comprobando configuración…</span>
            </div>
            <form id="erp-key-form" class="admin-inline-form">
              <div class="admin-inline-field">
                <label for="erp-api-key">API key del ERP</label>
                <input id="erp-api-key" type="password" autocomplete="new-password" placeholder="pc_ext_…">
              </div>
              <button class="btn primary" type="submit">Guardar API key</button>
            </form>
          </section>

          <!-- Permiso de seguimiento de incidencias -->
          <section class="admin-panel admin-tool-card">
            <div class="admin-card-header">
              <div class="admin-card-title-group">
                <span class="admin-card-icon icon-amber"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg></span>
                <div>
                  <h3>Permiso de seguimiento de incidencias</h3>
                  <p class="muted">Permite consultar todas las incidencias, comentar, resolver y reabrir sin ser administrador.</p>
                </div>
              </div>
            </div>
            <div class="admin-permission-controls">
              <div class="admin-inline-field">
                <label for="incident-permission-user">Usuario de campo</label>
                <select id="incident-permission-user" aria-label="Usuario"></select>
              </div>
              <div class="admin-permission-row">
                <label class="admin-check-tile" for="incident-permission-enabled">
                  <input type="checkbox" id="incident-permission-enabled">
                  <span>Gestionar incidencias</span>
                </label>
                <button type="button" class="btn primary" id="incident-permission-save">Guardar permiso</button>
              </div>
              <p id="incident-permission-result" class="admin-feedback-note" role="status"></p>
            </div>
          </section>

          <!-- Vista previa de reportes faltantes -->
          <section class="admin-panel admin-tool-card">
            <div class="admin-card-header">
              <div class="admin-card-title-group">
                <span class="admin-card-icon icon-blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></span>
                <div>
                  <h3>Vista previa de reportes faltantes</h3>
                  <p class="muted">Consulta actual del ERP, no el corte definitivo de las 21:00. La prueba envía push solo a responsables con tareas faltantes; no publica en Telegram ni modifica el corte nocturno.</p>
                </div>
              </div>
            </div>
            <div class="admin-btn-group">
              <button id="reminders-preview" class="btn" type="button">Consultar faltantes y destinatarios</button>
              <button id="reminders-test" class="btn primary" type="button" disabled>Enviar prueba a responsables</button>
            </div>
            <div id="reminders-result" class="admin-preview-result" role="status" aria-live="polite"></div>
          </section>

          <!-- Prueba de notificaciones -->
          <section class="admin-panel admin-tool-card">
            <div class="admin-card-header">
              <div class="admin-card-title-group">
                <span class="admin-card-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg></span>
                <div>
                  <h3>Prueba de notificaciones</h3>
                  <p class="muted">Envía una prueba a todos los dispositivos registrados de usuarios activos. Este navegador no necesita tener los avisos activados. No modifica reportes ni publica en Telegram.</p>
                </div>
              </div>
            </div>
            <div class="admin-btn-group">
              <button id="admin-test-push" class="btn primary" type="button">Enviar prueba a todos los dispositivos</button>
            </div>
            <p id="admin-test-push-status" class="admin-feedback-note muted" role="status" aria-live="polite"></p>
          </section>
        </div>

        <!-- Bitácora Administrativa -->
        <section class="admin-panel admin-audit-section">
          <div class="admin-card-header">
            <div class="admin-card-title-group">
              <span class="admin-card-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg></span>
              <div>
                <h3>Bitácora administrativa</h3>
                <p class="muted">Historial auditable de movimientos de usuarios, reportes y sincronización.</p>
              </div>
            </div>
            <button id="admin-export-audit" class="btn small" type="button">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>Exportar bitácora
            </button>
          </div>
          <div class="admin-toolbar">
            <div class="admin-search-wrap">
              <svg class="admin-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input id="admin-audit-search" type="search" placeholder="Filtrar bitácora por actor, referencia o detalle…">
            </div>
            <select id="admin-audit-action" aria-label="Filtrar por tipo de acción">
              <option value="all">Todas las acciones</option>
              <option value="user_upsert">Alta / actualización</option>
              <option value="user_update">Edición / reasignación</option>
              <option value="user_toggle">Cambio de estado usuario</option>
              <option value="user_delete">Eliminación lógica</option>
              <option value="report_created">Reporte capturado</option>
              <option value="photo_uploaded">Fotografía cargada</option>
              <option value="report_state_changed">Cambio de estado reporte</option>
              <option value="monitor_retry_telegram">Reintento Telegram</option>
            </select>
          </div>
          <div id="admin-audit">Cargando bitácora…</div>
        </section>
      </div>`;

    $('#admin-test-push').onclick=async()=>{
      const button=$('#admin-test-push'), status=$('#admin-test-push-status');
      button.disabled=true;status.textContent='Comprobando suscripción…';
      try{
        status.textContent='Enviando prueba…';
        const result=await api('/api/admin/notifications/test',{});
        status.textContent=result.message;
      }catch(error){status.textContent=error.message;}
      finally{button.disabled=false;}
    };
    let editingUser='';
    let permissionUsers=[];
    let userPage=1, auditPage=1;
    const USER_PAGE_SIZE=8, AUDIT_PAGE_SIZE=10;

    $('#incident-permission-user').onchange=()=>{$('#incident-permission-enabled').checked=Boolean(permissionUsers.find(u=>u.username===$('#incident-permission-user').value)?.canManageIncidents);};
    $('#incident-permission-save').onclick=async()=>{
      const button=$('#incident-permission-save');button.disabled=true;
      try{await api('/api/admin/incidents/permission',{user:$('#incident-permission-user').value,enabled:$('#incident-permission-enabled').checked});$('#incident-permission-result').textContent='Permiso guardado. El usuario lo verá al sincronizar.';await load();}
      catch(e){$('#incident-permission-result').textContent=e.message;}finally{button.disabled=false;}
    };
    const previewButton=$('#reminders-preview'),testButton=$('#reminders-test'),resultPanel=$('#reminders-result');
    const showPreview=data=>{
      resultPanel.innerHTML=`<div class="admin-preview-box"><p class="admin-preview-summary"><strong>${esc(data.day)}</strong> · ${data.tasks.length} tareas sin reporte · ${data.devices} dispositivos destinatarios · ${data.unscheduled} tareas sin fechas válidas.</p>${data.tasks.length?`<ul class="admin-preview-list">${data.tasks.map(t=>`<li><strong>${esc(t.project)}</strong> · ${esc(t.task)} <span class="muted">(${esc(t.responsible)})</span></li>`).join('')}</ul>`:''}<p class="admin-preview-recipients"><strong>Destinatarios:</strong> ${data.recipients.map(r=>`${esc(r.user)} (${r.tasks} tareas)`).join(', ')||'Sin dispositivos elegibles'}</p></div>`;
    };
    previewButton.onclick=async()=>{
      previewButton.disabled=true;testButton.disabled=true;resultPanel.textContent='Consultando ERP…';
      try{const data=await api('/api/admin/reminders/preview',{});showPreview(data);testButton.disabled=!data.devices;}
      catch(error){resultPanel.textContent=error.message;}
      finally{previewButton.disabled=false;}
    };
    testButton.onclick=async()=>{
      if(!confirm('¿Enviar una notificación marcada como PRUEBA a los responsables elegibles? Se consultará nuevamente el ERP.'))return;
      testButton.disabled=true;previewButton.disabled=true;
      try{const data=await api('/api/admin/reminders/test',{});showPreview(data);resultPanel.insertAdjacentHTML('beforeend',`<p class="admin-feedback-note">Prueba: ${data.sent} aceptadas por el proveedor; ${data.failed} fallidas. No confirma recepción en pantalla.</p>`);}
      catch(error){resultPanel.textContent=error.message;}
      finally{previewButton.disabled=false;}
    };
    const resetEditor=()=>{editingUser='';$('#admin-user-form').reset();$('#admin-submit').innerHTML='<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>Guardar usuario';$('#admin-cancel-edit').hidden=true;$('#admin-selected').textContent='';$('#admin-error').textContent='';};
    $('#admin-cancel-edit').onclick=resetEditor;
    $('#erp-key-form').onsubmit=async e=>{e.preventDefault();const key=$('#erp-api-key').value.trim();if(!key)return;try{const result=await api('/api/admin/integration/erp-key',{apiKey:key});$('#erp-api-key').value='';$('#erp-key-status').textContent=`Configurada: ${result.masked}`;toast('API key ERP actualizada.');await load();}catch(error){$('#erp-key-status').textContent=error.message;}};
    $('#admin-export-audit').onclick=()=>{const rows=auditEntries||[];const blob=new Blob([JSON.stringify({exportedAt:new Date().toISOString(),entries:rows},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`agrokool-bitacora-${new Date().toISOString().slice(0,10)}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Bitácora exportada.');};
    let auditEntries=[];

    const load=async()=>{
      try{
        const [people,data,audit,keyStatus]=await Promise.all([api('/api/admin/responsibles').catch(()=>({responsibles:[]})),api('/api/admin/users'),api('/api/admin/audit'),api('/api/admin/integration/erp-key')]);
        $('#erp-key-status').textContent=keyStatus.configured?`Configurada: ${resultMask(keyStatus)}`:'No configurada';
        $('#erp-key-status').className=`admin-status-pill ${keyStatus.configured?'ok':'warn'}`;
        auditEntries=audit.entries||[];
        permissionUsers=data.users;
        $('#incident-permission-user').innerHTML=data.users.map(u=>`<option value="${esc(u.username)}">${esc(u.responsible_name)} (${esc(u.username)})</option>`).join('');
        $('#incident-permission-user').onchange();
        $('#admin-assignment').innerHTML='<option value="">Selecciona un empleado</option>'+people.responsibles.map(p=>`<option value="${esc(p.assignmentId)}">${esc(p.name)} · ${esc(p.employeeNumber)}</option>`).join('');
        $('#admin-available').textContent=people.responsibles.length;
        $('#admin-assignment').onchange=()=>{const p=people.responsibles.find(x=>x.assignmentId===$('#admin-assignment').value);$('#admin-selected').textContent=p?`Usuario generado: ${p.employeeNumber.toLowerCase()} · Asignación: ${p.assignmentId}`:'';};
        const labels={user_upsert:'Alta / actualización',user_update:'Edición / reasignación',user_toggle:'Cambio de estado',user_delete:'Eliminación lógica',report_created:'Reporte capturado',photo_uploaded:'Fotografía cargada',report_state_changed:'Cambio de estado',monitor_retry_telegram:'Reintento Telegram'};
        const detail=item=>{let d={};try{d=JSON.parse(item.details||'{}');}catch{}const transition=d.from&&d.to?` · ${d.from} -> ${d.to}`:'';const error=d.error?` · ${d.error}`:'';const origin=d.origin?` · Origen: ${d.origin}`:'';return `${transition}${origin}${error}`;};

        const drawUsers=()=>{
          const q=($('#admin-search')?.value||'').toLowerCase(),status=$('#admin-status')?.value||'all';
          const rows=data.users.filter(u=>(status==='all'||(status==='active'?u.active:!u.active))&&(`${u.username} ${u.responsible_name} ${u.employee_number}`).toLowerCase().includes(q));
          $('#admin-total').textContent=data.users.length;
          $('#admin-active').textContent=data.users.filter(u=>u.active).length;
          $('#admin-assigned').textContent=data.users.filter(u=>u.assignment_id).length;

          const totalPages=Math.max(1,Math.ceil(rows.length/USER_PAGE_SIZE));
          userPage=Math.min(Math.max(1,userPage),totalPages);
          const start=(userPage-1)*USER_PAGE_SIZE;
          const pageRows=rows.slice(start,start+USER_PAGE_SIZE);

          $('#admin-users').innerHTML=`<div class="admin-table"><div class="admin-row admin-head"><span>USUARIO</span><span>EMPLEADO</span><span>NÚMERO</span><span>ASIGNACIÓN ERP</span><span>ESTADO</span><span>ACCIONES</span></div>${pageRows.map(u=>`<div class="admin-row"><span><strong class="admin-user-chip">${esc(u.username)}</strong></span><span>${esc(u.responsible_name)}</span><span>${esc(u.employee_number)}</span><span class="mono">${esc(u.assignment_id)}</span><span><em class="admin-badge ${u.active?'ok':'off'}">${u.active?'Activo':'Inactivo'}</em></span><span class="admin-row-actions"><button class="btn small" data-edit-user="${esc(u.username)}">Editar PIN</button> <button class="btn small" data-toggle-user="${esc(u.username)}">${u.active?'Desactivar':'Activar'}</button> <button class="btn small danger" data-delete-user="${esc(u.username)}">Eliminar</button></span></div>`).join('')||'<p class="admin-empty-row muted">No hay usuarios que coincidan.</p>'}</div>
          <div class="table-caption table-pagination-bar">
            <span>${rows.length?`Mostrando ${start+1}–${Math.min(rows.length,start+pageRows.length)} de ${rows.length} usuario(s) · Página ${userPage} de ${totalPages}`:'0 usuarios · Página 1 de 1'}</span>
            <div class="pagination-btns">
              <button type="button" class="btn subtle small" id="admin-users-prev" ${userPage<=1?'disabled':''}>&lt; Anterior</button>
              <button type="button" class="btn subtle small" id="admin-users-next" ${userPage>=totalPages?'disabled':''}>Siguiente &gt;</button>
            </div>
          </div>`;

          if($('#admin-users-prev'))$('#admin-users-prev').onclick=()=>{if(userPage>1){userPage--;drawUsers();}};
          if($('#admin-users-next'))$('#admin-users-next').onclick=()=>{if(userPage<totalPages){userPage++;drawUsers();}};
          document.querySelectorAll('[data-edit-user]').forEach(b=>b.onclick=()=>{const u=data.users.find(item=>item.username===b.dataset.editUser);if(!u)return;editingUser=u.username;$('#admin-assignment').value=u.assignment_id;$('#admin-pin').value='';$('#admin-submit').textContent='Actualizar PIN';$('#admin-cancel-edit').hidden=false;$('#admin-selected').textContent=`Editando ${u.username}. Captura el nuevo PIN.`;$('#admin-error').textContent='';$('#admin-pin').focus();});
          document.querySelectorAll('[data-toggle-user]').forEach(b=>b.onclick=async()=>{await api('/api/admin/users/toggle',{username:b.dataset.toggleUser});await load();});
          document.querySelectorAll('[data-delete-user]').forEach(b=>b.onclick=async()=>{if(confirm(`¿Eliminar ${b.dataset.deleteUser}?`)){await api('/api/admin/users/delete',{username:b.dataset.deleteUser});await load();}});
        };

        const drawAudit=()=>{
          const q=($('#admin-audit-search')?.value||'').toLowerCase();
          const act=($('#admin-audit-action')?.value||'all');
          const filtered=(audit.entries||[]).filter(item=>{
            if(act!=='all'&&item.action!==act)return false;
            if(q){
              const text=`${item.created||''} ${labels[item.action]||item.action||''} ${item.target||''} ${item.actor||''} ${detail(item)}`.toLowerCase();
              if(!text.includes(q))return false;
            }
            return true;
          });

          const totalPages=Math.max(1,Math.ceil(filtered.length/AUDIT_PAGE_SIZE));
          auditPage=Math.min(Math.max(1,auditPage),totalPages);
          const start=(auditPage-1)*AUDIT_PAGE_SIZE;
          const pageRows=filtered.slice(start,start+AUDIT_PAGE_SIZE);

          $('#admin-audit').innerHTML=`<div class="admin-table"><div class="admin-row admin-audit-row admin-head"><span>FECHA</span><span>ACCIÓN</span><span>REFERENCIA</span><span>ACTOR</span><span>DETALLE</span></div>${pageRows.map(item=>`<div class="admin-row admin-audit-row"><span>${esc(item.created)}</span><span><strong>${esc(labels[item.action]||item.action)}</strong></span><span class="mono">${esc(item.target)}</span><span>${esc(item.actor)}</span><span>${esc(detail(item))}</span></div>`).join('')||'<p class="admin-empty-row muted">Sin movimientos registrados.</p>'}</div>
          <div class="table-caption table-pagination-bar">
            <span>${filtered.length?`Mostrando ${start+1}–${Math.min(filtered.length,start+pageRows.length)} de ${filtered.length} movimiento(s) · Página ${auditPage} de ${totalPages}`:'0 movimientos · Página 1 de 1'}</span>
            <div class="pagination-btns">
              <button type="button" class="btn subtle small" id="admin-audit-prev" ${auditPage<=1?'disabled':''}>&lt; Anterior</button>
              <button type="button" class="btn subtle small" id="admin-audit-next" ${auditPage>=totalPages?'disabled':''}>Siguiente &gt;</button>
            </div>
          </div>`;

          if($('#admin-audit-prev'))$('#admin-audit-prev').onclick=()=>{if(auditPage>1){auditPage--;drawAudit();}};
          if($('#admin-audit-next'))$('#admin-audit-next').onclick=()=>{if(auditPage<totalPages){auditPage++;drawAudit();}};
        };

        drawUsers();
        drawAudit();
        $('#admin-search').oninput=()=>{userPage=1;drawUsers();};
        $('#admin-status').onchange=()=>{userPage=1;drawUsers();};
        if($('#admin-audit-search'))$('#admin-audit-search').oninput=()=>{auditPage=1;drawAudit();};
        if($('#admin-audit-action'))$('#admin-audit-action').onchange=()=>{auditPage=1;drawAudit();};
      }catch(e){$('#admin-error').textContent=e.message;}
    };
    function resultMask(k){return k.masked||'';}
    $('#admin-user-form').onsubmit=async e=>{e.preventDefault();try{const body={assignmentId:$('#admin-assignment').value,pin:$('#admin-pin').value.trim()};if(editingUser)body.username=editingUser;await api('/api/admin/users',body);const message=editingUser?'Usuario actualizado.':'Usuario creado y asignado.';resetEditor();await load();toast(message);}catch(error){$('#admin-error').textContent=error.message;}};
    await load();
  }
};

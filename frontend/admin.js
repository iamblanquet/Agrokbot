'use strict';

// Pantalla administrativa: el catálogo visible se obtiene siempre del ERP.
// El PIN es el único dato que el administrador captura manualmente.
window.campoAdmin = {
  async render(){
    const { $, esc, heading, api, toast } = window.campoUi;
    $('#main').innerHTML=heading('Administración','Usuarios de campo y asignaciones ERP.')+`<section class="admin-stats"><div class="admin-stat"><small>USUARIOS TOTALES</small><strong id="admin-total">0</strong><span>Registrados</span></div><div class="admin-stat"><small>USUARIOS ACTIVOS</small><strong id="admin-active">0</strong><span>Con acceso</span></div><div class="admin-stat"><small>EMPLEADOS DISPONIBLES</small><strong id="admin-available">0</strong><span>Desde la API</span></div><div class="admin-stat"><small>ASIGNACIONES</small><strong id="admin-assigned">0</strong><span>Relacionadas</span></div></section><section class="admin-panel"><h3>Conexión ERP</h3><p class="muted">Solo administradores pueden actualizar esta credencial. Nunca se muestra completa.</p><form id="erp-key-form" class="admin-form"><div><label for="erp-api-key">API key del ERP</label><input id="erp-api-key" type="password" autocomplete="new-password" placeholder="pc_ext_…"></div><button class="btn primary" type="submit">Guardar API key</button></form><p id="erp-key-status" class="muted">Comprobando configuración…</p><hr><form id="admin-user-form" class="admin-form"><div><label>Empleado ERP</label><select id="admin-assignment" required><option value="">Cargando empleados de la API…</option></select></div><div><label>PIN de acceso</label><input id="admin-pin" required inputmode="numeric" pattern="[0-9]{4,8}" placeholder="4 a 8 dígitos"></div><button id="admin-submit" class="btn primary" type="submit"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>Guardar usuario</button><button id="admin-cancel-edit" class="btn" type="button" hidden>Cancelar edición</button></form><p id="admin-selected" class="muted"></p><p id="admin-error" class="error"></p><div class="admin-toolbar"><input id="admin-search" type="search" placeholder="Buscar usuario o empleado…"><select id="admin-status"><option value="all">Todos los estados</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select></div><div id="admin-users">Cargando usuarios…</div><hr><div class="section-heading"><h3>Bitácora administrativa</h3><button id="admin-export-audit" class="btn small" type="button">Exportar bitácora</button></div><div id="admin-audit">Cargando bitácora…</div></section>`;

    $('#main').insertAdjacentHTML('afterbegin', `<section class="admin-panel"><h3>Prueba de notificaciones</h3><p class="muted">Envía una prueba a todos los dispositivos registrados de usuarios activos. Este navegador no necesita tener los avisos activados. No modifica reportes ni publica en Telegram.</p><button id="admin-test-push" class="btn primary" type="button">Enviar prueba a todos los dispositivos</button><p id="admin-test-push-status" class="muted" role="status" aria-live="polite"></p></section>`);
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
    $('#main').insertAdjacentHTML('afterbegin',`<section class="admin-panel"><h3>Permiso de seguimiento de incidencias</h3><p>Permite consultar todas las incidencias, comentar, resolver y reabrir sin ser administrador.</p><select id="incident-permission-user" aria-label="Usuario"></select><label><input type="checkbox" id="incident-permission-enabled"> Gestionar incidencias</label><button type="button" class="btn" id="incident-permission-save">Guardar permiso</button><p id="incident-permission-result" role="status"></p></section>`);
    let permissionUsers=[];
    $('#incident-permission-user').onchange=()=>{$('#incident-permission-enabled').checked=Boolean(permissionUsers.find(u=>u.username===$('#incident-permission-user').value)?.canManageIncidents);};
    $('#incident-permission-save').onclick=async()=>{
      const button=$('#incident-permission-save');button.disabled=true;
      try{await api('/api/admin/incidents/permission',{user:$('#incident-permission-user').value,enabled:$('#incident-permission-enabled').checked});$('#incident-permission-result').textContent='Permiso guardado. El usuario lo verá al sincronizar.';await load();}
      catch(e){$('#incident-permission-result').textContent=e.message;}finally{button.disabled=false;}
    };
    $('#main').insertAdjacentHTML('afterbegin', `<section class="admin-panel"><h3>Vista previa de reportes faltantes</h3><p>Consulta actual del ERP, no el corte definitivo de las 21:00. La prueba envía push solo a responsables con tareas faltantes; no publica en Telegram ni modifica el corte nocturno.</p><button id="reminders-preview" class="btn" type="button">Consultar faltantes y destinatarios</button> <button id="reminders-test" class="btn" type="button" disabled>Enviar prueba a responsables</button><div id="reminders-result" role="status" aria-live="polite"></div></section>`);
    const previewButton=$('#reminders-preview'),testButton=$('#reminders-test'),resultPanel=$('#reminders-result');
    const showPreview=data=>{
      resultPanel.innerHTML=`<p>${esc(data.day)} · ${data.tasks.length} tareas sin reporte · ${data.devices} dispositivos destinatarios · ${data.unscheduled} tareas sin fechas válidas.</p><ul>${data.tasks.map(t=>`<li>${esc(t.project)} · ${esc(t.task)} · ${esc(t.responsible)}</li>`).join('')}</ul><p>Destinatarios: ${data.recipients.map(r=>`${esc(r.user)} (${r.tasks} tareas)`).join(', ')||'Sin dispositivos elegibles'}</p>`;
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
      try{const data=await api('/api/admin/reminders/test',{});showPreview(data);resultPanel.insertAdjacentHTML('beforeend',`<p>Prueba: ${data.sent} aceptadas por el proveedor; ${data.failed} fallidas. No confirma recepción en pantalla.</p>`);}
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
        $('#erp-key-status').textContent=keyStatus.configured?`Configurada: ${keyStatus.masked}`:'No configurada';
        auditEntries=audit.entries||[];
        permissionUsers=data.users;
        $('#incident-permission-user').innerHTML=data.users.map(u=>`<option value="${esc(u.username)}">${esc(u.responsible_name)} (${esc(u.username)})</option>`).join('');
        $('#incident-permission-user').onchange();
        $('#admin-assignment').innerHTML='<option value="">Selecciona un empleado</option>'+people.responsibles.map(p=>`<option value="${esc(p.assignmentId)}">${esc(p.name)} · ${esc(p.employeeNumber)}</option>`).join('');
        $('#admin-available').textContent=people.responsibles.length;
        $('#admin-assignment').onchange=()=>{const p=people.responsibles.find(x=>x.assignmentId===$('#admin-assignment').value);$('#admin-selected').textContent=p?`Usuario generado: ${p.employeeNumber.toLowerCase()} · Asignación: ${p.assignmentId}`:'';};
        const draw=()=>{
          const q=($('#admin-search')?.value||'').toLowerCase(),status=$('#admin-status')?.value||'all';
          const rows=data.users.filter(u=>(status==='all'||(status==='active'?u.active:!u.active))&&(`${u.username} ${u.responsible_name} ${u.employee_number}`).toLowerCase().includes(q));
          $('#admin-total').textContent=data.users.length;
          $('#admin-active').textContent=data.users.filter(u=>u.active).length;
          $('#admin-assigned').textContent=data.users.filter(u=>u.assignment_id).length;
          $('#admin-users').innerHTML=`<div class="admin-table"><div class="admin-row admin-head"><span>USUARIO</span><span>EMPLEADO</span><span>NÚMERO</span><span>ASIGNACIÓN ERP</span><span>ESTADO</span><span>ACCIONES</span></div>${rows.map(u=>`<div class="admin-row"><span><strong>${esc(u.username)}</strong></span><span>${esc(u.responsible_name)}</span><span>${esc(u.employee_number)}</span><span class="mono">${esc(u.assignment_id)}</span><span><em class="admin-badge ${u.active?'ok':'off'}">${u.active?'Activo':'Inactivo'}</em></span><span><button class="btn small" data-edit-user="${esc(u.username)}">Editar PIN</button> <button class="btn small" data-toggle-user="${esc(u.username)}">${u.active?'Desactivar':'Activar'}</button> <button class="btn small danger" data-delete-user="${esc(u.username)}">Eliminar</button></span></div>`).join('')||'<p class="muted">No hay usuarios que coincidan.</p>'}</div>`;
          document.querySelectorAll('[data-edit-user]').forEach(b=>b.onclick=()=>{const u=data.users.find(item=>item.username===b.dataset.editUser);if(!u)return;editingUser=u.username;$('#admin-assignment').value=u.assignment_id;$('#admin-pin').value='';$('#admin-submit').textContent='Actualizar PIN';$('#admin-cancel-edit').hidden=false;$('#admin-selected').textContent=`Editando ${u.username}. Captura el nuevo PIN.`;$('#admin-error').textContent='';$('#admin-pin').focus();});
          document.querySelectorAll('[data-toggle-user]').forEach(b=>b.onclick=async()=>{await api('/api/admin/users/toggle',{username:b.dataset.toggleUser});await load();});
          document.querySelectorAll('[data-delete-user]').forEach(b=>b.onclick=async()=>{if(confirm(`¿Eliminar ${b.dataset.deleteUser}?`)){await api('/api/admin/users/delete',{username:b.dataset.deleteUser});await load();}});
          const labels={user_upsert:'Alta / actualización',user_update:'Edición / reasignación',user_toggle:'Cambio de estado',user_delete:'Eliminación lógica',report_created:'Reporte capturado',photo_uploaded:'Fotografía cargada',report_state_changed:'Cambio de estado',monitor_retry_telegram:'Reintento Telegram'};
          const detail=item=>{let data={};try{data=JSON.parse(item.details||'{}');}catch{}const transition=data.from&&data.to?` · ${data.from} -> ${data.to}`:'';const error=data.error?` · ${data.error}`:'';const origin=data.origin?` · Origen: ${data.origin}`:'';return `${transition}${origin}${error}`;};
          $('#admin-audit').innerHTML=`<div class="admin-table"><div class="admin-row admin-head"><span>FECHA</span><span>ACCIÓN</span><span>REFERENCIA</span><span>ACTOR</span><span>DETALLE</span></div>${audit.entries.map(item=>`<div class="admin-row"><span>${esc(item.created)}</span><span>${esc(labels[item.action]||item.action)}</span><span class="mono">${esc(item.target)}</span><span>${esc(item.actor)}</span><span>${esc(detail(item))}</span></div>`).join('')||'<p class="muted">Sin movimientos registrados.</p>'}</div>`;
        };
        draw();
        $('#admin-search').oninput=draw;
        $('#admin-status').onchange=draw;
      }catch(e){$('#admin-error').textContent=e.message;}
    };
    $('#admin-user-form').onsubmit=async e=>{e.preventDefault();try{const body={assignmentId:$('#admin-assignment').value,pin:$('#admin-pin').value.trim()};if(editingUser)body.username=editingUser;await api('/api/admin/users',body);const message=editingUser?'Usuario actualizado.':'Usuario creado y asignado.';resetEditor();await load();toast(message);}catch(error){$('#admin-error').textContent=error.message;}};
    await load();
  }
};

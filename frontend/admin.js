'use strict';

// Pantalla administrativa: el catálogo visible se obtiene siempre del ERP.
// El PIN es el único dato que el administrador captura manualmente.
window.campoAdmin = {
  async render(){
    const { $, esc, heading, api, toast } = window.campoUi;
    $('#main').innerHTML=heading('Administración','Usuarios de campo y asignaciones ERP.')+`<section class="admin-stats"><div class="admin-stat"><small>USUARIOS TOTALES</small><strong id="admin-total">0</strong><span>Registrados</span></div><div class="admin-stat"><small>USUARIOS ACTIVOS</small><strong id="admin-active">0</strong><span>Con acceso</span></div><div class="admin-stat"><small>EMPLEADOS DISPONIBLES</small><strong id="admin-available">0</strong><span>Desde la API</span></div><div class="admin-stat"><small>ASIGNACIONES</small><strong id="admin-assigned">0</strong><span>Relacionadas</span></div></section><section class="admin-panel"><form id="admin-user-form" class="admin-form"><div><label>Empleado ERP</label><select id="admin-assignment" required><option value="">Cargando empleados de la API…</option></select></div><div><label>PIN de acceso</label><input id="admin-pin" required inputmode="numeric" pattern="[0-9]{4,8}" placeholder="4 a 8 dígitos"></div><button id="admin-submit" class="btn primary" type="submit">＋ Guardar usuario</button><button id="admin-cancel-edit" class="btn" type="button" hidden>Cancelar edición</button></form><p id="admin-selected" class="muted"></p><p id="admin-error" class="error"></p><div class="admin-toolbar"><input id="admin-search" type="search" placeholder="Buscar usuario o empleado…"><select id="admin-status"><option value="all">Todos los estados</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select></div><div id="admin-users">Cargando usuarios…</div><hr><h3>Bitácora administrativa</h3><div id="admin-audit">Cargando bitácora…</div></section>`;

    let editingUser='';
    const resetEditor=()=>{editingUser='';$('#admin-user-form').reset();$('#admin-submit').textContent='＋ Guardar usuario';$('#admin-cancel-edit').hidden=true;$('#admin-selected').textContent='';$('#admin-error').textContent='';};
    $('#admin-cancel-edit').onclick=resetEditor;

    const load=async()=>{
      try{
        const [people,data,audit]=await Promise.all([api('/api/admin/responsibles'),api('/api/admin/users'),api('/api/admin/audit')]);
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
          const labels={user_upsert:'Alta / actualización',user_update:'Edición / reasignación',user_toggle:'Cambio de estado',user_delete:'Eliminación lógica'};
          $('#admin-audit').innerHTML=`<div class="admin-table"><div class="admin-row admin-head"><span>FECHA</span><span>ACCIÓN</span><span>USUARIO</span><span>ADMINISTRADOR</span></div>${audit.entries.map(item=>`<div class="admin-row"><span>${esc(item.created)}</span><span>${esc(labels[item.action]||item.action)}</span><span class="mono">${esc(item.target)}</span><span>${esc(item.actor)}</span></div>`).join('')||'<p class="muted">Sin movimientos registrados.</p>'}</div>`;
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

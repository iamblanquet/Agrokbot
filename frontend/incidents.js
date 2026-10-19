'use strict';
window.campoIncidents = {
  async render() {
    const { $, esc, heading, api, toast } = window.campoUi;
    $('#main').innerHTML =
      heading('Incidencias', 'Seguimiento vinculado al diario ERP. Requiere conexión.') +
      `<div class="incidents-view">
        <section class="incidents-stats" id="incident-stats" aria-label="Resumen de incidencias">
          <div class="incident-stat-card">
            <small>TOTAL REGISTRADAS</small>
            <strong id="inc-stat-total">0</strong>
            <span>Vinculadas al ERP</span>
          </div>
          <div class="incident-stat-card stat-open">
            <small>ABIERTAS</small>
            <strong id="inc-stat-open">0</strong>
            <span>Requieren atención</span>
          </div>
          <div class="incident-stat-card stat-progress">
            <small>EN ATENCIÓN</small>
            <strong id="inc-stat-progress">0</strong>
            <span>Seguimiento activo</span>
          </div>
          <div class="incident-stat-card stat-resolved">
            <small>RESUELTAS</small>
            <strong id="inc-stat-resolved">0</strong>
            <span>Cerradas en bitácora</span>
          </div>
        </section>

        <section class="incidents-panel">
          <div class="incidents-toolbar">
            <div class="incidents-tabs" role="tablist" aria-label="Filtrar por estado">
              <button type="button" class="inc-tab active" data-status-tab="">Todas</button>
              <button type="button" class="inc-tab" data-status-tab="open">Abiertas</button>
              <button type="button" class="inc-tab" data-status-tab="in_progress">En atención</button>
              <button type="button" class="inc-tab" data-status-tab="resolved">Resueltas</button>
            </div>
            <div class="incidents-filters-row">
              <div class="inc-search-wrap">
                <svg class="inc-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input id="incident-search" type="search" placeholder="Buscar por proyecto, tarea, responsable o descripción…" aria-label="Buscar incidencia">
              </div>
              <div class="inc-select-group">
                <label class="sr-only" for="incident-filter">Estado</label>
                <select id="incident-filter" aria-label="Estado">
                  <option value="">Todos los estados</option>
                  <option value="open">Abierta</option>
                  <option value="in_progress">En atención</option>
                  <option value="resolved">Resuelta</option>
                </select>
                <select id="incident-priority-filter" aria-label="Prioridad">
                  <option value="">Todas las prioridades</option>
                  <option value="critical">Prioridad: Crítica</option>
                  <option value="high">Prioridad: Alta</option>
                  <option value="normal">Prioridad: Normal</option>
                  <option value="low">Prioridad: Baja</option>
                </select>
                <button id="incident-refresh" type="button" class="btn inc-refresh-btn">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                  <span>Actualizar</span>
                </button>
              </div>
            </div>
          </div>

          <p id="incident-error" class="error" role="status"></p>
          <div id="incident-list" class="incident-cards-list">
            <div class="incidents-loading">Cargando incidencias…</div>
          </div>
          <div class="table-caption table-pagination-bar" id="incident-pagination"></div>
        </section>
      </div>`;

    const list = $('#incident-list');
    const paginationEl = $('#incident-pagination');
    const error = $('#incident-error');
    const filter = $('#incident-filter');
    const priorityFilter = $('#incident-priority-filter');
    const searchInput = $('#incident-search');
    const labels = { open: 'Abierta', in_progress: 'En atención', resolved: 'Resuelta' };
    const statusTone = { open: 'red', in_progress: 'amber', resolved: 'green' };
    const priorityLabels = { critical: 'Crítica', high: 'Alta', normal: 'Normal', low: 'Baja' };
    const priorityTone = { critical: 'critical', high: 'high', normal: 'normal', low: 'low' };
    const tgLabels = { sent: ['Enviado a Telegram', 'ok'], pending: ['Envío pendiente', 'pending'], retry: ['Reintento programado', 'warn'], review: ['Verificar envío', 'warn'] };
    const fmtDate = value => {
      if (!value) return '—';
      const d = new Date(value);
      return isNaN(d) ? esc(value) : d.toLocaleString('es-MX', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    let rows = [];
    let page = 1;
    const PAGE_SIZE = 6;

    const updateStats = () => {
      const openCount = rows.filter(r => r.status === 'open').length;
      const progCount = rows.filter(r => r.status === 'in_progress').length;
      const resCount = rows.filter(r => r.status === 'resolved').length;
      if ($('#inc-stat-total')) $('#inc-stat-total').textContent = rows.length;
      if ($('#inc-stat-open')) $('#inc-stat-open').textContent = openCount;
      if ($('#inc-stat-progress')) $('#inc-stat-progress').textContent = progCount;
      if ($('#inc-stat-resolved')) $('#inc-stat-resolved').textContent = resCount;
    };

    const syncTabs = () => {
      document.querySelectorAll('[data-status-tab]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.statusTab === filter.value);
      });
    };

    const draw = () => {
      updateStats();
      syncTabs();
      const q = (searchInput?.value || '').trim().toLowerCase();
      const prio = priorityFilter?.value || '';
      const filtered = rows.filter(r => {
        if (filter.value && r.status !== filter.value) return false;
        if (prio && r.payload?.priority !== prio) return false;
        if (q) {
          const hay = `${r.payload?.task || ''} ${r.payload?.project || ''} ${r.payload?.author || ''} ${r.payload?.description || ''} ${r.id || ''} ${r.erp_log_id || ''}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });

      const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
      page = Math.min(Math.max(1, page), totalPages);
      const start = (page - 1) * PAGE_SIZE;
      const pageRows = filtered.slice(start, start + PAGE_SIZE);

      if (paginationEl) {
        paginationEl.innerHTML = `
          <span>${filtered.length ? `Mostrando ${start + 1}–${Math.min(filtered.length, start + pageRows.length)} de ${filtered.length} incidencia(s) · Página ${page} de ${totalPages}` : '0 incidencias · Página 1 de 1'}</span>
          <div class="pagination-btns">
            <button type="button" class="btn subtle small" id="incident-prev" ${page <= 1 ? 'disabled' : ''}>&lt; Anterior</button>
            <button type="button" class="btn subtle small" id="incident-next" ${page >= totalPages ? 'disabled' : ''}>Siguiente &gt;</button>
          </div>`;
        if ($('#incident-prev')) $('#incident-prev').onclick = () => { if (page > 1) { page--; draw(); } };
        if ($('#incident-next')) $('#incident-next').onclick = () => { if (page < totalPages) { page++; draw(); } };
      }

      if (!filtered.length) {
        const hasFilters = Boolean(filter.value || prio || q);
        list.innerHTML = `<div class="incidents-empty">
          <div class="incidents-empty-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>
          </div>
          <h3>No hay incidencias en este estado.</h3>
          <p>${hasFilters ? 'Prueba cambiando el filtro de estado, prioridad o término de búsqueda.' : 'Las incidencias reportadas desde el diario de campo y confirmadas en el ERP aparecerán aquí para su seguimiento.'}</p>
        </div>`;
        return;
      }

      list.innerHTML = pageRows.map(r => {
        const p = r.payload || {};
        const stTone = statusTone[r.status] || '';
        const prTone = priorityTone[p.priority] || 'normal';
        const prLabel = priorityLabels[p.priority] || p.priority || 'Normal';
        const [tgText, tgClass] = tgLabels[r.telegramState] || [r.telegramState || 'Pendiente', 'pending'];
        return `<article class="incident-card status-border-${esc(r.status)}">
          <header class="incident-card-head">
            <div class="incident-badges">
              <span class="status ${stTone}">${esc(labels[r.status] || r.status)}</span>
              <span class="inc-prio-badge prio-${esc(prTone)}">Prioridad ${esc(prLabel)}</span>
              ${p.stopsWork
                ? '<span class="inc-stop-badge stops"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="10" y1="15" x2="10" y2="9"></line><line x1="14" y1="15" x2="14" y2="9"></line></svg> Detiene actividad</span>'
                : '<span class="inc-stop-badge continues">Actividad continúa</span>'}
            </div>
            <span class="incident-date-pill" title="Fecha de operación">${esc(p.operationDate || '—')}</span>
          </header>

          <div class="incident-card-body">
            <h3 class="incident-task-title">${esc(p.task || 'Tarea sin nombre')}</h3>
            <div class="incident-meta-row">
              <span class="inc-meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                <strong>${esc(p.project || 'Proyecto')}</strong>
              </span>
              <span class="inc-meta-sep">•</span>
              <span class="inc-meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                <span>Reportó: <strong>${esc(p.author || r.user || 'Operador')}</strong></span>
              </span>
            </div>

            <div class="incident-description-box">${esc(p.description || '')}</div>

            <div class="incident-tech-strip">
              <span class="inc-tech-chip">Ref: <code>${esc(r.id.slice(0, 8))}</code></span>
              <span class="inc-tech-chip">Asiento ERP: <code>${esc(r.erp_log_id)}</code></span>
              <span class="inc-tech-chip tg-${esc(tgClass)}">${esc(tgText)}</span>
              ${r.telegramPhotos?.total ? `<span class="inc-tech-chip">Fotos en Incidencias: ${esc(r.telegramPhotos.sent)}/${esc(r.telegramPhotos.total)}</span>` : ''}
            </div>

            <details class="incident-history">
              <summary>
                <span>Historial de seguimiento (${(r.events || []).length})</span>
                <svg class="inc-chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </summary>
              <div class="incident-timeline">
                ${(r.events || []).map(e => `<div class="inc-timeline-item">
                  <div class="inc-timeline-head">
                    <span class="status ${statusTone[e.status] || ''}">${esc(labels[e.status] || e.status)}</span>
                    <strong>${esc(e.actor)}</strong>
                    <time>${fmtDate(e.created)}</time>
                  </div>
                  <p class="inc-timeline-note">${esc(e.note)}</p>
                </div>`).join('')}
              </div>
            </details>
          </div>

          <form class="incident-followup-form" data-incident="${esc(r.id)}">
            <div class="inc-form-grid">
              <div class="inc-form-field inc-field-status">
                <label>Nuevo estado
                  <select name="status">
                    ${Object.entries(labels).map(([v, l]) => `<option value="${v}" ${v === r.status ? 'selected' : ''}>${l}</option>`).join('')}
                  </select>
                </label>
              </div>
              <div class="inc-form-field inc-field-note">
                <label>Comentario de seguimiento
                  <textarea name="note" rows="2" required maxlength="1000" placeholder="Registra acciones tomadas, acuerdos o resolución…"></textarea>
                </label>
              </div>
              <div class="inc-form-actions">
                <button class="btn primary inc-save-btn" type="submit">Guardar seguimiento</button>
              </div>
            </div>
          </form>
        </article>`;
      }).join('');

      list.querySelectorAll('form[data-incident]').forEach(form => {
        form.onsubmit = async event => {
          event.preventDefault();
          const button = form.querySelector('button');
          button.disabled = true;
          error.textContent = '';
          const row = rows.find(r => r.id === form.dataset.incident);
          try {
            await api('/api/incidents/update', {
              id: row.id,
              version: row.version,
              status: form.elements.status.value,
              note: form.elements.note.value
            });
            if (toast) toast('Seguimiento de incidencia actualizado.');
            await load();
          } catch (e) {
            error.textContent = e.message;
            button.disabled = false;
          }
        };
      });
    };

    const load = async () => {
      try {
        let offset = 0, loaded = [];
        do {
          const data = await api('/api/incidents?offset=' + offset);
          loaded.push(...(data.incidents || []));
          offset = data.nextOffset;
        } while (offset != null);
        rows = loaded;
        error.textContent = '';
        draw();
      } catch (e) {
        error.textContent = e.message;
        list.innerHTML = `<div class="incidents-empty">
          <h3>No se pudo consultar el seguimiento.</h3>
          <p>Verifica tu conexión a internet e intenta actualizar nuevamente.</p>
        </div>`;
      }
    };

    document.querySelectorAll('[data-status-tab]').forEach(btn => {
      btn.onclick = () => {
        filter.value = btn.dataset.statusTab;
        page = 1;
        draw();
      };
    });
    filter.onchange = () => { page = 1; draw(); };
    if (priorityFilter) priorityFilter.onchange = () => { page = 1; draw(); };
    if (searchInput) searchInput.oninput = () => { page = 1; draw(); };
    $('#incident-refresh').onclick = load;
    await load();
  }
};

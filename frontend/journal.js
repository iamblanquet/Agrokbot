'use strict';
window.campoJournal = {
  project: '', rows: [], projects: [], fetched: '', page: 1, selected: null,
  filters: { from: '', to: '', task: '', author: '', status: '', search: '', hasPhotos: false },
  filtersOpen: false,

  async render() {
    const { $, esc, heading, api } = window.campoUi;
    const self = this;

    const label = s => ({
      IN_PROGRESS: 'En progreso',
      FINISHED: 'Finalizado',
      CREATED: 'Creado',
      CANCELLED: 'Cancelado'
    })[s] || s || 'Sin estado';

    const statusChipClass = s => ({
      FINISHED: 'chip-status-finished',
      IN_PROGRESS: 'chip-status-in_progress',
      CREATED: 'chip-status-created',
      CANCELLED: 'chip-status-cancelled'
    })[s] || '';

    const statusColorClass = s => ({
      FINISHED: 'green',
      IN_PROGRESS: 'amber',
      CREATED: 'blue',
      CANCELLED: 'red'
    })[s] || '';

    const progress = n => typeof n === 'number'
      ? `${(n / 100).toLocaleString('es-MX', { maximumFractionDigits: 1 })} %`
      : '0 %';

    const activeProject = () => self.projects.find(p => p.id === self.project);

    const renderProjectSliderHtml = () => {
      const projects = self.projects;
      if (!projects.length) return '';
      const cardsHtml = projects.map(p => {
        const isSel = self.project === p.id;
        return `
          <button class="project-card ${isSel ? 'selected' : ''}" data-project-card="${esc(p.id)}" aria-pressed="${isSel ? 'true' : 'false'}">
            <div class="project-meta">
              <span class="project-code">${esc(p.folio || p.code || 'PRJ')}</span>
              <span class="chip ${isSel ? '' : 'chip-inactive'}">${isSel ? 'En consulta' : 'Disponible'}</span>
            </div>
            <h3>${esc(p.name)}</h3>
            <p class="subline">Folio: ${esc(p.folio || p.code || 'S/N')} · Catálogo central ERP</p>
            <div class="project-foot">
              <span class="project-journal-label">${isSel ? 'Bitácora cargada' : 'Consultar asientos'}</span>
              <span class="selected-label">${isSel ? 'Seleccionado' : 'Ver bitácora <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>'}</span>
            </div>
          </button>`;
      }).join('');

      return `
        <div class="section-heading project-section-heading journal-project-heading">
          <div class="project-heading-info">
            <h2>Proyectos en ERP</h2>
            <span class="project-count-badge">${projects.length} ${projects.length === 1 ? 'proyecto' : 'proyectos'}</span>
          </div>
          <div class="project-slider-nav-wrap">
            <button id="journal-refresh" class="btn small primary btn-refresh-journal" title="Actualizar datos desde el ERP">
              <svg class="refresh-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 4 23 10 17 10"></polyline>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              <span>Actualizar ERP</span>
            </button>
            ${projects.length > 1 ? `
            <div class="slider-arrow-controls" aria-label="Navegación de proyectos ERP">
              <button class="slider-nav-btn prev" data-journal-slider-nav="prev" aria-label="Proyecto anterior" title="Proyecto anterior">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
              </button>
              <span class="slider-counter" id="journal-slider-counter">1 / ${projects.length}</span>
              <button class="slider-nav-btn next" data-journal-slider-nav="next" aria-label="Siguiente proyecto" title="Siguiente proyecto">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </button>
            </div>` : ''}
            <span class="catalog-badge" id="journal-time"></span>
          </div>
        </div>
        <div class="project-slider-wrapper journal-slider-wrapper">
          ${projects.length > 1 ? `
          <button class="project-floating-arrow prev" data-journal-slider-nav="prev" aria-label="Proyecto anterior" title="Proyecto anterior">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
          </button>` : ''}
          <section class="project-slider-track journal-slider-track" id="journal-slider-track" tabindex="0" role="region" aria-label="Carrusel de proyectos ERP">
            ${cardsHtml}
          </section>
          ${projects.length > 1 ? `
          <button class="project-floating-arrow next" data-journal-slider-nav="next" aria-label="Siguiente proyecto" title="Siguiente proyecto">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>` : ''}
        </div>
        ${projects.length > 1 ? `
        <div class="project-slider-dots" id="journal-slider-dots" role="tablist" aria-label="Indicadores de proyectos ERP">
          ${projects.map((p, i) => `
            <button class="slider-dot ${self.project === p.id ? 'active' : (i === 0 && !self.project ? 'active' : '')}" data-journal-dot="${i}" aria-label="Ir a proyecto ${i + 1}: ${esc(p.name)}" title="${esc(p.name)}"></button>
          `).join('')}
        </div>` : ''}
      `;
    };

    $('#main').innerHTML = heading('Bitácora ERP', 'Historial del ERP · Solo consulta · Trazabilidad de operaciones en campo') + `
      <section id="journal" class="journal">
        <!-- 1. Franja de Resumen Operativo ARRIBA (Idéntico a Mis proyectos) -->
        <section class="stats journal-stats" id="journal-stats" aria-label="Resumen de bitácora"></section>

        <!-- 2. Carrusel de Proyectos ERP -->
        <div id="journal-slider-container"></div>

        <!-- Hidden select for compatibility -->
        <select id="journal-project" hidden aria-hidden="true"></select>

        <div class="journal-status-strip">
          <p id="journal-message" role="status" class="journal-message"></p>
        </div>

        <!-- 3. Panel de Asientos idéntico a Tareas del proyecto -->
        <section class="task-panel">
          <div class="task-panel-head">
            <div>
              <h2>Asientos y registros ERP</h2>
              <p id="journal-active-project-name">Selecciona un proyecto</p>
            </div>
            <div class="filters">
              <input id="journal-search" type="search" placeholder="Buscar tarea…" aria-label="Buscar tarea">
              <select id="journal-status" aria-label="Filtrar estado">
                <option value="">Todos los estados</option>
                <option value="IN_PROGRESS">En progreso</option>
                <option value="FINISHED">Finalizadas</option>
                <option value="CREATED">Creados</option>
                <option value="CANCELLED">Cancelados</option>
              </select>
            </div>
          </div>

          <!-- Listado Visual: Tabla idéntica a Tareas del proyecto -->
          <div id="journal-results"></div>

          <!-- Pie del panel con paginación integrada -->
          <div class="table-caption" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
            <span id="journal-count">0 registros · Página 1 de 1</span>
            <div style="display: inline-flex; gap: 8px;">
              <button id="journal-prev" class="btn subtle small" type="button" aria-label="Página anterior">&lt; Anterior</button>
              <button id="journal-next" class="btn subtle small" type="button" aria-label="Página siguiente">Siguiente &gt;</button>
            </div>
          </div>
        </section>

        <!-- 4. Detalle del Asiento (Modal Sheet Dialog) -->
        <section id="journal-detail" tabindex="-1"></section>
      </section>
    `;

    const root = $('#journal'), find = s => root.querySelector(s), active = () => root.isConnected;

    const fill = (id, values, all) => {
      const el = find(id);
      if (!el) return;
      el.innerHTML = `<option value="">${all}</option>` +
        [...new Set(values.filter(Boolean))].sort().map(v => `<option value="${esc(v)}">${esc(id === '#journal-status' ? label(v) : v)}</option>`).join('');
    };

    const controls = () => {
      fill('#journal-task', self.rows.map(r => r.taskName), 'Todas las tareas');
      fill('#journal-author', self.rows.map(r => r.author), 'Todos los autores');
      fill('#journal-status', self.rows.map(r => r.status), 'Todos los estados');
      for (const key of ['from', 'to', 'task', 'author', 'status']) {
        const input = find('#journal-' + key);
        if (input) input.value = self.filters[key] || '';
      }
      const searchInput = find('#journal-search');
      if (searchInput) searchInput.value = self.filters.search || '';

      // Actualizar píldoras rápidas
      root.querySelectorAll('.quick-pill').forEach(pill => {
        const type = pill.dataset.quickFilter;
        let isAct = false;
        if (type === 'all') isAct = !self.filters.status && !self.filters.hasPhotos;
        else if (type === 'photos') isAct = !!self.filters.hasPhotos;
        else isAct = self.filters.status === type;
        pill.classList.toggle('active', isAct);
      });

      // Actualizar badge de filtros avanzados
      let activeAdvCount = 0;
      if (self.filters.from) activeAdvCount++;
      if (self.filters.to) activeAdvCount++;
      if (self.filters.task) activeAdvCount++;
      if (self.filters.author) activeAdvCount++;
      const badge = find('#journal-filter-badge');
      const toggleBtn = find('#journal-toggle-filters');
      if (badge && toggleBtn) {
        badge.textContent = activeAdvCount;
        badge.hidden = activeAdvCount === 0;
        toggleBtn.classList.toggle('has-active', activeAdvCount > 0);
      }
    };

    let activeModalCloser = null;

    const formatDateTime = str => {
      if (!str) return 'No informada';
      try {
        const d = new Date(str);
        if (isNaN(d.getTime())) return str;
        return d.toLocaleString('es-MX', {
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
      } catch (_) {
        return str;
      }
    };

    const getFieldIconSvg = label => {
      const l = (label || '').toLowerCase();
      if (l.includes('captura') || l.includes('fecha') || l.includes('hora')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>';
      }
      if (l.includes('conectiv') || l.includes('red') || l.includes('internet') || l.includes('online')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"></path><path d="M1.42 9a16 16 0 0 1 21.16 0"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>';
      }
      if (l.includes('ejecutad') || l.includes('avance') || l.includes('cantid') || l.includes('meta')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
      }
      if (l.includes('cuadrilla') || l.includes('persona')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>';
      }
      if (l.includes('técnico') || l.includes('tecnico')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><polyline points="17 11 19 13 23 9"></polyline></svg>';
      }
      if (l.includes('auxiliar')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
      }
      if (l.includes('maquin') || l.includes('equipo') || l.includes('dron') || l.includes('tractor')) {
        return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>';
      }
      return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle></svg>';
    };

    const detail = row => {
      if (activeModalCloser) activeModalCloser();
      self.selected = row.id;
      const info = row.presentation || { observations: row.notes, resources: [] };
      const author = info.reportedBy || row.author;
      const opDate = (row.operationDate || '').slice(0, 10);
      const base = { project: self.project, log: row.id };
      const url = (a, kind) => '/api/admin/journal/' + kind + '?' + new URLSearchParams({ ...base, attachment: a.id });

      find('#journal-detail').innerHTML = `
        <dialog class="modal-sheet journal-modal-sheet" id="journal-modal" aria-labelledby="journal-modal-title">
          <div class="journal-modal-header">
            <div class="journal-modal-header-main">
              <div class="journal-modal-eyebrow">
                <span class="eyebrow-icon-bubble">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                  </svg>
                </span>
                <span>DETALLE DEL REPORTE · ERP</span>
              </div>
              <h2 id="journal-modal-title" class="journal-modal-title">${esc(row.taskName || 'Detalle del asiento')}</h2>
              <div class="journal-modal-subtitle-row">
                ${row.taskCode ? `<span class="journal-task-code-badge">${esc(row.taskCode)}</span>` : ''}
                <span class="journal-modal-activity">${esc(row.activityName || 'Operación general')}</span>
              </div>
            </div>
            <button type="button" id="journal-close" class="journal-modal-close-btn" aria-label="Cerrar modal (Esc)" title="Cerrar (Esc)">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div class="modal-scroll-body">
            <!-- 1. Franja de métricas clave con iconos -->
            <div class="journal-detail-highlight">
              <div class="highlight-item">
                <div class="hl-head">
                  <span class="hl-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                      <line x1="16" y1="2" x2="16" y2="6"></line>
                      <line x1="8" y1="2" x2="8" y2="6"></line>
                      <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                  </span>
                  <span class="hl-label">Fecha operativa</span>
                </div>
                <strong class="hl-val">${esc(opDate || 'Sin fecha')}</strong>
              </div>

              <div class="highlight-item">
                <div class="hl-head">
                  <span class="hl-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                      <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                  </span>
                  <span class="hl-label">Estado</span>
                </div>
                <div class="hl-val">
                  <span class="chip ${statusChipClass(row.status)}">${esc(label(row.status))}</span>
                </div>
              </div>

              <div class="highlight-item">
                <div class="hl-head">
                  <span class="hl-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
                      <polyline points="17 6 23 6 23 12"></polyline>
                    </svg>
                  </span>
                  <span class="hl-label">Avance acumulado</span>
                </div>
                <strong class="hl-val hl-pct">${esc(progress(row.progressBps))}</strong>
              </div>

              <div class="highlight-item">
                <div class="hl-head">
                  <span class="hl-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                      <circle cx="12" cy="13" r="4"></circle>
                    </svg>
                  </span>
                  <span class="hl-label">Evidencias</span>
                </div>
                <strong class="hl-val">${row.attachments.length} foto(s)</strong>
              </div>
            </div>

            <!-- 2. Barra de avance con porcentaje -->
            <div class="journal-detail-progress-wrap">
              <div class="progress-label">
                <span class="progress-title">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                  </svg>
                  Porcentaje de avance en ERP
                </span>
                <strong class="progress-val-text">${esc(progress(row.progressBps))}</strong>
              </div>
              <progress max="10000" value="${typeof row.progressBps === 'number' ? row.progressBps : 0}" aria-label="Porcentaje de avance en ERP"></progress>
            </div>

            <!-- 3. Información del registro -->
            <div class="journal-modal-section">
              <h3 class="journal-section-subtitle">
                <span class="section-icon-bubble">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                  </svg>
                </span>
                <span>Información del registro</span>
              </h3>
              <dl class="journal-meta-grid">
                <div class="meta-field">
                  <dt>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="4" y1="9" x2="20" y2="9"></line>
                      <line x1="4" y1="15" x2="20" y2="15"></line>
                      <line x1="10" y1="3" x2="8" y2="21"></line>
                      <line x1="16" y1="3" x2="14" y2="21"></line>
                    </svg>
                    Referencia ERP
                  </dt>
                  <dd><code class="ref-code">${esc(row.id)}</code></dd>
                </div>
                <div class="meta-field">
                  <dt>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    Registro en ERP
                  </dt>
                  <dd>${esc(formatDateTime(row.createdAt))}</dd>
                </div>
                <div class="meta-field">
                  <dt>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                      <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                    Reportado por
                  </dt>
                  <dd class="user-meta">
                    <span class="avatar-mini">${esc((author || 'A').charAt(0).toUpperCase())}</span>
                    <strong>${esc(author)}</strong>
                  </dd>
                </div>
                ${row.responsible && row.responsible !== author ? `
                <div class="meta-field">
                  <dt>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                      <circle cx="8.5" cy="7" r="4"></circle>
                      <polyline points="17 11 19 13 23 9"></polyline>
                    </svg>
                    Responsable de tarea
                  </dt>
                  <dd>${esc(row.responsible || 'Sin responsable asignado')}</dd>
                </div>` : ''}
                <div class="meta-field">
                  <dt>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                      <line x1="6" y1="6" x2="6.01" y2="6"></line>
                      <line x1="6" y1="18" x2="6.01" y2="18"></line>
                    </svg>
                    Origen del asiento
                  </dt>
                  <dd><span class="origin-badge">${esc(row.source || 'ERP Central')}</span></dd>
                </div>
              </dl>
            </div>

            <!-- 4. Trabajo en campo -->
            ${info.parsed ? `
            <div class="journal-modal-section">
              <h3 class="journal-section-subtitle">
                <span class="section-icon-bubble">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                    <polyline points="2 17 12 22 22 17"></polyline>
                    <polyline points="2 12 12 17 22 12"></polyline>
                  </svg>
                </span>
                <span>Trabajo en campo</span>
              </h3>
              <dl class="journal-meta-grid">
                <div class="meta-field">
                  <dt>
                    ${getFieldIconSvg('captura')}
                    Captura en campo
                  </dt>
                  <dd>${esc(formatDateTime(info.capturedAt))}</dd>
                </div>
                ${(info.resources || []).map(item => {
                  const lbl = item.label === 'Avance' ? 'Cantidad ejecutada' : item.label;
                  return `
                    <div class="meta-field">
                      <dt>
                        ${getFieldIconSvg(lbl)}
                        ${esc(lbl)}
                      </dt>
                      <dd>${esc(item.value || 'Sin detalle')}</dd>
                    </div>
                  `;
                }).join('')}
              </dl>
            </div>` : ''}

            <!-- 5. Observaciones de campo -->
            <div class="journal-modal-section">
              <h3 class="journal-section-subtitle">
                <span class="section-icon-bubble">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                  </svg>
                </span>
                <span>Observaciones de campo</span>
              </h3>
              <div class="journal-detail-notes-card">
                <svg class="notes-quote-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <p class="journal-notes">${esc(info.observations || 'Sin observaciones registradas para este asiento.')}</p>
              </div>
              ${info.parsed && row.notes ? `
              <details class="journal-notes-raw-details">
                <summary>Ver registro original completo del ERP</summary>
                <pre class="journal-raw-pre">${esc(row.notes)}</pre>
              </details>` : ''}
            </div>

            <!-- 6. Galería de Evidencias -->
            <div class="journal-modal-section">
              <h3 class="journal-section-subtitle">
                <span class="section-icon-bubble">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                    <circle cx="12" cy="13" r="4"></circle>
                  </svg>
                </span>
                <span>Evidencias fotográficas</span>
                <span class="photo-count-badge">${row.attachments.length} foto(s)</span>
              </h3>
              <div class="journal-gallery">
                ${row.attachments.map(a => `
                  <figure class="gallery-card">
                    <div class="gallery-img-wrapper">
                      <img src="${esc(url(a, 'preview'))}" alt="${esc(a.originalFileName || 'Evidencia')}" loading="lazy">
                      <div class="gallery-zoom-overlay">
                        <a href="${esc(url(a, 'file'))}" target="_blank" rel="noopener" class="zoom-btn" title="Abrir original en pestaña nueva">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                            <polyline points="15 3 21 3 21 9"></polyline>
                            <line x1="10" y1="14" x2="21" y2="3"></line>
                          </svg>
                        </a>
                      </div>
                    </div>
                    <figcaption>
                      <div class="gallery-file-info">
                        <strong class="file-name" title="${esc(a.originalFileName || 'Fotografía')}">${esc(a.originalFileName || 'Fotografía')}</strong>
                        <small class="file-size">${a.sizeBytes ? (a.sizeBytes / 1024).toFixed(1) + ' KB' : ''}</small>
                      </div>
                      <p class="journal-image-error" hidden>No se pudo cargar la vista previa. Intenta actualizar o descargar el original.</p>
                      <a class="btn small btn-download-file" href="${esc(url(a, 'file'))}" download="${esc(a.originalFileName || 'evidencia')}">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="7 10 12 15 17 10"></polyline>
                          <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        <span>Descargar original</span>
                      </a>
                    </figcaption>
                  </figure>
                `).join('') || '<div class="gallery-empty"><p>Este asiento no tiene fotografías adjuntas.</p></div>'}
              </div>
            </div>
          </div>

          <div class="journal-modal-footer">
            <div class="dialog-footer-left">
              <span class="journal-footer-ref">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle; margin-right:4px;">
                  <line x1="4" y1="9" x2="20" y2="9"></line>
                  <line x1="4" y1="15" x2="20" y2="15"></line>
                  <line x1="10" y1="3" x2="8" y2="21"></line>
                  <line x1="16" y1="3" x2="14" y2="21"></line>
                </svg>
                Asiento ERP: <code class="ref-code-inline">${esc(row.id)}</code>
              </span>
            </div>
            <div class="dialog-footer-right">
              <button type="button" id="journal-footer-close" class="btn">Cerrar</button>
            </div>
          </div>
        </dialog>
      `;

      let escHandler = null;

      const closeDetail = () => {
        if (escHandler) {
          window.removeEventListener('keydown', escHandler);
          escHandler = null;
        }
        activeModalCloser = null;
        const dlg = find('#journal-modal');
        if (dlg) {
          try {
            if (typeof dlg.close === 'function' && dlg.open) dlg.close();
          } catch (_) {}
        }
        self.selected = null;
        const detailEl = find('#journal-detail');
        if (detailEl) detailEl.innerHTML = '';
      };

      activeModalCloser = closeDetail;

      const dlg = find('#journal-modal');
      if (dlg) {
        if (typeof dlg.showModal === 'function') {
          try {
            dlg.showModal();
          } catch (_) {
            dlg.setAttribute('open', '');
          }
        } else {
          dlg.setAttribute('open', '');
        }

        // 1. Escuchar Escape globalmente
        escHandler = e => {
          if (e.key === 'Escape' || e.key === 'Esc' || e.keyCode === 27) {
            e.preventDefault();
            closeDetail();
          }
        };
        window.addEventListener('keydown', escHandler);

        // 2. Evento cancel nativo de <dialog>
        dlg.addEventListener('cancel', e => {
          e.preventDefault();
          closeDetail();
        });

        // 3. Clic en el backdrop oscuro
        dlg.addEventListener('click', e => {
          const rect = dlg.getBoundingClientRect();
          const clickedOutside = (
            e.clientX < rect.left ||
            e.clientX > rect.right ||
            e.clientY < rect.top ||
            e.clientY > rect.bottom
          );
          if (clickedOutside || e.target === dlg) {
            closeDetail();
          }
        });
      }

      // 4. Botones de cerrar (header y footer)
      const closeBtn = find('#journal-close');
      if (closeBtn) closeBtn.onclick = closeDetail;
      const footerCloseBtn = find('#journal-footer-close');
      if (footerCloseBtn) footerCloseBtn.onclick = closeDetail;

      find('#journal-detail').querySelectorAll('img').forEach(img => {
        img.onerror = () => {
          img.hidden = true;
          const errEl = img.closest('.gallery-card')?.querySelector('.journal-image-error');
          if (errEl) errEl.hidden = false;
        };
      });
    };

    const draw = () => {
      const f = self.filters;
      const invalid = f.from && f.to && f.from > f.to;
      const sTerm = (f.search || '').trim().toLowerCase();

      const rows = invalid ? [] : self.rows.filter(r => {
        const d = (r.operationDate || '').slice(0, 10);
        if (f.from && (!d || d < f.from)) return false;
        if (f.to && (!d || d > f.to)) return false;
        if (f.task && r.taskName !== f.task) return false;
        if (f.author && r.author !== f.author) return false;
        if (f.status && r.status !== f.status) return false;
        if (f.hasPhotos && (!r.attachments || !r.attachments.length)) return false;
        if (sTerm) {
          const haystack = `${r.taskName || ''} ${r.activityName || ''} ${r.taskCode || ''} ${r.author || ''} ${r.responsible || ''} ${r.notes || ''} ${r.id || ''}`.toLowerCase();
          if (!haystack.includes(sTerm)) return false;
        }
        return true;
      });

      // Franja de estadísticas en la parte SUPERIOR
      const totalPhotos = self.rows.reduce((acc, r) => acc + (r.attachments?.length || 0), 0);
      const uniqueTasks = new Set(self.rows.map(r => r.taskName).filter(Boolean)).size;
      const uniqueAuthors = new Set(self.rows.map(r => r.author).filter(Boolean)).size;

      const statsEl = find('#journal-stats');
      if (statsEl) {
        statsEl.innerHTML = `
          <div class="stat">
            <span class="stat-label">Asientos ERP</span>
            <strong>${self.rows.length.toString().padStart(2, '0')}</strong>
            <small>${self.project ? 'en este proyecto' : 'sin seleccionar'}</small>
          </div>
          <div class="stat">
            <span class="stat-label">Tareas</span>
            <strong>${uniqueTasks.toString().padStart(2, '0')}</strong>
            <small>documentadas</small>
          </div>
          <div class="stat">
            <span class="stat-label">Evidencias</span>
            <strong>${totalPhotos.toString().padStart(2, '0')}</strong>
            <small>fotos de campo</small>
          </div>
          <div class="stat">
            <span class="stat-label">Cuadrillas</span>
            <strong>${uniqueAuthors.toString().padStart(2, '0')}</strong>
            <small>personal activo</small>
          </div>
        `;
      }

      // Nombre del proyecto activo en el encabezado del panel
      const activeProj = activeProject();
      const projNameEl = find('#journal-active-project-name');
      if (projNameEl) {
        projNameEl.textContent = activeProj
          ? `${activeProj.name} (${activeProj.folio || activeProj.code || 'ERP'})`
          : 'Selecciona un proyecto arriba';
      }

      // Paginación
      const pages = Math.max(1, Math.ceil(rows.length / 20));
      self.page = Math.max(1, Math.min(self.page, pages));

      const countEl = find('#journal-count');
      if (countEl) countEl.textContent = `${rows.length} ${rows.length === 1 ? 'registro' : 'registros'} · Página ${self.page} de ${pages}`;

      find('#journal-prev').disabled = self.page === 1;
      find('#journal-next').disabled = self.page === pages;

      const timeEl = find('#journal-time');
      if (timeEl) {
        timeEl.textContent = self.fetched ? 'Actualizado: ' + new Date(self.fetched).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }) : '';
      }

      const pageRows = rows.slice((self.page - 1) * 20, self.page * 20);

      find('#journal-results').innerHTML = invalid
        ? '<div class="journal-alert error" role="alert"><p>La fecha inicial debe ser anterior o igual a la final.</p></div>'
        : rows.length
          ? `<div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>TAREA / ACTIVIDAD</th>
                    <th class="person-column">RESPONSABLE</th>
                    <th>AVANCE</th>
                    <th class="status-column">ESTADO</th>
                    <th class="photos-column" style="text-align: center;">FOTOS</th>
                    <th style="text-align: right;"><span class="muted">ACCIÓN</span></th>
                  </tr>
                </thead>
                <tbody>
                  ${pageRows.map(r => {
                    const authorName = r.author || r.responsible || 'Sin asignar';
                    const initials = esc(authorName.split(' ').filter(Boolean).map(s => s[0]).slice(0, 2).join('').toUpperCase() || 'A');
                    const opDate = (r.operationDate || '').slice(0, 10);
                    const photoCount = Array.isArray(r.attachments) ? r.attachments.length : 0;
                    return `
                      <tr data-entry="${esc(r.id)}">
                        <td class="task-name">
                          <strong>${esc(r.taskName || 'Tarea sin nombre')}</strong>
                          <small>
                            ${r.taskCode ? `<span class="task-code">${esc(r.taskCode)}</span> ` : ''}${esc(r.activityName || 'Operación')}${opDate ? ` · ${esc(opDate)}` : ''}
                          </small>
                        </td>
                        <td class="person-column">
                          <span class="person">
                            <span class="person-circle">${initials}</span>
                            ${esc(authorName)}
                          </span>
                        </td>
                        <td class="task-progress">
                          <span>${esc(progress(r.progressBps))}</span>
                          <progress max="10000" value="${typeof r.progressBps === 'number' ? r.progressBps : 0}" aria-label="Avance"></progress>
                        </td>
                        <td class="status-column">
                          <span class="status ${statusColorClass(r.status)}">${esc(label(r.status))}</span>
                        </td>
                        <td class="photos-column" style="text-align: center;">
                          ${photoCount > 0
                            ? `<span class="photo-count-pill">${photoCount}</span>`
                            : '<span class="muted">—</span>'}
                        </td>
                        <td class="task-action" style="text-align: right;">
                          <button class="btn subtle" data-entry="${esc(r.id)}">Detalle</button>
                        </td>
                      </tr>
                    `;
                  }).join('')}
                </tbody>
              </table>
            </div>`
          : `<div class="empty">
              <h3>${self.project ? 'Sin asientos con estos filtros' : 'Selecciona un proyecto'}</h3>
              <p>${self.project ? 'Prueba cambiando los filtros o el texto de búsqueda.' : 'Elige un proyecto en el carrusel superior para consultar su bitácora ERP.'}</p>
            </div>`;

      // Eventos para abrir detalle al pulsar filas o botón Detalle
      find('#journal-results').querySelectorAll('tbody tr').forEach(tr => {
        tr.style.cursor = 'pointer';
        tr.onclick = () => {
          const entryId = tr.dataset.entry;
          const row = self.rows.find(r => r.id === entryId);
          if (row) {
            detail(row);
            const detailEl = find('#journal-detail');
            if (detailEl) detailEl.focus();
          }
        };
      });

      find('#journal-results').querySelectorAll('button[data-entry]').forEach(btn => {
        btn.onclick = (e) => {
          e.stopPropagation();
          const entryId = btn.dataset.entry;
          const row = self.rows.find(r => r.id === entryId);
          if (row) {
            detail(row);
            const detailEl = find('#journal-detail');
            if (detailEl) detailEl.focus();
          }
        };
      });
    };

    let requestId = 0;
    const load = async () => {
      const id = ++requestId;
      self.selected = null;
      self.rows = [];
      self.fetched = '';
      if (activeModalCloser) activeModalCloser();
      else find('#journal-detail').innerHTML = '';
      controls();
      draw();
      if (!self.project) {
        find('#journal-message').textContent = '';
        return;
      }
      find('#journal-message').textContent = 'Consultando asientos en el ERP…';
      const refreshBtn = find('#journal-refresh');
      if (refreshBtn) refreshBtn.disabled = true;
      try {
        const data = await api('/api/admin/journal/entries?' + new URLSearchParams({ project: self.project }));
        if (!active() || id !== requestId) return;
        self.rows = data.entries || [];
        self.fetched = new Date().toISOString();
        self.page = 1;
        controls();
        draw();
        find('#journal-message').textContent = 'Consulta actualizada.';
      } catch (error) {
        if (active() && id !== requestId) {
          find('#journal-message').textContent = 'No se pudo consultar el ERP: ' + error.message;
        }
      } finally {
        if (active() && id === requestId) {
          const btn = find('#journal-refresh');
          if (btn) btn.disabled = false;
        }
      }
    };

    const initJournalSlider = () => {
      const container = find('#journal-slider-container');
      if (!container) return;
      container.innerHTML = renderProjectSliderHtml();

      const refreshBtn = find('#journal-refresh');
      if (refreshBtn) refreshBtn.onclick = load;

      const track = find('#journal-slider-track');
      if (!track) return;
      const cards = Array.from(track.querySelectorAll('.project-card'));
      if (!cards.length) return;

      const getCardStep = () => {
        if (cards.length > 1) {
          const step = cards[1].offsetLeft - cards[0].offsetLeft;
          if (step > 0) return step;
        }
        return cards[0].offsetWidth + 14;
      };

      const updateSliderUi = () => {
        const scrollLeft = track.scrollLeft;
        const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth);
        const isAtStart = scrollLeft <= 4;
        const isAtEnd = scrollLeft >= maxScroll - 6 || maxScroll <= 2;

        const step = getCardStep() || 1;
        const activeIdx = Math.min(cards.length - 1, Math.max(0, Math.round(scrollLeft / step)));

        root.querySelectorAll('#journal-slider-dots .slider-dot').forEach((dot, i) => {
          dot.classList.toggle('active', i === activeIdx);
        });

        const counter = find('#journal-slider-counter');
        if (counter) {
          const isDesktop = track.clientWidth >= 768;
          if (isDesktop && cards.length >= 2) {
            const endIdx = Math.min(cards.length, activeIdx + 2);
            counter.textContent = `${activeIdx + 1}–${endIdx} / ${cards.length}`;
          } else {
            counter.textContent = `${activeIdx + 1} / ${cards.length}`;
          }
        }

        root.querySelectorAll('[data-journal-slider-nav="prev"]').forEach(btn => {
          btn.disabled = isAtStart;
        });
        root.querySelectorAll('[data-journal-slider-nav="next"]').forEach(btn => {
          btn.disabled = isAtEnd;
        });
      };

      const slide = direction => {
        const step = getCardStep();
        track.scrollBy({ left: direction * step, behavior: 'smooth' });
      };

      root.querySelectorAll('[data-journal-slider-nav]').forEach(btn => {
        btn.onclick = e => {
          e.preventDefault();
          e.stopPropagation();
          slide(btn.dataset.journalSliderNav === 'next' ? 1 : -1);
        };
      });

      root.querySelectorAll('#journal-slider-dots .slider-dot').forEach(dot => {
        dot.onclick = e => {
          e.preventDefault();
          const idx = parseInt(dot.dataset.journalDot, 10);
          const targetCard = cards[idx];
          if (targetCard) {
            track.scrollTo({ left: targetCard.offsetLeft - track.offsetLeft, behavior: 'smooth' });
          }
        };
      });

      cards.forEach(card => {
        card.onclick = () => {
          const projId = card.dataset.projectCard;
          if (self.project === projId) return;
          self.project = projId;
          self.filters = { from: '', to: '', task: '', author: '', status: '', search: '', hasPhotos: false };
          const hiddenSelect = find('#journal-project');
          if (hiddenSelect) hiddenSelect.value = projId;
          syncSelectedProjectCard();
          load();
        };
      });

      let ticking = false;
      track.onscroll = () => {
        if (!ticking) {
          window.requestAnimationFrame(() => {
            updateSliderUi();
            ticking = false;
          });
          ticking = true;
        }
      };

      track.onkeydown = e => {
        if (e.key === 'ArrowRight') {
          e.preventDefault();
          slide(1);
        } else if (e.key === 'ArrowLeft') {
          e.preventDefault();
          slide(-1);
        }
      };

      updateSliderUi();
    };

    const syncSelectedProjectCard = () => {
      const cards = root.querySelectorAll('#journal-slider-track .project-card');
      cards.forEach(c => {
        const isSel = c.dataset.projectCard === self.project;
        c.classList.toggle('selected', isSel);
        c.setAttribute('aria-pressed', isSel ? 'true' : 'false');
        const chip = c.querySelector('.chip');
        if (chip) {
          chip.textContent = isSel ? 'En consulta' : 'Disponible';
          chip.classList.toggle('chip-inactive', !isSel);
        }
        const footLabel = c.querySelector('.project-journal-label');
        if (footLabel) footLabel.textContent = isSel ? 'Bitácora cargada' : 'Consultar asientos';
        const label = c.querySelector('.selected-label');
        if (label) {
          label.innerHTML = isSel
            ? 'Seleccionado'
            : 'Ver bitácora <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
        }
      });
    };

    // Quick Status Pills
    root.querySelectorAll('.quick-pill').forEach(pill => {
      pill.onclick = () => {
        const filterType = pill.dataset.quickFilter;
        if (filterType === 'all') {
          self.filters.status = '';
          self.filters.hasPhotos = false;
        } else if (filterType === 'photos') {
          self.filters.hasPhotos = !self.filters.hasPhotos;
        } else {
          self.filters.status = self.filters.status === filterType ? '' : filterType;
          self.filters.hasPhotos = false;
        }
        self.page = 1;
        controls();
        draw();
      };
    });

    // Quick Search Input
    const searchInput = find('#journal-search');
    if (searchInput) {
      searchInput.oninput = e => {
        self.filters.search = e.target.value;
        self.page = 1;
        draw();
      };
    }

    // Toggle Advanced Filters Drawer
    const toggleBtn = find('#journal-toggle-filters');
    const drawer = find('#journal-advanced-filters');
    if (toggleBtn && drawer) {
      toggleBtn.onclick = () => {
        self.filtersOpen = !self.filtersOpen;
        drawer.hidden = !self.filtersOpen;
        toggleBtn.setAttribute('aria-expanded', self.filtersOpen ? 'true' : 'false');
      };
    }

    // Advanced Drawer Fields
    for (const key of ['from', 'to', 'task', 'author', 'status']) {
      const input = find('#journal-' + key);
      if (input) {
        input.onchange = e => {
          self.filters[key] = e.target.value;
          self.page = 1;
          controls();
          draw();
        };
      }
    }

    const clearBtn = find('#journal-clear');
    if (clearBtn) {
      clearBtn.onclick = () => {
        self.filters = { from: '', to: '', task: '', author: '', status: '', search: '', hasPhotos: false };
        self.page = 1;
        controls();
        draw();
      };
    }

    find('#journal-prev').onclick = () => {
      self.page--;
      draw();
    };

    find('#journal-next').onclick = () => {
      self.page++;
      draw();
    };

    const hiddenSelect = find('#journal-project');
    if (hiddenSelect) {
      hiddenSelect.onchange = e => {
        self.project = e.target.value;
        self.filters = { from: '', to: '', task: '', author: '', status: '', search: '', hasPhotos: false };
        syncSelectedProjectCard();
        load();
      };
    }

    controls();
    draw();

    find('#journal-message').textContent = 'Consultando proyectos en el ERP…';
    try {
      const data = await api('/api/admin/journal/projects');
      if (!active()) return;
      self.projects = data.projects || [];
      const hiddenSelectEl = find('#journal-project');
      if (hiddenSelectEl) {
        hiddenSelectEl.innerHTML = '<option value="">Selecciona un proyecto</option>' +
          self.projects.map(p => `<option value="${esc(p.id)}">${esc(p.folio || p.code || '')} · ${esc(p.name)}</option>`).join('');
      }

      if (!self.projects.some(p => p.id === self.project)) {
        self.project = self.projects[0]?.id || '';
        self.rows = [];
        self.fetched = '';
      }

      if (hiddenSelectEl) hiddenSelectEl.value = self.project;
      initJournalSlider();
      find('#journal-message').textContent = self.projects.length ? '' : 'No hay proyectos disponibles.';
      if (self.project) await load(); else draw();
    } catch (error) {
      if (active()) {
        self.rows = [];
        self.fetched = '';
        draw();
        find('#journal-message').textContent = 'La bitácora necesita conexión al ERP: ' + error.message;
      }
    }
  }
};

/* ============================================================
   Churn AI — front-end controller
   Shared by the onboarding page and the dashboard.
   ============================================================ */
(() => {
  'use strict';

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const icon = (name, cls = '') => `<svg class="${cls}"><use href="#i-${name}"></use></svg>`;
  const escapeHtml = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

  /* ---------- Storage (survives blocked/partitioned storage) ---------- */
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, val) { try { localStorage.setItem(key, val); } catch { /* ignore */ } },
    remove(key) { try { localStorage.removeItem(key); } catch { /* ignore */ } },
  };

  /* ---------- Toasts ---------- */
  const TOAST_ICONS = { ok: 'check-circle', error: 'alert-circle', info: 'info' };

  function toast(title, text = '', kind = 'info', ttl = 4200) {
    const host = $('#toasts');
    if (!host) return;
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.innerHTML = `
      ${icon(TOAST_ICONS[kind] || 'info', 'toast-ico')}
      <div class="toast-body">
        <div class="toast-title">${escapeHtml(title)}</div>
        ${text ? `<div class="toast-text">${escapeHtml(text)}</div>` : ''}
      </div>`;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      el.addEventListener('animationend', () => el.remove(), { once: true });
    }, ttl);
  }

  /* ---------- Theme ---------- */
  const theme = {
    listeners: [],
    get current() { return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'; },
    apply(next) {
      document.documentElement.dataset.theme = next;
      store.set('theme', next);
      $$('.theme-ico-dark').forEach((n) => n.classList.toggle('hidden', next === 'light'));
      $$('.theme-ico-light').forEach((n) => n.classList.toggle('hidden', next !== 'light'));
      this.listeners.forEach((fn) => fn(next));
    },
    onChange(fn) { this.listeners.push(fn); },
    init() {
      this.apply(this.current);
      const btn = $('#theme-toggle');
      if (btn) btn.addEventListener('click', () => this.apply(this.current === 'light' ? 'dark' : 'light'));
    },
  };

  /* Reads a design token so charts stay in sync with the theme. */
  const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* ---------- Risk helpers ---------- */
  const TIERS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

  const normaliseTier = (raw) => {
    const t = String(raw || '').trim().toUpperCase();
    return TIERS.includes(t) ? t : 'MEDIUM';
  };
  const tierColor = (tier) => token(`--${normaliseTier(tier).toLowerCase()}`);
  const tierClass = (tier) => `badge badge-${normaliseTier(tier).toLowerCase()}`;
  const pct = (p) => `${(Number(p || 0) * 100).toFixed(1)}%`;
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

  function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  /** Reads a FastAPI error body, falling back to the status line. */
  async function errorFrom(res, fallback) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    return fallback || `Request failed (${res.status})`;
  }

  /* ============================================================
     Onboarding
     ============================================================ */
  function initOnboarding() {
    const form = $('#onboard-form');
    if (!form) return;

    const nameInput = $('#company-name');
    const errorEl = $('#company-error');
    const submit = $('#onboard-submit');

    nameInput.addEventListener('input', () => {
      nameInput.classList.remove('has-error');
      errorEl.textContent = '';
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const name = nameInput.value.trim();
      const sector = form.querySelector('input[name="sector"]:checked')?.value;

      if (name.length < 2) {
        nameInput.classList.add('has-error');
        errorEl.textContent = 'Please enter a company name (at least 2 characters).';
        nameInput.focus();
        return;
      }

      const label = $('.btn-text', submit);
      const original = label.textContent;
      submit.disabled = true;
      label.textContent = 'Creating workspace…';
      $('.btn-arrow', submit).outerHTML = '<span class="spinner btn-arrow"></span>';

      try {
        const res = await fetch('/api/v1/tenants/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, sector }),
        });
        if (!res.ok) throw new Error(await errorFrom(res));

        const data = await res.json();
        store.set('tenant_id', data.tenant_id);
        store.set('tenant_name', data.name);
        store.set('tenant_sector', data.sector);
        window.location.href = '/dashboard';
      } catch (err) {
        console.error(err);
        toast('Could not create the workspace', err.message, 'error');
        submit.disabled = false;
        label.textContent = original;
        $('.btn-arrow', submit).outerHTML = '<svg class="btn-arrow"><use href="#i-arrow-right"></use></svg>';
      }
    });
  }

  /* ============================================================
     Dashboard
     ============================================================ */
  function initDashboard() {
    const dropzone = $('#dropzone');
    if (!dropzone) return;

    /* ----- Tenant identity ----- */
    const tenantId = store.get('tenant_id');
    if (!tenantId) { window.location.replace('/'); return; }

    const tenantName = store.get('tenant_name') || 'Workspace';
    const tenantSector = store.get('tenant_sector') || '—';

    $('#tenant-name').textContent = tenantName;
    $('#tenant-sector').textContent = tenantSector;
    $('#sector-display').textContent = tenantSector;
    $('#tenant-avatar').textContent = tenantName
      .split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
    document.title = `${tenantName} — Churn AI`;

    function signOut() {
      ['tenant_id', 'tenant_name', 'tenant_sector'].forEach((k) => store.remove(k));
      window.location.href = '/';
    }
    $('#switch-tenant').addEventListener('click', signOut);

    /* ----- Sidebar / navigation ----- */
    const sidebar = $('#sidebar');
    $('#menu-btn').addEventListener('click', () => sidebar.classList.toggle('open'));

    $$('.nav-item').forEach((item) => {
      item.addEventListener('click', () => {
        const target = document.getElementById(item.dataset.scroll);
        if (!target || target.closest('.hidden')) {
          toast('Not available yet', 'Run an analysis to unlock this section.', 'info');
          return;
        }
        $$('.nav-item').forEach((n) => n.classList.toggle('active', n === item));
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        sidebar.classList.remove('open');
      });
    });

    /* ----- File selection ----- */
    const fileInput = $('#file-upload');
    const fileList = $('#file-list');
    const uploadActions = $('#upload-actions');
    const uploadSummary = $('#upload-summary');
    const clearBtn = $('#clear-files');
    const analyzeBtn = $('#analyze-btn');

    /** @type {File[]} */
    let files = [];

    function renderFiles() {
      fileList.innerHTML = files.map((f, i) => `
        <div class="file-chip">
          <span class="file-chip-ico">${icon('file')}</span>
          <div class="file-chip-meta">
            <div class="file-chip-name">${escapeHtml(f.name)}</div>
            <div class="file-chip-size">${formatBytes(f.size)}</div>
          </div>
          <button class="file-chip-x" type="button" data-index="${i}" aria-label="Remove ${escapeHtml(f.name)}">
            ${icon('x')}
          </button>
        </div>`).join('');

      $$('.file-chip-x', fileList).forEach((btn) => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          files.splice(Number(btn.dataset.index), 1);
          renderFiles();
        });
      });

      const has = files.length > 0;
      uploadActions.classList.toggle('hidden', !has);
      clearBtn.classList.toggle('hidden', !has);
      $('#nav-file-count').textContent = String(files.length);

      const bytes = files.reduce((sum, f) => sum + f.size, 0);
      uploadSummary.textContent = has ? `${plural(files.length, 'table')} · ${formatBytes(bytes)}` : '';
    }

    function addFiles(incoming) {
      const rejected = [];
      Array.from(incoming).forEach((f) => {
        if (!/\.(csv|xlsx|xls)$/i.test(f.name)) { rejected.push(f.name); return; }
        // Same name and size means the same table was picked twice.
        if (files.some((existing) => existing.name === f.name && existing.size === f.size)) return;
        files.push(f);
      });
      if (rejected.length) {
        toast('Some files were skipped', `${rejected.join(', ')} — only CSV and Excel files are supported.`, 'error');
      }
      renderFiles();
    }

    fileInput.addEventListener('change', () => {
      addFiles(fileInput.files);
      fileInput.value = '';   // allow re-picking the same file after removal
    });

    clearBtn.addEventListener('click', (e) => {
      e.preventDefault();
      files = [];
      renderFiles();
    });

    /* Drag & drop */
    let dragDepth = 0;
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); });
    });
    dropzone.addEventListener('dragenter', () => {
      dragDepth += 1;
      dropzone.classList.add('is-dragging');
    });
    dropzone.addEventListener('dragleave', () => {
      dragDepth -= 1;
      if (dragDepth <= 0) { dragDepth = 0; dropzone.classList.remove('is-dragging'); }
    });
    dropzone.addEventListener('drop', (e) => {
      dragDepth = 0;
      dropzone.classList.remove('is-dragging');
      if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files);
    });

    /* ----- Progress choreography ----- */
    const progressPanel = $('#progress-panel');
    const progressBar = $('#progress-bar');
    const progressMsg = $('#progress-msg');
    const steps = $$('.progress-step');

    const STAGES = [
      { msg: 'Parsing your tables…', at: 12 },
      { msg: 'Resolving the schema across files…', at: 38 },
      { msg: 'Synthesising behavioural features…', at: 64 },
      { msg: 'Scoring churn risk per account…', at: 86 },
    ];
    let stageTimer = null;

    function startProgress() {
      progressPanel.classList.remove('hidden');
      steps.forEach((s) => s.classList.remove('done', 'active'));
      let i = 0;
      const advance = () => {
        if (i > 0) steps[i - 1].classList.replace('active', 'done');
        if (i >= STAGES.length) return;
        steps[i].classList.add('active');
        progressMsg.textContent = STAGES[i].msg;
        progressBar.style.width = `${STAGES[i].at}%`;
        i += 1;
        // Schema resolution and scoring are the slow calls, so linger on them.
        stageTimer = setTimeout(advance, i <= 1 ? 900 : 4200);
      };
      advance();
    }

    function stopProgress(succeeded) {
      clearTimeout(stageTimer);
      if (succeeded) {
        steps.forEach((s) => { s.classList.remove('active'); s.classList.add('done'); });
        progressBar.style.width = '100%';
        progressMsg.textContent = 'Analysis complete';
      }
      setTimeout(() => {
        progressPanel.classList.add('hidden');
        progressBar.style.width = '8%';
      }, succeeded ? 700 : 0);
    }

    /* ----- Analysis ----- */
    let predictions = [];
    let running = false;

    async function runAnalysis(button, request) {
      if (running) return;
      running = true;

      const label = $('.btn-text', button);
      const previous = label.textContent;
      button.disabled = true;
      analyzeBtn.disabled = true;
      $('#sample-btn').disabled = true;
      label.textContent = 'Analysing…';
      startProgress();

      try {
        const res = await request();
        if (!res.ok) throw new Error(await errorFrom(res, 'The analysis endpoint failed.'));

        const data = await res.json();
        stopProgress(true);
        render(data);

        const via = data.engine === 'qwen' ? 'Qwen AI' : 'the local engine';
        toast('Analysis complete', `${plural(data.predictions.length, 'account')} scored by ${via}.`, 'ok');
        if (data.engine_reason) {
          toast('Fell back to the local engine', data.engine_reason, 'info', 7000);
          loadEngineStatus();
        }
      } catch (err) {
        console.error(err);
        stopProgress(false);
        toast('Analysis failed', err.message, 'error', 8000);
        if (/tenant not found/i.test(err.message)) {
          setTimeout(signOut, 2500);
        }
      } finally {
        running = false;
        button.disabled = false;
        analyzeBtn.disabled = false;
        $('#sample-btn').disabled = !samplesAvailable;
        label.textContent = previous;
      }
    }

    analyzeBtn.addEventListener('click', () => {
      if (!files.length) return;
      const body = new FormData();
      body.append('tenant_id', tenantId);
      body.append('engine', engineMode);
      files.forEach((f) => body.append('files', f));
      runAnalysis(analyzeBtn, () => fetch('/api/v1/upload/analyze', { method: 'POST', body }));
    });

    /* ----- Engine selection ----- */
    let engineMode = 'auto';
    let engineStatus = null;

    $$('#engine-filter button').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('#engine-filter button').forEach((b) => b.classList.toggle('active', b === btn));
        engineMode = btn.dataset.engine;
        renderEngineNote();
      });
    });

    /** Names the engine that will run, and why. */
    function renderEngineNote() {
      const note = $('#engine-note');
      const text = $('#engine-note-text');
      if (!engineStatus) { note.classList.add('hidden'); return; }

      if (engineMode === 'local') {
        text.textContent = 'Local engine selected. Scoring runs on this machine with no API calls, '
          + 'and the whole cohort is scored rather than a capped batch.';
      } else if (engineMode === 'qwen') {
        text.textContent = engineStatus.qwen_available
          ? 'Qwen only. If the API call fails the analysis will error rather than fall back.'
          : `Qwen only, but it is not currently usable: ${engineStatus.detail}`;
      } else if (!engineStatus.qwen_available) {
        text.textContent = `${engineStatus.detail} Analyses will run on the local engine.`;
      } else {
        text.textContent = 'Qwen will be tried first, with an automatic fall back to the local engine.';
      }
      note.classList.remove('hidden');
    }

    function setEngineBadge(engine, reason) {
      const badge = $('#engine-badge');
      const isQwen = engine === 'qwen';
      $('#engine-display').textContent = isQwen ? 'Qwen AI' : 'Local engine';
      badge.className = `badge ${isQwen ? 'badge-accent' : 'badge-medium'}`;
      badge.title = reason || (isQwen
        ? 'Scored by the Qwen model.'
        : 'Scored by the built-in local engine.');
    }

    async function loadEngineStatus() {
      try {
        const res = await fetch('/api/v1/engine/status');
        if (!res.ok) return;
        engineStatus = await res.json();
        setEngineBadge(engineStatus.qwen_available ? 'qwen' : 'local', engineStatus.detail);
        renderEngineNote();
      } catch (err) {
        console.error('Engine status lookup failed', err);
      }
    }

    /* ----- Bundled sample dataset ----- */
    let samplesAvailable = false;
    const sampleBtn = $('#sample-btn');

    sampleBtn.addEventListener('click', () => {
      const body = new FormData();
      body.append('tenant_id', tenantId);
      body.append('engine', engineMode);
      runAnalysis(sampleBtn, () => fetch('/api/v1/upload/analyze-sample', { method: 'POST', body }));
    });

    async function loadSampleInfo() {
      try {
        const res = await fetch(`/api/v1/samples/${encodeURIComponent(tenantSector)}`);
        if (!res.ok) return;
        const info = await res.json();
        if (!info.available) return;

        samplesAvailable = true;
        $('#sample-row').classList.remove('hidden');
        sampleBtn.disabled = running;
        $('#sample-text').textContent =
          `Run the analysis on the bundled ${info.sector} dataset — ` +
          `${plural(info.file_count, 'table')}, ${info.total_rows.toLocaleString()} rows ` +
          `(${info.files.map((f) => f.file_name).join(', ')}).`;
      } catch (err) {
        console.error('Sample dataset lookup failed', err);
      }
    }

    /* ----- Rendering ----- */
    function render(data) {
      predictions = (data.predictions || []).map((item) => ({
        ...item,
        prediction: { ...item.prediction, risk_tier: normaliseTier(item.prediction.risk_tier) },
      }));

      $('#placeholder').classList.add('hidden');
      $('#results-section').classList.remove('hidden');
      $('#export-btn').classList.remove('hidden');

      setEngineBadge(data.engine, data.engine_reason);
      const sourceFiles = data.source_files || [];
      renderStats(sourceFiles);
      renderSchema(data.schema_mapping);
      renderCharts();
      renderDrivers();
      renderMix();
      visibleCount = PAGE_SIZE;
      renderTable();
      renderBatchNote(data, sourceFiles);

      const when = data.created_at ? new Date(data.created_at) : new Date();
      $('#topbar-sub').textContent =
        `${plural(predictions.length, 'account')} scored · ${data.source === 'sample' ? 'sample dataset' : 'your upload'}` +
        ` · ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }

    function renderBatchNote(data, sourceFiles) {
      const total = data.entities_total;
      const scored = data.entities_scored ?? predictions.length;
      const note = $('#batch-note');
      if (typeof total === 'number' && total > scored) {
        $('#batch-note-text').textContent =
          `${sourceFiles.length ? `${plural(sourceFiles.length, 'table')} ingested. ` : ''}` +
          `${total.toLocaleString()} entities were resolved but only the first ${scored} were scored — ` +
          `each entity costs one model call, so the MVP caps the batch.`;
        note.classList.remove('hidden');
      } else {
        note.classList.add('hidden');
      }
    }

    function renderStats(sourceFiles) {
      const total = predictions.length;
      const atRisk = predictions.filter((p) => p.prediction.risk_tier !== 'LOW').length;
      const critical = predictions.filter((p) => p.prediction.risk_tier === 'CRITICAL').length;
      const avg = total
        ? predictions.reduce((sum, p) => sum + Number(p.prediction.churn_probability || 0), 0) / total
        : 0;
      const actions = predictions.filter((p) => p.playbook?.action_type).length;
      const tableCount = sourceFiles.length || files.length;

      $('#stat-total').textContent = total;
      $('#stat-total-foot').textContent = `${plural(tableCount, 'source table')} ingested`;

      $('#stat-risk').innerHTML = `${atRisk}<small> / ${total}</small>`;
      $('#stat-risk-foot').textContent = `${critical} in the critical tier`;

      $('#stat-avg').textContent = pct(avg);
      $('#stat-avg-foot').textContent = total ? 'Across the scored cohort' : '—';

      $('#stat-actions').textContent = actions;
      $('#stat-actions-foot').textContent = 'Playbooks generated';

      $('#nav-risk-count').textContent = String(atRisk);
    }

    function renderSchema(schema) {
      $('#primary-key').textContent = schema?.primary_entity_key || 'not detected';
      $('#schema-list').innerHTML = (schema?.tables || []).map((t) => `
        <div class="schema-item">
          <div class="schema-item-top">
            <span class="file-chip-ico" style="width:26px;height:26px">${icon('file')}</span>
            <span class="schema-item-name" title="${escapeHtml(t.file_name)}">${escapeHtml(t.file_name)}</span>
          </div>
          <span class="badge badge-accent">${escapeHtml(String(t.role || 'UNKNOWN').replace(/_/g, ' '))}</span>
          <div class="schema-row"><span class="k">Key</span><span class="v mono">${escapeHtml(t.primary_entity_key || '—')}</span></div>
          ${t.timestamp_column ? `<div class="schema-row"><span class="k">Time</span><span class="v mono">${escapeHtml(t.timestamp_column)}</span></div>` : ''}
          <div class="schema-row"><span class="k">Dropped</span><span class="v">${
            t.noise_columns?.length ? escapeHtml(t.noise_columns.join(', ')) : 'nothing'
          }</span></div>
        </div>`).join('');
    }

    /* Each sector core explains itself under a different key. */
    function driversOf(prediction) {
      if (prediction.primary_drivers?.length) return prediction.primary_drivers.map(String);
      if (prediction.root_cause) return [String(prediction.root_cause)];
      if (prediction.dormancy_type) return [String(prediction.dormancy_type)];
      return [];
    }

    function renderDrivers() {
      const counts = new Map();
      predictions.forEach((p) => {
        // Drivers carry a per-account severity in brackets; group on the reason
        // itself so the same cause is not split across several bars.
        const seen = new Set();
        driversOf(p.prediction).forEach((d) => {
          const reason = d.replace(/\s*\([^)]*\)\s*$/, '').trim() || d;
          if (seen.has(reason)) return;
          seen.add(reason);
          counts.set(reason, (counts.get(reason) || 0) + 1);
        });
      });

      const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
      $('#drivers-empty').classList.toggle('hidden', top.length > 0);

      const max = top[0]?.[1] || 1;
      $('#driver-bars').innerHTML = top.map(([driver, count]) => `
        <div class="bar-row">
          <span class="bar-label" title="${escapeHtml(driver)}">${escapeHtml(driver)}</span>
          <span class="bar-count">${count}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${(count / max * 100).toFixed(1)}%"></span></span>
        </div>`).join('');
    }

    function renderMix() {
      const tally = (pick) => {
        const counts = new Map();
        predictions.forEach((p) => {
          const value = p.playbook?.[pick];
          if (value) counts.set(value, (counts.get(value) || 0) + 1);
        });
        return [...counts.entries()].sort((a, b) => b[1] - a[1]);
      };

      const pills = (entries) => entries.length
        ? entries.map(([name, count]) => `
            <span class="mix-pill">${escapeHtml(String(name).replace(/_/g, ' '))}<span class="n">${count}</span></span>
          `).join('')
        : '<span class="subtle" style="font-size:12.5px">None returned.</span>';

      $('#channel-mix').innerHTML = pills(tally('channel'));
      $('#action-mix').innerHTML = pills(tally('action_type'));
    }

    /* ----- Charts ----- */
    let tierChart = null;
    let spreadChart = null;

    const tierCounts = () => TIERS.map((t) => predictions.filter((p) => p.prediction.risk_tier === t).length);

    const spreadBands = () => {
      const bands = [0, 0, 0, 0, 0];
      predictions.forEach((p) => {
        const v = Number(p.prediction.churn_probability || 0);
        bands[Math.min(Math.floor(v * 5), 4)] += 1;
      });
      return bands;
    };

    function tooltipStyle() {
      return {
        backgroundColor: token('--surface-2'),
        titleColor: token('--text'),
        bodyColor: token('--text-muted'),
        borderColor: token('--border-strong'),
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        boxPadding: 4,
      };
    }

    function renderCharts() {
      if (typeof Chart === 'undefined') return;

      const counts = tierCounts();
      const colors = TIERS.map(tierColor);

      $('#tier-legend').innerHTML = TIERS.map((t, i) => `
        <span class="legend-item">
          <span class="legend-swatch" style="background:${colors[i]}"></span>
          ${t[0]}${t.slice(1).toLowerCase()}
          <span class="legend-val">${counts[i]}</span>
        </span>`).join('');

      tierChart?.destroy();
      tierChart = new Chart($('#chart-tiers'), {
        type: 'doughnut',
        data: {
          labels: TIERS.map((t) => t[0] + t.slice(1).toLowerCase()),
          datasets: [{
            data: counts,
            backgroundColor: colors,
            borderColor: token('--surface'),
            borderWidth: 3,
            hoverOffset: 8,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '64%',
          plugins: { legend: { display: false }, tooltip: tooltipStyle() },
        },
      });

      spreadChart?.destroy();
      spreadChart = new Chart($('#chart-spread'), {
        type: 'bar',
        data: {
          labels: ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%'],
          datasets: [{
            label: 'Accounts',
            data: spreadBands(),
            backgroundColor: [token('--low'), token('--low'), token('--medium'), token('--high'), token('--critical')],
            borderRadius: 6,
            borderSkipped: false,
            maxBarThickness: 46,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: tooltipStyle() },
          scales: {
            x: {
              grid: { display: false },
              border: { color: token('--border') },
              ticks: { color: token('--text-subtle'), font: { size: 11 } },
            },
            y: {
              beginAtZero: true,
              grid: { color: token('--border') },
              border: { display: false },
              ticks: { color: token('--text-subtle'), font: { size: 11 }, precision: 0 },
            },
          },
        },
      });
    }

    theme.onChange(() => {
      if (!predictions.length) return;
      renderCharts();
      renderTable();   // tier colours are baked into the row markup
    });

    /* ----- Table ----- */
    const PAGE_SIZE = 12;
    const tbody = $('#predictions-body');
    const tableEmpty = $('#table-empty');
    const searchInput = $('#table-search');
    const tableFoot = $('#table-foot');

    let filterTier = 'RISK';
    let sortKey = 'churn_probability';
    let sortDir = 'desc';
    let query = '';
    let visibleCount = PAGE_SIZE;

    function matchingRows() {
      return predictions
        .filter((p) => {
          const tier = p.prediction.risk_tier;
          if (filterTier === 'RISK') return tier !== 'LOW';
          if (filterTier === 'ALL') return true;
          return tier === filterTier;
        })
        .filter((p) => !query || String(p.prediction.entity_id).toLowerCase().includes(query))
        .sort((a, b) => {
          let av = a.prediction[sortKey];
          let bv = b.prediction[sortKey];
          if (sortKey === 'risk_tier') { av = TIERS.indexOf(av); bv = TIERS.indexOf(bv); }
          if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
          return sortDir === 'asc' ? av - bv : bv - av;
        });
    }

    /** The rows currently on screen — also the order the drawer pages through. */
    let shownRows = [];

    function renderTable() {
      const all = matchingRows();
      shownRows = all.slice(0, visibleCount);

      $('#table-count').textContent = `${all.length} of ${predictions.length} accounts`;
      tableEmpty.classList.toggle('hidden', all.length > 0);

      const remaining = all.length - shownRows.length;
      tableFoot.classList.toggle('hidden', all.length === 0);
      $('#load-more').classList.toggle('hidden', remaining <= 0);
      $('#load-more-text').textContent = remaining > 0
        ? `${shownRows.length} shown, ${remaining} more`
        : `All ${all.length} shown`;

      tbody.innerHTML = shownRows.map((item, index) => {
        const p = item.prediction;
        const colour = tierColor(p.risk_tier);
        const probability = Number(p.churn_probability || 0);
        return `
          <tr>
            <td>
              <span class="entity-cell">
                <span class="entity-dot" style="background:${colour}"></span>
                <span class="mono">${escapeHtml(p.entity_id)}</span>
              </span>
            </td>
            <td><span class="${tierClass(p.risk_tier)}"><span class="dot"></span>${escapeHtml(p.risk_tier)}</span></td>
            <td>
              <span class="prob-cell">
                <span class="prob-track">
                  <span class="prob-fill" style="width:${(probability * 100).toFixed(1)}%;background:${colour}"></span>
                </span>
                <span class="prob-num">${pct(probability)}</span>
              </span>
            </td>
            <td class="muted">${escapeHtml(item.playbook?.channel || '—')}</td>
            <td style="text-align:right">
              <button class="link-btn" type="button" data-index="${index}">
                Playbook ${icon('arrow-right')}
              </button>
            </td>
          </tr>`;
      }).join('');

      $$('.link-btn', tbody).forEach((btn) => {
        btn.addEventListener('click', () => openDrawer(Number(btn.dataset.index)));
      });
    }

    $('#load-more').addEventListener('click', () => {
      visibleCount += PAGE_SIZE;
      renderTable();
    });

    searchInput.addEventListener('input', () => {
      query = searchInput.value.trim().toLowerCase();
      visibleCount = PAGE_SIZE;
      renderTable();
    });

    $$('#tier-filter button').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('#tier-filter button').forEach((b) => b.classList.toggle('active', b === btn));
        filterTier = btn.dataset.tier;
        visibleCount = PAGE_SIZE;
        renderTable();
      });
    });

    $$('th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (sortKey === key) {
          sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          sortKey = key;
          sortDir = key === 'entity_id' ? 'asc' : 'desc';
        }
        $$('th.sortable').forEach((other) => {
          other.classList.toggle('sorted', other === th);
          $('.sort-ind', other).textContent = other === th ? (sortDir === 'asc' ? '▲' : '▼') : '▲▼';
        });
        renderTable();
      });
    });

    /* ----- Export ----- */
    $('#export-btn').addEventListener('click', () => {
      const header = ['entity_id', 'risk_tier', 'churn_probability', 'channel', 'action_type', 'action_payload', 'drivers'];
      const cell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const rows = matchingRows();
      const csv = [
        header.join(','),
        ...rows.map((item) => [
          item.prediction.entity_id,
          item.prediction.risk_tier,
          item.prediction.churn_probability,
          item.playbook?.channel,
          item.playbook?.action_type,
          item.playbook?.action_payload,
          driversOf(item.prediction).join(' | '),
        ].map(cell).join(',')),
      ].join('\n');

      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `churn-predictions-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast('Export ready', `${plural(rows.length, 'row')} saved as CSV.`, 'ok');
    });

    /* ----- Drawer ----- */
    const drawer = $('#drawer');
    const overlay = $('#overlay');
    let lastFocused = null;
    let drawerIndex = -1;

    function closeDrawer() {
      drawer.classList.remove('open');
      overlay.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
      drawerIndex = -1;
      lastFocused?.focus();
    }

    $('#close-drawer').addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);
    $('#drawer-prev').addEventListener('click', () => openDrawer(drawerIndex - 1, true));
    $('#drawer-next').addEventListener('click', () => openDrawer(drawerIndex + 1, true));

    $('#deploy-btn').addEventListener('click', () => {
      toast('Intervention queued', `${$('#drawer-title').textContent} — handed to the outreach channel.`, 'ok');
      closeDrawer();
    });

    $('#copy-message').addEventListener('click', async () => {
      const message = shownRows[drawerIndex]?.playbook?.action_payload;
      if (!message) return;
      try {
        await navigator.clipboard.writeText(message);
        toast('Copied', 'The outreach message is on your clipboard.', 'ok', 2500);
      } catch {
        toast('Could not copy', 'Your browser blocked clipboard access.', 'error');
      }
    });

    function openDrawer(index, keepFocus = false) {
      if (index < 0 || index >= shownRows.length) return;

      const item = shownRows[index];
      const p = item.prediction;
      const book = item.playbook || {};
      const colour = tierColor(p.risk_tier);
      const probability = Number(p.churn_probability || 0);

      if (!keepFocus) lastFocused = document.activeElement;
      drawerIndex = index;

      $('#drawer-title').textContent = p.entity_id;
      $('#drawer-pos').textContent = `${index + 1} / ${shownRows.length}`;
      $('#drawer-prev').disabled = index === 0;
      $('#drawer-next').disabled = index === shownRows.length - 1;

      const drivers = driversOf(p);
      const driverHeading = p.primary_drivers?.length ? 'Primary drivers'
        : p.root_cause ? 'Root cause'
        : p.dormancy_type ? 'Dormancy type'
        : '';

      const reasoning = drivers.length ? `
        <div>
          <div class="section-title">${icon('trend-down')} ${driverHeading}</div>
          <div class="driver-list">
            ${drivers.map((d, i) => `
              <div class="driver"><span class="driver-num">${drivers.length > 1 ? i + 1 : '!'}</span><span>${escapeHtml(d)}</span></div>
            `).join('')}
          </div>
        </div>` : '';

      const networkFlag = p.regional_network_impact_flag
        ? `<span class="badge badge-high">${icon('signal')} Regional network impact</span>`
        : '';

      $('#drawer-content').innerHTML = `
        <div class="gauge">
          <div class="gauge-ring" style="--pct:${(probability * 100).toFixed(1)};--ring:${colour}">
            <span class="gauge-num">${(probability * 100).toFixed(0)}%</span>
          </div>
          <div class="stack gap-8">
            <span class="${tierClass(p.risk_tier)}"><span class="dot"></span>${escapeHtml(p.risk_tier)} risk</span>
            <span class="subtle" style="font-size:12.5px">Probability of churn in the next cycle</span>
            ${networkFlag}
          </div>
        </div>

        ${reasoning}

        <div>
          <div class="section-title">${icon('zap')} Recommended action</div>
          <div class="playbook-card">
            <div class="playbook-meta">
              <div class="cell"><div class="k">Channel</div><div class="v">${escapeHtml(book.channel || '—')}</div></div>
              <div class="cell"><div class="k">Action</div><div class="v">${escapeHtml(String(book.action_type || '—').replace(/_/g, ' '))}</div></div>
            </div>
            <div class="eyebrow" style="margin-bottom:6px">Message</div>
            <div class="payload">${escapeHtml(book.action_payload || 'No payload returned.')}</div>
          </div>
        </div>`;

      $('#copy-message').disabled = !book.action_payload;

      drawer.classList.add('open');
      overlay.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
      if (!keepFocus) $('#close-drawer').focus();
      $('#drawer-content').scrollTop = 0;
    }

    /* ----- Keyboard shortcuts ----- */
    document.addEventListener('keydown', (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
      const drawerOpen = drawer.classList.contains('open');

      if (e.key === 'Escape') {
        if (drawerOpen) { closeDrawer(); return; }
        if (typing && document.activeElement === searchInput) { searchInput.blur(); return; }
        return;
      }
      if (drawerOpen && !typing) {
        if (e.key === 'ArrowLeft')  { e.preventDefault(); openDrawer(drawerIndex - 1, true); return; }
        if (e.key === 'ArrowRight') { e.preventDefault(); openDrawer(drawerIndex + 1, true); return; }
      }
      if (e.key === '/' && !typing && !drawerOpen && predictions.length) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
    });

    /* ----- Boot: verify the workspace, then restore the last run ----- */
    async function restore() {
      try {
        const check = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}`);
        if (check.status === 404) {
          toast('Workspace expired', 'The server restarted, so this workspace is gone. Registering again…', 'info', 3000);
          setTimeout(signOut, 2600);
          return;
        }

        loadEngineStatus();
        loadSampleInfo();

        const res = await fetch(`/api/v1/analytics/latest?tenant_id=${encodeURIComponent(tenantId)}`);
        if (res.status === 204 || !res.ok) return;   // 204 means nothing has been run yet

        const data = await res.json();
        render(data);
        toast('Previous run restored', `${plural(data.predictions.length, 'account')} loaded from the last analysis.`, 'info', 3200);
      } catch (err) {
        console.error('Restore failed', err);
      }
    }

    renderFiles();
    restore();
  }

  /* ---------- Boot ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    theme.init();
    initOnboarding();
    initDashboard();
  });
})();

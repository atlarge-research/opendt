// recommendations.js

(function(){
  const BYTES_PER_GIB = 1024 ** 3;

  const state = {
    server: null,
    staged: null,
    editing: false,
    editSnapshot: null,
    dirty: false,
    pending: null,
  };

  function clone(value){
    return value === undefined || value === null ? null : JSON.parse(JSON.stringify(value));
  }

  function hasHosts(topo){
    if (!topo || !Array.isArray(topo.clusters)) return false;
    return topo.clusters.some(cluster => Array.isArray(cluster?.hosts) && cluster.hosts.length > 0);
  }

  function escapeHtml(value){
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(value ?? '—').replace(/[&<>"']/g, ch => map[ch]);
  }

  function inputValue(value){
    const num = Number(value);
    return Number.isFinite(num) ? String(num) : '';
  }

  function memToGiB(memory){
    const size = Number(memory?.memorySize ?? NaN);
    if (!Number.isFinite(size) || size <= 0) return '';
    return String(Math.round(size / BYTES_PER_GIB));
  }

  function giBToBytes(value, fallbackBytes){
    const num = Number(value);
    if (!Number.isFinite(num) || num < 0) return fallbackBytes ?? 0;
    return Math.round(num * BYTES_PER_GIB);
  }

  function parseIntField(value, fallback){
    const num = Number(value);
    if (!Number.isFinite(num) || num < 0) return Number.isFinite(fallback) ? Math.round(fallback) : 0;
    return Math.round(num);
  }

  function flattenHosts(topo, fn){
    if (!topo || !Array.isArray(topo.clusters)) return;
    topo.clusters.forEach((cluster, cIdx) => {
      const hosts = Array.isArray(cluster?.hosts) ? cluster.hosts : [];
      hosts.forEach((host, hIdx) => fn(cluster, host, cIdx, hIdx));
    });
  }

  function render(){
    const body = document.querySelector('#recTable tbody');
    const table = document.getElementById('recTable');
    if (!body || !table) return;

    if (!hasHosts(state.staged)){
      body.innerHTML = '<tr><td colspan="6">No recommendation</td></tr>';
      table.classList.toggle('rec-table-editing', false);
      return;
    }

    const rows = [];
    flattenHosts(state.staged, (cluster, host, cIdx, hIdx) => {
      const clusterName = escapeHtml(cluster?.name || '—');
      const hostName = escapeHtml(host?.name || '—');
      const count = Number(host?.count ?? NaN);
      const coreCount = Number(host?.cpu?.coreCount ?? NaN);
      const coreSpeed = Number(host?.cpu?.coreSpeed ?? NaN);
      const memoryGiB = memToGiB(host?.memory);

      if (state.editing){
        rows.push(`
          <tr data-cluster-index="${cIdx}" data-host-index="${hIdx}">
            <td>${clusterName}</td>
            <td>${hostName}</td>
            <td><input class="rec-edit-input" type="number" name="count" min="0" value="${inputValue(count)}"></td>
            <td><input class="rec-edit-input" type="number" name="coreCount" min="0" value="${inputValue(coreCount)}"></td>
            <td><input class="rec-edit-input" type="number" name="coreSpeed" min="0" value="${inputValue(coreSpeed)}"></td>
            <td><input class="rec-edit-input" type="number" name="memoryGiB" min="0" value="${memoryGiB}"></td>
          </tr>
        `);
      } else {
        const memDisplay = memoryGiB === '' ? '—' : memoryGiB;
        rows.push(`
          <tr>
            <td>${clusterName}</td>
            <td>${hostName}</td>
            <td>${Number.isFinite(count) ? Math.round(count) : '—'}</td>
            <td>${Number.isFinite(coreCount) ? Math.round(coreCount) : '—'}</td>
            <td>${Number.isFinite(coreSpeed) ? Math.round(coreSpeed) : '—'}</td>
            <td>${memDisplay}</td>
          </tr>
        `);
      }
    });

    body.innerHTML = rows.join('');
    table.classList.toggle('rec-table-editing', state.editing);
  }

  function updateJSON(){
    const pre = document.getElementById('recJSON');
    if (!pre) return;
    const content = hasHosts(state.staged) ? state.staged : null;
    const text = JSON.stringify(content, null, 2);
    if (pre.textContent !== text) pre.textContent = text;
  }

  function updateButtons(){
    const hasData = hasHosts(state.staged);
    const accept = document.getElementById('btnAcceptRec');
    const edit = document.getElementById('btnEditRec');
    const confirm = document.getElementById('btnConfirmRec');
    const cancel = document.getElementById('btnCancelRec');

    if (accept){
      accept.disabled = !hasData || state.editing;
    }
    if (edit){
      edit.disabled = !hasData || state.editing;
      edit.hidden = state.editing;
    }
    if (confirm){
      confirm.hidden = !state.editing;
      confirm.disabled = !state.editing;
    }
    if (cancel){
      cancel.hidden = !state.editing;
      cancel.disabled = !state.editing;
    }
  }

  function applyPendingIfIdle(){
    if (!state.pending || state.editing || state.dirty) return;
    const next = state.pending;
    state.pending = null;
    ingest(next);
  }

  function ingest(topology){
    const incoming = clone(topology);
    state.server = incoming;
    if (state.editing || state.dirty){
      state.pending = incoming;
      return;
    }
    state.staged = clone(incoming);
    render();
    updateButtons();
    updateJSON();
  }

  function startEditing(){
    if (state.editing || !hasHosts(state.staged)) return;
    state.editing = true;
    state.editSnapshot = clone(state.staged);
    render();
    updateButtons();
  }

  function commitEditing(){
    if (!state.editing) return;
    const table = document.getElementById('recTable');
    if (!table) return;

    table.querySelectorAll('tbody tr').forEach(row => {
      const cIdx = Number(row.dataset.clusterIndex);
      const hIdx = Number(row.dataset.hostIndex);
      const cluster = state.staged?.clusters?.[cIdx];
      const host = cluster && Array.isArray(cluster.hosts) ? cluster.hosts[hIdx] : null;
      if (!cluster || !host) return;

      const countInput = row.querySelector('input[name="count"]');
      const coreInput = row.querySelector('input[name="coreCount"]');
      const speedInput = row.querySelector('input[name="coreSpeed"]');
      const memInput = row.querySelector('input[name="memoryGiB"]');

      host.count = parseIntField(countInput?.value, host.count);
      host.cpu = host.cpu || {};
      host.cpu.coreCount = parseIntField(coreInput?.value, host.cpu.coreCount);
      host.cpu.coreSpeed = parseIntField(speedInput?.value, host.cpu.coreSpeed);

      const fallbackBytes = Number(host.memory?.memorySize ?? NaN);
      const fallbackGiB = Number.isFinite(fallbackBytes) ? fallbackBytes / BYTES_PER_GIB : 0;
      const memGiB = parseIntField(memInput?.value, fallbackGiB);
      host.memory = host.memory || {};
      host.memory.memorySize = giBToBytes(memGiB, fallbackBytes);
    });

    state.editing = false;
    state.editSnapshot = null;
    state.dirty = !deepEqual(state.staged, state.server);
    render();
    updateButtons();
    updateJSON();
    applyPendingIfIdle();
  }

  function cancelEditing(){
    if (!state.editing){
      applyPendingIfIdle();
      return;
    }
    state.staged = clone(state.editSnapshot ?? state.staged);
    state.editing = false;
    state.editSnapshot = null;
    state.dirty = !deepEqual(state.staged, state.server);
    render();
    updateButtons();
    updateJSON();
    applyPendingIfIdle();
  }

  function getTopology(){
    return hasHosts(state.staged) ? clone(state.staged) : null;
  }

  function markSaved(){
    state.server = clone(state.staged);
    state.dirty = false;
    updateButtons();
    updateJSON();
    applyPendingIfIdle();
  }

  function deepEqual(a, b){
    return JSON.stringify(a) === JSON.stringify(b);
  }

  window.recommendationEditor = {
    ingest,
    startEditing,
    commitEditing,
    cancelEditing,
    getTopology,
    markSaved,
    isDirty: () => state.dirty,
    isEditing: () => state.editing,
    refresh: () => { render(); updateButtons(); updateJSON(); },
  };
})();

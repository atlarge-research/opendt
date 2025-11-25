// ui.js

// UI mode / button ripple
document.addEventListener('click', e => {
  const b = e.target.closest('.btn');
  if (!b) return;
  const r = b.getBoundingClientRect();
  b.style.setProperty('--press-x', (e.clientX - r.left) + 'px');
  b.style.setProperty('--press-y', (e.clientY - r.top) + 'px');
});

function setMode(mode){
  document.body.classList.toggle('mode-json', mode === 'json');
  $('#btnModeUI')?.classList.toggle('active', mode === 'ui');
  $('#btnModeJSON')?.classList.toggle('active', mode === 'json');
  localStorage.setItem(modeKey, mode);
  if (window.drawCharts) window.drawCharts();   // <- refresh with new theme
}
window.setMode = setMode;

function applyStatus(status){
  const up = (status||'').toLowerCase() === 'running';
  const btn = $('#toggleBtn');
  if (btn){
    btn.className = 'btn ' + (up ? 'btn-danger' : 'btn-primary');
    btn.innerHTML = up
      ? `<span class="icon" style="--icon-url:var(--sym-stop)"></span>&nbsp;Stop`
      : `<span class="icon" style="--icon-url:var(--sym-play)"></span>&nbsp;Start`;
  }
  const pill = $('#statusPill');
  pill?.classList.toggle('running', up);
  pill?.classList.toggle('stopped', !up);
  $('#statusText') && ($('#statusText').textContent = (status || '—').toUpperCase());
}
window.applyStatus = applyStatus;

async function toggleSystem(){
  const status = ($('#statusText')?.textContent || '').toUpperCase();
  const endpoint = (status === 'RUNNING' || status === 'STARTING') ? '/api/stop' : '/api/start';
  try{ await fetch(endpoint, {method:'POST'}); }catch(e){}
}
window.toggleSystem = toggleSystem;

// SLO submit handler
async function submitSLO() {
  const btn = document.getElementById('submit_slo');
  if (!btn) return;

  try {
    const energy = parseFloat(document.getElementById('energy_input').value);
    const runtime = parseFloat(document.getElementById('runtime_input').value);

    if (isNaN(energy) || isNaN(runtime)) {
      console.error('Invalid input values');
      btn.classList.add('btn-danger');
      setTimeout(() => {
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-primary');
      }, 1000);
      return;
    }

    btn.disabled = true;
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-ghost');

    await fetch('/api/submit_slo', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ energy_target: energy, runtime_target: runtime })
    });

    await window.poll();
  } catch(e) {
    console.error('Failed to submit SLO:', e);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('btn-ghost');
      btn.classList.add('btn-primary');
    }
  }
}
window.submitSLO = submitSLO;

// Recommendation Action
async function acceptRecommendation() {
  const btn = $('#btnAcceptRec');
  if (!btn) return;

  try {
    btn.disabled = true;
    const topology = window.recommendationEditor?.getTopology() || null;
    const payload = topology ? { topology } : {};

    const response = await fetch('/api/accept_recommendation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let detail = '';
      try {
        const err = await response.json();
        detail = err?.error ? `: ${err.error}` : '';
      } catch(_) { /* ignore JSON parse issues */ }
      throw new Error(`HTTP ${response.status}${detail}`);
    }

    if (window.recommendationEditor && typeof window.recommendationEditor.markSaved === 'function') {
      window.recommendationEditor.markSaved();
    }

    await window.poll();
  } catch(e) {
    console.error('Failed to accept recommendation:', e);
  } finally {
    btn.disabled = false;
  }
}
window.acceptRecommendation = acceptRecommendation;


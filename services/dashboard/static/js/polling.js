// polling.js

async function poll(){
  try{
    const r = await fetch('/api/status', {cache:'no-store'});
    const s = await r.json();

    applyStatus(s.status);

    const slo = s?.slo_targets || {};
    const energyField = document.getElementById('energy_input');
    const runtimeField = document.getElementById('runtime_input');

    if (energyField && document.activeElement !== energyField) {
      energyField.value = slo.energy_target ?? '';
    }
    if (runtimeField && document.activeElement !== runtimeField) {
      runtimeField.value = slo.runtime_target ?? '';
    }

    // right-side window pill text
    const wp = document.querySelector('#windowPill');
    if (wp) {
      const n = s.cycle_count ?? null;
      const info = s.current_window || '';
      wp.textContent = n ? `Window ${n}` : (info || '—');
    }

    renderMetrics(s);
    renderOpenDC(s.last_optimization || {}, s);
    renderLLM(s.last_optimization || {});
    renderTopoTable(s.current_topology || null, "currentTopoTable", "currentTopologyJSON");
    //console.log(s);
    renderBest(s.best_config || null);
  }catch(e){}
}
window.poll = poll;


(function () {
  const el = () => document.getElementById('sloCombo');

  // Decide if SLOs are met: both energy and runtime under targets
  function evalSLO(state){
    const slo = state?.slo_targets || {};
    const sim = state?.last_simulation || state?.last_optimization || {};
    const energy   = Number(sim.energy_kwh ?? NaN);
    const runtime  = Number(sim.runtime_hours ?? NaN);
    const eTarget  = Number(slo.energy_target ?? NaN);
    const rTarget  = Number(slo.runtime_target ?? NaN);
    if (!isFinite(energy) || !isFinite(runtime) || !isFinite(eTarget) || !isFinite(rTarget)) return null;
    return (energy <= eTarget) && (runtime <= rTarget);
  }

  // Apply visual state
  function setSLOState(ok){
    const node = el(); if (!node || ok === null) return;
    node.classList.toggle('ok',  ok === true);
    node.classList.toggle('bad', ok === false);
  }

  // Poll /api/status periodically (lightweight)
  async function refreshSLO(){
    try {
      const res = await fetch('/api/status', {cache:'no-store'});
      const state = await res.json();
      setSLOState( evalSLO(state) );
    } catch(e){ /* ignore */ }
  }

  // run on load and every 2s
  window.addEventListener('DOMContentLoaded', () => {
    refreshSLO();
    setInterval(refreshSLO, 2000);
  });

  ['energy_input','runtime_input'].forEach(id=>{
    const n = document.getElementById(id);
    if (n) n.addEventListener('change', refreshSLO);
    if (n) n.addEventListener('input',  () => { /* debounce quick feedback */ });
  });

  const _submitSLO = window.submitSLO;
  if (typeof _submitSLO === 'function') {
    window.submitSLO = async function(){
      const r = await _submitSLO.apply(this, arguments);
      refreshSLO();
      return r;
    }
  }
})();


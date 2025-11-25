// boot.js

setMode(localStorage.getItem(modeKey) || 'ui');

document.addEventListener('DOMContentLoaded', () => {

  init_graphs();
  setInterval(()=>{ drawCharts().catch(()=>{}); }, 5000);

  const energy  = document.getElementById('energy_input');
  const runtime = document.getElementById('runtime_input');
  if (!energy || !runtime || typeof submitSLO !== 'function') return;

  const debounce = (fn, ms=300) => {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  };
  const trigger = debounce(() => submitSLO());

  ['change','input'].forEach(evt => {
    energy.addEventListener(evt, trigger);
    runtime.addEventListener(evt, trigger);
  });
});

setInterval(poll, 2000);
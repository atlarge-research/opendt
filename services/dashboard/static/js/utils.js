// utils.js
const $ = s => document.querySelector(s);
const modeKey = 'opendt-view-mode';

// ---- helpers -------------------------------------------------
function fmt(n, d = 1){ return (n===null||n===undefined||isNaN(n)) ? '—' : Number(n).toFixed(d); }
function pct(n, d = 1){ return (n===null||n===undefined||isNaN(n)) ? '—' : (Number(n)*100).toFixed(d) + '%'; }

// Parse "Window 1: 121 tasks, 1155 fragments"
function parseWindowCounts(info){
  const m = /:\s*([\d,]+)\s*tasks?\s*,\s*([\d,]+)\s*fragments?/i.exec(info || "");
  if (!m) return { tasks: null, frags: null };
  const toInt = s => parseInt(String(s).replace(/,/g,''), 10);
  return { tasks: toInt(m[1]), frags: toInt(m[2]) };
}

// Decide if x looks like real timestamps (very loose check)
function looksLikeDates(arr) {
  if (!arr || !arr.length) return false;
  const v = arr[0];
  return typeof v === 'string' && /\d{4}-\d{2}-\d{2}.*\d{2}:\d{2}/.test(v);
}

// ----- time normalization helpers (fix 1970) -----
function _isBadEpoch(v){
  const d = new Date(v);
  return !isFinite(d) || d.getFullYear() < 2000;
}
function _genTimeline(count, stepMs = 5*60*1000, anchorMs = Date.now()){
  const start = anchorMs - (count - 1) * stepMs;
  const arr = new Array(count);
  for (let i = 0; i < count; i++) arr[i] = new Date(start + i*stepMs).toISOString();
  return arr;
}
function _normalizeX(x, yLen, stepMs = 5*60*1000, anchorMs = Date.now()){
  if (Array.isArray(x) && x.length === yLen && x.length > 0) {
    const first = x.find(v => v != null);
    if (first && !_isBadEpoch(first)) return x;          // already real timestamps
  }
  return _genTimeline(yLen, stepMs, anchorMs);           // fabricate sane "now" timeline
}

// the bar creeps toward the end of its step, so it never stands still; once the twin's first window is done, the
// page reloads to show the twin (the rows follow a variable read at load)
const state = (window.opendtStart ??= { step: 0, since: Date.now() });
const card = () => document.querySelector('.opendt-start');
const step = Number(card()?.dataset.step || 1);
if (step !== state.step) Object.assign(state, { step, since: Date.now() });
state.bar ??= setInterval(() => {
  const el = card();
  if (!el) return;
  const near = 1 - Math.exp(-(Date.now() - state.since) / 20000); // toward the end of the step, never at it
  el.querySelector('.bar div').style.width = (100 * (state.step - 1 + 0.9 * near)) / Number(el.dataset.steps) + '%';
}, 200);
state.ready ??= setInterval(async () => {
  try {
    const { data } = await (await fetch(progress)).json();
    if (!data.length) location.reload();
  } catch {} // the API is not up yet
}, 3000);

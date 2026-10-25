// the bar creeps toward the end of its step, so it never stands still; once the twin's first window is done, the
// page reloads to show the twin (the rows follow a variable read at load)
// the card, copied over the whole screen, which does not scroll until the page reloads: on the page, as a fixed
// element inside the panel would stay in the panel
css('opendt-start-css', 'html, body { overflow: hidden }\n' + style);
const screen = document.getElementById('opendt-start') ?? document.body.appendChild(document.createElement('div'));
screen.id = 'opendt-start';
const width = screen.querySelector('.bar div')?.style.width;  // the bar where it was, not back at 0
screen.innerHTML = context.element.innerHTML;
if (width) screen.querySelector('.bar div').style.width = width;
const state = (window.opendtStart ??= { step: 0, since: Date.now() });
const card = () => document.querySelector('#opendt-start .opendt-start');
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

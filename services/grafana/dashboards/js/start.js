// Grafana's own loading bar (@grafana/ui's LoadingBar, as over a loading panel) moves while the twin starts; once the
// twin's first window is done, the page reloads to show the twin (the rows follow a variable read at load)
// the card, copied over the whole screen, which does not scroll until the page reloads: on the page, as a fixed
// element inside the panel would stay in the panel; the bar beside the copy, so a new copy does not restart it
css('opendt-start-css', 'html, body { overflow: hidden }\n' + style);
let screen = document.getElementById('opendt-start');
if (!screen) {
  screen = document.body.appendChild(document.createElement('div'));
  screen.id = 'opendt-start';
  screen.innerHTML = '<div></div><div class="bar"></div>';
  const bar = screen.lastChild;
  render(bar, (h, ui) => h(ui.LoadingBar, { width: bar.clientWidth, delay: 0 }));
}
const state = (window.opendtStart ??= { step: 0 });
// never a step back: once the twin's first window is done, the panel shows the card of before the API answered (step
// 1) until the page reloads
const step = Number(context.element.querySelector('.opendt-start').dataset.step);
if (step >= state.step) {
  state.step = step;
  screen.firstChild.innerHTML = context.element.innerHTML;
}
state.done ??= setInterval(() => {
  // the twin's time came after the panel had rendered, and hid its row: the twin runs, and the screen goes
  if (context.grafana.replaceVariables('$twin')) {
    clearInterval(state.done);
    clearInterval(state.ready);
    delete window.opendtStart;
    document.getElementById('opendt-start-css').remove();
    screen.remove();
  }
}, 200);
state.ready ??= setInterval(async () => {
  try {
    const { data } = await (await fetch(progress)).json();
    if (!data.length) location.reload();
  } catch {} // the API is not up yet
}, 3000);

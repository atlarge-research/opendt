// the view: Week, Day, or 6 h, the markers, and the interval show at once on a click, kept in the address; Day and
// 6 h follow the twin, to its last hours, at every refresh; always Grafana's kiosk mode (no menus, no bars)
const address = context.grafana.locationService;
const time = context.element.querySelector('[data-time]');
const twin = time.dataset.time;
time.textContent = twin.slice(0, 16).replace('T', ' ');
// the time a window shows: Week, the SURF week; Day or 6 h, the twin's last ones, within the week, to its next full
// hour (the range moves, and the panels ask again, once an hour, not at every window)
const range = (window, twin) => {
  const hours = { day: 24, hours: 6 }[window];
  if (!hours) return week;
  const to = Math.ceil(new Date(twin).getTime() / 3600000) * 3600000;
  const from = Math.max(to - hours * 3600000, new Date(week.from).getTime());
  return { from, to: from + hours * 3600000 };
};
const shown = (key) => context.grafana.replaceVariables('$' + key);
context.element.querySelectorAll('[data-var]').forEach((choice) => {
  const { var: key, value } = choice.dataset;
  if (choice.tagName === 'SELECT') {
    choice.value = shown(key);
    choice.onchange = () => address.partial({ ['var-' + key]: choice.value });
  } else {
    choice.classList.toggle('on', shown(key) === value);
    choice.onclick = () => address.partial({ ['var-' + key]: value, ...(key === 'window' ? range(value, twin) : {}) });
  }
});
// the Tutorial at the step last opened in this browser tab (step.js), not back at step 1, which would set the twin anew
const last = sessionStorage.getItem('opendt-step');
const tutorial = context.element.querySelector('[data-href^="/d/opendt-tutorial"]');
if (last && tutorial) tutorial.href += '&var-step=' + last;
if (!('kiosk' in address.getSearchObject())) address.partial({ kiosk: true }, true);
const { from = week.from, to = week.to } = address.getSearchObject();
const end = Number(to) || Date.parse(to); // the address has milliseconds or an ISO date
const wholeWeek = from === week.from && to === week.to; // Day or 6 h before the twin's time was known
if (twin && shown('window') !== 'week' && (Date.parse(twin) > end || wholeWeek)) {
  address.partial(range(shown('window'), twin), true);
}
// ☀ or ☾, next to the twin's time: the other theme, kept in this browser (light and theme: grafana.js)
const toggle = context.element.querySelector('.theme');
toggle.textContent = light ? '☾' : '☀';
toggle.title = light ? 'Dark' : 'Light';
toggle.onclick = () => {
  localStorage.setItem('opendt-theme', light ? 'dark' : 'light');
  theme(light ? 'dark' : 'light');
};

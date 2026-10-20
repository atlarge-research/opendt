// the view: Week, Day, or 6 h, the markers, and the interval show at once on a click, kept in the address; Day and
// 6 h follow the twin, to its last hours, at every refresh; always Grafana's kiosk mode (no menus, no bars)
const address = context.grafana.locationService;
const time = context.element.querySelector('[data-time]');
const twin = time.dataset.time;
time.textContent = twin.slice(0, 16).replace('T', ' ');
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
if (!('kiosk' in address.getSearchObject())) address.partial({ kiosk: true }, true);
const { from = week.from, to = week.to } = address.getSearchObject();
const end = Number(to) || Date.parse(to); // the address has milliseconds or an ISO date
const wholeWeek = from === week.from && to === week.to; // Day or 6 h before the twin's time was known
if (twin && shown('window') !== 'week' && (Date.parse(twin) > end || wholeWeek)) {
  address.partial(range(shown('window'), twin), true);
}

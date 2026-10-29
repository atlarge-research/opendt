// the view, in Grafana's buttons: the screens, then Week, Day, or 6 h, the markers, and the interval, at once on a
// click, kept in the address; Day and 6 h follow the twin, to its last hours, at every refresh; always Grafana's kiosk
// mode (no menus, no bars)
const address = context.grafana.locationService;
const twin = context.data.twin_time ?? ''; // none until the twin's status answers
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
if (!('kiosk' in address.getSearchObject())) address.partial({ kiosk: true }, true);
const { from = week.from, to = week.to } = address.getSearchObject();
const end = Number(to) || Date.parse(to); // the address has milliseconds or an ISO date
const wholeWeek = from === week.from && to === week.to; // Day or 6 h before the twin's time was known
if (twin && shown('window') !== 'week' && (Date.parse(twin) > end || wholeWeek)) {
  address.partial(range(shown('window'), twin), true);
}
// a screen with the same time and markers; the Tutorial at the step last opened in this browser tab (step.js), not
// back at step 1, which would set the twin anew
const last = sessionStorage.getItem('opendt-step');
const href = (key) => context.grafana.replaceVariables('/d/' + key + '?${__url_time_range}&${markers:queryparam}&kiosk') +
  (key === 'opendt-tutorial' && last ? '&var-step=' + last : '');
// a choice's button: the one shown in blue, the others as text
const look = (on) => ({ size: 'sm', variant: on ? 'primary' : 'secondary', fill: on ? 'solid' : 'text' });
// ☀ or ☾, next to the twin's time: the other theme, kept in this browser (light and theme: grafana.js)
const other = light ? 'dark' : 'light';
const toggle = () => {
  localStorage.setItem('opendt-theme', other);
  theme(other);
};
render(context.element.querySelector('.view'), (h, ui) => {
  // a setting's choices; Week, Day, or 6 h also moves the time shown
  const choose = (key, choices) => h(ui.Stack, { gap: 0.5 }, ...choices.map(([value, label]) => h(ui.Button,
    { ...look(shown(key) === value), onClick: () => address.partial({ ['var-' + key]: value, ...(key === 'window' ? range(value, twin) : {}) }) }, label)));
  const small = (text) => h(ui.Text, { variant: 'bodySmall', color: 'secondary' }, text);
  return h(ui.Stack, { direction: 'column' },
    h(ui.Stack, { justifyContent: 'space-between', alignItems: 'center' },
      h(ui.Stack, { alignItems: 'center', gap: 1.5 }, h('img', { src: '/public/img/opendt.png', height: 36 }), h(ui.Text, { variant: 'h3' }, 'OpenDT')),
      h(ui.Stack, { alignItems: 'center' }, h(ui.Text, { tabular: true }, twin.slice(0, 16).replace('T', ' ')),
        h(ui.ToolbarButton, { tooltip: light ? 'Dark' : 'Light', onClick: toggle }, light ? '☾' : '☀'))),
    h(ui.Stack, { justifyContent: 'space-between', alignItems: 'center' },
      h(ui.Stack, null, ...screens.map(([key, name]) => h(ui.Button, { ...look(key === uid), onClick: () => address.push(href(key)) }, name))),
      plots.length > 0 && h(ui.ToolbarButton, { onClick: pick }, '☰ Plots')),
    h(ui.Stack, { alignItems: 'center' }, choose('window', windows), small('Decisions'), choose('markers', decisions),
      periods.length > 0 && small('Interval'),
      // ${period} in full, so a new interval runs this code again at once (Business Text runs it again for the
      // variables its code names), not only at the next refresh
      periods.length > 0 && h(ui.Combobox, { options: periods.map((value) => ({ value })), value: context.grafana.replaceVariables('${period}'), width: 'auto', onChange: ({ value }) => address.partial({ 'var-period': value }) })));
});

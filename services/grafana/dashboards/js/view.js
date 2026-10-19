// a change shows at once: Period moves the time (Day and 6 h, to the twin's last hours), Decisions shows or hides
// the markers, and Interval sets the plots' interval; the values the screen shows already change nothing
const { id, value } = context.element;
const shown = { window: '${window}', markers: '${markers}', period: '${period}' };
if (shown[id] !== value) {
  const view = { ['var-' + id]: value };
  if (id === 'window') Object.assign(view, range(value, context.panel.initial.twin_time));
  context.grafana.locationService.partial(view);
}

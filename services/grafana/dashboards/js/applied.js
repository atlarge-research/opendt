// the twin has the levers: the form's values are the new baseline (Apply off again), and the view changes;
// refused: the API's reason
const { response, elements, initial } = context.panel;
if (response && response.ok) {
  const changed = Object.fromEntries(elements.filter((e) => e.value !== initial[e.id]).map((e) => [e.id, e.value]));
  context.panel.setInitial({ ...initial, ...changed });
  const url = context.grafana.locationService;
  const view = {};
  if (changed.period) view['var-period'] = changed.period;
  if (changed.markers) view['var-markers'] = changed.markers;
  if (changed.window) {
    const end = new Date(initial.twin_time).getTime();
    const hours = { day: 24, hours: 6 }[changed.window];
    Object.assign(view, hours ? { from: end - hours * 3600000, to: end } : week);
  }
  if (changed.screen) {
    const range = { ...url.getSearchObject(), ...view };
    const { from = week.from, to = week.to } = range;
    url.push(`/d/${changed.screen}?from=${from}&to=${to}&var-markers=${range['var-markers'] || 'on'}`);
  } else {
    url.partial(view);
  }
  context.grafana.notifySuccess(['OpenDT', 'Applied']);
} else if (response) {
  response.json().then(({ detail }) => {
    const reason = typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ');
    context.grafana.notifyError(['OpenDT', reason]);
  });
}

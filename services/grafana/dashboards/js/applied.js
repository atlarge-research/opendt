// the twin has the levers: the form's values are the new baseline (Apply off again), and the view changes;
// refused: the API's reason
const { response, initial } = context.panel;
if (response && response.ok) {
  const sent = Object.fromEntries(changed(context.panel).map((e) => [e.id, e.value]));
  context.panel.setInitial({ ...initial, ...sent });
  const address = context.grafana.locationService;
  const view = {};
  if (sent.period) view['var-period'] = sent.period;
  if (sent.markers) view['var-markers'] = sent.markers;
  if (sent.window) {
    Object.assign(view, { 'var-window': sent.window }, range(sent.window, initial.twin_time));
  }
  if (sent.screen) {
    // not ${markers}: Grafana would put its own variable there
    const { from = week.from, to = week.to, 'var-markers': shown = 'on' } = { ...address.getSearchObject(), ...view };
    address.push(`/d/${sent.screen}?from=${from}&to=${to}&var-markers=${shown}`);
  } else {
    address.partial(view);
  }
  context.grafana.notifySuccess(['OpenDT', 'Applied']);
} else if (response) {
  response.json().then(({ detail }) => {
    const reason = typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ');
    context.grafana.notifyError(['OpenDT', reason]);
  });
}

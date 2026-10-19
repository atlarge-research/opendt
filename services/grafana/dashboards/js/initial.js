// the view as the address has it, the twin's levers as the API has them
const view = { ...start, window: '${window}', period: '${period}', markers: '${markers}' };
context.panel.patchFormValue(view);
context.panel.setInitial({ ...context.panel.initial, ...view });
// a screen that starts on Day or 6 h shows the week until the twin's time is known
const address = context.grafana.locationService;
const { from = week.from, to = week.to } = address.getSearchObject();
if (view.window !== 'week' && from === week.from && to === week.to && context.panel.initial.twin_time) {
  address.partial(range(view.window, context.panel.initial.twin_time), true);
}

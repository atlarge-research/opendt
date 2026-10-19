// the view as the address has it, the twin's levers as the API has them
const view = { window: '${window}', period: '${period}', markers: '${markers}' };
context.panel.patchFormValue(view);
context.panel.setInitial({ ...context.panel.initial, ...view });
// always Grafana's kiosk mode: no menus, no bars
const address = context.grafana.locationService;
if (!('kiosk' in address.getSearchObject())) address.partial({ kiosk: true }, true);
// a screen that starts on Day or 6 h shows the week until the twin's time is known
const { from = week.from, to = week.to } = address.getSearchObject();
if (view.window !== 'week' && from === week.from && to === week.to && context.panel.initial.twin_time) {
  address.partial(range(view.window, context.panel.initial.twin_time), true);
}

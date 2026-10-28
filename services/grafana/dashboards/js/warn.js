// a failure, as Grafana's own warning: in kiosk mode, Grafana drops its error toasts on a dashboard
// (AppNotificationList), so a failed change would say nothing
const warn = (text) => System.import('@grafana/runtime')
  .then((runtime) => runtime.getAppEvents().publish({ type: 'alert-warning', payload: ['OpenDT', text] }))
  .catch(() => context.grafana.notifyError(['OpenDT', text]));

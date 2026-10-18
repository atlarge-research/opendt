// Back or Next: the step `by` away, within the tutorial's steps
const step = Math.min(Math.max(Number('${step}') + by, 1), last);
context.grafana.locationService.partial({ 'var-step': step });
context.panel.enableSubmit();

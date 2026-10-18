// Day and 6 h follow the twin: every 10 s, once its time passes the view's end, the view moves to its last
// hours; one timer per browser tab, though each screen and step mounts the control panel anew
globalThis.followTwin ??= setInterval(async () => {
  const address = context.grafana.locationService;
  const { 'var-window': shown = 'week', to } = address.getSearchObject();
  if (shown === 'week') return;
  const { twin_time } = await (await fetch(status)).json();
  const end = Number(to) || Date.parse(to); // the address has milliseconds or an ISO date
  if (Date.parse(twin_time) > end) address.partial(range(shown, twin_time), true);
}, 10000);

// ☰ Plots opens the plots of the screen by row, ticked while shown, in Grafana's dialog: a tick shows or hides a plot
// at once, a row's tick all of its plots. The address keeps the hidden plots, so a plot added later shows, even with
// an old address. On the page, the dialog outlives the view's refreshes
const pick = () => {
  document.getElementById('opendt-plots') || document.body.insertAdjacentHTML('beforeend', '<div id="opendt-plots"></div>');
  const node = document.getElementById('opendt-plots');
  // kept here: Grafana's $hidden follows the address only at the view's next run
  let hidden = context.grafana.replaceVariables('$' + '{hidden:csv}').split(',');
  const close = () => render(node, () => null);
  const draw = () => render(node, (h, ui) => {
    // a tick for these plots: on while all of them show, a dash while some do
    const tick = (label, keys) => {
      const on = keys.filter((key) => !hidden.includes(key)).length;
      const show = ({ target }) => {
        hidden = hidden.filter((key) => !keys.includes(key)).concat(target.checked ? [] : keys);
        context.grafana.locationService.partial({ 'var-hidden': hidden }, true);
        draw();
      };
      return h(ui.Checkbox, { label, value: on === keys.length, indeterminate: on > 0 && on < keys.length, onChange: show });
    };
    const rows = plots.map(([row, shown]) => h(ui.Stack, { direction: 'column', alignItems: 'flex-start' },
      tick(h(ui.Text, { weight: 'bold' }, row), shown.map(([key]) => key)), ...shown.map(([key, title]) => tick(title, [key]))));
    return h(ui.Modal, { title: 'Plots shown', isOpen: true, onDismiss: close }, h(ui.Grid, { columns: 2, gap: 3 }, ...rows),
      h(ui.Modal.ButtonRow, null, h(ui.Button, { onClick: close }, 'Close')));
  });
  draw();
};

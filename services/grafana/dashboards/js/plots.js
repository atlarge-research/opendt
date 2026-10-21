// ☰ Plots opens the plots of the screen by row, ticked while shown: a tick shows or hides a plot at once, a row's tick
// all of its plots. The address keeps the hidden plots, so a plot added later shows, even with an old address
const hidden = () => context.grafana.replaceVariables('$' + '{hidden:csv}').split(',');
css('opendt-plots', style);
const tick = (value, label, checked) =>
  '<label><input type="checkbox" value="' + value + '"' + (checked ? ' checked' : '') + '>' + label + '</label>';
const rows = Object.fromEntries(plots.map(([row, shown]) => [row, shown.map(([key]) => key)]));
context.element.onclick = ({ target }) => {
  if (!target.closest('.plots')) return;
  const dialog = document.createElement('div');
  dialog.className = 'opendt-plots';
  dialog.innerHTML =
    '<div><b>Plots shown</b><section>' +
    plots.map(([row, shown]) => '<div>' + tick(row, '<b>' + row + '</b>', false) +
      shown.map(([key, title]) => tick(key, title, !hidden().includes(key))).join('') + '</div>').join('') +
    '</section><button>Close</button></div>';
  const box = (value) => dialog.querySelector('[value="' + value + '"]');
  // a row's tick: on while all its plots show, a dash while some do
  const mark = () => Object.entries(rows).forEach(([row, keys]) => {
    const on = keys.filter((key) => box(key).checked).length;
    box(row).checked = on === keys.length;
    box(row).indeterminate = on > 0 && on < keys.length;
  });
  mark();
  dialog.onchange = ({ target }) => {
    const keys = rows[target.value] ?? [target.value];
    keys.forEach((key) => (box(key).checked = target.checked));
    const others = hidden().filter((key) => !keys.includes(key));
    context.grafana.locationService.partial({ 'var-hidden': target.checked ? others : [...others, ...keys] }, true);
    mark();
  };
  dialog.onclick = ({ target }) => {
    if (target === dialog || target.tagName === 'BUTTON') dialog.remove();
  };
  document.body.append(dialog);
};

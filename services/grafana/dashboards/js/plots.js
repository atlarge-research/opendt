// ☰ Plots opens the plots of the screen, ticked while shown; a tick shows or hides one at once. The address keeps
// the hidden plots, so a plot added later shows, even with an old address
const hidden = () => [].concat(context.grafana.locationService.getSearchObject()['var-hidden'] ?? 'none');
if (!document.getElementById('opendt-plots')) {
  document.head.insertAdjacentHTML('beforeend', '<style id="opendt-plots">' + style + '</style>');
}
context.element.onclick = ({ target }) => {
  if (!target.closest('.plots')) return;
  const dialog = document.createElement('div');
  dialog.className = 'opendt-plots';
  dialog.innerHTML =
    '<div><b>Plots shown</b><section>' +
    plots.map(([row, shown]) => '<div><b>' + row + '</b>' + shown.map(([key, title]) =>
      '<label><input type="checkbox" value="' + key + '"' + (hidden().includes(key) ? '' : ' checked') + '>' + title + '</label>').join('') + '</div>').join('') +
    '</section><button>Close</button></div>';
  dialog.onchange = ({ target }) => {
    const others = hidden().filter((key) => key !== target.value);
    context.grafana.locationService.partial({ 'var-hidden': target.checked ? others : [...others, target.value] }, true);
  };
  dialog.onclick = ({ target }) => {
    if (target === dialog || target.tagName === 'BUTTON') dialog.remove();
  };
  document.body.append(dialog);
};

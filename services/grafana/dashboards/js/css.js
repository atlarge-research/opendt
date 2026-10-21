// CSS for what lies outside the panel, added once to the page (the panel renders at every refresh), in the colours
// of Grafana's theme: var(--panel), var(--canvas), var(--line), and var(--ink)
const css = (id, text) => {
  const { background, border, text: ink } = context.grafana.theme.colors;
  const theme = ':root { --panel: ' + background.primary + '; --canvas: ' + background.canvas + '; --line: ' + border.medium + '; --ink: ' + ink.primary + ' }\n';
  document.getElementById(id) || document.head.insertAdjacentHTML('beforeend', '<style id="' + id + '">' + theme + text + '</style>');
};

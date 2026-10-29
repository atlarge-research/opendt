// CSS for what lies outside the panel, added once to the page (the panel renders at every refresh), in the colours
// of Grafana's theme: var(--canvas) and var(--ink)
const css = (id, text) => {
  const { background, text: ink } = context.grafana.theme.colors;
  const theme = ':root { --canvas: ' + background.canvas + '; --ink: ' + ink.primary + ' }\n';
  document.getElementById(id) || document.head.insertAdjacentHTML('beforeend', '<style id="' + id + '">' + theme + text + '</style>');
};

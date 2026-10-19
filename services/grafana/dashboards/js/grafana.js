// none of Grafana's own: no "Powered by Grafana" under the screen, no menus over the panels
const grafana = ['[data-testid="public-dashboard-footer"]', '[data-testid="hover-header-container"]', 'button[aria-label^="Menu for panel"]'];
if (!document.getElementById('opendt-grafana')) {
  document.head.insertAdjacentHTML('beforeend', '<style id="opendt-grafana">' + grafana.join(', ') + ' { display: none !important; }</style>');
}

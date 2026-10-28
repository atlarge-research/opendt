// none of Grafana's own: no "Powered by Grafana" under the screen, no menus over the panels, and no empty box where
// the menu was (Grafana 12.4's test id; a box with the ⓘ of an untitled panel stays)
const grafana = [
  '[data-testid="public-dashboard-footer"]',
  '[data-testid$="hover-header-container"]:has([data-testid="title-items-container"]:empty)',
  'button[aria-label^="Menu for panel"]',
];
css('opendt-grafana', grafana.join(', ') + ' { display: none !important; }');
// light or dark, as last chosen in this browser; Grafana takes its theme from the address, when the page loads
const light = document.body.classList.contains('theme-light');
const theme = (name) => {
  const address = new URL(location.href);
  address.searchParams.set('theme', name);
  location.replace(address);
};
const chosen = localStorage.getItem('opendt-theme');
if (chosen && (chosen === 'light') !== light) theme(chosen);

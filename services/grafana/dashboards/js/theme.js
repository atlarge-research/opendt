// ☀ or ☾, next to the twin's time: the other theme, kept in this browser (after grafana.js)
const toggle = context.element.querySelector('.theme');
toggle.textContent = light ? '☾' : '☀';
toggle.title = light ? 'Dark' : 'Light';
toggle.onclick = () => {
  localStorage.setItem('opendt-theme', light ? 'dark' : 'light');
  theme(light ? 'dark' : 'light');
};

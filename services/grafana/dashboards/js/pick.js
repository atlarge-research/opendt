// the address keeps the hidden plots, so a plot added later shows, even with an old address
if (context.element.id === 'plots') {
  const others = '${hidden:csv}'.split(',').filter((p) => !mine.includes(p));
  const off = mine.filter((p) => !context.element.value.includes(p));
  context.grafana.locationService.partial({ 'var-hidden': [...others, ...off] }, true);
}

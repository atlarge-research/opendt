// the links as Grafana fills them in now (the time, the markers, ...), again at every refresh
context.element.querySelectorAll('[data-href]').forEach((a) => (a.href = context.grafana.replaceVariables(a.dataset.href)));

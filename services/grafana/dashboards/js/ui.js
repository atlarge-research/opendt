// Grafana's own components (@grafana/ui) drawn in `node`, in Grafana's theme, anew at each call, e.g.
// render(node, (h, ui) => h(ui.Button, { onClick }, 'Apply')) with h being React.createElement; the node keeps its
// React root, so components in a panel whose content never changes (no {{...}}) stay over its refreshes
const render = (node, draw) =>
  Promise.all(['react', 'react-dom', '@grafana/ui'].map((name) => System.import(name))).then(([React, ReactDOM, ui]) => {
    node.root ??= ReactDOM.createRoot(node);
    node.root.render(React.createElement(ui.ThemeContext.Provider, { value: context.grafana.theme }, draw(React.createElement, ui)));
  });

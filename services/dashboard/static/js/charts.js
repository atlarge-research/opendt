const PLOTLY_CONFIG = {
  responsive: true,
  displaylogo: false,
  displayModeBar: false,
  modeBarButtonsToRemove: ['lasso2d','select2d','autoScale2d','toggleSpikelines']
};

let UIREVISION = 'persist-zoom';

const COLORS = {
  real: '#56B4E9',
  sim:  '#D55E00',
  grid: 'rgba(0,0,0,0.12)'
};

function layoutFor(_title) {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor:  'rgba(0,0,0,0)',
    margin: { l: 60, r: 140, t: 20, b: 80 },
    font: { color: '#000' },
    uirevision: UIREVISION, // <-- persist zoom

    legend: {
      x: 1.02, y: 1, xanchor: 'left', yanchor: 'top',
      bgcolor: 'rgba(0,0,0,0)', bordercolor: 'rgba(0,0,0,0.08)',
      borderwidth: 0, orientation: 'v', font: { size: 13, color: '#000' }
    },

    xaxis: {
      title: { text: 'Time', font: { color: '#000' } },
      tickfont: { color: '#000' },
      type: 'date',
      gridcolor: COLORS.grid,
      zeroline: false,
      rangeslider: { visible: false }
    },

    yaxis: {
      gridcolor: COLORS.grid,
      zeroline: false,
      tickfont: { color: '#000' },
      title: { font: { color: '#000' } }
    }
  };
}

async function fetchTS() {
  const r = await fetch('/api/sim/timeseries', { cache: 'no-store' });
  if (!r.ok) throw new Error('timeseries fetch failed');
  return r.json();
}

const PLOTS = {
  cpu_usages: {
    range: [0, 100],
    autorange: false,
    title: 'Average CPU Utilization [%]',
    legend: 'Average CPU Utilization [%]',
    transform: value => value * 100,
  },
  power_usages: {
    autorange: true,
    title: 'Power [kWh]',
    legend: 'Power [kWh]',
  }
};

function mapValues(values, transform) {
  if (!Array.isArray(values)) return [];
  if (typeof transform !== 'function') return values;
  return values.map(v => {
    if (v === null || v === undefined) return null;
    const numeric = Number(v);
    if (!Number.isFinite(numeric)) return null;
    return transform(numeric);
  });
}

function drawPlot(plot_name, x, y, extraConfigLayout, isNew = false) {
  const trace = {
    x, y,
    mode: 'lines',
    name: (extraConfigLayout && extraConfigLayout.legend) || plot_name,
    line: { color: COLORS.real, width: 2 }
  };

  // base layout
  const layout = layoutFor('');

  // always anchor plots to zero on the y-axis
  layout.yaxis = {
    ...layout.yaxis,
    rangemode: 'tozero',
  };

  // apply y-axis config from plot-specific settings
  if (extraConfigLayout) {
    layout.yaxis = {
      ...layout.yaxis,
      ...(extraConfigLayout.range ? { range: extraConfigLayout.range } : {}),
      ...(extraConfigLayout.autorange !== undefined ? { autorange: extraConfigLayout.autorange } : {})
    };
    if (extraConfigLayout.title) {
      layout.yaxis.title = {
        ...(layout.yaxis.title || {}),
        text: '',
      };
    }
  }

  const el = document.getElementById(plot_name);
  if (!el) {
    console.warn(`drawPlot: missing <div id="${plot_name}">`);
    return;
  }

  const data = [trace]; // <-- MUST be an array
  if (isNew) {
    Plotly.newPlot(el, data, layout, PLOTLY_CONFIG);
  } else {
    Plotly.react(el, data, layout, PLOTLY_CONFIG);
  }
}

function init_graphs() {
  Object.keys(PLOTS).forEach(plot_name => {
    drawPlot(plot_name, [], [], PLOTS[plot_name], true);
  });
}

async function drawCharts() {
  try {
    const d = await fetchTS();
   
    const xValues = Array.isArray(d.timestamps) ? d.timestamps : [];
    Object.keys(PLOTS).forEach(plot_name => {
      const cfg = PLOTS[plot_name] || {};
      const yValues = mapValues(d[plot_name], cfg.transform);
      drawPlot(plot_name, xValues, yValues, cfg);
    });
  } catch (err) {
    console.error('drawCharts error:', err);
  }
}

function startSse() {
  try {
    const es = new EventSource('/api/stream');
    es.onmessage = () => drawCharts();
    es.onerror = () => es.close();
  } catch (_) {}
}

// Make sure DOM is ready and the divs exist
document.addEventListener('DOMContentLoaded', () => {
  init_graphs();
  drawCharts();
  // startSse(); // enable if your SSE is live
});

window.init_graphs = init_graphs;
window.drawCharts = drawCharts;
window.startSse = startSse;

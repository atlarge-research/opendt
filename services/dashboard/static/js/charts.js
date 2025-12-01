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

async function fetchPowerData() {
  const r = await fetch('/api/power?interval_seconds=60', { cache: 'no-store' });
  if (!r.ok) {
    // If the endpoint returns 404 or 500, return empty data
    console.warn('Power data fetch failed:', r.status);
    return { data: [], metadata: {} };
  }
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
    title: 'Power [kW]',
    legend: 'Power [kW]',
    dual: true,  // This plot has two traces
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

function drawPowerPlot(powerData) {
  const el = document.getElementById('power_usages');
  if (!el) {
    console.warn('drawPowerPlot: missing <div id="power_usages">');
    return;
  }

  // Extract timestamps and power values (convert W to kW)
  const timestamps = powerData.map(d => d.timestamp);
  const simulated = powerData.map(d => d.simulated_power / 1000);
  const actual = powerData.map(d => d.actual_power / 1000);

  // Create two traces
  const traceSimulated = {
    x: timestamps,
    y: simulated,
    mode: 'lines',
    name: 'Simulated',
    line: { color: COLORS.sim, width: 2 }
  };

  const traceActual = {
    x: timestamps,
    y: actual,
    mode: 'lines',
    name: 'Actual',
    line: { color: COLORS.real, width: 2 }
  };

  // Create layout
  const layout = layoutFor('');
  layout.yaxis = {
    ...layout.yaxis,
    rangemode: 'tozero',
    autorange: true
  };

  const data = [traceActual, traceSimulated];
  Plotly.react(el, data, layout, PLOTLY_CONFIG);
}

async function drawCharts() {
  try {
    // Fetch power data from new endpoint
    const response = await fetchPowerData();
    
    if (response.data && response.data.length > 0) {
      drawPowerPlot(response.data);
      
      // Update metadata display if needed
      if (response.metadata) {
        console.log('Power data metadata:', response.metadata);
      }
    } else {
      console.log('No power data available yet');
    }
  } catch (err) {
    console.error('drawCharts error:', err);
  }
}

let powerPollingInterval = null;

function startPowerPolling(intervalMs = 5000) {
  // Clear any existing interval
  if (powerPollingInterval) {
    clearInterval(powerPollingInterval);
  }
  
  // Start polling
  powerPollingInterval = setInterval(() => {
    drawCharts();
  }, intervalMs);
  
  console.log(`Power data polling started (interval: ${intervalMs}ms)`);
}

function stopPowerPolling() {
  if (powerPollingInterval) {
    clearInterval(powerPollingInterval);
    powerPollingInterval = null;
    console.log('Power data polling stopped');
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
  
  // Start polling for power data every 5 seconds
  startPowerPolling(5000);
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  stopPowerPolling();
});

window.init_graphs = init_graphs;
window.drawCharts = drawCharts;
window.startSse = startSse;
window.startPowerPolling = startPowerPolling;
window.stopPowerPolling = stopPowerPolling;

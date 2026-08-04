// Balanza Comercial page script
// Data source: trade_argentina table from DoltHub
const DOLTHUB_OWNER = 'rbasa';
const DOLTHUB_REPO = 'macroeconomia';
const DOLTHUB_BRANCH = 'main';
const BASE_URL = `https://www.dolthub.com/api/v1alpha1/${DOLTHUB_OWNER}/${DOLTHUB_REPO}/${DOLTHUB_BRANCH}`;

const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };

async function fetchDolt(sql) {
  const params = new URLSearchParams({ q: sql });
  const url = `${BASE_URL}?${params.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const payload = await response.json();
  return payload.rows || [];
}

function calculatePercentChange(currentValue, previousValue) {
  if (currentValue == null || previousValue == null) return null;
  if (previousValue === 0) return null;
  return (currentValue / previousValue - 1) * 100;
}

function parseNumericRow(rawRow) {
  const parsedRow = { period: rawRow.period };

  Object.keys(rawRow).forEach((columnName) => {
    if (columnName === 'period') return;
    parsedRow[columnName] = rawRow[columnName] == null || rawRow[columnName] === undefined
      ? null
      : parseFloat(rawRow[columnName]);
  });

  return parsedRow;
}

function getLastItems(items, count) {
  return items.slice(Math.max(items.length - count, 0));
}

function formatDateLabel(dateString) {
  const date = new Date(dateString);
  try {
    const formatted = new Intl.DateTimeFormat('es-AR', {
      year: 'numeric',
      month: 'long',
      timeZone: 'UTC'
    }).format(date);
    return formatted.charAt(0).toUpperCase() + formatted.slice(1);
  } catch (error) {
    return dateString;
  }
}

// Extract YYYY-MM from date for grouping
function getPeriodLabel(dateString) {
  if (!dateString) return '';
  return dateString.substring(0, 7); // YYYY-MM
}

// Series chart: Exportaciones e Importaciones
function renderSeriesChart(containerId, seriesData) {
  const xValues = seriesData.map((row) => row.period);
  const traces = [
    {
      x: xValues,
      y: seriesData.map((row) => row.exportaciones_usd),
      name: 'Exportaciones',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#2b8cbe', width: 2 }
    },
    {
      x: xValues,
      y: seriesData.map((row) => row.importaciones_usd),
      name: 'Importaciones',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#de2d26', width: 2 }
    }
  ];

  const layout = {
    title: '',
    xaxis: { tickformat: '%Y-%m' },
    yaxis: { title: 'Millones de USD' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, traces, layout, PLOTLY_CONFIG);
}

// Balance chart: Barras mostrando balanza por período
function renderBalanceChart(containerId, seriesData) {
  const xValues = seriesData.map((row) => row.period);
  const balanceValues = seriesData.map((row) => row.balanza_comercial_usd);
  
  // Colores: verde si superávit, rojo si déficit
  const colors = balanceValues.map((val) => val >= 0 ? '#31a354' : '#e74c3c');

  const trace = {
    x: xValues,
    y: balanceValues,
    type: 'bar',
    marker: { color: colors }
  };

  const layout = {
    title: '',
    xaxis: { tickformat: '%Y-%m' },
    yaxis: { title: 'Millones de USD' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, [trace], layout, PLOTLY_CONFIG);
}

// YoY % variations for Exportaciones
function renderExportacionesYoYChart(containerId, seriesData) {
  const parsedData = seriesData.map(parseNumericRow);
  const yoyChanges = [];

  for (let index = 12; index < parsedData.length; index += 1) {
    const currentRow = parsedData[index];
    const previousYearRow = parsedData[index - 12];

    yoyChanges.push({
      period: currentRow.period,
      yoy_pct: calculatePercentChange(currentRow.exportaciones_usd, previousYearRow.exportaciones_usd)
    });
  }

  const last24Months = getLastItems(yoyChanges, 24);
  const xValues = last24Months.map((row) => row.period);
  const yValues = last24Months.map((row) => row.yoy_pct);
  
  const colors = yValues.map((val) => val >= 0 ? '#3182bd' : '#e74c3c');

  const trace = {
    x: xValues,
    y: yValues,
    type: 'bar',
    marker: { color: colors }
  };

  const layout = {
    title: '',
    xaxis: { tickangle: -45 },
    yaxis: { title: '%' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, [trace], layout, PLOTLY_CONFIG);
}

// YoY % variations for Importaciones
function renderImportacionesYoYChart(containerId, seriesData) {
  const parsedData = seriesData.map(parseNumericRow);
  const yoyChanges = [];

  for (let index = 12; index < parsedData.length; index += 1) {
    const currentRow = parsedData[index];
    const previousYearRow = parsedData[index - 12];

    yoyChanges.push({
      period: currentRow.period,
      yoy_pct: calculatePercentChange(currentRow.importaciones_usd, previousYearRow.importaciones_usd)
    });
  }

  const last24Months = getLastItems(yoyChanges, 24);
  const xValues = last24Months.map((row) => row.period);
  const yValues = last24Months.map((row) => row.yoy_pct);
  
  const colors = yValues.map((val) => val >= 0 ? '#31a354' : '#e74c3c');

  const trace = {
    x: xValues,
    y: yValues,
    type: 'bar',
    marker: { color: colors }
  };

  const layout = {
    title: '',
    xaxis: { tickangle: -45 },
    yaxis: { title: '%' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, [trace], layout, PLOTLY_CONFIG);
}

// Top stats (indicadores clave)
function renderTopStats(latestRow, previousYearRow, accum12m, accumYTD) {
  const balanceUltimo = latestRow.balanza_comercial_usd;

  const statsHtml = `
    <div class="stat-card"><div class="stat-label">Última observación</div><div class="stat-value">${formatDateLabel(latestRow.period)}</div></div>
    <div class="stat-card"><div class="stat-label">Balanza (último mes)</div><div class="stat-value">${balanceUltimo.toFixed(0)} M USD</div></div>
    <div class="stat-card"><div class="stat-label">Balanza acumulada (últimos 12 meses)</div><div class="stat-value">${accum12m.toFixed(0)} M USD</div></div>
    <div class="stat-card"><div class="stat-label">Balanza acumulada YTD</div><div class="stat-value">${accumYTD.toFixed(0)} M USD</div></div>
  `;

  const statsContainer = document.getElementById('stats');
  if (statsContainer) {
    statsContainer.innerHTML = statsHtml;
  }
}

// Calculate acumulado últimos 12 meses
function calculateAccum12M(data) {
  const last12 = data.slice(Math.max(0, data.length - 12));
  return last12.reduce((sum, row) => sum + row.balanza_comercial_usd, 0);
}

// Calculate acumulado YTD (desde enero del año actual)
function calculateAccumYTD(data) {
  if (data.length === 0) return 0;
  const lastRow = data[data.length - 1];
  const lastYear = parseInt(lastRow.period.split('-')[0], 10);
  
  let ytdSum = 0;
  for (let i = data.length - 1; i >= 0; i--) {
    const row = data[i];
    const rowYear = parseInt(row.period.split('-')[0], 10);
    if (rowYear === lastYear) {
      ytdSum += row.balanza_comercial_usd;
    } else {
      break;
    }
  }
  return ytdSum;
}

async function loadBalanzaComercial() {
  try {
    const sql = `SELECT period, exportaciones_usd, importaciones_usd, balanza_comercial_usd FROM trade_argentina ORDER BY period ASC`;
    const rows = await fetchDolt(sql);

    if (!rows || rows.length < 13) {
      throw new Error('Datos insuficientes en trade_argentina');
    }

    const parsedRows = rows.map(parseNumericRow);
    const latestRow = parsedRows[parsedRows.length - 1];
    const previousYearRow = parsedRows[parsedRows.length - 13];
    const latestLabel = formatDateLabel(latestRow.period);
    
    const accum12m = calculateAccum12M(parsedRows);
    const accumYTD = calculateAccumYTD(parsedRows);

    renderTopStats(latestRow, previousYearRow, accum12m, accumYTD);
    renderSeriesChart('chart_series', parsedRows);
    renderBalanceChart('chart_balance', parsedRows);
    renderExportacionesYoYChart('chart_expo_yoy', parsedRows);
    renderImportacionesYoYChart('chart_impo_yoy', parsedRows);

    const loadingElement = document.getElementById('loading');
    if (loadingElement) loadingElement.style.display = 'none';

    const contentElement = document.getElementById('content');
    if (contentElement) contentElement.style.display = 'block';

    const lastUpdatedElement = document.getElementById('lastUpdated');
    if (lastUpdatedElement) {
      lastUpdatedElement.textContent = `Último dato: ${latestLabel}`;
    }
  } catch (error) {
    console.error('Balanza Comercial error', error);

    const loadingElement = document.getElementById('loading');
    if (loadingElement) loadingElement.style.display = 'none';

    const errorElement = document.getElementById('error');
    if (errorElement) {
      errorElement.style.display = 'block';
      errorElement.textContent = `Error al cargar Balanza Comercial: ${error.message}`;
    }
  }
}

window.addEventListener('DOMContentLoaded', loadBalanzaComercial);

// EMAE page script
const DOLTHUB_OWNER = 'rbasa';
const DOLTHUB_REPO = 'macroeconomia';
const DOLTHUB_BRANCH = 'main';
const BASE_URL = `https://www.dolthub.com/api/v1alpha1/${DOLTHUB_OWNER}/${DOLTHUB_REPO}/${DOLTHUB_BRANCH}`;

const SERIES_COLUMNS = ['indice', 'indice_desestacionalizado', 'indice_tendencia_ciclo'];
const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };
const COMPONENT_COLUMNS = [
  'agricultura_ganaderia_caza_silvicultura',
  'pesca',
  'explotacion_minas_canteras',
  'industria_manufacturera',
  'electricidad_gas_agua',
  'construccion',
  'comercio_mayorista_minorista_reparaciones',
  'hoteles_restaurantes',
  'transporte_comunicaciones',
  'intermediacion_financiera',
  'actividades_inmobiliarias_empresariales_alquiler',
  'administracion_publica_defensa_seguridad_social',
  'ensenanza',
  'servicios_sociales_salud',
  'otras_actividades_servicios_comunitarios',
  'impuestos_netos_subsidios'
];

const SHORT_LABELS = {
  agricultura_ganaderia_caza_silvicultura: 'Agro',
  pesca: 'Pesca',
  explotacion_minas_canteras: 'Minería',
  industria_manufacturera: 'Industria',
  electricidad_gas_agua: 'Energía',
  construccion: 'Construcción',
  comercio_mayorista_minorista_reparaciones: 'Comercio',
  hoteles_restaurantes: 'Turismo',
  transporte_comunicaciones: 'Transporte',
  intermediacion_financiera: 'Finanzas',
  actividades_inmobiliarias_empresariales_alquiler: 'Inmobiliaria',
  administracion_publica_defensa_seguridad_social: 'Sector público',
  ensenanza: 'Enseñanza',
  servicios_sociales_salud: 'Salud',
  otras_actividades_servicios_comunitarios: 'Otros',
  impuestos_netos_subsidios: 'Impuestos'
};

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
  const parsedRow = { periodo: rawRow.periodo };

  Object.keys(rawRow).forEach((columnName) => {
    if (columnName === 'periodo') return;
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
  const match = String(dateString).match(/^(\d{4})-(\d{2})/);

  if (match) {
    const year = parseInt(match[1], 10);
    const monthIndex = parseInt(match[2], 10) - 1;

    try {
      const formatted = new Intl.DateTimeFormat('es-AR', {
        year: 'numeric',
        month: 'long',
        timeZone: 'UTC'
      }).format(new Date(Date.UTC(year, monthIndex, 1)));

      return formatted.charAt(0).toUpperCase() + formatted.slice(1);
    } catch (error) {
      return `${match[2]}/${match[1]}`;
    }
  }

  const parsedDate = new Date(dateString);
  const fallback = parsedDate.toLocaleDateString('es-AR', { year: 'numeric', month: 'long' });
  return fallback.charAt(0).toUpperCase() + fallback.slice(1);
}

function getComponentLabel(columnName) {
  if (SHORT_LABELS[columnName]) return SHORT_LABELS[columnName];

  return columnName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getComponentColumns(row) {
  const excludedColumns = ['periodo', 'indice_desestacionalizado', 'indice_tendencia_ciclo'];
  return Object.keys(row).filter((columnName) => !excludedColumns.includes(columnName));
}

function renderMainSeriesChart(containerId, seriesData) {
  const xValues = seriesData.map((row) => row.periodo);
  const traces = [
    {
      x: xValues,
      y: seriesData.map((row) => row.indice),
      name: 'Índice',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#667eea' }
    },
    {
      x: xValues,
      y: seriesData.map((row) => row.indice_desestacionalizado),
      name: 'Índice Desest.',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#50bc1d' }
    },
    {
      x: xValues,
      y: seriesData.map((row) => row.indice_tendencia_ciclo),
      name: 'Tendencia-Ciclo',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#f65555' }
    }
  ];

  const layout = {
    title: '',
    xaxis: { tickformat: '%Y-%m' },
    yaxis: { title: 'Índice' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, traces, layout, PLOTLY_CONFIG);
}

function renderInterannualChart(containerId, seriesData) {
  const parsedData = seriesData.map(parseNumericRow);
  const interannualChanges = [];

  for (let index = 24; index < parsedData.length; index += 1) {
    const currentRow = parsedData[index];
    const previousYearRow = parsedData[index - 12];

    interannualChanges.push({
      periodo: currentRow.periodo,
      indice: calculatePercentChange(currentRow.indice, previousYearRow.indice),
      tendencia: calculatePercentChange(currentRow.indice_tendencia_ciclo, previousYearRow.indice_tendencia_ciclo)
    });
  }

  const last24Months = getLastItems(interannualChanges, 24);
  const xValues = last24Months.map((row) => row.periodo);

  const traceIndex = {
    x: xValues,
    y: last24Months.map((row) => row.indice),
    type: 'bar',
    name: 'Índice EMAE',
    marker: { color: '#2ca02c' }
  };
  const traceTrend = {
    x: xValues,
    y: last24Months.map((row) => row.tendencia),
    type: 'bar',
    name: 'Tendencia-Ciclo EMAE',
    marker: { color: '#d62728' }
  };

  const layout = {
    title: '',
    barmode: 'group',
    xaxis: { tickangle: -45 },
    yaxis: { title: '%' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, [traceIndex, traceTrend], layout, PLOTLY_CONFIG);
}

function renderMonthlyChangeChart(containerId, seriesData) {
  const parsedData = seriesData.map(parseNumericRow);
  const monthlyChanges = [];

  for (let index = 1; index < parsedData.length; index += 1) {
    const currentRow = parsedData[index];
    const previousRow = parsedData[index - 1];

    monthlyChanges.push({
      periodo: currentRow.periodo,
      indice: calculatePercentChange(currentRow.indice_tendencia_ciclo, previousRow.indice_tendencia_ciclo),
      desest: calculatePercentChange(currentRow.indice_desestacionalizado, previousRow.indice_desestacionalizado)
    });
  }

  const last24Months = getLastItems(monthlyChanges, 24);
  const xValues = last24Months.map((row) => row.periodo);

  const traceIndex = {
    x: xValues,
    y: last24Months.map((row) => row.indice),
    type: 'bar',
    name: 'Mensual Índice Tendencia-Ciclo',
    marker: { color: '#636efa' }
  };
  const traceDesest = {
    x: xValues,
    y: last24Months.map((row) => row.desest),
    type: 'bar',
    name: 'Mensual Desest.',
    marker: { color: '#ef553b' }
  };

  const layout = {
    title: '',
    barmode: 'group',
    xaxis: { tickangle: -45 },
    yaxis: { title: '%' },
    legend: { orientation: 'h', y: -0.2 }
  };

  Plotly.newPlot(containerId, [traceIndex, traceDesest], layout, PLOTLY_CONFIG);
}

function renderComponentComparisonCharts(containerIdMonthly, containerInterannual, fullData) {
  const parsedData = fullData.map(parseNumericRow);
  const latestRow = parsedData[parsedData.length - 1];
  const previousRow = parsedData[parsedData.length - 2];
  const samePeriodLastYear = parsedData[parsedData.length - 13];
  const componentColumns = getComponentColumns(latestRow);

  const monthlyValues = [];
  const interannualValues = [];
  const labels = [];

  componentColumns.forEach((columnName) => {
    labels.push(getComponentLabel(columnName));
    monthlyValues.push(calculatePercentChange(latestRow[columnName], previousRow[columnName]));
    interannualValues.push(calculatePercentChange(latestRow[columnName], samePeriodLastYear[columnName]));
  });

  const traceMonthly = {
    x: labels,
    y: monthlyValues,
    type: 'bar',
    marker: { color: '#7cb5ec' }
  };
  const traceInterannual = {
    x: labels,
    y: interannualValues,
    type: 'bar',
    marker: { color: '#90ed7d' }
  };

  const layout = {
    title: '',
    xaxis: { tickangle: -45, automargin: true },
    yaxis: { title: '%' }
  };

  Plotly.newPlot(containerIdMonthly, [traceMonthly], layout, PLOTLY_CONFIG);
  Plotly.newPlot(containerInterannual, [traceInterannual], layout, PLOTLY_CONFIG);
}

function renderTopStats(latestRow, previousRow, previousYearRow) {
  const interannualChange = calculatePercentChange(latestRow.indice, previousYearRow.indice);
  const monthlyDesestChange = calculatePercentChange(latestRow.indice_desestacionalizado, previousRow.indice_desestacionalizado);
  const monthlyTendenciaChange = calculatePercentChange(latestRow.indice_tendencia_ciclo, previousRow.indice_tendencia_ciclo);

  const statsHtml = `
    <div class="stat-card"><div class="stat-label">Última observación</div><div class="stat-value">${formatDateLabel(latestRow.periodo)}</div></div>
    <div class="stat-card"><div class="stat-label">Última variación interanual</div><div class="stat-value">${interannualChange != null ? interannualChange.toFixed(2) + '%' : 'N/A'}</div></div>
    <div class="stat-card"><div class="stat-label">Última variación mensual (desest.)</div><div class="stat-value">${monthlyDesestChange != null ? monthlyDesestChange.toFixed(2) + '%' : 'N/A'}</div></div>
    <div class="stat-card"><div class="stat-label">Última variación mensual (Tendencia-ciclo)</div><div class="stat-value">${monthlyTendenciaChange != null ? monthlyTendenciaChange.toFixed(2) + '%' : 'N/A'}</div></div>
  `;

  const statsContainer = document.getElementById('stats');
  if (statsContainer) {
    statsContainer.innerHTML = statsHtml;
  }
}

function updateChartTitles(latestLabel) {
  const titleInterannual = document.getElementById('title_interannual');
  if (titleInterannual) {
    titleInterannual.textContent = `Variación interanual — ${latestLabel}`;
  }

  const titleMonthly = document.getElementById('title_monthly');
  if (titleMonthly) {
    titleMonthly.textContent = `Variación mensual — ${latestLabel}`;
  }

  const titleComponentsMonthly = document.getElementById('title_components_monthly');
  if (titleComponentsMonthly) {
    titleComponentsMonthly.textContent = `Variaciones mensuales ${latestLabel}`;
  }

  const titleComponentsInterannual = document.getElementById('title_components_interannual');
  if (titleComponentsInterannual) {
    titleComponentsInterannual.textContent = `Variaciones interanuales ${latestLabel}`;
  }
}

async function loadEmae() {
  try {
    const sql = `SELECT * FROM emae ORDER BY periodo ASC`;
    const rows = await fetchDolt(sql);

    if (!rows || rows.length < 13) {
      throw new Error('Datos insuficientes en emae');
    }

    const parsedRows = rows.map(parseNumericRow);
    const latestRow = parsedRows[parsedRows.length - 1];
    const previousRow = parsedRows[parsedRows.length - 2];
    const previousYearRow = parsedRows[parsedRows.length - 13];
    const latestLabel = formatDateLabel(latestRow.periodo);

    renderTopStats(latestRow, previousRow, previousYearRow);
    renderMainSeriesChart('chart_series', parsedRows);
    updateChartTitles(latestLabel);
    renderInterannualChart('chart_interannual', parsedRows);
    renderMonthlyChangeChart('chart_monthly', parsedRows);
    renderComponentComparisonCharts('chart_components_monthly', 'chart_components_interannual', parsedRows);

    const loadingElement = document.getElementById('loading');
    if (loadingElement) loadingElement.style.display = 'none';

    const contentElement = document.getElementById('content');
    if (contentElement) contentElement.style.display = 'block';

    const lastUpdatedElement = document.getElementById('lastUpdated');
    if (lastUpdatedElement) {
      lastUpdatedElement.textContent = `Último dato: ${latestLabel}`;
    }
  } catch (error) {
    console.error('EMAE error', error);

    const loadingElement = document.getElementById('loading');
    if (loadingElement) loadingElement.style.display = 'none';

    const errorElement = document.getElementById('error');
    if (errorElement) {
      errorElement.style.display = 'block';
      errorElement.textContent = `Error al cargar EMAE: ${error.message}`;
    }
  }
}

window.addEventListener('DOMContentLoaded', loadEmae);

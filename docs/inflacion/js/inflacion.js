// Inflacion page script - fetch IPC data and render charts
const DOLTHUB_OWNER = 'rbasa';
const DOLTHUB_REPO = 'macroeconomia';
const DOLTHUB_BRANCH = 'main';
const BASE_URL = `https://www.dolthub.com/api/v1alpha1/${DOLTHUB_OWNER}/${DOLTHUB_REPO}/${DOLTHUB_BRANCH}`;

async function fetchDolt(sql) {
    const params = new URLSearchParams({ q: sql });
    const url = `${BASE_URL}?${params.toString()}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const j = await resp.json();
    return j.rows || [];
}

function fmtMonth(dateStr) {
    // dateStr expected YYYY-MM-DD
    const d = new Date(dateStr);
    return d.toLocaleDateString('es-AR', { year: 'numeric', month: 'short' });
}

function calculateRates(rows) {
    // rows: array of objects with fecha and nivel_general (index values), ordered by fecha asc
    const res = rows.map(r => ({ fecha: r.fecha, nivel: parseFloat(r.nivel_general), nucleo: r.nucleo ? parseFloat(r.nucleo) : null }));
    const full = rows.map(r => ({
        ...r,
        nivel_general: r.nivel_general != null ? parseFloat(r.nivel_general) : null,
        nucleo: r.nucleo != null ? parseFloat(r.nucleo) : null
    }));

    // monthly change (percent)
    const monthly = [];
    for (let i = 1; i < res.length; i++) {
        const prev = res[i-1].nivel;
        const cur = res[i].nivel;
        const pct = (cur / prev - 1) * 100;
        monthly.push({ fecha: res[i].fecha, value: pct });
    }

    // interannual (12 months)
    const interannual = [];
    const nucleo_inter = [];
    for (let i = 12; i < res.length; i++) {
        const prev = res[i-12].nivel;
        const cur = res[i].nivel;
        const pct = (cur / prev - 1) * 100;
        interannual.push({ fecha: res[i].fecha, value: pct });

        // nucleo interanual if available
        if (res[i].nucleo != null && res[i-12] && res[i-12].nucleo != null) {
            const nucCur = res[i].nucleo;
            const nucPrev = res[i-12].nucleo;
            nucleo_inter.push({ fecha: res[i].fecha, value: (nucCur / nucPrev - 1) * 100 });
        } else {
            nucleo_inter.push({ fecha: res[i].fecha, value: null });
        }
    }

    return { monthly, interannual, nucleo_inter, full };
}

function createBarChartMonthly(containerId, monthly) {
    const last24 = monthly.slice(-24);
    const x = last24.map(d => d.fecha);
    const y = last24.map(d => d.value);
    const trace = { x, y, type: 'bar', marker: { color: '#ff7f0e' }, name: 'Inflación mensual %' };
    const layout = { title: 'Inflación mensual (últimos 24 meses)', xaxis: { title: 'Mes' }, yaxis: { title: '% mensual' } };
    Plotly.newPlot(containerId, [trace], layout, {responsive:true});
}

function createInterannualChart(containerId, interannual, nucleo_inter) {
    const last24 = interannual.slice(-24);
    const x = last24.map(d => d.fecha);
    const y = last24.map(d => d.value);
    const nuc = nucleo_inter.slice(-24).map(d => d ? d.value : null);

    const bar = { x, y, type: 'bar', name: 'Interanual %', marker: { color: '#2ca02c' } };
    const line = { x, y: nuc, type: 'scatter', mode: 'lines+markers', name: 'Núcleo interanual', line: { color: '#d62728', width: 2 } };

    const layout = { title: 'Inflación interanual (últimos 24 meses)', xaxis: { title: 'Mes' }, yaxis: { title: '% interanual' } };
    Plotly.newPlot(containerId, [bar, line], layout, {responsive:true});
}

function createComponentVariationChart(containerId, columns, values, title, color, traceName) {
    const labels = [];
    const vals = [];

    columns.forEach(c => {
        const value = values && values[c.key] != null ? values[c.key] : null;
        if (value != null && !Number.isNaN(value)) {
            labels.push(c.label);
            vals.push(value);
        }
    });

    if (!labels.length) {
        const container = document.getElementById(containerId);
        if (container) container.innerHTML = '<div class="chart-empty">No hay datos para mostrar</div>';
        return;
    }

    const trace = { x: labels, y: vals, type: 'bar', name: traceName, marker: { color } };
    const layout = {
        title,
        xaxis: { automargin: true, title: 'Componente' },
        yaxis: { title: 'Variación %' }
    };
    Plotly.newPlot(containerId, [trace], layout, { responsive: true });
}

function displayTopStats(latestDate, monthlyLast, interannualLast) {
    const statsHtml = `
        <div class="stat-card">
            <div class="stat-label">Inflación a la fecha</div>
            <div class="stat-value">${latestDate}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Interanual</div>
            <div class="stat-value">${interannualLast != null ? interannualLast.toFixed(2) + '%' : 'N/A'}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Mensual</div>
            <div class="stat-value">${monthlyLast != null ? monthlyLast.toFixed(2) + '%' : 'N/A'}</div>
        </div>
    `;
    const statsEl = document.getElementById('stats');
    if (statsEl) statsEl.innerHTML = statsHtml;
}

// Main loader
async function loadInflacion() {
    try {
        // Request last 36 months to be safe
        const sql = `SELECT fecha, nivel_general, nucleo, estacional, bienes, servicios, alimentos_bebidas_no_alcoholicas, bebidas_alcoholicas_tabaco, prendas_vestir_calzado, vivienda_agua_electricidad_gas_combustibles, equipamiento_mantenimiento_hogar, salud, transporte, comunicacion, recreacion_cultura, educacion, restaurantes_hoteles, bienes_servicios_varios FROM ipc_argentina ORDER BY fecha ASC`;
        const rows = await fetchDolt(sql);
        if (!rows || rows.length === 0) throw new Error('No hay datos de IPC');

        // Calculate rates
        const { monthly, interannual, nucleo_inter, full } = calculateRates(rows);

        // Update last updated
        const lastDate = full.length ? full[full.length-1].fecha : 'N/A';
        const lastMonthly = monthly.length ? monthly[monthly.length-1].value : null;
        const lastInter = interannual.length ? interannual[interannual.length-1].value : null;

        const lastUpdatedEl = document.getElementById('lastUpdated');
        if (lastUpdatedEl) lastUpdatedEl.textContent = `Última actualización: ${new Date().toLocaleString('es-AR')}`;

        displayTopStats(lastDate, lastMonthly, lastInter);

        createBarChartMonthly('chart_monthly', monthly);
        createInterannualChart('chart_interannual', interannual, nucleo_inter);

        // Latest components chart using most recent variation values
        const latestRow = full[full.length-1];
        const prevRow = full[full.length-2];
        const yearAgoRow = full[full.length-13];
        const cols = [
            { key: 'nivel_general', label: 'Nivel general' },
            { key: 'alimentos_bebidas_no_alcoholicas', label: 'Alimentos' },
            { key: 'bebidas_alcoholicas_tabaco', label: 'Bebidas y tabaco' },
            { key: 'prendas_vestir_calzado', label: 'Prendas y calzado' },
            { key: 'vivienda_agua_electricidad_gas_combustibles', label: 'Vivienda' },
            { key: 'equipamiento_mantenimiento_hogar', label: 'Equipamiento hogar' },
            { key: 'salud', label: 'Salud' },
            { key: 'transporte', label: 'Transporte' },
            { key: 'comunicacion', label: 'Comunicación' },
            { key: 'recreacion_cultura', label: 'Recreación' },
            { key: 'educacion', label: 'Educación' },
            { key: 'restaurantes_hoteles', label: 'Restaurantes y hoteles' },
            { key: 'bienes_servicios_varios', label: 'Otros' }
        ];

        const monthlyChanges = {};
        const interannualChanges = {};
        cols.forEach(c => {
            const cur = latestRow && latestRow[c.key] != null ? parseFloat(latestRow[c.key]) : null;
            const prev = prevRow && prevRow[c.key] != null ? parseFloat(prevRow[c.key]) : null;
            const prevYear = yearAgoRow && yearAgoRow[c.key] != null ? parseFloat(yearAgoRow[c.key]) : null;

            if (cur != null && prev != null && !Number.isNaN(cur) && !Number.isNaN(prev)) {
                monthlyChanges[c.key] = (cur / prev - 1) * 100;
            }
            if (cur != null && prevYear != null && !Number.isNaN(cur) && !Number.isNaN(prevYear)) {
                interannualChanges[c.key] = (cur / prevYear - 1) * 100;
            }
        });

        createComponentVariationChart('chart_latest_monthly', cols, monthlyChanges, `Variación mensual por componente (último período: ${lastDate})`, '#ff7f0e', 'Mensual');
        createComponentVariationChart('chart_latest_interannual', cols, interannualChanges, `Variación interanual por componente (último período: ${lastDate})`, '#2ca02c', 'Interanual');

        const seriesCols = [
            { key: 'estacional', label: 'Estacional' },
            { key: 'nucleo', label: 'Núcleo' },
            { key: 'bienes', label: 'Bienes' },
            { key: 'servicios', label: 'Servicios' }
        ];

        const monthlySeriesChanges = {};
        const interannualSeriesChanges = {};
        seriesCols.forEach(c => {
            const cur = latestRow && latestRow[c.key] != null ? parseFloat(latestRow[c.key]) : null;
            const prev = prevRow && prevRow[c.key] != null ? parseFloat(prevRow[c.key]) : null;
            const prevYear = yearAgoRow && yearAgoRow[c.key] != null ? parseFloat(yearAgoRow[c.key]) : null;

            if (cur != null && prev != null && !Number.isNaN(cur) && !Number.isNaN(prev)) {
                monthlySeriesChanges[c.key] = (cur / prev - 1) * 100;
            }
            if (cur != null && prevYear != null && !Number.isNaN(cur) && !Number.isNaN(prevYear)) {
                interannualSeriesChanges[c.key] = (cur / prevYear - 1) * 100;
            }
        });

        createComponentVariationChart('chart_series_monthly', seriesCols, monthlySeriesChanges, `Inflación mensual del último período - Estacional/Núcleo/Bienes/Servicios`, '#1f77b4', 'Mensual');
        createComponentVariationChart('chart_series_interannual', seriesCols, interannualSeriesChanges, `Inflación interanual del último período - Estacional/Núcleo/Bienes/Servicios`, '#9467bd', 'Interanual');

        // Hide loading, show content
        const loadingEl = document.getElementById('loading'); if (loadingEl) loadingEl.style.display = 'none';
        const contentEl = document.getElementById('content'); if (contentEl) contentEl.style.display = 'block';

    } catch (err) {
        console.error('Inflation load error', err);
        const loadingEl = document.getElementById('loading'); if (loadingEl) loadingEl.style.display = 'none';
        const errorEl = document.getElementById('error'); if (errorEl) { errorEl.style.display = 'block'; errorEl.textContent = `Error al cargar IPC: ${err.message}`; }
    }
}

window.addEventListener('DOMContentLoaded', loadInflacion);

import { useEffect, useMemo, useState } from 'react'

import { fetchDolt } from '../api/dolt'
import ChartCard from '../components/ChartCard'
import PlotlyChart from '../components/PlotlyChart'
import StatCard from '../components/StatCard'
import { createBarTrace, createLineTrace } from '../utils/charts'
import { formatDate, formatNumber, formatPercentage } from '../utils/formatters'
import { normalizeNumericRows } from '../utils/series'

const DAILY_TABLE = 'financial_sector_argentina'
const BALANCE_TABLE = 'bcra_balance_argentina'
const FX_TABLE = 'fx_rate'
const FIRST_YEAR = 2017
const BCRA_DAILY_SOURCE = 'https://www.bcra.gob.ar/principales-variables/'
const BCRA_LIQUIDITY_SOURCE =
  'https://www.bcra.gob.ar/normas-especiales-para-la-divulgacion-de-datos-fmi/'
const BCRA_BANK_REPORT_SOURCE = 'https://www.bcra.gob.ar/informe-sobre-bancos/'
const BCRA_BALANCE_SOURCE =
  'https://www.bcra.gob.ar/balances-y-agregados-monetarios/'
const BCRA_BALANCE_METHOD =
  'https://www.bcra.gob.ar/pdfs/publicacionesestadisticas/bolmetes.pdf'
const BLUE_SOURCE =
  'https://www.ambito.com/contenidos/dolar-informal-historico.html'

const DAILY_COLUMNS = [
  'reservas_internacionales_millones_usd',
  'reservas_netas_liquidez_millones_usd',
  'drenajes_netos_corto_plazo_millones_usd',
  'compras_divisas_millones_usd',
  'm2_millones_ars',
  'base_monetaria_millones_ars',
  'badlar_bancos_privados_tna',
  'tamar_bancos_privados_tna',
  'creditos_sector_privado_millones_ars',
  'creditos_sector_privado_millones_usd',
  'depositos_sector_privado_millones_usd',
  'morosidad_sector_privado_porcentaje',
  'morosidad_empresas_porcentaje',
  'morosidad_familias_porcentaje',
]

const BALANCE_COLUMNS = [
  'activos_externos_netos_millones_ars',
  'activos_sector_oficial_millones_ars',
  'adelantos_transitorios_millones_ars',
  'titulos_publicos_millones_ars',
  'creditos_entidades_financieras_millones_ars',
  'fuentes_absorcion_millones_ars',
  'depositos_totales_bcra_millones_ars',
  'titulos_emitidos_bcra_millones_ars',
]

async function fetchDailyRows() {
  const currentYear = new Date().getFullYear()
  const chunks = []
  for (let year = FIRST_YEAR; year <= currentYear; year += 1) {
    chunks.push(fetchDolt(`
      SELECT periodo AS period, ${DAILY_COLUMNS.join(', ')}
      FROM ${DAILY_TABLE}
      WHERE periodo >= '${year}-01-01'
        AND periodo < '${year + 1}-01-01'
      ORDER BY periodo ASC
    `))
  }
  return (await Promise.all(chunks)).flat()
}

function fetchBalanceRows() {
  return fetchDolt(`
    SELECT periodo AS period, ${BALANCE_COLUMNS.join(', ')}
    FROM ${BALANCE_TABLE}
    ORDER BY periodo ASC
  `)
}

function fetchBlueRows() {
  return fetchDolt(`
    SELECT DATE_FORMAT(DATE, '%Y-%m') AS period,
      CAST(SUBSTRING_INDEX(
        GROUP_CONCAT(rate ORDER BY DATE DESC), ',', 1
      ) AS DECIMAL(20, 6)) AS rate
    FROM ${FX_TABLE}
    WHERE pair = 'USDB_ARS' AND kind = 'ask'
      AND DATE >= '${FIRST_YEAR}-01-01'
    GROUP BY DATE_FORMAT(DATE, '%Y-%m')
    ORDER BY period ASC
  `)
}

function latestValue(rows, key) {
  return [...rows].reverse().find((row) => Number.isFinite(row[key]))
}

function monthlyValues(rows, key, aggregate = 'last') {
  const months = new Map()
  rows.forEach((row) => {
    if (!Number.isFinite(row[key])) return
    const period = row.period?.slice(0, 7)
    const previous = months.get(period) ?? 0
    months.set(period, aggregate === 'sum' ? previous + row[key] : row[key])
  })
  return [...months].map(([period, value]) => ({ period, value }))
}

function calculateAnnualChanges(rows, key) {
  const monthly = monthlyValues(rows, key)
  return monthly.slice(12).map((current, index) => ({
    period: current.period,
    value: monthly[index].value
      ? ((current.value / monthly[index].value) - 1) * 100
      : null,
  }))
}

function buildMonetaryExchangeRows(dailyRows, blueRows) {
  const reserves = new Map(monthlyValues(
    dailyRows,
    'reservas_internacionales_millones_usd',
  ).map((row) => [row.period, row.value]))
  const blue = new Map(monthlyValues(blueRows, 'rate').map(
    (row) => [row.period, row.value],
  ))

  return monthlyValues(dailyRows, 'm2_millones_ars').flatMap((row) => {
    const reserveValue = reserves.get(row.period)
    if (!Number.isFinite(reserveValue) || reserveValue <= 0) return []
    const monetaryDollar = row.value / reserveValue
    const blueValue = blue.get(row.period)
    return [{
      period: row.period,
      monetaryDollar,
      blue: blueValue,
      percentageDifference: Number.isFinite(blueValue)
        ? ((monetaryDollar / blueValue) - 1) * 100
        : null,
    }]
  })
}

function buildCreditQualityRows(rows) {
  const seriesMap = (key) => new Map(monthlyValues(rows, key).map(
    (row) => [row.period, row.value],
  ))
  const credits = seriesMap('creditos_sector_privado_millones_ars')
  const companies = seriesMap('morosidad_empresas_porcentaje')
  const families = seriesMap('morosidad_familias_porcentaje')

  return monthlyValues(rows, 'morosidad_sector_privado_porcentaje').map(
    (row) => {
      const credit = credits.get(row.period)
      return {
        period: row.period,
        ratio: row.value,
        companies: companies.get(row.period),
        families: families.get(row.period),
        estimatedDelinquent: Number.isFinite(credit)
          ? credit * row.value / 100
          : null,
      }
    },
  )
}

function datedUnit(unit, row) {
  return row?.period ? `${unit} · al ${formatDate(row.period)}` : unit
}

function hasChartData(data) {
  return data.some((trace) => trace.y?.some(Number.isFinite))
}

function FinancialPlot({ data, layout, height = 410 }) {
  if (!hasChartData(data)) {
    return <div className="chart-empty" role="status">No hay observaciones disponibles para este gráfico.</div>
  }
  return <PlotlyChart data={data} layout={layout} height={height} />
}

function SectionHeading({ number, title, children }) {
  return (
    <div className="financial-section-heading">
      <h2>{number}. {title}</h2>
      {children}
    </div>
  )
}

function FinancialSector() {
  const [dailyRows, setDailyRows] = useState([])
  const [balanceRows, setBalanceRows] = useState([])
  const [blueRows, setBlueRows] = useState([])
  const [balanceError, setBalanceError] = useState(null)
  const [blueError, setBlueError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function loadData() {
      try {
        const [dailyData, balanceResult, blueResult] = await Promise.all([
          fetchDailyRows(),
          fetchBalanceRows()
            .then((data) => ({ data, error: null }))
            .catch((loadError) => ({ data: [], error: loadError })),
          fetchBlueRows()
            .then((data) => ({ data, error: null }))
            .catch((loadError) => ({ data: [], error: loadError })),
        ])
        if (!cancelled) {
          setDailyRows(normalizeNumericRows(dailyData, ['period']))
          setBalanceRows(normalizeNumericRows(balanceResult.data, ['period']))
          setBlueRows(normalizeNumericRows(blueResult.data, ['period']))
          setBalanceError(balanceResult.error?.message ?? null)
          setBlueError(blueResult.error?.message ?? null)
        }
      } catch (loadError) {
        if (!cancelled) setError(loadError.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadData()
    return () => { cancelled = true }
  }, [])

  const analysis = useMemo(() => {
    const monetaryExchange = buildMonetaryExchangeRows(dailyRows, blueRows)
    const creditQuality = buildCreditQualityRows(dailyRows)
    return {
      reserves: latestValue(dailyRows, 'reservas_internacionales_millones_usd'),
      netReserves: latestValue(dailyRows, 'reservas_netas_liquidez_millones_usd'),
      m2: latestValue(dailyRows, 'm2_millones_ars'),
      monetaryBase: latestValue(dailyRows, 'base_monetaria_millones_ars'),
      badlar: latestValue(dailyRows, 'badlar_bancos_privados_tna'),
      tamar: latestValue(dailyRows, 'tamar_bancos_privados_tna'),
      creditArs: latestValue(dailyRows, 'creditos_sector_privado_millones_ars'),
      creditUsd: latestValue(dailyRows, 'creditos_sector_privado_millones_usd'),
      depositsUsd: latestValue(dailyRows, 'depositos_sector_privado_millones_usd'),
      delinquency: latestValue(dailyRows, 'morosidad_sector_privado_porcentaje'),
      reservePurchases: monthlyValues(
        dailyRows, 'compras_divisas_millones_usd', 'sum',
      ).slice(-24),
      m2Monthly: monthlyValues(dailyRows, 'm2_millones_ars').slice(-60),
      monetaryBaseMonthly: monthlyValues(
        dailyRows, 'base_monetaria_millones_ars',
      ).slice(-60),
      m2AnnualChange: calculateAnnualChanges(
        dailyRows, 'm2_millones_ars',
      ).slice(-48),
      monetaryExchange,
      gapRows: monetaryExchange.filter((row) => Number.isFinite(row.blue)),
      creditQuality,
      latestCreditQuality: creditQuality.at(-1),
    }
  }, [blueRows, dailyRows])

  if (loading) return <div className="loading"><div className="loading-spinner" />Cargando sector financiero...</div>
  if (error) return <div className="error">Error al cargar el sector financiero: {error}</div>
  if (!dailyRows.length) return <p>No hay datos financieros disponibles.</p>

  const dailyPeriod = dailyRows.at(-1)?.period
  const balancePeriod = balanceRows.at(-1)?.period

  return (
    <div className="page financial-sector-page">
      <header className="page-header">
        <h1>Sector Financiero</h1>
        <p className="subtitle">Reservas, mercado cambiario, dinero, tasas, crédito y balance del BCRA</p>
        <p className="last-updated">
          Indicadores diarios hasta {formatDate(dailyPeriod)}
          {balancePeriod && ` · Balance hasta ${formatDate(balancePeriod)}`}
        </p>
      </header>

      <section className="financial-section">
        <SectionHeading number="1" title="Reservas internacionales brutas y netas">
          <p className="source-note">
            Fuentes: <a href={BCRA_DAILY_SOURCE} target="_blank" rel="noreferrer">BCRA — series monetarias</a>
            {' '}y <a href={BCRA_LIQUIDITY_SOURCE} target="_blank" rel="noreferrer">BCRA — reservas y liquidez en moneda extranjera</a>.
          </p>
        </SectionHeading>
        <div className="stats comparison-stats">
          <StatCard label="Reservas internacionales brutas (RIB)" value={formatNumber(analysis.reserves?.reservas_internacionales_millones_usd)} subinfo={datedUnit('Millones de USD', analysis.reserves)} />
          <StatCard label="Reservas netas de liquidez (RIN)" value={formatNumber(analysis.netReserves?.reservas_netas_liquidez_millones_usd)} subinfo={datedUnit('Millones de USD', analysis.netReserves)} />
        </div>
        <div className="chart-row financial-chart-row">
          <ChartCard title="Reservas internacionales brutas" subtitle="Stock diario oficial del BCRA, en millones de USD.">
            <FinancialPlot data={[createLineTrace(dailyRows, 'RIB', { yKey: 'reservas_internacionales_millones_usd', mode: 'lines' })]} layout={{ yaxis: { title: 'Millones de USD' } }} />
          </ChartCard>
          <ChartCard title="Reservas netas de liquidez" subtitle="Serie mensual; vencimiento residual de hasta un año.">
            <p className="chart-description">
              RIN = activos de reserva oficiales menos préstamos, depósitos,
              repos y otras obligaciones netas de corto plazo de la autoridad
              monetaria. Excluye al Gobierno Central y derivados no entregables
              liquidados en pesos. No es la meta RIN de un programa del FMI,
              que puede aplicar otras valuaciones y ajustes.
            </p>
            <FinancialPlot data={[createLineTrace(dailyRows, 'RIN de liquidez', { yKey: 'reservas_netas_liquidez_millones_usd', mode: 'lines+markers' })]} layout={{ yaxis: { title: 'Millones de USD' } }} />
          </ChartCard>
        </div>
      </section>

      <section className="financial-section">
        <SectionHeading number="2" title="Compra de divisas"><p>Factor diario publicado por el BCRA, agregado por mes.</p></SectionHeading>
        <ChartCard title="Compras de divisas — últimos 24 meses" subtitle="Suma mensual; excluye operaciones directas con el Tesoro Nacional.">
          <p className="chart-description">
            No equivale necesariamente a las operaciones concertadas del
            reporte mensual: aquí importa la fecha de liquidación y el Sistema
            de Pagos en Monedas Locales (SML) puede generar diferencias. Los
            pagos de deuda, organismos, encajes y valuaciones son otros factores
            de reservas: una cancelación de deuda puede reducir el stock aunque
            las compras de divisas del mes sean positivas.
          </p>
          <FinancialPlot data={[createBarTrace(analysis.reservePurchases, 'Compras de divisas', { xKey: 'period', yKey: 'value', positiveColor: '#38a169', negativeColor: '#e53e3e' })]} layout={{ yaxis: { title: 'Millones de USD' } }} />
        </ChartCard>
      </section>

      <section className="financial-section">
        <SectionHeading number="3" title="Tasas de interés"><p>Depósitos a plazo fijo mayoristas de bancos privados, expresados como TNA.</p></SectionHeading>
        <div className="stats comparison-stats">
          <StatCard label="BADLAR bancos privados" value={formatPercentage(analysis.badlar?.badlar_bancos_privados_tna)} subinfo={datedUnit('TNA', analysis.badlar)} />
          <StatCard label="TAMAR bancos privados" value={formatPercentage(analysis.tamar?.tamar_bancos_privados_tna)} subinfo={datedUnit('TNA', analysis.tamar)} />
        </div>
        <ChartCard title="BADLAR y TAMAR">
          <FinancialPlot data={[
            createLineTrace(dailyRows, 'BADLAR', { yKey: 'badlar_bancos_privados_tna', mode: 'lines' }),
            createLineTrace(dailyRows, 'TAMAR', { yKey: 'tamar_bancos_privados_tna', mode: 'lines' }),
          ]} layout={{ yaxis: { title: 'TNA (%)' } }} />
        </ChartCard>
      </section>

      <section className="financial-section">
        <SectionHeading number="4" title="Agregado monetario M2">
          <p>M2 incluye circulante y depósitos transaccionales; la base monetaria es circulación más depósitos en pesos de entidades en el BCRA. M2 también incorpora dinero bancario, por eso es más amplio.</p>
        </SectionHeading>
        <div className="stats comparison-stats">
          <StatCard label="M2" value={formatNumber(analysis.m2?.m2_millones_ars)} subinfo={datedUnit('Millones de ARS', analysis.m2)} />
          <StatCard label="Base monetaria" value={formatNumber(analysis.monetaryBase?.base_monetaria_millones_ars)} subinfo={datedUnit('Millones de ARS', analysis.monetaryBase)} />
        </div>
        <div className="chart-row financial-chart-row">
          <ChartCard title="M2 y base monetaria — trayectoria" subtitle="Último saldo diario de cada mes, en millones de ARS.">
            <FinancialPlot data={[
              createLineTrace(analysis.m2Monthly, 'M2', { mode: 'lines' }),
              createLineTrace(analysis.monetaryBaseMonthly, 'Base monetaria', { mode: 'lines' }),
            ]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
          </ChartCard>
          <ChartCard title="M2 — variación interanual" subtitle="El mes en curso puede estar incompleto y no ser comparable con un cierre mensual.">
            <FinancialPlot data={[createBarTrace(analysis.m2AnnualChange, 'Variación interanual', { xKey: 'period', yKey: 'value', positiveColor: '#667eea', negativeColor: '#e53e3e' })]} layout={{ yaxis: { title: 'Variación interanual (%)' } }} />
          </ChartCard>
        </div>
      </section>

      <section className="financial-section">
        <SectionHeading number="5" title="M2 sobre reservas brutas"><p>Indicador monetario comparativo; no es un tipo de cambio de equilibrio ni una proyección.</p></SectionHeading>
        <ChartCard title="M2 / reservas internacionales brutas" subtitle="Último dato de cada mes; millones de ARS divididos por millones de USD.">
          <FinancialPlot data={[createLineTrace(analysis.monetaryExchange, 'M2 / RIB', { yKey: 'monetaryDollar', mode: 'lines' })]} layout={{ yaxis: { title: 'ARS por USD' } }} />
        </ChartCard>
      </section>

      <section className="financial-section">
        <SectionHeading number="6" title="Brecha contra el dólar blue"><p>Diferencia porcentual entre M2/RIB y el blue vendedor del mismo mes.</p></SectionHeading>
        {blueError && <p className="data-unavailable-detail">No se pudo cargar el dólar blue: {blueError}</p>}
        <ChartCard title="Brecha M2/RIB frente al dólar blue" subtitle="(M2/RIB ÷ dólar blue vendedor − 1) × 100.">
          <FinancialPlot data={[createBarTrace(analysis.gapRows, 'Brecha porcentual', { xKey: 'period', yKey: 'percentageDifference', positiveColor: '#667eea', negativeColor: '#e53e3e' })]} layout={{
            yaxis: { title: 'Brecha (%)' },
            shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0, y1: 0, line: { color: '#718096', width: 1 } }],
          }} />
          <p className="source-note chart-source-note">Fuentes: BCRA para M2 y reservas; <a href={BLUE_SOURCE} target="_blank" rel="noreferrer">Ámbito Financiero para dólar blue</a>.</p>
        </ChartCard>
      </section>

      <section className="financial-section">
        <SectionHeading number="7" title="Crédito y morosidad">
          <p className="source-note">Fuente: BCRA — series monetarias y <a href={BCRA_BANK_REPORT_SOURCE} target="_blank" rel="noreferrer">Informe sobre Bancos</a>.</p>
        </SectionHeading>
        <div className="stats financial-credit-stats">
          <StatCard label="Crédito privado total" value={formatNumber(analysis.creditArs?.creditos_sector_privado_millones_ars)} subinfo={datedUnit('Millones de ARS', analysis.creditArs)} />
          <StatCard label="Morosidad" value={formatPercentage(analysis.delinquency?.morosidad_sector_privado_porcentaje)} subinfo={datedUnit('% de financiaciones', analysis.delinquency)} />
          <StatCard label="Mora estimada" value={formatNumber(analysis.latestCreditQuality?.estimatedDelinquent)} subinfo={datedUnit('Millones de ARS · estimación', analysis.latestCreditQuality)} />
          <StatCard label="Crédito privado en USD" value={formatNumber(analysis.creditUsd?.creditos_sector_privado_millones_usd)} subinfo={datedUnit('Millones de USD', analysis.creditUsd)} />
          <StatCard label="Depósitos privados en USD" value={formatNumber(analysis.depositsUsd?.depositos_sector_privado_millones_usd)} subinfo={datedUnit('Millones de USD', analysis.depositsUsd)} />
        </div>
        <p className="chart-description financial-warning">
          El BCRA publica la tasa de irregularidad, no un monto total de mora.
          “Mora estimada” multiplica esa tasa por los préstamos al sector privado
          del mismo mes; es aproximada porque “financiaciones” y “préstamos” no
          tienen exactamente el mismo universo contable.
        </p>
        <div className="chart-row financial-chart-row">
          <ChartCard title="Crédito total y mora estimada" subtitle="Último saldo mensual, en millones de ARS.">
            <FinancialPlot data={[
              createLineTrace(monthlyValues(dailyRows, 'creditos_sector_privado_millones_ars'), 'Crédito total', { mode: 'lines' }),
              createLineTrace(analysis.creditQuality, 'Mora estimada', { yKey: 'estimatedDelinquent', mode: 'lines' }),
            ]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
          </ChartCard>
          <ChartCard title="Morosidad del crédito" subtitle="Financiaciones irregulares como porcentaje del total.">
            <FinancialPlot data={[
              createLineTrace(analysis.creditQuality, 'Sistema financiero', { yKey: 'ratio', mode: 'lines+markers' }),
              createLineTrace(analysis.creditQuality, 'Empresas', { yKey: 'companies', mode: 'lines' }),
              createLineTrace(analysis.creditQuality, 'Familias', { yKey: 'families', mode: 'lines' }),
            ]} layout={{ yaxis: { title: 'Porcentaje' } }} />
          </ChartCard>
        </div>
        <ChartCard title="Créditos y depósitos privados en moneda extranjera" subtitle="Saldos diarios expresados en millones de USD.">
          <FinancialPlot data={[
            createLineTrace(dailyRows, 'Créditos en USD', { yKey: 'creditos_sector_privado_millones_usd', mode: 'lines' }),
            createLineTrace(dailyRows, 'Depósitos en USD', { yKey: 'depositos_sector_privado_millones_usd', mode: 'lines' }),
          ]} layout={{ yaxis: { title: 'Millones de USD' } }} />
        </ChartCard>
      </section>

      <section className="financial-section">
        <SectionHeading number="8" title="Balance mensual del BCRA">
          <p className="source-note">Fuente: <a href={BCRA_BALANCE_SOURCE} target="_blank" rel="noreferrer">BCRA — balance con presentación analítica</a> y sus <a href={BCRA_BALANCE_METHOD} target="_blank" rel="noreferrer">notas metodológicas</a>. Saldos de fin de mes en millones de ARS.</p>
        </SectionHeading>
        {!balanceRows.length && <div className="data-unavailable" role="status"><strong>Balance mensual temporalmente no disponible.</strong>{balanceError && <span className="data-unavailable-detail">{balanceError}</span>}</div>}
        {balanceRows.length > 0 && (
          <>
            <div className="chart-row financial-chart-row">
              <ChartCard title="Activos externos netos y sector oficial">
                <p className="chart-description">Los activos externos netos son una partida contable en ARS, no reservas netas. Los activos del sector oficial son créditos y títulos del BCRA frente al Estado: no son depósitos estatales ni el tamaño total del Banco Central.</p>
                <FinancialPlot data={[
                  createLineTrace(balanceRows, 'Activos externos netos', { yKey: 'activos_externos_netos_millones_ars', mode: 'lines' }),
                  createLineTrace(balanceRows, 'Sector oficial', { yKey: 'activos_sector_oficial_millones_ars', mode: 'lines' }),
                ]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
              </ChartCard>
              <ChartCard title="Adelantos transitorios y títulos públicos">
                <p className="chart-description">Los adelantos son financiamiento temporal del BCRA al Tesoro; los títulos públicos son bonos y letras del Gobierno en su cartera. Son saldos de activos, no gasto público del mes.</p>
                <FinancialPlot data={[
                  createLineTrace(balanceRows, 'Adelantos transitorios', { yKey: 'adelantos_transitorios_millones_ars', mode: 'lines' }),
                  createLineTrace(balanceRows, 'Títulos públicos', { yKey: 'titulos_publicos_millones_ars', mode: 'lines' }),
                ]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
              </ChartCard>
            </div>
            <div className="chart-row financial-chart-row">
              <ChartCard title="Fuentes de absorción monetaria">
                <p className="chart-description">Agrupa pasivos y contrapartidas que absorben recursos: depósitos, obligaciones en moneda extranjera, títulos del BCRA y cuentas varias. No significa gasto ni destrucción automática de dinero.</p>
                <FinancialPlot data={[
                  createLineTrace(balanceRows, 'Fuentes de absorción', { yKey: 'fuentes_absorcion_millones_ars', mode: 'lines' }),
                  createLineTrace(balanceRows, 'Depósitos en el BCRA', { yKey: 'depositos_totales_bcra_millones_ars', mode: 'lines' }),
                  createLineTrace(balanceRows, 'Títulos emitidos', { yKey: 'titulos_emitidos_bcra_millones_ars', mode: 'lines' }),
                ]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
              </ChartCard>
              <ChartCard title="Crédito del BCRA a entidades financieras" subtitle="Asistencia a entidades; no es el crédito bancario al sector privado.">
                <FinancialPlot data={[createLineTrace(balanceRows, 'Crédito a entidades financieras', { yKey: 'creditos_entidades_financieras_millones_ars', mode: 'lines' })]} layout={{ yaxis: { title: 'Millones de ARS' } }} />
              </ChartCard>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

export default FinancialSector

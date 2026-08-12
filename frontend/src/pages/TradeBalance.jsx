import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { fetchDolt } from '../api/dolt.js'
import ChartCard from '../components/ChartCard.jsx'
import PlotlyChart from '../components/PlotlyChart.jsx'
import StatCard from '../components/StatCard.jsx'

import {
  calculateSeriesVariations,
  normalizeNumericRows,
  sumLastPeriods,
  sumYTD,
} from '../utils/series.js'

import {
  formatNumber,
  formatPercentage,
  formatPeriod,
} from '../utils/formatters.js'

import {
  createBarTrace,
  createLineTrace,
} from '../utils/charts.js'


const TRADE_QUERY = `
  SELECT
    period,
    exportaciones_usd,
    importaciones_usd,
    balanza_comercial_usd
  FROM trade_argentina
  ORDER BY period ASC
`


function TradeBalance() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadTradeBalance() {
      try {
        setLoading(true)
        setError(null)

        const result = await fetchDolt(
          TRADE_QUERY,
        )

        if (result.length < 13) {
          throw new Error(
            'No hay suficientes datos de comercio exterior',
          )
        }

        if (!cancelled) {
          setRows(
            normalizeNumericRows(
              result,
              ['period'],
            ),
          )
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Error desconocido',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadTradeBalance()

    return () => {
      cancelled = true
    }
  }, [])

  const analysis = useMemo(() => {
    if (rows.length < 13) {
      return null
    }

    const exportsVariations =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'exportaciones_usd',
          periodKey: 'period',
        },
      )

    const importsVariations =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'importaciones_usd',
          periodKey: 'period',
        },
      )

    return {
      exportsAnnual:
        exportsVariations.annual,

      importsAnnual:
        importsVariations.annual,

      balance12M: sumLastPeriods(
        rows,
        'balanza_comercial_usd',
        12,
      ),

      balanceYTD: sumYTD(
        rows,
        'balanza_comercial_usd',
        'period',
      ),
    }
  }, [rows])

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />

        <p>
          Cargando datos de balanza comercial...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error">
        Error al cargar balanza comercial:{' '}
        {error}
      </div>
    )
  }

  if (!analysis || !rows.length) {
    return (
      <div className="error">
        No hay datos disponibles.
      </div>
    )
  }

  const latestRow = rows.at(-1)

  const exportsAnnual =
    analysis.exportsAnnual.slice(-24)

  const importsAnnual =
    analysis.importsAnnual.slice(-24)

  const exportsLatestAnnual =
    exportsAnnual.at(-1)?.value ?? null

  const importsLatestAnnual =
    importsAnnual.at(-1)?.value ?? null

  const exportsSeries = rows.map(
    (row) => ({
      period: row.period,
      value: row.exportaciones_usd,
    }),
  )

  const importsSeries = rows.map(
    (row) => ({
      period: row.period,
      value: row.importaciones_usd,
    }),
  )

  const balanceSeries = rows.map(
    (row) => ({
      period: row.period,
      value: row.balanza_comercial_usd,
    }),
  )

  return (
    <>
      <header>
        <h1>
          Comercio Exterior
        </h1>

        <p className="subtitle">
          Exportaciones, importaciones y balanza
          comercial argentina
        </p>

        <p className="last-updated">
          Último período disponible:{' '}
          {formatPeriod(latestRow.period)}
        </p>
      </header>

      <main>
        <section className="stats">
          <StatCard
            label="Período"
            value={formatPeriod(
              latestRow.period,
            )}
          />

          <StatCard
            label="Balanza último mes"
            value={
              `${formatNumber(
                latestRow.balanza_comercial_usd,
                {
                  maximumFractionDigits: 0,
                },
              )} M USD`
            }
          />

          <StatCard
            label="Balanza últimos 12 meses"
            value={
              `${formatNumber(
                analysis.balance12M,
                {
                  maximumFractionDigits: 0,
                },
              )} M USD`
            }
          />

          <StatCard
            label="Balanza acumulada YTD"
            value={
              `${formatNumber(
                analysis.balanceYTD,
                {
                  maximumFractionDigits: 0,
                },
              )} M USD`
            }
          />
        </section>

        <ChartCard title="Exportaciones e Importaciones">
          <PlotlyChart
            data={[
              createLineTrace(
                exportsSeries,
                'Exportaciones',
              ),

              createLineTrace(
                importsSeries,
                'Importaciones',
              ),
            ]}
            layout={{
              xaxis: {
                title: 'Período',
              },
              yaxis: {
                title: 'Millones de USD',
              },
              legend: {
                orientation: 'h',
                y: -0.2,
              },
            }}
          />
        </ChartCard>

        <ChartCard title="Balanza comercial por período">
          <PlotlyChart
            data={[
              createBarTrace(
                balanceSeries,
                'Balanza comercial',
                {
                  xKey: 'period',
                  yKey: 'value',
                  positiveColor: '#31a354',
                  negativeColor: '#e74c3c',
                },
              ),
            ]}
            layout={{
              xaxis: {
                title: 'Período',
              },
              yaxis: {
                title: 'Millones de USD',
              },
            }}
          />
        </ChartCard>

        <div className="chart-row">
          <ChartCard
            title={`Exportaciones - Variación interanual (${formatPercentage(
              exportsLatestAnnual,
            )})`}
          >
            <PlotlyChart
              data={[
                createBarTrace(
                  exportsAnnual,
                  'Exportaciones',
                  {
                    xKey: 'period',
                    yKey: 'value',
                    positiveColor: '#3182bd',
                    negativeColor: '#e74c3c',
                  },
                ),
              ]}
              layout={{
                xaxis: {
                  title: 'Período',
                },
                yaxis: {
                  title: 'Variación %',
                },
              }}
            />
          </ChartCard>

          <ChartCard
            title={`Importaciones - Variación interanual (${formatPercentage(
              importsLatestAnnual,
            )})`}
          >
            <PlotlyChart
              data={[
                createBarTrace(
                  importsAnnual,
                  'Importaciones',
                  {
                    xKey: 'period',
                    yKey: 'value',
                    positiveColor: '#31a354',
                    negativeColor: '#e74c3c',
                  },
                ),
              ]}
              layout={{
                xaxis: {
                  title: 'Período',
                },
                yaxis: {
                  title: 'Variación %',
                },
              }}
            />
          </ChartCard>
        </div>
      </main>
    </>
  )
}

export default TradeBalance
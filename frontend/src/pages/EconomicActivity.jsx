import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { fetchDolt } from '../api/dolt.js'
import ChartCard from '../components/ChartCard.jsx'
import PlotlyChart from '../components/PlotlyChart.jsx'
import StatCard from '../components/StatCard.jsx'
import VariationChart from '../components/VariationChart.jsx'

import {
  calculateLatestVariations,
  calculateSeriesVariations,
  calculateVariation,
  normalizeNumericRows,
} from '../utils/series.js'

import {
  formatPercentage,
  formatPeriod,
} from '../utils/formatters.js'

import {
  createBarTrace,
  createLineTrace,
} from '../utils/charts.js'


const EMAE_QUERY = `
  SELECT *
  FROM emae
  ORDER BY periodo ASC
`

const componentColumns = [
  {
    key: 'agricultura_ganaderia_caza_silvicultura',
    label: 'Agro',
  },
  {
    key: 'pesca',
    label: 'Pesca',
  },
  {
    key: 'explotacion_minas_canteras',
    label: 'Minería',
  },
  {
    key: 'industria_manufacturera',
    label: 'Industria',
  },
  {
    key: 'electricidad_gas_agua',
    label: 'Energía',
  },
  {
    key: 'construccion',
    label: 'Construcción',
  },
  {
    key: 'comercio_mayorista_minorista_reparaciones',
    label: 'Comercio',
  },
  {
    key: 'hoteles_restaurantes',
    label: 'Turismo',
  },
  {
    key: 'transporte_comunicaciones',
    label: 'Transporte',
  },
  {
    key: 'intermediacion_financiera',
    label: 'Finanzas',
  },
  {
    key: 'actividades_inmobiliarias_empresariales_alquiler',
    label: 'Inmobiliaria',
  },
  {
    key: 'administracion_publica_defensa_seguridad_social',
    label: 'Sector público',
  },
  {
    key: 'ensenanza',
    label: 'Enseñanza',
  },
  {
    key: 'servicios_sociales_salud',
    label: 'Salud',
  },
  {
    key: 'otras_actividades_servicios_comunitarios',
    label: 'Otros servicios',
  },
  {
    key: 'impuestos_netos_subsidios',
    label: 'Impuestos',
  },
]


function EconomicActivity() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadEconomicActivity() {
      try {
        setLoading(true)
        setError(null)

        const result = await fetchDolt(EMAE_QUERY)

        if (result.length < 13) {
          throw new Error(
            'No hay suficientes observaciones de EMAE',
          )
        }

        if (!cancelled) {
          setRows(
            normalizeNumericRows(
              result,
              ['periodo'],
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

    loadEconomicActivity()

    return () => {
      cancelled = true
    }
  }, [])

  const analysis = useMemo(() => {
    if (rows.length < 13) {
      return null
    }

    const originalSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'indice',
          periodKey: 'periodo',
        },
      )

    const seasonallyAdjustedSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'indice_desestacionalizado',
          periodKey: 'periodo',
        },
      )

    const trendSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'indice_tendencia_ciclo',
          periodKey: 'periodo',
        },
      )

    return {
      original: originalSeries,
      seasonallyAdjusted: seasonallyAdjustedSeries,
      trend: trendSeries,

      components: calculateLatestVariations(
        rows,
        componentColumns,
      ),
    }
  }, [rows])

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>Cargando EMAE...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error">
        Error al cargar EMAE: {error}
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
  const previousRow = rows.at(-2)
  const previousYearRow = rows.at(-13)

  const latestInterannual = calculateVariation(
    latestRow.indice,
    previousYearRow.indice,
  )

  const latestSeasonallyAdjusted = calculateVariation(
    latestRow.indice_desestacionalizado,
    previousRow.indice_desestacionalizado,
  )

  const latestTrend = calculateVariation(
    latestRow.indice_tendencia_ciclo,
    previousRow.indice_tendencia_ciclo,
  )

  const last24OriginalAnnual =
    analysis.original.annual.slice(-24)

  const last24TrendAnnual =
    analysis.trend.annual.slice(-24)

  const last24SeasonallyAdjustedMonthly =
    analysis.seasonallyAdjusted.monthly.slice(-24)

  const last24TrendMonthly =
    analysis.trend.monthly.slice(-24)

  return (
    <>
      <header>
        <h1>🏭 Actividad Económica</h1>

        <p className="subtitle">
          Estimador Mensual de Actividad Económica
        </p>

        <p className="last-updated">
          Último período disponible:{' '}
          {formatPeriod(latestRow.periodo)}
        </p>
      </header>

      <main>
        <section className="stats">
          <StatCard
            label="Período"
            value={formatPeriod(latestRow.periodo)}
          />

          <StatCard
            label="Variación interanual"
            value={formatPercentage(
              latestInterannual,
            )}
          />

          <StatCard
            label="Variación mensual desestacionalizada"
            value={formatPercentage(
              latestSeasonallyAdjusted,
            )}
          />

          <StatCard
            label="Variación mensual tendencia-ciclo"
            value={formatPercentage(
              latestTrend,
            )}
          />
        </section>

        <ChartCard title="Series EMAE">
          <PlotlyChart
            data={[
              createLineTrace(
                rows.map((row) => ({
                  period: row.periodo,
                  value: row.indice,
                })),
                'Índice original',
              ),

              createLineTrace(
                rows.map((row) => ({
                  period: row.periodo,
                  value:
                    row.indice_desestacionalizado,
                })),
                'Índice desestacionalizado',
              ),

              createLineTrace(
                rows.map((row) => ({
                  period: row.periodo,
                  value:
                    row.indice_tendencia_ciclo,
                })),
                'Tendencia-ciclo',
              ),
            ]}
            layout={{
              xaxis: {
                title: 'Período',
              },
              yaxis: {
                title: 'Índice',
              },
              legend: {
                orientation: 'h',
                y: -0.2,
              },
            }}
            height={620}
          />
        </ChartCard>

        <ChartCard title="Variación interanual">
          <PlotlyChart
            data={[
              createBarTrace(
                last24OriginalAnnual,
                'Índice EMAE',
                {
                  xKey: 'period',
                  yKey: 'value',
                },
              ),

              createBarTrace(
                last24TrendAnnual,
                'Tendencia-ciclo',
                {
                  xKey: 'period',
                  yKey: 'value',
                },
              ),
            ]}
            layout={{
              barmode: 'group',
              xaxis: {
                title: 'Período',
              },
              yaxis: {
                title: 'Variación %',
              },
              legend: {
                orientation: 'h',
                y: -0.2,
              },
            }}
          />
        </ChartCard>

        <ChartCard title="Variación mensual">
          <PlotlyChart
            data={[
              createBarTrace(
                last24SeasonallyAdjustedMonthly,
                'Desestacionalizado',
                {
                  xKey: 'period',
                  yKey: 'value',
                },
              ),

              createBarTrace(
                last24TrendMonthly,
                'Tendencia-ciclo',
                {
                  xKey: 'period',
                  yKey: 'value',
                },
              ),
            ]}
            layout={{
              barmode: 'group',
              xaxis: {
                title: 'Período',
              },
              yaxis: {
                title: 'Variación %',
              },
              legend: {
                orientation: 'h',
                y: -0.2,
              },
            }}
          />
        </ChartCard>

        <VariationChart
          title="Variaciones por actividad"
          monthlyData={analysis.components.monthly}
          annualData={analysis.components.annual}
          xAxisTitle="Actividad"
        />

        <section id="otros">
          <h2>Otros indicadores</h2>
          <p>Próximamente...</p>
        </section>
      </main>
    </>
  )
}

export default EconomicActivity
import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { fetchDolt } from '../api/dolt.js'
import ChartCard from '../components/ChartCard.jsx'
import PlotlyChart from '../components/PlotlyChart.jsx'
import StatCard from '../components/StatCard.jsx'
import VariationCharts from '../components/VariationChart.jsx'

import {
  calculateLatestVariations,
  calculateSeriesVariations,
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


const IPC_QUERY = `
  SELECT
    fecha,
    nivel_general,
    nucleo,
    estacional,
    bienes,
    servicios,
    alimentos_bebidas_no_alcoholicas,
    bebidas_alcoholicas_tabaco,
    prendas_vestir_calzado,
    vivienda_agua_electricidad_gas_combustibles,
    equipamiento_mantenimiento_hogar,
    salud,
    transporte,
    comunicacion,
    recreacion_cultura,
    educacion,
    restaurantes_hoteles,
    bienes_servicios_varios
  FROM ipc_argentina
  ORDER BY fecha ASC
`

const componentColumns = [
  {
    key: 'nivel_general',
    label: 'Nivel general',
  },
  {
    key: 'alimentos_bebidas_no_alcoholicas',
    label: 'Alimentos',
  },
  {
    key: 'bebidas_alcoholicas_tabaco',
    label: 'Bebidas y tabaco',
  },
  {
    key: 'prendas_vestir_calzado',
    label: 'Prendas y calzado',
  },
  {
    key: 'vivienda_agua_electricidad_gas_combustibles',
    label: 'Vivienda',
  },
  {
    key: 'equipamiento_mantenimiento_hogar',
    label: 'Equipamiento hogar',
  },
  {
    key: 'salud',
    label: 'Salud',
  },
  {
    key: 'transporte',
    label: 'Transporte',
  },
  {
    key: 'comunicacion',
    label: 'Comunicación',
  },
  {
    key: 'recreacion_cultura',
    label: 'Recreación',
  },
  {
    key: 'educacion',
    label: 'Educación',
  },
  {
    key: 'restaurantes_hoteles',
    label: 'Restaurantes y hoteles',
  },
  {
    key: 'bienes_servicios_varios',
    label: 'Otros',
  },
]

const aggregateColumns = [
  {
    key: 'estacional',
    label: 'Estacional',
  },
  {
    key: 'nucleo',
    label: 'Núcleo',
  },
  {
    key: 'bienes',
    label: 'Bienes',
  },
  {
    key: 'servicios',
    label: 'Servicios',
  },
]


function Inflation() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadInflation() {
      try {
        setLoading(true)
        setError(null)

        const result = await fetchDolt(IPC_QUERY)

        if (!result.length) {
          throw new Error('No hay datos de IPC')
        }

        if (!cancelled) {
          setRows(
            normalizeNumericRows(
              result,
              ['fecha'],
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

    loadInflation()

    return () => {
      cancelled = true
    }
  }, [])

  const analysis = useMemo(() => {
    if (!rows.length) {
      return null
    }

    const generalSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'nivel_general',
          periodKey: 'fecha',
        },
      )

    const coreSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey: 'nucleo',
          periodKey: 'fecha',
        },
      )

    return {
      monthly: generalSeries.monthly,
      interannual: generalSeries.annual,
      coreInterannual: coreSeries.annual,

      components: calculateLatestVariations(
        rows,
        componentColumns,
      ),

      aggregates: calculateLatestVariations(
        rows,
        aggregateColumns,
      ),
    }
  }, [rows])

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />

        <p>Cargando datos de IPC...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error">
        Error al cargar IPC: {error}
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

  const latestMonthly =
    analysis.monthly.at(-1)?.value ?? null

  const latestInterannual =
    analysis.interannual.at(-1)?.value ?? null

  const monthlySeries =
    analysis.monthly.slice(-24)

  const interannualSeries =
    analysis.interannual.slice(-24)

  const coreInterannualSeries =
    analysis.coreInterannual.slice(-24)

  return (
    <>
      <header>
        <h1>📈 Análisis de Inflación</h1>

        <p className="subtitle">
          IPC Argentina - últimos datos y desagregación
        </p>

        <p className="last-updated">
          Último período disponible:{' '}
          {formatPeriod(latestRow.fecha)}
        </p>
      </header>

      <main>
        <section className="stats">
          <StatCard
            label="Período"
            value={formatPeriod(latestRow.fecha)}
          />

          <StatCard
            label="Inflación interanual"
            value={formatPercentage(
              latestInterannual,
            )}
          />

          <StatCard
            label="Inflación mensual"
            value={formatPercentage(
              latestMonthly,
            )}
          />
        </section>

        <div className="chart-row">
          <ChartCard title="Inflación mensual">
            <PlotlyChart
              data={[
                createBarTrace(
                  monthlySeries,
                  'Inflación mensual',
                  {
                    xKey: 'period',
                    yKey: 'value',
                  },
                ),
              ]}
              layout={{
                xaxis: {
                  title: 'Período',
                },
                yaxis: {
                  title: '% mensual',
                },
              }}
            />
          </ChartCard>

          <ChartCard title="Inflación interanual">
            <PlotlyChart
              data={[
                createBarTrace(
                  interannualSeries,
                  'Nivel general',
                  {
                    xKey: 'period',
                    yKey: 'value',
                  },
                ),

                createLineTrace(
                  coreInterannualSeries,
                  'Núcleo',
                ),
              ]}
              layout={{
                xaxis: {
                  title: 'Período',
                },
                yaxis: {
                  title: '% interanual',
                },
              }}
            />
          </ChartCard>
        </div>

        <VariationCharts
          title="Variaciones por componente"
          monthlyData={analysis.components.monthly}
          annualData={analysis.components.annual}
          xAxisTitle="Componente"
        />

        <VariationCharts
          title="Variaciones de series agregadas"
          monthlyData={analysis.aggregates.monthly}
          annualData={analysis.aggregates.annual}
          xAxisTitle="Serie"
        />
      </main>
    </>
  )
}

export default Inflation
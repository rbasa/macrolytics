import { useEffect, useMemo, useState } from 'react'

import { fetchDolt } from '../../api/dolt.js'
import ChartCard from '../../components/ChartCard.jsx'
import PlotlyChart from '../../components/PlotlyChart.jsx'
import StatCard from '../../components/StatCard.jsx'
import VariationChart from '../../components/VariationChart.jsx'
import {
  calculateLatestVariations,
  calculateSeriesVariations,
  calculateVariation,
  normalizeNumericRows,
} from '../../utils/series.js'
import {
  formatPercentage,
  formatPeriod,
} from '../../utils/formatters.js'
import {
  createBarTrace,
  createLineTrace,
} from '../../utils/charts.js'


const EMAE_QUERY = 'SELECT * FROM emae ORDER BY periodo ASC'

const componentColumns = [
  ['agricultura_ganaderia_caza_silvicultura', 'Agro'],
  ['pesca', 'Pesca'],
  ['explotacion_minas_canteras', 'Minería'],
  ['industria_manufacturera', 'Industria'],
  ['electricidad_gas_agua', 'Energía'],
  ['construccion', 'Construcción'],
  ['comercio_mayorista_minorista_reparaciones', 'Comercio'],
  ['hoteles_restaurantes', 'Turismo'],
  ['transporte_comunicaciones', 'Transporte'],
  ['intermediacion_financiera', 'Finanzas'],
  ['actividades_inmobiliarias_empresariales_alquiler', 'Inmobiliaria'],
  ['administracion_publica_defensa_seguridad_social', 'Sector público'],
  ['ensenanza', 'Enseñanza'],
  ['servicios_sociales_salud', 'Salud'],
  ['otras_actividades_servicios_comunitarios', 'Otros servicios'],
  ['impuestos_netos_subsidios', 'Impuestos'],
].map(([key, label]) => ({ key, label }))


function EmaeAnalysis() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadEmae() {
      try {
        const result = await fetchDolt(EMAE_QUERY)
        if (result.length < 13) {
          throw new Error('No hay suficientes observaciones de EMAE')
        }
        if (!cancelled) {
          setRows(normalizeNumericRows(result, ['periodo']))
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

    loadEmae()
    return () => {
      cancelled = true
    }
  }, [])

  const analysis = useMemo(() => {
    if (rows.length < 13) {
      return null
    }
    return {
      original: calculateSeriesVariations(rows, {
        valueKey: 'indice',
        periodKey: 'periodo',
      }),
      seasonallyAdjusted: calculateSeriesVariations(rows, {
        valueKey: 'indice_desestacionalizado',
        periodKey: 'periodo',
      }),
      trend: calculateSeriesVariations(rows, {
        valueKey: 'indice_tendencia_ciclo',
        periodKey: 'periodo',
      }),
      components: calculateLatestVariations(rows, componentColumns),
    }
  }, [rows])

  if (loading) {
    return <p className="section-status">Cargando EMAE...</p>
  }
  if (error || !analysis) {
    return (
      <div className="error">
        Error al cargar EMAE: {error || 'No hay datos disponibles'}
      </div>
    )
  }

  const latestRow = rows.at(-1)
  const previousRow = rows.at(-2)
  const previousYearRow = rows.at(-13)

  return (
    <section className="activity-section" id="emae">
      <div className="activity-section-heading">
        <p className="activity-kicker">Seguimiento mensual</p>
        <h2>EMAE</h2>
        <p>
          Señal mensual de actividad para seguir el trimestre en curso
          antes de la publicación de Cuentas Nacionales.
        </p>
        <p className="last-updated">
          Último período: {formatPeriod(latestRow.periodo)}
        </p>
      </div>

      <div className="stats">
        <StatCard
          label="Variación interanual"
          value={formatPercentage(
            calculateVariation(latestRow.indice, previousYearRow.indice),
          )}
        />
        <StatCard
          label="Mensual desestacionalizada"
          value={formatPercentage(calculateVariation(
            latestRow.indice_desestacionalizado,
            previousRow.indice_desestacionalizado,
          ))}
        />
        <StatCard
          label="Mensual tendencia-ciclo"
          value={formatPercentage(calculateVariation(
            latestRow.indice_tendencia_ciclo,
            previousRow.indice_tendencia_ciclo,
          ))}
        />
      </div>

      <ChartCard title="Series EMAE">
        <PlotlyChart
          data={[
            createLineTrace(rows.map((row) => ({
              period: row.periodo,
              value: row.indice,
            })), 'Índice original'),
            createLineTrace(rows.map((row) => ({
              period: row.periodo,
              value: row.indice_desestacionalizado,
            })), 'Índice desestacionalizado'),
            createLineTrace(rows.map((row) => ({
              period: row.periodo,
              value: row.indice_tendencia_ciclo,
            })), 'Tendencia-ciclo'),
          ]}
          layout={{
            xaxis: { title: 'Período' },
            yaxis: { title: 'Índice' },
            legend: { orientation: 'h', y: -0.2 },
          }}
          height={620}
        />
      </ChartCard>

      <div className="chart-row">
        <ChartCard title="Variación interanual">
          <PlotlyChart
            data={[
              createBarTrace(
                analysis.original.annual.slice(-24),
                'Índice EMAE',
                { xKey: 'period', yKey: 'value' },
              ),
              createBarTrace(
                analysis.trend.annual.slice(-24),
                'Tendencia-ciclo',
                { xKey: 'period', yKey: 'value' },
              ),
            ]}
            layout={{
              barmode: 'group',
              xaxis: { title: 'Período' },
              yaxis: { title: 'Variación %' },
            }}
          />
        </ChartCard>

        <ChartCard title="Variación mensual">
          <PlotlyChart
            data={[
              createBarTrace(
                analysis.seasonallyAdjusted.monthly.slice(-24),
                'Desestacionalizado',
                { xKey: 'period', yKey: 'value' },
              ),
              createBarTrace(
                analysis.trend.monthly.slice(-24),
                'Tendencia-ciclo',
                { xKey: 'period', yKey: 'value' },
              ),
            ]}
            layout={{
              barmode: 'group',
              xaxis: { title: 'Período' },
              yaxis: { title: 'Variación %' },
            }}
          />
        </ChartCard>
      </div>

      <VariationChart
        title="Variaciones por actividad"
        monthlyData={analysis.components.monthly}
        annualData={analysis.components.annual}
        xAxisTitle="Actividad"
      />
    </section>
  )
}

export default EmaeAnalysis

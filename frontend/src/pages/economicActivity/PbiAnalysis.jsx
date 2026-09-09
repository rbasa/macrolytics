import { useEffect, useMemo, useState } from 'react'

import { fetchDolt } from '../../api/dolt.js'
import ChartCard from '../../components/ChartCard.jsx'
import PlotlyChart from '../../components/PlotlyChart.jsx'
import StatCard from '../../components/StatCard.jsx'
import {
  calculateLatestVariations,
  calculateSeriesVariations,
  calculateVariation,
  normalizeNumericRows,
} from '../../utils/series.js'
import {
  formatNumber,
  formatPercentage,
  formatQuarter,
} from '../../utils/formatters.js'
import {
  createBarTrace,
  createLineTrace,
} from '../../utils/charts.js'


const PBI_CONSTANT_QUERY =
  'SELECT * FROM pbi_argentina_precios_2004 ORDER BY periodo ASC'
const PBI_CURRENT_QUERY =
  'SELECT periodo, pib FROM pbi_argentina_precios_corrientes ORDER BY periodo ASC'
const DEMAND_CONSTANT_QUERY =
  'SELECT * FROM pbi_demanda_argentina_precios_2004 ORDER BY periodo ASC'

const sectorColumns = [
  ['agricultura_ganaderia_caza_silvicultura', 'Agro'],
  ['pesca', 'Pesca'],
  ['explotacion_minas_canteras', 'Minería'],
  ['industria_manufacturera', 'Industria'],
  ['electricidad_gas_agua', 'Energía'],
  ['construccion', 'Construcción'],
  ['comercio_mayorista_minorista_reparaciones', 'Comercio'],
  ['hoteles_restaurantes', 'Hoteles y restaurantes'],
  ['transporte_almacenamiento_comunicaciones', 'Transporte'],
  ['intermediacion_financiera', 'Finanzas'],
  ['actividades_inmobiliarias_empresariales_alquiler', 'Inmobiliarias'],
  ['administracion_publica_defensa_seguridad_social', 'Sector público'],
  ['ensenanza', 'Enseñanza'],
  ['servicios_sociales_salud', 'Salud'],
  ['otras_actividades_servicios_comunitarios', 'Otros servicios'],
].map(([key, label]) => ({ key, label }))

const demandColumns = [
  ['consumo_privado', 'Consumo privado'],
  ['consumo_publico', 'Consumo público'],
  ['formacion_bruta_capital_fijo', 'Inversión fija'],
  ['exportaciones', 'Exportaciones'],
  ['importaciones', 'Importaciones'],
].map(([key, label]) => ({ key, label }))


function PbiAnalysis() {
  const [data, setData] = useState({
    pbi: [],
    currentPbi: [],
    demand: [],
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadPbi() {
      try {
        const [pbiRows, currentRows, demandRows] = await Promise.all([
          fetchDolt(PBI_CONSTANT_QUERY),
          fetchDolt(PBI_CURRENT_QUERY),
          fetchDolt(DEMAND_CONSTANT_QUERY),
        ])

        if (pbiRows.length < 5 || demandRows.length < 5) {
          throw new Error('No hay suficientes observaciones trimestrales')
        }

        if (!cancelled) {
          setData({
            pbi: normalizeNumericRows(pbiRows, ['periodo']),
            currentPbi: normalizeNumericRows(currentRows, ['periodo']),
            demand: normalizeNumericRows(demandRows, ['periodo']),
          })
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

    loadPbi()
    return () => {
      cancelled = true
    }
  }, [])

  const analysis = useMemo(() => {
    if (data.pbi.length < 5 || data.demand.length < 5) {
      return null
    }

    return {
      pbi: calculateSeriesVariations(data.pbi, {
        valueKey: 'pib',
        periodKey: 'periodo',
        annualLag: 4,
      }),
      seasonallyAdjusted: calculateSeriesVariations(data.pbi, {
        valueKey: 'pib_desestacionalizado',
        periodKey: 'periodo',
        annualLag: 4,
      }),
      sectors: calculateLatestVariations(data.pbi, sectorColumns, {
        annualLag: 4,
      }),
      demand: calculateLatestVariations(data.demand, demandColumns, {
        annualLag: 4,
      }),
    }
  }, [data])

  if (loading) {
    return <p className="section-status">Cargando PBI trimestral...</p>
  }
  if (error || !analysis) {
    return (
      <div className="error">
        Error al cargar PBI: {error || 'No hay datos disponibles'}
      </div>
    )
  }

  const latest = data.pbi.at(-1)
  const previous = data.pbi.at(-2)
  const previousYear = data.pbi.at(-5)
  const latestDemand = data.demand.at(-1)
  const previousYearDemand = data.demand.at(-5)
  const latestCurrent = data.currentPbi.at(-1)

  return (
    <section className="activity-section activity-section--primary" id="pbi">
      <div className="activity-section-heading">
        <p className="activity-kicker">Ancla trimestral</p>
        <h2>Producto Interno Bruto</h2>
        <p>
          Cuentas Nacionales a precios de 2004: nivel de actividad,
          sectores productivos y componentes de la demanda.
        </p>
        <p className="last-updated">
          Último período: {formatQuarter(latest.periodo)}
        </p>
      </div>

      <div className="stats pbi-stats">
        <StatCard
          label="PBI real interanual"
          value={formatPercentage(
            calculateVariation(latest.pib, previousYear.pib),
          )}
        />
        <StatCard
          label="PBI trimestral desestacionalizado"
          value={formatPercentage(calculateVariation(
            latest.pib_desestacionalizado,
            previous.pib_desestacionalizado,
          ))}
        />
        <StatCard
          label="Consumo privado interanual"
          value={formatPercentage(calculateVariation(
            latestDemand.consumo_privado,
            previousYearDemand.consumo_privado,
          ))}
        />
        <StatCard
          label="Inversión fija interanual"
          value={formatPercentage(calculateVariation(
            latestDemand.formacion_bruta_capital_fijo,
            previousYearDemand.formacion_bruta_capital_fijo,
          ))}
        />
        <StatCard
          label="PBI a precios corrientes"
          value={formatNumber(latestCurrent?.pib, {
            maximumFractionDigits: 0,
          })}
          subinfo="Millones de pesos"
        />
      </div>

      <ChartCard
        title="PBI a precios de 2004"
        subtitle="Serie original y serie desestacionalizada, en millones de pesos de 2004."
      >
        <PlotlyChart
          data={[
            createLineTrace(data.pbi.map((row) => ({
              period: row.periodo,
              value: row.pib,
            })), 'PBI original'),
            createLineTrace(data.pbi.map((row) => ({
              period: row.periodo,
              value: row.pib_desestacionalizado,
            })), 'PBI desestacionalizado'),
          ]}
          layout={{
            xaxis: { title: 'Trimestre' },
            yaxis: { title: 'Millones de pesos de 2004' },
            legend: { orientation: 'h', y: -0.2 },
          }}
          height={560}
        />
      </ChartCard>

      <ChartCard
        title="Crecimiento del PBI"
        subtitle="Interanual sobre la serie original y trimestral sobre la serie desestacionalizada."
      >
        <PlotlyChart
          data={[
            createBarTrace(
              analysis.pbi.annual.slice(-32),
              'Interanual',
              { xKey: 'period', yKey: 'value' },
            ),
            createBarTrace(
              analysis.seasonallyAdjusted.monthly.slice(-32),
              'Trimestral desestacionalizada',
              { xKey: 'period', yKey: 'value' },
            ),
          ]}
          layout={{
            barmode: 'group',
            xaxis: { title: 'Trimestre' },
            yaxis: { title: 'Variación %' },
            legend: { orientation: 'h', y: -0.2 },
          }}
        />
      </ChartCard>

      <div className="chart-row">
        <ChartCard
          title="Sectores productivos"
          subtitle="Variación interanual real del último trimestre."
        >
          <PlotlyChart
            data={[
              createBarTrace(analysis.sectors.annual, 'Interanual'),
            ]}
            layout={{
              xaxis: { title: 'Sector', automargin: true },
              yaxis: { title: 'Variación %' },
            }}
          />
        </ChartCard>

        <ChartCard
          title="Componentes de la demanda"
          subtitle="Variación interanual real del último trimestre."
        >
          <PlotlyChart
            data={[
              createBarTrace(analysis.demand.annual, 'Interanual'),
            ]}
            layout={{
              xaxis: { title: 'Componente', automargin: true },
              yaxis: { title: 'Variación %' },
            }}
          />
        </ChartCard>
      </div>
    </section>
  )
}

export default PbiAnalysis

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
  calculateVariation,
  normalizeNumericRows,
} from '../utils/series.js'

import {
  formatNumber,
  formatPercentage,
  formatPeriod,
} from '../utils/formatters.js'

import {
  createBarTrace,
  createPieTrace,
} from '../utils/charts.js'


const FISCAL_QUERY = `
  SELECT *
  FROM fiscal_argentina
  ORDER BY period ASC
`


const currentRevenueComposition = [
  {
    key: 'ingresos_tributarios_total',
    label: 'Ingresos impositivos',
  },
  {
    key: 'ingresos_aportes_contribuciones_seguridad_social',
    label: 'Aportes y contribuciones',
  },
  {
    key: 'ingresos_no_tributarios',
    label: 'Ingresos no impositivos',
  },
  {
    key: 'ingresos_ventas_bienes_servicios_adm_publica',
    label: 'Ventas de bienes y servicios',
  },
  {
    key: 'ingresos_operacion',
    label: 'Ingresos de operación',
  },
  {
    key: 'ingresos_rentas_propiedad_netas',
    label: 'Rentas de la propiedad',
  },
  {
    key: 'ingresos_transferencias_corrientes',
    label: 'Transferencias corrientes',
  },
  {
    key: 'ingresos_otros',
    label: 'Otros ingresos',
  },
  {
    key: 'ingresos_superavit_operativo_empresas_publicas',
    label: 'Superávit empresas públicas',
  },
]


const taxComposition = [
  {
    key: 'ingresos_tributarios_iva',
    label: 'IVA',
  },
  {
    key: 'ingresos_tributarios_ganancias',
    label: 'Ganancias',
  },
  {
    key: 'ingresos_tributarios_debitos_creditos',
    label: 'Débitos y créditos',
  },
  {
    key: 'ingresos_tributarios_bienes_personales',
    label: 'Bienes personales',
  },
  {
    key: 'ingresos_tributarios_combustibles',
    label: 'Combustibles',
  },
  {
    key: 'ingresos_tributarios_derechos_exportacion',
    label: 'Derechos de exportación',
  },
  {
    key: 'ingresos_tributarios_derechos_importacion',
    label: 'Derechos de importación',
  },
  {
    key: 'ingresos_tributarios_impuestos_internos',
    label: 'Impuestos internos',
  },
  {
    key: 'ingresos_tributarios_resto',
    label: 'Otros tributarios',
  },
]


const currentExpenseComposition = [
  {
    key: 'gastos_consumo_operacion_total',
    label: 'Consumo y operación',
  },
  {
    key: 'gastos_intereses_otras_rentas_total',
    label: 'Intereses y otras rentas',
  },
  {
    key: 'gastos_prestaciones_seguridad_social',
    label: 'Prestaciones seguridad social',
  },
  {
    key: 'gastos_otros_corrientes',
    label: 'Otros gastos corrientes',
  },
  {
    key: 'gastos_transferencias_corrientes_total',
    label: 'Transferencias corrientes',
  },
  {
    key: 'gastos_otros',
    label: 'Otros gastos',
  },
  {
    key: 'gastos_deficit_operativo_empresas_publicas',
    label: 'Déficit empresas públicas',
  },
]


const transferComposition = [
  {
    key: 'gastos_transferencias_sector_privado',
    label: 'Sector privado',
  },
  {
    key: 'gastos_transferencias_provincias_caba',
    label: 'Provincias y CABA',
  },
  {
    key: 'gastos_transferencias_universidades',
    label: 'Universidades',
  },
  {
    key: 'gastos_transferencias_sector_publico_otras',
    label: 'Otras sector público',
  },
  {
    key: 'gastos_transferencias_sector_externo',
    label: 'Sector externo',
  },
]


function getYtdRows(
  rows,
  year,
  endMonth,
) {
  return rows.filter((row) => {
    const date = new Date(
      `${row.period}T00:00:00`,
    )

    return (
      date.getFullYear() === year &&
      date.getMonth() + 1 <= endMonth
    )
  })
}


function sumColumn(rows, column) {
  return rows.reduce(
    (sum, row) =>
      sum + (Number(row[column]) || 0),
    0,
  )
}


function getComposition(
  rows,
  columns,
) {
  return columns.map((column) => ({
    label: column.label,
    value: sumColumn(
      rows,
      column.key,
    ),
  }))
}


function formatMoney(value) {
  return `${formatNumber(
    value,
    {
      maximumFractionDigits: 0,
    },
  )}`
}


function FiscalBalance() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadFiscalBalance() {
      try {
        setLoading(true)
        setError(null)

        const result = await fetchDolt(
          FISCAL_QUERY,
        )

        if (!result.length) {
          throw new Error(
            'No hay datos fiscales disponibles',
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

    loadFiscalBalance()

    return () => {
      cancelled = true
    }
  }, [])


  const analysis = useMemo(() => {
    if (!rows.length) {
      return null
    }

    const latestRow = rows.at(-1)

    const latestDate = new Date(
      `${latestRow.period}T00:00:00`,
    )

    const currentYear =
      latestDate.getFullYear()

    const previousYear =
      currentYear - 1

    const latestMonth =
      latestDate.getMonth() + 1

    const currentYtdRows = getYtdRows(
      rows,
      currentYear,
      latestMonth,
    )

    const previousYtdRows = getYtdRows(
      rows,
      previousYear,
      latestMonth,
    )

    const revenueYtd = sumColumn(
      currentYtdRows,
      'ingresos_despues_figurativos',
    )

    const previousRevenueYtd = sumColumn(
      previousYtdRows,
      'ingresos_despues_figurativos',
    )

    const primaryExpenseYtd = sumColumn(
      currentYtdRows,
      'gastos_primarios_despues_figurativos',
    )

    const previousPrimaryExpenseYtd =
      sumColumn(
        previousYtdRows,
        'gastos_primarios_despues_figurativos',
      )

    const totalExpenseYtd = sumColumn(
      currentYtdRows,
      'gastos_despues_figurativos',
    )

    const previousTotalExpenseYtd =
      sumColumn(
        previousYtdRows,
        'gastos_despues_figurativos',
      )

    const primaryResultYtd = sumColumn(
      currentYtdRows,
      'resultado_primario',
    )

    const previousPrimaryResultYtd =
      sumColumn(
        previousYtdRows,
        'resultado_primario',
      )

    const financialResultYtd = sumColumn(
      currentYtdRows,
      'resultado_financiero',
    )

    const previousFinancialResultYtd =
      sumColumn(
        previousYtdRows,
        'resultado_financiero',
      )

    const interestYtd = sumColumn(
      currentYtdRows,
      'gastos_intereses_netos',
    )

    const revenueSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey:
            'ingresos_despues_figurativos',
          periodKey: 'period',
        },
      )

    const primaryExpenseSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey:
            'gastos_primarios_despues_figurativos',
          periodKey: 'period',
        },
      )

    const ivaSeries =
      calculateSeriesVariations(
        rows,
        {
          valueKey:
            'ingresos_tributarios_iva',
          periodKey: 'period',
        },
      )

    return {
      latestRow,

      revenueYtd,
      primaryExpenseYtd,
      totalExpenseYtd,
      interestYtd,
      primaryResultYtd,
      financialResultYtd,

      revenueYtdVariation:
        calculateVariation(
          revenueYtd,
          previousRevenueYtd,
        ),

      primaryExpenseYtdVariation:
        calculateVariation(
          primaryExpenseYtd,
          previousPrimaryExpenseYtd,
        ),

      totalExpenseYtdVariation:
        calculateVariation(
          totalExpenseYtd,
          previousTotalExpenseYtd,
        ),

      primaryResultYtdVariation:
        calculateVariation(
          primaryResultYtd,
          previousPrimaryResultYtd,
        ),

      financialResultYtdVariation:
        calculateVariation(
          financialResultYtd,
          previousFinancialResultYtd,
        ),

      primaryResultYtdDifference:
        primaryResultYtd -
        previousPrimaryResultYtd,

      financialResultYtdDifference:
        financialResultYtd -
        previousFinancialResultYtd,

      revenueAnnual:
        revenueSeries.annual,

      primaryExpenseAnnual:
        primaryExpenseSeries.annual,

      ivaAnnual:
        ivaSeries.annual,

      expenseComposition:
        getComposition(
          currentYtdRows,
          currentExpenseComposition,
        ),

      transferComposition:
        getComposition(
          currentYtdRows,
          transferComposition,
        ),

      revenueComposition:
        getComposition(
          currentYtdRows,
          currentRevenueComposition,
        ),

      taxComposition:
        getComposition(
          currentYtdRows,
          taxComposition,
        ),
    }
  }, [rows])


  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />

        <p>
          Cargando datos fiscales...
        </p>
      </div>
    )
  }


  if (error) {
    return (
      <div className="error">
        Error al cargar datos fiscales:{' '}
        {error}
      </div>
    )
  }


  if (!analysis) {
    return (
      <div className="error">
        No hay datos disponibles.
      </div>
    )
  }


  const latestRow = analysis.latestRow

  const balanceSeries = rows.map(
    (row) => ({
      period: row.period,
      value: row.resultado_financiero,
    }),
  )

  const revenueAnnual =
    analysis.revenueAnnual.slice(-24)

  const primaryExpenseAnnual =
    analysis.primaryExpenseAnnual.slice(-24)

  const ivaAnnual =
    analysis.ivaAnnual.slice(-24)


  return (
    <>
      <header>
        <h1>
          Balance Fiscal
        </h1>

        <p className="subtitle">
          Ingresos, gasto y resultado fiscal del
          Sector Público Nacional
        </p>

        <p className="last-updated">
          Último período disponible:{' '}
          {formatPeriod(latestRow.period)}
        </p>
      </header>

      <main>
        <section className="stats">
          <StatCard
            label="Ingresos YTD"
            value={formatMoney(
              analysis.revenueYtd,
            )}
          />

          <StatCard
            label="Gasto total (Primario + Intereses) YTD"
            value={formatMoney(
              analysis.totalExpenseYtd,
            )}
          />

          <StatCard
            label="Resultado financiero YTD"
            value={formatMoney(
              analysis.financialResultYtd,
            )}
          />
        </section>

        <section className="stats">
          <StatCard
            label="Ingresos YTD vs año anterior"
            value={formatPercentage(
              analysis.revenueYtdVariation,
            )}
          />

          <StatCard
            label="Gasto total YTD vs año anterior"
            value={formatPercentage(
              analysis.totalExpenseYtdVariation,
            )}
          />

          <StatCard
            label="Resultado financiero YTD vs año anterior"
            value={formatPercentage(
              analysis.financialResultYtdVariation,
            )}
          />
        </section>

        <section className="stats">
          <StatCard
            label="Últimos ingresos"
            value={formatMoney(
              latestRow.ingresos_despues_figurativos,
            )}
          />

          <StatCard
            label="Último gasto total"
            value={formatMoney(
              latestRow.gastos_despues_figurativos,
            )}
          />

          <StatCard
            label="Último resultado financiero"
            value={formatMoney(
              latestRow.resultado_financiero,
            )}
          />
        </section>
        <p className="last-updated">
          Expresado en millones de ARS corrientes. Datos del Sector Público Nacional, incluyendo organismos descentralizados y empresas públicas.
        </p>
        <ChartCard title="Evolución del resultado financiero">
          <PlotlyChart
            data={[
              createBarTrace(
                balanceSeries,
                'Resultado financiero',
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
                title: 'Millones de ARS',
              },
            }}
          />
        </ChartCard>

        <ChartCard title="Variación interanual de ingresos y gasto primario">
          <PlotlyChart
            data={[
              createBarTrace(
                revenueAnnual,
                'Ingresos',
                {
                  xKey: 'period',
                  yKey: 'value',
                },
              ),

              createBarTrace(
                primaryExpenseAnnual,
                'Gasto primario',
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
                title: 'Variación interanual %',
              },

              legend: {
                orientation: 'h',
                y: -0.2,
              },
            }}
          />
        </ChartCard>

        <div className="chart-row">
          <ChartCard title="Composición de gastos corrientes YTD">
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.expenseComposition,
                  'Gastos corrientes',
                ),
              ]}
            />
          </ChartCard>

          <ChartCard title="Transferencias corrientes YTD">
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.transferComposition,
                  'Transferencias',
                ),
              ]}
            />
          </ChartCard>
        </div>

        <div className="chart-row">
          <ChartCard title="Composición de ingresos corrientes YTD">
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.revenueComposition,
                  'Ingresos corrientes',
                ),
              ]}
            />
          </ChartCard>

          <ChartCard title="Composición de ingresos tributarios YTD">
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.taxComposition,
                  'Ingresos tributarios',
                ),
              ]}
            />
          </ChartCard>
        </div>

        <ChartCard title="IVA - Variación interanual">
          <PlotlyChart
            data={[
              createBarTrace(
                ivaAnnual,
                'IVA',
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
                title: 'Variación interanual %',
              },
            }}
          />
        </ChartCard>
      </main>
    </>
  )
}

export default FiscalBalance
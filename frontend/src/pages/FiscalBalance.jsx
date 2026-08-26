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
    keys: [
      'ingresos_tributarios_total',
      'ingresos_aportes_contribuciones_seguridad_social',
    ],
    label: 'Tributarios y contribuciones sociales',
  },
  {
    key: 'ingresos_rentas_propiedad_netas',
    label: 'Rentas de la propiedad',
  },
  {
    keys: [
      'ingresos_no_tributarios',
      'ingresos_ventas_bienes_servicios_adm_publica',
      'ingresos_operacion',
      'ingresos_transferencias_corrientes',
      'ingresos_otros',
      'ingresos_superavit_operativo_empresas_publicas',
    ],
    label: 'Otros ingresos corrientes',
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


const imigExpenseComposition = [
  {
    keys: [
      'imig_gasto_prestaciones_jubilaciones',
      'imig_gasto_prestaciones_pensiones_no_contributivas',
      'imig_gasto_prestaciones_asignaciones',
      'imig_gasto_prestaciones_otros_programas',
      'imig_gasto_prestaciones_inssjp',
    ],
    label: 'Prestaciones sociales',
  },
  {
    keys: [
      'imig_gasto_subsidios_energia',
      'imig_gasto_subsidios_transporte',
      'imig_gasto_subsidios_otras_funciones',
    ],
    label: 'Subsidios económicos',
  },
  {
    keys: [
      'imig_gasto_funcionamiento_salarios',
      'imig_gasto_funcionamiento_otros',
    ],
    label: 'Gastos de funcionamiento y otros',
  },
  {
    keys: [
      'imig_gasto_provincias_desarrollo_social',
      'imig_gasto_provincias_educacion',
      'imig_gasto_provincias_salud',
      'imig_gasto_provincias_seguridad_social',
      'imig_gasto_provincias_otras',
    ],
    label: 'Transferencias corrientes a provincias',
  },
  {
    key: 'imig_gasto_transferencias_universidades',
    label: 'Transferencias a universidades',
  },
  {
    keys: [
      'imig_gasto_otros_deficit_empresas_publicas',
      'imig_gasto_otros_resto',
    ],
    label: 'Otros gastos corrientes',
  },
]


const aifExpenseComposition = [
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
    label: 'Prestaciones de la seguridad social',
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
    label: 'Déficit de empresas públicas',
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


function primaryExpense(row) {
  return (
    (Number(row.gastos_antes_figurativos) || 0) -
    (Number(row.gastos_intereses_netos) || 0)
  )
}


function sumPrimaryExpense(rows) {
  return rows.reduce(
    (sum, row) => sum + primaryExpense(row),
    0,
  )
}


function getComposition(
  rows,
  columns,
) {
  return columns.map((column) => ({
    label: column.label,
    value: (column.keys ?? [column.key])
      .reduce(
        (total, key) =>
          total + sumColumn(rows, key),
        0,
      ),
  }))
}


function hasCompleteComposition(
  row,
  columns,
) {
  return columns.every((column) =>
    (column.keys ?? [column.key]).every(
      (key) => Number.isFinite(row[key]),
    ),
  )
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

    const latestTaxRow = rows.findLast(
      (row) => hasCompleteComposition(
        row,
        taxComposition,
      ),
    )

    const latestTaxDate = latestTaxRow
      ? new Date(
        `${latestTaxRow.period}T00:00:00`,
      )
      : null

    const latestExpenseRow = rows.findLast(
      (row) => hasCompleteComposition(
        row,
        imigExpenseComposition,
      ),
    )

    const latestExpenseDate = latestExpenseRow
      ? new Date(
        `${latestExpenseRow.period}T00:00:00`,
      )
      : null

    const taxYtdRows = latestTaxDate
      ? getYtdRows(
        rows,
        latestTaxDate.getFullYear(),
        latestTaxDate.getMonth() + 1,
      )
      : []

    const expenseYtdRows = latestExpenseDate
      ? getYtdRows(
        rows,
        latestExpenseDate.getFullYear(),
        latestExpenseDate.getMonth() + 1,
      )
      : currentYtdRows

    const expenseColumns = latestExpenseRow
      ? imigExpenseComposition
      : aifExpenseComposition

    const previousYtdRows = getYtdRows(
      rows,
      previousYear,
      latestMonth,
    )

    const revenueYtd = sumColumn(
      currentYtdRows,
      'ingresos_antes_figurativos',
    )

    const previousRevenueYtd = sumColumn(
      previousYtdRows,
      'ingresos_antes_figurativos',
    )

    const primaryExpenseYtd = sumPrimaryExpense(
      currentYtdRows,
    )

    const previousPrimaryExpenseYtd =
      sumPrimaryExpense(
        previousYtdRows,
      )

    const totalExpenseYtd = sumColumn(
      currentYtdRows,
      'gastos_antes_figurativos',
    )

    const previousTotalExpenseYtd =
      sumColumn(
        previousYtdRows,
        'gastos_antes_figurativos',
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
            'ingresos_antes_figurativos',
          periodKey: 'period',
        },
      )

    const primaryExpenseRows = rows.map(
      (row) => ({
        ...row,
        gastos_primarios_consolidados:
          primaryExpense(row),
      }),
    )

    const primaryExpenseSeries =
      calculateSeriesVariations(
        primaryExpenseRows,
        {
          valueKey:
            'gastos_primarios_consolidados',
          periodKey: 'period',
        },
      )

    const taxRows = rows.filter(
      (row) => Number.isFinite(
        row.ingresos_tributarios_iva,
      ),
    )

    const ivaSeries =
      calculateSeriesVariations(
        taxRows,
        {
          valueKey:
            'ingresos_tributarios_iva',
          periodKey: 'period',
        },
      )

    return {
      latestRow,
      latestTaxPeriod:
        latestTaxRow?.period ?? null,
      latestExpensePeriod:
        latestExpenseRow?.period ?? latestRow.period,
      expenseSource:
        latestExpenseRow ? 'IMIG' : 'AIF',

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
          expenseYtdRows,
          expenseColumns,
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
          taxYtdRows,
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

  const aifPeriod = formatPeriod(
    latestRow.period,
  )

  const taxPeriod = formatPeriod(
    analysis.latestTaxPeriod,
  )

  const expensePeriod = formatPeriod(
    analysis.latestExpensePeriod,
  )

  const taxCoverageNote =
    analysis.latestTaxPeriod === latestRow.period
      ? `Fuente IMIG. Distribuye los ingresos impositivos; no incluye contribuciones a la seguridad social ni operaciones figurativas. Datos hasta ${taxPeriod}.`
      : `Fuente IMIG. Distribuye los ingresos impositivos; no incluye contribuciones a la seguridad social ni operaciones figurativas. Datos hasta ${taxPeriod}; el balance AIF llega hasta ${aifPeriod}.`

  const expenseUsesImig =
    analysis.expenseSource === 'IMIG'

  const expenseChartTitle = expenseUsesImig
    ? 'Composición del gasto corriente primario IMIG YTD'
    : 'Composición del gasto corriente AIF YTD'

  const expenseCoverageNote = expenseUsesImig
    ? (
      analysis.latestExpensePeriod === latestRow.period
        ? `Fuente IMIG. Gasto corriente primario consolidado: excluye intereses, gasto de capital y operaciones figurativas. Datos hasta ${expensePeriod}.`
        : `Fuente IMIG. Gasto corriente primario consolidado: excluye intereses, gasto de capital y operaciones figurativas. Datos hasta ${expensePeriod}; el balance AIF llega hasta ${aifPeriod}.`
    )
    : `Incluye intereses y muestra la apertura contable del gasto corriente antes de figurativos. Datos hasta ${aifPeriod}.`

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
            label="Ingresos consolidados YTD"
            value={formatMoney(
              analysis.revenueYtd,
            )}
          />

          <StatCard
            label="Gasto total consolidado YTD"
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
            label="Ingresos consolidados YTD vs año anterior"
            value={formatPercentage(
              analysis.revenueYtdVariation,
            )}
          />

          <StatCard
            label="Gasto total consolidado YTD vs año anterior"
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
            label="Últimos ingresos consolidados"
            value={formatMoney(
              latestRow.ingresos_antes_figurativos,
            )}
          />

          <StatCard
            label="Último gasto total consolidado"
            value={formatMoney(
              latestRow.gastos_antes_figurativos,
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
          Expresado en millones de ARS corrientes. Ingresos y gastos consolidados antes de operaciones figurativas del Sector Público Nacional.
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

        <ChartCard title="Variación interanual de ingresos y gasto primario consolidados">
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

        <p className="chart-description">
          Las composiciones siguientes muestran
          flujos consolidados del Sector Público
          Nacional y no incorporan operaciones
          figurativas. AIF presenta la clasificación
          contable de la Cuenta
          Ahorro-Inversión-Financiamiento; IMIG
          reagrupa ingresos y gastos para el informe
          mensual.
        </p>

        <div className="chart-row">
          <ChartCard
            title={expenseChartTitle}
            subtitle={expenseCoverageNote}
          >
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.expenseComposition,
                  expenseUsesImig
                    ? 'Gasto corriente primario'
                    : 'Gasto corriente AIF',
                ),
              ]}
            />
          </ChartCard>

          <ChartCard
            title="Transferencias corrientes AIF YTD"
            subtitle={`Fuente AIF. Transferencias incluidas en el gasto corriente antes de figurativos, clasificadas por sector receptor. Datos hasta ${aifPeriod}.`}
          >
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
          <ChartCard
            title="Composición de ingresos corrientes AIF YTD"
            subtitle={`Fuente AIF. Ingresos corrientes antes de figurativos; no incluye recursos de capital. Datos hasta ${aifPeriod}.`}
          >
            <PlotlyChart
              data={[
                createPieTrace(
                  analysis.revenueComposition,
                  'Ingresos corrientes',
                ),
              ]}
            />
          </ChartCard>

          <ChartCard
            title="Composición de ingresos impositivos IMIG YTD"
            subtitle={taxCoverageNote}
          >
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

        <ChartCard
          title="IVA - Variación interanual"
          subtitle={taxCoverageNote}
        >
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

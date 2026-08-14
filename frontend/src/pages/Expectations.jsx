import { useEffect, useMemo, useState } from 'react'

import { fetchDolt } from '../api/dolt'
import ChartCard from '../components/ChartCard'
import PlotlyChart from '../components/PlotlyChart'
import StatCard from '../components/StatCard'
import { createLineTrace }  from '../utils/charts'
import {
  calculatePointChange,
  normalizeNumericRows,
} from '../utils/series'
import {
  formatPeriod,
  formatPointChange,
  formatIndex,
} from '../utils/formatters'

const TABLE_NAME = 'consumer_confidence_argentina'

const SERIES = {
  nacional: {
    key: 'icc_nacional',
    label: 'ICC Nacional',
  },
  components: [
    {
      key: 'icc_situacion_personal',
      label: 'Situación personal',
    },
    {
      key: 'icc_situacion_macro',
      label: 'Situación macroeconómica',
    },
    {
      key: 'icc_bienes_durables_inmuebles',
      label: 'Bienes durables e inmuebles',
    },
  ],
  regions: [
    {
      key: 'icc_capital',
      label: 'Capital',
    },
    {
      key: 'icc_gba',
      label: 'GBA',
    },
    {
      key: 'icc_interior',
      label: 'Interior',
    },
  ],
}


function Expectations() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadData() {
      try {
        const sql = `
          SELECT *
          FROM ${TABLE_NAME}
          ORDER BY period ASC
        `

        const data = await fetchDolt(sql)

        setRows(
          normalizeNumericRows(
            data,
            ['period'],
          ),
        )
      } catch (loadError) {
        console.error(loadError)
        setError(loadError.message)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const analysis = useMemo(() => {
    const nationalRows = rows.filter(
      (row) => row.icc_nacional !== null,
    )

    if (!nationalRows.length) {
      return null
    }

    const latest = nationalRows.at(-1)
    const previous = nationalRows.at(-2)

    const previousYear = nationalRows.find(
      (row) => {
        const currentDate = new Date(
          `${latest.period}T00:00:00`,
        )

        const previousDate = new Date(
          `${row.period}T00:00:00`,
        )

        return (
          currentDate.getFullYear()
            - previousDate.getFullYear() === 1
          && currentDate.getMonth()
            === previousDate.getMonth()
        )
      },
    )

    return {
      latest,
      monthlyChange: calculatePointChange(
        latest.icc_nacional,
        previous?.icc_nacional,
      ),
      annualChange: calculatePointChange(
        latest.icc_nacional,
        previousYear?.icc_nacional,
      ),
    }
  }, [rows])

  if (loading) {
    return <p>Cargando expectativas...</p>
  }

  if (error) {
    return (
      <div className="error">
        Error al cargar expectativas: {error}
      </div>
    )
  }

  if (!analysis) {
    return <p>No hay datos disponibles.</p>
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Expectativas</h1>

        <p className="subtitle">
          Confianza del consumidor y expectativas económicas
        </p>

        <p className="last-updated">
          Último dato: {formatPeriod(analysis.latest.period)}
        </p>
      </header>

      <div className="stats">
        <StatCard
          label="ICC Nacional"
          value={formatIndex(
            analysis.latest.icc_nacional,
          )}
        />

        <StatCard
          label="Cambio mensual"
          value={formatPointChange(
            analysis.monthlyChange,
          )}
        />

        <StatCard
          label="Cambio interanual"
          value={formatPointChange(
            analysis.annualChange,
          )}
        />

        <StatCard
          label="Situación personal"
          value={formatIndex(
            analysis.latest.icc_situacion_personal,
          )}
        />

        <StatCard
          label="Situación macroeconómica"
          value={formatIndex(
            analysis.latest.icc_situacion_macro,
          )}
        />

        <StatCard
          label="Bienes durables e inmuebles"
          value={formatIndex(
            analysis.latest.icc_bienes_durables_inmuebles,
          )}
        />
      </div>

      <ChartCard title="Índice de Confianza del Consumidor">
        <PlotlyChart
          data={[
            createLineTrace(
              rows,
              SERIES.nacional.label,
              {
                xKey: 'period',
                yKey: SERIES.nacional.key,
                mode: 'lines',
              },
            )
          ]}
          layout={{
            yaxis: {
              title: 'Índice',
            },
            shapes: [
              {
                type: 'line',
                xref: 'paper',
                x0: 0,
                x1: 1,
                y0: 50,
                y1: 50,
                line: {
                  dash: 'dot',
                  width: 1,
                },
              },
            ],
          }}
        />
      </ChartCard>

       <ChartCard title="Componentes del ICC">
        <PlotlyChart
          data={SERIES.components.map(
            (series) => createLineTrace(
              rows,
              series.label,
              {
                xKey: 'period',
                yKey: series.key,
                mode: 'lines',
              },
            ),
          )}
          layout={{
            yaxis: {
              title: 'Índice',
            },
          }}
        />
      </ChartCard>

      <ChartCard title="ICC por región">
        <PlotlyChart
          data={SERIES.regions.map(
            (series) => createLineTrace(
              rows,
              series.label,
              {
                xKey: 'period',
                yKey: series.key,
                mode: 'lines',
              },
            ),
          )}
          layout={{
            yaxis: {
              title: 'Índice',
            },
          }}
        />
      </ChartCard> 

    </div>
  )
}

export default Expectations
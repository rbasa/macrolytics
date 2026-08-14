import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { fetchDolt } from '../api/dolt'
import ChartCard from '../components/ChartCard'
import PlotlyChart from '../components/PlotlyChart'
import StatCard from '../components/StatCard'

import {
  createLineTrace,
} from '../utils/charts'

import {
  formatNumber,
  formatPeriod,
} from '../utils/formatters'


function getMid(bid, ask) {
  if (
    !Number.isFinite(bid) &&
    !Number.isFinite(ask)
  ) {
    return null
  }

  if (!Number.isFinite(bid)) {
    return ask
  }

  if (!Number.isFinite(ask)) {
    return bid
  }

  return (bid + ask) / 2
}


function transformRows(rows) {
  const dataByDate = new Map()

  rows.forEach((row) => {
    const date = row.DATE

    if (!dataByDate.has(date)) {
      dataByDate.set(date, {
        period: date,
      })
    }

    const current = dataByDate.get(date)
    const rate = Number(row.rate)

    if (!Number.isFinite(rate)) {
      return
    }

    if (
      row.pair === 'UVA_ARS' &&
      row.kind === 'index'
    ) {
      current.uva = rate
    }

    if (row.pair === 'USD_ARS') {
      if (row.kind === 'bid') {
        current.usdBid = rate
      }

      if (row.kind === 'ask') {
        current.usdAsk = rate
      }
    }

    if (row.pair === 'USDB_ARS') {
      if (row.kind === 'bid') {
        current.usdbBid = rate
      }

      if (row.kind === 'ask') {
        current.usdbAsk = rate
      }
    }
  })

  return Array.from(
    dataByDate.values(),
  )
    .sort(
      (a, b) =>
        String(a.period).localeCompare(
          String(b.period),
        ),
    )
    .map((row) => {
      const usd = getMid(
        row.usdBid,
        row.usdAsk,
      )

      const usdBlue = getMid(
        row.usdbBid,
        row.usdbAsk,
      )

      return {
        ...row,

        usd,
        usdBlue,

        uvaUsd:
          Number.isFinite(row.uva) &&
          Number.isFinite(usd) &&
          usd !== 0
            ? row.uva / usd
            : null,

        uvaUsdBlue:
          Number.isFinite(row.uva) &&
          Number.isFinite(usdBlue) &&
          usdBlue !== 0
            ? row.uva / usdBlue
            : null,
      }
    })
}


function getLastValue(
  rows,
  key,
) {
  for (
    let index = rows.length - 1;
    index >= 0;
    index -= 1
  ) {
    if (Number.isFinite(rows[index][key])) {
      return {
        value: rows[index][key],
        period: rows[index].period,
      }
    }
  }

  return {
    value: null,
    period: null,
  }
}


function UvaAnalysis() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function loadData() {
      try {
        setLoading(true)
        setError(null)
        const rawRows = await fetchUvaData()

        const transformedRows =
          transformRows(rawRows)

        if (
          !cancelled &&
          transformedRows.length
        ) {
          setRows(transformedRows)
        }
      } catch (loadError) {
        console.error(loadError)

        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Error desconocido',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadData()

    return () => {
      cancelled = true
    }
  }, [])


  const analysis = useMemo(() => {
    if (!rows.length) {
      return null
    }

    return {
      latestUva:
        getLastValue(
          rows,
          'uva',
        ),

      latestUvaBlue:
        getLastValue(
          rows,
          'uvaUsdBlue',
        ),

      latestUvaOfficial:
        getLastValue(
          rows,
          'uvaUsd',
        ),

      latestBlue:
        getLastValue(
          rows,
          'usdBlue',
        ),

      latestOfficial:
        getLastValue(
          rows,
          'usd',
        ),

      startPeriod:
        rows.at(0)?.period,

      endPeriod:
        rows.at(-1)?.period,
    }
  }, [rows])


  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>Cargando datos UVA...</p>
      </div>
    )
  }


  if (error) {
    return (
      <div className="error">
        Error al cargar datos UVA: {error}
      </div>
    )
  }


  if (!analysis) {
    return (
      <div className="error">
        No hay datos UVA disponibles.
      </div>
    )
  }
function formatQueryDate(date) {
  return date.toISOString().slice(0, 10)
}


async function fetchUvaData() {
  const start = new Date('2017-01-01T00:00:00')
  const today = new Date()

  const rows = []
  let current = new Date(start)

  while (current < today) {
    const chunkEnd = new Date(current)

    chunkEnd.setMonth(
      chunkEnd.getMonth() + 6,
    )

    if (chunkEnd > today) {
      chunkEnd.setTime(today.getTime())
    }

    const startDate = formatQueryDate(current)
    const endDate = formatQueryDate(chunkEnd)

    const sql = `
      SELECT
        DATE,
        pair,
        kind,
        rate
      FROM fx_rate
      WHERE pair IN (
        'UVA_ARS',
        'USD_ARS',
        'USDB_ARS'
      )
        AND DATE >= '${startDate}'
        AND DATE < '${endDate}'
      ORDER BY DATE ASC, pair ASC
    `

    const chunk = await fetchDolt(sql)

    rows.push(...chunk)

    current = chunkEnd
  }

  return rows
}

  return (
    <>
      <header>
        <h1>
          Análisis UVA
        </h1>

        <p className="subtitle">
          Unidad de Valor Adquisitivo y tipos de cambio
        </p>

        <p className="last-updated">
          Último dato:{' '}
          {formatPeriod(
            analysis.endPeriod,
          )}
        </p>
      </header>

      <main>
        <section className="stats">
          <StatCard
            label="Último valor UVA"
            value={formatNumber(
              analysis.latestUva.value,
              {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              },
            )}
            subinfo={
              analysis.latestUva.period
                ? analysis.latestUva.period
                : undefined
            }
          />

          <StatCard
            label="UVA en USD Blue"
            value={formatNumber(
              analysis.latestUvaBlue.value,
              {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              },
            )}
            subinfo={
              Number.isFinite(
                analysis.latestBlue.value,
              )
                ? `USD Blue: ${formatNumber(
                    analysis.latestBlue.value,
                    {
                      maximumFractionDigits: 2,
                    },
                  )}`
                : undefined
            }
          />

          <StatCard
            label="UVA en USD Oficial"
            value={formatNumber(
              analysis.latestUvaOfficial.value,
              {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              },
            )}
            subinfo={
              Number.isFinite(
                analysis.latestOfficial.value,
              )
                ? `USD Oficial: ${formatNumber(
                    analysis.latestOfficial.value,
                    {
                      maximumFractionDigits: 2,
                    },
                  )}`
                : undefined
            }
          />

          <StatCard
            label="Rango de datos"
            value={`${analysis.startPeriod} → ${analysis.endPeriod}`}
          />
        </section>

        <ChartCard title="UVA medido en USD">
          <PlotlyChart
            data={[
              createLineTrace(
                rows,
                'UVA Blue',
                {
                  xKey: 'period',
                  yKey: 'uvaUsdBlue',
                  mode: 'lines',
                },
              ),

              createLineTrace(
                rows,
                'UVA Oficial',
                {
                  xKey: 'period',
                  yKey: 'uvaUsd',
                  mode: 'lines',
                },
              ),
            ]}
            layout={{
              xaxis: {
                title: 'Fecha',
              },

              yaxis: {
                title: 'Valor en USD',
              },
            }}
          />
        </ChartCard>
      </main>
    </>
  )
}

export default UvaAnalysis
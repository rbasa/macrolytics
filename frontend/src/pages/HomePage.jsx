import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchDolt } from '../api/dolt.js'
import { fetchPublicGoogleSheet } from '../api/googleSheets.js'
import {
  CALENDAR_SOURCE,
  CALENDAR_SHEET,
  ECONOMIC_DATASETS,
} from '../data/economicCalendar.js'


const RECENT_UPDATES_QUERY = `
  SELECT date, message
  FROM dolt_log
  WHERE message LIKE '%IPC%'
    OR message LIKE '%inflation%'
    OR message LIKE '%foreign trade%'
    OR message LIKE '%EMAE%'
    OR message LIKE '%GDP%'
    OR message LIKE '%PBI%'
    OR message LIKE '%fiscal%'
    OR message LIKE '%consumer confidence%'
  ORDER BY date DESC
  LIMIT 100
`

const MAX_CALENDAR_ITEMS = 6

const sections = [
  {
    label: 'Precios',
    to: '/Inflation',
  },
  {
    label: 'Actividad Económica',
    to: '/economicActivity',
  },
  {
    label: 'Balanza Comercial',
    to: '/tradeBalance',
  },
  {
    label: 'Balance Fiscal',
    to: '/fiscal-balance',
  },
  {
    label: 'Expectativas',
    to: '/expectations',
  },
  {
    label: 'Sector Financiero',
    to: '/financial-sector',
  },
  {
    label: 'Análisis UVA',
    to: '/uvaAnalysis',
  },
]


function parseCalendarDate(value) {
  const datePart = String(value).slice(0, 10)
  const date = new Date(`${datePart}T00:00:00`)

  return Number.isNaN(date.getTime())
    ? null
    : date
}


function formatCalendarDay(value) {
  const date = parseCalendarDate(value)

  if (!date) {
    return { day: '—', month: '' }
  }

  return {
    day: date.toLocaleDateString('es-AR', { day: '2-digit' }),
    month: date.toLocaleDateString('es-AR', { month: 'short' })
      .replace('.', '')
      .toUpperCase(),
  }
}


function CalendarItem({ item, detail }) {
  const { day, month } = formatCalendarDay(item.date)

  return (
    <li className="economic-calendar-item">
      <Link className="economic-calendar-link" to={item.to}>
        <time className="economic-calendar-date" dateTime={item.date}>
          <span className="economic-calendar-day">{day}</span>
          <span className="economic-calendar-month">{month}</span>
        </time>

        <span className="economic-calendar-copy">
          <strong>{item.label}</strong>
          <span>{detail}</span>
        </span>

        <span className="economic-calendar-arrow" aria-hidden="true">
          →
        </span>
      </Link>
    </li>
  )
}


function EconomicCalendar() {
  const [recentUpdates, setRecentUpdates] = useState([])
  const [upcomingReleases, setUpcomingReleases] = useState([])
  const [recentLoading, setRecentLoading] = useState(true)
  const [recentError, setRecentError] = useState(false)
  const [upcomingLoading, setUpcomingLoading] = useState(true)
  const [upcomingError, setUpcomingError] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadRecentUpdates() {
      try {
        const rows = await fetchDolt(RECENT_UPDATES_QUERY)
        const foundDatasets = new Set()
        const updates = []

        rows.forEach((row) => {
          const dataset = ECONOMIC_DATASETS.find(
            (candidate) => candidate.messagePattern.test(row.message),
          )

          if (!dataset || foundDatasets.has(dataset.id)) {
            return
          }

          foundDatasets.add(dataset.id)
          updates.push({
            date: String(row.date).slice(0, 10),
            id: dataset.id,
            label: dataset.label,
            to: dataset.to,
          })
        })

        if (!cancelled) {
          setRecentUpdates(updates.slice(0, MAX_CALENDAR_ITEMS))
        }
      } catch (error) {
        console.error('No se pudieron cargar las novedades económicas', error)
        if (!cancelled) {
          setRecentError(true)
        }
      } finally {
        if (!cancelled) {
          setRecentLoading(false)
        }
      }
    }

    async function loadUpcomingReleases() {
      try {
        const rows = await fetchPublicGoogleSheet(CALENDAR_SHEET)
        const releases = rows
          .filter((row) => String(row.status).toLowerCase() === 'confirmed')
          .map((row) => ({
            id: row.event_id,
            datasetKey: row.dataset_key,
            date: String(row.date).slice(0, 10),
            label: row.title,
            period: row.reference_period,
            to: row.route,
          }))
          .filter((release) => (
            release.date
            && release.label
            && String(release.to).startsWith('/')
          ))
          .sort((left, right) => left.date.localeCompare(right.date))

        if (!cancelled) {
          setUpcomingReleases(releases)
        }
      } catch (error) {
        console.error('No se pudo cargar el calendario económico', error)
        if (!cancelled) {
          setUpcomingError(true)
        }
      } finally {
        if (!cancelled) {
          setUpcomingLoading(false)
        }
      }
    }

    loadRecentUpdates()
    loadUpcomingReleases()

    return () => {
      cancelled = true
    }
  }, [])

  const visibleUpcomingReleases = useMemo(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const latestUpdateByDataset = new Map(
      recentUpdates.map((update) => [update.id, parseCalendarDate(update.date)]),
    )

    return upcomingReleases
      .map((release) => {
        const releaseDate = parseCalendarDate(release.date)

        if (!releaseDate || releaseDate >= today) {
          return release
        }
        if (recentLoading || recentError) {
          return null
        }

        const latestUpdate = latestUpdateByDataset.get(release.datasetKey)
        if (latestUpdate && latestUpdate >= releaseDate) {
          return null
        }

        return { ...release, overdue: true }
      })
      .filter(Boolean)
      .slice(0, MAX_CALENDAR_ITEMS)
  }, [recentError, recentLoading, recentUpdates, upcomingReleases])

  return (
    <section className="economic-calendar" aria-labelledby="calendar-title">
      <div className="economic-calendar-heading">
        <div>
          <p className="economic-calendar-kicker">Agenda macro</p>
          <h2 id="calendar-title">Calendario económico</h2>
        </div>

        <a href={CALENDAR_SOURCE} target="_blank" rel="noreferrer">
          Calendario oficial INDEC ↗
        </a>
      </div>

      <div className="economic-calendar-grid">
        <article className="economic-calendar-panel">
          <div className="economic-calendar-panel-heading">
            <span className="economic-calendar-status economic-calendar-status--recent" />
            <h3>Últimos datos actualizados</h3>
          </div>

          {recentLoading && (
            <p className="economic-calendar-empty">Cargando novedades…</p>
          )}

          {!recentLoading && recentUpdates.length === 0 && (
            <p className="economic-calendar-empty">
              No hay novedades disponibles en este momento.
            </p>
          )}

          {recentUpdates.length > 0 && (
            <ul className="economic-calendar-list">
              {recentUpdates.map((update) => (
                <CalendarItem
                  key={update.id}
                  item={update}
                  detail="Base de datos actualizada"
                />
              ))}
            </ul>
          )}
        </article>

        <article className="economic-calendar-panel">
          <div className="economic-calendar-panel-heading">
            <span className="economic-calendar-status economic-calendar-status--upcoming" />
            <h3>Próximas publicaciones</h3>
          </div>

          {upcomingLoading && (
            <p className="economic-calendar-empty">Cargando agenda…</p>
          )}

          {!upcomingLoading && upcomingError && (
            <p className="economic-calendar-empty">
              No se pudo leer la agenda de Google Sheets.
            </p>
          )}

          {!upcomingLoading && !upcomingError && visibleUpcomingReleases.length > 0 && (
            <ul className="economic-calendar-list">
              {visibleUpcomingReleases.map((release) => (
                <CalendarItem
                  key={release.id || `${release.date}-${release.label}`}
                  item={release}
                  detail={release.overdue
                    ? `Pendiente de carga · ${release.period}`
                    : release.period}
                />
              ))}
            </ul>
          )}

          {!upcomingLoading && !upcomingError && visibleUpcomingReleases.length === 0 && (
            <p className="economic-calendar-empty">
              No hay publicaciones confirmadas en el calendario cargado.
            </p>
          )}
        </article>
      </div>

      <p className="economic-calendar-note">
        Se excluyen las actualizaciones diarias financieras y cambiarias.
      </p>
    </section>
  )
}

function HomePage() {
  return (
    <>
      <header className="home-header">
        <h1>📊 Macrolytics</h1>

        <p className="subtitle">
          Análisis macroeconómico en tiempo real
        </p>
      </header>

      <main className="home-content">
        <EconomicCalendar />

        <ul className="home-sections">
          {sections.map((section) => (
            <li
              className="home-section-item"
              key={section.to}
            >
              <Link
                className="home-card"
                to={section.to}
              >
                {section.label}
              </Link>
            </li>
          ))}

          <li className="home-section-item">
            <div className="home-card home-card-disabled">
              Análisis Otros (próximo)
            </div>
          </li>
        </ul>
      </main>
    </>
  )
}

export default HomePage

import { Link } from 'react-router-dom'

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
    label: 'Análisis UVA',
    to: '/uvaAnalysis',
  },
  {
    label: 'Expectativas',
    to: '/expectations',
  },
]

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
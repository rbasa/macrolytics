import { NavLink } from 'react-router-dom'

const links = [
  {
    label: 'Inicio',
    to: '/',
  },
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
    label: 'Análisis UVA',
    to: '/uvaAnalysis',
  },
]

function Navbar() {
  return (
    <nav className="navbar">
      <NavLink className="brand" to="/">
        📈 Macrolytics
      </NavLink>

      <div className="nav-links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              isActive
                ? 'nav-link active'
                : 'nav-link'
            }
          >
            {link.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

export default Navbar
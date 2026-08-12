import {
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'

import Layout from './components/Layout.jsx'
import HomePage from './pages/HomePage.jsx'
import Inflation from './pages/Inflation.jsx'
import EconomicActivity from './pages/EconomicActivity.jsx'
import TradeBalance from './pages/TradeBalance.jsx'
import UvaAnalysis from './pages/UvaAnalysis.jsx'
import FiscalBalance from './pages/FiscalBalance.jsx'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />

        <Route
          path="inflation"
          element={<Inflation />}
        />

        <Route
          path="economicActivity"
          element={<EconomicActivity />}
        />
        <Route
          path="tradeBalance"
          element={<TradeBalance />}
        />
        <Route
          path="uvaAnalysis"
          element={<UvaAnalysis />}
        />

        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
        <Route
          path="fiscal-balance"
          element={<FiscalBalance />}
        />
      </Route>
    </Routes>
  )
}

export default App
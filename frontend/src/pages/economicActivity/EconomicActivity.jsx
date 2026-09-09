import EmaeAnalysis from './EmaeAnalysis.jsx'
import PbiAnalysis from './PbiAnalysis.jsx'


function EconomicActivity() {
  return (
    <>
      <header>
        <h1>🏭 Actividad Económica</h1>
        <p className="subtitle">
          PBI trimestral y seguimiento mensual del EMAE
        </p>
      </header>

      <main className="actividad-economica">
        <PbiAnalysis />
        <EmaeAnalysis />
      </main>
    </>
  )
}

export default EconomicActivity

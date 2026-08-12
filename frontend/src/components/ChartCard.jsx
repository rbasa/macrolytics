function ChartCard({ title, children }) {
  return (
    <section className="chart-container">
      <h2 className="chart-title">
        {title}
      </h2>

      {children}
    </section>
  )
}

export default ChartCard
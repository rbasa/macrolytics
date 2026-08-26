function ChartCard({
  title,
  subtitle,
  children,
}) {
  return (
    <section className="chart-container">
      <h2 className="chart-title">
        {title}
      </h2>

      {subtitle && (
        <p className="chart-note">
          {subtitle}
        </p>
      )}

      {children}
    </section>
  )
}

export default ChartCard

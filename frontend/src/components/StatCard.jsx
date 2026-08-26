function StatCard({ label, value, subinfo }) {
  return (
    <article className="stat-card">
      <div className="stat-label">
        {label}
      </div>

      <div className="stat-value">
        {value}
      </div>

      {subinfo && (
        <div className="stat-subinfo">
          {subinfo}
        </div>
      )}
    </article>
  )
}

export default StatCard

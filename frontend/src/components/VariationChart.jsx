import ChartCard from './ChartCard.jsx'
import PlotlyChart from './PlotlyChart.jsx'

import { createBarTrace } from '../utils/charts.js'


function VariationChart({
  title,
  monthlyData,
  annualData,
  xAxisTitle,
}) {
  const charts = [
    {
      subtitle: 'Mensual',
      data: monthlyData,
      traceName: 'Variación mensual',
    },
    {
      subtitle: 'Interanual',
      data: annualData,
      traceName: 'Variación interanual',
    },
  ]

  return (
    <ChartCard title={title}>
      <div className="chart-row">
        {charts.map((chart) => (
          <div
            className="chart-column"
            key={chart.subtitle}
          >
            <h3 className="chart-subtitle">
              {chart.subtitle}
            </h3>

            <PlotlyChart
              data={[
                createBarTrace(
                  chart.data,
                  chart.traceName,
                ),
              ]}
              layout={{
                xaxis: {
                  title: xAxisTitle,
                  automargin: true,
                },
                yaxis: {
                  title: 'Variación %',
                },
              }}
            />
          </div>
        ))}
      </div>
    </ChartCard>
  )
}

export default VariationChart
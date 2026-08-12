import {
  useEffect,
  useRef,
} from 'react'

import Plotly from 'plotly.js-dist-min'

function PlotlyChart({
  data,
  layout = {},
  height = 520,
}) {
  const chartRef = useRef(null)

  useEffect(() => {
    const chartElement = chartRef.current

    if (!chartElement) {
      return undefined
    }

    Plotly.react(
      chartElement,
      data,
      {
        autosize: true,
        margin: {
          left: 60,
          right: 20,
          top: 30,
          bottom: 80,
        },
        paper_bgcolor: '#f7fafc',
        plot_bgcolor: '#f7fafc',
        ...layout,
      },
      {
        responsive: true,
        displaylogo: false,
      },
    )

    return () => {
      Plotly.purge(chartElement)
    }
  }, [data, layout])

  return (
    <div
      ref={chartRef}
      className="chart"
      style={{
        width: '100%',
        height,
      }}
    />
  )
}

export default PlotlyChart
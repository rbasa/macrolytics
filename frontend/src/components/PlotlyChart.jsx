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

    const defaultLayout = {
      autosize: true,

      margin: {
        left: 60,
        right: 20,
        top: 30,
        bottom: 90,
      },

      legend: {
        orientation: 'h',
        x: 0.5,
        xanchor: 'center',
        y: -0.15,
        yanchor: 'top',
      },

      paper_bgcolor: '#f7fafc',
      plot_bgcolor: '#f7fafc',
    }

    Plotly.react(
      chartElement,
      data,
      {
        ...defaultLayout,
        ...layout,

        margin: {
          ...defaultLayout.margin,
          ...layout.margin,
        },

        legend: {
          ...defaultLayout.legend,
          ...layout.legend,
        },
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
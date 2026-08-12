export function createBarTrace(
  values,
  name,
  {
    xKey = 'label',
    yKey = 'value',
    positiveColor,
    negativeColor,
  } = {},
) {
  const filteredValues = values.filter(
    (item) => Number.isFinite(item[yKey]),
  )

  const trace = {
    x: filteredValues.map(
      (item) => item[xKey],
    ),
    y: filteredValues.map(
      (item) => item[yKey],
    ),
    type: 'bar',
    name,
  }

  if (positiveColor && negativeColor) {
    trace.marker = {
      color: filteredValues.map(
        (item) =>
          item[yKey] >= 0
            ? positiveColor
            : negativeColor,
      ),
    }
  }

  return trace
}
export function createPieTrace(
  values,
  name,
  {
    labelKey = 'label',
    valueKey = 'value',
  } = {},
) {
  const filteredValues = values.filter(
    (item) => Number.isFinite(item[valueKey]) && item[valueKey] > 0,
  )

  return {
    labels: filteredValues.map(
      (item) => item[labelKey],
    ),
    values: filteredValues.map(
      (item) => item[valueKey],
    ),
    type: 'pie',
    name,
    hole: 0.35,
  }
}

export function createLineTrace(
  values,
  name,
  {
    xKey = 'period',
    yKey = 'value',
    mode = 'lines+markers',
  } = {},
) {
  const filteredValues = values.filter(
    (item) => Number.isFinite(item[yKey]),
  )

  return {
    x: filteredValues.map(
      (item) => item[xKey],
    ),
    y: filteredValues.map(
      (item) => item[yKey],
    ),
    type: 'scatter',
    mode,
    name,
  }
}
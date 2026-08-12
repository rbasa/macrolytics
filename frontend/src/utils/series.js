export function parseNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const parsedValue = Number(value)

  return Number.isFinite(parsedValue)
    ? parsedValue
    : null
}


export function normalizeNumericRows(
  rows,
  nonNumericKeys = ['fecha', 'period'],
) {
  return rows.map((row) => {
    const normalizedRow = {}

    Object.entries(row).forEach(([key, value]) => {
      normalizedRow[key] = nonNumericKeys.includes(key)
        ? value
        : parseNumber(value)
    })

    return normalizedRow
  })
}


export function calculateVariation(
  currentValue,
  previousValue,
) {
  if (
    !Number.isFinite(currentValue) ||
    !Number.isFinite(previousValue) ||
    previousValue === 0
  ) {
    return null
  }

  return (
    (currentValue / previousValue) - 1
  ) * 100
}


export function calculateSeriesVariations(
  rows,
  {
    valueKey,
    periodKey = 'fecha',
    monthlyLag = 1,
    annualLag = 12,
  },
) {
  const monthly = []
  const annual = []

  rows.forEach((row, index) => {
    if (index >= monthlyLag) {
      monthly.push({
        period: row[periodKey],
        value: calculateVariation(
          row[valueKey],
          rows[index - monthlyLag][valueKey],
        ),
      })
    }

    if (index >= annualLag) {
      annual.push({
        period: row[periodKey],
        value: calculateVariation(
          row[valueKey],
          rows[index - annualLag][valueKey],
        ),
      })
    }
  })

  return {
    monthly,
    annual,
  }
}


export function calculateLatestVariations(
  rows,
  columns,
  {
    monthlyLag = 1,
    annualLag = 12,
  } = {},
) {
  const minimumRows = Math.max(
    monthlyLag,
    annualLag,
  ) + 1

  if (rows.length < minimumRows) {
    return {
      monthly: [],
      annual: [],
    }
  }

  const latestRow = rows.at(-1)
  const previousRow = rows.at(
    -(monthlyLag + 1),
  )
  const previousYearRow = rows.at(
    -(annualLag + 1),
  )

  const monthly = columns.map((column) => ({
    key: column.key,
    label: column.label,
    value: calculateVariation(
      latestRow[column.key],
      previousRow[column.key],
    ),
  }))

  const annual = columns.map((column) => ({
    key: column.key,
    label: column.label,
    value: calculateVariation(
      latestRow[column.key],
      previousYearRow[column.key],
    ),
  }))

  return {
    monthly,
    annual,
  }
}
export function sumLastPeriods(
  rows,
  valueKey,
  periods,
) {
  return rows
    .slice(-periods)
    .reduce(
      (sum, row) =>
        sum + (Number(row[valueKey]) || 0),
      0,
    )
}


export function sumYTD(
  rows,
  valueKey,
  periodKey = 'period',
) {
  if (!rows.length) {
    return 0
  }

  const latestPeriod = rows.at(-1)[periodKey]
  const latestYear = String(latestPeriod).slice(0, 4)

  return rows.reduce((sum, row) => {
    const rowYear = String(
      row[periodKey],
    ).slice(0, 4)

    if (rowYear !== latestYear) {
      return sum
    }

    return sum + (Number(row[valueKey]) || 0)
  }, 0)
}
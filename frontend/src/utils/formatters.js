export function formatPercentage(
  value,
  decimals = 2,
) {
  if (!Number.isFinite(value)) {
    return 'N/A'
  }

  return `${value.toFixed(decimals)}%`
}


export function formatPeriod(
  period,
  locale = 'es-AR',
) {
  if (!period) {
    return 'N/A'
  }

  const date = new Date(
    `${period}T00:00:00`,
  )

  if (Number.isNaN(date.getTime())) {
    return 'N/A'
  }

  return date.toLocaleDateString(
    locale,
    {
      month: 'long',
      year: 'numeric',
    },
  )
}


export function formatNumber(
  value,
  {
    locale = 'es-AR',
    minimumFractionDigits = 0,
    maximumFractionDigits = 2,
  } = {},
) {
  if (!Number.isFinite(value)) {
    return 'N/A'
  }

  return value.toLocaleString(
    locale,
    {
      minimumFractionDigits,
      maximumFractionDigits,
    },
  )
}
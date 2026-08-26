const DOLTHUB_OWNER = 'rbasa'
const DOLTHUB_REPO = 'macroeconomia'
const DOLTHUB_BRANCH = 'main'

const DOLTHUB_API_URL =
  `https://www.dolthub.com/api/v1alpha1/` +
  `${DOLTHUB_OWNER}/${DOLTHUB_REPO}/${DOLTHUB_BRANCH}`

export async function fetchDolt(sql) {
  const params = new URLSearchParams({
    q: sql,
  })

  const response = await fetch(
    `${DOLTHUB_API_URL}?${params.toString()}`,
  )

  if (!response.ok) {
    throw new Error(
      `DoltHub request failed: ${response.status}`,
    )
  }

  const payload = await response.json()

  if (
    payload.query_execution_status
    && payload.query_execution_status !== 'Success'
  ) {
    throw new Error(
      payload.query_execution_message
      || 'DoltHub no pudo ejecutar la consulta',
    )
  }

  return payload.rows ?? []
}

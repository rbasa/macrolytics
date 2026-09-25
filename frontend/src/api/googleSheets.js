let requestSequence = 0


function cellValue(cell) {
  if (!cell) {
    return ''
  }

  return cell.v ?? cell.f ?? ''
}


function tableToRows(table) {
  const tableRows = table?.rows ?? []

  if (tableRows.length === 0) {
    return []
  }

  const columnLabels = (table.cols ?? []).map((column) => column.label)
  const hasColumnLabels = columnLabels.some(Boolean)
  const headers = hasColumnLabels
    ? columnLabels
    : tableRows[0].c.map((cell) => String(cellValue(cell)).trim())
  const dataRows = hasColumnLabels ? tableRows : tableRows.slice(1)

  return dataRows.map((row) => Object.fromEntries(
    headers.map((header, index) => [header, cellValue(row.c[index])]),
  ))
}


export function fetchPublicGoogleSheet({
  spreadsheetId,
  sheetName,
  timeoutMs = 10000,
}) {
  return new Promise((resolve, reject) => {
    const callbackName = [
      '__macrolyticsGoogleSheet',
      Date.now(),
      requestSequence++,
    ].join('_')
    const script = document.createElement('script')
    let timeoutId

    function cleanup() {
      window.clearTimeout(timeoutId)
      script.remove()
      delete window[callbackName]
    }

    window[callbackName] = (response) => {
      try {
        if (response?.status !== 'ok') {
          throw new Error('Google Sheets devolvió una respuesta inválida')
        }

        resolve(tableToRows(response.table))
      } catch (error) {
        reject(error)
      } finally {
        cleanup()
      }
    }

    script.onerror = () => {
      cleanup()
      reject(new Error('No se pudo descargar el calendario de Google Sheets'))
    }

    const params = new URLSearchParams({
      sheet: sheetName,
      tqx: `out:json;responseHandler:${callbackName}`,
    })
    script.src = [
      `https://docs.google.com/spreadsheets/d/${spreadsheetId}/gviz/tq`,
      params.toString(),
    ].join('?')

    timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('Google Sheets demoró demasiado en responder'))
    }, timeoutMs)

    document.head.appendChild(script)
  })
}

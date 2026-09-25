export const CALENDAR_SOURCE =
  'https://www.indec.gob.ar/ftp/cuadros/publicaciones/calendario_2sem2026.pdf'

export const CALENDAR_SHEET = {
  spreadsheetId: '1zgTdwumDXhTWMpdXv-RLKSW2LR3njo42l7LxmiETtWU',
  sheetName: 'Próximas publicaciones',
}

export const ECONOMIC_DATASETS = [
  {
    id: 'pbi',
    label: 'Producto Interno Bruto',
    to: '/economicActivity',
    messagePattern: /quarterly GDP|PBI/i,
  },
  {
    id: 'fiscal',
    label: 'Balance fiscal',
    to: '/fiscal-balance',
    messagePattern: /fiscal/i,
  },
  {
    id: 'emae',
    label: 'EMAE',
    to: '/economicActivity',
    messagePattern: /EMAE/i,
  },
  {
    id: 'confidence',
    label: 'Confianza del consumidor',
    to: '/expectations',
    messagePattern: /consumer confidence/i,
  },
  {
    id: 'ipc',
    label: 'Índice de precios al consumidor',
    to: '/inflation',
    messagePattern: /IPC|inflation/i,
  },
  {
    id: 'trade',
    label: 'Intercambio comercial',
    to: '/tradeBalance',
    messagePattern: /foreign trade/i,
  },
]

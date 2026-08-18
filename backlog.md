Secciones
## Sector financiero
 - Reservas del BCRA 
 - M2
 - tasa de interes
 - Descomposición de la tasa de préstamos personales y del CFT
   - Construir una serie mensual histórica que explique la brecha entre la tasa de plazo fijo, la TNA de préstamos personales y el CFT.
   - Componentes: fondeo, encajes, riesgo de tasa/depreciación, riesgo de crédito, costos operativos, rentabilidad, IIBB, sellos, IVA y otros impuestos.
   - Priorizar series oficiales del BCRA: tasas activas y pasivas, depósitos, encajes, mora, previsiones y balances del sistema financiero.
   - Mantener parámetros regulatorios e impositivos versionados, con vigencia temporal y jurisdicción cuando corresponda.
   - Identificar cada componente como dato oficial, cálculo determinístico o estimación Macrolytics.
   - Investigar la metodología de Econométrica y documentar cualquier diferencia respecto de su estimación.
   - Visualizaciones: descomposición para el último mes y evolución histórica de cada componente.
   - Validar como referencia junio de 2026: plazo fijo 19,9%; TNA 67,2%; CFTNA 82,8%; CFTEA 122,7%.

## Expectativas
 - Indice confianza la consumidor (UTDT)
 - ICP?
 - Imagen del gobierno?

## Precios
 - variacion acumulada en el año
 - IPP o mayorista
 - Precios internacionales o Terminos de intercambio?
 - break even de inflacion o expectativas de inflacion


## Sector fiscal
  - deflatarlas por ipc o por terminos constantes
  - cuentas como porcentaje del pib
  - stock de deuda
  - Riesgo país
    - en bps 
    - calificacion de moodys etc

## Tabla de presidencias 

## escritura de informe macroeconomico de los indicadores
## agentes 
  - que verifique calendario economico y corra etls
  - que twittee 

## Actividad
 - PBI
 - Encuesta nacional de hogares
 - Desempleo
 - Necesidades Basicas Insatisfechas
 - utilizacion de capacidad instalada


## Graficos de salario real
  A Salario real
  B ipc 
  C agua electricidad energía y vivienda (componente ipc)
  A/b vs a/c
  
  Los populistas subsidian c

## Tipo de cambio
  Tipo de cambio real multilateral
  Ver la disminución de la varianza cambiaira desde milei
  Ver saltos de devaluación 


## precios constantes
  hacer tabla para calcular las cosas en terminos reales, precios constantes no corrientes
  - en pesos
  - en usd


## Workflow
en vez de que corra todos los dias todos los updaters, podriamos hacer que corra una simple api que se fije el ultimo dato de cada tabla y lo compare con el ultimo dato de cada endpoint, si hay novedades que monte todo el circo y updatee todo lo nuevo

que corra todos los dias los usd pero una vez por hora, y si triggerea que haga todo el baile

## Flexibilizar el uso de parametros en los etl
en GH actions hoy tenemos:

IPC_LAST_PERIODS: '5'

en el futuro podriamos hacer que sea un parametro opcional para que al correrlo, podamos agregar periodos si falla algo

IPC_LAST_PERIODS: ${{ github.event.inputs.ipc_last_periods || '5' }}

workflow_dispatch:

  inputs:
    days_back:
      description: 'Days to update for daily FX/UVA ETL'
      required: false
      default: '7'

    ipc_last_periods:
      description: 'IPC periods to refresh'
      required: false
      default: '5'

last_periods = int(
  os.getenv(
    'IPC_LAST_PERIODS',
    DEFAULT_LAST_PERIODS,
  )
)

---

# Bitcoin on chain data
precio de compra de STH y LTH
interes abierto

# analsis mundiales 
 - copper to gold ratio
 - sp500 sobre pbi


# USA
## Actividad
 - Ventas minoristas
 - Estimaciones de crecimiento Goldman Sachs (futuro)
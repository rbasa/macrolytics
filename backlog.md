Secciones
## Sector financiero
 - Reservas del BCRA 
 - M2
 - tasa de interes

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
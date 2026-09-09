Secciones
## home
Últimas Novedades
Próximos indicadores

## Sector financiero
 - [x] Reservas del BCRA
 - [x] M2
 - [x] tasa de interés (BADLAR bancos privados, TNA)
 - [x] BCRA compra de dólares por día
 - [x] Hoja de balance
 - [x] Base monetaria
 - [x] Ratio base monetaria sobre reservas
 - [x] Créditos
   - [x] Total de créditos
   - [x] Morosidad
   - [x] Total de mora
   - [x] Créditos en USD

## Expectativas
 - [x] Indice confianza la consumidor (UTDT)
 - [ ] ICP?
 - [ ] Índice de confianza al gobierno

## Precios
 - variacion acumulada en el año
 - IPP o mayorista
 - Precios internacionales o Terminos de intercambio?
 - break even de inflacion o expectativas de inflacion


## Sector fiscal
  - deflatarlas por ipc o por terminos constantes
  - cuentas como porcentaje del pib
  - stock de deuda
  - rollover de deuda en pesos: valor efectivo sobre vencimientos
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
 - Ingreso disponible
 - [ ] Desempleo y mercado de trabajo (EPH): tasa de desocupación, actividad, empleo, subocupación e informalidad; incluir aperturas por sexo, edad y región. Frecuencia trimestral. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-58)
 - utilizacion de capacidad instalada

### Indicadores de consumo y actividad comercial
 - [ ] Ventas en supermercados: precios constantes, variación interanual, desestacionalizada mensual y tendencia-ciclo. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-1-34)
 - [ ] Ventas en autoservicios mayoristas: precios constantes, variación interanual, desestacionalizada mensual y tendencia-ciclo. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-1-168)
 - [ ] Ventas en centros de compras: precios constantes, variación interanual, desestacionalizada mensual y tendencia-ciclo. Fuente: [INDEC](https://www.indec.gob.ar/)
 - [ ] Ventas de electrodomésticos y artículos para el hogar: facturación trimestral a precios corrientes, variación interanual y detalle por rubro. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-1-37)

## Indicadores sociales
### Prioridad alta
 - [ ] Pobreza e indigencia: porcentaje de personas y hogares, brecha de pobreza y apertura regional. Frecuencia semestral. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-46-152)
 - [ ] Distribución del ingreso: coeficiente de Gini, ingreso medio y mediano per cápita, deciles y brecha entre extremos. Frecuencia trimestral. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-60)
 - [ ] Canasta básica alimentaria y canasta básica total: valores mensuales, variaciones e ingresos necesarios para no ser indigente o pobre. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel3-Tema-4-43)
 - [ ] Indicadores socioeconómicos de la EPH: composición de los hogares, cobertura de salud, educación y características habitacionales. Frecuencia trimestral. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-31-59)
 - [ ] Necesidades básicas insatisfechas (NBI): hogares y personas, apertura provincial y por componente. Frecuencia censal. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-47-156)
 - [ ] Canasta de crianza: costo de bienes y servicios más costo del tiempo de cuidado, por tramo de edad. Frecuencia mensual. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-43-173)

### Segunda etapa
 - [ ] Educación: asistencia escolar, máximo nivel alcanzado, alumnos y egresados. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-33-97)
 - [ ] Salud: esperanza de vida, mortalidad infantil, cobertura y otros indicadores sanitarios. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-32-94)
 - [ ] Acceso digital: hogares con internet y computadora; uso de internet y celular. Fuente: [INDEC](https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-26-71)


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

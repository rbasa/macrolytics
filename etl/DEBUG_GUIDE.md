# 🔍 Guía de Debug del ETL

Esta guía explica cómo ejecutar el ETL en modo debug para ver exactamente qué datos se están obteniendo y cargando en la base de datos.

## 📋 Scripts Disponibles

### 1. `debug_etl.py` - Sin conexión a BD (solo visualización)

Este script **NO** se conecta a la base de datos, solo muestra qué datos se obtendrían del API.

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar debug (por defecto: últimos 30 días)
python etl/debug_etl.py

# Especificar cantidad de días
DEBUG_DAYS=60 python etl/debug_etl.py
```

**Uso:** Cuando quieres verificar qué datos devuelve el API sin necesidad de tener la BD corriendo.

---

### 2. `debug_etl_with_db.py` - Con conexión a BD (recomendado) ⭐

Este script **SÍ** se conecta a la BD y muestra logs detallados de lo que se inserta.

#### Modo Dry-Run (solo visualización, NO inserta):

```bash
# Activar entorno virtual
source venv/bin/activate

# Ver qué se insertaría SIN insertar realmente
python etl/debug_etl_with_db.py --dry-run

# Especificar días
python etl/debug_etl_with_db.py --dry-run --days 60
```

#### Modo con Inserts (inserta y muestra logs detallados):

```bash
# Ver logs detallados mientras se inserta
python etl/debug_etl_with_db.py

# Especificar días
python etl/debug_etl_with_db.py --days 30
```

**Requisitos previos:**
1. Dolt SQL Server debe estar corriendo:
   ```bash
   cd macroeconomia
   dolt sql-server
   ```
2. Variable de entorno `DOLT_DB` configurada (opcional, usa default si no está):
   ```bash
   export DOLT_DB="mysql://user:@localhost:3306/macroeconomia"
   ```

**Uso:** Cuando quieres ver exactamente qué se está insertando en la BD y qué registros ya existen (se ignoran).

---

### 3. `daily_update.py` - ETL Normal (producción)

El script normal de ETL con logging estándar:

```bash
source venv/bin/activate
python etl/daily_update.py

# Especificar días
UPDATE_DAYS=30 python etl/daily_update.py
```

---

## 🎯 Recomendación para Debug

Para ver los logs de lo que se cargaría en la BD, usa:

```bash
# 1. Asegúrate de que el servidor Dolt esté corriendo
cd macroeconomia
dolt sql-server  # En una terminal separada

# 2. En otra terminal, ejecuta el debug con dry-run primero
cd /Users/user/uva
source venv/bin/activate
python etl/debug_etl_with_db.py --dry-run

# 3. Si todo se ve bien, ejecuta con inserts
python etl/debug_etl_with_db.py
```

---

## 📊 Qué Muestra el Debug

El script `debug_etl_with_db.py` muestra:

1. **Resumen de datos obtenidos:**
   - Cantidad total de registros por tipo (UVA, USD oficial, blue, etc.)
   - Rango de fechas
   - Muestras de los datos

2. **Resumen por currency pair:**
   - Cuántos registros hay por par (UVA_ARS, USDB_ARS, etc.)
   - Rango de fechas de cada par

3. **Logs de inserción (si no es dry-run):**
   - Cada registro que se inserta exitosamente
   - Registros que se ignoran (ya existen en la BD)
   - Errores si los hay

4. **Resumen final:**
   - Total de registros insertados
   - Total de registros ignorados (ya existían)
   - Errores encontrados

---

## 🔧 Troubleshooting

### Error: "Can't connect to MySQL server"

Asegúrate de que el servidor Dolt esté corriendo:
```bash
cd macroeconomia
dolt sql-server
```

### Error: "ModuleNotFoundError: No module named 'pymysql'"

Instala las dependencias:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Quieres ver más días de datos

Usa el flag `--days`:
```bash
python etl/debug_etl_with_db.py --dry-run --days 90
```


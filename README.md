# UVA Analysis - Argentine Inflation-Indexed Unit

Analysis of the **UVA (Unidad de Valor Adquisitivo)** index measured in different USD exchange rates in Argentina.

## 🎯 What This Project Does

1. **📊 Analysis Notebook**: Study UVA volatility when measured in USD
2. **📥 Data Pipeline**: Automated ETL to fetch and version financial data
3. **🗄️ DoltHub Integration**: Public dataset available at [dolthub.com/rbasa/macroeconomia](https://www.dolthub.com/repositories/rbasa/macroeconomia)
4. **🌐 Live Analysis**: Daily-updated HTML analysis published on [GitHub Pages](https://rbasa.github.io/macrolytics/)

## 📈 Data Coverage

- **UVA Index**: Daily values from 2016-03-31 to present (~3,500 records)
- **USD Rates**: Multiple types with bid/ask spreads:
  - USD Official (Formal)
  - USD MEP (Electronic Payment Market)  
  - USD Blue (Informal)
  - USD Crypto
- **Historical Range**: From 2002 (post-convertibilidad) to present

## 📊 Data Structure

### Table: `fx_rate`

| Column | Type | Description |
|--------|------|-------------|
| DATE | date | Date of the exchange rate |
| pair | varchar(10) | Currency pair (e.g., USD_ARS, UVA_ARS) |
| kind | varchar(20) | Data type (e.g., UVA, USD_OFICIAL, USD_BLUE) |
| rate | decimal(15,6) | Exchange rate value |

**Primary Key**: `(DATE, pair, kind)`

## 🚀 Quick Start

### For Analysis

Just open the notebook - data loads from DoltHub automatically:

```bash
# Install dependencies
pip install -r requirements.txt

# Open notebook
jupyter notebook uva_analisis.ipynb
```

### For Data Contributors

See `SETUP.md` for complete setup instructions including local Dolt database.

Keep this terminal open with the server running.

### 3. Run the ETL

In a new terminal:

```bash
cd /Users/user/uva
source .venv/bin/activate

# Configure database connection (or script will use default)
export DOLT_DB='mysql://user:@localhost:3306/macroeconomia'

# Run ETL
python etl/populate_usd_uva.py
```

## 📁 Project Structure

```
uva/
├── data/                    # Dolt database directory
│   └── tables.sql          # Table schemas
├── etl/                    # ETL scripts
│   ├── populate_usd_uva.py # Main ETL script
│   ├── fix_schema.py       # Schema fix utilities
│   ├── fix_primary_key.py  # Primary key fix utilities
│   └── utils/              # Shared utilities
│       ├── __init__.py
│       ├── utils.py        # Common functions
│       ├── db_manager.py   # Database manager
│       ├── fetch_usd_data.py
│       ├── fetch_uva.py
│       └── README.md
├── uva_analisis.ipynb      # Jupyter notebook for analysis
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## 📚 Usage Examples

### Fetch USD Data

```python
from etl.utils.fetch_usd_data import fetch_ambito_dolar

# Fetch official dollar data (returns standardized format)
data = fetch_ambito_dolar('formal', '2024-01-01', '2024-12-31')
# Returns: [{'date': '2024-01-01', 'rate': 942.82}, ...]
```

### Fetch UVA Data

```python
from etl.utils.fetch_uva import fetch_uva_data

# Fetch all UVA historical data (returns standardized format)
data = fetch_uva_data()
# Returns: [{'date': '2016-03-31', 'rate': 14.05}, ...]
```

### Database Operations

```python
from etl.utils import DoltDBManager
import os

os.environ['DOLT_DB'] = 'mysql://user:@localhost:3306/macroeconomia'
db = DoltDBManager()
db.connect()

# Query data
data = db.query("SELECT * FROM fx_rate WHERE kind='UVA' ORDER BY DATE DESC LIMIT 10")

# Insert data
db.insert_fx_rate(date='2024-08-26', kind='UVA', pair='UVA_ARS', rate=1565.43)

db.disconnect()
```

## 🔧 Maintenance

### Fix Schema

```bash
python etl/fix_schema.py
```

### Fix Primary Key

```bash
python etl/fix_primary_key.py
```

## 📈 Data Summary

After running the ETL, you should have:

- **~3,500 UVA records** (2016-03-31 to present)
- **~5,900 USD_OFICIAL records** (2002-04-09 to present)
- **~5,900 USD_MEP records** (2002-04-09 to present)
- **~6,000 USD_BLUE records** (2002-01-11 to present)
- **~5,900 USD_CRIPTO records** (2002-04-09 to present)

**Total: ~27,000 records**

## 🛠️ Technical Details

- **Python**: 3.12+
- **Database**: Dolt (MySQL-compatible with version control)
- **Data Sources**:
  - UVA: https://api.argentinadatos.com/v1/finanzas/indices/uva
  - USD: https://mercados.ambito.com/dolar/

## 📝 Notes

- The ETL uses `INSERT IGNORE` to avoid duplicates
- Today's data is excluded to avoid incomplete records
- The database uses Unix socket (`/tmp/mysql.sock`) for local connections
- All monetary values use Argentine format (. for thousands, , for decimals) and are converted to float

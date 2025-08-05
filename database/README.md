# Database Files

## Files Description

- `schema.sql` - Complete database schema (tables, indexes, constraints)
- `sample_data.sql` - 3 months of recent earthquake data (~3-5k records)
- `quick_demo.sql` - 1 month of recent data for quick testing

## Usage

### Load Schema Only
```bash
docker exec phivolcs_db psql -U username -d dbname -f /app/database/schema.sql
```

### Load Sample Data
```bash
# Load schema first
docker exec phivolcs_db psql -U username -d dbname -f /app/database/schema.sql

# Then load sample data
docker exec phivolcs_db psql -U username -d dbname -f /app/database/sample_data.sql
```

### Quick Demo
```bash
# For quick testing with minimal data
docker exec phivolcs_db psql -U username -d dbname -f /app/database/schema.sql
docker exec phivolcs_db psql -U username -d dbname -f /app/database/quick_demo.sql
```

## Data Source

All earthquake data is sourced from PHIVOLCS (Philippine Institute of Volcanology and Seismology).
Please respect their data usage policies.

# Administración de Condominio con PostgreSQL

## Cambios principales
- PostgreSQL como única base de datos.
- `BIGSERIAL`, claves foráneas, restricciones e índices.
- Pool de conexiones con Psycopg 3.
- Consultas parametrizadas `%s`.
- `ON CONFLICT` en cargos duplicados.
- Tokens de recuperación almacenados como hash y con expiración de 30 minutos.
- Script opcional para migrar una base SQLite V3 existente.

## Configuración local en macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edita secrets.toml con la URL real de PostgreSQL
streamlit run app.py
```

## Streamlit Community Cloud
En Secrets configura:
```toml
DATABASE_URL = "postgresql://...?...sslmode=require"
ADMIN_INITIAL_PASSWORD = "..."
```
No subas `.streamlit/secrets.toml` a GitHub.

## Migrar datos de SQLite
Usa una base PostgreSQL vacía y respalda ambos lados.
```bash
export DATABASE_URL='postgresql://...?...sslmode=require'
python migrate_sqlite_to_postgres.py /ruta/condominio_secure.db
```
Después compara unidades, cargos, pagos, gastos y saldos. El script no migra archivos físicos de comprobantes; debe cargarlos a almacenamiento de objetos y registrar sus URLs.

## Nota de producción
PostgreSQL resuelve persistencia de datos, pero los comprobantes deben vivir en almacenamiento de objetos, no en el disco efímero de Streamlit. Configura respaldos administrados en el proveedor PostgreSQL.

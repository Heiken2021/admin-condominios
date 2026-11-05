"""Migra datos de la V3 SQLite a PostgreSQL. Ejecutar una sola vez con DATABASE_URL definido."""
import argparse, os, sqlite3
import psycopg
from psycopg.rows import dict_row
from pathlib import Path

TABLES=["unidades","usuarios","cargos","pagos","gastos","auditoria"]

def rows(conn,table):
    try:return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    except sqlite3.OperationalError:return []

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("sqlite_file"); args=ap.parse_args()
    url=os.environ.get("DATABASE_URL")
    if not url: raise SystemExit("Falta DATABASE_URL")
    src=sqlite3.connect(Path(args.sqlite_file)); src.row_factory=sqlite3.Row
    with psycopg.connect(url,row_factory=dict_row) as dst:
        for table in TABLES:
            data=rows(src,table)
            for raw in data:
                r=dict(raw)
                # La app PostgreSQL crea IDs nuevos; se preservan relaciones usando IDs originales solo en una base destino vacía.
                cols=[k for k in r if k in {
                  'id','unidad','propietario','inquilino','telefono','email','cuota_base','recargo_pct','activo',
                  'username','nombre','rol','unidad_id','salt','password_hash','reset_token_hash','reset_expira',
                  'periodo','concepto','monto','vencimiento','recargo','fecha','metodo','referencia','notas',
                  'categoria','proveedor','comprobante_url','creado_por','accion','detalle'}]
                if table=='usuarios' and 'reset_token' in r: r['reset_token_hash']=None
                if table=='pagos' and 'comprobante' in r: r['comprobante_url']=None
                if table=='gastos' and 'comprobante' in r: r['comprobante_url']=None
                vals=[r.get(c) for c in cols]; marks=','.join(['%s']*len(cols))
                sql=f"INSERT INTO {table} ({','.join(cols)}) VALUES ({marks}) ON CONFLICT DO NOTHING"
                dst.execute(sql,vals)
        for table in ["unidades","usuarios","cargos","pagos","gastos","auditoria"]:
            dst.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),COALESCE((SELECT MAX(id) FROM "+table+"),1),true)",(table,))
        dst.commit()
    print("Migración terminada. Verifica conteos y saldos antes de usar producción.")
if __name__=="__main__":main()

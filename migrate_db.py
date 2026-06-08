"""Migración manual: agrega columnas de trazabilidad y tabla de auditoría."""
import sqlite3
import os

db_path = "tregistro.db"

if not os.path.exists(db_path):
    print("No existe tregistro.db — se creará desde cero al iniciar el servidor.")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(trabajador)")
    cols = [row[1] for row in cur.fetchall()]
    print(f"Columnas actuales en 'trabajador': {cols}")

    nuevas = [
        ("actualizado_en", "DATETIME"),
        ("eliminado",      "INTEGER NOT NULL DEFAULT 0"),
        ("eliminado_en",   "DATETIME"),
    ]
    for col, tipo in nuevas:
        if col not in cols:
            cur.execute(f"ALTER TABLE trabajador ADD COLUMN {col} {tipo}")
            print(f"  + Agregada: {col} ({tipo})")
        else:
            print(f"  = Ya existe: {col}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_registro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registro_id INTEGER NOT NULL,
            numero_documento TEXT NOT NULL DEFAULT '',
            momento DATETIME NOT NULL,
            accion TEXT NOT NULL DEFAULT '',
            detalle TEXT NOT NULL DEFAULT ''
        )
    """)
    print("  = Tabla auditoria_registro OK")

    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_rid ON auditoria_registro(registro_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_momento ON auditoria_registro(momento)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_accion ON auditoria_registro(accion)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_trab_cat_estado_activo "
        "ON trabajador(categoria, estado, eliminado)"
    )
    print("  = Índices OK")

    conn.commit()
    conn.close()
    print("\nMigración completada correctamente.")

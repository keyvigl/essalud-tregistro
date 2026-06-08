#!/bin/sh
set -e

echo "=== T-Registro EsSalud — arranque ==="
echo "DATABASE_URL configurado: $([ -n "$DATABASE_URL" ] && echo 'SI (PostgreSQL)' || echo 'NO (SQLite local)')"

echo "Inicializando tablas en la base de datos..."
python - <<'PYEOF'
import sys, time

# Espera hasta 90 segundos para que la BD esté lista
for intento in range(30):
    try:
        from app.models import init_db, engine
        from sqlmodel import SQLModel
        init_db()
        tablas = list(SQLModel.metadata.tables.keys())
        print(f"OK — tablas creadas: {tablas}", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"Intento {intento+1}/30 — {e}", flush=True)
        if intento < 29:
            time.sleep(3)

print("ERROR: No se pudo inicializar la base de datos después de 90 segundos.", flush=True)
sys.exit(1)
PYEOF

echo "Iniciando servidor uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

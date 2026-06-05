# T-Registro EsSalud — App de carga masiva

App web para que los trabajadores llenen sus datos (Etapa 1) y la trabajadora de
EsSalud complete lo laboral y genere los archivos de **carga masiva del T-Registro**
de SUNAT, listos para validar en el **PVS – T-Registro** antes de subirlos a SOL.

## Cómo ejecutar en local

```powershell
pip install -r requirements.txt
# 1) Generar las tablas de SUNAT (solo la primera vez o si cambian):
python app/scripts/extract_tables.py
# 2) Levantar la app:
python -m uvicorn app.main:app --reload --port 8000
```

- Formulario del trabajador:  http://127.0.0.1:8000/
- Panel de EsSalud:           http://127.0.0.1:8000/panel  (clave: `essalud2026`)

## Configuración (variables de entorno)

| Variable | Por defecto | Uso |
|----------|-------------|-----|
| `RUC_EMPLEADOR` | 20131257750 | RUC de EsSalud para nombrar `RP_<RUC>.*` |
| `SECTOR` | publico | `publico` o `privado` (tablas de ocupación) |
| `DATABASE_URL` | sqlite local | En Railway se usa Postgres |
| `PANEL_PASSWORD` | essalud2026 | Clave del panel |

## Estructura

- `app/scripts/extract_tables.py` — extrae las tablas oficiales SUNAT a JSON.
- `app/data/*.json` — catálogos (tablas, ubigeo, instituciones, ocupaciones).
- `app/catalogs.py` — acceso a catálogos.
- `app/models.py` — modelo del trabajador (Etapa 1 + Etapa 2).
- `app/main.py` — rutas web.
- `app/templates/`, `app/static/` — interfaz.

## Pendiente
- Etapa 2 (panel: completar datos laborales + validación tipo PVS).
- Generación de los 6 archivos `.ide/.tra/.per/.est/.edu/.cta` + ZIP.
- Deploy a Railway.

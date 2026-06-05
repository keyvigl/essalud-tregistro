"""Configuración de la app. Para Railway, las variables se leen del entorno."""
import os

# RUC del empleador (EsSalud). Se usa para nombrar los archivos RP_<RUC>.*
RUC_EMPLEADOR = os.getenv("RUC_EMPLEADOR", "20131257750")
NOMBRE_EMPLEADOR = os.getenv("NOMBRE_EMPLEADOR", "SEGURO SOCIAL DE SALUD - ESSALUD")

# Sector del empleador: "publico" o "privado" (afecta tablas de ocupación, etc.)
SECTOR = os.getenv("SECTOR", "publico")

# Código de establecimiento por defecto (local Trujillo del RUC de EsSalud)
COD_ESTABLECIMIENTO = os.getenv("COD_ESTABLECIMIENTO", "0537")

# Base de datos: SQLite en local, Postgres (DATABASE_URL) en Railway.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tregistro.db")
# Railway entrega 'postgres://'; SQLAlchemy necesita 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Clave simple para el panel de la trabajadora de EsSalud
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "essalud2026")

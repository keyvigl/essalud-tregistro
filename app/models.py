"""Modelo de datos. Un registro = un trabajador a inscribir en el T-Registro.

Diseño de base de datos:
- Una sola tabla 'trabajador' (forma normal adecuada para vínculo 1-a-1 por persona)
- Soft-delete: los registros nunca se borran físicamente (obligatorio en entidades públicas)
- Auditoría: toda acción queda registrada en 'auditoria_registro'
- Trazabilidad: creado / actualizado_en en cada registro
- Portabilidad: SQLite (local/desarrollo) y PostgreSQL (producción) sin cambio de código
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel, Session, create_engine

from .config import DATABASE_URL

# ── Estados del flujo de trabajo (máquina de 3 nodos) ──────────────────────
PENDIENTE  = "pendiente"    # trabajador llenó sus datos (Etapa 1)
COMPLETADO = "completado"   # EsSalud completó datos laborales (Etapa 2)
EXPORTADO  = "exportado"    # incluido en al menos un ZIP de carga masiva

# ── Categorías ──────────────────────────────────────────────────────────────
CAT_TRABAJADOR  = "trabajador"
CAT_PRACTICANTE = "practicante"   # Personal en Formación Laboral


# ── Tabla principal ─────────────────────────────────────────────────────────
class Trabajador(SQLModel, table=True):
    __tablename__ = "trabajador"
    __table_args__ = (
        # Índice compuesto para las consultas más frecuentes del panel:
        # filtrar activos por categoría y estado en una sola pasada de índice.
        Index("ix_trab_cat_estado_activo", "categoria", "estado", "eliminado"),
        # Nota sobre unicidad de numero_documento:
        # La deduplicación se aplica en capa de aplicación (main.py) filtrando
        # por eliminado=False. Una UniqueConstraint a nivel DB no es compatible
        # con soft-delete en SQLite (no soporta índices únicos parciales).
        # En PostgreSQL de producción se puede agregar vía Alembic:
        #   CREATE UNIQUE INDEX uq_trab_doc_activo ON trabajador(numero_documento)
        #   WHERE eliminado = false;
    )

    id:       Optional[int] = Field(default=None, primary_key=True)
    estado:   str = Field(default=PENDIENTE,      index=True)
    categoria: str = Field(default=CAT_TRABAJADOR, index=True)

    # ── Trazabilidad ────────────────────────────────────────────────────────
    creado:         datetime           = Field(default_factory=datetime.utcnow)
    actualizado_en: Optional[datetime] = Field(default=None)

    # ── Soft-delete (los registros NUNCA se borran físicamente) ─────────────
    eliminado:    bool               = Field(default=False, index=True)
    eliminado_en: Optional[datetime] = Field(default=None)

    # ===== ETAPA 1 — Datos que llena el trabajador =====
    # Identificación
    tipo_documento:   str = ""
    numero_documento: str = Field(default="", index=True)
    pais_emisor:      str = ""
    fecha_nacimiento: str = ""
    ap_paterno:       str = ""
    ap_materno:       str = ""
    nombres:          str = ""
    sexo:             str = ""
    nacionalidad:     str = ""
    telefono:         str = ""
    email:            str = ""
    # Dirección
    tipo_via:    str = ""
    nombre_via:  str = ""
    numero_via:  str = ""
    departamento: str = ""
    provincia:   str = ""
    ubigeo:      str = ""
    interior:    str = ""
    manzana:     str = ""
    lote:        str = ""
    km:          str = ""
    block:       str = ""
    etapa_dir:   str = ""
    tipo_zona:   str = ""
    nombre_zona: str = ""
    referencia:  str = ""
    # Educación / discapacidad
    discapacidad:       str = "0"
    situacion_educativa: str = ""
    formacion_superior: str = ""
    educ_completa_peru: str = "0"
    cod_institucion:    str = ""
    cod_carrera:        str = ""
    anio_egreso:        str = ""
    # Pensión
    regimen_pensionario: str = ""
    cuspp:               str = ""
    # Cuenta bancaria
    entidad_bancaria: str = ""
    numero_cuenta:    str = ""

    # ===== ETAPA 2 — Datos que completa EsSalud =====
    regimen_laboral:      str = ""
    ocupacion:            str = ""
    categoria_ocupacional: str = ""
    tipo_contrato:        str = ""
    # Constantes EsSalud (invariables para todos los registros)
    sujeto_atipico:    str = "0"
    jornada_maxima:    str = "0"
    horario_nocturno:  str = "0"
    sindicalizado:     str = "0"
    situacion:         str = "1"
    exonerado_5ta:     str = "0"
    situacion_especial: str = "0"
    sctr_pension:      str = "0"
    convenio_doble_trib: str = "0"
    # Varían por trabajador
    periodicidad:     str = ""
    sueldo:           str = ""
    tipo_pago:        str = ""
    num_ruc_cas:      str = ""
    tipo_trabajador:  str = ""
    cod_establecimiento: str = ""
    # Solo practicantes
    modalidad_formativa:   str = ""
    seguro_medico:         str = "1"
    madre_resp_familiar:   str = "0"
    tipo_centro_formacion: str = "2"
    # Periodos
    fecha_inicio_vinculo:  str = ""
    fecha_fin_vinculo:     str = ""
    motivo_baja:           str = ""
    fecha_inicio_tt:       str = ""
    fecha_fin_tt:          str = ""
    regimen_salud:         str = "00"
    eps:                   str = ""
    fecha_inicio_salud:    str = ""
    fecha_fin_salud:       str = ""
    fecha_inicio_pension:  str = ""
    fecha_fin_pension:     str = ""
    sctr_salud:            str = "1"
    fecha_inicio_sctr:     str = ""
    fecha_fin_sctr:        str = ""


# ── Tabla de auditoría ───────────────────────────────────────────────────────
class AuditoriaRegistro(SQLModel, table=True):
    """Registro inmutable de toda acción sobre un prestador.
    Nunca se actualiza ni elimina: solo INSERT. Cumple con el principio de
    trazabilidad exigido en sistemas de entidades públicas peruanas."""
    __tablename__ = "auditoria_registro"

    id:               Optional[int] = Field(default=None, primary_key=True)
    registro_id:      int            = Field(index=True)
    numero_documento: str            = Field(default="")
    momento:          datetime       = Field(default_factory=datetime.utcnow, index=True)
    accion:           str            = Field(default="", index=True)
    # acciones: crear | actualizar_etapa1 | completar_etapa2 | exportar | eliminar | importar
    detalle:          str            = Field(default="")


# ── Motor de base de datos ───────────────────────────────────────────────────
_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # SQLite: check_same_thread=False es obligatorio en FastAPI (async/threading).
    # PostgreSQL: pool_size controla conexiones permanentes; max_overflow permite
    # picos; pool_pre_ping detecta y descarta conexiones rotas antes de usarlas;
    # pool_recycle evita que conexiones idle sean cerradas por el servidor.
    **(
        {"connect_args": {"check_same_thread": False}}
        if _sqlite else
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    ),
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


# ── Helper de auditoría ─────────────────────────────────────────────────────
def auditar(session: Session, registro_id: int, numero_documento: str,
            accion: str, detalle: str = "") -> None:
    """Inserta una fila de auditoría en la misma transacción activa."""
    session.add(AuditoriaRegistro(
        registro_id=registro_id,
        numero_documento=numero_documento,
        accion=accion,
        detalle=detalle,
    ))

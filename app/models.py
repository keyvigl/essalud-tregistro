"""Modelo de datos. Un registro = un trabajador a inscribir en el T-Registro.
Los campos se agrupan por ETAPA 1 (los llena el trabajador) y ETAPA 2 (EsSalud)."""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine

from .config import DATABASE_URL

# Estados del flujo de trabajo
PENDIENTE = "pendiente"        # el trabajador llenó su parte
COMPLETADO = "completado"      # EsSalud terminó su parte
EXPORTADO = "exportado"        # ya se generó el archivo de carga masiva


# Categorías que registra EsSalud
CAT_TRABAJADOR = "trabajador"
CAT_PRACTICANTE = "practicante"   # Personal en Formación Laboral


class Trabajador(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    estado: str = Field(default=PENDIENTE, index=True)
    categoria: str = Field(default=CAT_TRABAJADOR, index=True)
    creado: datetime = Field(default_factory=datetime.utcnow)

    # ===== ETAPA 1 — Datos del trabajador =====
    # Identificación
    tipo_documento: str = ""
    numero_documento: str = Field(default="", index=True)
    pais_emisor: str = ""
    fecha_nacimiento: str = ""           # dd/mm/aaaa
    ap_paterno: str = ""
    ap_materno: str = ""
    nombres: str = ""
    sexo: str = ""                       # 1=M / 2=F
    nacionalidad: str = ""
    telefono: str = ""
    email: str = ""
    # Dirección 1
    tipo_via: str = ""
    nombre_via: str = ""
    numero_via: str = ""
    departamento: str = ""
    provincia: str = ""
    ubigeo: str = ""                     # código de distrito (6 dígitos)
    interior: str = ""
    manzana: str = ""
    lote: str = ""
    km: str = ""
    block: str = ""
    etapa_dir: str = ""
    tipo_zona: str = ""
    nombre_zona: str = ""
    referencia: str = ""
    # Educación / discapacidad
    discapacidad: str = "0"
    situacion_educativa: str = ""
    formacion_superior: str = ""         # 11 o 13 (si aplica)
    educ_completa_peru: str = "0"
    cod_institucion: str = ""
    cod_carrera: str = ""
    anio_egreso: str = ""
    # Pensión
    regimen_pensionario: str = ""
    cuspp: str = ""
    # Cuenta bancaria
    entidad_bancaria: str = ""
    numero_cuenta: str = ""

    # ===== ETAPA 2 — Datos que completa EsSalud =====
    # Laboral (.tra)
    regimen_laboral: str = ""
    ocupacion: str = ""
    categoria_ocupacional: str = ""
    tipo_contrato: str = ""
    # Constantes de EsSalud (no se preguntan; SUNAT las pide siempre igual)
    sujeto_atipico: str = "0"          # jornada atípica: No
    jornada_maxima: str = "0"          # las 3 opciones de jornada van sin marcar
    horario_nocturno: str = "0"        # No
    sindicalizado: str = "0"           # No
    situacion: str = "1"               # Activo
    exonerado_5ta: str = "0"           # No
    situacion_especial: str = "0"      # Ninguna
    sctr_pension: str = "0"            # cobertura pensión SCTR: sin marcar
    convenio_doble_trib: str = "0"     # No
    # Varían (se llenan/importan)
    periodicidad: str = ""
    sueldo: str = ""
    tipo_pago: str = ""
    num_ruc_cas: str = ""
    # Tipo de trabajador y establecimiento
    tipo_trabajador: str = ""
    cod_establecimiento: str = ""
    # ===== Solo PRACTICANTES (Personal en Formación Laboral, .pfl / E-9) =====
    modalidad_formativa: str = ""       # tabla 18
    seguro_medico: str = "1"            # 1=EsSalud / 2=privado
    madre_resp_familiar: str = "0"      # solo mujeres
    tipo_centro_formacion: str = "2"    # 1 CE / 2 Universidad / 3 Instituto / 4 Otros

    # Periodos (.per)
    fecha_inicio_vinculo: str = ""
    fecha_fin_vinculo: str = ""
    motivo_baja: str = ""
    fecha_inicio_tt: str = ""
    fecha_fin_tt: str = ""
    regimen_salud: str = "00"          # EsSalud Regular (todos los trabajadores)
    eps: str = ""
    fecha_inicio_salud: str = ""
    fecha_fin_salud: str = ""
    fecha_inicio_pension: str = ""
    fecha_fin_pension: str = ""
    sctr_salud: str = "1"              # SCTR cobertura salud: EsSalud
    fecha_inicio_sctr: str = ""
    fecha_fin_sctr: str = ""


engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

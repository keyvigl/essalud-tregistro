"""Genera los archivos de texto de carga masiva del T-Registro (entrada del PVS).

Cada archivo RP_<RUC>.<ext> contiene una línea por trabajador (o varias, en .per),
campos separados por '|' y con un '|' final, tal como lo exige SUNAT.

Formatos verificados contra el Anexo 3 (estructuras) y las macros que ya funcionan.
"""
import io
import zipfile
from datetime import datetime

from . import config

AFP = {"21", "22", "23", "24", "25"}


# ---------------- helpers de formato ----------------
def fdate(s: str) -> str:
    """Convierte 'aaaa-mm-dd' o 'dd/mm/aaaa' a 'dd/mm/aaaa'. Vacío -> ''."""
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return s


def z(v, n: int) -> str:
    """Rellena con ceros a la izquierda hasta n (solo si hay valor)."""
    v = (v or "").strip()
    return v.zfill(n) if v else ""


def g(v) -> str:
    return ("" if v is None else str(v)).strip()


def sueldo(v) -> str:
    v = g(v)
    if not v:
        return ""
    try:
        return f"{round(float(v), 2):g}"
    except ValueError:
        return v


def _linea(campos) -> str:
    """Une con '|' y agrega el '|' final que exige SUNAT."""
    return "|".join(g(c) for c in campos) + "|"


# ---------------- una línea por archivo ----------------
def linea_ide(t) -> str:
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        fdate(t.fecha_nacimiento), t.ap_paterno, t.ap_materno, t.nombres,
        t.sexo, t.nacionalidad,
        "",                       # 10: tel. larga distancia (no vigente)
        t.telefono, t.email,
        z(t.tipo_via, 2), t.nombre_via, t.numero_via,
        "",                       # 16: departamento (n° de dpto del inmueble; no se captura)
        t.interior, t.manzana, t.lote, t.km, t.block, t.etapa_dir,
        z(t.tipo_zona, 2), t.nombre_zona, t.referencia, z(t.ubigeo, 6),
        "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # 27-40: dirección 2 (opcional)
        "",                       # 41: indicador centro asistencial (solo con 2 direcciones)
    ])


def linea_tra(t) -> str:
    cuspp = t.cuspp if t.regimen_pensionario in AFP else ""
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        z(t.regimen_laboral, 2), z(t.situacion_educativa, 2), z(t.ocupacion, 6),
        t.discapacidad or "0", cuspp, t.sctr_pension or "0",
        z(t.tipo_contrato, 2), t.sujeto_atipico or "0", t.jornada_maxima or "0",
        t.horario_nocturno or "0", t.sindicalizado or "0", t.periodicidad,
        sueldo(t.sueldo), z(t.situacion, 2), t.exonerado_5ta or "0",
        t.situacion_especial or "0", t.tipo_pago, z(t.categoria_ocupacional, 2),
        t.convenio_doble_trib or "0", t.num_ruc_cas,
    ])


def lineas_per(t) -> list[str]:
    """Una línea por cada tipo de registro con datos.
    Categoría 1 = Trabajador, 5 = Personal en Formación (practicante).
    Si una fecha de inicio de bloque está vacía, se usa la del vínculo/ingreso."""
    es_practicante = getattr(t, "categoria", "trabajador") == "practicante"
    cat = "5" if es_practicante else "1"
    ini = fdate(t.fecha_inicio_vinculo)
    base = [z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3), cat]
    out = []

    def add(tipo, fi, ff, ind, eps=""):
        fi = fdate(fi) or ini
        if not fi:
            return
        out.append(_linea(base + [tipo, fi, fdate(ff), ind, eps]))

    if es_practicante:
        # Practicante: período de formación (1) y régimen pensionario (4) si aplica
        add("1", t.fecha_inicio_vinculo, t.fecha_fin_vinculo, z(t.motivo_baja, 2))
        if t.regimen_pensionario:
            add("4", t.fecha_inicio_pension, t.fecha_fin_pension, z(t.regimen_pensionario, 2))
        return out

    add("1", t.fecha_inicio_vinculo, t.fecha_fin_vinculo, z(t.motivo_baja, 2))     # vínculo
    add("2", t.fecha_inicio_tt, t.fecha_fin_tt, z(t.tipo_trabajador, 2))           # tipo trabajador
    eps = t.eps if t.regimen_salud in ("01", "03") else ""
    add("3", t.fecha_inicio_salud, t.fecha_fin_salud, z(t.regimen_salud, 2), eps)  # régimen salud
    if t.regimen_pensionario:
        add("4", t.fecha_inicio_pension, t.fecha_fin_pension, z(t.regimen_pensionario, 2))  # pensión
    if t.sctr_salud in ("1", "2"):
        add("5", t.fecha_inicio_sctr, t.fecha_fin_sctr, t.sctr_salud)              # SCTR salud
    return out


def linea_pfl(t) -> str:
    """E-9: Personal en Formación Laboral (practicantes)."""
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        z(t.modalidad_formativa, 2), t.seguro_medico or "1",
        z(t.situacion_educativa, 2), z(t.ocupacion, 6),
        t.madre_resp_familiar or "0", t.discapacidad or "0",
        t.tipo_centro_formacion or "2", t.horario_nocturno or "0",
    ])


def linea_est(t) -> str:
    estab = (t.cod_establecimiento or "").strip() or config.COD_ESTABLECIMIENTO
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        config.RUC_EMPLEADOR, z(estab, 4),
    ])


def linea_edu(t):
    """Solo TRABAJADORES con formación superior (situación 11/13/14-21).
    Los practicantes no llevan estudios concluidos: usan 'centro de formación' en el .pfl."""
    if getattr(t, "categoria", "trabajador") == "practicante":
        return None
    if not t.formacion_superior:
        return None
    completa = t.educ_completa_peru == "1"
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        z(t.formacion_superior, 2), t.educ_completa_peru or "0",
        t.cod_institucion if completa else "",
        t.cod_carrera if completa else "",
        t.anio_egreso if completa else "",
    ])


def linea_cta(t):
    """Solo si el pago es Depósito en cuenta (tipo_pago=2) y hay datos bancarios."""
    if t.tipo_pago != "2" or not (t.entidad_bancaria and t.numero_cuenta):
        return None
    return _linea([
        z(t.tipo_documento, 2), t.numero_documento, z(t.pais_emisor, 3),
        t.entidad_bancaria, t.numero_cuenta,
    ])


# ---------------- armado de los 6 archivos ----------------
def generar_archivos(trabajadores) -> dict[str, str]:
    """Devuelve {extension: contenido} solo de los archivos que tienen datos.
    .tra solo para Trabajadores; .pfl solo para Personal en Formación (practicantes)."""
    buckets = {"ide": [], "tra": [], "pfl": [], "per": [], "est": [], "edu": [], "cta": []}
    for t in trabajadores:
        buckets["ide"].append(linea_ide(t))
        if getattr(t, "categoria", "trabajador") == "practicante":
            buckets["pfl"].append(linea_pfl(t))
        else:
            buckets["tra"].append(linea_tra(t))
        buckets["per"].extend(lineas_per(t))
        buckets["est"].append(linea_est(t))
        if (e := linea_edu(t)):
            buckets["edu"].append(e)
        if (c := linea_cta(t)):
            buckets["cta"].append(c)
    return {ext: "\r\n".join(lineas) + "\r\n" for ext, lineas in buckets.items() if lineas}


def generar_zip(trabajadores) -> bytes:
    """Empaqueta los archivos RP_<RUC>.<ext> en un ZIP (codificación ANSI/cp1252)."""
    archivos = generar_archivos(trabajadores)
    ruc = config.RUC_EMPLEADOR
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext, contenido in archivos.items():
            zf.writestr(f"RP_{ruc}.{ext}", contenido.encode("cp1252", errors="replace"))
    return buf.getvalue()

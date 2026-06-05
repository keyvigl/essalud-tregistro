"""Validaciones de la Etapa 1 (datos del trabajador).

Replican las reglas de SUNAT/PVS-T-Registro para que el trabajador corrija TODO
antes de enviar y luego los archivos no sean rechazados por el PVS.
Devuelve una lista de mensajes de error (vacía = todo OK).
"""
import re
from datetime import date

# Régimen pensionario que es AFP/SPP -> requiere CUSPP (tabla 11)
AFP_CODES = {"21", "22", "23", "24", "25"}
# Situaciones educativas de nivel superior -> aplican estudios concluidos (tabla 9)
SUP_EDU = {"11", "13", "14", "15", "16", "17", "18", "19", "20", "21"}
# Tipos de documento que exigen país emisor (tabla 3): pasaporte y doc. extranjero
PAIS_REQ_DOC = {"7", "24"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _fmt_fecha(s):
    """Acepta 'aaaa-mm-dd' (input date) o 'dd/mm/aaaa'. Devuelve date o None."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def validar_etapa1(d: dict) -> list[str]:
    e = []
    g = lambda k: (d.get(k) or "").strip()

    td = g("tipo_documento")
    num = g("numero_documento")
    if not td:
        e.append("Elige el tipo de documento.")
    if not num:
        e.append("Ingresa el número de documento.")
    elif td == "1" and not re.fullmatch(r"\d{8}", num):
        e.append("El DNI debe tener exactamente 8 dígitos.")
    elif len(num) > 15:
        e.append("El número de documento no puede superar los 15 caracteres.")

    if td in PAIS_REQ_DOC and not g("pais_emisor"):
        e.append("Para pasaporte o documento extranjero debes indicar el país emisor.")

    f = g("fecha_nacimiento")
    if not f:
        e.append("Ingresa tu fecha de nacimiento.")
    else:
        fn = _fmt_fecha(f)
        if not fn:
            e.append("La fecha de nacimiento no tiene un formato válido.")
        elif fn > date.today():
            e.append("La fecha de nacimiento no puede ser futura.")
        elif fn.year < 1900:
            e.append("Revisa tu fecha de nacimiento (año demasiado antiguo).")

    # Apellidos y nombres: para DNI los toma RENIEC -> no obligatorios.
    if g("sexo") not in ("1", "2"):
        e.append("Selecciona tu sexo.")

    cel = g("telefono")
    if not cel:
        e.append("El celular es obligatorio.")
    elif not re.fullmatch(r"9\d{8}", cel):
        e.append("El celular debe tener 9 dígitos y empezar con 9.")

    email = g("email")
    if not email:
        e.append("El correo electrónico es obligatorio.")
    elif not EMAIL_RE.match(email):
        e.append("El correo electrónico no es válido.")

    # Domicilio: para DNI lo toma RENIEC -> opcional.

    es_practicante = g("categoria") == "practicante"

    # Pensión / CUSPP y banco SOLO se piden al Trabajador.
    # En practicantes esos datos vienen del Excel de RRHH.
    if not es_practicante:
        rp = g("regimen_pensionario")
        cuspp = g("cuspp")
        if not rp:
            e.append("Selecciona tu régimen pensionario.")
        if rp in AFP_CODES:
            if not cuspp:
                e.append("Si estás en una AFP debes ingresar tu CUSPP.")
            elif len(cuspp) != 12:
                e.append("El CUSPP debe tener 12 caracteres.")

        banco = g("entidad_bancaria")
        cta = g("numero_cuenta")
        if banco and not cta:
            e.append("Ingresa el número de cuenta del banco elegido.")
        if cta and not banco:
            e.append("Elige la entidad bancaria de tu cuenta.")
        if cta:
            if not cta.isdigit():
                e.append("El número de cuenta debe contener solo números.")
            elif len(set(cta)) == 1:
                e.append("El número de cuenta no puede ser todos los dígitos iguales.")
            elif cta == num:
                e.append("El número de cuenta no puede ser igual a tu documento.")

    # Educación
    se = g("situacion_educativa")
    if not se:
        e.append("Selecciona tu situación educativa.")
    if se in SUP_EDU and g("educ_completa_peru") == "1":
        if not g("cod_institucion"):
            e.append("Selecciona tu institución educativa.")
        if not g("cod_carrera"):
            e.append("Selecciona tu carrera.")
        anio = g("anio_egreso")
        if not re.fullmatch(r"\d{4}", anio) or not (1950 <= int(anio) <= date.today().year):
            e.append(f"Ingresa un año de egreso válido (entre 1950 y {date.today().year}).")

    return e


def validar_etapa2(d: dict, trab=None) -> list[str]:
    """Valida los datos laborales que completa EsSalud. `trab` es el registro del
    trabajador (para reglas cruzadas, p.ej. depósito en cuenta sin cuenta)."""
    e = []
    g = lambda k: (d.get(k) or "").strip()

    if not g("tipo_trabajador"):
        e.append("Selecciona el tipo de trabajador.")
    if not g("regimen_laboral"):
        e.append("Selecciona el régimen laboral.")
    if not g("ocupacion"):
        e.append("Selecciona la ocupación.")
    if not g("tipo_contrato"):
        e.append("Selecciona el tipo de contrato.")
    if not g("periodicidad"):
        e.append("Selecciona la periodicidad de la remuneración.")

    sueldo = g("sueldo")
    if not sueldo:
        e.append("Ingresa el monto de remuneración.")
    else:
        try:
            if float(sueldo) < 0:
                e.append("El sueldo no puede ser negativo.")
        except ValueError:
            e.append("El sueldo debe ser un número.")

    if not g("fecha_inicio_vinculo"):
        e.append("Ingresa la fecha de inicio del vínculo (ingreso).")

    # CAS (tipo trabajador 67) requiere N° RUC
    if g("tipo_trabajador") == "67" and not g("num_ruc_cas"):
        e.append("El tipo de trabajador CAS requiere el N° de RUC.")

    # Depósito en cuenta requiere que el trabajador tenga cuenta bancaria
    if g("tipo_pago") == "2" and trab is not None:
        if not (trab.entidad_bancaria and trab.numero_cuenta):
            e.append("El tipo de pago es 'Depósito en cuenta' pero el trabajador no registró su cuenta bancaria.")

    return e


def validar_practicante(d: dict, trab=None) -> list[str]:
    """Valida los datos de practicante (Personal en Formación Laboral) que completa EsSalud."""
    e = []
    g = lambda k: (d.get(k) or "").strip()
    if not g("modalidad_formativa"):
        e.append("Selecciona la modalidad formativa.")
    if not g("ocupacion"):
        e.append("Selecciona la ocupación (según su carrera/área).")
    if not g("situacion_educativa"):
        e.append("Indica la situación educativa.")
    if not g("fecha_inicio_vinculo"):
        e.append("Ingresa la fecha de inicio del período formativo.")
    if g("tipo_pago") == "2" and trab is not None:
        if not (g("entidad_bancaria") or trab.entidad_bancaria) or not (g("numero_cuenta") or trab.numero_cuenta):
            e.append("El pago es 'Depósito en cuenta' pero falta la cuenta bancaria.")
    return e


def verificar_alta(t) -> list[str]:
    """Revisa un registro completo y devuelve lo que FALTA para el alta en SUNAT
    (el mínimo obligatorio). Lista vacía = listo para registrar."""
    f = []
    g = lambda k: (getattr(t, k, "") or "").strip()
    es_practicante = getattr(t, "categoria", "trabajador") == "practicante"

    # --- Identificación (.ide) ---
    if not g("tipo_documento"):
        f.append("Tipo de documento")
    num = g("numero_documento")
    if not num:
        f.append("Número de documento")
    elif g("tipo_documento") == "1" and not re.fullmatch(r"\d{8}", num):
        f.append("DNI debe tener 8 dígitos")
    if g("tipo_documento") in PAIS_REQ_DOC and not g("pais_emisor"):
        f.append("País emisor (pasaporte/doc. extranjero)")
    if not g("fecha_nacimiento"):
        f.append("Fecha de nacimiento")
    if g("sexo") not in ("1", "2"):
        f.append("Sexo")
    if not re.fullmatch(r"9\d{8}", g("telefono")):
        f.append("Celular (9 dígitos)")
    if not EMAIL_RE.match(g("email")):
        f.append("Correo electrónico")
    if not g("situacion_educativa"):
        f.append("Situación educativa")

    # --- Pensión (ambas categorías) ---
    if not g("regimen_pensionario"):
        f.append("Régimen pensionario")
    elif g("regimen_pensionario") in AFP_CODES and len(g("cuspp")) != 12:
        f.append("CUSPP (12 caracteres, por ser AFP)")

    # --- Cuenta bancaria (si el pago es depósito) ---
    if g("tipo_pago") == "2" and not (g("entidad_bancaria") and g("numero_cuenta")):
        f.append("Cuenta bancaria (pago en depósito)")

    # --- Datos de su categoría ---
    if es_practicante:
        if not g("modalidad_formativa"):
            f.append("Modalidad formativa")
        if not g("ocupacion"):
            f.append("Ocupación")
        if not g("fecha_inicio_vinculo"):
            f.append("Fecha de inicio (formación)")
    else:
        reqs = [
            ("tipo_trabajador", "Tipo de trabajador"),
            ("regimen_laboral", "Régimen laboral"),
            ("ocupacion", "Ocupación"),
            ("tipo_contrato", "Tipo de contrato"),
            ("periodicidad", "Periodicidad"),
            ("sueldo", "Monto de remuneración"),
            ("fecha_inicio_vinculo", "Fecha de ingreso"),
        ]
        for campo, etiqueta in reqs:
            if not g(campo):
                f.append(etiqueta)
    return f


def formacion_superior(situacion_educativa: str) -> str:
    """E-29: 'Formación superior completa' debe ser 11 o 13 según la situación."""
    if situacion_educativa == "11":
        return "11"
    if situacion_educativa in SUP_EDU:
        return "13"
    return ""

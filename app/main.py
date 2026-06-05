"""App web del T-Registro EsSalud.

ETAPA 1: el trabajador entra por un link y llena sus datos (formulario público).
ETAPA 2: la trabajadora de EsSalud entra al panel, completa lo laboral y genera
         los archivos de carga masiva.
"""
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from . import catalogs as cat
from . import config
from . import generate
from . import import_rrhh
from .validation import (validar_etapa1, validar_etapa2, validar_practicante,
                         verificar_alta, formacion_superior)
from .models import (Trabajador, get_session, init_db,
                     PENDIENTE, COMPLETADO, EXPORTADO, CAT_PRACTICANTE, CAT_TRABAJADOR)

# Campos personales: si el trabajador ya los registró, no los pisa la importación
CAMPOS_PERSONALES = {"ap_paterno", "ap_materno", "nombres", "fecha_nacimiento",
                     "sexo", "email", "nacionalidad"}

# Campos de la Etapa 2 que VARÍAN (los completa EsSalud). Los demás son
# constantes de EsSalud con valor por defecto (no se preguntan).
CAMPOS_ETAPA2 = [
    "tipo_trabajador", "regimen_laboral", "categoria_ocupacional", "ocupacion",
    "tipo_contrato", "periodicidad", "tipo_pago", "sueldo", "fecha_inicio_vinculo",
    "fecha_fin_vinculo", "motivo_baja", "num_ruc_cas", "cod_establecimiento",
]

# Campos que edita EsSalud para un PRACTICANTE (los fijos -seguro médico EsSalud,
# horario nocturno No- van por defecto y no se preguntan).
CAMPOS_PRACTICANTE = [
    "modalidad_formativa", "ocupacion", "situacion_educativa", "tipo_centro_formacion",
    "madre_resp_familiar", "discapacidad",
    "regimen_pensionario", "cuspp", "entidad_bancaria", "numero_cuenta", "tipo_pago",
    "cod_establecimiento", "fecha_inicio_vinculo", "fecha_fin_vinculo", "motivo_baja",
    "fecha_inicio_pension", "fecha_fin_pension",
]

BASE = Path(__file__).resolve().parent
app = FastAPI(title="T-Registro EsSalud")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
# El LRUCache de Jinja2 es incompatible con Python 3.14; lo desactivamos.
templates.env.cache = None

# Campos de la Etapa 1 que se reciben del formulario del trabajador
CAMPOS_ETAPA1 = [
    "tipo_documento", "numero_documento", "pais_emisor", "fecha_nacimiento",
    "ap_paterno", "ap_materno", "nombres", "sexo", "nacionalidad", "telefono",
    "email", "tipo_via", "nombre_via", "numero_via", "departamento", "provincia",
    "ubigeo", "interior", "manzana", "lote", "km", "block", "etapa_dir",
    "tipo_zona", "nombre_zona", "referencia", "discapacidad", "situacion_educativa",
    "formacion_superior", "educ_completa_peru", "cod_institucion", "cod_carrera",
    "anio_egreso", "regimen_pensionario", "cuspp", "entidad_bancaria", "numero_cuenta",
    "tipo_centro_formacion", "cod_establecimiento", "ocupacion",
]


@app.on_event("startup")
def _startup():
    init_db()


# ---------------- ETAPA 1: formulario del trabajador ----------------
def _render_form(request, valores=None, errores=None):
    return templates.TemplateResponse(request, "form_trabajador.html", {
        "empleador": config.NOMBRE_EMPLEADOR,
        "cat": cat,
        "departamentos": cat.departamentos(),
        "instituciones": cat.lista_instituciones(),
        "establecimientos": cat.establecimientos(),
        "v": valores or {},
        "errores": errores or [],
    })


@app.get("/", response_class=HTMLResponse)
def form_trabajador(request: Request):
    return _render_form(request)


@app.post("/registrar")
async def registrar(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    categoria = (form.get("categoria") or "trabajador").strip()
    datos = {k: (form.get(k) or "").strip() for k in CAMPOS_ETAPA1}
    datos_val = dict(datos, categoria=categoria)

    errores = validar_etapa1(datos_val)
    if errores:
        return _render_form(request, valores=datos_val, errores=errores)

    # Normalizaciones derivadas
    datos["formacion_superior"] = formacion_superior(datos.get("situacion_educativa", ""))
    if datos.get("regimen_pensionario") not in ("21", "22", "23", "24", "25"):
        datos["cuspp"] = ""  # CUSPP solo aplica a AFP

    # Upsert por DNI: si ya existe (p.ej. importado de RRHH), se actualiza
    t = session.exec(select(Trabajador).where(
        Trabajador.numero_documento == datos["numero_documento"])).first()
    if t:
        # No pisar con vacíos: conserva lo que vino de RRHH (banco, pensión) si el
        # trabajador deja esos campos en blanco.
        for k, v in datos.items():
            if v:
                setattr(t, k, v)
        # Si fue importado como practicante, mantener esa categoría
        if t.categoria != CAT_PRACTICANTE:
            t.categoria = categoria
        # El estado lo decide EsSalud al completar en el panel (donde valida todo)
    else:
        t = Trabajador(estado=PENDIENTE, categoria=categoria, **datos)
    session.add(t)
    session.commit()
    session.refresh(t)
    return RedirectResponse(f"/gracias/{t.id}", status_code=303)


@app.get("/gracias/{tid}", response_class=HTMLResponse)
def gracias(request: Request, tid: int, session: Session = Depends(get_session)):
    t = session.get(Trabajador, tid)
    return templates.TemplateResponse(request, "gracias.html", {"t": t})


# ---------------- APIs de cascada (dropdowns dependientes) ----------------
@app.get("/api/provincias/{dep}")
def api_provincias(dep: str):
    return JSONResponse(cat.provincias(dep))


@app.get("/api/distritos/{prov}")
def api_distritos(prov: str):
    return JSONResponse(cat.distritos(prov))


@app.get("/api/carreras/{inst}")
def api_carreras(inst: str):
    return JSONResponse(cat.carreras(inst))


@app.get("/api/ocupaciones")
def api_ocupaciones(todas: int = 0):
    # Por defecto solo las ocupaciones de EsSalud; ?todas=1 devuelve las 4.753.
    if todas:
        return JSONResponse(cat.lista_ocupaciones(config.SECTOR))
    return JSONResponse(cat.ocupaciones_essalud())


# ---------------- Panel EsSalud (lista) ----------------
@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, clave: str = "", msg: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return templates.TemplateResponse(request, "panel_login.html", {})
    registros = session.exec(select(Trabajador).order_by(Trabajador.creado.desc())).all()
    listos = [r for r in registros if r.estado in (COMPLETADO, EXPORTADO)]
    return templates.TemplateResponse(request, "panel.html", {
        "registros": registros, "clave": clave, "cat": cat, "n_listos": len(listos), "msg": msg,
        "PENDIENTE": PENDIENTE, "COMPLETADO": COMPLETADO, "EXPORTADO": EXPORTADO,
        "CAT_PRACTICANTE": CAT_PRACTICANTE,
    })


# ---------------- Importar Excel de RRHH (altas de practicantes) ----------------
@app.post("/panel/importar")
async def importar(clave: str = "", archivo: UploadFile = File(...),
                   session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    try:
        filas = import_rrhh.parse(archivo.file)
    except Exception as e:
        return RedirectResponse(f"/panel?clave={clave}&msg=Error al leer el archivo: {e}", status_code=303)

    nuevos = actualizados = 0
    for d in filas:
        t = session.exec(select(Trabajador).where(
            Trabajador.numero_documento == d["numero_documento"])).first()
        if t:
            for k, v in d.items():
                if k in CAMPOS_PERSONALES and (getattr(t, k) or "").strip():
                    continue  # respeta lo que registró el trabajador
                setattr(t, k, v)
            # La categoría la define el Excel de RRHH (fila por fila)
            # El estado lo confirma EsSalud en el panel
            actualizados += 1
        else:
            t = Trabajador(estado=PENDIENTE, **d)  # falta que el trabajador registre su domicilio
            session.add(t)
            nuevos += 1
    session.commit()
    msg = f"Importación lista: {nuevos} nuevos, {actualizados} actualizados (practicantes)."
    return RedirectResponse(f"/panel?clave={clave}&msg={msg}", status_code=303)


# ---------------- Panel EsSalud: completar Etapa 2 ----------------
@app.get("/panel/{tid:int}", response_class=HTMLResponse)
def panel_detalle(request: Request, tid: int, clave: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    t = session.get(Trabajador, tid)
    if not t:
        return RedirectResponse(f"/panel?clave={clave}", status_code=303)
    tpl = "panel_practicante.html" if t.categoria == CAT_PRACTICANTE else "panel_detalle.html"
    return templates.TemplateResponse(request, tpl, {
        "t": t, "clave": clave, "cat": cat, "errores": [],
    })


@app.post("/panel/{tid:int}")
async def panel_guardar(request: Request, tid: int, clave: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    t = session.get(Trabajador, tid)
    if not t:
        return RedirectResponse(f"/panel?clave={clave}", status_code=303)

    es_prac = t.categoria == CAT_PRACTICANTE
    campos = CAMPOS_PRACTICANTE if es_prac else CAMPOS_ETAPA2
    tpl = "panel_practicante.html" if es_prac else "panel_detalle.html"

    form = await request.form()
    datos = {k: (form.get(k) or "").strip() for k in campos}
    errores = validar_practicante(datos, trab=t) if es_prac else validar_etapa2(datos, trab=t)
    if errores:
        for k, v in datos.items():
            setattr(t, k, v)  # conservar lo escrito al re-mostrar
        return templates.TemplateResponse(request, tpl, {
            "t": t, "clave": clave, "cat": cat, "errores": errores,
        })

    for k, v in datos.items():
        setattr(t, k, v)
    t.estado = COMPLETADO
    session.add(t)
    session.commit()
    return RedirectResponse(f"/panel?clave={clave}", status_code=303)


# ---------------- Completar practicantes EN LOTE (vista tipo Excel) ----------------
@app.get("/panel/lote", response_class=HTMLResponse)
def panel_lote(request: Request, clave: str = "", categoria: str = CAT_PRACTICANTE,
               session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    if categoria not in (CAT_PRACTICANTE, CAT_TRABAJADOR):
        categoria = CAT_PRACTICANTE
    regs = session.exec(
        select(Trabajador).where(Trabajador.categoria == categoria).order_by(Trabajador.id)
    ).all()
    # conteo por categoría para las pestañas
    n_prac = len(session.exec(select(Trabajador).where(Trabajador.categoria == CAT_PRACTICANTE)).all())
    n_trab = len(session.exec(select(Trabajador).where(Trabajador.categoria == CAT_TRABAJADOR)).all())
    return templates.TemplateResponse(request, "panel_lote.html", {
        "regs": regs, "clave": clave, "cat": cat, "estab": config.COD_ESTABLECIMIENTO,
        "modo": categoria, "n_prac": n_prac, "n_trab": n_trab,
        "CAT_PRACTICANTE": CAT_PRACTICANTE, "CAT_TRABAJADOR": CAT_TRABAJADOR,
    })


# Campos editables en lote según categoría
LOTE_FIELDS = set(CAMPOS_PRACTICANTE) | set(CAMPOS_ETAPA2)


@app.post("/panel/lote/guardar")
async def panel_lote_guardar(request: Request, clave: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return JSONResponse({"ok": False, "msg": "Clave inválida"}, status_code=403)
    cambios = await request.json()  # { "<id>": {campo: valor, ...}, ... }
    completados, errores = 0, {}
    for sid, datos in cambios.items():
        t = session.get(Trabajador, int(sid))
        if not t:
            continue
        for k in LOTE_FIELDS:
            if k in datos:
                setattr(t, k, (datos[k] or "").strip())
        if t.categoria == CAT_PRACTICANTE:
            errs = validar_practicante({k: getattr(t, k) for k in CAMPOS_PRACTICANTE}, trab=t)
        else:
            errs = validar_etapa2({k: getattr(t, k) for k in CAMPOS_ETAPA2}, trab=t)
        if errs:
            errores[sid] = errs
        else:
            t.estado = COMPLETADO
            completados += 1
        session.add(t)
    session.commit()
    return JSONResponse({"ok": True, "completados": completados, "errores": errores})


# ---------------- Verificación "listo para alta" ----------------
@app.get("/panel/verificar", response_class=HTMLResponse)
def panel_verificar(request: Request, clave: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    regs = session.exec(select(Trabajador).order_by(Trabajador.id)).all()
    filas = [(t, verificar_alta(t)) for t in regs]
    listos = sum(1 for _, f in filas if not f)
    return templates.TemplateResponse(request, "panel_verificar.html", {
        "filas": filas, "clave": clave, "cat": cat, "listos": listos, "total": len(filas),
        "CAT_PRACTICANTE": CAT_PRACTICANTE,
    })


# ---------------- Generar carga masiva (ZIP) ----------------
@app.get("/panel/generar/zip")
def generar(clave: str = "", session: Session = Depends(get_session)):
    if clave != config.PANEL_PASSWORD:
        return RedirectResponse("/panel", status_code=303)
    listos = session.exec(
        select(Trabajador).where(Trabajador.estado.in_([COMPLETADO, EXPORTADO]))
    ).all()
    if not listos:
        return RedirectResponse(f"/panel?clave={clave}", status_code=303)
    data = generate.generar_zip(listos)
    for t in listos:
        t.estado = EXPORTADO
        session.add(t)
    session.commit()
    nombre = f"T-REGISTRO_RP_{config.RUC_EMPLEADOR}.zip"
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})

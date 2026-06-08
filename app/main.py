"""App web del T-Registro EsSalud.

ETAPA 1: el trabajador entra por un link y llena sus datos (formulario público).
ETAPA 2: la trabajadora de EsSalud entra al panel, completa lo laboral y genera
         los archivos de carga masiva.
"""
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from . import catalogs as cat
from . import config
from . import generate
from . import import_rrhh
from .validation import (validar_etapa1, validar_etapa2, validar_practicante,
                         verificar_alta, formacion_superior)
from .models import (Trabajador, get_session, init_db, auditar,
                     PENDIENTE, COMPLETADO, EXPORTADO, CAT_PRACTICANTE, CAT_TRABAJADOR)

CAMPOS_PERSONALES = {"ap_paterno", "ap_materno", "nombres", "fecha_nacimiento",
                     "sexo", "email", "nacionalidad"}

CAMPOS_ETAPA2 = [
    "tipo_trabajador", "regimen_laboral", "categoria_ocupacional", "ocupacion",
    "tipo_contrato", "periodicidad", "tipo_pago", "sueldo", "fecha_inicio_vinculo",
    "fecha_fin_vinculo", "motivo_baja", "num_ruc_cas", "cod_establecimiento",
]

CAMPOS_PRACTICANTE = [
    "modalidad_formativa", "ocupacion", "tipo_centro_formacion",
    "madre_resp_familiar", "discapacidad", "situacion_educativa",
    "cod_establecimiento", "fecha_inicio_vinculo", "fecha_fin_vinculo", "motivo_baja",
]

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

BASE = Path(__file__).resolve().parent
app = FastAPI(title="T-Registro EsSalud")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.cache = None


# ── Auth helpers ────────────────────────────────────────────────────────────
def _authed(request: Request) -> bool:
    return request.session.get("panel_auth") is True

def _login_redirect():
    return RedirectResponse("/panel/login", status_code=303)

def _panel_redirect():
    return RedirectResponse("/panel", status_code=303)


@app.on_event("startup")
def _startup():
    init_db()


# ── ETAPA 1: formulario público del trabajador ───────────────────────────────
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

    datos["formacion_superior"] = formacion_superior(datos.get("situacion_educativa", ""))
    if datos.get("regimen_pensionario") not in ("21", "22", "23", "24", "25"):
        datos["cuspp"] = ""

    # Solo busca entre registros activos (no eliminados)
    t = session.exec(select(Trabajador).where(
        Trabajador.numero_documento == datos["numero_documento"],
        Trabajador.eliminado == False,
    )).first()

    es_nuevo = t is None
    if t:
        for k, v in datos.items():
            if v:
                setattr(t, k, v)
        if t.categoria != CAT_PRACTICANTE:
            t.categoria = categoria
        t.actualizado_en = datetime.utcnow()
    else:
        t = Trabajador(estado=PENDIENTE, categoria=categoria,
                       actualizado_en=datetime.utcnow(), **datos)

    session.add(t)
    session.commit()
    session.refresh(t)
    auditar(session, t.id, t.numero_documento,
            "crear" if es_nuevo else "actualizar_etapa1")
    session.commit()
    return RedirectResponse(f"/gracias/{t.id}", status_code=303)


@app.get("/gracias/{tid}", response_class=HTMLResponse)
def gracias(request: Request, tid: int, session: Session = Depends(get_session)):
    t = session.get(Trabajador, tid)
    return templates.TemplateResponse(request, "gracias.html", {"t": t})


# ── APIs de cascada ──────────────────────────────────────────────────────────
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
    if todas:
        return JSONResponse(cat.lista_ocupaciones(config.SECTOR))
    return JSONResponse(cat.ocupaciones_essalud())


# ── Panel: login / logout ────────────────────────────────────────────────────
@app.get("/panel/login", response_class=HTMLResponse)
def panel_login_get(request: Request):
    if _authed(request):
        return _panel_redirect()
    return templates.TemplateResponse(request, "panel_login.html", {"error": ""})


@app.post("/panel/login")
async def panel_login_post(request: Request):
    form = await request.form()
    clave = (form.get("clave") or "").strip()
    if clave == config.PANEL_PASSWORD:
        request.session["panel_auth"] = True
        return _panel_redirect()
    return templates.TemplateResponse(request, "panel_login.html",
                                      {"error": "Clave incorrecta. Intenta de nuevo."})


@app.get("/panel/logout")
def panel_logout(request: Request):
    request.session.clear()
    return _login_redirect()


# ── Panel: listado principal ─────────────────────────────────────────────────
@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, msg: str = "", session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    registros = session.exec(
        select(Trabajador)
        .where(Trabajador.eliminado == False)
        .order_by(Trabajador.creado.desc())
    ).all()
    listos = [r for r in registros if r.estado in (COMPLETADO, EXPORTADO)]
    n_prac = sum(1 for r in registros if r.categoria == CAT_PRACTICANTE)
    n_trab = sum(1 for r in registros if r.categoria == CAT_TRABAJADOR)
    return templates.TemplateResponse(request, "panel.html", {
        "registros": registros, "cat": cat,
        "n_listos": len(listos), "msg": msg,
        "n_prac": n_prac, "n_trab": n_trab,
        "PENDIENTE": PENDIENTE, "COMPLETADO": COMPLETADO, "EXPORTADO": EXPORTADO,
        "CAT_PRACTICANTE": CAT_PRACTICANTE,
    })


# ── Panel: importar Excel ────────────────────────────────────────────────────
@app.post("/panel/importar")
async def importar(request: Request, archivo: UploadFile = File(...),
                   session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    try:
        filas = import_rrhh.parse(archivo.file)
    except Exception as e:
        return RedirectResponse(f"/panel?msg=Error al leer el archivo: {e}", status_code=303)

    nuevos = actualizados = 0
    ahora = datetime.utcnow()
    for d in filas:
        t = session.exec(select(Trabajador).where(
            Trabajador.numero_documento == d["numero_documento"],
            Trabajador.eliminado == False,
        )).first()
        if t:
            for k, v in d.items():
                if k in CAMPOS_PERSONALES and (getattr(t, k) or "").strip():
                    continue
                setattr(t, k, v)
            t.actualizado_en = ahora
            actualizados += 1
            accion = "importar_actualizar"
        else:
            t = Trabajador(estado=PENDIENTE, actualizado_en=ahora, **d)
            session.add(t)
            nuevos += 1
            accion = "importar"
        session.flush()   # asegura t.id antes de la auditoría
        auditar(session, t.id, t.numero_documento, accion,
                f"Excel: {archivo.filename}")
    session.commit()
    msg = f"Importación lista: {nuevos} nuevos, {actualizados} actualizados."
    return RedirectResponse(f"/panel?msg={msg}", status_code=303)


# ── Panel: completar Etapa 2 ─────────────────────────────────────────────────
@app.get("/panel/{tid:int}", response_class=HTMLResponse)
def panel_detalle(request: Request, tid: int, session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    t = session.get(Trabajador, tid)
    if not t:
        return _panel_redirect()
    tpl = "panel_practicante.html" if t.categoria == CAT_PRACTICANTE else "panel_detalle.html"
    return templates.TemplateResponse(request, tpl, {"t": t, "cat": cat, "errores": []})


@app.post("/panel/{tid:int}")
async def panel_guardar(request: Request, tid: int, session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    t = session.get(Trabajador, tid)
    if not t:
        return _panel_redirect()

    es_prac = t.categoria == CAT_PRACTICANTE
    campos = CAMPOS_PRACTICANTE if es_prac else CAMPOS_ETAPA2
    tpl = "panel_practicante.html" if es_prac else "panel_detalle.html"

    form = await request.form()
    datos = {k: (form.get(k) or "").strip() for k in campos}
    errores = validar_practicante(datos, trab=t) if es_prac else validar_etapa2(datos, trab=t)
    if errores:
        for k, v in datos.items():
            setattr(t, k, v)
        return templates.TemplateResponse(request, tpl, {"t": t, "cat": cat, "errores": errores})

    for k, v in datos.items():
        setattr(t, k, v)
    t.estado = COMPLETADO
    t.actualizado_en = datetime.utcnow()
    session.add(t)
    auditar(session, t.id, t.numero_documento, "completar_etapa2")
    session.commit()
    return _panel_redirect()


# ── Panel: completar en lote ─────────────────────────────────────────────────
@app.get("/panel/lote", response_class=HTMLResponse)
def panel_lote(request: Request, categoria: str = CAT_PRACTICANTE,
               session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    if categoria not in (CAT_PRACTICANTE, CAT_TRABAJADOR):
        categoria = CAT_PRACTICANTE
    regs = session.exec(
        select(Trabajador)
        .where(Trabajador.categoria == categoria, Trabajador.eliminado == False)
        .order_by(Trabajador.id)
    ).all()
    n_prac = session.exec(select(Trabajador).where(
        Trabajador.categoria == CAT_PRACTICANTE, Trabajador.eliminado == False)).all().__len__()
    n_trab = session.exec(select(Trabajador).where(
        Trabajador.categoria == CAT_TRABAJADOR, Trabajador.eliminado == False)).all().__len__()
    return templates.TemplateResponse(request, "panel_lote.html", {
        "regs": regs, "cat": cat, "estab": config.COD_ESTABLECIMIENTO,
        "modo": categoria, "n_prac": n_prac, "n_trab": n_trab,
        "CAT_PRACTICANTE": CAT_PRACTICANTE, "CAT_TRABAJADOR": CAT_TRABAJADOR,
    })


LOTE_FIELDS = set(CAMPOS_PRACTICANTE) | set(CAMPOS_ETAPA2)


@app.post("/panel/lote/guardar")
async def panel_lote_guardar(request: Request, session: Session = Depends(get_session)):
    if not _authed(request):
        return JSONResponse({"ok": False, "msg": "No autenticado"}, status_code=403)
    cambios = await request.json()
    completados, errores = 0, {}
    ahora = datetime.utcnow()
    for sid, datos in cambios.items():
        t = session.get(Trabajador, int(sid))
        if not t or t.eliminado:
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
        t.actualizado_en = ahora
        session.add(t)
        auditar(session, t.id, t.numero_documento, "completar_etapa2_lote")
    session.commit()
    return JSONResponse({"ok": True, "completados": completados, "errores": errores})


# ── Panel: verificar ─────────────────────────────────────────────────────────
@app.get("/panel/verificar", response_class=HTMLResponse)
def panel_verificar(request: Request, session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    regs = session.exec(
        select(Trabajador)
        .where(Trabajador.eliminado == False)
        .order_by(Trabajador.categoria, Trabajador.id)
    ).all()
    filas = [(t, verificar_alta(t)) for t in regs]

    filas_trab = [(t, f) for t, f in filas if t.categoria == CAT_TRABAJADOR]
    filas_prac = [(t, f) for t, f in filas if t.categoria == CAT_PRACTICANTE]
    listos_trab = sum(1 for _, f in filas_trab if not f)
    listos_prac = sum(1 for _, f in filas_prac if not f)

    return templates.TemplateResponse(request, "panel_verificar.html", {
        "filas": filas,
        "filas_trab": filas_trab, "filas_prac": filas_prac,
        "listos_trab": listos_trab, "listos_prac": listos_prac,
        "total_trab": len(filas_trab), "total_prac": len(filas_prac),
        "cat": cat, "config": config,
        "CAT_PRACTICANTE": CAT_PRACTICANTE, "CAT_TRABAJADOR": CAT_TRABAJADOR,
    })


# ── Panel: eliminar (SOFT DELETE — registros nunca se borran físicamente) ────
@app.delete("/panel/eliminar/{tid:int}")
def eliminar_uno(tid: int, request: Request, session: Session = Depends(get_session)):
    if not _authed(request):
        return JSONResponse({"ok": False}, status_code=403)
    t = session.get(Trabajador, tid)
    if not t or t.eliminado:
        return JSONResponse({"ok": False, "msg": "No encontrado"}, status_code=404)
    ahora = datetime.utcnow()
    t.eliminado    = True
    t.eliminado_en = ahora
    t.actualizado_en = ahora
    session.add(t)
    auditar(session, t.id, t.numero_documento, "eliminar")
    session.commit()
    return JSONResponse({"ok": True})


@app.delete("/panel/eliminar/todo")
def eliminar_todo(request: Request, session: Session = Depends(get_session)):
    if not _authed(request):
        return JSONResponse({"ok": False}, status_code=403)
    activos = session.exec(
        select(Trabajador).where(Trabajador.eliminado == False)
    ).all()
    ahora = datetime.utcnow()
    for t in activos:
        t.eliminado    = True
        t.eliminado_en = ahora
        t.actualizado_en = ahora
        session.add(t)
        auditar(session, t.id, t.numero_documento, "eliminar")
    session.commit()
    return JSONResponse({"ok": True, "eliminados": len(activos)})


# ── Generar ZIP por categoría ─────────────────────────────────────────────────
# Cada categoría genera su propio ZIP con los archivos que le corresponden:
#   Trabajador  → .ide  .tra  .est  .per  [.edu]  [.cta]
#   Practicante → .ide  .pfl  .lug  .per  [.cta]
# Importarlos por separado en el PVS evita errores cruzados entre categorías.
@app.get("/panel/generar/zip/{categoria}")
def generar(categoria: str, request: Request, session: Session = Depends(get_session)):
    if not _authed(request):
        return _login_redirect()
    if categoria not in (CAT_TRABAJADOR, CAT_PRACTICANTE):
        return _panel_redirect()

    listos = session.exec(
        select(Trabajador).where(
            Trabajador.categoria == categoria,
            Trabajador.estado.in_([COMPLETADO, EXPORTADO]),
            Trabajador.eliminado == False,
        )
    ).all()
    if not listos:
        return RedirectResponse("/panel/verificar", status_code=303)

    data = generate.generar_zip(listos)
    ahora = datetime.utcnow()
    etiqueta = "TRABAJADORES" if categoria == CAT_TRABAJADOR else "PRACTICANTES"
    nombre_zip = f"T-REGISTRO_{etiqueta}_RP_{config.RUC_EMPLEADOR}.zip"
    for t in listos:
        t.estado = EXPORTADO
        t.actualizado_en = ahora
        session.add(t)
        auditar(session, t.id, t.numero_documento, "exportar", f"ZIP: {nombre_zip}")
    session.commit()
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre_zip}"'})


# ── Compatibilidad: redirigir /panel?clave=... al nuevo login ────────────────
@app.get("/panel/old-login", response_class=HTMLResponse)
def panel_old(request: Request):
    return _login_redirect()

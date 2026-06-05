"""Carga las tablas paramétricas de SUNAT (JSON generados por extract_tables.py)
y ofrece helpers de búsqueda (código -> descripción) y de listas para los <select>.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def tablas():
    return _load("tablas.json")


@lru_cache(maxsize=1)
def ubigeo():
    return _load("ubigeo.json")


@lru_cache(maxsize=1)
def instituciones():
    return _load("instituciones.json")


@lru_cache(maxsize=1)
def ocupaciones():
    return _load("ocupaciones.json")


@lru_cache(maxsize=1)
def ocupaciones_essalud():
    """Lista curada de ocupaciones que usa EsSalud (editable)."""
    return _load("ocupaciones_essalud.json")


def establecimientos():
    """Lista de sucursales EsSalud [{codigo, nombre}]. Editar establecimientos.json."""
    return _load("establecimientos.json")


def tabla(tid):
    """Lista [{codigo, descripcion}] de una tabla simple."""
    return tablas().get(tid, [])


def descripcion(tid, codigo):
    if codigo in (None, ""):
        return ""
    for it in tabla(tid):
        if it["codigo"] == str(codigo):
            return it["descripcion"]
    return str(codigo)


# ---- ubigeo en cascada ----
def departamentos():
    return ubigeo()["departamentos"]


def provincias(dep):
    return [p for p in ubigeo()["provincias"] if p["departamento"] == dep]


def distritos(prov):
    return [d for d in ubigeo()["distritos"] if d["provincia"] == prov]


def distrito_de_ubigeo(cod):
    for d in ubigeo()["distritos"]:
        if d["codigo"] == cod:
            return d
    return None


# ---- instituciones / carreras ----
def lista_instituciones():
    return instituciones()["instituciones"]


def carreras(cod_institucion):
    return instituciones()["carreras_por_institucion"].get(str(cod_institucion), [])


# ---- ocupaciones según sector ----
def lista_ocupaciones(sector):
    return ocupaciones()["privado" if sector == "privado" else "publico"]

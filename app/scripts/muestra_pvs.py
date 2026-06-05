"""Genera un paquete de PRUEBA para validar en el PVS - T-Registro.

Toma el Excel de RRHH de practicantes, completa con valores de prueba los campos
que normalmente aporta el practicante (celular, situación educativa, centro) y la
trabajadora (ocupación), y escribe los archivos RP_<RUC>.* en la carpeta PVS_prueba/.

Uso:  python app/scripts/muestra_pvs.py "ALTAS PRACTICANTES PRE PROFESIONALES (2).xlsx"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import config, generate, import_rrhh          # noqa: E402
from app.models import Trabajador                       # noqa: E402

# Valores de prueba para los datos que aún no están (en producción los dan
# el practicante y la trabajadora). Solo sirven para validar la ESTRUCTURA.
SITUACION_EDU_PRUEBA = "12"     # universitaria incompleta
CENTRO_PRUEBA = "2"            # universidad
OCUPACION_PRUEBA = "343004"     # PRACTICANTE EN MEDICINA (código válido de tabla 10)


def main(xlsx):
    filas = import_rrhh.parse(xlsx)
    registros = []
    for d in filas:
        dni = d["numero_documento"]
        d.setdefault("sexo", "2")
        d.update(
            telefono=("9" + dni)[:9],          # celular placeholder válido (9 díg)
            situacion_educativa=SITUACION_EDU_PRUEBA,
            tipo_centro_formacion=CENTRO_PRUEBA,
            ocupacion=OCUPACION_PRUEBA,
            cod_establecimiento=config.COD_ESTABLECIMIENTO,
        )
        d.pop("sueldo", None)                  # no va en el alta de practicante
        registros.append(Trabajador(**d))

    archivos = generate.generar_archivos(registros)
    out = ROOT / "PVS_prueba"
    out.mkdir(exist_ok=True)
    ruc = config.RUC_EMPLEADOR
    for ext, contenido in archivos.items():
        f = out / f"RP_{ruc}.{ext}"
        f.write_bytes(contenido.encode("cp1252", errors="replace"))
        print(f"  {f.name}: {len(contenido.splitlines())} línea(s)")
    print(f"\nListo. {len(registros)} practicantes -> carpeta: {out}")


if __name__ == "__main__":
    archivo = sys.argv[1] if len(sys.argv) > 1 else "ALTAS PRACTICANTES PRE PROFESIONALES (2).xlsx"
    main(str(ROOT / archivo))

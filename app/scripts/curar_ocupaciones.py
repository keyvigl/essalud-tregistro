"""Genera una lista CURADA de ocupaciones relevantes para EsSalud (salud +
administrativo + apoyo) a partir de la tabla 10. Es un punto de partida editable:
EsSalud puede quitar/agregar después.

Salida: app/data/ocupaciones_essalud.json
Uso:    python app/scripts/curar_ocupaciones.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "app" / "data"

# Se incluye si coincide con INCLUDE y NO con EXCLUDE. Patrones ESPECÍFICOS
# (no términos sueltos como "técnico" o "administrador" que traen cientos).
INCLUDE = re.compile(r"""
  # --- Salud (profesionales) ---
  ^MEDIC|\ MEDIC|ENFERMER|OBSTETR|OBSTETRIZ|ODONT[OÓ]L|DENTISTA|CIRUJAN|
  PEDIATR|GINEC[OÓ]L|CARDI[OÓ]L|NEUR[OÓ]L|DERMAT[OÓ]L|OFTALM[OÓ]L|PSIQUIATR|
  RADI[OÓ]L|ANESTESI[OÓ]L|ONC[OÓ]L|TRAUMAT[OÓ]L|UR[OÓ]L|GASTROENTER|ENDOCRIN[OÓ]L|
  NEUM[OÓ]L|NEFR[OÓ]L|REUMAT[OÓ]L|HEMAT[OÓ]L|PAT[OÓ]L[OÓ]G|INTERNISTA|GERIATR|
  EPIDEMI[OÓ]L|SANITARI[OA]|QU[IÍ]MIC[OA],\ FARMAC|FARMAC[EÉ]UTIC|PSIC[OÓ]L[OÓ]G|
  NUTRICI[OÓ]N|TECN[OÓ]L[OÓ]G[OA]\ M[EÉ]DIC|TERAPEUTA|FISIOTERAP|OPTOMETR|PODOL[OÓ]G|
  LABORATORISTA|MICROBI[OÓ]L|BACTERI[OÓ]L|^BI[OÓ]L[OÓ]GO$|
  TRABAJADOR.*SOCIAL|ASISTENT[AE]\ SOCIAL|
  # --- Salud (técnicos/auxiliares específicos) ---
  T[EÉ]CNIC[OA].*(ENFERMER|LABORATORI|FARMACI|RADIOL|SANITARI|SALUD|M[EÉ]DIC)|
  AUXILIAR.*(ENFERMER|LABORATORI|FARMACI|SALUD|M[EÉ]DIC)|
  # --- Administrativo ---
  ^ABOGAD|^CONTAD|^ECONOMISTA|^ESTAD[IÍ]STIC|^SECRETARI|^RECEPCIONISTA|^DIGITADOR|
  ^OFICINISTA|^CAJER|^ALMACENER|^ARCHIVER|
  ^ADMINISTRADOR,\ (ADMINISTRACION\ PUBLICA|PERSONAL|ABASTECIMIENTO)|
  ^ADMINISTRADOR\ DE\ EMPRESAS|^ADMINISTRADORES,\ OTROS|
  INGENIER[OA].*(SISTEMA|INFORM[AÁ]TIC|INDUSTRIAL)|
  ANALISTA.*(SISTEMA|PROGRAMAD|COMPUTAC|INFORM)|^PROGRAMADOR|
  T[EÉ]CNIC[OA]\ (ADMINISTRATIV|EN\ COMPUTAC|EN\ INFORM)|
  (ASISTENTE|AUXILIAR)\ ADMINISTRATIV|RECURSOS\ HUMANOS|
  # --- Apoyo / servicios ---
  ^CHOFER|^CONDUCTOR\ DE\ (VEHICUL|AMBULANCIA|AUTOM)|VIGILAN|^GUARDIA\ (DE\ SEGURID|CIVIL|PARTICULAR)|
  (TRABAJADOR|OPERARIO|PERSONAL|PE[OÓ]N|OBRERO)\ DE\ LIMPIEZA|^LIMPIADOR|
  ^COCINER|^LAVANDER|^TRABAJADOR.*LAVANDER|^ELECTRICISTA|^MENSAJER|^CONSERJE|
  ^PORTER|^TELEFONISTA|^JARDINER
""", re.I | re.X)

EXCLUDE = re.compile(r"""
  VETERINAR|FAUNA|MARIN|PESC|AGUA\ DULCE|HIDROBIOL|PISCICUL|ACUICOL|
  AGRICOL|AGROPECUARI|AGRONOM|GANADER|AVICOL|MINER|PETROL|GAS\ NATURAL|
  TEXTIL|CALZAD|CUERO|MADERA|FORESTAL|NAVAL|AERONAUT|AVIAC|MILITAR|POLICI|
  RELIGIOS|SACERDOT|DEPORT|ATLETA|FUTBOL|ARTIST|MUSIC|ACTOR|BAILARIN|PINTOR\ ARTIST|
  PESQUER|TEJEDOR|HILANDER|SASTRE|ZAPATER|CERAMIST|JOYER|SOLDADOR|FUNDIDOR|
  ALBANIL|CONSTRUCC|TOPOGRAF|GEOLOG|MINEROLOG|METALURG|TEXTILER|CURTIDOR
""", re.I | re.X)


def main():
    pub = json.loads((DATA / "ocupaciones.json").read_text(encoding="utf-8"))["publico"]
    sel = [o for o in pub if INCLUDE.search(o["descripcion"]) and not EXCLUDE.search(o["descripcion"])]
    # ordenar por descripción
    sel.sort(key=lambda o: o["descripcion"])
    (DATA / "ocupaciones_essalud.json").write_text(
        json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ocupaciones curadas para EsSalud: {len(sel)} (de {len(pub)})")
    print("Muestra:")
    for o in sel[:20]:
        print("  ", o["codigo"], o["descripcion"][:55])


if __name__ == "__main__":
    main()

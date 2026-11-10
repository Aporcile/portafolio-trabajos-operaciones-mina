# -*- coding: utf-8 -*-
"""Compuerta de seguridad: falla si el repositorio contiene datos sensibles.

Revisa nombres de archivo y contenido (texto, OOXML por dentro y blobs base64) contra:
  * reglas genéricas: correos, IP, URL fuera de lista, rutas locales de Windows, UNC, secretos,
    cadenas de conexión con servidor real, imágenes y archivos binarios no permitidos;
  * una lista privada opcional (--denylist) con términos y --guids con identificadores reales.
    Esa lista vive FUERA del repositorio y nunca se sube.

Imágenes y binarios: solo pasan si su SHA-256 figura en assets/archivos_permitidos.txt
(se generan con --registrar-permitidos después de revisar las salidas propias del proyecto).

Uso:
  python tools/verificar_limpio.py
  python tools/verificar_limpio.py --denylist RUTA\\terminos.txt --guids RUTA\\guids.txt
  python tools/verificar_limpio.py --registrar-permitidos     (registra imágenes/binarios actuales)
Código de salida: 0 = limpio, 1 = hay hallazgos.
"""
import argparse
import base64
import hashlib
import io
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PERMITIDAS = RAIZ / "assets" / "archivos_permitidos.txt"
OMITIR_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".emf", ".tif", ".tiff"}
EXT_OOXML = {".docx", ".xlsx", ".pptx", ".xlsm", ".dotx", ".potx"}
EXT_PROHIBIDAS = {".pbix", ".abf", ".pyc", ".exe", ".dll", ".msapp", ".zip", ".7z", ".rar", ".pfx", ".pem", ".key",
                  ".pdf", ".bak", ".mdb", ".bin", ".pbit", ".pbiviz"}
EXT_TEXTO = {".json", ".tmdl", ".py", ".ps1", ".sql", ".yaml", ".yml", ".md", ".txt", ".html", ".htm", ".js", ".css",
             ".m", ".dax", ".xml", ".pbir", ".platform", ".pbism", ".fx", ".toml", ".cfg", ".pbip", ".bat", ".csv",
             ".tsv", ".ini", ".env", ".ejemplo", ".svg", ".gitignore", ".mermaid", ".mmd", ".rels", ".config", ""}

HOSTS_OK = re.compile(
    r"(^|\.)(example(\.com|\.org|\.net)?|contoso\.(com|example)|json-schema\.org|developer\.microsoft\.com|"
    r"learn\.microsoft\.com|www\.w3\.org|aka\.ms|go\.microsoft\.com|github\.com|githubusercontent\.com|"
    r"shields\.io|img\.shields\.io|mermaid\.js\.org|python\.org|docs\.python\.org|pypi\.org|powerbi\.microsoft\.com|"
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|schema\.management\.azure\.com|"
    r"localhost|127\.0\.0\.1|0\.0\.0\.0|minera-demo\.example|tmdl\.dev|opensource\.org)$", re.I)
EMAIL_OK = re.compile(r"@(minera-demo\.example|example\.(com|org|net)|contoso\.example|users\.noreply\.github\.com)$", re.I)
IP_OK = re.compile(r"^(127\.|0\.0\.0\.0|255\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.)")

R_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
R_IP = re.compile(r"(?<![\w.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\w.])")
R_URL = re.compile(r"https?://([A-Za-z0-9.-]+)", re.I)
R_RUTA = re.compile(r"(?i)\b[A-Z]:(?:\\{1,4}|/)(?:Users|Innovaci|Windows|Program Files|Temp|Descargas|Downloads|Escritorio)")
R_UNC = re.compile(r"(?<![\w\\])\\\\{1,2}[A-Za-z0-9_.-]{3,}\\{1,2}[A-Za-z0-9$_.-]+")
R_SECRETO = re.compile(
    r"(?i)\b(password|pwd|passwd|contrase\w+|secret|api[_-]?key|bearer|client_secret|access_token)\b\s*[\"']?\s*[:=]\s*"
    r"[\"']?([^\s\"'<>$%{(\[,;]{4,})")
R_SECRETO_OK = re.compile(r"(?i)^(x{3,}|\*{3,}|tu_|su_|changeme|ejemplo|example|demo|dummy|placeholder|null|none|true|false|"
                          r"os\.|env|get|input|read|param|sec|secure|args|self|cfg|config|valor|<)")
R_CONEXION = re.compile(r"(?i)(Sql\.Database|Server\s*=|Data Source\s*=|AnalysisServices\.Database|powerbi://)[^\n]{0,120}")
R_CONEXION_OK = re.compile(r"(?i)(servidor-demo|srv-[a-z-]*-demo|localhost|127\.0\.0\.1|\(local\)|\bRutaDatos\b|example)")
R_GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
R_B64 = re.compile(r"[A-Za-z0-9+/]{300,}={0,2}")
MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"%PDF", b"PK\x03\x04", b"MZ", b"\xd0\xcf\x11\xe0")


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def cargar_permitidas():
    if not PERMITIDAS.exists():
        return set()
    return {l.split()[0] for l in PERMITIDAS.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def cargar_denylist(ruta):
    plano, regex = [], []
    if not ruta:
        return plano, regex
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("re:"):
            regex.append(re.compile(linea[3:], re.I))
        else:
            plano.append(norm(linea))
    return plano, regex


class Informe:
    def __init__(self):
        self.h = []

    def add(self, archivo, regla, detalle):
        self.h.append((str(archivo), regla, detalle))


def desescapar_unicode(t):
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)


ARCHIVOS_DE_REGLAS = {"tools/verificar_limpio.py"}  # define los patrones: solo se le aplica la lista privada


def revisar_texto(rel, texto, inf, plano, regex, guids, permitidas):
    if rel in ARCHIVOS_DE_REGLAS:
        revisar_denylist(rel, texto, inf, plano, regex)
        return
    vistas = [texto]
    if "\\u" in texto:
        vistas.append(desescapar_unicode(texto))
    for t in vistas:
        for m in R_EMAIL.finditer(t):
            if not EMAIL_OK.search(m.group(0)):
                inf.add(rel, "correo", m.group(0))
        for m in R_IP.finditer(t):
            if not IP_OK.match(m.group(0)):
                inf.add(rel, "ip", m.group(0))
        for m in R_URL.finditer(t):
            if not HOSTS_OK.search(m.group(1).rstrip(".")):
                inf.add(rel, "url", m.group(0))
        for m in R_RUTA.finditer(t):
            inf.add(rel, "ruta-local", t[m.start():m.start() + 60])
        for m in R_UNC.finditer(t):
            inf.add(rel, "ruta-unc", m.group(0))
        for m in R_SECRETO.finditer(t):
            if not R_SECRETO_OK.match(m.group(2)):
                inf.add(rel, "secreto", m.group(1) + "=…")
        for m in R_CONEXION.finditer(t):
            if not R_CONEXION_OK.search(m.group(0)):
                inf.add(rel, "conexion", m.group(0)[:90])
        if guids:
            for m in R_GUID.finditer(t):
                if m.group(0).lower() in guids:
                    inf.add(rel, "guid-real", m.group(0))
    # blobs base64: no se permiten imágenes/binarios incrustados salvo hash permitido
    for m in R_B64.finditer(texto):
        try:
            b = base64.b64decode(m.group(0) + "=" * (-len(m.group(0)) % 4), validate=False)
        except Exception:
            continue
        if b[:8].startswith(MAGIC) and sha(b) not in permitidas:
            inf.add(rel, "base64-binario", f"{len(b)} bytes, sha {sha(b)[:12]}")
    revisar_denylist(rel, texto, inf, plano, regex)


def revisar_denylist(rel, texto, inf, plano, regex):
    if not (plano or regex):
        return
    n = norm(texto)
    if "\\u" in texto:
        n += "\n" + norm(desescapar_unicode(texto))
    for term in plano:
        if len(term) < 5:
            if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", n):
                inf.add(rel, "denylist", term)
        elif term in n:
            inf.add(rel, "denylist", term)
    for rx in regex:
        m = rx.search(n)
        if m:
            inf.add(rel, "denylist-re", m.group(0)[:40])


def revisar_ooxml(rel, datos, inf, plano, regex, guids, permitidas):
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile:
        inf.add(rel, "binario", "zip ilegible")
        return
    for e in z.infolist():
        nombre = e.filename
        raw = z.read(nombre)
        ext = Path(nombre).suffix.lower()
        if ext in EXT_IMAGEN or "/embeddings/" in nombre or ext == ".bin":
            if sha(raw) not in permitidas:
                inf.add(rel, "ooxml-medio-no-permitido", nombre)
        elif ext in {".xml", ".rels", ".txt", ".json", ".csv"}:
            revisar_texto(f"{rel}!{nombre}", raw.decode("utf-8", "replace"), inf, plano, regex, guids, permitidas)


def revisar(raiz, plano, regex, guids, permitidas, registrar=False):
    inf = Informe()
    registro = []
    n = 0
    for p in sorted(raiz.rglob("*")):
        if any(parte in OMITIR_DIRS for parte in p.relative_to(raiz).parts):
            continue
        rel = p.relative_to(raiz).as_posix()
        if plano or regex:
            nr = norm(rel)
            for t in plano:
                if len(t) >= 5 and t in nr:
                    inf.add(rel, "denylist-en-nombre", t)
        if not p.is_file():
            continue
        n += 1
        ext = p.suffix.lower()
        datos = p.read_bytes()
        h = sha(datos)
        if p.stat().st_size > 10 * 1024 * 1024:
            inf.add(rel, "archivo-grande", f"{p.stat().st_size // 1024 // 1024} MB")
        if ext in EXT_IMAGEN:
            if registrar:
                registro.append((h, rel))
            elif h not in permitidas:
                inf.add(rel, "imagen-no-permitida", h[:12])
            continue
        if ext in EXT_OOXML:
            if registrar:
                registro.append((h, rel))
            elif h not in permitidas:
                inf.add(rel, "ooxml-no-permitido", h[:12])
            revisar_ooxml(rel, datos, inf, plano, regex, guids, permitidas | ({h} if registrar else set()))
            continue
        if ext in EXT_PROHIBIDAS:
            if registrar:
                registro.append((h, rel))
            elif h not in permitidas:
                inf.add(rel, "binario-prohibido", ext)
            continue
        if ext in EXT_TEXTO or p.name.startswith("."):
            texto = datos.decode("utf-8", "replace")
            revisar_texto(rel, texto, inf, plano, regex, guids, permitidas)
        elif datos[:8].startswith(MAGIC):
            inf.add(rel, "binario-desconocido", ext)
    return inf, n, registro


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ))
    ap.add_argument("--denylist", help="archivo privado con términos (uno por línea; 're:' = regex)")
    ap.add_argument("--guids", help="archivo privado con GUID reales (uno por línea)")
    ap.add_argument("--registrar-permitidos", action="store_true", help="registra hashes de imágenes/binarios actuales")
    ap.add_argument("--max", type=int, default=60, help="máximo de hallazgos a imprimir por regla")
    a = ap.parse_args()
    raiz = Path(a.raiz)
    plano, regex = cargar_denylist(a.denylist)
    guids = {l.strip().lower() for l in Path(a.guids).read_text(encoding="utf-8").splitlines()} if a.guids else set()
    permitidas = cargar_permitidas()
    inf, n, registro = revisar(raiz, plano, regex, guids, permitidas, a.registrar_permitidos)
    if a.registrar_permitidos:
        lineas = ["# sha256  ruta   (imágenes/binarios propios del proyecto, revisados a mano)"]
        lineas += [f"{h}  {r}" for h, r in sorted(registro, key=lambda x: x[1])]
        PERMITIDAS.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        print(f"Registrados {len(registro)} archivos permitidos en {PERMITIDAS}")
        return 0
    c = Counter(r for _, r, _ in inf.h)
    print(f"Archivos revisados: {n} | denylist: {len(plano) + len(regex)} reglas | GUID reales: {len(guids)}")
    if not inf.h:
        print("LIMPIO: 0 hallazgos")
        return 0
    print(f"HALLAZGOS: {len(inf.h)}  " + ", ".join(f"{k}={v}" for k, v in c.most_common()))
    por_regla = Counter()
    for arch, regla, det in inf.h:
        por_regla[regla] += 1
        if por_regla[regla] <= a.max:
            print(f"  [{regla}] {arch}  ->  {det}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

# Política de seguridad y datos

## Qué hay (y qué no) en este repositorio
- Solo código, modelos y documentación genéricos y **datos 100 % sintéticos**.
- No contiene credenciales, cadenas de conexión reales, nombres de servidores, correos, URLs internas, rutas locales,
  identificadores de entornos ni imágenes de marcas reales.
- No hay binarios de Office, PDF ni archivos `.pbix`; los datos van en CSV/JSON generados por script.

## Controles
- `tools/verificar_limpio.py` es una **compuerta**: revisa nombres de archivo y contenido (incluido el interior de
  archivos OOXML y blobs base64) y falla ante correos, IP, URLs fuera de lista, rutas de Windows, rutas UNC, secretos,
  cadenas de conexión no genéricas e imágenes o binarios no registrados.
- El workflow `.github/workflows/sanitizacion.yml` la ejecuta en cada push y pull request.
- Las imágenes permitidas se registran por hash en `assets/archivos_permitidos.txt`; cualquier otra falla.

## Cómo reportar un hallazgo
Abre un issue sin pegar el dato sensible (indica archivo y línea) o escribe al autor. Se retira el contenido de inmediato.

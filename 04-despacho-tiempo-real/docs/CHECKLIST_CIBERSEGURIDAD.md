# Checklist de ciberseguridad

Plantilla para pedir la autorización de conexión de un dashboard operacional a bases de datos y para
declarar cómo opera. Pensada para que el área de seguridad pueda revisarla sin leer código.
Los nombres (`servidor-demo`, `despacho_demo`, `planta_demo`) son marcadores: reemplazar por los reales
en el entorno de cada organización.

## 1. Qué es

- Aplicación web **local** (Python, biblioteca estándar) que corre en un equipo de la sala de despacho
  y se muestra en un televisor con el navegador en modo kiosko.
- Lee datos operacionales de la base de despacho (`despacho_demo`) y de la base de planta (`planta_demo`),
  calcula KPI, genera alertas y los muestra. **No escribe en ninguna base de datos** y no envía datos fuera
  de la red corporativa (salvo que se active explícitamente un proveedor externo de IA, ver §6).

## 2. Lo que hay que pedir

| Ítem | Detalle | Estado |
|---|---|---|
| Login SQL de **solo lectura** en `servidor-demo` (base `despacho_demo`) | `SELECT` únicamente sobre las tablas listadas en `sql/esquema_demo.sql` (equipos, ciclos, descargas, horas_equipo, gps_lecturas, planes, plan_items, estados_equipo). Idealmente una cuenta de servicio dedicada, con un rol de lectura limitado a esas tablas. | [ ] |
| Login SQL de **solo lectura** en `servidor-demo` (base `planta_demo`) | `SELECT` sobre `puntos` y `valores`. Opcional: sin él, el dashboard funciona sin el plan de la flota auxiliar. | [ ] |
| Alternativa: **autenticación integrada** | Si se prefiere no usar logins SQL, el dashboard soporta autenticación integrada con la cuenta que ejecuta el proceso (`DESPACHO_AUTH=windows`). | [ ] |
| Acceso de red desde el equipo del dashboard | Puerto TCP del motor SQL hacia `servidor-demo` (el puerto concreto lo define el administrador). | [ ] |
| Cifrado de la conexión | Por defecto cifrada y con validación de certificado (`SQL_ENCRYPT=yes`, `SQL_TRUST_SERVER_CERTIFICATE=no`). Relajar solo con aprobación y en redes controladas. | [ ] |

## 3. Cómo se protege el acceso

- **Solo lectura por código**: antes de enviar cualquier consulta, `backend/despacho/datos/solo_lectura.py`
  rechaza todo lo que no sea una única sentencia `SELECT` (INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, CREATE,
  TRUNCATE, EXEC, GRANT, `SELECT INTO`, procedimientos `xp_`/`sp_`, OPENROWSET, sentencias apiladas, etc.). Es una
  segunda barrera además del permiso del login, con tests que cubren intentos de esconder sentencias en
  comentarios, cadenas e identificadores.
- **Consultas fijas y parametrizadas**: viven en `sql/consultas/*.sql`, usan `WITH (NOLOCK)` y reciben fechas
  como parámetros tipados (nunca se concatena texto en el SQL). No hay entrada de usuario que llegue a SQL.
- **Carga mínima**: cada consulta tiene su propia frecuencia (GPS 10 s, ciclos 30 s, horas 60 s, planes 30 min),
  timeout, y nunca se ejecuta dos veces a la vez.
- **Valores por defecto seguros**: el servidor escucha solo en `127.0.0.1` y la conexión SQL va cifrada.

## 4. Dónde quedan las credenciales

- Archivo `.env` en la carpeta del proyecto: texto plano, excluido de git (`.gitignore`), con permisos del
  sistema de archivos restringidos al usuario que ejecuta el proceso. El repositorio solo incluye `env.ejemplo`
  con marcadores.
- Recomendado: almacén de secretos del sistema operativo o de la organización, o autenticación integrada.
- Las credenciales no se escriben en logs, no viajan al navegador, no aparecen en el snapshot ni en la base
  local. `Config.resumen_sin_secretos()` enmascara toda variable cuyo nombre contenga `PASSWORD`, `API_KEY`,
  `TOKEN`, `SECRET` o `CONTRASENA`.

## 5. Exposición de red del dashboard

- Por defecto el servidor web escucha **solo en `127.0.0.1`**: solo el propio equipo puede abrirlo.
- Si otro equipo (video wall) debe abrirlo desde la red, se configura `WEB_HOST=0.0.0.0` y es **obligatorio**
  definir `WEB_TOKEN`: las acciones (reconocer alertas) exigen ese token. La lectura de KPI no contiene datos
  personales.
- Sin CORS, sin cookies y sin autenticación de usuarios: es una pantalla de sala, no una aplicación multiusuario.
- Conexiones salientes en ejecución: **ninguna** por defecto (sin CDN, sin telemetría, sin actualizaciones automáticas).

## 6. Inteligencia artificial (opcional)

- Por defecto el panel de recomendaciones usa un **motor local de reglas** (sin red).
- Un proveedor externo de IA, si se habilita, es opt-in explícito (`IA_PROVEEDOR=externo` y una clave de API).
  Solo recibiría KPI agregados y alertas (tonelajes, porcentajes, nombres de equipos y rutas); nunca credenciales,
  nombres de personas ni filas crudas, y cualquier error vuelve al motor de reglas.

## 7. Datos locales

- Base SQLite local (prevista) con historial de snapshots y alertas: contiene solo KPI.
- Logs rotativos sin secretos.

## 8. Dependencias

- Backend: solo biblioteca estándar de Python. Cualquier paquete opcional (por ejemplo, un driver ODBC)
  se instalaría en un entorno virtual dentro de la carpeta del proyecto, nunca a nivel sistema.
- Frontend: sin librerías externas ni CDN.

## 9. Lo que el equipo declara

- No se instala software a nivel sistema ni se modifican firewall, registro, servicios o tareas programadas.
- El código es auditable: consultas SQL legibles en `sql/consultas/`, barrera de solo lectura en
  `backend/despacho/datos/solo_lectura.py` y sus tests en `tests/test_solo_lectura.py`.

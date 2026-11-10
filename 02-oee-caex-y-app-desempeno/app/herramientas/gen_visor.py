"""Genera scrVisor.yaml (pantalla que se muestra en la reunión: solo lectura salvo el Cierre)."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from yamlgen import *  # noqa

DEV = Path(__file__).resolve().parent.parent / 'pantallas'
GRIS_TXT = 'RGBA(90, 98, 104, 1)'

# ---------- minuta por correo ----------
# Se arma al cerrar con lo mismo que se vio en el visor y se envía al sincronizar (Outlook de quien sincroniza).
# Va a todos los convocados de RD_Participantes, hayan asistido o no; los ausentes la reciben con un aviso arriba.
# HTML con estilos en línea (Outlook ignora las hojas de estilo) y comillas simples para no escapar en Power Fx.


def esc(x):
    """Texto escrito por personas, con los caracteres HTML escapados."""
    return f'Substitute(Substitute(Substitute({x}, "&", "&amp;"), "<", "&lt;"), ">", "&gt;")'


def escnl(x):
    return f'Substitute(Substitute({esc(x)}, Char(13), ""), Char(10), "<br>")'


H3 = "<h3 style='font-size:15px;color:#1b2a41;border-bottom:2px solid #4f9dde;padding-bottom:4px;margin:24px 0 8px'>"
TBL = "<table cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;font-size:13px'>"
TH = "<th align='left' style='background:#dfe5ee;color:#1b2a41;padding:6px 8px'>"
THC = "<th align='center' style='background:#dfe5ee;color:#1b2a41;padding:6px 8px'>"
THR = "<th align='right' style='background:#dfe5ee;color:#1b2a41;padding:6px 8px'>"
THO = "style='background:#1b2a41;color:#ffffff;padding:6px 8px"
TD = "<td style='padding:6px 8px;border-bottom:1px solid #e1e6e8;vertical-align:top'>"
TDC = "<td align='center' style='padding:6px 8px;border-bottom:1px solid #e1e6e8;vertical-align:top;white-space:nowrap'>"
P = "<p style='margin:4px 0'>"
PGRIS = "<p style='margin:4px 0;color:#828a8e'>"
WRAP_INI = "<div style='font-family:Segoe UI,Arial,sans-serif;color:#212529;max-width:760px'>"
NOTA_AUSENTE = ("<div style='background:#fff3e0;border-left:4px solid #f28c28;padding:10px 14px;margin:14px 20px 0;"
                "font-size:13px'>No asististe a esta reunión. Este es el resumen de lo que se vio.</div>")



# 3. Indicadores en la minuta: lleva el OEE de transporte (CAEX) del informe que se vio en la reunión, en sus 3 periodos: el
# movimiento real contra el plan y solo las palancas que quedaron bajo el plan, de la que más perdió a la que menos. Bajo el
# plan = perdió más del 0,1 % del plan de toneladas, la misma regla del botón rojo del informe. colOEE la carga Inicio ›
# Actualizar datos con el flujo RD-OEE-Minuta (consulta dax/OEE_minuta.dax sobre el modelo del informe). Sin números con
# decimales (/ 1000 en vez de 0.001), para que la fórmula también se pueda pegar en la barra de Studio en español.
OTD = "<td style='padding:5px 8px;border-bottom:1px solid #e1e6e8'>"
OTDR = "<td align='right' style='padding:5px 8px;border-bottom:1px solid #e1e6e8;white-space:nowrap'>"
# Fila a lo ancho de la tabla; queda abierta (sin cerrar el atributo style) para agregarle su color.
OTDF = "<td colspan='4' style='padding:5px 8px;border-bottom:1px solid #e1e6e8"
OEE_MINUTA = f'''If(
    IsEmpty(colOEE),
    "{PGRIS}Sin datos del informe OEE cargados.</p>",
    "<p style='margin:4px 0 6px;font-size:12px;color:#5a6268'>Movimiento de los CAEX contra el plan y, en cada periodo, solo las " &
    "palancas que quedaron bajo el plan, de la que más perdió a la que menos. " & First(colOEE).Datos & ".</p>" &
    "{TBL}<tr>{TH}Palanca</th>{THR}Real</th>{THR}Plan</th>{THR}Toneladas</th></tr>" &
    Concat(
        Sort(colOEE, Orden) As p,
        "<tr><td colspan='4' {THO};font-weight:bold'>" & p.Periodo & "<span style='font-weight:normal;color:#c8d3e3'> · " &
        Text(p.Ini, "ddd dd-mm", "es-ES") & If(p.Fin = p.Ini, "", " a " & Text(p.Fin, "ddd dd-mm", "es-ES")) & "</span></td></tr>" &
        If(
            IsBlank(p.PlanT) || p.PlanT = 0,
            "<tr>{OTDF};color:#828a8e'>Movimiento " & Text(p.RealT, "#,##0") & " t · sin plan cargado para este periodo.</td></tr>",
            With(
                {{v: p.RealT / p.PlanT - 1}},
                "<tr>{OTDF};background:#f0f3f9'>Movimiento <b>" & Text(p.RealT, "#,##0") & " t</b> de " & Text(p.PlanT, "#,##0") &
                " t del plan (<b style='color:" & If(v * 1000 < -1, "#c62828", "#1b2a41") & "'>" & If(v > 0, "+", "") &
                Text(v * 100, "0.00") & "%</b>) · OEE " & Text(p.OEEReal * 100, "0.0") & "% (plan " & Text(p.OEEPlan * 100, "0.0") &
                "%)</td></tr>"
            ) &
            With(
                {{
                    bajo: Sort(
                        Filter(
                            Table(
                                {{Palanca: "Disponibilidad", Real: Text(p.DFReal * 100, "0.0") & "%", Plan: Text(p.DFPlan * 100, "0.0") & "%", T: p.PerdDF}},
                                {{Palanca: "UEBD", Real: Text(p.UEBDReal * 100, "0.0") & "%", Plan: Text(p.UEBDPlan * 100, "0.0") & "%", T: p.PerdUEBD}},
                                {{Palanca: "Rendimiento efectivo", Real: Text(p.RendReal, "#,##0") & " t/h", Plan: Text(p.RendPlan, "#,##0") & " t/h", T: p.PerdRend}},
                                {{Palanca: "Horas nominales", Real: Text(p.HNReal, "#,##0") & " h", Plan: Text(p.HNPlan, "#,##0") & " h", T: p.PerdHN}}
                            ),
                            !IsBlank(T) && T < -p.PlanT / 1000
                        ),
                        T
                    )
                }},
                If(
                    IsEmpty(bajo),
                    "<tr>{OTDF};color:#2e7d32'>✔ Ninguna palanca quedó bajo el plan.</td></tr>",
                    Concat(
                        bajo,
                        "<tr>{OTD}" & Palanca & "</td>{OTDR}<b>" & Real & "</b></td>{OTDR}<span style='color:#5a6268'>" & Plan &
                        "</span></td>{OTDR}<b style='color:#c62828'>" & Text(T, "#,##0") & " t</b></td></tr>"
                    )
                )
            )
        )
    ) & "</table>"
)'''

MINUTA_CAB = '''"<div style='background:#1b2a41;color:#ffffff;padding:16px 20px'>" &
"<div style='font-size:20px;font-weight:bold'>Minuta · Reunión semanal de supervisores</div>" &
"<div style='font-size:13px;color:#c8d3e3;margin-top:4px'>RD Minera Demo · " & Text(varInicio, "dddd dd-mm-yyyy", "es-ES") &
" · " & Text(varInicio, "hh:mm") & " a " & Text(varFin, "hh:mm") & " · " &
Round(DateDiff(varInicio, varFin, TimeUnit.Seconds) / 60, 0) & " de " & nMinutosMeta & " min</div></div>"'''

# Seguridad en la minuta: los indicadores en una línea y los avisos con su nivel, como en el visor. Los campos
# Rep / RepMeta (claves rep / repm del JSON) se escriben a mano.
TD_NIVEL = "<td style='padding:6px 8px;border-bottom:1px solid #e1e6e8;vertical-align:top;white-space:nowrap;width:120px'>"
SEG_MINUTA = f'''With(
    {{d: varCierreInd}},
    If(
        IsBlank(d.Inc) && IsBlank(d.Rep) && IsBlank(d.InsReal),
        "",
        "{P}<b>Incidentes de la semana:</b> " & Coalesce(Text(d.Inc), "—") & If(IsBlank(d.IncAnt), "", " (anterior: " & d.IncAnt & ")") &
        " · <b>Hipo Hazard:</b> " & Coalesce(Text(d.Rep), "—") & If(IsBlank(d.RepMeta), "", " (meta " & d.RepMeta & ")") &
        " · <b>Inspecciones:</b> " & Coalesce(Text(d.InsReal), "—") & If(IsBlank(d.InsPlan), "", " de " & d.InsPlan) & "</p>"
    )
) &
If(
    IsEmpty(colCierreAvisos),
    "{PGRIS}Sin avisos registrados.</p>",
    "{TBL}" &
    Concat(
        Sort(colCierreAvisos, Rango * 1000 + Orden),
        "<tr>{TD_NIVEL}<span style='color:#ffffff;padding:2px 8px;border-radius:10px;background:" &
        Switch(Nivel, "Crítico", "#c62828", "Precaución", "#ed6c02", "Recordar", "#2e7d32", "#1b2a41") & "'>" &
        Switch(Nivel, "Crítico", "✖ Crítico", "Precaución", "⚠ Precaución", "Recordar", "✔ Recordar", "Aviso") &
        "</span></td>{TD}" & {esc("Texto")} & "</td></tr>"
    ) & "</table>"
)'''

def cuenta(expr, singular, plural):
    """«1 abierto» / «3 abiertos»."""
    return f'With({{n: {expr}}}, n & If(n = 1, " {singular}", " {plural}"))'


MINUTA_CUERPO = f'''"<div style='padding:4px 20px 16px'>" &
// Asistencia
"{H3}Asistencia</h3>" &
"{P}<b>Líder:</b> " & {esc("User().FullName")} & "</p>" &
"{P}<b>Presentes (" & CountRows(Filter(colAsis, Tipo = "Convocado" && Presente)) & " de " &
CountRows(Filter(colAsis, Tipo = "Convocado")) & " convocados):</b> " &
If(
    IsEmpty(Filter(colAsis, Tipo = "Convocado" && Presente)),
    "ninguno",
    Concat(Sort(Filter(colAsis, Tipo = "Convocado" && Presente), Nombre), {esc("Nombre")}, ", ")
) & "</p>" &
If(
    IsEmpty(Filter(colAsis, !Presente)),
    "",
    "{P}<b>Ausentes:</b> " & Concat(Sort(Filter(colAsis, !Presente), Nombre), {esc("Nombre")}, ", ") & "</p>"
) &
If(
    IsEmpty(Filter(colAsis, Tipo = "Invitado")),
    "",
    "{P}<b>Invitados:</b> " & Concat(Sort(Filter(colAsis, Tipo = "Invitado"), Nombre), {esc("Nombre")}, ", ") & "</p>"
) &
// 1. Seguridad
"{H3}1. Seguridad</h3>" &
{SEG_MINUTA} &
// 2. Compromisos: los de la semana pasada y, al final, los de esta semana preparados en el editor (En progreso)
"{H3}2. Compromisos</h3>" &
If(
    IsEmpty(colCierreRev) && IsEmpty(colNuevosPrep),
    "{PGRIS}No había compromisos abiertos.</p>",
    "{P}" & {cuenta('CountRows(colCierreRev)', 'revisado', 'revisados')} & " · " &
    {cuenta('CountRows(Filter(colCierreRev, EstadoNuevo = "Cumplido"))', 'cumplido', 'cumplidos')} & " · " &
    {cuenta('CountRows(Filter(colCierreRev, EstadoNuevo = "Atrasado"))', 'atrasado', 'atrasados')} &
    If(IsEmpty(colNuevosPrep), "", " · " & {cuenta('CountRows(colNuevosPrep)', 'nuevo de esta semana', 'nuevos de esta semana')}) & "</p>" &
    "{TBL}<tr>{TH}Compromiso</th>{TH}Responsable</th>{THC}Vence</th>{THC}Estado</th></tr>" &
    Concat(
        Sort(colCierreRev, FechaLimite),
        "<tr>{TD}" & {esc("Titulo")} &
        If(IsBlank(Comentario), "", "<br><span style='font-size:12px;color:#2e7d32'>Evidencia: " & {esc("Comentario")} & "</span>") &
        If(IsBlank(Url), "", " <a href='" & Url & "' style='font-size:12px'>ver evidencia</a>") &
        "</td>{TD}" & {esc("ResponsableNombre")} & "</td>{TDC}" & Text(FechaLimite, "dd-mm") & "</td>{TDC}" &
        "<span style='color:#ffffff;padding:2px 8px;border-radius:10px;background:" &
        Switch(EstadoNuevo, "Cumplido", "#2e7d32", "Atrasado", "#ed6c02", "#1b2a41") & "'>" &
        Switch(EstadoNuevo, "Cumplido", "✔ Cumplido", "Atrasado", "⚠ Atrasado", "En progreso") &
        "</span></td></tr>"
    ) &
    Concat(
        Sort(colNuevosPrep, FechaLimite),
        "<tr>{TD}" & {esc("Titulo")} & "</td>{TD}" & {esc("Responsable")} & "</td>{TDC}" & Text(FechaLimite, "dd-mm") &
        "</td>{TDC}<span style='color:#ffffff;padding:2px 8px;border-radius:10px;background:#1b2a41'>En progreso</span></td></tr>"
    ) & "</table>"
) &
// 3. Indicadores: OEE de transporte (CAEX) en JUE-DOM, SEMANAL y MENSUAL, con el detalle solo de lo bajo plan
"{H3}3. Indicadores · OEE de transporte (CAEX)</h3>" &
{OEE_MINUTA} &
// 4. Compromisos nuevos que surgieron en la reunión (los preparados en el editor van en la sección 2)
"{H3}4. Compromisos nuevos</h3>" &
If(
    IsEmpty(colNuevos),
    "{PGRIS}No se registraron compromisos nuevos.</p>",
    "{TBL}<tr>{TH}Compromiso</th>{TH}Responsable</th>{THC}Fecha límite</th></tr>" &
    Concat(
        Sort(colNuevos, FechaLimite),
        "<tr>{TD}" & {esc("Titulo")} & "</td>{TD}" & {esc("Responsable")} & "</td>{TDC}" & Text(FechaLimite, "dd-mm-yyyy") & "</td></tr>"
    ) & "</table>"
) &
"<p style='margin:24px 0 0;font-size:11px;color:#828a8e'>Minuta generada por la app RD Terreno (prototipo) al cerrar la reunión. " &
"Se envía a todos los convocados, hayan asistido o no.</p></div>"'''


def indentar(txt, n):
    return '\n'.join((' ' * n + ln) if ln else ln for ln in txt.split('\n'))


# Asistencia por área: colAsisVista es lo que muestra la ventana: por cada área, un encabezado a lo ancho (celda "Area" + celda
# "AreaFin", porque la galería va en 2 columnas) y sus personas por nombre; si el área queda impar se completa con una celda
# "Vacio". Las áreas van por orden alfabético, después "Sin área" y al final los invitados. Se rearma al abrir la ventana,
# al quitar o restaurar y al sumar un invitado; marcar presente o ausente actualiza las dos colecciones.
ARMAR_ASIS = '''Clear(colAsisVista);
With(
    {areas: Sort(Distinct(colAsis, Area), Value)},
    ForAll(
        Sequence(CountRows(areas)) As i,
        With(
            {a: Index(areas, i.Value).Value},
            With(
                {o: If(a = "Invitados", 999, a = "Sin área", 998, i.Value) * 1000, gente: Sort(Filter(colAsis, Area = a), Nombre)},
                Collect(
                    colAsisVista,
                    {Orden: o, Fila: "Area", Area: a, IdLocal: "", Nombre: "", Correo: "", Cargo: "", Tipo: "", Presente: true},
                    {Orden: o + 1, Fila: "AreaFin", Area: a, IdLocal: "", Nombre: "", Correo: "", Cargo: "", Tipo: "", Presente: true}
                );
                ForAll(
                    Sequence(CountRows(gente)) As j,
                    With(
                        {p: Index(gente, j.Value)},
                        Collect(
                            colAsisVista,
                            {Orden: o + 1 + j.Value, Fila: "Persona", Area: a, IdLocal: p.IdLocal, Nombre: p.Nombre, Correo: p.Correo, Cargo: p.Cargo, Tipo: p.Tipo, Presente: p.Presente}
                        )
                    )
                );
                If(
                    Mod(CountRows(gente), 2) = 1,
                    Collect(colAsisVista, {Orden: o + 999, Fila: "Vacio", Area: a, IdLocal: "", Nombre: "", Correo: "", Cargo: "", Tipo: "", Presente: true})
                )
            )
        )
    )
)'''

MINUTA = f'''// Asistencia y minuta: una fila de asistencia por reunión y la minuta en la bandeja de salida.
Collect(
    colOutAsistencia,
    {{
        Fecha: Text(Today(), "yyyy-mm-dd"),
        SesionIdLocal: gblSesionId,
        Convocados: CountRows(Filter(colAsis, Tipo = "Convocado")),
        Presentes: CountRows(Filter(colAsis, Tipo = "Convocado" && Presente)),
        Invitados: CountRows(Filter(colAsis, Tipo = "Invitado")),
        Ausentes: Concat(Filter(colAsis, !Presente), Nombre, ", "),
        Json: JSON(ForAll(colAsis As a, {{Nombre: a.Nombre, Correo: a.Correo, Area: a.Area, Tipo: a.Tipo, Presente: a.Presente}})),
        LiderEmail: User().Email
    }}
);
Set(
    varMinutaCab,
{indentar(MINUTA_CAB, 4)}
);
Set(
    varMinutaCuerpo,
{indentar(MINUTA_CUERPO, 4)}
);
// Destinatarios: presentes (con quien cierra, aunque no esté en la lista) y, en otro correo, los ausentes.
ClearCollect(colMinPara, ForAll(Filter(colAsis, Presente && !IsBlank(Correo)) As a, {{Correo: Lower(a.Correo)}}));
If(IsBlank(LookUp(colAsis, Lower(Correo) = Lower(User().Email))), Collect(colMinPara, {{Correo: Lower(User().Email)}}));
ClearCollect(colMinParaAus, ForAll(Filter(colAsis, !Presente && !IsBlank(Correo)) As a, {{Correo: Lower(a.Correo)}}));
Collect(
    colOutMinuta,
    {{
        Id: Text(GUID()),
        SesionIdLocal: gblSesionId,
        Para: Concat(Distinct(colMinPara, Correo), Value, ";"),
        Asunto: "Minuta RD Minera Demo · " & Text(Today(), "dd-mm-yyyy"),
        Html: "{WRAP_INI}" & varMinutaCab & varMinutaCuerpo & "</div>"
    }}
);
If(
    !IsEmpty(colMinParaAus),
    Collect(
        colOutMinuta,
        {{
            Id: Text(GUID()),
            SesionIdLocal: gblSesionId,
            Para: Concat(Distinct(colMinParaAus, Correo), Value, ";"),
            Asunto: "Minuta RD Minera Demo · " & Text(Today(), "dd-mm-yyyy"),
            Html: "{WRAP_INI}" & varMinutaCab & "{NOTA_AUSENTE}" & varMinutaCuerpo & "</div>"
        }}
    )
);
SaveData(colOutAsistencia, "rd_out_asis");
SaveData(colOutMinuta, "rd_out_min");
'''


# ---------- cierre de la reunión ----------
# Un compromiso nuevo escrito completo que no se alcanzó a agregar también se guarda.
CERRAR_INI = r'''=If(
    IsBlank(varEditNuevo) && !IsBlank(Trim(txtNuevoQue.Text)) && !IsBlank(Trim(txtNuevoResp.Text)),
    Collect(colNuevos, {Titulo: Trim(txtNuevoQue.Text), Responsable: Trim(txtNuevoResp.Text), FechaLimite: dpNuevoFecha.SelectedDate, IdLocal: Text(GUID())})
);
Set(varFin, Now());
Collect(colTiempos, {Bloque: varBloque, Seg: DateDiff(varBloqueInicio, varFin, TimeUnit.Seconds)});
// Copia de lo preparado: al registrar la sesión cambia la fecha de la próxima reunión y las fórmulas se recalculan.
ClearCollect(colCierreRev, fxRevision);
// colCierreDest queda vacía, con la forma de fxDest, para que Inicio siga sincronizando igual y no se escriban destacados
// de una preparación anterior.
ClearCollect(colCierreDest, FirstN(fxDest, 0));
Set(varCierreSeg, fxSeg);
ClearCollect(colCierreAvisos, fxAvisos);
Set(varCierreInd, fxIndSeg);
// Los registros salen con las mismas columnas que los Excel de RD/Datos.
// Fechas como texto aaaa-mm-dd (y hh:mm) para que no se corran por zona horaria.
Collect(
    colOutSesiones,
    {
        Titulo: "RD-" & gblGrupo & "-" & Text(Today(), "yyyy-mm-dd"),
        Grupo: gblGrupo,
        Area: "Operaciones Mina",
        Fecha: Text(Today(), "yyyy-mm-dd"),
        HoraInicio: Text(varInicio, "yyyy-mm-dd hh:mm"),
        HoraTermino: Text(varFin, "yyyy-mm-dd hh:mm"),
        Estado: "Cerrada",
        Motivo: "",
        LiderNombre: User().FullName,
        LiderEmail: User().Email,
        Asistentes: CountRows(Filter(colAsis, Presente)),
        Animo1: 0,
        Animo2: 0,
        Animo3: 0,
        Animo4: 0,
        Animo5: 0,
        TemaSeguridad: varCierreSeg,
        MinutosDuracion: Round(DateDiff(varInicio, varFin, TimeUnit.Seconds) / 60, 1),
        // Minutos sobre la duración planificada (nMinutosMeta).
        MinutosExceso: Max(0, Round(DateDiff(varInicio, varFin, TimeUnit.Seconds) / 60 - nMinutosMeta, 1)),
        TiemposBloques: JSON(colTiempos),
        IdeasPresentadas: 0,
        CompromisosNuevos: CountRows(colNuevos) + CountRows(colNuevosPrep),
        Observaciones: "",
        RutaActa: "",
        IdLocal: gblSesionId
    }
);
ForAll(
    colCierreRev As r,
    Collect(
        colOutRevisiones,
        {
            Clave: "REV-" & gblSesionId & "-" & r.ID,
            FechaRevision: Text(varFin, "yyyy-mm-dd hh:mm"),
            CompromisoId: r.ID,
            Compromiso: r.Titulo,
            EstadoAnterior: r.EstadoAnterior,
            EstadoNuevo: r.EstadoNuevo,
            Comentario: r.Comentario,
            Grupo: gblGrupo,
            SesionIdLocal: gblSesionId
        }
    )
);
// Evidencias (fotos o archivos) que no alcanzaron a subirse al preparar (solo en el equipo que las tomó): suben al sincronizar.
ForAll(
    colEvid As e,
    If(
        IsBlank(LookUp(colCierreRev, ID = e.CompromisoId).Url),
        Collect(
            colOutEvidencias,
            {
                IdLocal: Text(GUID()),
                SesionIdLocal: gblSesionId,
                CompromisoId: e.CompromisoId,
                Grupo: gblGrupo,
                Comentario: LookUp(colCierreRev, ID = e.CompromisoId).Comentario,
                Foto: e.Foto,
                Url: "",
                NombreArchivo: gblGrupo & "_" & Text(Today(), "yyyy-mm-dd") & "_C" & e.CompromisoId & "_" & Left(gblSesionId, 8) &
                    If(IsBlank(e.Nombre), ".jpg", IsBlank(Find(".", e.Nombre)), "", "." & Lower(Last(Split(e.Nombre, ".")).Value))
            }
        )
    )
);
// Evidencias ya subidas al preparar: solo falta dejar su link en el compromiso.
ForAll(
    Filter(colCierreRev, !IsBlank(Url)) As r,
    Collect(
        colOutEvidencias,
        {
            IdLocal: Text(GUID()),
            SesionIdLocal: gblSesionId,
            CompromisoId: r.ID,
            Grupo: gblGrupo,
            Comentario: r.Comentario,
            Foto: If(false, First(colEvid).Foto),
            Url: r.Url,
            NombreArchivo: ""
        }
    )
);
ForAll(
    colNuevos As n,
    If(
        IsBlank(LookUp(colOutCompromisos, IdLocal = n.IdLocal)),
        Collect(
            colOutCompromisos,
            {
                // ID se numera al sincronizar (Excel no tiene autonumérico).
                ID: 0,
                Titulo: n.Titulo,
                ResponsableNombre: n.Responsable,
                FechaLimite: Text(n.FechaLimite, "yyyy-mm-dd"),
                Estado: "Abierto",
                Abierto: "Sí",
                FechaCreacion: Text(Today(), "yyyy-mm-dd"),
                FechaCierre: "",
                Comentario: "",
                EvidenciaUrl: "",
                Grupo: gblGrupo,
                Prioridad: "Media",
                Origen: "Reunión",
                ResponsableEmail: "",
                SesionIdLocal: gblSesionId,
                IdLocal: n.IdLocal
            }
        )
    )
);
// Compromisos de esta semana preparados en el editor: se vieron en Compromisos y se suben En progreso.
ForAll(
    colNuevosPrep As n,
    If(
        IsBlank(LookUp(colOutCompromisos, IdLocal = n.IdLocal)),
        Collect(
            colOutCompromisos,
            {
                ID: 0,
                Titulo: n.Titulo,
                ResponsableNombre: n.Responsable,
                FechaLimite: Text(n.FechaLimite, "yyyy-mm-dd"),
                Estado: "En progreso",
                Abierto: "Sí",
                FechaCreacion: Text(Today(), "yyyy-mm-dd"),
                FechaCierre: "",
                Comentario: "",
                EvidenciaUrl: "",
                Grupo: gblGrupo,
                Prioridad: "Media",
                Origen: "Reunión",
                ResponsableEmail: "",
                SesionIdLocal: gblSesionId,
                IdLocal: n.IdLocal
            }
        )
    )
);
ForAll(
    colCierreDest As d,
    Collect(
        colOutDestacados,
        {
            FechaReunion: Text(Today(), "yyyy-mm-dd"),
            Tipo: d.Tipo,
            Orden: d.Orden,
            Texto: d.Texto,
            Grupo: gblGrupo,
            SesionIdLocal: gblSesionId,
            IdLocal: d.IdLocal
        }
    )
);
'''
CERRAR_FIN = r'''SaveData(colOutSesiones, "rd_out_ses");
SaveData(colOutRevisiones, "rd_out_rev");
SaveData(colOutCompromisos, "rd_out_comp");
SaveData(colOutEvidencias, "rd_out_evid");
SaveData(colOutDestacados, "rd_out_dest");
// Cumplido cierra el compromiso (queda en Excel, no vuelve a aparecer); En progreso y Atrasado siguen abiertos.
RemoveIf(colCompromisos, ID in Filter(colCierreRev, EstadoNuevo = "Cumplido").ID);
ForAll(Filter(colCierreRev, EstadoNuevo <> EstadoAnterior) As r, UpdateIf(colCompromisos, ID = r.ID, {Estado: r.EstadoNuevo}));
SaveData(colCompromisos, "rd_comp");
Clear(colNuevos);
Clear(colNuevosPrep);
Clear(colEvid);
Clear(colCierreRev);
Clear(colCierreDest);
Clear(colAsis);
Clear(colAsisQuitados);
Clear(colAsisVista);
Set(varVerAsistencia, false);
Set(varPrepSucia, false);
Set(varReunionEnCurso, false);
Notify("Reunión cerrada en " & Round(DateDiff(varInicio, varFin, TimeUnit.Seconds) / 60, 1) & " min. Se sube sola cuando haya señal.", NotificationType.Success);
Navigate(scrInicio, ScreenTransition.Fade)'''
CERRAR = CERRAR_INI + MINUTA + CERRAR_FIN

# ---------- encabezado ----------
encabezado = container('conHeaderReunion', {'Fill': '=colPrimario', 'Height': '=72', 'Width': '=Parent.Width',
                                             'RadiusBottomLeft': '=0', 'RadiusBottomRight': '=0',
                                             'RadiusTopLeft': '=0', 'RadiusTopRight': '=0'}, [
    ctl('imgLogoReunion', 'Image@2.2.3', {'Image': LOGO, 'ImagePosition': '=ImagePosition.Fit', 'Height': '=56',
                                          'Width': '=120', 'X': '=12', 'Y': '=8'}),
    # Logo secundario entre el logo principal y el título. Para hacerle lugar a 1024 px, el cronómetro mide 190 px de ancho
    # (mantiene su borde derecho; con tiempo excedido la letra baja de 18 a 14) y el título es de 16.
    ctl('imgLogoAreaReunion', 'Image@2.2.3', {'Image': LOGO_AREA, 'ImagePosition': '=ImagePosition.Fit', 'Height': '=44',
                                              'Width': '=44', 'X': '=138', 'Y': '=14'}),
    # Título al lado de la fecha en las 3 pantallas. Ocupa hasta el cronómetro; con el día de la semana («· ddd dd-mm») mide ~250 px en 15.
    # A ~1024 px la caja mide 234 px y el texto completo saldría cortado con «…»: la letra baja a 13 (y a 12 si la caja es aún más
    # angosta) y el día de la semana solo va con 260 px o más.
    label('lblTituloReunion', '="RD Minera Demo · " & Text(Today(), If(Self.Width >= 260, "ddd dd-mm", "dd-mm"), "es-ES")', 190, 6,
          'btnCronoTotal.X - 198', 44, size='If(Self.Width >= 300, 15, Self.Width >= 226, 13, 12)',
          color='RGBA(255, 255, 255, 1)', bold=True, nowrap=True),
    label('lblPrepInfo',
          '=With({f: fxPrepFila}, If(IsBlank(f), "Sin preparación guardada", "Preparación guardada " & IfError(Text(DateTimeValue(f.Actualizado), "dd-mm hh:mm"), f.Actualizado)))',
          190, 46, 242, 20, size=11, color='RGBA(200, 211, 227, 1)', nowrap=True),
    # Indicadores de tiempo: se ponen en rojo al pasarse, pero nunca cierran la reunión.
    button('btnCronoTotal', '''=With(
    {s: DateDiff(varInicio, varAhora, TimeUnit.Seconds), m: nMinutosMeta * 60},
    RoundDown(s / 60, 0) & ":" & Text(Mod(s, 60), "00") & " / " & nMinutosMeta & ":00" &
    If(s > m, " +" & RoundDown((s - m) / 60, 0) & ":" & Text(Mod(s - m, 60), "00"), "")
)''', 'Min(Max((Parent.Width - 190) / 2, 460), Parent.Width - 592)', 13, 190, 46, '=false',
           fill='=If(DateDiff(varInicio, varAhora, TimeUnit.Seconds) > nMinutosMeta * 60, colRojo, RGBA(255, 255, 255, 0.14))',
           size='If(Len(Self.Text) > 13, 14, 18)', radius=23, extra={'DisplayMode': '=DisplayMode.View'}),
    button('btnCronoBloque', '''=If(
    varBloque = 0,
    "Agenda de la reunión",
    With(
        {r: LookUp(tblBloques, N = varBloque).Min * 60 - DateDiff(varBloqueInicio, varAhora, TimeUnit.Seconds)},
        LookUp(tblBloques, N = varBloque).Bloque & ": " &
        If(r >= 0, "quedan " & RoundDown(r / 60, 0) & ":" & Text(Mod(r, 60), "00"), "excedido " & RoundDown(-r / 60, 0) & ":" & Text(Mod(-r, 60), "00"))
    )
)''', 'Parent.Width - 394', 13, 224, 46, '=false',
           fill='=If(varBloque > 0 && DateDiff(varBloqueInicio, varAhora, TimeUnit.Seconds) > LookUp(tblBloques, N = varBloque).Min * 60, colRojo, RGBA(255, 255, 255, 0.14))',
           size=12, radius=23, bold=False, extra={'DisplayMode': '=DisplayMode.View', 'FontWeight': '=FontWeight.Semibold'}),
    # «Finalizar» es lo único que cierra la reunión semanal: abre la asistencia y ahí «Cerrar y enviar minuta». Para salir sin cerrar
    # está «← Salir sin cerrar» en el menú de la izquierda. «Finalizar reunión» no cabía en 150 px (se partía en dos líneas); en el Cierre sí va completo.
    button('btnCerrarReunion', 'Finalizar', 'Parent.Width - 162', 12, 150, 48,
           '=' + ARMAR_ASIS + ';\nSet(varVerAsistencia, true)',
           fill='colAmbar'),
])

# ---------- menú de bloques con indicador de tiempo ----------
# El chip de tiempo cabe hasta "100:00/20'" (88 px) y el menú mide 266 px, sin barra de desplazamiento (alto justo para las 6 filas;
# la barra le quitaría 13 px a cada fila). "2. Compromisos" en semibold 13 mide ~144 px: con el chip en 92 px quedaba pegado.
# Para no achicar las páginas, el menú va en X 10 y las páginas en X 284 (8 px de separación), con el ancho Parent.Width - 296.
NAV_X, NAV_W = 10, 266
CONT_X = NAV_X + NAV_W + 8
TW = 'Parent.TemplateWidth'
TH = 'Parent.TemplateHeight'
SEG_BLOQUE = 'LookUp(fxTiemposBloques, N = ThisItem.N).Seg'
ONSEL_BLOQUE = '''=If(
    varBloque <> ThisItem.N,
    Collect(colTiempos, {Bloque: varBloque, Seg: DateDiff(varBloqueInicio, Now(), TimeUnit.Seconds)});
    Set(varBloque, ThisItem.N);
    Set(varBloqueInicio, Now())
)'''
# La página 0 (Agenda) no tiene tiempo propio: su chip solo muestra lo transcurrido y nunca se pone rojo.
CHIP_TXT_BLOQUE = ('=With({u: %s}, If(ThisItem.Min = 0, RoundDown(u / 60, 0) & ":" & Text(Mod(u, 60), "00"), '
                   'If(u = 0 && varBloque <> ThisItem.N, ThisItem.Min & "\'", '
                   'RoundDown(u / 60, 0) & ":" & Text(Mod(u, 60), "00") & "/" & ThisItem.Min & "\'")))' % SEG_BLOQUE)
CHIP_FILL_BLOQUE = ('=If(ThisItem.Min > 0 && %s > ThisItem.Min * 60, colRojo, varBloque = ThisItem.N, RGBA(255, 255, 255, 1), colPrimarioClaro)'
                    % SEG_BLOQUE)
CHIP_COLOR_BLOQUE = '=If(ThisItem.Min > 0 && %s > ThisItem.Min * 60, RGBA(255, 255, 255, 1), colPrimario)' % SEG_BLOQUE

TIMER_STEPPER = ''.join('\n'.join(f(6)) + '\n' for f in (
    ctl('tmrReunion', 'Timer@2.1.0', {'AutoStart': '=true', 'Duration': '=1000', 'OnTimerEnd': '=Set(varAhora, Now())',
                                      'Repeat': '=true', 'Visible': '=false'}),
    # Alto justo para las filas del menú: Agenda + los bloques de tblBloques.
    gallery('galBloques', '=tblPaginasVisor', NAV_X, 88, NAV_W, 'CountRows(tblPaginasVisor) * 64 + 6', 58, [
        button('btnBloque', '=If(ThisItem.N = 0, ThisItem.Bloque, ThisItem.N & ". " & ThisItem.Bloque)', 0, 0, f'{TW} - 6', f'{TH} - 6', ONSEL_BLOQUE,
               fill='''=If(
    varBloque = ThisItem.N,
    colPrimario,
    ThisItem.N in colTiempos.Bloque,
    colPrimarioClaro,
    RGBA(255, 255, 255, 1)
)''', color='=If(varBloque = ThisItem.N, RGBA(255, 255, 255, 1), colPrimario)', size=13, bold=False,
               border='colPrimario', extra={'Align': '=Align.Left', 'FontWeight': '=FontWeight.Semibold',
                                            'PaddingLeft': '=12'}),
        button('btnBloqueTiempo', CHIP_TXT_BLOQUE, f'{TW} - 6 - 94', f'({TH} - 6 - 26) / 2', 88, 26, ONSEL_BLOQUE,
               fill=CHIP_FILL_BLOQUE, color=CHIP_COLOR_BLOQUE, size=11, radius=13),
    ], padding=6, extra={'ShowScrollbar': '=false'}),
    button('btnSiguienteBloque', '="Siguiente ▶"', NAV_X, 'galBloques.Y + galBloques.Height + 10', NAV_W - 6, 56, '''=Collect(colTiempos, {Bloque: varBloque, Seg: DateDiff(varBloqueInicio, Now(), TimeUnit.Seconds)});
Set(varBloque, varBloque + 1);
Set(varBloqueInicio, Now())''', size=16, extra={'DisplayMode': '=If(varBloque < CountRows(tblBloques), DisplayMode.Edit, DisplayMode.Disabled)'}),
    # Salir del visor sin cerrar la reunión (pide confirmación; ver confirmar_salir).
    button('btnSalirSinCerrar', '="← Salir sin cerrar"', NAV_X, 'btnSiguienteBloque.Y + btnSiguienteBloque.Height + 10',
           NAV_W - 6, 44, '=Set(varConfSalir, true)', fill='RGBA(255, 255, 255, 1)', color='colPrimario',
           border='colPrimario', size=14, bold=False),
))

# ---------- página 1: Agenda (modelo de agenda) ----------
W = 'Parent.Width'
BW = '(Parent.Width - 64) / 3'          # ancho de cada recuadro superior
COL = '(Parent.Width - 40)'             # ancho útil de la tabla

PUNTOS = '''=Switch(
    ThisItem.N,
    1,
    // Cuántos avisos hay y el más grave. La fila mide 44 px: caben 2 líneas de 11 px.
    // El tope sale del ancho de la etiqueta (~7,2 px por carácter, en dos líneas): a 1024 px son ~100 caracteres y en
    // pantallas más anchas casi todo el aviso.
    With(
        {n: CountRows(fxAvisos), c: CountRows(Filter(fxAvisos, Nivel = "Crítico"))},
        If(
            n = 0,
            "Aún no hay avisos de seguridad cargados en el editor.",
            With(
                {
                    p: n & If(n = 1, " aviso", " avisos") & If(c > 0, " (✖ " & c & If(c = 1, " crítico", " críticos") & ")", "") & ": ",
                    t: First(Sort(fxAvisos, Rango * 1000 + Orden)).Texto,
                    tope: Max(40, Int((Self.Width - 10) / 7.2) * 2 - 8)
                },
                p & If(Len(p) + Len(t) > tope, Left(t, Max(0, tope - 3 - Len(p))) & "…", t)
            )
        )
    ),
    2,
    ''' + cuenta('CountRows(fxRevision) + CountRows(colNuevosPrep)', 'abierto', 'abiertos') + ''' & " · " &
    ''' + cuenta('CountRows(Filter(fxRevision, EstadoNuevo = "Cumplido"))', 'cumplido', 'cumplidos') + ''' & " · " &
    ''' + cuenta('CountRows(Filter(fxRevision, EstadoNuevo = "Atrasado"))', 'atrasado', 'atrasados') + ''',
    3,
    // La página 3 es el informe OEE de Power BI.
    "OEE de transporte (CAEX): del plan al real por palanca; se revisa el detalle de lo que quedó bajo plan.",
    4,
    "Compromisos nuevos con responsable y fecha límite. Cierre de la reunión.",
    ""
)'''


DECISIONES = '''=With(
    {nAtr: CountRows(Filter(fxRevision, EstadoNuevo = "Atrasado"))},
    // A 1024 px el recuadro deja ~26 caracteres por línea: quedan hasta dos puntos.
    If(nAtr > 0, "• Acciones para " & nAtr & If(nAtr = 1, " compromiso atrasado.", " compromisos atrasados.") & Char(10), "") &
    "• Acordar compromisos nuevos."
)'''

# Los indicadores son el informe OEE (página 3), que la app no lee: el recuadro dice qué se revisa.
INDICADORES_BOX = '''="• OEE de transporte (CAEX), del plan al real" & Char(10) &
"• Foco en las palancas bajo plan" & Char(10) &
"• Periodos hasta ayer; el lunes, la semana completa"'''


def caja(prefijo, titulo, cuerpo, indice):
    x = f'=20 + {indice} * ((Parent.Width - 64) / 3 + 12)'
    return [
        rect(f'rec{prefijo}Cab', 'colPrimario', x[1:], '62', BW, '24'),
        label(f'lbl{prefijo}Cab', f'="{titulo}"', x[1:], '62', BW, '24', size=13, color='RGBA(255, 255, 255, 1)',
              bold=True, align='Center'),
        # El tamaño va en puntos: una línea de 11 mide ~17,5 px en pantalla. 114 px con 3 px arriba y abajo alcanzan
        # para 6 líneas, lo que usan Asistentes con un nombre largo y Decisiones con sus tres puntos a 1024 px.
        label(f'lbl{prefijo}Cuerpo', cuerpo, x[1:], '86', BW, '114', size=11, color='colTexto',
              fill='RGBA(240, 243, 249, 1)', valign='Top', pad=10, padv=3),
    ]


agenda_hijos = [
    label('lblAgTitulo', '="Estandar"', 20, 4, 300, 50, size=32, color='colPrimario', bold=True),
    rect('recAgChip', 'colPrimario', 'Parent.Width - 300', '8', '280', '26'),
    label('lblAgChip', '="Semanal (" & nMinutosMeta & " min)"', 'Parent.Width - 300', 8, 280, 26, size=13,
          color='RGBA(255, 255, 255, 1)', bold=True, align='Center'),
    # La fecha es la de hoy; la reunión es los lunes (nDiaReunion en App.Formulas).
    label('lblAgFecha', '=Text(Today(), "dddd dd-mm", "es-ES") & " · inicio de turno"', 'Parent.Width - 300', 34,
          280, 22, size=11, color='colPrimario', align='Center', fill='colPrimarioClaro'),
]
agenda_hijos += caja('AgAsist', 'Asistentes',
                     '="Líder · " & User().FullName & Char(10) & "Convocados · " & If(IsEmpty(Filter(colAsis, Tipo = "Convocado")), "supervisores de turno", With({n: CountRows(Filter(colAsis, Tipo = "Convocado"))}, n & If(n = 1, " supervisor", " supervisores"))) & If(IsBlank(fxPrepFila), "", Char(10) & "Preparó · " & fxPrepFila.Autor)', 0)
agenda_hijos += caja('AgDec', 'Decisiones a tomar', DECISIONES, 1)
agenda_hijos += caja('AgInd', 'Indicadores', INDICADORES_BOX, 2)
agenda_hijos += [
    rect('recAgBarra', 'colAzul', '20', '204', COL, '24'),
    label('lblAgBarra', '="Agenda"', 20, 204, COL, 24, size=14, color='RGBA(255, 255, 255, 1)', bold=True,
          align='Center'),
]
# Columnas de la tabla (fracciones del ancho): Sección 25 %, Puntos 61 %, Tiempo 14 %.
# Con 1024 px de pantalla caben "Compromisos" y "6:25 / 20'" en una línea.
C_SEC, C_PUN, C_TIE = 0.25, 0.61, 0.14
X_TIE = round(C_SEC + C_PUN, 2)
cols = [('lblAgHSeccion', 'Sección', '0', str(C_SEC), None),
        ('lblAgHPuntos', 'Puntos de discusión', str(C_SEC), str(C_PUN), None),
        ('lblAgHTiempo', 'Tiempo', str(X_TIE), str(C_TIE), 'Center')]
for nom, txt, fx, fw, al in cols:
    agenda_hijos.append(label(nom, f'="{txt}"', f'20 + {COL} * {fx}', 228, f'{COL} * {fw}', 22, size=11,
                              color='colPrimario', bold=True, align=al, fill='colPrimarioClaro',
                              pad=8 if al is None else None, nowrap=True))

TW = 'Parent.TemplateWidth'
TH = 'Parent.TemplateHeight'
# La tabla muestra 5 filas: con una ventana de 640 px de alto cada fila mide 44 px (2 líneas de 11) y caben las cinco;
# más baja, la galería se desplaza.
agenda_hijos.append(gallery('galAgenda', '=tblBloques', 20, 250, COL, 'Parent.Height - 314', 'Max(44, (Parent.Height - 314) / 5)', [
    rect('recAgFila', '=If(varBloque = ThisItem.N, RGBA(255, 243, 224, 1), RGBA(255, 255, 255, 1))', '0', '0', TW, TH),
    rect('recAgLinea', 'RGBA(225, 230, 232, 1)', '0', f'{TH} - 1', TW, '1'),
    rect('recAgNum', 'colPrimario', '6', f'({TH} - 30) / 2', '30', '30'),
    label('lblAgNum', '=Text(ThisItem.N)', 6, f'({TH} - 30) / 2', 30, 30, size=15, color='RGBA(255, 255, 255, 1)',
          bold=True, align='Center'),
    label('lblAgSeccion', '=ThisItem.Bloque', 42, 0, f'{TW} * {C_SEC} - 42', TH, size=12, color='colPrimario', bold=True,
          nowrap=True),
    label('lblAgPuntos', PUNTOS, f'{TW} * {C_SEC}', 0, f'{TW} * {C_PUN} - 8', TH, size=11, color='colTexto', padv=2),
    # Tiempo por sección: indicador que se pone rojo al pasarse (nunca cierra la reunión).
    button('btnAgTiempo',
           '=With({u: %s}, If(u = 0 && varBloque <> ThisItem.N, ThisItem.Min & " min", RoundDown(u / 60, 0) & ":" & Text(Mod(u, 60), "00") & " / " & ThisItem.Min & "\'"))' % SEG_BLOQUE,
           f'{TW} * {X_TIE} + 4', f'({TH} - 30) / 2', f'{TW} * {C_TIE} - 8', 30, '=false',
           fill='=If(%s > ThisItem.Min * 60, colRojo, RGBA(255, 236, 204, 1))' % SEG_BLOQUE,
           color='=If(%s > ThisItem.Min * 60, RGBA(255, 255, 255, 1), colPrimario)' % SEG_BLOQUE,
           size=11, radius=6, extra={'DisplayMode': '=DisplayMode.View'}),
]))
# Pie: solo la franja con el logo.
agenda_hijos.append(rect('recAgPie', 'colPrimario', '20', 'Parent.Height - 58', COL, '50'))
agenda_hijos.append(ctl('imgAgLogo', 'Image@2.2.3', {'Image': LOGO, 'ImagePosition': '=ImagePosition.Fit',
                                                     'Height': '=40', 'Width': '=100', 'X': '=Parent.Width - 130',
                                                     'Y': '=Parent.Height - 53'}))

pagina0 = container('conB0Agenda', {'Height': '=Parent.Height - 104', 'Visible': '=varBloque = 0',
                                    'Width': '=Parent.Width - 296', 'X': f'={CONT_X}', 'Y': '=88'}, agenda_hijos)

# ---------- página 1: Seguridad (página propia, entre la Agenda y Compromisos) ----------
# Arriba los recuadros con los indicadores de seguridad (escritos a mano en el editor, tres a todo el ancho) y abajo los
# avisos con su nivel, del más grave al más leve. «Hipo Hazard» se compara contra la meta (sufijo y campos Rep / RepMeta,
# clave rep / repm del JSON).
GRIS_VACIO = 'RGBA(200, 205, 208, 1)'
# (sufijo, valor grande, texto bajo el valor, color de la barra y del estado, texto del estado)
TARJETAS_SEG = (
    ('Inc', 'If(IsBlank(fxIndSeg.Inc), "—", Text(fxIndSeg.Inc))', 'incidentes de la semana',
     f'With({{v: fxIndSeg.Inc, a: fxIndSeg.IncAnt}}, If(IsBlank(v), {GRIS_VACIO}, v = 0 || (!IsBlank(a) && v < a), colVerde, colAmbar))',
     '''With(
    {v: fxIndSeg.Inc, a: fxIndSeg.IncAnt},
    If(
        IsBlank(v), "sin dato",
        v = 0, "✔ sin incidentes",
        IsBlank(a), "⚠ revisar causas",
        v > a, "⚠ +" & (v - a) & " vs. anterior",
        v < a, "✔ " & (v - a) & " vs. anterior",
        "⚠ igual a anterior"
    )
)'''),
    ('Rep', 'If(IsBlank(fxIndSeg.Rep), "—", Text(fxIndSeg.Rep))', 'Hipo Hazard',
     f'With({{v: fxIndSeg.Rep, m: fxIndSeg.RepMeta}}, If(IsBlank(v), {GRIS_VACIO}, IsBlank(m), colPrimario, v >= m, colVerde, colAmbar))',
     'With({v: fxIndSeg.Rep, m: fxIndSeg.RepMeta}, If(IsBlank(v), "sin dato", IsBlank(m), "", v >= m, "✔ meta " & m, "⚠ meta " & m & ", faltan " & (m - v)))'),
    ('Ins', 'With({r: fxIndSeg.InsReal, p: fxIndSeg.InsPlan}, If(IsBlank(r), "—", IsBlank(p), Text(r), r & "/" & p))',
     'inspecciones hechas / planificadas',
     f'With({{r: fxIndSeg.InsReal, p: fxIndSeg.InsPlan}}, If(IsBlank(r), {GRIS_VACIO}, IsBlank(p), colPrimario, r >= p, colVerde, colRojo))',
     'With({r: fxIndSeg.InsReal, p: fxIndSeg.InsPlan}, If(IsBlank(r), "sin dato", IsBlank(p), "", r >= p, "✔ completas", "✖ faltan " & (p - r)))'),
)
CW = '(Parent.Width - 48 - 24) / 3'   # ~219 px por recuadro a 1024 px (tres recuadros, 12 px entre ellos)
seg_hijos = [
    label('lblB1Titulo', '="Seguridad"', 24, 12, 'Parent.Width - 48', 48, size=28, color='colPrimario', bold=True),
    label('lblB1Sub', '="Indicadores y avisos de seguridad de la semana"', 24, 62, 'Parent.Width - 48', 26, size=14,
          color='RGBA(90, 98, 104, 1)'),
]
for i, (suf, valor, texto, color, estado) in enumerate(TARJETAS_SEG):
    x = f'24 + {i} * ({CW} + 12)'
    seg_hijos += [
        rect(f'recB1{suf}', 'RGBA(244, 246, 251, 1)', x, '96', CW, '118'),
        rect(f'recB1{suf}Barra', '=' + color, x, '96', CW, '5'),
        label(f'lblB1{suf}Valor', '=' + valor, x, 104, CW, 42, size=28, color='colPrimario', bold=True, pad=10,
              padv=0, nowrap=True),
        label(f'lblB1{suf}Texto', f'="{texto}"', x, 146, CW, 36, size=11, color='RGBA(90, 98, 104, 1)', valign='Top',
              pad=10, padv=0),
        label(f'lblB1{suf}Estado', '=' + estado, x, 184, CW, 24, size=11, color='=' + color, semibold=True, pad=10,
              padv=0, nowrap=True),
    ]
CONTEO_AVISOS = '''=With(
    {
        c: CountRows(Filter(fxAvisos, Nivel = "Crítico")),
        p: CountRows(Filter(fxAvisos, Nivel = "Precaución")),
        r: CountRows(Filter(fxAvisos, Nivel = "Recordar")),
        o: CountRows(Filter(fxAvisos, Rango = 4))
    },
    Mid(
        If(c > 0, " · ✖ " & c & If(c = 1, " crítico", " críticos"), "") &
        If(p > 0, " · ⚠ " & p & If(p = 1, " precaución", " precauciones"), "") &
        If(r > 0, " · ✔ " & r & If(r = 1, " recordatorio", " recordatorios"), "") &
        If(o > 0, " · " & o & If(o = 1, " aviso", " avisos"), ""),
        4
    )
)'''
# Cada aviso: etiqueta del nivel y el texto. La fila se reparte el alto disponible (máx. 96 px, mín. 64 px; con más
# avisos la lista se desplaza). Un texto de 3 líneas de 17 cabe en 96 px.
TPL_AVISO = 'Max(64, Min(96, (Parent.Height - 266) / Max(1, CountRows(fxAvisos))))'
seg_hijos += [
    label('lblB1Avisos', '="Avisos"', 24, 224, 120, 28, size=15, color='colPrimario', bold=True),
    label('lblB1Conteo', CONTEO_AVISOS, 144, 224, 'Parent.Width - 168', 28, size=12, color='RGBA(90, 98, 104, 1)',
          semibold=True, align='Right', nowrap=True),
    rect('recB1Linea', 'colAzul', '24', '254', 'Parent.Width - 48', '2'),
    label('lblB1SinAvisos', '="Aún no hay avisos de seguridad cargados para esta reunión. Se escriben en el editor."',
          24, 264, 'Parent.Width - 48', 60, size=16, color='RGBA(130, 138, 142, 1)', visible='=IsEmpty(fxAvisos)'),
    gallery('galB1Avisos', '=Sort(fxAvisos, Rango * 1000 + Orden)', 24, 258, 'Parent.Width - 48', 'Parent.Height - 266',
            TPL_AVISO, [
        button('btnB1Nivel', '=Switch(ThisItem.Nivel, "Crítico", "✖ CRÍTICO", "Precaución", "⚠ PRECAUCIÓN", "Recordar", "✔ RECORDAR", "AVISO")',
               0, '(Parent.TemplateHeight - 40) / 2', 150, 40, '=false',
               fill='=Switch(ThisItem.Nivel, "Crítico", colRojo, "Precaución", colAmbar, "Recordar", colVerde, colPrimario)',
               size=12, radius=20, extra={'DisplayMode': '=DisplayMode.View'}),
        label('lblB1AvisoTexto', '=ThisItem.Texto', 166, 0, 'Parent.TemplateWidth - 166', 'Parent.TemplateHeight', size=17,
              color='colTexto', padv=4),
        rect('recB1AvisoSep', 'RGBA(225, 230, 232, 1)', '0', 'Parent.TemplateHeight - 1', 'Parent.TemplateWidth', '1'),
    ]),
]
pagina1 = container('conB1Seguridad', {'Height': '=Parent.Height - 104', 'Visible': '=varBloque = 1',
                                       'Width': '=Parent.Width - 296', 'X': f'={CONT_X}', 'Y': '=88'}, seg_hijos)

# ---------- página 2: compromisos (solo lectura) ----------
# El editor exige marcar el estado de todos. Si alguno llega sin marcar (por ejemplo, no se preparó la reunión), se muestra
# su último estado registrado; "Abierto" (recién creado) se lee como En progreso.
CHIP_FILL = '''=Switch(
    ThisItem.EstadoNuevo,
    "Cumplido",
    colVerde,
    "Atrasado",
    colAmbar,
    colPrimario
)'''
CHIP_TXT = '''=Switch(ThisItem.EstadoNuevo, "Cumplido", "✔ Cumplido", "Atrasado", "⚠ Atrasado", "En progreso")'''
# Los compromisos de esta semana preparados en el editor (clave «nue»; colNuevosPrep, copia hecha al empezar la reunión) también
# salen en esta página, con estado En progreso, junto a los de la semana pasada. Van con la misma forma que fxRevision
# (ID 0: no tienen ID en el Excel hasta que se suben al cerrar la reunión).
N_PREP = 'CountRows(colNuevosPrep)'
COMP_SEMANA = '''Ungroup(
    Table(
        {Filas: fxRevision},
        {
            Filas: ForAll(
                colNuevosPrep As n,
                {ID: 0, Titulo: n.Titulo, ResponsableNombre: n.Responsable, FechaLimite: n.FechaLimite, FechaCreacion: Today(), EstadoAnterior: "En progreso", EstadoNuevo: "En progreso", Revisado: true, Comentario: "", Url: ""}
            )
        }
    ),
    Filas
)'''
RESUMEN2 = ('=' + cuenta(f'CountRows(fxRevision) + {N_PREP}', 'abierto', 'abiertos') + ' & " · ✔ " & ' +
            cuenta('CountRows(Filter(fxRevision, EstadoNuevo = "Cumplido"))', 'cumplido', 'cumplidos') + ' & " · ⚠ " & ' +
            cuenta('CountRows(Filter(fxRevision, EstadoNuevo = "Atrasado"))', 'atrasado', 'atrasados') + ' & " · " & ' +
            f'(CountRows(Filter(fxRevision, !(EstadoNuevo in ["Cumplido", "Atrasado"]))) + {N_PREP}) & " en progreso" & '
            f'If({N_PREP} = 0, "", " (" & ' + cuenta(N_PREP, 'nuevo de esta semana', 'nuevos de esta semana') + ' & ")")')

# ---------- visor de evidencias: «Ver evidencia» en cada compromiso con evidencia ----------
# Una foto se muestra en grande sobre la presentación: si este equipo la tiene (se preparó aquí) sale de colEvid; si no,
# de SharePoint. Un PDF, Excel, Word u otro archivo se abre en una pestaña nueva del navegador (Launch).
IMGS = '["jpg", "jpeg", "png", "gif", "bmp", "webp", "heic"]'


def ext(x):
    return f'Lower(Last(Split({x}, ".")).Value)'


HAY_EVID = '!IsBlank(ThisItem.Url) || ThisItem.ID in colEvid.CompromisoId'
VER_EVID = f'''=With(
    {{loc: LookUp(colEvid, CompromisoId = ThisItem.ID), u: ThisItem.Url}},
    If(
        If(IsBlank(loc), {ext("u")} in {IMGS}, IsBlank(loc.Nombre) || {ext("loc.Nombre")} in {IMGS}),
        Set(varEvidVerId, ThisItem.ID),
        !IsBlank(u),
        Launch(u),
        Notify("Este archivo todavía no se sube a SharePoint: se puede abrir en el equipo donde se preparó.", NotificationType.Information)
    )
)'''
EVID_LOC = 'LookUp(colEvid, CompromisoId = varEvidVerId)'
EVID_REV = 'LookUp(fxRevision, ID = varEvidVerId)'
ver_tarjeta = container('conVerEvidTarjeta', {
    'DropShadow': '=DropShadow.Bold', 'Height': '=Parent.Height - 48', 'Width': '=Min(Parent.Width - 48, 960)',
    'X': '=(Parent.Width - Self.Width) / 2', 'Y': '=24'}, [
    label('lblVerEvidTitulo', f'="✔ " & {EVID_REV}.Titulo', 24, 12, 'Parent.Width - 48 - 56', 56, size=18,
          color='colVerde', bold=True, valign='Top', padv=2),
    ctl('icoVerEvidCerrar', 'Classic/Icon@2.5.0', {
        'Icon': '=Icon.Cancel', 'Color': '=RGBA(90, 98, 104, 1)', 'Width': '=44', 'Height': '=44',
        'X': '=Parent.Width - 24 - 44', 'Y': '=12', 'PaddingLeft': '=10', 'PaddingRight': '=10',
        'PaddingTop': '=10', 'PaddingBottom': '=10', 'Tooltip': '="Volver a la reunión"',
        'AccessibleLabel': '="Cerrar la evidencia"', 'OnSelect': '=Set(varEvidVerId, 0)'}),
    label('lblVerEvidComentario', f'=If(IsBlank({EVID_REV}.Comentario), "", "Comentario: " & {EVID_REV}.Comentario)',
          24, 70, 'Parent.Width - 48', 44, size=13, color='colTexto', valign='Top', padv=2),
    # Foto de este equipo (preparada aquí, aunque no se haya subido) o de SharePoint.
    ctl('imgVerEvidLocal', 'Image@2.2.3', {
        'Image': f'={EVID_LOC}.Foto', 'ImagePosition': '=ImagePosition.Fit', 'Visible': f'=!IsBlank({EVID_LOC})',
        'Width': '=Parent.Width - 48', 'Height': '=Parent.Height - 120 - 76', 'X': '=24', 'Y': '=120'}),
    ctl('imgVerEvidNube', 'Image@2.2.3', {
        'Image': f'={EVID_REV}.Url', 'ImagePosition': '=ImagePosition.Fit',
        'Visible': f'=IsBlank({EVID_LOC})',
        'Width': '=Parent.Width - 48', 'Height': '=Parent.Height - 120 - 76', 'X': '=24', 'Y': '=120'}),
    rect('sepVerEvid', 'RGBA(225, 230, 232, 1)', '0', 'Parent.Height - 72', 'Parent.Width', '1'),
    button('btnVerEvidAbrir', 'Abrir en el navegador', 24, 'Parent.Height - 60', 240, 48, f'=Launch({EVID_REV}.Url)',
           fill='RGBA(255, 255, 255, 1)', color='colPrimario', border='colPrimario', bold=False, size=14,
           extra={'Visible': f'=!IsBlank({EVID_REV}.Url)'}),
    button('btnVerEvidVolver', 'Volver a la reunión', 'Parent.Width - 24 - 220', 'Parent.Height - 60', 220, 48,
           '=Set(varEvidVerId, 0)', size=15),
])
ventana_evidencia = container('conVerEvid', {
    'Fill': '=RGBA(0, 0, 0, 0.6)', 'Height': '=Parent.Height', 'Visible': '=varEvidVerId <> 0', 'Width': '=Parent.Width',
    'X': '=0', 'Y': '=0', 'RadiusBottomLeft': '=0', 'RadiusBottomRight': '=0', 'RadiusTopLeft': '=0',
    'RadiusTopRight': '=0'}, [ver_tarjeta])

# Filtro por estado, para que con muchos compromisos la vista no se sobrecargue. Sin filtro (varFiltroEstado en blanco) van todos,
# ordenados Cumplido, En progreso y Atrasado, y dentro de cada uno por vencimiento. «Abierto» (recién creado) o sin marcar
# cuenta como En progreso, igual que la píldora.
ESTADO_GRUPO = 'Switch(EstadoNuevo, "Cumplido", "Cumplido", "Atrasado", "Atrasado", "En progreso")'
# Con fxRevision vacío, Ungroup deja una fila en blanco (saldría «VENCIDO» sin título): se filtra por Titulo.
REV_ITEMS = (f'=Sort(Filter({COMP_SEMANA}, !IsBlank(Titulo) && (IsBlank(varFiltroEstado) || {ESTADO_GRUPO} = varFiltroEstado)), '
             'Switch(EstadoNuevo, "Cumplido", 1, "Atrasado", 3, 2) * 100000 + DateDiff(Date(2020, 1, 1), FechaLimite))')
FILTROS_B2 = [('', 'Todos', 'colPrimario'), ('Cumplido', '✔ Cumplido', 'colVerde'),
              ('En progreso', 'En progreso', 'colPrimario'), ('Atrasado', '⚠ Atrasado', 'colAmbar')]


def filtro_b2(i, valor, texto, color):
    n = f'CountRows(fxRevision) + {N_PREP}' if not valor else f'CountRows(Filter(fxRevision, {ESTADO_GRUPO} = "{valor}"))'
    if valor == 'En progreso':
        n += f' + {N_PREP}'
    sel = 'IsBlank(varFiltroEstado)' if not valor else f'varFiltroEstado = "{valor}"'
    return button(f'btnFiltroB2_{i}', f'="{texto} (" & {n} & ")"', f'20 + {i} * 158', 98, 150, 34,
                  f'=Set(varFiltroEstado, "{valor}")', fill=f'=If({sel}, {color}, RGBA(255, 255, 255, 1))',
                  color=f'=If({sel}, RGBA(255, 255, 255, 1), {color})', border=color, size=12, bold=False, radius=17)


# Columnas: cada compromiso se lee en este orden, de izquierda a derecha: Compromiso (el texto), Responsable, Fecha límite y Estado.
# Todo se calcula desde el ancho de la plantilla w. Estado (chip de 140 px) y Fecha (96 px, con «VENCIDO» abajo) tienen
# ancho fijo; Responsable crece con la pantalla (entre 116 y 180 px) y Compromiso toma el resto: ~309 px a 1024 px de
# pantalla y ~600 px a 1366. La evidencia va en una franja al pie de la fila, bajo las tres primeras columnas.
# El encabezado usa galRevision.TemplateWidth (no Parent.Width) para quedar alineado aunque aparezca la barra de
# desplazamiento, que le quita ancho a la plantilla.
def cols_b2(w):
    r_w = f'Min(180, Max(116, {w} * 0.18))'
    return {'e_x': f'{w} - 152', 'f_x': f'{w} - 248', 'r_x': f'{w} - 248 - {r_w}', 'r_w': f'{r_w} - 8',
            'c_w': f'{w} - 248 - {r_w} - 20'}


CT = cols_b2(TW)
CG = cols_b2('galRevision.TemplateWidth')
CAB_Y = 140
CAB_B2 = [
    rect('recRevCab', 'colPrimarioClaro', 'galRevision.X', str(CAB_Y), 'galRevision.Width', '24'),
    label('lblRevCabComp', '="Compromiso"', 'galRevision.X + 12', CAB_Y, CG['c_w'], 24, size=11, color='colPrimario',
          bold=True, nowrap=True),
    label('lblRevCabResp', '="Responsable"', f'galRevision.X + {CG["r_x"]}', CAB_Y, CG['r_w'], 24, size=11,
          color='colPrimario', bold=True, nowrap=True),
    label('lblRevCabFecha', '="Fecha límite"', f'galRevision.X + {CG["f_x"]}', CAB_Y, 96, 24, size=11,
          color='colPrimario', bold=True, nowrap=True),
    label('lblRevCabEstado', '="Estado"', f'galRevision.X + {CG["e_x"]}', CAB_Y, 140, 24, size=11, color='colPrimario',
          bold=True, align='Center', nowrap=True),
]
VENCIDO = 'ThisItem.FechaLimite < Today()'

pagina2 = container('conB2Compromisos', {'Height': '=Parent.Height - 104', 'Visible': '=varBloque = 2',
                                         'Width': '=Parent.Width - 296', 'X': f'={CONT_X}', 'Y': '=88'}, [
    label('lblB2Titulo', '="Compromisos de la semana"', 20, 10, 'Parent.Width - 40', 44, size=26,
          color='colTexto', bold=True),
    # Resumen en hasta dos líneas (12 px) y lista desde Y = 100: así no se pisan aunque la frase se parta.
    label('lblB2Resumen', RESUMEN2, 20, 52, 'Parent.Width - 40', 44, size=12, color='RGBA(90, 98, 104, 1)', valign='Top'),
    *[filtro_b2(i, *f) for i, f in enumerate(FILTROS_B2)],
    *CAB_B2,
    gallery('galRevision', REV_ITEMS, 12, CAB_Y + 26, 'Parent.Width - 24', f'Parent.Height - {CAB_Y + 26 + 12}', 112, [
        # Fila de 112 px: el compromiso hasta en tres líneas y, al pie, la evidencia en una línea. Todo el texto arranca
        # arriba, a la misma altura. La letra es de 14 puntos (~8,7 px por carácter, ~35 por línea a 1024 px); solo baja a
        # 12 si el título no cabría en tres líneas con ese ancho (a 1024 px, desde ~90 caracteres; con pantallas más
        # anchas nunca baja, así que las filas se ven parejas).
        label('lblRevTitulo', '=ThisItem.Titulo', 12, 4, CT['c_w'], f'{TH} - 34',
              size='If(Len(ThisItem.Titulo) > Int((Self.Width - 10) / 8.7) * 2.7, 12, 14)', color='colTexto',
              semibold=True, valign='Top', padv=2),
        label('lblRevResp', '=ThisItem.ResponsableNombre', CT['r_x'], 4, CT['r_w'], f'{TH} - 34', size=13,
              color='colTexto', valign='Top', padv=2),
        label('lblRevFecha', '=Text(ThisItem.FechaLimite, "dd-mm")', CT['f_x'], 4, 88, 30, size=14,
              color=f'=If({VENCIDO}, colRojo, colTexto)', semibold=True, valign='Top', nowrap=True, padv=2),
        label('lblRevVencido', f'=If({VENCIDO}, "VENCIDO", "")', CT['f_x'], 34, 88, 24, size=11, color='colRojo',
              bold=True, valign='Top', nowrap=True, padv=0),
        label('lblRevEvid', '''=If(
    !IsBlank(ThisItem.Comentario),
    "Evidencia: " & ThisItem.Comentario,
    !IsBlank(ThisItem.Url),
    "Con evidencia (archivo)",
    ""
)''', 12, f'{TH} - 30', f'{CT["e_x"]} - 20', 26, size=12, color='colVerde', nowrap=True),
        button('btnRevEstado', CHIP_TXT, CT['e_x'], 10, 140, 38, '=false', fill=CHIP_FILL,
               size=13, radius=19, extra={'DisplayMode': '=DisplayMode.View'}),
        button('btnRevVerEvid', 'Ver evidencia', CT['e_x'], 56, 140, 28, VER_EVID,
               fill='RGBA(255, 255, 255, 1)', color='colVerde', border='colVerde', size=12, bold=False, radius=14,
               extra={'Visible': f'={HAY_EVID}'}),
        rect('sepRevision', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1'),
    ]),
    label('lblB2Vacio', '=If(IsEmpty(fxRevision) && IsEmpty(colNuevosPrep), "No hay compromisos abiertos.", "No hay compromisos con ese estado.")',
          20, CAB_Y + 54, 'Parent.Width - 40', 60, size=16, color='RGBA(90, 98, 104, 1)', align='Center',
          visible='=IsEmpty(galRevision.AllItems)'),
])


# ---------- página 3: indicadores = informe OEE Transporte de Power BI ----------
# La página muestra el informe «OEE Transporte» del PBIP de pbip/ (generado por gen_pbi_oee.py): la cascada del plan al
# real de los CAEX por palanca y la tabla «Datos Transporte». Bajo cada barra, «Ver detalle» abre su tablero dentro del
# mismo informe, ordenado de peor a mejor. El periodo (JUE-DOM, SEMANAL o MENSUAL) se elige en el informe: hasta ayer;
# el lunes, la semana completa, y el primer lunes del mes, el mes anterior.
# Se usa el control Power BI tile con la API nueva (AllowNewAPI): acepta la URL de inserción de un informe y su página.
# Límites (documentación de Microsoft): no funciona en la app móvil de Power Apps, solo en el navegador; cada supervisor
# necesita permiso de lectura sobre el informe; conviene un solo informe cargado a la vez (LoadPowerBIContent).
PBI_TIPO = 'PowerBI@2.4.0'
PBI_TENANT = '00000000-0000-0000-0000-000000000000'    # marcador: id del tenant
# Los ids del tenant, del informe y del área de trabajo son marcadores: reemplazarlos por los del informe publicado
# (la URL de inserción se copia en Studio: Insertar › Gráficos › Icono de Power BI › Copiar).
PBI_OEE = '00000000-0000-0000-0000-000000000001'    # marcador: id del informe publicado
PBI_OEE_AREA = '00000000-0000-0000-0000-000000000002'    # marcador: id del área de trabajo
PBI_OEE_PAGINA = '83b1eaa13fad9412b69e'   # página «OEE Transporte» del informe de pbip/: hid('oee', 'pagina', 'oee') de pbir_lib.py
# En la fórmula el esquema y el host van como textos separados ("https://" & "host/ruta") para no fijar una URL completa en el YAML.
PBI_HOST = 'app.powerbi.com'   # host público del servicio de Power BI
PBI_OEE_URL = (f'https://" & "{PBI_HOST}/reportEmbed?reportId={PBI_OEE}' + (f'&groupId={PBI_OEE_AREA}' if PBI_OEE_AREA else '')
               + f'&autoAuth=true&ctid={PBI_TENANT}&navContentPaneEnabled=false&filterPaneEnabled=false&pageName={PBI_OEE_PAGINA}')

pagina3 = container('conB3Indicadores', {'Height': '=Parent.Height - 104', 'Visible': '=varBloque = 3',
                                         'Width': '=Parent.Width - 296', 'X': f'={CONT_X}', 'Y': '=88'}, [
    label('lblB3Titulo', '="Indicadores · OEE de transporte (CAEX)"', 20, 10, 'Parent.Width - 40', 40, size=20,
          color='colTexto', bold=True, nowrap=True),
    # ~80 caracteres en 12: una línea desde 1024 px (688 px de ancho útil)
    label('lblB3Periodo', '="«Ver detalle» bajo cada barra abre su porqué. El periodo se elige en el informe."', 20, 50,
          'Parent.Width - 40', 26, size=12, color=GRIS_TXT, nowrap=True),
    # Queda detrás del informe: se ve mientras carga o si el informe no se puede mostrar.
    label('lblB3Cargando', '''="Cargando el informe de Power BI…" & Char(10) & Char(10) &
"Si no aparece: el informe se ve en Power Apps desde el navegador (no en la app móvil) y hace falta permiso de lectura sobre el informe en Power BI."''',
          40, 140, 'Parent.Width - 80', 140, size=13, color=GRIS_TXT, align='Center'),
    ctl('pbiOEE', PBI_TIPO, {'AllowNewAPI': '=true', 'Height': '=Parent.Height - 88',
                             'LoadPowerBIContent': '=varBloque = 3', 'PowerBIInteractions': '=true',
                             'TileUrl': f'="{PBI_OEE_URL}"', 'Width': '=Parent.Width - 24', 'X': '=12', 'Y': '=80'}),
])


# ---------- página 5: cierre (compromisos nuevos en vivo, resumen y cierre de la reunión) ----------
LEFT_W = 'Parent.Width * 0.38 - 40'
# Agregar, editar y eliminar (con confirmación) igual que en el Cierre del editor.
FN = formulas_nuevos('')
# El resumen va una cifra por línea (4 líneas de 12 px en una caja de 100 px): así no se corta en la columna angosta.
RESUMEN_CIERRE = '''="Compromisos de la semana: " & (CountRows(fxRevision) + CountRows(colNuevosPrep)) & Char(10) &
"Cumplidos: " & CountRows(Filter(fxRevision, EstadoNuevo = "Cumplido")) & Char(10) &
"Con evidencia: " & CountRows(Filter(fxRevision, !IsBlank(Comentario) || !IsBlank(Url))) & Char(10) &
"Nuevos: " & CountRows(colNuevos)'''
# El Cierre es la página 4; los nombres conB5Cierre y lblB5… se conservan por compatibilidad.
pagina5 = container('conB5Cierre', {'Height': '=Parent.Height - 104', 'Visible': '=varBloque = 4',
                                    'Width': '=Parent.Width - 296', 'X': f'={CONT_X}', 'Y': '=88'}, [
    label('lblB5Titulo', '="Cierre · compromisos para la próxima semana"', 20, 12, 'Parent.Width - 40', 44, size=20,
          color='colTexto', bold=True),
    textinput('txtNuevoQue', FN['def_que'], '="¿Qué se hará?"', 20, 64, LEFT_W, 72, size=14, multiline=True,
              extra={'MaxLength': '=100'}),
    textinput('txtNuevoResp', FN['def_resp'], '="Responsable"', 20, 144, LEFT_W, 48, size=14),
    ctl('dpNuevoFecha', 'Classic/DatePicker@2.6.0', {
        'DefaultDate': FN['def_fecha'], 'Format': '=DateTimeFormat.ShortDate', 'Height': '=48',
        'Size': '=14', 'Width': f'={LEFT_W}', 'X': '=20', 'Y': '=200'}),
    button('btnAgregarCompromiso', FN['texto_agregar'], 20, 260, LEFT_W, 52, FN['agregar'], size=15, extra={
        'DisplayMode': '=If(IsBlank(Trim(txtNuevoQue.Text)) || IsBlank(Trim(txtNuevoResp.Text)), DisplayMode.Disabled, DisplayMode.Edit)'}),
    label('lblNuevosTitulo', '="Compromisos nuevos de esta reunión · " & CountRows(colNuevos)', 'Parent.Width * 0.38 + 8',
          64, 'Parent.Width * 0.62 - 40', 36, size=15, color='colTexto', semibold=True),
    # Cada fila: texto a la izquierda y a la derecha «Editar» y «Eliminar», uno sobre otro. A 1024 px la columna deja
    # ~32 caracteres por línea: 100 caracteres (MaxLength) son 4 líneas más la del responsable = 5 líneas de 13 (108 px).
    gallery('galNuevos', '=colNuevos', 'Parent.Width * 0.38 + 8', 104, 'Parent.Width * 0.62 - 32', 'Parent.Height - 196',
            112, [
        label('lblNuevoItem', '=ThisItem.Titulo & Char(10) & ThisItem.Responsable & " · vence " & Text(ThisItem.FechaLimite, "dd-mm")',
              8, 0, f'{TW} - 108', 108, size=13, color='colTexto', padv=2),
        button('btnEditarNuevo', FN['texto_editar'], f'{TW} - 96', 4, 88, 32, FN['editar'], fill='RGBA(255, 255, 255, 1)',
               color='colPrimario', size=12, bold=False, border='colPrimario'),
        button('btnEliminarNuevo', 'Eliminar', f'{TW} - 96', 40, 88, 32, FN['eliminar'], fill='RGBA(255, 255, 255, 1)',
               color='colRojo', size=12, bold=False, border='colRojo'),
        rect('sepNuevo', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1'),
    ], padding=2, extra={'BorderColor': '=RGBA(230, 230, 230, 1)', 'BorderThickness': '=1',
                         'TemplateFill': FN['fill_fila']}),
    label('lblResumenCierre', RESUMEN_CIERRE, 20, 'Parent.Height - 188', LEFT_W, 100, size=12, color=GRIS_TXT, valign='Top'),
    button('btnCerrarDesdeCierre', 'Finalizar reunión', 20, 'Parent.Height - 80', LEFT_W, 64, '=Select(btnCerrarReunion)',
           fill='colAmbar', size=17),
])

# ---------- ventana de asistencia: se abre con «Finalizar reunión» ----------
# Lista de convocados (RD_Participantes, se carga en «Actualizar datos»): todos parten presentes y se toca a quien no vino.
# Se pueden sumar invitados (nombre y correo opcional). «Cerrar y enviar minuta» cierra la reunión.
# Con la × de cada fila se quita a alguien solo de esta reunión: no queda en la asistencia ni recibe la minuta.
# Los quitados pasan a colAsisQuitados y «Restaurar quitados» los devuelve.
# Para sacarlo de la lista de convocados de todas las reuniones está «Quitar» en Convocados del editor.
# Tarjeta de hasta 960 px: a 1024 x 640 la lista muestra 2 columnas y ~10 personas sin desplazarse.
AS_ITEMS = '=Sort(colAsisVista, Orden)'
ES_PERSONA = '=ThisItem.Fila = "Persona"'
AS_AREA_CONTEO = '''=With(
    {g: Filter(colAsis, Area = ThisItem.Area)},
    If(
        ThisItem.Area = "Invitados",
        CountRows(g) & If(CountRows(g) = 1, " invitado", " invitados"),
        CountRows(Filter(g, Presente)) & " de " & CountRows(g) & If(CountRows(g) = 1, " presente", " presentes")
    )
)'''
AS_SUB = ('="Toca a quien no vino: igual recibe la minuta, con un aviso. Con la × de la derecha lo quitas de esta reunión: '
          'no queda en la asistencia ni le llega la minuta."')
AS_N_CORREOS = ('CountRows(Distinct(Filter(colAsis, !IsBlank(Correo)), Lower(Correo))) + '
                'If(IsBlank(LookUp(colAsis, Lower(Correo) = Lower(User().Email))), 1, 0)')
AS_CONTEO = f'''="Presentes: " & CountRows(Filter(colAsis, Tipo = "Convocado" && Presente)) & " de " & CountRows(Filter(colAsis, Tipo = "Convocado")) &
If(IsEmpty(Filter(colAsis, Tipo = "Invitado")), "", " · invitados: " & CountRows(Filter(colAsis, Tipo = "Invitado"))) & Char(10) &
With({{n: {AS_N_CORREOS}}}, "La minuta va a " & n & If(n = 1, " correo", " correos"))'''
AS_SIN_CONV = 'IsEmpty(Filter(colAsis, Tipo = "Convocado"))'
INV_OK = ('!IsBlank(Trim(txtInvNombre.Text)) && '
          '(IsBlank(Trim(txtInvCorreo.Text)) || IsMatch(Trim(txtInvCorreo.Text), Match.Email))')

as_tarjeta = container('conAsTarjeta', {
    'DropShadow': '=DropShadow.Bold', 'Height': '=Parent.Height - 48', 'Width': '=Min(Parent.Width - 48, 960)',
    'X': '=(Parent.Width - Self.Width) / 2', 'Y': '=24'}, [
    label('lblAsTitulo', '="Asistencia · confirma antes de cerrar"', 24, 14, 'Parent.Width - 48 - 208', 40, size=20,
          color='colPrimario', bold=True, nowrap=True),
    button('btnAsRestaurar', '="Restaurar quitados (" & CountRows(colAsisQuitados) & ")"', 'Parent.Width - 24 - 196', 16,
           196, 36, '=Collect(colAsis, colAsisQuitados);\nClear(colAsisQuitados);\n' + ARMAR_ASIS,
           fill='RGBA(255, 255, 255, 1)',
           color='colPrimario', border='colPrimario', size=12, bold=False,
           extra={'Visible': '=!IsEmpty(colAsisQuitados)'}),
    label('lblAsSub', AS_SUB, 24, 54, 'Parent.Width - 48', 46, size=12, color=GRIS_TXT, valign='Top', padv=2),
    # Sin convocados, el aviso va en una franja arriba y la lista baja.
    gallery('galAsis', AS_ITEMS, 16, f'104 + If({AS_SIN_CONV}, 60, 0)',
            f'Parent.Width - 32', f'Parent.Height - 104 - 156 - If({AS_SIN_CONV}, 60, 0)', 56, [
        # Encabezado de área: nombre a la izquierda y el conteo en la celda de la derecha, con una línea a lo ancho.
        # La tarjeta es de 960 px (celdas de 464, ~294 px de texto) y los textos largos bajan a 11 o 10 para no cortarse con «…».
        label('lblAsArea', '=Upper(ThisItem.Area)', 10, 18, f'{TW} - 10', 32, size='If(Len(ThisItem.Area) > 34, 11, 13)',
              color='colPrimario', bold=True, nowrap=True, visible='=ThisItem.Fila = "Area"'),
        label('lblAsAreaConteo', AS_AREA_CONTEO, 0, 18, f'{TW} - 10', 32, size=12, color=GRIS_TXT, align='Right',
              nowrap=True, visible='=ThisItem.Fila = "AreaFin"'),
        rect('linAsArea', 'colAzul', '0', f'{TH} - 2', TW, '2',
             extra={'Visible': '=ThisItem.Fila in ["Area", "AreaFin"]'}),
        rect('recAsFila', '=If(ThisItem.Presente, RGBA(255, 255, 255, 1), RGBA(253, 236, 234, 1))', '0', '0',
             f'{TW}', f'{TH}', extra={'Visible': ES_PERSONA}),
        label('lblAsNombre', '=ThisItem.Nombre', 10, 4, f'{TW} - 10 - 160', 26, size='If(Len(ThisItem.Nombre) > 34, 11, 13)',
              color='colTexto', semibold=True, nowrap=True, visible=ES_PERSONA),
        label('lblAsCargo', '''=If(
    // El encabezado ya dice INVITADOS: aquí va solo el correo.
    ThisItem.Tipo = "Invitado",
    If(IsBlank(ThisItem.Correo), "sin correo", ThisItem.Correo),
    ThisItem.Cargo
)''', 10, 28, f'{TW} - 10 - 160', 22, size='If(Len(Self.Text) > 40, 10, 11)', color=GRIS_TXT, nowrap=True,
              visible=ES_PERSONA),
        # Convocado: alterna Presente / Ausente. El invitado está presente por definición (si no vino, se quita).
        button('btnAsEstado', '=If(ThisItem.Presente, "✔ Presente", "✖ Ausente")',
               f'{TW} - 150', f'({TH} - 34) / 2', 108, 34,
               '''=UpdateIf(colAsis, IdLocal = ThisItem.IdLocal, {Presente: !ThisItem.Presente});
UpdateIf(colAsisVista, IdLocal = ThisItem.IdLocal, {Presente: !ThisItem.Presente})''',
               fill='=If(ThisItem.Presente, colVerde, colRojo)', size=12, radius=17, border='RGBA(255, 255, 255, 0)',
               extra={'DisplayMode': '=If(ThisItem.Tipo = "Invitado", DisplayMode.View, DisplayMode.Edit)',
                      'Visible': ES_PERSONA,
                      'HoverFill': '=ColorFade(Self.Fill, -15%)', 'PressedFill': '=ColorFade(Self.Fill, -25%)',
                      'DisabledFill': '=Self.Fill', 'DisabledColor': '=Self.Color'}),
        # Quita a la persona solo de esta reunión; «Restaurar quitados» la devuelve.
        ctl('icoAsQuitar', 'Classic/Icon@2.5.0', {
            'Icon': '=Icon.Cancel', 'Color': '=RGBA(120, 128, 133, 1)', 'Width': '=32', 'Height': '=32',
            'X': f'={TW} - 38', 'Y': f'=({TH} - 32) / 2', 'PaddingLeft': '=6', 'PaddingRight': '=6',
            'PaddingTop': '=6', 'PaddingBottom': '=6', 'Tooltip': '="Quitar de esta reunión"',
            'AccessibleLabel': '="Quitar a " & ThisItem.Nombre & " de esta reunión"', 'Visible': ES_PERSONA,
            'OnSelect': '=Collect(colAsisQuitados, LookUp(colAsis, IdLocal = ThisItem.IdLocal));\n'
                        'RemoveIf(colAsis, IdLocal = ThisItem.IdLocal);\n' + ARMAR_ASIS}),
        rect('sepAsFila', 'RGBA(225, 230, 232, 1)', '0', f'{TH} - 1', TW, '1', extra={'Visible': ES_PERSONA}),
    ], padding=4, extra={'WrapCount': '=2', 'BorderColor': '=RGBA(225, 230, 232, 1)', 'BorderThickness': '=1'}),
    label('lblAsVacio', '''=If(
    IsEmpty(Filter(colAsisQuitados, Tipo = "Convocado")),
    "No hay lista de convocados en este equipo: se carga desde RD_Participantes con «Actualizar datos» en Inicio.",
    "Quitaste a todos los convocados de esta reunión: «Restaurar quitados» los devuelve."
) & Char(10) & "Si cierras así, la minuta llega solo a ti y a los invitados con correo."''',
          16, 104, 'Parent.Width - 32', 52, size=12, color=GRIS_TXT, fill='RGBA(244, 246, 247, 1)', pad=12, padv=4,
          valign='Middle', visible=f'={AS_SIN_CONV}'),
    # Invitados: nombre y correo (opcional) en una fila.
    label('lblAsInvitado', '="Invitado"', 24, 'Parent.Height - 140', 80, 44, size=13, color='colTexto', semibold=True),
    textinput('txtInvNombre', '', '="Nombre"', 104, 'Parent.Height - 140', '(Parent.Width - 104 - 24 - 24 - 150) / 2',
              44, size=13),
    textinput('txtInvCorreo', '', '="Correo (opcional)"', '104 + (Parent.Width - 104 - 24 - 24 - 150) / 2 + 12',
              'Parent.Height - 140', '(Parent.Width - 104 - 24 - 24 - 150) / 2', 44, size=13),
    button('btnAgregarInvitado', '+ Agregar', 'Parent.Width - 24 - 150', 'Parent.Height - 140', 150, 44, '''=Collect(
    colAsis,
    {
        Nombre: Trim(txtInvNombre.Text),
        Correo: Lower(Trim(txtInvCorreo.Text)),
        Cargo: "",
        Area: "Invitados",
        Tipo: "Invitado",
        Presente: true,
        IdLocal: Text(GUID())
    }
);
Reset(txtInvNombre);
Reset(txtInvCorreo);
''' + ARMAR_ASIS, fill='RGBA(255, 255, 255, 1)', color='colPrimario', size=13, border='colPrimario',
           extra={'DisplayMode': f'=If({INV_OK}, DisplayMode.Edit, DisplayMode.Disabled)'}),
    rect('sepAsPie', 'RGBA(225, 230, 232, 1)', '0', 'Parent.Height - 84', 'Parent.Width', '1'),
    label('lblAsConteo', AS_CONTEO, 24, 'Parent.Height - 74', 'Parent.Width - 24 - 24 - 470 - 12', 60, size=12,
          color='colTexto', valign='Middle', padv=2),
    button('btnAsVolver', 'Volver a la reunión', 'Parent.Width - 24 - 260 - 12 - 198', 'Parent.Height - 70', 198, 52,
           '=Set(varVerAsistencia, false)', fill='RGBA(255, 255, 255, 1)', color='colTexto',
           border='RGBA(160, 160, 160, 1)', bold=False, size=14),
    button('btnAsCerrar', 'Cerrar y enviar minuta', 'Parent.Width - 24 - 260', 'Parent.Height - 70', 260, 52, CERRAR,
           fill='colAmbar', size=15),
])
ventana_asistencia = container('conAsistencia', {
    'Fill': '=RGBA(0, 0, 0, 0.45)', 'Height': '=Parent.Height', 'Visible': '=varVerAsistencia', 'Width': '=Parent.Width',
    'X': '=0', 'Y': '=0', 'RadiusBottomLeft': '=0', 'RadiusBottomRight': '=0', 'RadiusTopLeft': '=0',
    'RadiusTopRight': '=0'}, [as_tarjeta])


# ---------- armado de la pantalla ----------
ONVISIBLE = '''=If(
    !varReunionEnCurso,
    Set(varReunionEnCurso, true);
    Set(gblSesionId, Text(GUID()));
    Set(varInicio, Now());
    Set(varAhora, Now());
    Set(varBloque, 0);
    Set(varFiltroEstado, "");
    Set(varBloqueInicio, Now());
    Clear(colTiempos);
    // Compromisos de esta semana preparados en el editor: salen en Compromisos con estado En progreso.
    // El Cierre (colNuevos) parte vacío: es para los que surgen en la reunión.
    ClearCollect(
        colNuevosPrep,
''' + indentar(NUEVOS_PREP, 8) + '''
    );
    Clear(colNuevos);
    // Asistencia: parte con todos los convocados presentes (lista de RD_Participantes).
    ClearCollect(
        colAsis,
        ForAll(
            colParticipantes As p,
            {Nombre: p.Nombre, Correo: p.Correo, Cargo: p.Cargo, Area: If(IsBlank(p.Area), "Sin área", p.Area), Tipo: "Convocado", Presente: true, IdLocal: Text(GUID())}
        )
    );
    Clear(colAsisQuitados)
);
// Si la reunión empezó antes de que llegara la preparación, se vuelven a tomar los compromisos preparados.
If(IsEmpty(colNuevosPrep) && IsEmpty(colNuevos), ClearCollect(
        colNuevosPrep,
''' + indentar(NUEVOS_PREP, 8) + '''
    ));
Set(varVerAsistencia, false);
Set(varEvidVerId, 0);
Set(varConfSalir, false);
''' + FN['reset_vars']

# Confirmación para eliminar un compromiso nuevo: último hijo de la pantalla, así queda encima de todo.
confirmar_borrar = confirmar('BorrarNuevo', FN['confirmar_visible'], '="¿Seguro que quieres eliminar este compromiso?"',
                             FN['confirmar_detalle'], FN['confirmar_si'], FN['confirmar_no'])

# «← Salir sin cerrar»: se puede entrar al visor las veces que haga falta (por ejemplo, para ver cómo quedó lo preparado)
# sin que cuente como reunión. Salir no escribe nada ni manda la minuta: deja la reunión como no empezada y la próxima
# entrada parte de cero con la preparación. Lo único que cierra la reunión semanal es «Finalizar reunión» › «Cerrar y enviar
# minuta». Cerrar la pestaña del navegador tampoco escribe nada.
SALIR_SI = '''=Set(varConfSalir, false);
Set(varReunionEnCurso, false);
Clear(colNuevos);
Clear(colNuevosPrep);
Clear(colAsis);
Clear(colAsisQuitados);
Set(varVerAsistencia, false);
Set(varEvidVerId, 0);
Navigate(scrInicio, ScreenTransition.Fade)'''
confirmar_salir = confirmar('Salir', '=varConfSalir', '="¿Salir sin cerrar la reunión?"',
                            '="No se guarda nada de esta presentación ni se envía la minuta. Lo preparado en el editor sigue '
                            'igual y se puede volver a presentar cuantas veces se quiera."',
                            SALIR_SI, '=Set(varConfSalir, false)', si='Salir')

base = screen('scrVisor', {'Fill': '=colFondo', 'OnVisible': ONVISIBLE}, [encabezado])
base = base.rstrip('\n') + '\n'
cuerpo = ''.join('\n'.join(f(6)) + '\n' for f in (pagina0, pagina1, pagina2, pagina3, pagina5, ventana_asistencia, ventana_evidencia, confirmar_borrar, confirmar_salir))
yaml = base + TIMER_STEPPER + cuerpo
(DEV / 'scrVisor.yaml').write_text(yaml, encoding='utf-8', newline='\n')
print('scrVisor.yaml:', len(yaml), 'caracteres,', yaml.count('\n'), 'líneas')


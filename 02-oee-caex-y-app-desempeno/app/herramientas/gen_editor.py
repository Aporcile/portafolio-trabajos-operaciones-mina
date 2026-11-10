"""Genera scrEditor.yaml (modo editor: se prepara la reunión antes de presentarla)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from yamlgen import *  # noqa

DEV = Path(__file__).resolve().parent.parent / 'pantallas'
WHITE = 'RGBA(255, 255, 255, 1)'
GRIS = 'RGBA(90, 98, 104, 1)'
TW = 'Parent.TemplateWidth'
TH = 'Parent.TemplateHeight'
SUCIA = 'Set(varPrepSucia, true)'

# Convocados por área: la lista muestra, por cada área, un encabezado (se toca para elegirla en el cuadro «Área») y sus personas
# por nombre. Áreas en orden alfabético y "Sin área" al final. Se calcula de colParticipantes.
CONV_VISTA = '''=Sort(
    Ungroup(
        With(
            {areas: Sort(Distinct(colParticipantes, If(IsBlank(Area), "Sin área", Area)), Value)},
            ForAll(
                Sequence(CountRows(areas)) As i,
                With(
                    {a: Index(areas, i.Value).Value},
                    With(
                        {o: If(a = "Sin área", 999, i.Value) * 1000, gente: Sort(Filter(colParticipantes, If(IsBlank(Area), "Sin área", Area) = a), Nombre)},
                        {
                            Filas: ForAll(
                                Sequence(CountRows(gente) + 1, 0) As j,
                                If(
                                    j.Value = 0,
                                    {Orden: o, Fila: "Area", Area: a, N: CountRows(gente), Nombre: "", Correo: "", Cargo: ""},
                                    With(
                                        {p: Index(gente, j.Value)},
                                        {Orden: o + j.Value, Fila: "Persona", Area: a, N: 0, Nombre: p.Nombre, Correo: p.Correo, Cargo: p.Cargo}
                                    )
                                )
                            )
                        }
                    )
                )
            )
        ),
        Filas
    ),
    Orden
)'''

# ---------------- guardar la preparación ----------------
# colDest se carga de fxDest y se guarda en la clave «des» del JSON para conservar lo ya preparado; ninguna sección lo
# muestra ni lo sube (el visor deja vacía colCierreDest al cerrar la reunión).

# Seguridad: avisos con nivel (colAvisos) e indicadores escritos a mano. Rango ordena del más grave al más leve.
NIVELES = (('Crítico', '✖ Crítico', 'colRojo'), ('Precaución', '⚠ Precaución', 'colAmbar'),
           ('Recordar', '✔ Recordar', 'colVerde'))
RANGO = 'Switch({n}, "Crítico", 1, "Precaución", 2, "Recordar", 3, 4)'
ALTA_AVISO = ('Collect(colAvisos, {Nivel: varNivelEd, Texto: Trim(txtAvisoEd.Text), '
              'Orden: Coalesce(Max(colAvisos, Orden), 0) + 1, IdLocal: Text(GUID()), Rango: '
              + RANGO.format(n='varNivelEd') + '});\nReset(txtAvisoEd)')
# Recuadros de indicadores: (sufijo, título, filas (texto, campo de fxIndSeg)). El campo da el nombre de la casilla
# (txtSeg<campo>Ed) y su clave en el JSON. Los campos Rep / RepMeta (claves rep / repm) se escriben a mano.
IND_SEG = (('Inc', 'Incidentes', (('Semana', 'Inc'), ('Anterior', 'IncAnt'))),
           ('Rep', 'Hipo Hazard', (('Semana', 'Rep'), ('Meta', 'RepMeta'))),
           ('Ins', 'Inspecciones', (('Hechas', 'InsReal'), ('Plan', 'InsPlan'))))
CLAVE_IND = {'Inc': 'inc', 'IncAnt': 'inca', 'Rep': 'rep', 'RepMeta': 'repm', 'InsReal': 'ire', 'InsPlan': 'ipl'}

# Guardar la evidencia del panel abierto (botón Guardar del panel, y Guardar de arriba si quedó abierto).
# La evidencia puede ser una foto o cualquier archivo (control Adjuntos). Nombre guarda el nombre original
# del archivo (vacío para una foto) para subirlo con su extensión.
EVID_NUEVA = '(!IsEmpty(attEvidEd.Attachments) || !IsBlank(addFotoEvidEd.Media))'
EVID_NOMBRE = '''If(
    !IsEmpty(attEvidEd.Attachments),
    First(attEvidEd.Attachments).Name,
    IsBlank(addFotoEvidEd.Media),
    LookUp(colEvid, CompromisoId = varEvidId).Nombre,
    ""
)'''
EVID_APLICAR = '''With(
    {f: imgEvidPreviaEd.Image, nom: ''' + EVID_NOMBRE.replace('\n', ' ') + ''', nuevo: ''' + EVID_NUEVA + '''},
    RemoveIf(colEvid, CompromisoId = varEvidId);
    If(!IsBlank(f), Collect(colEvid, {CompromisoId: varEvidId, Foto: f, TieneFoto: true, Nombre: nom}));
    Patch(
        colRevision,
        LookUp(colRevision, ID = varEvidId),
        {
            Comentario: Trim(txtEvidComentarioEd.Text),
            Url: If(nuevo, "", LookUp(colRevision, ID = varEvidId).Url)
        }
    )
);
Set(varEvidId, 0);
Reset(addFotoEvidEd);
Reset(attEvidEd);
Reset(txtEvidComentarioEd)'''
# Extensión del archivo que se sube: la del original, o .jpg para una foto.
def ext_evid(n):
    return f'If(IsBlank({n}), ".jpg", IsBlank(Find(".", {n})), "", "." & Lower(Last(Split({n}, ".")).Value))'

# Lo escrito sin confirmar también se guarda (por ejemplo, un aviso escrito sin tocar «+»).
PENDIENTES = ('// 0) Lo escrito sin confirmar: evidencia con el panel abierto, aviso sin «+ Agregar aviso» y compromiso nuevo completo.\n'
              'If(\n    varEvidId <> 0,\n' + '\n'.join('    ' + ln for ln in EVID_APLICAR.split('\n')) + '\n);\n'
              + f'If(!IsBlank(Trim(txtAvisoEd.Text)), {ALTA_AVISO.replace(chr(10), " ")});\n'
              + '''If(
    !IsBlank(Trim(txtNuevoQueEd.Text)) && !IsBlank(Trim(txtNuevoRespEd.Text)),
    Collect(colNuevos, {Titulo: Trim(txtNuevoQueEd.Text), Responsable: Trim(txtNuevoRespEd.Text), FechaLimite: dpNuevoFechaEd.SelectedDate, IdLocal: Text(GUID())});
    Reset(txtNuevoQueEd);
    Reset(txtNuevoRespEd);
    Reset(dpNuevoFechaEd)
);
''')

GUARDAR = '=Set(varPrepGuardando, true);\n' + PENDIENTES + r'''// seg: resumen en texto de los avisos (lo usan la sesión y las versiones anteriores del visor).
Set(varSeg, Concat(Sort(colAvisos, Rango * 1000 + Orden), Nivel & ": " & Texto, Char(10)));
// 1) Evidencias nuevas (fotos o archivos) a la carpeta Evidencias (solo con señal). Cada una se sube una vez: al subirla queda su link en Url.
If(
    Connection.Connected,
    ForAll(
        colEvid As e,
        If(
            IsBlank(LookUp(colRevision, ID = e.CompromisoId).Url),
            IfError(
                With(
                    {u: RDSubirEvidencia.Run("Prep_" & claveReunion & "_C" & e.CompromisoId & "_" & Text(Now(), "hhmmss") & ''' + ext_evid('e.Nombre') + r''', JSON(e.Foto, JSONFormat.IncludeBinaryData)).url},
                    Patch(colRevision, LookUp(colRevision, ID = e.CompromisoId), {Url: u})
                );
                true,
                Notify("No se pudo subir una evidencia: " & FirstError.Message, NotificationType.Error);
                false
            )
        )
    )
);
// 2) Texto JSON de la preparación: tema de seguridad, estado de cada compromiso, destacados y compromisos nuevos.
Set(
    varPrepJson,
    JSON(
        {
            seg: varSeg,
            avi: ForAll(colAvisos As a, {id: a.IdLocal, n: a.Nivel, x: a.Texto, o: a.Orden}),
            ind: {''' + ', '.join(f'{CLAVE_IND[c]}: Value(txtSeg{c}Ed.Text)' for _, _, filas in IND_SEG for _, c in filas) + r'''},
            cor: User().Email,
            est: ForAll(colRevision As r, {id: r.ID, estado: r.EstadoNuevo, rev: r.Revisado, com: r.Comentario, url: r.Url}),
            des: ForAll(colDest As d, {id: d.IdLocal, t: d.Tipo, x: d.Texto, o: d.Orden}),
            nue: ForAll(colNuevos As n, {id: n.IdLocal, t: n.Titulo, r: n.Responsable, f: Text(n.FechaLimite, "yyyy-mm-dd")})
        },
        JSONFormat.Compact
    )
);
// 3) Copia local (el visor de este equipo la lee) y subida a Excel (RD_Preparacion).
ClearCollect(colPrepFila, {Clave: claveReunion, Json: varPrepJson, Actualizado: Text(Now(), "yyyy-mm-dd hh:mm"), Autor: User().FullName});
SaveData(colPrepFila, "rd_prepfila");
Set(varPrepErr, "");
// Refresh: la lectura en memoria puede ser vieja; así no se crea una fila repetida si otro equipo ya la creó.
If(Connection.Connected, Refresh(RD_Preparacion));
Set(
    varPrepNube,
    Connection.Connected &&
    IfError(
        If(
            IsBlank(LookUp(RD_Preparacion, Clave = claveReunion)),
            Patch(RD_Preparacion, Defaults(RD_Preparacion), First(colPrepFila)),
            Patch(RD_Preparacion, LookUp(RD_Preparacion, Clave = claveReunion), {Json: varPrepJson, Actualizado: First(colPrepFila).Actualizado, Autor: First(colPrepFila).Autor})
        );
        true,
        Set(varPrepErr, FirstError.Message);
        false
    )
);
If(
    varPrepNube,
    Clear(colOutPrep);
    Notify("Preparación guardada.", NotificationType.Success),
    ClearCollect(colOutPrep, First(colPrepFila));
    Notify(If(Connection.Connected, "No se pudo guardar en la nube (" & varPrepErr & "). ", "Sin señal: ") & "La preparación quedó en este equipo y se sube sola al sincronizar.", NotificationType.Warning)
);
SaveData(colOutPrep, "rd_out_prep");
Set(varPrepSucia, false);
Set(varPrepGuardando, false)'''

# Todos los compromisos de la semana pasada deben quedar con estado.
# Mientras falte alguno no se puede guardar ni volver a Inicio: el aviso dice cuántos faltan y lleva al bloque 2.
FALTAN = 'CountRows(Filter(colRevision, !Revisado))'
# Un compromiso nuevo a medio escribir (solo qué o solo responsable) no se puede guardar solo: se avisa.
MEDIO_NUEVO = 'IsBlank(Trim(txtNuevoQueEd.Text)) <> IsBlank(Trim(txtNuevoRespEd.Text))'
# El formulario de compromisos nuevos está en la pestaña «Nuevos compromisos» de Compromisos (sección 2 con varSubCompEd = 2):
# panel conB5Ed, lista colNuevos. Un aviso sobre un compromiso nuevo a medio escribir lleva al panel solo si no se está
# viendo ya; uno sobre estados sin marcar lleva a la pestaña «Semana pasada».
EN_NUEVOS = '(varBloqueEd = 2 && varSubCompEd = 2)'
IR_NUEVOS = f'If(!{EN_NUEVOS}, Set(varBloqueEd, 2); Set(varSubCompEd, 2));'
GUARDAR_BTN = ('=If(\n'
               f'    {FALTAN} > 0,\n'
               '    Set(varBloqueEd, 2);\n'
               '    Set(varSubCompEd, 1);\n'
               f'    Notify("Para guardar, todos los compromisos deben tener estado. Faltan " & {FALTAN} & ".", NotificationType.Warning),\n'
               '    !IsBlank(varEditNuevoEd),\n'
               f'    {IR_NUEVOS}\n'
               '    Notify("Termina de editar el compromiso nuevo: «Guardar cambios» o «Cancelar».", NotificationType.Warning),\n'
               f'    {MEDIO_NUEVO},\n'
               f'    {IR_NUEVOS}\n'
               '    Notify("Al compromiso nuevo le falta qué se hará o el responsable: complétalo o bórralo.", NotificationType.Warning),\n'
               + '\n'.join('    ' + ln for ln in GUARDAR[1:].split('\n')) + '\n)')
# Cambios sin guardar: los marcados (varPrepSucia) y lo escrito que todavía no se confirmó.
SIN_GUARDAR = ('varPrepSucia || varEvidId <> 0 || !IsBlank(varEditNuevoEd) || '
               + ' || '.join(f'!IsBlank(Trim(txt{p}Ed.Text))' for p in ('NuevoQue', 'NuevoResp', 'Aviso')))
VOLVER = f'''=If(
    {FALTAN} > 0,
    Set(varBloqueEd, 2);
    Set(varSubCompEd, 1);
    Notify("Antes de salir, marca el estado de todos los compromisos. Faltan " & {FALTAN} & ".", NotificationType.Warning),
    {SIN_GUARDAR},
    Notify("Guarda la preparación antes de salir (botón Guardar).", NotificationType.Warning),
    Navigate(scrInicio, ScreenTransition.Fade)
)'''

ONVISIBLE = f'''=If(
    !varPrepSucia || varPrepFecha <> claveReunion,
    Set(varPrepFecha, claveReunion);
    Set(varPrepSucia, false);
    ClearCollect(colRevision, fxRevision);
    Clear(colEvid);
    ClearCollect(colDest, fxDest);
    ClearCollect(
        colNuevos,
{indentar(NUEVOS_PREP, 8)}
    );
    // Sin preparación guardada, la meteorología del plan semanal parte como aviso de precaución.
    ClearCollect(colAvisos, fxAvisos);
    If(
        IsBlank(fxPrepFila) && IsEmpty(colAvisos) && !IsBlank(First(colPlan).Meteorologia),
        Collect(colAvisos, {{Nivel: "Precaución", Texto: First(colPlan).Meteorologia, Orden: 1, IdLocal: Text(GUID()), Rango: 2}})
    );
    Set(varIndEd, fxIndSeg)
);
Set(varNivelEd, "Precaución");
Set(varBloqueEd, 1);
Set(varSubCompEd, 1);
Set(varEvidId, 0);
Set(varConvEditEd, Blank())'''

# ---------------- encabezado ----------------
encabezado = container('conHeaderEd', {'Fill': '=colPrimario', 'Height': '=72', 'Width': '=Parent.Width',
                                        'RadiusBottomLeft': '=0', 'RadiusBottomRight': '=0',
                                        'RadiusTopLeft': '=0', 'RadiusTopRight': '=0'}, [
    ctl('imgLogoEd', 'Image@2.2.3', {'Image': LOGO, 'ImagePosition': '=ImagePosition.Fit', 'Height': '=56',
                                      'Width': '=120', 'X': '=12', 'Y': '=8'}),
    # Logo secundario junto al logo principal.
    ctl('imgLogoAreaEd', 'Image@2.2.3', {'Image': LOGO_AREA, 'ImagePosition': '=ImagePosition.Fit', 'Height': '=44',
                                          'Width': '=44', 'X': '=138', 'Y': '=14'}),
    # Título de la pantalla, al lado de la fecha de la reunión que se prepara (en 15 cabe en 310 px).
    label('lblTituloEd', '="RD Minera Demo · " & Text(fecReunion, "ddd dd-mm", "es-ES")', 190, 8, 310, 36, size=15,
          color=WHITE, bold=True, nowrap=True),
    # El estado del guardado va debajo del título y la descripción a su derecha, para que se lea completa.
    label('lblEstadoPrepEd', f'''=If(
    varPrepGuardando,
    "Guardando…",
    {SIN_GUARDAR},
    "● Cambios sin guardar",
    !IsBlank(fxPrepFila),
    // Actualizado viene como «aaaa-mm-dd hh:mm»: se muestra «dd-mm hh:mm», como en el resto de la app.
    "✔ Guardado " & With({{a: fxPrepFila.Actualizado}}, If(Len(a) >= 16, Mid(a, 9, 2) & "-" & Mid(a, 6, 2) & " " & Mid(a, 12, 5), a)),
    "Sin preparación guardada"
)''', 190, 44, 300, 22, size=12,
          color=f'=If({SIN_GUARDAR}, RGBA(255, 204, 128, 1), RGBA(165, 214, 167, 1))', semibold=True, nowrap=True),
    # Descripción a la derecha del título, entre el título y el botón Guardar. Con 1024 px de pantalla son ~178 px:
    # tres líneas de 11 (3 x 20 px) en 64 px de alto.
    label('lblSubEd', '="Modo editor: lo que prepares se muestra en la reunión (visor)."', 506, 4, 'Parent.Width - 852',
          64, size=11, color='RGBA(200, 211, 227, 1)', valign='Middle', padv=2),
    button('btnGuardarPrepEd', '="Guardar"', 'Parent.Width - 318', 12, 150, 48, GUARDAR_BTN, fill='colAmbar',
           extra={'DisplayMode': '=If(varPrepGuardando, DisplayMode.Disabled, DisplayMode.Edit)'}),
    button('btnVolverEd', '="← Inicio"', 'Parent.Width - 160', 12, 148, 48, VOLVER,
           fill='RGBA(255, 255, 255, 0.15)', color=WHITE, border=WHITE),
])

# El editor tiene dos secciones: 1 Seguridad y 2 Compromisos (pestañas «Semana pasada» y «Nuevos compromisos»).
# Convocados es una entrada aparte (varBloqueEd = 6). Los números internos no coinciden con los del visor.
menu = gallery('galBloquesEd',
               '=Table({N: 1, Nombre: "Seguridad"}, {N: 2, Nombre: "Compromisos"})',
               16, 88, 240, '2 * 80 + 6', 74, [
    button('btnBloqueEd', '=ThisItem.N & ". " & ThisItem.Nombre', 0, 0, f'{TW} - 6', f'{TH} - 6', '=Set(varBloqueEd, ThisItem.N)',
           fill='''=If(
    varBloqueEd = ThisItem.N,
    colPrimario,
    RGBA(255, 255, 255, 1)
)''', color='=If(varBloqueEd = ThisItem.N, RGBA(255, 255, 255, 1), colPrimario)', size=15, bold=False,
           border='colPrimario', extra={'Align': '=Align.Left', 'FontWeight': '=FontWeight.Semibold',
                                        'PaddingLeft': '=16'}),
], padding=6)
# Siguiente: Seguridad › Compromisos (Semana pasada) › Nuevos compromisos.
siguiente = button('btnSiguienteEd', '="Siguiente ▶"', 16, 'galBloquesEd.Y + galBloquesEd.Height + 12', 234, 64,
                   '=If(varBloqueEd = 2, Set(varSubCompEd, 2), Set(varBloqueEd, 2); Set(varSubCompEd, 1))', size=16,
                   extra={'DisplayMode': '=If(varBloqueEd = 1 || (varBloqueEd = 2 && varSubCompEd = 1), DisplayMode.Edit, DisplayMode.Disabled)'})

# ---------------- sección 1: seguridad ----------------
sec1_hijos = [
    label('lblB1TituloEd', '="Seguridad"', 24, 14, 'Parent.Width - 48', 44, size=24, color='colTexto', bold=True),
    label('lblB1AyudaEd', '="Cifras de la semana (a mano) y avisos con su nivel. Toca el nivel para cambiarlo."',
          24, 56, 'Parent.Width - 48', 30, size=12, color=GRIS, valign='Top', padv=2),
]
# Tres recuadros como los del visor. A 1024 px cada uno mide ~219 px: el texto de cada fila
# va a la izquierda y la casilla (76 px) a la derecha.
BWS = '(Parent.Width - 48 - 24) / 3'
for i, (suf, titulo, filas) in enumerate(IND_SEG):
    x = f'24 + {i} * ({BWS} + 12)'
    sec1_hijos += [
        rect(f'recSeg{suf}Ed', 'RGBA(244, 246, 251, 1)', x, '92', BWS, '116'),
        label(f'lblSegTit{suf}Ed', f'="{titulo}"', x, 94, BWS, 38, size=11, color='colPrimario', bold=True,
              valign='Top', pad=8, padv=2),
    ]
    for j, (txt, campo) in enumerate(filas):
        y = 134 + j * 36
        sec1_hijos += [
            label(f'lblSeg{campo}Ed', f'="{txt}"', f'{x} + 8', y, f'{BWS} - 96', 30, size=11, color=GRIS, nowrap=True),
            textinput(f'txtSeg{campo}Ed', f'=Text(varIndEd.{campo})', '=""', f'{x} + {BWS} - 84', y, 76, 30, size=13,
                      onchange='=' + SUCIA, extra={'Format': '=TextFormat.Number'}),
        ]
# Avisos: se escribe el texto, se elige el nivel y «+ Agregar aviso». En la lista, el nivel se toca para cambiarlo.
sec1_hijos += [
    label('lblSegAvisosEd', '="Avisos"', 24, 216, 200, 28, size=14, color='colTexto', bold=True),
    textinput('txtAvisoEd', '=""', '="Ej.: tronadura en Fase 2 a las 13:00; evacuación desde las 12:30"', 24, 248,
              'Parent.Width - 48', 40, size=14),
]
for i, (niv, txt, color) in enumerate(NIVELES):
    sel = f'varNivelEd = "{niv}"'
    sec1_hijos.append(button(f'btnNivel{i + 1}Ed', f'="{txt}"', f'24 + {i} * 128', 296, 120, 36, f'=Set(varNivelEd, "{niv}")',
                             fill=f'=If({sel}, {color}, RGBA(255, 255, 255, 1))',
                             color=f'=If({sel}, RGBA(255, 255, 255, 1), {color})', size=12, border=color))
sec1_hijos += [
    button('btnAgregarAvisoEd', '="+ Agregar aviso"', 'Parent.Width - 24 - 170', 296, 170, 36,
           '=' + ALTA_AVISO + ';\n' + SUCIA, size=13,
           extra={'DisplayMode': '=If(IsBlank(Trim(txtAvisoEd.Text)), DisplayMode.Disabled, DisplayMode.Edit)'}),
    label('lblSinAvisosEd', '="Sin avisos todavía."', 24, 344, 'Parent.Width - 48', 40, size=13,
          color='RGBA(130, 138, 142, 1)', visible='=IsEmpty(colAvisos)'),
    gallery('galAvisosEd', '=Sort(colAvisos, Orden)', 24, 344, 'Parent.Width - 48', 'Parent.Height - 356', 52, [
        button('btnNivelAvisoEd', '=Switch(ThisItem.Nivel, "Crítico", "✖ Crítico", "Precaución", "⚠ Precaución", "Recordar", "✔ Recordar", "Aviso")',
               0, f'({TH} - 32) / 2', 120, 32,
               '=With({n: Switch(ThisItem.Nivel, "Crítico", "Precaución", "Precaución", "Recordar", "Crítico")}, '
               'Patch(colAvisos, ThisItem, {Nivel: n, Rango: ' + RANGO.format(n='n') + '}));\n' + SUCIA,
               fill='=Switch(ThisItem.Nivel, "Crítico", colRojo, "Precaución", colAmbar, "Recordar", colVerde, colPrimario)',
               size=11, radius=16,
               extra={'Tooltip': '="Toca para cambiar el nivel"', 'HoverFill': '=ColorFade(Self.Fill, -0.15)'}),
        label('lblTextoAvisoEd', '=ThisItem.Texto', 132, 0, f'{TW} - 132 - 48', TH, size=13, color='colTexto', padv=2),
        icon_cancel('icoQuitarAvisoEd', '=RemoveIf(colAvisos, IdLocal = ThisItem.IdLocal);\n' + SUCIA,
                    x=f'{TW} - 40', y=f'({TH} - 32) / 2'),
        rect('sepAvisoEd', 'RGBA(225, 230, 232, 1)', '0', f'{TH} - 1', TW, '1'),
    ]),
]
sec1 = container('conB1Ed', {'Height': '=Parent.Height - 104', 'Visible': '=varBloqueEd = 1',
                             'Width': '=Parent.Width - 296', 'X': '=272', 'Y': '=88'}, sec1_hijos)

# ---------------- sección 2: compromisos ----------------
# La lista ocupa el 65 % del ancho. Hay tres estados: a 1024 px de pantalla cada botón mide ~145 px.
LISTA_W = 'Parent.Width * 0.65'
BW3 = f'({TW} - 24 - 2 * 8) / 3'


def estado_btn(nombre, texto, estado, color, i, onselect):
    sel = f'ThisItem.Revisado && ThisItem.EstadoNuevo = "{estado}"'
    return button(nombre, f'="{texto}"', f'12 + {i} * ({BW3} + 8)', 108, BW3, 40, onselect,
                  fill=f'=If({sel}, {color}, RGBA(255, 255, 255, 1))',
                  color=f'=If({sel}, RGBA(255, 255, 255, 1), {color})', size=12, bold=False, radius=0,
                  border=color, extra={'Height': '=40'})


QUITAR_EVID = '''RemoveIf(colEvid, CompromisoId = ThisItem.ID);
If(varEvidId = ThisItem.ID, Set(varEvidId, 0));
Set(varPrepSucia, true)'''


def onsel_estado(estado):
    return ('=Patch(colRevision, ThisItem, {EstadoNuevo: "%s", Revisado: true, Comentario: "", Url: ""});\n' % estado
            + QUITAR_EVID)


ONSEL_CUMPLIDO = '''=Patch(colRevision, ThisItem, {EstadoNuevo: "Cumplido", Revisado: true});
Set(varEvidId, ThisItem.ID);
Reset(txtEvidComentarioEd);
Reset(addFotoEvidEd);
Reset(attEvidEd);
Set(varPrepSucia, true)'''

evidencia = container('conEvidenciaEd', {'Fill': '=RGBA(244, 249, 244, 1)', 'Height': '=Parent.Height - 24',
                                         'RadiusBottomLeft': '=10', 'RadiusBottomRight': '=10',
                                         'RadiusTopLeft': '=10', 'RadiusTopRight': '=10',
                                         'Visible': '=varEvidId <> 0', 'Width': '=Parent.Width * 0.35 - 36',
                                         'X': '=Parent.Width * 0.65 + 20', 'Y': '=12'}, [
    label('lblEvidTituloEd', '="✔ Evidencia"', 12, 8, 'Parent.Width - 24', 36, size=17,
          color='colVerde', bold=True),
    # Panel angosto (~220 px a 1024 px de pantalla): el nombre del compromiso (hasta 100 caracteres) ocupa hasta cuatro
    # líneas de 12 puntos (4 x 21,8 px = 87 px). El comentario es multilínea y se desplaza.
    label('lblEvidCompromisoEd', '=LookUp(colRevision, ID = varEvidId).Titulo', 12, 42, 'Parent.Width - 24', 88,
          size=12, color='colTexto', semibold=True, valign='Top', padv=0),
    label('lblEvidAyudaEd', '="Foto, archivo o comentario"', 12, 132, 'Parent.Width - 24', 22,
          size=11, color=GRIS),
    textinput('txtEvidComentarioEd', '=LookUp(colRevision, ID = varEvidId).Comentario',
              '="Ej.: baliza instalada en rampa 3"', 12, 156, 'Parent.Width - 24', 64,
              size=13, multiline=True),
    label('lblEvidSubidaEd', '''=If(
    !IsBlank(LookUp(colRevision, ID = varEvidId).Url),
    "✔ Evidencia guardada",
    IsEmpty(attEvidEd.Attachments) && IsBlank(addFotoEvidEd.Media) && !IsBlank(LookUp(colEvid, CompromisoId = varEvidId).Nombre),
    "✔ Archivo adjunto",
    ""
)''', 12, 224, 'Parent.Width - 24', 22, size=11, color='colVerde', nowrap=True),
    ctl('imgEvidPreviaEd', 'Image@2.2.3', {
        'BorderColor': '=RGBA(200, 200, 200, 1)', 'BorderThickness': '=1', 'Fill': f'={WHITE}',
        'Height': '=Parent.Height - 252 - 72 - 92',
        'Image': '''=If(
    !IsEmpty(attEvidEd.Attachments),
    First(attEvidEd.Attachments).Value,
    IsBlank(addFotoEvidEd.Media),
    LookUp(colEvid, CompromisoId = varEvidId).Foto,
    addFotoEvidEd.Media
)''',
        'ImagePosition': '=ImagePosition.Fit', 'Width': '=Parent.Width - 24', 'X': '=12', 'Y': '=248'}),
    ctl('addFotoEvidEd', 'AddMedia@2.2.1', {
        'BorderColor': '=RGBA(0, 0, 0, 0)', 'BorderStyle': '=BorderStyle.None', 'Color': '=colPrimario',
        'Fill': '=RGBA(0, 0, 0, 0)', 'Height': '=imgEvidPreviaEd.Height', 'HoverColor': '=colPrimario',
        'HoverFill': '=RGBA(27, 42, 65, 0.08)', 'PressedFill': '=RGBA(27, 42, 65, 0.15)', 'Size': '=15',
        'Text': '=If(IsBlank(imgEvidPreviaEd.Image), "Tocar para tomar o elegir foto", "")',
        'Width': '=imgEvidPreviaEd.Width', 'X': '=imgEvidPreviaEd.X', 'Y': '=imgEvidPreviaEd.Y'}),
    # Cualquier archivo (PDF, Excel, Word, foto…), uno por compromiso. Control Adjuntos suelto, sin formulario.
    ctl('attEvidEd', 'Attachments@2.3.0', {
        'AddAttachmentText': '="+ Adjuntar archivo"', 'NoAttachmentsText': '=""',
        'MaxAttachments': '=1', 'MaxAttachmentSize': '=10', 'DisplayMode': '=DisplayMode.Edit',
        'BorderColor': '=RGBA(200, 200, 200, 1)', 'BorderThickness': '=1', 'Fill': f'={WHITE}', 'Size': '=12',
        'Height': '=84', 'Width': '=Parent.Width - 24', 'X': '=12', 'Y': '=Parent.Height - 72 - 88'}),
    button('btnGuardarEvidEd', 'Guardar', 12, 'Parent.Height - 64', '(Parent.Width - 32) / 2', 52,
           f'={EVID_APLICAR};\n{SUCIA}', fill='colVerde', extra={
        'DisplayMode': '=If(IsBlank(Trim(txtEvidComentarioEd.Text)) && IsBlank(imgEvidPreviaEd.Image) && IsEmpty(attEvidEd.Attachments), DisplayMode.Disabled, DisplayMode.Edit)'}),
    button('btnOmitirEvidEd', 'Ahora no', '20 + (Parent.Width - 32) / 2', 'Parent.Height - 64',
           '(Parent.Width - 32) / 2', 52, '''=Set(varEvidId, 0);
Reset(addFotoEvidEd);
Reset(attEvidEd);
Reset(txtEvidComentarioEd)''', fill=WHITE, color='colTexto', border='RGBA(160, 160, 160, 1)', bold=False),
])

def pestanas_comp(suf, visible=None):
    """Pestañas de la sección Compromisos: «Semana pasada» (estado de los compromisos de la reunión anterior) y
    «Nuevos compromisos» (los de esta semana, que salen en Compromisos de la presentación como En progreso). Cada panel lleva
    su propio par (suf '' en la revisión, '2' en el panel de nuevos): sustituyen al título de 20 puntos de la sección y
    terminan en X 452, antes de la columna derecha (X = 65 % del ancho + 24 = 497 a 1024 px). Variable: varSubCompEd."""
    def tab(nombre, texto, x, w, n):
        sel = f'varSubCompEd = {n}'
        extra = {'FontWeight': '=FontWeight.Semibold'}
        if visible:
            extra['Visible'] = visible
        return button(nombre, texto, x, 12, w, 40, f'=Set(varSubCompEd, {n})',
                      fill=f'=If({sel}, colPrimario, RGBA(255, 255, 255, 1))',
                      color=f'=If({sel}, RGBA(255, 255, 255, 1), colPrimario)', size=14, bold=False, radius=20,
                      border='colPrimario', extra=extra)
    return [tab(f'btnTabSemana{suf}Ed', '="Semana pasada"', 20, 180, 1),
            tab(f'btnTabNuevos{suf}Ed', '="Nuevos compromisos · " & CountRows(colNuevos)', 208, 244, 2)]


sec2 = container('conB2Ed', {'Height': '=Parent.Height - 104', 'Visible': '=varBloqueEd = 2 && varSubCompEd = 1',
                             'Width': '=Parent.Width - 296', 'X': '=272', 'Y': '=88'}, [
    *pestanas_comp(''),
    # Cada compromiso: título en hasta tres líneas (Y 4), detalle (Y 80) y los cuatro botones de estado (Y 108).
    # Tres líneas porque con ✔ Cumplido el botón «Con evidencia» le quita 144 px al título.
    # La barra naranja a la izquierda marca los que aún no tienen estado.
    gallery('galRevisionEd', '=Sort(colRevision, FechaLimite)', 12, 60, LISTA_W, 'Parent.Height - 72',
            156, [
        rect('recRevFaltaEd', 'colNaranja', '0', '4', '4', f'{TH} - 8', extra={'Visible': '=!ThisItem.Revisado'}),
        label('lblRevTituloEd', '=ThisItem.Titulo', 12, 4, f'{TW} - 24 - If(ThisItem.EstadoNuevo = "Cumplido", 144, 0)',
              76, size=14, color='colTexto', semibold=True, valign='Top', padv=2),
        button('btnRevEvidenciaEd',
               '=If(!IsBlank(ThisItem.Comentario) || !IsBlank(ThisItem.Url) || ThisItem.ID in colEvid.CompromisoId, "Con evidencia", "Evidencia")',
               f'{TW} - 148', 6, 136, 30, '''=Set(varEvidId, ThisItem.ID);
Reset(txtEvidComentarioEd);
Reset(addFotoEvidEd);
Reset(attEvidEd)''',
               fill='=If(!IsBlank(ThisItem.Comentario) || !IsBlank(ThisItem.Url) || ThisItem.ID in colEvid.CompromisoId, colVerde, RGBA(255, 255, 255, 1))',
               color='=If(!IsBlank(ThisItem.Comentario) || !IsBlank(ThisItem.Url) || ThisItem.ID in colEvid.CompromisoId, RGBA(255, 255, 255, 1), colVerde)',
               size=11, bold=False, radius=15, border='colVerde',
               extra={'Visible': '=ThisItem.EstadoNuevo = "Cumplido"'}),
        label('lblRevDetalleEd', '''=ThisItem.ResponsableNombre & " · vence " & Text(ThisItem.FechaLimite, "dd-mm") &
If(ThisItem.FechaLimite < Today(), " · VENCIDO", "") &
" · desde " & Text(ThisItem.FechaCreacion, "dd-mm")''', 12, 80, f'{TW} - 24', 26, size=12,
              color='=If(ThisItem.FechaLimite < Today(), colRojo, RGBA(90, 98, 104, 1))', nowrap=True),
        estado_btn('btnRevProgresoEd', 'En progreso', 'En progreso', 'colPrimario', 0, onsel_estado('En progreso')),
        estado_btn('btnRevCumplidoEd', '✔ Cumplido', 'Cumplido', 'colVerde', 1, ONSEL_CUMPLIDO),
        estado_btn('btnRevAtrasadoEd', '⚠ Atrasado', 'Atrasado', 'colAmbar', 2, onsel_estado('Atrasado')),
        rect('sepRevisionEd', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1'),
    ], padding=4),
    evidencia,
    # Avance arriba de la columna derecha (a 1024 px de pantalla son ~210 px: "Marcados: 12 de 15" en 14 px cabe).
    label('lblMarcadosEd', '=If(IsEmpty(colRevision), "", "Marcados: " & CountRows(Filter(colRevision, Revisado)) & " de " & CountRows(colRevision))',
          'Parent.Width * 0.65 + 24', 16, 'Parent.Width * 0.35 - 44', 36, size=14,
          color=f'=If({FALTAN} = 0, colVerde, colAmbar)', bold=True, nowrap=True, visible='=varEvidId = 0'),
    # Ayuda en la columna derecha, alineada arriba y con letra de 12 px: a 1024 px y 640 px de alto son 20 líneas de
    # ~28 caracteres (~385 px) en un espacio de 456 px.
    label('lblEvidPistaEd', '''="Todos los compromisos deben quedar con estado: si falta alguno, no se puede guardar ni volver a Inicio." & Char(10) & Char(10) & "✔ Cumplido lo cierra: queda en el Excel y no vuelve a aparecer." & Char(10) & Char(10) & "En progreso y ⚠ Atrasado vuelven a aparecer la semana siguiente." & Char(10) & Char(10) & "Con ✔ Cumplido puedes agregar evidencia (foto, archivo o comentario)." & Char(10) & Char(10) & "Lo que marques se muestra en el visor una vez que guardes."''',
          'Parent.Width * 0.65 + 24', 64, 'Parent.Width * 0.35 - 44', 'Parent.Height - 80', size=12, color=GRIS,
          valign='Top', visible='=varEvidId = 0'),
])


# Escribir en una casilla ya cuenta como cambio sin guardar (Guardar agrega lo escrito aunque no se toque «+»).
SUCIA_TXT = '=If(!IsBlank(Trim(Self.Text)), Set(varPrepSucia, true))'

# ---------------- compromisos nuevos (panel de Compromisos › «Nuevos compromisos») ----------------
# Los nombres conB5Ed y lblB5…Ed se conservan por compatibilidad con la numeración de secciones anterior.
LEFT_W = 'Parent.Width * 0.38 - 40'
# Los compromisos nuevos del editor son parte de la preparación (clave "nue" del JSON): se guardan con Guardar,
# aparecen en el visor y se suben como compromisos al cerrar la reunión.
FN = formulas_nuevos('Ed', despues=f';\n{SUCIA}')
# Este panel se ve en Compromisos › «Nuevos compromisos» (EN_NUEVOS): allí las pestañas ocupan el lugar del título.
# Es la misma lista (colNuevos) en todas las vistas.
sec5 = container('conB5Ed', {'Height': '=Parent.Height - 104', 'Visible': '=' + EN_NUEVOS,
                             'Width': '=Parent.Width - 296', 'X': '=272', 'Y': '=88'}, [
    *pestanas_comp('2'),
    # La ayuda ocupa hasta dos líneas (12 px; ~98 caracteres por línea a 1024 px) y los campos empiezan debajo, en Y = 104.
    # En la presentación salen en Compromisos (página 2), con estado En progreso; el Cierre del visor queda para los que surgen en la reunión.
    label('lblB5AyudaEd', '="Los compromisos de esta semana que ya se conocen. En la presentación salen en Compromisos con estado «En progreso» y se suben al Excel al cerrar la reunión."',
          20, 52, 'Parent.Width - 40', 44, size=12, color=GRIS, valign='Top', padv=2),
    textinput('txtNuevoQueEd', FN['def_que'], '="¿Qué se hará?"', 20, 104, LEFT_W, 72, size=14, multiline=True,
              onchange=SUCIA_TXT, extra={'MaxLength': '=100'}),
    textinput('txtNuevoRespEd', FN['def_resp'], '="Responsable"', 20, 184, LEFT_W, 48, size=14, onchange=SUCIA_TXT),
    ctl('dpNuevoFechaEd', 'Classic/DatePicker@2.6.0', {
        'DefaultDate': FN['def_fecha'], 'Format': '=DateTimeFormat.ShortDate', 'Height': '=48',
        'Size': '=14', 'Width': f'={LEFT_W}', 'X': '=20', 'Y': '=240'}),
    button('btnAgregarCompromisoEd', FN['texto_agregar'], 20, 300, LEFT_W, 52, FN['agregar'], size=15, extra={
        'DisplayMode': '=If(IsBlank(Trim(txtNuevoQueEd.Text)) || IsBlank(Trim(txtNuevoRespEd.Text)), DisplayMode.Disabled, DisplayMode.Edit)'}),
    label('lblNuevosTituloEd', '="Compromisos nuevos · " & CountRows(colNuevos)', 'Parent.Width * 0.38 + 8', 104,
          'Parent.Width * 0.62 - 40', 36, size=15, color='colTexto', semibold=True, nowrap=True),
    # Cada fila: texto a la izquierda y a la derecha «Editar» y «Eliminar», uno sobre otro. A 1024 px la columna deja
    # ~32 caracteres por línea: 100 caracteres (MaxLength) son 4 líneas más la del responsable = 5 líneas de 13 (108 px).
    gallery('galNuevosEd', '=colNuevos', 'Parent.Width * 0.38 + 8', 144, 'Parent.Width * 0.62 - 32',
            'Parent.Height - 164', 112, [
        label('lblNuevoItemEd', '=ThisItem.Titulo & Char(10) & ThisItem.Responsable & " · vence " & Text(ThisItem.FechaLimite, "dd-mm")',
              8, 0, f'{TW} - 108', 108, size=13, color='colTexto', padv=2),
        button('btnEditarNuevoEd', FN['texto_editar'], f'{TW} - 96', 4, 88, 32, FN['editar'], fill=WHITE,
               color='colPrimario', size=12, bold=False, border='colPrimario'),
        button('btnEliminarNuevoEd', 'Eliminar', f'{TW} - 96', 40, 88, 32, FN['eliminar'], fill=WHITE,
               color='colRojo', size=12, bold=False, border='colRojo'),
        rect('sepNuevoEd', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1'),
    ], padding=2, extra={'BorderColor': '=RGBA(230, 230, 230, 1)', 'BorderThickness': '=1',
                         'TemplateFill': FN['fill_fila']}),
])

# ---------------- convocados: lista de RD_Participantes, fuera de la agenda ----------------
# Se agregan personas desde el editor: se buscan en el directorio (Office 365 Users) o se agregan a mano. Escribe directo en
# RD_Participantes (necesita señal): quitar deja Activo = "No" en vez de borrar la fila, y volver a agregar a alguien lo reactiva.
# Entrada aparte bajo «Siguiente» (varBloqueEd = 6): no es un bloque de la reunión. A 640 px de alto termina en Y = 628.
convocados_btn = button('btnConvocadosEd', '="Convocados (" & CountRows(colParticipantes) & ")"', 16,
                        'btnSiguienteEd.Y + btnSiguienteEd.Height + 12', 234, 40, '=Set(varBloqueEd, 6)',
                        fill='=If(varBloqueEd = 6, colPrimario, RGBA(255, 255, 255, 1))',
                        color='=If(varBloqueEd = 6, RGBA(255, 255, 255, 1), colPrimario)', size=14, bold=False,
                        border='colPrimario', extra={'FontWeight': '=FontWeight.Semibold'})


def guardar_convocado(nombre, correo, cargo, area, despues=''):
    """Crea o reactiva al convocado en RD_Participantes (clave Correo) y lo deja en colParticipantes.
    Área: la del cuadro «Área»; si viene vacía se conserva la que tenía."""
    return f'''=If(
    !Connection.Connected,
    Notify("Sin señal: la lista de convocados se edita con conexión.", NotificationType.Warning),
    With(
        {{n: {nombre}, c: Lower(Trim({correo})), g: {cargo}, a: Trim({area})}},
        With(
            {{x: LookUp(RD_Participantes, Lower(Trim(Correo)) = c)}},
            IfError(
                If(
                    IsBlank(x),
                    Patch(RD_Participantes, Defaults(RD_Participantes), {{Nombre: n, Correo: c, Cargo: g, Area: a, Activo: "Sí"}}),
                    Patch(RD_Participantes, x, {{Nombre: n, Cargo: g, Area: Coalesce(a, x.Area, ""), Activo: "Sí"}})
                );
                RemoveIf(colParticipantes, Correo = c);
                Collect(colParticipantes, {{Nombre: n, Correo: c, Cargo: g, Area: Coalesce(a, x.Area, "")}});
                // En el navegador (vista previa, web) SaveData falla: su error no debe anular lo que ya quedó en el Excel.
                IfError(SaveData(colParticipantes, "rd_part"); true, false);{despues}
                Notify(n & " quedó en la lista de convocados" & If(IsBlank(Coalesce(a, x.Area)), ".", " · " & Coalesce(a, x.Area) & "."), NotificationType.Success),
                Notify("No se pudo guardar en RD_Participantes: " & FirstError.Message, NotificationType.Error)
            )
        )
    )
)'''


QUITAR_CONVOCADO = '''=If(
    !Connection.Connected,
    Notify("Sin señal: la lista de convocados se edita con conexión.", NotificationType.Warning),
    With(
        {c: ThisItem.Correo, n: ThisItem.Nombre},
        IfError(
            Patch(RD_Participantes, LookUp(RD_Participantes, Lower(Trim(Correo)) = c), {Activo: "No"});
            RemoveIf(colParticipantes, Correo = c);
            IfError(SaveData(colParticipantes, "rd_part"); true, false);
            Notify(n & " ya no está convocado (queda en el Excel con Activo = No).", NotificationType.Success),
            Notify("No se pudo quitar: " & FirstError.Message, NotificationType.Error)
        )
    )
)'''

# El conector Office 365 Users queda en la app con su nombre en español: UsuariosdeOffice365.
COL_W = '(Parent.Width - 72) / 2'          # ancho de cada columna (328 px con 1024 de pantalla)
DIR_ITEMS = ('=If(Len(Trim(txtBuscarConvEd.Text)) >= 3, '
             'UsuariosdeOffice365.SearchUserV2({searchTerm: Trim(txtBuscarConvEd.Text), top: 8}).value)')
YA_ESTA = '!IsBlank(LookUp(colParticipantes, Correo = Lower(Trim(ThisItem.Mail))))'
MANUAL_OK = ('!IsBlank(Trim(txtNomConvEd.Text)) && IsMatch(Trim(txtCorConvEd.Text), Match.Email)')
AREA_TXT = 'Trim(txtAreaConvEd.Text)'
# Editar a un convocado ya agregado: el lápiz de la fila la pinta como un compromiso nuevo en edición, pasa a flecha (cancelar)
# y carga a la persona en la columna izquierda, que cambia «agregar» por «editar», como el formulario de los compromisos nuevos.
# varConvEditEd es el correo de la persona que se edita y varAreaEditEd, el área de la casilla.
EDITANDO = '!IsBlank(varConvEditEd) && ThisItem.Correo = varConvEditEd'
SIN_EDICION = '=IsBlank(varConvEditEd)'
CON_EDICION = '=!IsBlank(varConvEditEd)'
CONV_EDIT = 'LookUp(colParticipantes, Correo = varConvEditEd)'
ABRIR_EDICION = '''=Set(varConvEditEd, ThisItem.Correo);
Set(varAreaEditEd, If(ThisItem.Area = "Sin área", "", ThisItem.Area));
Reset(txtEditNomEd);
Reset(txtEditCorEd);
Reset(txtEditCargoEd);
Reset(txtEditAreaEd)'''
# «Guardar cambios» se habilita con nombre, un correo válido y algo distinto de lo que ya está.
EDIT_OK = f'''With(
    {{p: {CONV_EDIT}}},
    !IsBlank(Trim(txtEditNomEd.Text)) && IsMatch(Trim(txtEditCorEd.Text), Match.Email) && (
        Trim(txtEditNomEd.Text) <> p.Nombre ||
        Lower(Trim(txtEditCorEd.Text)) <> p.Correo ||
        (Trim(txtEditCargoEd.Text) & "") <> (Trim(p.Cargo) & "") ||
        (Trim(txtEditAreaEd.Text) & "") <> (p.Area & "")
    )
)'''
GUARDAR_EDICION = '''=If(
    !Connection.Connected,
    Notify("Sin señal: la lista de convocados se edita con conexión.", NotificationType.Warning),
    With(
        {c0: varConvEditEd, n: Trim(txtEditNomEd.Text), c: Lower(Trim(txtEditCorEd.Text)), g: Trim(txtEditCargoEd.Text), t: Trim(txtEditAreaEd.Text)},
        // Con correo nuevo se relee el Excel antes de buscarlo: el conector puede devolver la fila de antes de un Patch
        // y aquí importa si ese correo está activo.
        If(c <> c0, Refresh(RD_Participantes));
        With(
            {
                // Si el área ya existe con otras mayúsculas se usa la que está, para no partir el grupo en dos.
                a: Coalesce(LookUp(colParticipantes, Correo <> c0 && !IsBlank(Area) && Lower(Area) = Lower(t)).Area, t),
                // Fila del correo nuevo, si ya estaba en el Excel (convocada o quitada).
                x: If(c <> c0, LookUp(RD_Participantes, Lower(Trim(Correo)) = c))
            },
            If(
                !IsBlank(x) && Lower(Trim(x.Activo)) in ["sí", "si"],
                Notify("El correo " & c & " ya es de " & x.Nombre & ", que está convocado.", NotificationType.Warning),
                IfError(
                    If(
                        c = c0,
                        Patch(RD_Participantes, LookUp(RD_Participantes, Lower(Trim(Correo)) = c0), {Nombre: n, Cargo: g, Area: a}),
                        // Correo es la clave de RD_Participantes en Power Apps y no se cambia en su fila: se crea (o se
                        // reactiva) la del correo nuevo y la anterior queda con Activo = No, como al quitar a alguien.
                        If(
                            IsBlank(x),
                            Patch(RD_Participantes, Defaults(RD_Participantes), {Nombre: n, Correo: c, Cargo: g, Area: a, Activo: "Sí"}),
                            Patch(RD_Participantes, x, {Nombre: n, Cargo: g, Area: a, Activo: "Sí"})
                        );
                        Patch(RD_Participantes, LookUp(RD_Participantes, Lower(Trim(Correo)) = c0), {Activo: "No"})
                    );
                    UpdateIf(colParticipantes, Correo = c0, {Nombre: n, Correo: c, Cargo: g, Area: a});
                    IfError(SaveData(colParticipantes, "rd_part"); true, false);
                    Set(varConvEditEd, Blank());
                    Notify("Cambios guardados: " & n & If(IsBlank(a), " · sin área.", " · " & a & "."), NotificationType.Success),
                    Notify("No se pudo guardar el cambio: " & FirstError.Message, NotificationType.Error)
                )
            )
        )
    )
)'''
# Tocar el encabezado de un área: sin edición la elige para agregar personas; editando, la pone en la casilla del área.
TOCAR_AREA = '''=If(
    IsBlank(varConvEditEd),
    Set(varAreaConvEd, If(ThisItem.Area = "Sin área", "", ThisItem.Area));
    Reset(txtAreaConvEd),
    Set(varAreaEditEd, If(ThisItem.Area = "Sin área", "", ThisItem.Area));
    Reset(txtEditAreaEd)
)'''

# Formulario de edición, en la columna izquierda mientras se edita a alguien. Cada casilla lleva su título
# arriba (en 11, 20 px) porque viene llena y no se vería el texto de ayuda. A 640 px de alto termina en Y = 516.
EDIT_CAMPOS = (('Nom', 'Nombre', f'={CONV_EDIT}.Nombre', 'Nombre', {}),
               ('Cor', 'Correo', '=varConvEditEd', 'Correo', {}),
               ('Cargo', 'Cargo', f'={CONV_EDIT}.Cargo', 'Cargo', {}),
               ('Area', 'Área (vacía: sin área)', '=varAreaEditEd', 'Área (ej.: Mina, Planta, Mantención)',
                {'MaxLength': '=40'}))
editar_conv = [label('lblEditTituloEd', '="Editar convocado"', 24, 104, COL_W, 36, size=15, color='colTexto',
                     semibold=True, nowrap=True, visible=CON_EDICION)]
for i, (campo, titulo, default, hint, extra) in enumerate(EDIT_CAMPOS):
    y = 144 + i * 68
    editar_conv += [
        label(f'lblEdit{campo}Ed', f'="{titulo}"', 24, y, COL_W, 20, size=11, color=GRIS, nowrap=True, padv=0,
              visible=CON_EDICION),
        textinput(f'txtEdit{campo}Ed', default, f'="{hint}"', 24, y + 20, COL_W, 40, size=13,
                  extra={**extra, 'Visible': CON_EDICION}),
    ]
editar_conv += [
    button('btnEditGuardarEd', 'Guardar cambios', 24, 420, f'{COL_W} - 136', 44, GUARDAR_EDICION, size=13, extra={
        'DisplayMode': f'=If({EDIT_OK}, DisplayMode.Edit, DisplayMode.Disabled)', 'Visible': CON_EDICION}),
    button('btnEditCancelarEd', 'Cancelar', f'24 + {COL_W} - 128', 420, 128, 44, '=Set(varConvEditEd, Blank())',
           fill=WHITE, color='colPrimario', size=13, bold=False, border='colPrimario', extra={'Visible': CON_EDICION}),
    label('lblEditAvisoEd', '''=If(
    IsBlank(Trim(txtEditNomEd.Text)),
    "Falta el nombre.",
    !IsMatch(Trim(txtEditCorEd.Text), Match.Email),
    "El correo no es válido.",
    Lower(Trim(txtEditCorEd.Text)) <> varConvEditEd,
    "El correo anterior queda en el Excel con Activo = No.",
    ""
)''', 24, 472, COL_W, 44, size=11, color=GRIS, valign='Top', padv=2, visible=CON_EDICION),
]

sec6 = container('conB6Ed', {'Height': '=Parent.Height - 104', 'Visible': '=varBloqueEd = 6',
                             'Width': '=Parent.Width - 296', 'X': '=272', 'Y': '=88'}, [
    label('lblB6TituloEd', '="Convocados a la reunión"', 24, 12, 'Parent.Width - 48', 40, size=20, color='colTexto',
          bold=True, nowrap=True),
    label('lblB6AyudaEd', '''=If(
    IsBlank(varConvEditEd),
    "Reciben la minuta por correo, asistan o no. Escribe el área (o toca una en la lista) y agrega a sus personas. Se guarda solo en RD_Participantes (necesita señal).",
    "Corrige los datos y toca «Guardar cambios». Para cambiar de área también puedes tocar una en la lista. Se guarda solo en RD_Participantes (necesita señal)."
)''', 24, 52, 'Parent.Width - 48', 44, size=12, color=GRIS, valign='Top', padv=2),
    # Columna izquierda: el área a la que se agrega, la búsqueda en el directorio y, si no aparece, a mano.
    # Mientras se edita a alguien (lápiz de la lista), en su lugar va el formulario de edición (más abajo).
    textinput('txtAreaConvEd', '=varAreaConvEd', '="Área (ej.: Mina, Planta, Mantención)"', 24, 104, COL_W, 40, size=13,
              extra={'MaxLength': '=40', 'Visible': SIN_EDICION}),
    textinput('txtBuscarConvEd', '', '="Buscar en el directorio: nombre o correo"', 24, 152, COL_W, 40, size=13,
              extra={'DelayOutput': '=true', 'Visible': SIN_EDICION}),
    # Filas de 72 px: a 1024 px la columna deja ~200 px de texto y los nombres y correos largos se cortarían con «…».
    # El nombre va en una línea, en 13 o en 11 si es largo, y el correo con el cargo usa hasta dos líneas de 11
    # (una línea de Open Sans mide ~1,81 veces los puntos: 13 = 23,6 px; 11 = 20 px).
    gallery('galDirConvEd', DIR_ITEMS, 24, 200, COL_W, 'Parent.Height - 200 - 176', 72, [
        label('lblDirNombreEd', '=ThisItem.DisplayName', 8, 2, f'{TW} - 8 - 116', 26,
              size='If(Len(ThisItem.DisplayName) > 24, 11, 13)', color='colTexto', semibold=True, nowrap=True, padv=0),
        label('lblDirDetalleEd', '=Coalesce(ThisItem.Mail, "sin correo") & If(IsBlank(ThisItem.JobTitle), "", " · " & ThisItem.JobTitle)',
              8, 28, f'{TW} - 8 - 116', 42, size=11, color=GRIS, valign='Top', padv=0),
        # Sin área escrita se usa el departamento del directorio. Si ya está en la lista, sus datos y su área se cambian
        # con el lápiz de la lista.
        button('btnDirAgregarEd', f'=If({YA_ESTA}, "✔ En la lista", "+ Agregar")',
               f'{TW} - 112', f'({TH} - 34) / 2', 104, 34,
               guardar_convocado('ThisItem.DisplayName', 'ThisItem.Mail', 'Coalesce(ThisItem.JobTitle, "")',
                                 f'Coalesce({AREA_TXT}, ThisItem.Department, "")'),
               fill=f'=If({YA_ESTA}, RGBA(232, 245, 233, 1), RGBA(255, 255, 255, 1))',
               color=f'=If({YA_ESTA}, colVerde, colPrimario)', size=12, bold=False,
               border=f'=If({YA_ESTA}, colVerde, colPrimario)',
               extra={'DisplayMode': f'=If(({YA_ESTA}) || IsBlank(ThisItem.Mail), DisplayMode.View, DisplayMode.Edit)'}),
        rect('sepDirEd', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1'),
    ], extra={'BorderColor': '=RGBA(225, 230, 232, 1)', 'BorderThickness': '=1', 'Visible': SIN_EDICION}),
    label('lblDirVacioEd', '''=If(
    Len(Trim(txtBuscarConvEd.Text)) < 3,
    "Escribe al menos 3 letras del nombre o del correo.",
    !Connection.Connected,
    "Sin señal: el directorio se busca con conexión.",
    "Sin resultados en el directorio. Agrégalo a mano abajo."
)''', 40, 212, f'{COL_W} - 32', 60, size=12, color=GRIS, align='Center',
          visible='=IsBlank(varConvEditEd) && (Len(Trim(txtBuscarConvEd.Text)) < 3 || IsEmpty(galDirConvEd.AllItems))'),
    label('lblManualEd', '="¿No aparece? Agrégalo a mano:"', 24, 'Parent.Height - 164', COL_W, 24, size=12,
          color='colTexto', semibold=True, visible=SIN_EDICION),
    textinput('txtNomConvEd', '', '="Nombre"', 24, 'Parent.Height - 136', f'{COL_W} * 0.55', 40, size=13,
              extra={'Visible': SIN_EDICION}),
    textinput('txtCargoConvEd', '', '="Cargo"', f'24 + {COL_W} * 0.55 + 8', 'Parent.Height - 136',
              f'{COL_W} * 0.45 - 8', 40, size=13, extra={'Visible': SIN_EDICION}),
    textinput('txtCorConvEd', '', '="Correo"', 24, 'Parent.Height - 88', f'{COL_W} - 128', 40, size=13,
              extra={'Visible': SIN_EDICION}),
    button('btnManualConvEd', '+ Agregar', f'24 + {COL_W} - 120', 'Parent.Height - 88', 120, 40,
           guardar_convocado('Trim(txtNomConvEd.Text)', 'txtCorConvEd.Text', 'Trim(txtCargoConvEd.Text)', AREA_TXT,
                             despues='\n                Reset(txtNomConvEd);\n                Reset(txtCargoConvEd);\n                Reset(txtCorConvEd);'),
           size=13, extra={'DisplayMode': f'=If({MANUAL_OK}, DisplayMode.Edit, DisplayMode.Disabled)',
                           'Visible': SIN_EDICION}),
    *editar_conv,
    # Columna derecha: convocados activos, agrupados por área.
    label('lblConvTituloEd', '="Convocados · " & CountRows(colParticipantes)', f'48 + {COL_W}', 104, COL_W, 36,
          size=15, color='colTexto', semibold=True, nowrap=True),
    # Filas de 72 px, como el directorio: el nombre del área (puede ocupar dos líneas), el nombre y el correo con el cargo,
    # en dos líneas cada uno. A la derecha, el lápiz (editar) y la × (quitar). La fila que se edita se pinta como un compromiso
    # nuevo en edición y su lápiz pasa a flecha (cancelar).
    gallery('galConvEd', CONV_VISTA, f'48 + {COL_W}', 144, COL_W, 'Parent.Height - 160', 72, [
        # Encabezado de área: al tocarlo queda escrita en el cuadro «Área» para agregar personas ahí (o, editando a
        # alguien, en la casilla del área del formulario).
        label('lblConvAreaEd', '=Upper(ThisItem.Area) & "  ·  " & ThisItem.N', 8, 6, f'{TW} - 16', f'{TH} - 10',
              size='If(Len(ThisItem.Area) > 24, 11, 13)', color='colPrimario', bold=True, valign='Bottom', padv=2,
              visible='=ThisItem.Fila = "Area"',
              extra={'OnSelect': TOCAR_AREA,
                     'Tooltip': '=If(IsBlank(varConvEditEd), "Elegir esta área para agregar personas", "Pasar a esta área")'}),
        rect('linConvAreaEd', 'colAzul', '0', f'{TH} - 2', TW, '2', extra={'Visible': '=ThisItem.Fila = "Area"'}),
        label('lblConvNombreEd', '=ThisItem.Nombre', 8, 2, f'{TW} - 8 - 80', 26,
              size='If(Len(ThisItem.Nombre) > 24, 11, 13)', color='colTexto', semibold=True, nowrap=True, padv=0,
              visible='=ThisItem.Fila = "Persona"'),
        label('lblConvDetalleEd', '=ThisItem.Correo & If(IsBlank(ThisItem.Cargo), "", " · " & ThisItem.Cargo)',
              8, 28, f'{TW} - 8 - 80', 42, size=11, color=GRIS, valign='Top', padv=0,
              visible='=ThisItem.Fila = "Persona"'),
        ctl('icoEditarConvEd', 'Classic/Icon@2.5.0', {
            'Icon': '=Icon.Edit', 'Color': '=colPrimario', 'Width': '=32', 'Height': '=32',
            'X': f'={TW} - 76', 'Y': f'=({TH} - 32) / 2', 'PaddingLeft': '=6', 'PaddingRight': '=6',
            'PaddingTop': '=6', 'PaddingBottom': '=6', 'Tooltip': '="Editar nombre, correo, cargo o área"',
            'AccessibleLabel': '="Editar a " & ThisItem.Nombre',
            'Visible': f'=ThisItem.Fila = "Persona" && !({EDITANDO})',
            'OnSelect': ABRIR_EDICION}),
        ctl('icoQuitarConvEd', 'Classic/Icon@2.5.0', {
            'Icon': '=Icon.Cancel', 'Color': '=colRojo', 'Width': '=32', 'Height': '=32',
            'X': f'={TW} - 40', 'Y': f'=({TH} - 32) / 2', 'PaddingLeft': '=6', 'PaddingRight': '=6',
            'PaddingTop': '=6', 'PaddingBottom': '=6', 'Tooltip': '="Quitar de la lista de convocados"',
            'AccessibleLabel': '="Quitar a " & ThisItem.Nombre & " de la lista de convocados"',
            'Visible': f'=ThisItem.Fila = "Persona" && !({EDITANDO})', 'OnSelect': QUITAR_CONVOCADO}),
        ctl('icoCancelarConvEd', 'Classic/Icon@2.5.0', {
            'Icon': '=Icon.Undo', 'Color': f'={GRIS}', 'Width': '=32', 'Height': '=32',
            'X': f'={TW} - 76', 'Y': f'=({TH} - 32) / 2', 'PaddingLeft': '=6', 'PaddingRight': '=6',
            'PaddingTop': '=6', 'PaddingBottom': '=6', 'Tooltip': '="Cancelar la edición"',
            'AccessibleLabel': '="Cancelar la edición de " & ThisItem.Nombre',
            'Visible': f'={EDITANDO}', 'OnSelect': '=Set(varConvEditEd, Blank())'}),
        rect('sepConvEd', 'RGBA(230, 230, 230, 1)', '0', f'{TH} - 1', TW, '1',
             extra={'Visible': '=ThisItem.Fila = "Persona"'}),
    ], extra={'BorderColor': '=RGBA(225, 230, 232, 1)', 'BorderThickness': '=1',
              'TemplateFill': f'=If({EDITANDO}, RGBA(255, 243, 224, 1), RGBA(255, 255, 255, 0))'}),
    label('lblConvVacioEd', '="Todavía no hay convocados. Si ya hay en el Excel, toca «Actualizar datos» en Inicio."',
          f'64 + {COL_W}', 170, f'{COL_W} - 32', 60, size=12, color=GRIS, align='Center',
          visible='=IsEmpty(colParticipantes)'),
])

# Confirmación para eliminar un compromiso nuevo: último hijo de la pantalla, así queda encima de todo.
confirmar_borrar = confirmar('BorrarNuevoEd', FN['confirmar_visible'], '="¿Seguro que quieres eliminar este compromiso?"',
                             FN['confirmar_detalle'], FN['confirmar_si'], FN['confirmar_no'])

base = screen('scrEditor', {'Fill': '=colFondo', 'OnVisible': ONVISIBLE + ';\n' + FN['reset_vars']},
              [encabezado, menu, siguiente, convocados_btn, sec1, sec2, sec5, sec6, confirmar_borrar])
(DEV / 'scrEditor.yaml').write_text(base, encoding='utf-8', newline='\n')
print('scrEditor.yaml:', len(base), 'caracteres,', base.count('\n'), 'líneas')

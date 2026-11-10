"""Ayudas para escribir el YAML de pantallas de Power Apps (formato de "Ver código" de Studio)."""

import base64
from pathlib import Path

LOGO = "='logo_minera_demo_blanco'"  # recurso de Multimedia de Studio
# Logo secundario (símbolo de la marca), junto al logo principal y antes del título. Va incrustado como data URI
# (256 x 256 px, ~1,8 KB): así no hay que subirlo a Multimedia de Studio. El PNG está en recursos/ de la raíz del proyecto.
ICONO = Path(__file__).resolve().parents[2] / 'recursos' / 'icono_minera_demo.png'
LOGO_AREA = '="data:image/png;base64,' + base64.b64encode(ICONO.read_bytes()).decode() + '"'


def indentar(txt, n):
    return '\n'.join((' ' * n + ln) if ln else ln for ln in txt.split('\n'))


def _bloque(v: str) -> bool:
    # Un escalar simple de YAML no puede llevar ': ' ni ' #' ni saltos de línea: ahí se usa el estilo de bloque.
    return ('\n' in v) or (': ' in v) or (' #' in v) or v.endswith(':')


def emit(name, control, props, children=None, variant=None, indent=0):
    """Devuelve las líneas YAML de un control. props: dict nombre -> fórmula (empieza con '=')."""
    pad = ' ' * indent
    out = [f"{pad}- {name}:", f"{pad}    Control: {control}"]
    if variant:
        out.append(f"{pad}    Variant: {variant}")
    out.append(f"{pad}    Properties:")
    for k in sorted(props):
        v = props[k]
        if not v.startswith('='):
            raise ValueError(f"{name}.{k} debe empezar con '=': {v[:40]}")
        if _bloque(v):
            out.append(f"{pad}      {k}: |-")
            for ln in v.split('\n'):
                out.append(f"{pad}        {ln}")
        else:
            out.append(f"{pad}      {k}: {v}")
    if children:
        out.append(f"{pad}    Children:")
        for c in children:
            out.extend(c(indent + 6))
    return out


def ctl(name, control, props, children=None, variant=None):
    """Control diferido: se indenta cuando lo emite su padre."""
    return lambda indent: emit(name, control, props, children, variant, indent)


# ---- atajos por tipo de control ----
def container(name, props, children):
    p = {'Fill': '=RGBA(255, 255, 255, 1)', 'RadiusBottomLeft': '=12', 'RadiusBottomRight': '=12',
         'RadiusTopLeft': '=12', 'RadiusTopRight': '=12'}
    p.update(props)
    return ctl(name, 'GroupContainer@1.5.0', p, children, variant='ManualLayout')


def label(name, text, x, y, w, h, size=13, color='colTexto', bold=False, semibold=False, align=None,
          fill=None, valign=None, extra=None, visible=None, pad=None, nowrap=False, padv=None):
    x, y, w, h = (str(v) for v in (x, y, w, h))
    p = {'Text': text if text.startswith('=') else f'="{text}"', 'X': x, 'Y': y, 'Width': w, 'Height': h,
         'Size': f'={size}', 'Color': color if color.startswith('=') else f'={color}'}
    for k in ('X', 'Y', 'Width', 'Height'):
        if not p[k].startswith('='):
            p[k] = f'={p[k]}'
    if bold:
        p['FontWeight'] = '=FontWeight.Bold'
    elif semibold:
        p['FontWeight'] = '=FontWeight.Semibold'
    if align:
        p['Align'] = f'=Align.{align}'
    if fill:
        p['Fill'] = fill if fill.startswith('=') else f'={fill}'
    if valign:
        p['VerticalAlign'] = f'=VerticalAlign.{valign}'
    if visible:
        p['Visible'] = visible
    if nowrap:
        p['Wrap'] = '=false'
    if pad:
        p['PaddingLeft'] = f'={pad}'
        p['PaddingRight'] = f'={pad}'
        p['PaddingTop'] = f'={pad // 2}'
        p['PaddingBottom'] = f'={pad // 2}'
    if padv is not None:
        # Relleno vertical explícito: una etiqueta de n líneas necesita n * (tamaño * 1,33) + 2 * relleno de alto.
        p['PaddingTop'] = f'={padv}'
        p['PaddingBottom'] = f'={padv}'
    if extra:
        p.update(extra)
    return ctl(name, 'Label@2.5.1', p)


def rect(name, fill, x, y, w, h, extra=None):
    p = {'Fill': fill if fill.startswith('=') else f'={fill}', 'X': x if x.startswith('=') else f'={x}',
         'Y': y if y.startswith('=') else f'={y}', 'Width': w if w.startswith('=') else f'={w}',
         'Height': h if h.startswith('=') else f'={h}'}
    if extra:
        p.update(extra)
    return ctl(name, 'Rectangle@2.3.0', p)


def button(name, text, x, y, w, h, onselect, fill='colPrimario', color='RGBA(255, 255, 255, 1)', size=14,
           bold=True, radius=8, border=None, extra=None):
    p = {'Text': text if text.startswith('=') else f'="{text}"', 'X': f'={x}', 'Y': f'={y}', 'Width': f'={w}',
         'Height': f'={h}', 'OnSelect': onselect if onselect.startswith('=') else f'={onselect}',
         'Fill': fill if fill.startswith('=') else f'={fill}', 'Color': color if color.startswith('=') else f'={color}',
         'Size': f'={size}', 'RadiusBottomLeft': f'={radius}', 'RadiusBottomRight': f'={radius}',
         'RadiusTopLeft': f'={radius}', 'RadiusTopRight': f'={radius}'}
    if bold:
        p['FontWeight'] = '=FontWeight.Bold'
    if border:
        p['BorderColor'] = border if border.startswith('=') else f'={border}'
        p['BorderThickness'] = '=1'
    if extra:
        p.update(extra)
    return ctl(name, 'Classic/Button@2.2.0', p)


def textinput(name, default, hint, x, y, w, h, size=14, multiline=False, onchange=None, extra=None):
    p = {'Default': default if default.startswith('=') else f'="{default}"',
         'HintText': hint if hint.startswith('=') else f'="{hint}"',
         'X': f'={x}', 'Y': f'={y}', 'Width': f'={w}', 'Height': f'={h}', 'Size': f'={size}'}
    if multiline:
        p['Mode'] = '=TextMode.MultiLine'
    if onchange:
        p['OnChange'] = onchange
    if extra:
        p.update(extra)
    return ctl(name, 'Classic/TextInput@2.3.2', p)


def gallery(name, items, x, y, w, h, template_size, children, padding=0, extra=None):
    p = {'Items': items, 'X': f'={x}', 'Y': f'={y}', 'Width': f'={w}', 'Height': f'={h}',
         'TemplateSize': f'={template_size}', 'TemplatePadding': f'={padding}'}
    if extra:
        p.update(extra)
    return ctl(name, 'Gallery@2.15.0', p, children, variant='BrowseLayout_Vertical_ThreeTextVariant_ver5.0')


def icon_cancel(name, onselect, color='RGBA(150, 150, 150, 1)', x='Parent.TemplateWidth - 40', y='(Parent.TemplateHeight - 32) / 2', size=32):
    return ctl(name, 'Classic/Icon@2.5.0', {'Icon': '=Icon.Cancel', 'Color': f'={color}', 'OnSelect': onselect,
                                          'Width': f'={size}', 'Height': f'={size}', 'X': f'={x}', 'Y': f'={y}'})




# Compromisos nuevos preparados en el editor (clave "nue" del JSON de RD_Preparacion). El editor los carga al abrir y el visor
# al empezar la reunión; se suben como compromisos al cerrarla. Las preparaciones sin "nue" parten con la lista vacía.
NUEVOS_PREP = '''ForAll(
    If(IsBlank(fxPrep.nue), Table(ParseJSON("[]")), Table(fxPrep.nue)) As n,
    {
        Titulo: Text(n.Value.t),
        Responsable: Text(n.Value.r),
        FechaLimite: DateValue(Text(n.Value.f)),
        IdLocal: Text(n.Value.id)
    }
)'''


def formulas_nuevos(suf, despues=''):
    """Agregar, editar y eliminar compromisos nuevos (colNuevos) en el Cierre del editor (suf='Ed') y del visor (suf='').
    Editar carga el compromiso en el formulario, el botón pasa a «Guardar cambios» y en esa fila «Editar» pasa a
    «Cancelar». Eliminar abre una ventana de confirmación.
    despues: instrucciones que se agregan al final de agregar y eliminar (en el editor marca la preparación sin guardar)."""
    ed, bo = f'varEditNuevo{suf}', f'varBorrarNuevo{suf}'
    q, r, d = f'txtNuevoQue{suf}', f'txtNuevoResp{suf}', f'dpNuevoFecha{suf}'
    reset = f'Reset({q});\nReset({r});\nReset({d})'
    actual = f'LookUp(colNuevos, IdLocal = {ed})'
    return {
        'def_que': f'=If(IsBlank({ed}), "", {actual}.Titulo)',
        'def_resp': f'=If(IsBlank({ed}), "", {actual}.Responsable)',
        'def_fecha': f'=If(IsBlank({ed}), DateAdd(Today(), 7, TimeUnit.Days), {actual}.FechaLimite)',
        'texto_agregar': f'=If(IsBlank({ed}), "+ Agregar compromiso", "Guardar cambios")',
        'agregar': f'''=If(
    IsBlank({ed}),
    Collect(
        colNuevos,
        {{
            Titulo: Trim({q}.Text),
            Responsable: Trim({r}.Text),
            FechaLimite: {d}.SelectedDate,
            IdLocal: Text(GUID())
        }}
    ),
    Patch(colNuevos, {actual}, {{Titulo: Trim({q}.Text), Responsable: Trim({r}.Text), FechaLimite: {d}.SelectedDate}})
);
Set({ed}, Blank());
{reset}{despues}''',
        'texto_editar': f'=If(ThisItem.IdLocal = {ed}, "Cancelar", "Editar")',
        'editar': f'=Set({ed}, If(ThisItem.IdLocal = {ed}, Blank(), ThisItem.IdLocal));\n{reset}',
        'eliminar': f'=Set({bo}, ThisItem.IdLocal)',
        'fill_fila': f'=If(ThisItem.IdLocal = {ed}, RGBA(255, 243, 224, 1), RGBA(255, 255, 255, 0))',
        'confirmar_visible': f'=!IsBlank({bo})',
        'confirmar_detalle': f'''=With(
    {{n: LookUp(colNuevos, IdLocal = {bo})}},
    If(Len(n.Titulo) > 100, Left(n.Titulo, 97) & "…", n.Titulo) & Char(10) & n.Responsable & " · vence " & Text(n.FechaLimite, "dd-mm")
)''',
        'confirmar_si': f'''=RemoveIf(colNuevos, IdLocal = {bo});
If({ed} = {bo}, Set({ed}, Blank()); {reset.replace(chr(10), ' ')});
Set({bo}, Blank()){despues}''',
        'confirmar_no': f'=Set({bo}, Blank())',
        'reset_vars': f'Set({ed}, Blank());\nSet({bo}, Blank())',
    }


def confirmar(pref, visible, pregunta, detalle, on_si, on_no, si='Eliminar'):
    """Ventana de confirmación que tapa toda la pantalla: va como último hijo de la pantalla para quedar encima.
    Tarjeta de 480 x 232 px: pregunta en hasta dos líneas de 15 y detalle en hasta tres de 12."""
    tarjeta = container(f'con{pref}Tarjeta', {
        'DropShadow': '=DropShadow.Bold', 'Height': '=232', 'Width': '=480',
        'X': '=(Parent.Width - 480) / 2', 'Y': '=(Parent.Height - 232) / 2'}, [
        label(f'lbl{pref}Pregunta', pregunta, 24, 20, 'Parent.Width - 48', 56, size=15, bold=True, valign='Top', padv=2),
        label(f'lbl{pref}Detalle', detalle, 24, 80, 'Parent.Width - 48', 64, size=12, color='RGBA(90, 98, 104, 1)',
              valign='Top', padv=2),
        button(f'btn{pref}Si', si, 'Parent.Width - 24 - 280 - 12', 'Parent.Height - 72', 140, 48, on_si, fill='colRojo'),
        button(f'btn{pref}No', 'Cancelar', 'Parent.Width - 24 - 140', 'Parent.Height - 72', 140, 48, on_no,
               fill='RGBA(255, 255, 255, 1)', color='colTexto', border='RGBA(160, 160, 160, 1)', bold=False),
    ])
    return container(f'con{pref}', {
        'Fill': '=RGBA(0, 0, 0, 0.45)', 'Height': '=Parent.Height', 'Visible': visible, 'Width': '=Parent.Width',
        'X': '=0', 'Y': '=0', 'RadiusBottomLeft': '=0', 'RadiusBottomRight': '=0', 'RadiusTopLeft': '=0',
        'RadiusTopRight': '=0'}, [tarjeta])


def screen(name, props, children):
    out = ["Screens:", f"  {name}:", "    Properties:"]
    for k in sorted(props):
        v = props[k]
        if _bloque(v):
            out.append(f"      {k}: |-")
            for ln in v.split('\n'):
                out.append(f"        {ln}")
        else:
            out.append(f"      {k}: {v}")
    out.append("    Children:")
    for c in children:
        out.extend(c(6))
    return '\n'.join(out) + '\n'

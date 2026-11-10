# -*- coding: utf-8 -*-
"""Identificador correlativo de actividades.

Formato letra-número(2 dígitos)-año(2 dígitos), p. ej. A-01-yy. El correlativo recorre A-01 … A-99, luego B-00,
B-01 … y reinicia cada año en A-01. generar_datos.py usa la misma regla (función id_actividad).
"""
ID_REGEX = r"[A-Z]-\d{2}-\d{2}"
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def id_actividad(n, yy):
    """n = correlativo del año (1, 2, …); yy = año en dos dígitos como texto."""
    return f"{LETRAS[n // 100]}-{n % 100:02d}-{yy}"


# Fórmula Power Fx equivalente: calcula el siguiente ID a partir del máximo del año en curso.
NEXT_ID = "\n".join([
    'With(',
    '    {yy: Text(Today(), "yy"), letras: "' + LETRAS + '"},',
    '    With(',
    '        {',
    '            n: Coalesce(',
    '                Max(',
    '                    Filter(Actividades, IsMatch(ID, "' + ID_REGEX + '") && Right(ID, 2) = yy),',
    '                    (Find(Left(ID, 1), letras) - 1) * 100 + Value(Mid(ID, 3, 2))',
    '                ),',
    '                0',
    '            ) + 1',
    '        },',
    '        Mid(letras, RoundDown(n / 100, 0) + 1, 1) & "-" & Text(Mod(n, 100), "00") & "-" & yy',
    '    )',
    ')'])

"""Convierte una fórmula (o varias, App.Formulas/OnStart) del formato del YAML / en-US al formato que
espera la barra de fórmulas de Studio en español: argumentos con ';', encadenado con ';;'.
Deja intactos los textos entre comillas ("...", con "" como comilla escapada) y los comentarios //.

Uso: python fx_a_studio.py entrada.fx salida.txt
"""
import sys


def convertir(texto: str) -> str:
    out = []
    i = 0
    n = len(texto)
    en_texto = False
    while i < n:
        c = texto[i]
        if en_texto:
            out.append(c)
            if c == '"':
                if i + 1 < n and texto[i + 1] == '"':  # comilla escapada ""
                    out.append('"')
                    i += 1
                else:
                    en_texto = False
        else:
            if c == '"':
                en_texto = True
                out.append(c)
            elif c == '/' and i + 1 < n and texto[i + 1] == '/':  # comentario hasta fin de línea
                j = texto.find('\n', i)
                j = n if j == -1 else j
                out.append(texto[i:j])
                i = j - 1
            elif c == ';':
                out.append(';;')
            elif c == ',':
                out.append(';')
            else:
                out.append(c)
        i += 1
    return ''.join(out)


if __name__ == '__main__':
    src = open(sys.argv[1], encoding='utf-8').read().replace('\r\n', '\n')
    res = convertir(src).replace('\n', '\r\n')
    open(sys.argv[2], 'w', encoding='utf-8', newline='').write(res)
    print(f'{len(src)} -> {len(res)} caracteres')

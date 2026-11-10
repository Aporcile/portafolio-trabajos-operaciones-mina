"""Compara una pantalla copiada de Studio («…» › Copiar, luego Get-Clipboard) con el YAML local, control por control.

Uso:  python diff_pantalla.py studio.yaml local.yaml [--todo]

Studio omite las propiedades que valen su valor por defecto, así que «solo en local» casi siempre son valores por defecto
(se muestran contados; con --todo se listan). Lo que importa:
  - controles que están en un lado y no en el otro;
  - propiedades con distinto valor en los dos lados (se comparan sin espacios ni saltos de línea de más);
  - propiedades «solo en Studio» (cambios que alguien hizo a mano o que Studio agregó).
Resultado «0 diferencias» = el control coincide en todo lo que Studio guarda.
"""
import re
import sys

import yaml


def cargar(ruta):
    txt = open(ruta, encoding='utf-8-sig').read()
    d = yaml.safe_load(txt)
    pantallas = d['Screens']
    nombre = next(iter(pantallas))
    return nombre, pantallas[nombre]


def aplanar(nodo, ruta, salida):
    """salida[nombre] = {'control':…, 'variant':…, 'props': {…}, 'ruta': 'padre/hijo'}"""
    for item in nodo.get('Children') or []:
        (nombre, cuerpo), = item.items()
        salida[nombre] = {'control': cuerpo.get('Control'), 'variant': cuerpo.get('Variant'),
                          'props': dict(cuerpo.get('Properties') or {}), 'ruta': ruta}
        aplanar(cuerpo, f'{ruta}/{nombre}', salida)


def norm(v):
    v = str(v)
    v = re.sub(r'\s+', ' ', v).strip()
    # Studio escribe «( » y « )» sin espacios de más en algunos casos: se ignoran los espacios junto a signos.
    v = re.sub(r'\s*([(),;])\s*', r'\1', v)
    return v


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    todo = '--todo' in sys.argv
    if len(args) != 2:
        print(__doc__)
        sys.exit(2)
    n1, p1 = cargar(args[0])
    n2, p2 = cargar(args[1])
    a, b = {}, {}
    aplanar(p1, n1, a)
    aplanar(p2, n2, b)
    print(f'Studio: {n1}, {len(a)} controles | local: {n2}, {len(b)} controles')
    solo_a = [k for k in a if k not in b]
    solo_b = [k for k in b if k not in a]
    if solo_a:
        print('\nControles solo en Studio:', ', '.join(solo_a))
    if solo_b:
        print('\nControles solo en local:', ', '.join(solo_b))
    dif = 0
    n_def = 0
    # Propiedades de la pantalla misma.
    pa, pb = dict(p1.get('Properties') or {}), dict(p2.get('Properties') or {})
    a[n1 + ' (pantalla)'] = {'control': 'Screen', 'variant': None, 'props': pa, 'ruta': ''}
    b[n1 + ' (pantalla)'] = {'control': 'Screen', 'variant': None, 'props': pb, 'ruta': ''}
    for k in a:
        if k not in b:
            continue
        x, y = a[k], b[k]
        if x['control'] != y['control']:
            dif += 1
            print(f'\n[{k}] Control: Studio={x["control"]} local={y["control"]}')
        for p in sorted(set(x['props']) | set(y['props'])):
            if p in x['props'] and p in y['props']:
                if norm(x['props'][p]) != norm(y['props'][p]):
                    dif += 1
                    print(f'\n[{k}].{p} DIFERENTE\n  Studio: {str(x["props"][p])[:300]!r}\n  local : {str(y["props"][p])[:300]!r}')
            elif p in x['props']:
                dif += 1
                print(f'\n[{k}].{p} SOLO EN STUDIO: {str(x["props"][p])[:300]!r}')
            else:
                n_def += 1
                if todo:
                    print(f'[{k}].{p} solo en local: {str(y["props"][p])[:120]!r}')
    print(f'\n{dif} diferencias (más {n_def} propiedades solo en local, normalmente valores por defecto que Studio omite).')


if __name__ == '__main__':
    main()

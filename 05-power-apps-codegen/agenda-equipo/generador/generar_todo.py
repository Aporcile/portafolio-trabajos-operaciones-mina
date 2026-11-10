# -*- coding: utf-8 -*-
"""Regenera todos los YAML de la app en ../yaml y los verifica.

Uso:  python generar_todo.py
"""
import importlib
import sys

sys.dont_write_bytecode = True

# Cada módulo expone generar() y escribe uno o más archivos en ../yaml
MODULOS = ["gen_encabezado", "gen_pestanas_y_vistas", "gen_tablero_por_area", "gen_highlights", "gen_revisar", "gen_historial", "gen_paneles"]

# Orden de capas al pegar en la pantalla (el primero queda al fondo)
ORDEN_DE_PEGADO = ["01_encabezado.yaml", "01b_pestanas.yaml", "02_tablero_por_area.yaml", "04_vista_tablero.yaml", "05_vista_lista.yaml",
                   "06_vista_persona.yaml", "07_vista_highlights.yaml", "08_vista_revisar.yaml", "09_vista_historial.yaml", "03_paneles.yaml"]


def main():
    for nombre in MODULOS:
        importlib.import_module(nombre).generar()
    print("\nOrden de pegado en la pantalla (de fondo a frente):")
    for i, archivo in enumerate(ORDEN_DE_PEGADO, 1):
        print(f"  {i:2d}. {archivo}")
    import verificar_yaml
    print()
    errores, n_archivos, n_controles = verificar_yaml.verificar()
    print(f"Verificación: {n_archivos} archivos, {n_controles} controles, {len(errores)} errores")
    for e in errores[:50]:
        print("  -", e)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

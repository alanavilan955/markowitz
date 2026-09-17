"""Paquete de análisis de eficiencia de producción y frontera eficiente por línea.

Este archivo convierte `src/` en un paquete importable. Sin él, `from src import graficas`
falla con ModuleNotFoundError en entornos donde la carpeta de la app no está en sys.path,
como Streamlit Community Cloud.
"""

__all__ = ["analitica", "datos", "graficas", "markowitz"]

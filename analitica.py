"""Correlación y regresión lineal simple (MCO) sobre KPIs de eficiencia y retornos."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

VARIABLES_KPI = {
    "OEE": "OEE",
    "Disponibilidad": "Disponibilidad",
    "Rendimiento": "Rendimiento",
    "Calidad": "Calidad",
    "Paro_No_Planificado_h": "Paro no planificado (h)",
    "Cumplimiento_Plan": "Cumplimiento de plan",
    "Pct_Horas_Extra": "% horas extra",
    "Lbs_por_Hora_MO": "Lbs por hora de MO",
    "YTP_Pct": "YTP",
    "MUV_USD": "MUV (USD)",
    "Costo_Conversion_USD_lb": "Conversión (USD/lb)",
    "Margen_Contribucion_Pct": "Margen de contribución %",
    "Retorno_Semanal_Capital": "Retorno semanal sobre capital",
}


def centrar_por_linea(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Resta la media de cada línea a cada variable.

    Mide la relación dentro de cada línea. Sin este paso, las diferencias estructurales
    entre líneas (por ejemplo, queso crema con OEE bajo y margen bajo) pueden producir
    correlaciones que no existen semana a semana.
    """
    out = df.copy()
    out[columnas] = df[columnas] - df.groupby("Linea_ID")[columnas].transform("mean")
    return out


def correlacion(data: pd.DataFrame, metodo: str = "pearson") -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Devuelve matriz de coeficientes, matriz de p-values y número de observaciones."""
    data = data.dropna()
    cols = list(data.columns)
    coef = data.corr(method=metodo)
    pval = pd.DataFrame(np.nan, index=cols, columns=cols)
    prueba = stats.pearsonr if metodo == "pearson" else stats.spearmanr
    for i, a in enumerate(cols):
        pval.loc[a, a] = 0.0
        for b in cols[i + 1:]:
            if data[a].nunique() > 1 and data[b].nunique() > 1:
                p = float(prueba(data[a], data[b])[1])
                pval.loc[a, b] = pval.loc[b, a] = p
    return coef, pval, len(data)


def regresion_simple(x, y) -> dict:
    """MCO y = a + b·x con R², p-value de la pendiente e intervalo de confianza de 95%."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(x)
    vacio = {"n": n, "pendiente": np.nan, "intercepto": np.nan, "r2": np.nan, "p_value": np.nan,
             "ic95_inf": np.nan, "ic95_sup": np.nan, "error_std": np.nan}
    if n < 3 or np.ptp(x) == 0:
        return vacio
    r = stats.linregress(x, y)
    t = stats.t.ppf(0.975, n - 2)
    return {"n": n, "pendiente": r.slope, "intercepto": r.intercept, "r2": r.rvalue ** 2, "p_value": r.pvalue,
            "ic95_inf": r.slope - t * r.stderr, "ic95_sup": r.slope + t * r.stderr, "error_std": r.stderr}


def regresion_por_linea(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    filas = [{"Linea_ID": lid, **regresion_simple(g[x], g[y])} for lid, g in df.groupby("Linea_ID")]
    filas.append({"Linea_ID": "Todas (agrupado)", **regresion_simple(df[x], df[y])})
    return pd.DataFrame(filas)


def beta_contra_planta(ret: pd.DataFrame, planta: pd.Series) -> pd.DataFrame:
    """Regresión del retorno de cada línea contra el retorno de la planta (modelo de mercado).

    Beta > 1: la línea amplifica los movimientos de la planta.
    R² bajo: la variación de la línea es propia y diversifica el portafolio.
    """
    base = planta.reindex(ret.index)
    filas = []
    for lid in ret.columns:
        r = regresion_simple(base, ret[lid])
        filas.append({"Linea_ID": lid, "Beta": r["pendiente"], "Alfa_semanal": r["intercepto"], "R2": r["r2"],
                      "p_value": r["p_value"], "IC95_inf": r["ic95_inf"], "IC95_sup": r["ic95_sup"], "n": r["n"]})
    return pd.DataFrame(filas)

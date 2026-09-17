"""Frontera eficiente de Markowitz con límites de peso por línea.

Supuesto clave: el retorno por dólar de capital de cada línea es constante al cambiar la
asignación. Fuera de un rango cercano a la operación actual no se cumple; por eso los pesos
tienen mínimo y máximo.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pandas as pd
from scipy.optimize import minimize

PERIODOS_ANIO = 52


class ErrorModelo(ValueError):
    """Configuración infactible o datos insuficientes."""


@dataclass
class ResultadoMarkowitz:
    retornos: pd.DataFrame
    mu: pd.Series
    cov: pd.DataFrame
    pesos: pd.DataFrame
    metricas: pd.DataFrame
    frontera: pd.DataFrame
    reasignacion: pd.DataFrame
    tasa_minima: float


def filtrar_cierre_diciembre(ret: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(ret.index)
    return ret[~((idx.month == 12) & (idx.day >= 22))]


def metricas(w, mu, cov, rf):
    r = float(w @ mu)
    s = float(np.sqrt(w @ cov @ w))
    return r, s, (r - rf) / s if s > 0 else np.nan


def _optimizar(objetivo, n, bounds, restricciones, w0=None):
    w0 = np.full(n, 1.0 / n) if w0 is None else w0
    res = minimize(objetivo, w0, method="SLSQP", bounds=bounds, constraints=restricciones,
                   options={"maxiter": 1000, "ftol": 1e-10})
    # SLSQP puede reportar "Positive directional derivative" ya en el óptimo cuando la función
    # es plana; se acepta la solución si cumple restricciones y límites.
    factible = (all(abs(c["fun"](res.x)) < 1e-6 for c in restricciones)
                and all(lo - 1e-8 <= v <= hi + 1e-8 for v, (lo, hi) in zip(res.x, bounds)))
    if not (res.success or factible):
        raise ErrorModelo(f"El optimizador no convergió: {res.message}")
    return res.x


def optimizar(ret: pd.DataFrame, capital: pd.Series, tasa_minima: float = 0.10, peso_min: float = 0.05,
              peso_max: float = 0.30, puntos: int = 40) -> ResultadoMarkowitz:
    n = ret.shape[1]
    if n < 2:
        raise ErrorModelo("Se necesitan al menos 2 líneas.")
    if len(ret) <= n:
        raise ErrorModelo(f"Hay {len(ret)} semanas y {n} líneas; la covarianza no es estimable.")
    if peso_min > peso_max or peso_min * n > 1 + 1e-9 or peso_max * n < 1 - 1e-9:
        raise ErrorModelo(f"Límites infactibles para {n} líneas: se requiere peso_min x n <= 1 <= peso_max x n.")

    lineas = list(ret.columns)
    mu_s = ret.mean() * PERIODOS_ANIO
    cov_df = ret.cov() * PERIODOS_ANIO
    mu, cov = mu_s.values, cov_df.values
    k = 1.0 / np.mean(np.diag(cov))  # normaliza la escala de la varianza para SLSQP
    bounds = [(peso_min, peso_max)] * n
    suma1 = {"type": "eq", "fun": lambda w: w.sum() - 1}

    cap = capital.reindex(lineas).astype(float)
    w_act = (cap / cap.sum()).values
    w_mv = _optimizar(lambda w: k * (w @ cov @ w), n, bounds, [suma1])
    w_ms = _optimizar(lambda w: -(w @ mu - tasa_minima) / np.sqrt(w @ cov @ w), n, bounds, [suma1])
    w_rmax = _optimizar(lambda w: -(w @ mu), n, bounds, [suma1])

    filas, w_prev = [], w_mv
    for obj in np.linspace(w_mv @ mu, w_rmax @ mu, puntos):
        cons = [suma1, {"type": "eq", "fun": lambda w, t=obj: w @ mu - t}]
        try:
            w_prev = _optimizar(lambda w: k * (w @ cov @ w), n, bounds, cons, w0=w_prev)
            filas.append(w_prev)
        except ErrorModelo:
            continue

    claves = {"Actual": w_act, "Minima_Varianza": w_mv, "Maximo_Sharpe": w_ms}
    pesos = pd.DataFrame(claves, index=lineas)
    met = pd.DataFrame({c: metricas(w, mu, cov, tasa_minima) for c, w in claves.items()},
                       index=["Retorno_Anual", "Riesgo_Anual", "Sharpe"]).T
    fr = pd.DataFrame(filas, columns=lineas)
    m = np.array([metricas(w, mu, cov, tasa_minima) for w in filas])
    fr.insert(0, "Sharpe", m[:, 2])
    fr.insert(0, "Riesgo_Anual", m[:, 1])
    fr.insert(0, "Retorno_Anual", m[:, 0])
    reasig = pesos.mul(cap.sum()).sub(cap, axis=0)
    reasig.columns = [f"Delta_Capital_USD_{c}" for c in reasig.columns]
    return ResultadoMarkowitz(ret, mu_s, cov_df, pesos, met, fr, reasig, tasa_minima)


def portafolios_aleatorios(mu, cov, n_sim=4000, semilla=7):
    rng = np.random.default_rng(semilla)
    w = rng.dirichlet(np.ones(len(mu)), n_sim)
    return w @ mu, np.sqrt(np.einsum("ij,jk,ik->i", w, cov, w))


def exportar_excel(res: ResultadoMarkowitz, config: dict, extras: dict | None = None) -> bytes:
    buf = BytesIO()
    sd = np.sqrt(np.diag(res.cov))
    resumen = pd.DataFrame({"Retorno_Anual": res.mu, "Riesgo_Anual": sd,
                            "Sharpe_vs_Tasa_Minima": (res.mu - res.tasa_minima) / sd})
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(list(config.items()), columns=["Parametro", "Valor"]).to_excel(
            xw, sheet_name="Configuracion", index=False)
        resumen.to_excel(xw, sheet_name="Resumen_Lineas")
        res.metricas.to_excel(xw, sheet_name="Metricas_Portafolios")
        pd.concat([res.pesos, res.reasignacion], axis=1).to_excel(xw, sheet_name="Pesos_y_Reasignacion")
        res.frontera.to_excel(xw, sheet_name="Frontera", index=False)
        res.cov.to_excel(xw, sheet_name="Covarianza_Anual")
        res.retornos.corr().to_excel(xw, sheet_name="Correlacion_Retornos")
        res.retornos.to_excel(xw, sheet_name="Retornos_Usados")
        for nombre, tabla in (extras or {}).items():
            tabla.to_excel(xw, sheet_name=nombre[:31], index=not isinstance(tabla.index, pd.RangeIndex))
    return buf.getvalue()

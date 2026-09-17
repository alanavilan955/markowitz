"""Gráficas Plotly usadas por la app de Streamlit."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analitica import regresion_simple
from .markowitz import ResultadoMarkowitz, metricas, portafolios_aleatorios

TINTA = "#1B2A41"
ACERO = "#3E6D9C"
VERDE = "#2E7D5B"
AMBAR = "#C98A1B"
ROJO = "#A23B3B"
REJILLA = "#D9DEE5"
COLORES_LINEA = ["#1B2A41", "#3E6D9C", "#7FA7C9", "#2E7D5B", "#8BB174", "#C98A1B", "#A23B3B", "#7A6A9E"]

ESCALA_CORR = [[0.0, ROJO], [0.5, "#F4F5F7"], [1.0, ACERO]]


def _layout(fig, titulo, x=None, y=None, alto=520):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=16, color=TINTA)), height=alto,
        plot_bgcolor="white", paper_bgcolor="white", font=dict(color=TINTA, size=12),
        margin=dict(l=60, r=20, t=60, b=50), legend=dict(bgcolor="rgba(255,255,255,0.8)"),
    )
    fig.update_xaxes(title=x, gridcolor=REJILLA, zeroline=False)
    fig.update_yaxes(title=y, gridcolor=REJILLA, zeroline=False)
    return fig


def color_linea(lineas):
    return {lid: COLORES_LINEA[i % len(COLORES_LINEA)] for i, lid in enumerate(sorted(lineas))}


def heatmap_correlacion(coef: pd.DataFrame, pval: pd.DataFrame, etiquetas: dict | None = None,
                        titulo="Matriz de correlación", alfa=0.05):
    etiquetas = etiquetas or {}
    nombres = [etiquetas.get(c, c) for c in coef.columns]
    texto = np.empty(coef.shape, dtype=object)
    for i in range(coef.shape[0]):
        for j in range(coef.shape[1]):
            marca = "" if i == j or pd.isna(pval.iat[i, j]) or pval.iat[i, j] < alfa else " (ns)"
            texto[i, j] = f"{coef.iat[i, j]:.2f}{marca}"
    fig = go.Figure(go.Heatmap(
        z=coef.values, x=nombres, y=nombres, zmin=-1, zmax=1, colorscale=ESCALA_CORR,
        text=texto, texttemplate="%{text}", textfont=dict(size=10),
        customdata=pval.values, hovertemplate="%{y} vs %{x}<br>r = %{z:.3f}<br>p = %{customdata:.4f}<extra></extra>",
        colorbar=dict(title="r"),
    ))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, titulo, alto=max(420, 38 * len(nombres) + 160))


def dispersion_regresion(df: pd.DataFrame, x: str, y: str, por_linea: bool, etiqueta_x: str, etiqueta_y: str):
    fig = go.Figure()
    grupos = df.groupby("Linea_ID") if por_linea else [("Todas", df)]
    colores = color_linea(df["Linea_ID"].unique())
    for lid, g in grupos:
        c = colores.get(lid, ACERO)
        fig.add_trace(go.Scatter(x=g[x], y=g[y], mode="markers", name=str(lid), marker=dict(color=c, size=6, opacity=0.55),
                                 hovertemplate=f"{lid}<br>{etiqueta_x}: %{{x:.4g}}<br>{etiqueta_y}: %{{y:.4g}}<extra></extra>"))
        r = regresion_simple(g[x], g[y])
        if np.isfinite(r["pendiente"]):
            xs = np.linspace(g[x].min(), g[x].max(), 50)
            fig.add_trace(go.Scatter(x=xs, y=r["intercepto"] + r["pendiente"] * xs, mode="lines",
                                     line=dict(color=c, width=2.5), showlegend=False,
                                     hovertemplate=f"{lid}: R² = {r['r2']:.3f}<extra></extra>"))
    return _layout(fig, f"Regresión MCO: {etiqueta_y} contra {etiqueta_x}", etiqueta_x, etiqueta_y)


def barras_beta(tabla: pd.DataFrame):
    t = tabla.sort_values("Beta")
    err_sup = t["IC95_sup"] - t["Beta"]
    err_inf = t["Beta"] - t["IC95_inf"]
    colores = [AMBAR if b > 1 else ACERO for b in t["Beta"]]
    fig = go.Figure(go.Bar(x=t["Beta"], y=t["Linea_ID"], orientation="h", marker_color=colores,
                           error_x=dict(type="data", array=err_sup, arrayminus=err_inf, color=TINTA),
                           customdata=t["R2"], hovertemplate="%{y}<br>Beta = %{x:.2f}<br>R² = %{customdata:.2f}<extra></extra>"))
    fig.add_vline(x=1, line_dash="dash", line_color=TINTA)
    return _layout(fig, "Beta de cada línea contra el retorno de la planta (IC 95%)", "Beta", None, alto=420)


def dispersion_beta(ret: pd.DataFrame, planta: pd.Series, linea: str):
    x, y = planta.reindex(ret.index), ret[linea]
    r = regresion_simple(x, y)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="markers", marker=dict(color=ACERO, size=7, opacity=0.7),
                               text=[d.strftime("%Y-%m-%d") for d in ret.index],
                               hovertemplate="Semana %{text}<br>Planta %{x:.3%}<br>Línea %{y:.3%}<extra></extra>",
                               name="Semanas"))
    xs = np.linspace(x.min(), x.max(), 50)
    fig.add_trace(go.Scatter(x=xs, y=r["intercepto"] + r["pendiente"] * xs, mode="lines", line=dict(color=AMBAR, width=3),
                             name=f"Beta {r['pendiente']:.2f}, R² {r['r2']:.2f}"))
    fig.update_xaxes(tickformat=".2%")
    fig.update_yaxes(tickformat=".2%")
    return _layout(fig, f"{linea} contra planta", "Retorno semanal planta", f"Retorno semanal {linea}", alto=420)


def frontera(res: ResultadoMarkowitz):
    mu, cov = res.mu.values, res.cov.values
    r_sim, s_sim = portafolios_aleatorios(mu, cov)
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=s_sim, y=r_sim, mode="markers", name="Portafolios aleatorios sin límites",
                               marker=dict(color="#AEB8C4", size=3, opacity=0.35), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=res.frontera["Riesgo_Anual"], y=res.frontera["Retorno_Anual"], mode="lines",
                             line=dict(color=TINTA, width=3), name="Frontera eficiente con límites",
                             hovertemplate="Riesgo %{x:.3%}<br>Retorno %{y:.2%}<extra></extra>"))
    sd = np.sqrt(np.diag(cov))
    fig.add_trace(go.Scatter(x=sd, y=mu, mode="markers+text", text=list(res.mu.index), textposition="top right",
                             marker=dict(color=ROJO, size=9), name="Líneas individuales",
                             hovertemplate="%{text}<br>Riesgo %{x:.3%}<br>Retorno %{y:.2%}<extra></extra>"))
    estilos = {"Actual": ("diamond", "#7A6A9E"), "Minima_Varianza": ("square", VERDE), "Maximo_Sharpe": ("star", AMBAR)}
    for nombre in res.pesos.columns:
        r, s, _ = metricas(res.pesos[nombre].values, mu, cov, res.tasa_minima)
        simb, c = estilos[nombre]
        fig.add_trace(go.Scatter(x=[s], y=[r], mode="markers", name=nombre.replace("_", " "),
                                 marker=dict(symbol=simb, size=18, color=c, line=dict(color=TINTA, width=1.5)),
                                 hovertemplate=f"{nombre}<br>Riesgo %{{x:.3%}}<br>Retorno %{{y:.2%}}<extra></extra>"))
    fig.update_xaxes(tickformat=".2%")
    fig.update_yaxes(tickformat=".1%")
    return _layout(fig, "Frontera eficiente del portafolio de líneas", "Riesgo anualizado", "Retorno anualizado sobre capital", 560)


def barras_pesos(res: ResultadoMarkowitz):
    fig = go.Figure()
    colores = {"Actual": "#7A6A9E", "Minima_Varianza": VERDE, "Maximo_Sharpe": AMBAR}
    for c in res.pesos.columns:
        fig.add_trace(go.Bar(x=res.pesos.index, y=res.pesos[c], name=c.replace("_", " "), marker_color=colores[c],
                             hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat=".0%")
    return _layout(fig, "Asignación de capital por línea", None, "Peso", alto=420)


def tendencia(df: pd.DataFrame, columna: str, etiqueta: str, formato=".0%"):
    fig = go.Figure()
    colores = color_linea(df["Linea_ID"].unique())
    for lid, g in df.groupby("Linea_ID"):
        suav = g.set_index("Semana_Inicio")[columna].rolling(4, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=suav.index, y=suav.values, mode="lines", name=lid, line=dict(color=colores[lid], width=2)))
    fig.update_yaxes(tickformat=formato)
    return _layout(fig, f"{etiqueta} por línea (promedio móvil de 4 semanas)", None, etiqueta, alto=420)

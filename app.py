"""Tablero de eficiencia de producción, correlación, regresión y frontera eficiente.

Ejecutar localmente:
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:  # Streamlit Cloud no siempre agrega la carpeta de la app a sys.path
    sys.path.insert(0, str(RAIZ))

try:
    import pandas as pd

    from src import graficas as gr
    from src.analitica import (VARIABLES_KPI, beta_contra_planta, centrar_por_linea, correlacion,
                               regresion_por_linea)
    from src.datos import ErrorDatos, calcular_kpis, cargar_libro, matriz, resumen_lineas, retorno_planta
    from src.markowitz import ErrorModelo, exportar_excel, filtrar_cierre_diciembre, optimizar
except ModuleNotFoundError as e:  # el mensaje de Streamlit Cloud sale censurado; aquí se ve completo
    st.error(f"Falta el módulo '{e.name}'. Revisa requirements.txt y que la carpeta src/ con su "
             f"__init__.py esté en el repositorio.")
    st.code(f"Módulo: {e.name}\n"
            f"Carpeta de la app: {RAIZ}\n"
            f"Contenido: {sorted(p.name for p in RAIZ.iterdir())}\n"
            f"Contenido de src/: {sorted(p.name for p in (RAIZ / 'src').iterdir()) if (RAIZ / 'src').is_dir() else 'no existe'}\n"
            f"Python: {sys.version}")
    st.stop()

RUTA_DATOS = Path(__file__).parent / "data" / "BD_Eficiencia_Produccion_Planta_Alimentos.xlsx"

st.set_page_config(page_title="Eficiencia de planta y frontera eficiente", layout="wide")


@st.cache_data(show_spinner="Calculando KPIs")
def preparar(contenido: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    libro = cargar_libro(contenido)
    return calcular_kpis(libro), libro["parametros"]


def pct(v, d=1):
    return f"{v:.{d}%}"


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.header("Datos")
    archivo = st.file_uploader("Libro de Excel con la estructura del modelo", type=["xlsx"])
    if archivo is None:
        if not RUTA_DATOS.exists():
            st.error(f"No se encontró {RUTA_DATOS.name} en /data. Sube un libro para continuar.")
            st.stop()
        contenido = RUTA_DATOS.read_bytes()
        st.caption("Usando la base sintética incluida en el repositorio.")
    else:
        contenido = archivo.getvalue()

try:
    kpis, parametros = preparar(contenido)
except (ErrorDatos, ValueError, KeyError) as e:
    st.error(f"El libro no se pudo procesar: {e}")
    st.stop()

with st.sidebar:
    lineas_todas = sorted(kpis["Linea_ID"].unique())
    lineas = st.multiselect("Líneas", lineas_todas, default=lineas_todas,
                            format_func=lambda l: f"{l} {parametros.loc[l, 'Linea']}")
    fmin, fmax = kpis["Semana_Inicio"].min().date(), kpis["Semana_Inicio"].max().date()
    rango = st.date_input("Semanas (fecha de inicio)", value=(fmin, fmax), min_value=fmin, max_value=fmax)
    excluir_dic = st.checkbox("Excluir semanas de cierre de diciembre", value=False,
                              help="Quita semanas que inician del 22 al 31 de diciembre.")

    st.header("Frontera eficiente")
    tasa_minima = st.number_input("Tasa mínima anual sobre capital", 0.0, 1.0, 0.10, 0.01, format="%.2f")
    peso_min = st.slider("Peso mínimo por línea", 0.0, 0.20, 0.05, 0.01)
    peso_max = st.slider("Peso máximo por línea", 0.10, 1.0, 0.30, 0.01)
    puntos = st.slider("Puntos de la frontera", 10, 80, 40, 5)
    if lineas:
        st.caption(f"Con {len(lineas)} líneas: peso mínimo ≤ {1 / len(lineas):.1%} y peso máximo ≥ {1 / len(lineas):.1%}.")

if len(lineas) < 2:
    st.warning("Selecciona al menos dos líneas.")
    st.stop()
if not isinstance(rango, (tuple, list)) or len(rango) != 2:
    st.info("Elige fecha inicial y final.")
    st.stop()

df = kpis[kpis["Linea_ID"].isin(lineas)
          & kpis["Semana_Inicio"].between(pd.Timestamp(rango[0]), pd.Timestamp(rango[1]))]
if excluir_dic:
    df = df[~((df["Semana_Inicio"].dt.month == 12) & (df["Semana_Inicio"].dt.day >= 22))]
if df.empty:
    st.warning("No hay registros con esos filtros.")
    st.stop()

ret = matriz(df, "Retorno_Semanal_Capital")
planta = retorno_planta(df)

# ------------------------------------------------------------------ encabezado
st.title("Eficiencia de planta y asignación de capital por línea")
n_sem = df["Semana_Inicio"].nunique()
st.caption(f"{len(lineas)} líneas, {n_sem} semanas, del {df['Semana_Inicio'].min():%Y-%m-%d} "
           f"al {df['Semana_Inicio'].max():%Y-%m-%d}. Moneda USD, volumen en lbs.")

margen_pct = df["Margen_Contribucion_USD"].sum() / df["Ingreso_Neto_USD"].sum()
ytp = df["Perdida_Abs_Real_USD"].sum() / df["Costo_Perfeccion_USD"].sum()
ret_anual = df["Margen_Contribucion_USD"].sum() / df.groupby("Linea_ID")["Capital_Empleado_USD"].first().sum() * 52 / n_sem
c1, c2, c3, c4 = st.columns(4)
c1.metric("OEE promedio", pct(df["OEE"].mean()))
c2.metric("Yield loss to perfection", pct(ytp, 2))
c3.metric("Margen de contribución", pct(margen_pct))
c4.metric("Retorno anual sobre capital", pct(ret_anual))

tab_planta, tab_corr, tab_reg, tab_front, tab_datos = st.tabs(
    ["Planta", "Correlación", "Regresión", "Frontera eficiente", "Datos y descargas"])

# ------------------------------------------------------------------ planta
with tab_planta:
    res_lin = resumen_lineas(df)
    st.dataframe(res_lin, hide_index=True, width="stretch", column_config={
        "Lbs_Buenas": st.column_config.NumberColumn(format="%,.0f"),
        "OEE_Promedio": st.column_config.NumberColumn("OEE", format="percent"),
        "Paro_No_Plan_h": st.column_config.NumberColumn("Paro no plan. (h)", format="%,.1f"),
        "MUV_USD": st.column_config.NumberColumn("MUV (USD)", format="dollar"),
        "YTP_Pct": st.column_config.NumberColumn("YTP", format="percent"),
        "Margen_Contribucion_USD": st.column_config.NumberColumn("Margen (USD)", format="dollar"),
        "Margen_Pct": st.column_config.NumberColumn("Margen %", format="percent"),
        "Retorno_Anual": st.column_config.NumberColumn("Retorno anual", format="percent"),
    })
    opciones_t = {"OEE": ("OEE", ".0%"), "YTP_Pct": ("YTP", ".1%"), "Margen_Contribucion_Pct": ("Margen %", ".0%"),
                  "Paro_No_Planificado_h": ("Paro no planificado (h)", ".1f")}
    col_t = st.selectbox("Tendencia", list(opciones_t), format_func=lambda c: opciones_t[c][0])
    st.plotly_chart(gr.tendencia(df, col_t, *opciones_t[col_t]), width="stretch")

# ------------------------------------------------------------------ correlación
with tab_corr:
    st.subheader("Correlación de retornos entre líneas")
    metodo_r = st.radio("Método", ["pearson", "spearman"], horizontal=True, key="met_ret")
    coef_r, p_r, n_r = correlacion(ret, metodo_r)
    st.plotly_chart(gr.heatmap_correlacion(coef_r, p_r, titulo=f"Retornos semanales, n = {n_r} semanas"),
                    width="stretch")
    st.caption("(ns) = no significativa con 95% de confianza. Correlaciones bajas entre líneas "
               "son las que reducen el riesgo del portafolio.")

    st.subheader("Correlación entre KPIs de eficiencia")
    a, b = st.columns([3, 1])
    vars_sel = a.multiselect("Variables", list(VARIABLES_KPI), default=list(VARIABLES_KPI),
                             format_func=VARIABLES_KPI.get)
    metodo_k = b.radio("Método", ["pearson", "spearman"], key="met_kpi")
    centrar = b.checkbox("Centrar por línea", value=True,
                         help="Resta la media de cada línea. Mide la relación semana a semana dentro de cada "
                              "línea y evita correlaciones causadas solo por diferencias entre líneas.")
    if len(vars_sel) >= 2:
        base = centrar_por_linea(df, vars_sel) if centrar else df
        coef_k, p_k, n_k = correlacion(base[vars_sel], metodo_k)
        st.plotly_chart(gr.heatmap_correlacion(coef_k, p_k, VARIABLES_KPI,
                                               f"KPIs {'centrados por línea' if centrar else 'agrupados'}, n = {n_k}"),
                        width="stretch")
        st.caption("Correlación no es causalidad. Úsala para priorizar qué validar con Operaciones.")
    else:
        st.info("Selecciona al menos dos variables.")

# ------------------------------------------------------------------ regresión
with tab_reg:
    st.subheader("Regresión lineal simple entre KPIs")
    a, b, c = st.columns(3)
    x = a.selectbox("Variable explicativa (X)", list(VARIABLES_KPI), index=list(VARIABLES_KPI).index("OEE"),
                    format_func=VARIABLES_KPI.get)
    y = b.selectbox("Variable de resultado (Y)", list(VARIABLES_KPI),
                    index=list(VARIABLES_KPI).index("Retorno_Semanal_Capital"), format_func=VARIABLES_KPI.get)
    por_linea = c.checkbox("Una recta por línea", value=True)
    if x == y:
        st.info("Elige variables distintas para X y Y.")
    else:
        st.plotly_chart(gr.dispersion_regresion(df, x, y, por_linea, VARIABLES_KPI[x], VARIABLES_KPI[y]),
                        width="stretch")
        tabla = regresion_por_linea(df, x, y)
        st.dataframe(tabla, hide_index=True, width="stretch", column_config={
            "pendiente": st.column_config.NumberColumn(format="%.4g"),
            "intercepto": st.column_config.NumberColumn(format="%.4g"),
            "r2": st.column_config.NumberColumn("R²", format="%.3f"),
            "p_value": st.column_config.NumberColumn("p-value", format="%.4f"),
            "ic95_inf": st.column_config.NumberColumn("IC95 inf.", format="%.4g"),
            "ic95_sup": st.column_config.NumberColumn("IC95 sup.", format="%.4g"),
            "error_std": st.column_config.NumberColumn("Error std.", format="%.3g"),
        })
        st.caption("Pendiente = cambio en Y por unidad de X. Si el intervalo de 95% cruza cero, "
                   "la relación no es significativa. La fila agrupada mezcla diferencias entre líneas.")

    st.subheader("Beta de cada línea contra la planta")
    betas = beta_contra_planta(ret, planta)
    a, b = st.columns([1, 1])
    a.plotly_chart(gr.barras_beta(betas), width="stretch")
    linea_b = b.selectbox("Línea", list(ret.columns), format_func=lambda l: f"{l} {parametros.loc[l, 'Linea']}")
    b.plotly_chart(gr.dispersion_beta(ret, planta, linea_b), width="stretch")
    st.caption("Retorno de planta = suma de márgenes / suma de capital de las líneas seleccionadas. Beta mayor a 1 "
               "amplifica la volatilidad de la planta; R² bajo indica riesgo propio que diversifica.")

# ------------------------------------------------------------------ frontera
with tab_front:
    ret_opt = filtrar_cierre_diciembre(ret) if excluir_dic else ret
    try:
        res = optimizar(ret_opt, parametros["Capital_Empleado_USD"], tasa_minima, peso_min, peso_max, puntos)
    except ErrorModelo as e:
        res = None
        st.error(f"{e} Ajusta los límites de peso en la barra lateral.")

    if res is not None:
        met = res.metricas
        a, b, c = st.columns(3)
        for col, nombre, etiqueta in ((a, "Actual", "Asignación actual"), (b, "Minima_Varianza", "Mínima varianza"),
                                      (c, "Maximo_Sharpe", "Máximo Sharpe")):
            delta = met.loc[nombre, "Retorno_Anual"] - met.loc["Actual", "Retorno_Anual"]
            col.metric(etiqueta, pct(met.loc[nombre, "Retorno_Anual"]),
                       None if nombre == "Actual" else f"{delta * 100:+.2f} pp de retorno")
            col.caption(f"Riesgo {pct(met.loc[nombre, 'Riesgo_Anual'], 2)}; Sharpe {met.loc[nombre, 'Sharpe']:.1f}")

        st.plotly_chart(gr.frontera(res), width="stretch")
        st.plotly_chart(gr.barras_pesos(res), width="stretch")
        tabla_p = pd.concat([res.pesos, res.reasignacion], axis=1)
        st.dataframe(tabla_p, width="stretch", column_config={
            **{c: st.column_config.NumberColumn(c.replace("_", " "), format="percent") for c in res.pesos.columns},
            **{c: st.column_config.NumberColumn(c.replace("Delta_Capital_USD_", "Δ capital ").replace("_", " "),
                                                format="dollar") for c in res.reasignacion.columns},
        })
        st.warning("El modelo supone que cada dólar reasignado rinde igual que el promedio histórico de la línea. "
                   "Ajusta los límites de peso a la capacidad física y a los compromisos comerciales antes de usar "
                   "la reasignación.")

# ------------------------------------------------------------------ datos
with tab_datos:
    st.dataframe(df, hide_index=True, width="stretch", height=420)
    st.download_button("Descargar KPIs en CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="kpis_semanales.csv", mime="text/csv")
    if res is None:
        st.info("Los resultados de la frontera se habilitan cuando los límites de peso son factibles.")
    else:
        config = {"Lineas": ", ".join(lineas), "Semana_inicial": str(rango[0]), "Semana_final": str(rango[1]),
                  "Excluye_cierre_dic": excluir_dic, "Tasa_minima": tasa_minima, "Peso_min": peso_min,
                  "Peso_max": peso_max, "Semanas_modelo": len(res.retornos)}
        extras = {"Beta_vs_Planta": betas, "Resumen_Operativo": res_lin}
        st.download_button("Descargar resultados en Excel", exportar_excel(res, config, extras),
                           file_name="resultados_markowitz.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

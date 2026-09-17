import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="Plant Production Efficiency", layout="wide")

DATA_FILE = Path("plant_efficiency_database.xlsx")

@st.cache_data
def load_data():
    if not DATA_FILE.exists():
        st.error(f"No se encontró {DATA_FILE}. Coloca el Excel en el mismo directorio que app.py.")
        st.stop()
    return pd.read_excel(DATA_FILE, sheet_name="Production_Data")

df = load_data()
df["Fecha"] = pd.to_datetime(df["Fecha"])

st.title("Plant Production Efficiency Dashboard")
st.caption("Base de datos operativa para análisis de eficiencia. No contiene implementación de frontera eficiente/Markowitz.")

# Sidebar filters
st.sidebar.header("Filtros")
lines = st.sidebar.multiselect("Línea", sorted(df["Linea"].unique()), default=sorted(df["Linea"].unique()))
products = st.sidebar.multiselect("Producto", sorted(df["Producto"].unique()), default=sorted(df["Producto"].unique()))
shifts = st.sidebar.multiselect("Turno", sorted(df["Turno"].unique()), default=sorted(df["Turno"].unique()))

f = df[df["Linea"].isin(lines) & df["Producto"].isin(products) & df["Turno"].isin(shifts)].copy()

# KPIs
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("OEE promedio", f"{f['OEE'].mean()*100:.1f}%")
c2.metric("Yield", f"{f['Yield'].mean()*100:.1f}%")
c3.metric("MUV", f"{f['MUV_pct'].mean()*100:.2f}%")
c4.metric("Costo/kg bueno", f"{f['Costo_por_Kg_Bueno'].mean():.3f}")
c5.metric("Downtime no planeado", f"{f['Paro_No_Planeado_pct'].mean()*100:.1f}%")

st.subheader("Tendencia de OEE y Yield")
trend = f.groupby("Fecha", as_index=False).agg(OEE=("OEE","mean"), Yield=("Yield","mean"))
fig, ax = plt.subplots(figsize=(12,4))
ax.plot(trend["Fecha"], trend["OEE"], label="OEE")
ax.plot(trend["Fecha"], trend["Yield"], label="Yield")
ax.set_ylabel("Ratio")
ax.legend()
ax.grid(alpha=0.25)
st.pyplot(fig)

st.subheader("Regresión: Downtime vs OEE")
reg = f[["Horas_Paro_No_Planeado","OEE"]].dropna()
if len(reg) >= 3 and reg["Horas_Paro_No_Planeado"].nunique() > 1:
    x = reg["Horas_Paro_No_Planeado"].to_numpy()
    y = reg["OEE"].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    pred = intercept + slope*x
    r = np.corrcoef(x, y)[0,1]
    fig, ax = plt.subplots(figsize=(8,5))
    ax.scatter(x, y, alpha=0.5)
    order = np.argsort(x)
    ax.plot(x[order], pred[order], linewidth=2, label=f"y={slope:.4f}x+{intercept:.4f}")
    ax.set_xlabel("Horas de paro no planeado")
    ax.set_ylabel("OEE")
    ax.set_title(f"Correlación Pearson r = {r:.3f}")
    ax.legend()
    ax.grid(alpha=0.25)
    st.pyplot(fig)
else:
    st.info("No hay suficiente variación para calcular la regresión.")

st.subheader("Regresión: MUV vs Costo por kg bueno")
reg2 = f[["MUV_pct","Costo_por_Kg_Bueno"]].dropna()
if len(reg2) >= 3 and reg2["MUV_pct"].nunique() > 1:
    x = reg2["MUV_pct"].to_numpy()
    y = reg2["Costo_por_Kg_Bueno"].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    pred = intercept + slope*x
    r = np.corrcoef(x, y)[0,1]
    fig, ax = plt.subplots(figsize=(8,5))
    ax.scatter(x*100, y, alpha=0.5)
    order = np.argsort(x)
    ax.plot(x[order]*100, pred[order], linewidth=2, label=f"Pendiente={slope:.4f}")
    ax.set_xlabel("MUV (%)")
    ax.set_ylabel("Costo por kg bueno")
    ax.set_title(f"Correlación Pearson r = {r:.3f}")
    ax.legend()
    ax.grid(alpha=0.25)
    st.pyplot(fig)
else:
    st.info("No hay suficiente variación para calcular la regresión.")

st.subheader("Matriz de correlación")
numeric = f.select_dtypes(include=np.number)
corr = numeric.corr(numeric_only=True)
st.dataframe(corr.round(3), use_container_width=True)

st.subheader("Datos filtrados")
st.dataframe(f, use_container_width=True)

csv = f.to_csv(index=False).encode("utf-8")
st.download_button("Descargar datos filtrados CSV", csv, "plant_efficiency_filtered.csv", "text/csv")

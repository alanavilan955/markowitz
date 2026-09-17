"""Carga del libro de Excel y cálculo de KPIs en Python.

Todos los KPIs se recalculan desde las columnas de captura con las mismas fórmulas
del libro. Así la app funciona igual con un archivo guardado por Excel o con uno
generado por openpyxl sin valores calculados.
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd

HOJA_PRODUCCION = "Produccion_Semanal"
HOJA_PARAMETROS = "Parametros"
HOJA_EVENTOS = "Eventos_Paro"

COLUMNAS_CAPTURA = [
    "Semana_Inicio", "Linea_ID", "Horas_Programadas", "Paro_Planificado_h", "Lbs_Plan", "Lbs_Buenas",
    "Lbs_Scrap", "Horas_MO", "HC", "Horas_Extra", "Material_Real_USD", "kWh",
    "Mant_Planificado_USD", "Mant_No_Planificado_USD",
]
COLUMNAS_PARAMETROS = [
    "Linea_ID", "Linea", "Familia", "Tasa_Estandar_lbs_h", "Costo_Material_Std_USD_lb", "Factor_Scrap_Std",
    "Precio_Neto_USD_lb", "Tarifa_MO_USD_h", "Capital_Empleado_USD",
]
GLOBALES_REQUERIDOS = ["Tarifa_Energia_USD_kWh", "Prima_Horas_Extra"]


class ErrorDatos(ValueError):
    """Estructura del libro incompatible con el modelo."""


def _div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.zeros_like(a)
    np.divide(a, b, out=out, where=b > 0)
    return out


def cargar_libro(fuente) -> dict:
    """fuente: ruta, bytes o archivo subido. Devuelve parámetros, globales, producción y eventos."""
    if isinstance(fuente, (bytes, bytearray)):
        fuente = BytesIO(fuente)
    xls = pd.ExcelFile(fuente)
    for hoja in (HOJA_PRODUCCION, HOJA_PARAMETROS):
        if hoja not in xls.sheet_names:
            raise ErrorDatos(f"Falta la hoja '{hoja}' en el libro.")

    pa = pd.read_excel(xls, sheet_name=HOJA_PARAMETROS, usecols="A:K").dropna(subset=["Linea_ID"])
    faltan = [c for c in COLUMNAS_PARAMETROS if c not in pa.columns]
    if faltan:
        raise ErrorDatos(f"Faltan columnas en Parametros: {faltan}")
    glob_df = pd.read_excel(xls, sheet_name=HOJA_PARAMETROS, usecols="M:N").dropna()
    glob = dict(zip(glob_df.iloc[:, 0], glob_df.iloc[:, 1].astype(float)))
    faltan = [g for g in GLOBALES_REQUERIDOS if g not in glob]
    if faltan:
        raise ErrorDatos(f"Faltan parámetros globales en Parametros!M:N: {faltan}")

    prod = pd.read_excel(xls, sheet_name=HOJA_PRODUCCION)
    faltan = [c for c in COLUMNAS_CAPTURA if c not in prod.columns]
    if faltan:
        raise ErrorDatos(f"Faltan columnas de captura en {HOJA_PRODUCCION}: {faltan}")
    prod["Semana_Inicio"] = pd.to_datetime(prod["Semana_Inicio"])
    desconocidas = set(prod["Linea_ID"]) - set(pa["Linea_ID"])
    if desconocidas:
        raise ErrorDatos(f"Líneas sin parámetros: {sorted(desconocidas)}")

    eventos = None
    if HOJA_EVENTOS in xls.sheet_names:
        eventos = pd.read_excel(xls, sheet_name=HOJA_EVENTOS)
        eventos["Semana_Inicio"] = pd.to_datetime(eventos["Semana_Inicio"])
    return {"parametros": pa.set_index("Linea_ID"), "globales": glob, "produccion": prod, "eventos": eventos}


def calcular_kpis(libro: dict) -> pd.DataFrame:
    pa, glob = libro["parametros"], libro["globales"]
    df = libro["produccion"][COLUMNAS_CAPTURA].copy()
    ev = libro["eventos"]

    if ev is not None and {"Semana_Inicio", "Linea_ID", "Minutos_Paro"} <= set(ev.columns):
        paros = (ev.groupby(["Linea_ID", "Semana_Inicio"])["Minutos_Paro"].sum().div(60)
                 .rename("Paro_No_Planificado_h").reset_index())
        df = df.merge(paros, on=["Linea_ID", "Semana_Inicio"], how="left")
        df["Paro_No_Planificado_h"] = df["Paro_No_Planificado_h"].fillna(0.0)
    elif "Paro_No_Planificado_h" in libro["produccion"]:
        df["Paro_No_Planificado_h"] = pd.to_numeric(libro["produccion"]["Paro_No_Planificado_h"],
                                                    errors="coerce").fillna(0.0)
    else:
        raise ErrorDatos("No hay hoja Eventos_Paro ni columna Paro_No_Planificado_h.")

    df = df.reset_index(drop=True)
    p = pa.loc[df["Linea_ID"]].reset_index(drop=True)
    df.insert(2, "Linea", p["Linea"].values)
    df.insert(3, "Familia", p["Familia"].values)

    neto = df["Horas_Programadas"] - df["Paro_Planificado_h"]
    df["Tiempo_Operativo_h"] = neto - df["Paro_No_Planificado_h"]
    df["Lbs_Totales"] = df["Lbs_Buenas"] + df["Lbs_Scrap"]
    df["Disponibilidad"] = _div(df["Tiempo_Operativo_h"], neto)
    df["Rendimiento"] = _div(df["Lbs_Totales"], p["Tasa_Estandar_lbs_h"] * df["Tiempo_Operativo_h"])
    df["Calidad"] = _div(df["Lbs_Buenas"], df["Lbs_Totales"])
    df["OEE"] = df["Disponibilidad"] * df["Rendimiento"] * df["Calidad"]
    df["Cumplimiento_Plan"] = _div(df["Lbs_Buenas"], df["Lbs_Plan"])
    df["Pct_Horas_Extra"] = _div(df["Horas_Extra"], df["Horas_MO"])
    df["Lbs_por_Hora_MO"] = _div(df["Lbs_Buenas"], df["Horas_MO"])

    df["Costo_Perfeccion_USD"] = df["Lbs_Buenas"] * p["Costo_Material_Std_USD_lb"]
    df["Scrap_Estandar_USD"] = df["Costo_Perfeccion_USD"] * p["Factor_Scrap_Std"]
    df["Costo_Prime_Std_USD"] = df["Costo_Perfeccion_USD"] + df["Scrap_Estandar_USD"]
    df["MUV_USD"] = df["Material_Real_USD"] - df["Costo_Prime_Std_USD"]
    df["Perdida_Abs_Real_USD"] = df["Scrap_Estandar_USD"] + df["MUV_USD"]
    df["YTP_Pct"] = _div(df["Perdida_Abs_Real_USD"], df["Costo_Perfeccion_USD"])

    tarifa = p["Tarifa_MO_USD_h"]
    df["Costo_MO_USD"] = ((df["Horas_MO"] - df["Horas_Extra"]) * tarifa
                          + df["Horas_Extra"] * tarifa * glob["Prima_Horas_Extra"])
    df["Costo_Energia_USD"] = df["kWh"] * glob["Tarifa_Energia_USD_kWh"]
    df["Costo_Conversion_USD"] = (df["Costo_MO_USD"] + df["Costo_Energia_USD"]
                                  + df["Mant_Planificado_USD"] + df["Mant_No_Planificado_USD"])
    df["Costo_Conversion_USD_lb"] = _div(df["Costo_Conversion_USD"], df["Lbs_Buenas"])
    df["Ingreso_Neto_USD"] = df["Lbs_Buenas"] * p["Precio_Neto_USD_lb"]
    df["Margen_Contribucion_USD"] = df["Ingreso_Neto_USD"] - df["Material_Real_USD"] - df["Costo_Conversion_USD"]
    df["Margen_Contribucion_Pct"] = _div(df["Margen_Contribucion_USD"], df["Ingreso_Neto_USD"])
    df["Capital_Empleado_USD"] = p["Capital_Empleado_USD"].astype(float)
    df["Retorno_Semanal_Capital"] = _div(df["Margen_Contribucion_USD"], df["Capital_Empleado_USD"])

    dup = int(df.duplicated(["Linea_ID", "Semana_Inicio"]).sum())
    if dup:
        raise ErrorDatos(f"Hay {dup} registros duplicados de línea y semana.")
    return df.sort_values(["Semana_Inicio", "Linea_ID"]).reset_index(drop=True)


def matriz(df: pd.DataFrame, columna: str) -> pd.DataFrame:
    """Semanas en filas y líneas en columnas. Elimina semanas incompletas."""
    m = df.pivot_table(index="Semana_Inicio", columns="Linea_ID", values=columna, aggfunc="sum")
    return m.dropna().sort_index()


def retorno_planta(df: pd.DataFrame) -> pd.Series:
    """Retorno semanal de la planta ponderado por capital: suma de márgenes / suma de capital."""
    g = df.groupby("Semana_Inicio")[["Margen_Contribucion_USD", "Capital_Empleado_USD"]].sum()
    return (g["Margen_Contribucion_USD"] / g["Capital_Empleado_USD"]).rename("Planta")


def resumen_lineas(df: pd.DataFrame, periodos_anio: int = 52) -> pd.DataFrame:
    g = df.groupby(["Linea_ID", "Linea"])
    out = pd.DataFrame({
        "Semanas": g.size(),
        "Lbs_Buenas": g["Lbs_Buenas"].sum(),
        "OEE_Promedio": g["OEE"].mean(),
        "Paro_No_Plan_h": g["Paro_No_Planificado_h"].sum(),
        "MUV_USD": g["MUV_USD"].sum(),
        "YTP_Pct": g["Perdida_Abs_Real_USD"].sum() / g["Costo_Perfeccion_USD"].sum(),
        "Margen_Contribucion_USD": g["Margen_Contribucion_USD"].sum(),
        "Margen_Pct": g["Margen_Contribucion_USD"].sum() / g["Ingreso_Neto_USD"].sum(),
        "Retorno_Anual": g["Retorno_Semanal_Capital"].mean() * periodos_anio,
    })
    return out.reset_index()

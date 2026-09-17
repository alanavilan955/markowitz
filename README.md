# Eficiencia de planta y frontera eficiente por línea

![pruebas](https://github.com/USUARIO/REPOSITORIO/actions/workflows/pruebas.yml/badge.svg)

Tablero en Streamlit para una planta de alimentos con 8 líneas y 104 semanas. Calcula OEE, MUV, yield loss to perfection, margen de contribución y retorno sobre capital; muestra correlaciones y regresiones entre KPIs, y resuelve la frontera eficiente de Markowitz para asignar capital entre líneas.

La base incluida en `data/` es sintética (semilla 20260917). No proviene de ninguna planta real ni de SAP.

> Reemplaza `USUARIO/REPOSITORIO` en la insignia por tu ruta de GitHub.

## Estructura

```
.
├── app.py                          # app de Streamlit
├── src/
│   ├── datos.py                    # carga del Excel y cálculo de KPIs
│   ├── analitica.py                # correlación, regresión MCO y beta contra planta
│   ├── markowitz.py                # frontera eficiente con límites de peso
│   └── graficas.py                 # gráficas Plotly de la app
├── scripts/
│   ├── generar_base_datos.py       # crea el Excel sintético
│   └── optimizacion_markowitz.py   # versión de línea de comandos con PNG y Excel
├── data/
│   └── BD_Eficiencia_Produccion_Planta_Alimentos.xlsx
├── tests/test_modelo.py            # 13 pruebas, incluida la app
├── .streamlit/config.toml          # tema y límite de carga
├── .github/workflows/pruebas.yml   # pytest en cada push a main
├── requirements.txt                # dependencias de ejecución
├── requirements-dev.txt            # agrega pytest
└── conftest.py
```

## Qué muestra la app

| Pestaña | Contenido |
|---|---|
| Planta | Resumen por línea y tendencia de OEE, YTP, margen o paros (promedio móvil de 4 semanas) |
| Correlación | Heatmap de retornos entre líneas y heatmap de 13 KPIs, Pearson o Spearman, con p-values y opción de centrar por línea |
| Regresión | Dispersión con recta MCO por línea o agrupada; tabla con pendiente, R², p-value e IC 95%. Beta de cada línea contra el retorno de la planta |
| Frontera eficiente | Frontera con límites, portafolios actual, mínima varianza y máximo Sharpe; pesos y reasignación de capital en USD |
| Datos y descargas | Tabla de KPIs, CSV y Excel de resultados |

La barra lateral permite subir otro libro con la misma estructura, filtrar líneas y semanas, excluir el cierre de diciembre y fijar tasa mínima y límites de peso.

## Ejecutar en local

```bash
git clone https://github.com/USUARIO/REPOSITORIO.git
cd REPOSITORIO
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q                # debe terminar con 13 passed
streamlit run app.py               # abre http://localhost:8501
```

Versión de línea de comandos:

```bash
python scripts/optimizacion_markowitz.py --tasa-minima 0.10 --peso-min 0.05 --peso-max 0.30
```

Genera en `salidas/`: `frontera_eficiente.png`, `correlacion_retornos.png`, `correlacion_kpis.png`, `regresion_oee_retorno.png`, `regresion_paro_margen.png`, `beta_lineas.png` y `resultados_markowitz.xlsx`.

Regenerar la base sintética:

```bash
python scripts/generar_base_datos.py --salida data/BD_Eficiencia_Produccion_Planta_Alimentos.xlsx
```

El archivo regenerado no trae valores calculados en sus fórmulas. La app no los necesita porque recalcula todos los KPIs en Python; la prueba que compara Python contra el Excel se omite hasta que abras y guardes el libro en Excel.

## Publicar en GitHub

1. Crea un repositorio vacío en GitHub, sin README ni .gitignore.
2. Desde la carpeta del proyecto:

```bash
git init
git add .
git commit -m "Tablero de eficiencia de planta y frontera eficiente"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

3. En la pestaña Actions del repositorio verifica que el flujo `pruebas` termine en verde.

## Desplegar en Streamlit Community Cloud

1. Entra a https://share.streamlit.io con tu cuenta de GitHub y autoriza el acceso al repositorio.
2. Crea una app nueva desde un repositorio existente.
3. Repositorio: `USUARIO/REPOSITORIO`. Rama: `main`. Archivo principal: `app.py`.
4. En la configuración avanzada elige Python 3.12 (la versión con la que se probó).
5. Despliega. Streamlit instala `requirements.txt` y publica una URL `https://<nombre>.streamlit.app`.
6. Cada `git push` a `main` actualiza la app.

Los nombres de los botones en Streamlit Community Cloud pueden cambiar; la documentación vigente está en https://docs.streamlit.io/deploy/streamlit-community-cloud.

### Antes de subir datos reales

- Un repositorio público y una app pública exponen el Excel de `data/` a cualquiera. No subas costos, precios, volúmenes ni capital reales de la empresa a un repositorio público.
- Para datos reales usa un repositorio privado y restringe quién puede ver la app en su configuración de uso compartido, o deja `data/` vacío y carga el libro con el botón de la barra lateral en cada sesión.
- Confirma con Seguridad de la Información si la política de la empresa permite procesar esos datos en Streamlit Community Cloud. Si no, despliega en infraestructura interna con `streamlit run app.py`.

## Estructura mínima del libro que acepta la app

| Hoja | Columnas requeridas |
|---|---|
| `Parametros` A:K | `Linea_ID`, `Linea`, `Familia`, `Tasa_Estandar_lbs_h`, `Costo_Material_Std_USD_lb`, `Factor_Scrap_Std`, `Precio_Neto_USD_lb`, `Tarifa_MO_USD_h`, `Capital_Empleado_USD` |
| `Parametros` M:N | filas `Tarifa_Energia_USD_kWh` y `Prima_Horas_Extra` |
| `Produccion_Semanal` | `Semana_Inicio`, `Linea_ID`, `Horas_Programadas`, `Paro_Planificado_h`, `Lbs_Plan`, `Lbs_Buenas`, `Lbs_Scrap`, `Horas_MO`, `HC`, `Horas_Extra`, `Material_Real_USD`, `kWh`, `Mant_Planificado_USD`, `Mant_No_Planificado_USD` |
| `Eventos_Paro` (opcional) | `Semana_Inicio`, `Linea_ID`, `Minutos_Paro`. Si falta, se usa `Paro_No_Planificado_h` de `Produccion_Semanal` |

## Método

**KPIs.** OEE = disponibilidad × rendimiento × calidad; el paro planificado no penaliza disponibilidad. MUV = material real − (costo de perfección + scrap estándar). YTP = (scrap estándar + MUV) / costo de perfección. Retorno semanal = margen de contribución / capital empleado.

**Correlación.** Pearson mide relación lineal; Spearman, relación monótona y es menos sensible a semanas atípicas. "ns" marca coeficientes con p ≥ 0.05. Centrar por línea resta la media de cada línea antes de correlacionar: sin ese paso, una línea con OEE bajo y margen bajo en todas las semanas crea una correlación agrupada que no existe semana a semana.

**Regresión.** MCO simple y = a + b·x por línea y agrupada, con `scipy.stats.linregress`. El IC 95% de la pendiente usa la distribución t con n − 2 grados de libertad.

**Beta contra planta.** Regresión del retorno de cada línea contra el retorno de la planta (suma de márgenes / suma de capital). La media de las betas ponderada por capital es 1 por construcción; la prueba `test_beta_ponderada` lo verifica.

**Frontera eficiente.** Media × 52 y covarianza × 52. Mínima varianza, máximo Sharpe contra la tasa mínima y 40 puntos de frontera con SLSQP, pesos que suman 1 y límites por línea. La varianza se normaliza antes de optimizar porque su orden de magnitud (1e-5) detenía al solver antes del óptimo.

## Resultados con la base sintética y parámetros por defecto

| Portafolio | Retorno anual | Riesgo anual | Sharpe |
|---|---|---|---|
| Actual | 27.2% | 0.31% | 55.2 |
| Mínima varianza | 25.2% | 0.27% | 56.9 |
| Máximo Sharpe | 28.3% | 0.29% | 62.2 |

Salsa BBQ (L04) y single serve (L07) tienen beta cercana a 2 contra la planta; mayonesa (L02) y queso crema (L05) tienen 0.49 y 0.61. Con KPIs centrados por línea, el costo de conversión por lb tiene r = −0.73 con el retorno semanal y la calidad r = 0.14.

## Limitaciones

- El riesgo sale bajo y el Sharpe inflado porque la simulación genera márgenes semanales poco volátiles. Con datos sintéticos, usa el orden relativo, no el nivel.
- Rendimientos constantes a escala: el modelo supone que cada dólar reasignado rinde igual que el promedio histórico. Una planta tiene capacidad instalada y costos fijos; los límites de peso deben reflejarlo.
- Capital empleado fijo por línea; margen sin depreciación ni allocations.
- Anualizar × 52 supone semanas independientes.
- Las regresiones son bivariadas. Una pendiente significativa no prueba causa; úsala para decidir qué validar con Operaciones.

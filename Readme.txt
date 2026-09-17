Plant Production Efficiency Dashboard
Aplicación de Streamlit para analizar la eficiencia operacional de una planta de alimentos.
Alcance
Este proyecto contiene únicamente la base de datos y el análisis descriptivo/estadístico de eficiencia.
No incluye código de frontera eficiente, Markowitz, optimización de portafolio ni optimización matemática.
La arquitectura está pensada para que posteriormente puedas agregar un módulo de optimización separado sin modificar la estructura de captura de datos.
Archivos
● app.py — aplicación Streamlit.
● plant_efficiency_database.xlsx — base de datos de ejemplo.
● requirements.txt — dependencias Python.
● README.md — instrucciones.
Estructura del Excel
Production_Data
Contiene registros diarios/operativos con:
● Fecha, planta, línea, turno y producto.
● Horas programadas, operación, setup y paros.
● Unidades y kg producidos/buenos/rechazados.
● Consumo real y estándar de materia prima.
● Costos de materia prima, mano de obra, mantenimiento y energía.
● OEE: disponibilidad, rendimiento y calidad.
● Yield.
● MUV %.
● Costo por kg bueno.
Monthly_Summary
Agregación mensual por línea y producto.
Data_Dictionary
Definición de los principales campos, categorías y unidades.
Ejecutar localmente
```bash
python -m venv .venv
```
Windows:
```bash
.venv\Scripts\activate
```
macOS/Linux:
```bash
source .venv/bin/activate
```
Instalar dependencias:
```bash
pip install -r requirements.txt
```
Ejecutar:
```bash
streamlit run app.py
```
La aplicación abrirá una dirección local indicada por Streamlit.
Publicar en GitHub + Streamlit Community Cloud
1. Crea un repositorio en GitHub.
2. Sube:
● app.py
● plant_efficiency_database.xlsx
● requirements.txt
● README.md
3. En Streamlit Community Cloud crea una nueva aplicación.
4. Selecciona el repositorio.
5. Selecciona app.py como archivo principal.
6. Despliega.
Modelo de datos recomendado para una planta real
Para producción, sustituye los datos sintéticos por datos reales provenientes de ERP/MES/SAP y agrega, como mínimo:
● Orden de producción.
● Centro de trabajo/línea.
● Material/SKU.
● Cantidad planificada y confirmada.
● Kg buenos.
● Kg scrap.
● Horas de máquina.
● Paros por código y causa.
● Setup/changeover.
● Velocidad estándar.
● Consumo real vs estándar.
● Costo estándar.
● Costo real.
● Labor hours.
● Maintenance hours.
● Energy usage.
● WIP.
● Rework.
● Yield.
● OEE.
● MUV/DUV y otras variaciones relevantes.
Nota metodológica
Las regresiones y correlaciones incluidas son descriptivas. Una correlación no demuestra causalidad. Antes de usar los resultados para decisiones de productividad o costo, conviene validar:
● calidad de datos;
● granularidad;
● outliers;
● cambios de producto;
● mix;
● tamaño de lote;
● velocidad estándar;
● downtime planificado vs no planificado;
● cambios de receta/BOM;
● turnos;
● condiciones de operación.
# Cuadrillas — Predicción de demanda y asignación de recursos para reclamos urbanos

**Propuesta B de Trabajo Práctico Integral**
Inteligencia Artificial Avanzada — UTN FRBA — 2do Cuatrimestre 2026

| Apellido y Nombres | E-Mail | Aporte |
|---|---|---|
| Sánchez, Tomás Agustín | _(completar)_ | 100% |

**Fecha de Presentación:** _(completar)_

---

## Resumen

La Ciudad de Buenos Aires recibe cerca de **830.000 reclamos por año**: basura sin retirar,
veredas rotas, luminarias apagadas, árboles para podar. Las cuadrillas que los resuelven son
limitadas y hay que decidir cuántas mandar a cada comuna.

Este trabajo propone un sistema que hace dos cosas: **predecir cuántos reclamos de cada tipo va
a haber en cada comuna la semana que viene**, y con esa predicción **repartir las cuadrillas**
para que la gente espere lo menos posible.

Se usa una **red neuronal recurrente** para la predicción y un **algoritmo genético** para el
reparto.

---

## 1. Introducción

Hoy las cuadrillas se asignan por historial y por criterio del responsable de cada comuna. El
problema es que la demanda no es pareja: cambia por época del año, por día de la semana, por
barrio y por tipo de reclamo. Las hojas caen en otoño, los escombros aparecen cuando hay obra,
las luminarias fallan más en invierno porque están más horas prendidas.

Si se pudiera anticipar dónde va a haber más trabajo, se podría mandar la gente antes en vez de
después.

### Objetivo

Construir un sistema que:

1. **prediga la cantidad de reclamos** por comuna, categoría y semana;
2. **proponga un reparto de cuadrillas** entre las 15 comunas que minimice la demora total;
3. muestre qué tan confiable es cada predicción.

### Qué queda afuera

- El texto de los reclamos: **el dato abierto no lo publica** (lo verificamos, ver sección 2).
- La resolución del reclamo en la calle y el seguimiento del trabajo.
- Reclamos que no son de competencia municipal.

---

## 2. Materiales Disponibles

### Datos

Se usa el conjunto **Sistema Único de Atención Ciudadana (SUACI)** del portal de datos abiertos
de la Ciudad, licencia CC-BY-2.5-AR, publicado por año de **2011 a 2026** en CSV.

**Lo descargamos y lo verificamos.** Sólo el año 2023 tiene:

| | |
|---|---|
| Filas | **831.373** |
| Columnas | 19 |
| Categorías | 39 |
| Prestaciones (subtipos) | 323 |
| Comunas / barrios | 15 / 48 |
| Rango de fechas | 2023-01-01 a 2023-12-31, día a día |

Columnas reales: `nro_solicitud, periodo, categoria, prestacion, tipo, fecha_ingreso,
hora_ingreso, comuna, barrio, calle, altura, esquina_proxima, canal, long, lat, genero,
estado_general, lat_wgs84, long_wgs84`.

Las categorías más frecuentes en 2023:

| Categoría | Reclamos |
|---|---|
| HIGIENE | 320.619 |
| DENUNCIA VIAL | 159.882 |
| VEREDAS | 67.358 |
| ARBOLADO | 60.010 |
| RESOLUCIONES URBANAS | 47.126 |
| ALUMBRADO | 30.921 |

Con 15 años publicados, el conjunto completo supera los **10 millones de registros**.

### Un hallazgo que cambió la idea original

La primera versión de esta propuesta era distinta: clasificar el **texto** del reclamo con
procesamiento de lenguaje natural, para derivarlo automáticamente al área correcta.

**Al descargar el dataset se cayó.** No hay texto libre: el reclamo ya viene clasificado en
`categoria` y `prestacion`. No hay nada que clasificar — la etiqueta está, falta la entrada.

Se deja asentado porque es el tipo de verificación que conviene hacer **antes** de comprometerse
con un enfoque, no después.

Lo bueno es que el dataset sirve para algo mejor: tiene **geografía, fecha, hora y canal** de
830.000 reclamos por año. Eso es una serie temporal espacial de primera calidad.

### Preparación de los datos

**1. Agregar por semana, comuna y categoría.** El dato viene reclamo por reclamo; el modelo
necesita conteos. Quedan unas 15 comunas × 39 categorías × 52 semanas ≈ 30.000 series-semana por
año.

**2. Quedarse con las categorías que tienen volumen.** De las 39, unas 10 concentran la gran
mayoría. Las demás tienen tan pocos casos que predecirlas es ruido.

**3. Completar semanas sin reclamos con cero.** Si una comuna no tuvo reclamos de arbolado una
semana, esa semana vale cero, no "falta el dato".

**4. Marcar feriados y estacionalidad.** La demanda cae los feriados y sube en ciertas épocas
(poda en otoño, por ejemplo). Se agregan como variables.

**5. Revisar el 4,9% sin comuna.** Casi 41.000 reclamos de 2023 no tienen comuna asignada. Hay
que ver si se pueden recuperar por las coordenadas antes de descartarlos.

### Cómo se separan los datos

**Se separa por tiempo, no al azar.** Es una serie temporal: entrenar con datos de después y
probar con datos de antes sería hacer trampa.

Se reserva **el último 25% del período** como prueba. Con 2019–2024 eso da:

| | Período | Aproximado |
|---|---|---|
| Entrenamiento | 2019 a mediados de 2023 | 75% |
| **Prueba** | **mediados de 2023 a 2024** | **25%** |

Dentro del entrenamiento se valida con las últimas semanas del tramo de entrenamiento, nunca con
las de prueba.

---

## 3. Solución Propuesta

Dos piezas, una por unidad del programa.

### Pieza 1 — Predicción de demanda (Unidad 2: Redes Recurrentes)

Una **red neuronal recurrente** que, dadas las últimas N semanas de reclamos de una comuna y
categoría, predice las próximas.

| | |
|---|---|
| Entrada | Serie de reclamos por semana, más día del año, feriados y comuna |
| Salida | Cantidad esperada de reclamos las próximas 1 a 4 semanas |
| Modelo | RNN / LSTM en Keras |
| Comparación | Contra un modelo ingenuo ("la semana que viene igual que esta") y contra el promedio histórico de esa semana |

Se elige una red recurrente y no un MLP porque la demanda tiene **memoria**: lo que pasó las
semanas anteriores importa, y el orden importa.

### Pieza 2 — Asignación de cuadrillas (Unidad 3: Algoritmo Genético)

Con la demanda predicha, hay que repartir un número fijo de cuadrillas entre las 15 comunas.

Un algoritmo genético busca la mejor solución imitando la evolución: prueba muchos repartos
distintos, se queda con los mejores, los combina entre sí y repite.

Acá cada "individuo" es **un reparto completo de cuadrillas**, una lista de 15 números, uno por
comuna. Por ejemplo `[3, 5, 2, 4, ...]` quiere decir tres cuadrillas a la Comuna 1, cinco a la 2,
dos a la 3, y así.

El procedimiento es:

1. **Se generan 100 repartos al azar.**
2. **Se le pone una nota a cada uno.** Se calcula la demora total: en cada comuna, los reclamos
   predichos divididos por la capacidad que se le asignó, sumado sobre las 15. Cuanto menor la
   demora, mejor la nota. A eso se lo llama **función de aptitud**.
3. **Se eligen los mejores y se combinan.** De dos repartos buenos sale uno nuevo que toma las
   primeras comunas de uno y las últimas del otro. Eso es el **cruce**.
4. **De vez en cuando se cambia algo al azar:** mover una cuadrilla de una comuna a otra. Eso es
   la **mutación**, y evita que la búsqueda se estanque.
5. **Se repite 200 veces**, y queda el mejor reparto encontrado.

**Las restricciones actúan como filtro:** un reparto que use más cuadrillas de las disponibles, o
que deje una comuna sin ninguna, se descarta antes de competir.

Se usa **DEAP**, la librería que recomienda la cátedra. Hay varias formas de elegir los mejores y
de combinarlos, y se van a comparar en lugar de elegir una sola.

**Herramientas:** Python, `pandas`, `Keras`/`TensorFlow`, `DEAP`, `matplotlib`, Google Colab.

**Línea futura:** agrupar comunas con perfiles de demanda parecidos usando una **red de Kohonen**
(SOM, Unidad 2), para armar zonas de servicio en vez de trabajar comuna por comuna.

---

## 4. Desarrollo

### Lo que ya está hecho

- Descarga y verificación del dataset: 831.373 filas de 2023 revisadas columna por columna.
- Confirmación de que no hay texto libre, que descartó el enfoque original.

### Lo que falta

- La agregación semanal por comuna y categoría.
- La red recurrente.
- El algoritmo genético de asignación.

### Riesgo principal identificado

La demanda de reclamos urbanos es **fuertemente estacional y bastante regular**. Eso hace que un
modelo ingenuo —"la semana que viene se parece a esta"— sea difícil de superar. Es el mismo
patrón que encontramos en la Propuesta A: los modelos tontos son buenos rivales.

Por eso el criterio de éxito se define contra ese modelo ingenuo desde el principio, y no en
términos absolutos.

---

## 5. Resultados

Todavía no hay prototipo. Se define qué se va a medir.

| Qué | Cómo se mide | Cuándo está bien |
|---|---|---|
| Predicción de demanda | Error absoluto medio (MAE) en reclamos por semana | Mejor que el modelo ingenuo |
| Predicción de demanda | MAE relativo, para comparar comunas de distinto tamaño | |
| Asignación de cuadrillas | Demora total simulada | Mejor que el reparto proporcional simple |
| Asignación de cuadrillas | Comuna peor atendida | Que ninguna quede abandonada |
| Ambas | Comparación contra el reparto real, si se consigue el dato | |

### Casos que se documentarán

Se van a mostrar semanas bien predichas y semanas mal predichas. Se espera que las malas sean las
de eventos puntuales —un temporal, un feriado largo, un corte de servicio— que por definición no
están en la serie histórica.

---

## 6. Análisis de los Resultados

**Contra modelos simples.** Todo resultado se compara contra "la semana que viene igual que esta"
y contra "el promedio de esa semana en años anteriores". Sin esa comparación, un MAE solo no
dice nada.

**Contra trabajos previos.** Este dataset ya fue usado públicamente para predecir demanda de
servicios urbanos con Prophet (Bits & Bricks). Se comparará contra ese enfoque, que es
estadístico clásico, mientras que acá se propone una red recurrente.

**Comparación entre las dos piezas.** Interesa medir cuánto de la mejora en la asignación viene
de predecir mejor y cuánto de optimizar mejor. Se puede aislar corriendo el algoritmo genético
con la demanda real conocida en lugar de la predicha.

---

## 7. Conclusiones

Esta propuesta ataca un problema con **datos verificados y abundantes**: 831.373 reclamos en un
solo año, 15 años publicados, geografía y fecha completas.

1. **El dataset se verificó antes de proponer nada.** Eso descartó la idea original de
   clasificación de texto, porque no hay texto que clasificar.
2. **Cubre dos unidades del programa**: redes recurrentes para predecir y algoritmo genético
   para asignar.
3. **Tiene valor real fuera del trabajo práctico**: repartir cuadrillas es un problema concreto
   de una ciudad concreta.
4. **El riesgo está identificado**: la demanda es regular y el modelo ingenuo va a ser un rival
   duro.

### Qué sigue

| Acción | Viabilidad |
|---|---|
| Agregación semanal por comuna y categoría | Alta, es transformación de datos |
| Red recurrente | Alta, hay demo de la cátedra (`datos-RNN.ipynb`) |
| Algoritmo genético de asignación | Alta, hay demo de la cátedra (`CE-*.ipynb`) |
| Red de Kohonen para zonificar | Línea futura |

---

## Comparación con la Propuesta A

| | **A — BoxBox (Fórmula 1)** | **B — Cuadrillas (reclamos urbanos)** |
|---|---|---|
| Problema | Cuándo parar en boxes y con qué goma | Cuántos reclamos habrá y cómo repartir cuadrillas |
| Datos | 104 carreras, ~112.000 vueltas | 831.373 reclamos por año, 15 años |
| Verificado | Sí, con mediciones propias | Sí, dataset descargado y revisado |
| Unidades del programa | 3 (Genético) y 5 (Refuerzo) | 2 (Recurrentes) y 3 (Genético) |
| Antecedente propio | **Sí** — TP de IA 2025 sobre el mismo dominio | No |
| Antecedente publicado | Paper de 2025 con redes profundas | Análisis público con Prophet |
| Novedad | Alta: temporada 2026, nadie pudo usar estos datos | Media: el dataset es muy usado |
| Riesgo | La estrategia depende de eventos impredecibles | El modelo ingenuo es difícil de superar |
| Utilidad fuera del TP | Baja, es un caso de estudio | Alta, es un problema real de gestión |

**Preferencia del autor: Propuesta A.** Tiene más novedad, ya hay trabajo de datos hecho y
verificado, y el pronóstico de carreras futuras permite una validación que no admite trampa. La
Propuesta B es más útil en la vida real y tiene un dataset más grande, pero el problema ya fue
abordado públicamente varias veces.

---

## Referencias

Gobierno de la Ciudad de Buenos Aires (2026). *Sistema Único de Atención Ciudadana / BA
Colaborativa*. Buenos Aires Data, licencia CC-BY-2.5-AR.
https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana

Antonio Vazquez Brust (2018). *Predicción de demanda de servicios urbanos con open data +
Facebook Prophet*. Bits & Bricks.
https://bitsandbricks.github.io/post/prediccion-de-demanda-de-servicios-urbanos-con-prophet/

Fortin, F. et al. (2012). *DEAP: Evolutionary Algorithms Made Easy*. Journal of Machine Learning
Research, vol. 13, pp. 2171–2175.

Hochreiter, S. y Schmidhuber, J. (1997). *Long Short-Term Memory*. Neural Computation, vol. 9,
n.º 8, pp. 1735–1780.

Chollet, F. et al. (2015). *Keras*. https://keras.io/

**Repositorio:** _(completar)_

# BoxBox — Asistente de estrategia de neumáticos y paradas en Fórmula 1

**Inteligencia Artificial Avanzada — Ingeniería en Sistemas de Información**
**Universidad Tecnológica Nacional — Facultad Regional Buenos Aires**

| Apellido y Nombres | E-Mail | Porcentaje de Aporte |
|---|---|---|
| _(completar)_ | _(completar)_ | _%_ |

**Fecha de Presentación:** _(completar)_

---

## Resumen

Este trabajo desarrolla un Sistema Inteligente que asiste al ingeniero de estrategia de
Fórmula 1 en la decisión de parada en boxes: dado el estado de una carrera, estimar cuántas
paradas conviene hacer, en qué ventana de vueltas y con qué compuesto.

El sistema **no predice el resultado de la carrera**, sino el *plan de neumáticos*. Se trabaja
exclusivamente sobre la temporada **2026**, la primera bajo el nuevo reglamento técnico, por dos
razones: la jerarquía de degradación de compuestos se invirtió respecto de años anteriores, lo
que impide mezclar temporadas, y ningún trabajo publicado puede haber usado estos datos.

Se construyó el pipeline completo de adquisición y preparación sobre la biblioteca `fastf1`
(14.095 vueltas, 12 carreras), se implementaron dos modelos —un regresor de degradación y un
clasificador de parada— y se evaluaron sobre un conjunto de prueba del 25% separado por carrera.

**El resultado central es negativo y se reporta como tal:** la predicción puntual falla en todos
los niveles ensayados, mientras que la medición agregada funciona bien. Ese contraste es el que
justifica la arquitectura propuesta para la etapa siguiente: un simulador Monte Carlo que emite
una **distribución** de estrategias en lugar de un valor puntual.

---

## 1. Introducción

Durante una carrera de Fórmula 1 el ingeniero de estrategia debe decidir, vuelta a vuelta, si su
piloto entra a boxes y con qué compuesto continúa. La decisión combina el desgaste del neumático
actual, el ritmo de los rivales cercanos, la pérdida de tiempo del pit-lane del circuito, la
dificultad para adelantar y la posibilidad de un evento de pista que altere por completo el
cálculo.

### 1.1. Objetivo

Construir un Sistema Inteligente que, dado el estado de una carrera, **estime la estrategia de
neumáticos y paradas** —cantidad de paradas, ventana de vueltas y secuencia de compuestos— y
justifique cada recomendación con las reglas que la produjeron.

La recomendación es **asistiva**: no reemplaza al ingeniero de estrategia, le ofrece una segunda
opinión cuantificada y trazable.

### 1.2. Alcance

**Dentro:** temporada 2026, carreras en seco y mixtas, estrategia de neumáticos, eventos de pista
(Safety Car, Virtual Safety Car, bandera roja), restricciones reglamentarias de compuesto.

**Fuera, y declarado explícitamente:** la **gestión de energía**. Bajo el reglamento 2026
aproximadamente el 50% de la potencia proviene del MGU-K, y el estado de carga de la batería junto
con el modo *Manual Override* son hoy parte real del cálculo estratégico. **La FIA y la Fórmula 1
no publican esos datos**, lo que se verificó empíricamente sobre los canales de telemetría
disponibles y está confirmado por el mantenedor de la biblioteca utilizada. El sistema modela la
mitad correspondiente a neumáticos y posición en pista, y declara la otra fuera de alcance.

También quedan fuera: fallas mecánicas, penalizaciones deportivas, órdenes de equipo, sesiones de
clasificación y carreras sprint.

---

## 2. Materiales Disponibles

### 2.1. Fuentes de conocimiento

| Fuente | Tipo | Uso |
|---|---|---|
| Biblioteca `fastf1` v3.8.3 (licencia MIT) | Datos | Tiempos por vuelta, compuesto, edad de neumático, stint, posición, clima, estado de pista |
| *2026 Formula 1 Sporting Regulations*, Sección B, Issue 05 | Conocimiento experto | Reglas duras: artículos B6.1.1, B6.1.2 y B6.3.8 sobre obligación de compuestos |
| API `jolpica-f1` (sucesora de Ergast) | Datos | Fuente secundaria de resultados históricos |
| Prensa técnica y análisis públicos de estrategia | Conocimiento experto | Heurísticas de *undercut* y *overcut* |

### 2.2. Descripción del conjunto de datos

| | |
|---|---|
| Temporada | 2026, rondas 1 a 12 |
| Vueltas | 14.095 |
| Stints | 756 |
| Pilotos-carrera | 257 |
| Paradas registradas | 527 |
| Grilla | 11 equipos, 22 pilotos (incorporan Audi y Cadillac) |

**Completitud medida** sobre las columnas críticas: `Stint`, `Compound`, `TyreLife`,
`FreshTyre`, `TrackStatus` e `IsAccurate` al **100%**; `LapTime` 99,4%; `Position` 99,8%.
`PitInTime` está poblada en el 3,3% de las vueltas — esa escasez **es la etiqueta**.

**Limitación operativa detectada:** `fastf1` impone un límite de **500 llamadas por hora**
(`RateLimitExceededError`). Una ingesta de varias temporadas lo supera y descarta silenciosamente
las carreras restantes. Se resolvió construyendo el caché por tandas e incorporando un modo
`--offline` que trabaja sólo sobre datos ya descargados.

### 2.3. Técnicas de preparación aplicadas

El pipeline `ingest → features` aplica cinco pasos. Cada uno responde a un problema concreto
encontrado en los datos.

**a. Marcado de vueltas representativas.** Se excluyen del ajuste de ritmo las vueltas de entrada
y salida de boxes (que contienen el tránsito por el pit-lane), las vueltas anuladas por los
comisarios y las que no superan la verificación de sincronía de `fastf1`. Quedan utilizables el
**90,0%** de las vueltas. No se eliminan del conjunto: una vuelta de entrada a boxes es
exactamente donde vive la etiqueta.

**b. Corrección por carga de combustible.** Un auto con combustible para `n` vueltas más es
aproximadamente `0,035 × n` segundos más lento. Se resta ese término para que una vuelta 8 sea
comparable con una vuelta 45.

**c. Cálculo de la posición dentro del stint.** No puede usarse `TyreLife` para esto: un piloto
que arranca con un juego usado en clasificación comienza la carrera con `TyreLife = 4`. Se deriva
`stint_lap` contando dentro del stint, y `FreshTyre` responde la pregunta distinta de si el juego
era nuevo.

**d. Decodificación del estado de pista.** `TrackStatus` es una **cadena concatenada**, no un
código: una vuelta en verde es `"1"` y una donde se desplegó y terminó el VSC es `"167"`. Se
evalúa por contención, nunca por igualdad.

**e. Separación de paradas libres.** Un cambio de neumáticos bajo **bandera roja es gratuito**:
la carrera está detenida y no cuesta tiempo en pista. La etiqueta derivada de `PitInTime` no
puede distinguirlo de una parada estratégica que cuesta ~20 s. Se midió que el **8,1%** de todas
las paradas son libres (7,5% en 2024, 8,7% en 2026), con concentraciones extremas: Mónaco 2024
69,6%, Zandvoort 2026 30,9%. Se emiten por eso dos etiquetas separadas, `free_stop` y
`strategic_stop`.

**f. Desfase temporal de las variables de ritmo (control de fuga).** Este es el paso más
importante. Las variables de degradación están presentes en el **87,2%** de las vueltas normales
y en el **0,0%** de las vueltas con parada, porque una vuelta de entrada a boxes nunca es
representativa. Un modelo alimentado con ellas en crudo lee la respuesta en el patrón de
faltantes y obtiene un desempeño casi perfecto sin haber aprendido nada. **Todas las variables de
ritmo se desfasan una vuelta**: la pregunta es "¿boxeará al final de esta vuelta?" usando sólo lo
conocido al comenzarla.

### 2.4. Método de selección de datos para entrenamiento, validación y prueba

**La unidad de partición es la carrera, no la vuelta.** Vueltas consecutivas de un mismo stint
son casi duplicados; partir por vuelta pondría datos del mismo stint a ambos lados y filtraría
información.

Se reservan las **últimas 3 de las 12 rondas** como conjunto de prueba, que **nunca** se usan
para entrenar ni ajustar. Tres de doce carreras es el **25%** exigido. Se eligen las más recientes
en lugar de tres al azar porque replica la tarea real: pronosticar rondas que aún no ocurrieron.

| Partición | Rondas | Carreras | Vueltas | Paradas estratégicas | Tasa |
|---|---|---|---|---|---|
| Entrenamiento + validación | 1 a 9 | 9 | 10.143 | 350 | 3,45% |
| **Prueba** | **10, 11, 12** | **3 (25%)** | **3.501 (25,7%)** | **118** | **3,37%** |

Dentro del conjunto de entrenamiento la validación se hace con **`GroupKFold` de 4 particiones
agrupadas por carrera**, de modo que ninguna carrera aparezca simultáneamente en entrenamiento y
validación de un mismo pliegue.

Las tasas de parada de ambas particiones son casi idénticas (3,45% contra 3,37%), lo que indica
que la partición temporal no introdujo un desbalance adicional.

---

## 3. Solución Propuesta

### 3.1. Arquitectura: tres capas

La recomendación **no** se produce con un único modelo extremo a extremo. Un ingeniero de carrera
no actúa sobre una recomendación que no puede interrogar, y —como se demuestra en la sección 6—
un clasificador puramente estadístico puede además emitir una estrategia **ilegal**.

| Capa | Técnica | Rol |
|---|---|---|
| **1. Estimación de degradación** | Regresión — *gradient boosting* sobre datos tabulares | Cuantifica cuánto tiempo por vuelta pierde cada compuesto |
| **2. Motor de reglas** | Reglas de producción y tablas de decisión (R1–R14) | Toma la decisión. Es la capa auditable y la que garantiza legalidad |
| **3. Simulación Monte Carlo** | Sorteo de eventos de pista + ejecución del motor de reglas | Produce una **distribución** de estrategias |

La capa 2 consume los números de la capa 1. Toda recomendación se emite acompañada de las reglas
que se dispararon.

### 3.2. Restricciones reglamentarias como filtro duro

La elección de compuesto se modela en **dos etapas**, porque el reglamento restringe el conjunto
de opciones *antes* de que la estrategia elija dentro de él:

1. **Filtro reglamentario** → construye `compuestos_admisibles`.
2. **Elección estratégica** → toma la preferencia de mayor prioridad dentro de ese conjunto.

El artículo **B6.3.8** exige al menos **dos especificaciones distintas** de neumático de seco, de
las cuales **al menos una debe ser una especificación obligatoria de carrera** anunciada por la
FIA dos semanas antes de cada competición (artículo **B6.1.2 b ii**, hasta un máximo de dos). En
**Mónaco** se exige además un mínimo de **tres juegos**, es decir una doble parada obligatoria. El
incumplimiento se sanciona con **descalificación**.

El módulo de selección de compuesto tiene por invariante que **no puede** devolver un compuesto
fuera del conjunto admisible: una recomendación ilegal es un defecto, no una estrategia agresiva.

### 3.3. Tecnología y herramientas

| Componente | Herramienta | Motivo |
|---|---|---|
| Lenguaje | Python 3.13 | Ecosistema de datos y compatibilidad con `fastf1` |
| Adquisición | `fastf1` 3.8.3 | Única fuente pública de timing por vuelta con datos de neumático |
| Manipulación | `pandas` 2.x, `numpy` 2.x, `pyarrow` | Estándar; `pyarrow` para persistencia en Parquet |
| Modelos | `LightGBM` 4.x | Desempeño en datos tabulares e importancias interpretables |
| Métricas y partición | `scikit-learn` 1.5 | `GroupKFold`, curvas precisión-exhaustividad |
| Estadística | `scipy` | Ajuste por máxima verosimilitud del *prior* Beta-Binomial |
| Gestión de entorno | `uv` | Reproducibilidad de dependencias |
| Calidad | `ruff`, `pytest` | Linting y pruebas |
| Backend | FastAPI + PostgreSQL | Exposición del sistema como servicio |
| Frontend | React 19 + Vite + TypeScript | Interfaz de demostración |

**Topología del regresor:** LightGBM, 400 árboles, tasa de aprendizaje 0,05, 31 hojas.
**Topología del clasificador:** LightGBM, 300 árboles, tasa de aprendizaje 0,05, 31 hojas, con
`scale_pos_weight` igual a la razón entre clases para compensar el desbalance de 28:1.

No se eligió una red neuronal profunda extremo a extremo: la estrategia exige justificación, y el
volumen de datos (12 carreras) no la sostendría.

---

## 4. Desarrollo

### 4.1. Lo construido

El repositorio es un monorepo con tres aplicaciones: `apps/api` (backend FastAPI generado desde
plantilla, 33 pruebas en verde), `apps/ml` (el pipeline y los modelos) y `apps/web` (interfaz).
El paquete `boxbox_ml` contiene seis módulos: `cache`, `ingest`, `track_status`, `features`,
`practice` y `neutralisation`.

### 4.2. Problemas encontrados y cómo se resolvieron

**a. Fuga por patrón de faltantes.** Descrita en 2.3.f. Detectada al comparar la presencia de
`degradation_s` entre vueltas con y sin parada: 87,2% contra 0,0%. Resuelta desfasando una vuelta
todas las variables de ritmo.

**b. Paradas gratuitas bajo bandera roja.** En el GP de Países Bajos 2026 se observó que **21 de
22 pilotos "boxearon" en la vuelta 2**. La carrera estaba con bandera roja y todos cambiaron
neumáticos gratis. Resuelto separando `free_stop` de `strategic_stop`.

**c. Nombres de circuito inestables entre temporadas.** `fastf1` reporta Mónaco como
`Monte Carlo` y Miami como `Miami Gardens` en 2026, pero `Monaco` y `Miami` en temporadas
anteriores, partiendo silenciosamente el historial de cada circuito en dos mitades sub-observadas.
Resuelto con una tabla de alias.

**d. Estimador de *prior* inadecuado.** El primer ajuste del *prior* Beta por método de momentos
devolvió una fuerza de **0,79 pseudo-visitas**, es decir prácticamente ningún encogimiento: un
circuito visto una vez con un Safety Car quedaba estimado en 0,83. Con 1 o 2 visitas por circuito
la dispersión de las tasas observadas *es* ruido binomial, que el método de momentos interpreta
como variación real. Se reemplazó por **máxima verosimilitud Beta-Binomial**, que devuelve 24,1
pseudo-visitas.

**e. Objetivo del regresor mal planteado.** El primer intento predecía el **tiempo de vuelta
absoluto**. Cada circuito aparece exactamente una vez por temporada, de modo que el modelo debía
predecir pistas que nunca había visto: MAE de prueba 13,050 s contra 9,385 s del ingenuo, con
R² = −0,887. Se corrigió el objetivo a `degradation_s`, que es relativo al stint y por
construcción transferible entre circuitos.

**f. Límite de tasa de la API.** Descrito en 2.2.

### 4.3. Mediciones realizadas

Se produjeron siete documentos de investigación reproducibles: verificación de `fastf1`, impacto
del reglamento 2026, factibilidad de modelado, pronóstico de estrategia, tasas de neutralización,
costo de parada bajo neutralización y el caso de estudio de Zandvoort.

---

## 5. Resultados

Todos los resultados de esta sección corresponden al **conjunto de prueba** (rondas 10, 11 y 12),
nunca visto durante el entrenamiento.

### 5.1. Regresor de degradación

| Métrica | Valor |
|---|---|
| Vueltas de entrenamiento / prueba | 8.692 / 3.080 |
| MAE de validación (`GroupKFold` de 4) | 1,014 s |
| **MAE de prueba** | **0,937 s** |
| MAE de prueba, modelo ingenuo (mediana) | **0,716 s** |
| R² de prueba | **−0,690** |

**El modelo no supera al ingenuo.** Un R² negativo significa que predecir siempre la mediana del
entrenamiento habría sido mejor.

### 5.2. Clasificador de parada

| Métrica | Valor |
|---|---|
| **PR-AUC de prueba** | **0,1430** |
| Azar (tasa positiva de prueba) | 0,0337 |
| **Mejora sobre el azar** | **4,24×** |
| F1 (mejor umbral, 0,206) | 0,2428 |
| Precisión | 0,1842 |
| Exhaustividad | 0,3559 |

**Matriz de confusión (prueba):**

| | Predicho: SEGUIR | Predicho: BOX |
|---|---|---|
| **Real: SEGUIR** | VN = 3.197 | FP = 186 |
| **Real: BOX** | FN = 76 | VP = 42 |

**La exactitud no se reporta como métrica de desempeño.** "Nunca boxear" acierta el **96,63%** de
las vueltas de prueba — y es una estrategia **ilegal** que termina en descalificación
(artículo B6.3.8).

### 5.3. Casos resueltos por carrera

| Ronda | Circuito | Vueltas | Paradas reales | Predichas | Aciertos |
|---|---|---|---|---|---|
| 10 | Spa-Francorchamps | 790 | 25 | 13 | 4 |
| 11 | Budapest | 1.409 | 47 | 151 | 30 |
| 12 | Zandvoort | 1.302 | 46 | 64 | 8 |

**Caso exitoso — Budapest.** El modelo captura 30 de 47 paradas (64% de exhaustividad), aunque a
costa de predecir 151, con lo que la precisión cae a 20%.

**Caso fallido — Zandvoort.** Sólo 8 de 46. La carrera tuvo bandera roja en la vuelta 2, dos
períodos de VSC y estrategias de tres paradas. Ninguna variable previa a la carrera podía
anticiparlo.

### 5.4. Mediciones agregadas (donde sí hay señal)

**Degradación mediana por compuesto (s/vuelta):**

| Temporada | DURO | MEDIO | BLANDO | El que más se degrada |
|---|---|---|---|---|
| 2024 | 0,0388 | 0,0376 | **0,0673** | BLANDO |
| 2026 | **0,0436** | 0,0239 | 0,0142 | DURO |

**Costo de una parada según el estado de pista** (413 paradas estratégicas):

| Estado | Segundos perdidos | **Posiciones perdidas** |
|---|---|---|
| Verde | 22,21 s | **+2,0** |
| VSC | 23,23 s | **0,0** |
| Safety Car | 32,62 s | **0,0** |

**Comportamiento de los equipos:** el 9,6% de las vueltas están neutralizadas pero se toma bajo
neutralización el **30,8%** de las paradas — una sobrerrepresentación de **3,20×**.

**Verificación reglamentaria:** de los 177 pilotos que terminaron una carrera en seco, **los 177
usaron dos o más compuestos**. Cero violaciones.

---

## 6. Análisis de los Resultados

### 6.1. La predicción puntual falla; la medición agregada funciona

Este es el hallazgo central, y se sostiene en cuatro experimentos independientes:

| Objetivo puntual | Resultado | Comparación |
|---|---|---|
| Tiempo de vuelta absoluto | MAE 13,05 s | Ingenuo 9,39 s — **peor** |
| Degradación por vuelta | MAE 0,937 s | Ingenuo 0,716 s — **peor** |
| Duración del stint | MAE 8,13 vueltas | Ingenuo 8,02 — **empate** |
| Cantidad de paradas | 32,1% exacto | Ingenuo 32,0% — **empate** |

Frente a esto, toda medición **agregada** dio resultados nítidos y reproducibles: la inversión de
la jerarquía de compuestos, el costo de parada en posiciones, la sobrerrepresentación de 3,20× y
el cumplimiento del reglamento.

La interpretación no es que el problema sea imposible, sino que **la variable objetivo elegida es
la equivocada**. La estrategia de carrera está gobernada por **eventos**, no por física del
neumático: en Zandvoort el 40% de las paradas cayó en vueltas neutralizadas contra un 15% de
vueltas neutralizadas.

### 6.2. El clasificador supera al azar; el regresor no

Resultado contraintuitivo. El clasificador —presentado como línea base débil— alcanza **4,24× el
azar** sobre datos no vistos, mientras el regresor de degradación, que se esperaba fuerte por
disponer de 22.378 pendientes ajustadas, **no supera a la mediana**.

La explicación es la varianza: la degradación por vuelta está dominada por tráfico, combustible y
estilo de pilotaje, y su mediana es difícil de batir punto a punto. La **degradación agregada por
compuesto** sí es medible con nitidez. Son preguntas distintas.

### 6.3. La curva de aprendizaje decreciente

Al entrenar con 3, 6, 9 y 12 carreras, el PR-AUC bajó de 0,3163 a 0,1028. Esto **no** es que los
datos perjudiquen: con tres carreras cada pliegue de validación es una sola carrera y el modelo se
aferra a particularidades de circuito que se repiten. El 0,3163 es optimismo de muestra pequeña.
**Esperar las rondas 13 a 23 no rescatará este planteo.**

### 6.4. Comparación con el estado del arte

El paper de referencia (Chaudhary et al., 2025) reporta **F1 = 0,81** con Bi-LSTM sobre
2020–2024. Nuestro 0,2428 está muy por debajo. Tres diferencias plausibles: modelan el stint como
**secuencia** y no como instantáneas tabulares por vuelta; entrenan con unas 100 carreras contra
nuestras 12; y su definición de ventana puede ser más amplia. No fue posible verificar su montaje
de forma independiente.

**La novedad de este trabajo no es el problema sino la temporada.** Ningún trabajo publicado puede
haber usado datos de 2026.

### 6.5. Discrepancia con análisis publicado

Un análisis público sostiene que la dispersión de degradación entre compuestos en 2026 es de
0,008 s/vuelta, la más baja de la era. **No se reproduce:** medimos 0,0293 s/vuelta en 2026 contra
0,0297 en 2024. La inversión de la jerarquía sí se reproduce; el colapso de la dispersión no. La
causa probable es el estimador. Queda como punto abierto y **no se cita ninguna de las dos cifras
como establecida**.

---

## 7. Conclusiones

1. **La predicción puntual de estrategia no es alcanzable con estos datos.** Cuatro objetivos
   distintos empataron o perdieron contra modelos ingenuos. Afirmar "el piloto para en la vuelta
   22" sería lo más fácil de refutar: la carrera siguiente simplemente no coincide.

2. **La medición agregada sí funciona**, y sostiene un sistema útil: se conoce la jerarquía de
   degradación 2026, el costo de parada en posiciones y las tasas de neutralización.

3. **El costo de una parada debe medirse en posiciones, no en segundos.** Bajo neutralización una
   parada cuesta 0 posiciones contra 2 en verde, aunque en segundos parezca más cara. Los equipos
   lo explotan 3,20× por encima del azar. Esto obliga a reformular las reglas R2 y R3.

4. **Las reglas duras del reglamento son un activo, no una molestia.** Un clasificador que
   maximice exactitud converge a "nunca boxear", que es descalificación. El motor de reglas hace
   esa salida **irrepresentable**. Es el argumento más fuerte a favor de la arquitectura híbrida.

5. **No se pueden mezclar temporadas.** La jerarquía de compuestos se invirtió en 2026.

### 7.1. Cursos de acción propuestos

| Acción | Justificación | Viabilidad |
|---|---|---|
| **Simulador Monte Carlo sobre el motor de reglas** — emitir `P(1 parada)`, `P(2 paradas)`, secuencia modal e intervalo creíble para la primera parada | Es el único planteo compatible con la evidencia: lo agregado se mide bien, lo puntual no | **Alta.** Los tres insumos ya están medidos |
| **Pronóstico prospectivo fechado** antes de cada una de las 11 carreras restantes, puntuado después | No admite fuga de datos ni ajuste a posteriori. La ronda 13 (Monza) se corre el 2026-09-06 | **Alta.** El calendario coincide con el cuatrimestre |
| Modelo de secuencia sobre el historial del stint | Única diferencia metodológica clara contra el estado del arte | Media |
| Reajustar el coeficiente de combustible con datos 2026 | Está fijo en 0,035 s/vuelta, calibrado en la era anterior; hoy es el supuesto más débil | **Alta** |
| Modelo de supervivencia con censura | Se descartan 178 stints que terminaron en bandera a cuadros; un modelo de supervivencia los aprovecha | Media |
| Completar el caché de 2022 a 2025 | Elevaría de 4 a 8 visitas por circuito y permitiría decidir si los efectos por circuito existen | **Alta**, limitada por el tope de 500 llamadas/hora |

---

## Referencias

Chaudhary, S. et al. (2025). *Data-driven pit stop decision support for Formula 1 using deep
learning models*. Frontiers in Artificial Intelligence, vol. 8.
https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full

Fédération Internationale de l'Automobile (2026). *2026 Formula 1 Sporting Regulations —
Section B*, Issue 05, 27 de febrero de 2026. Artículos B6.1.1, B6.1.2 y B6.3.8.
https://www.fia.com/regulation/category/110

Schäfer, P. et al. (2026). *FastF1 — Python package for F1 timing, telemetry and session data*,
versión 3.8.3. Licencia MIT. https://docs.fastf1.dev/

Schäfer, P. (2026). *FastF1 Discussion #861 — 2026 ERS Deployment & Energy Management Data*.
https://github.com/theOehrly/Fast-F1/discussions/861

Ke, G. et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*. Advances in
Neural Information Processing Systems 30 (NIPS 2017).

Pedregosa, F. et al. (2011). *Scikit-learn: Machine Learning in Python*. Journal of Machine
Learning Research, vol. 12, pp. 2825–2830.

Jolpica (2026). *jolpica-f1 — Ergast-compatible Formula 1 API*.
https://github.com/jolpica/jolpica-f1

**Repositorio del código fuente:** _(completar con la URL del repositorio)_
Contiene el paquete `boxbox_ml`, los scripts de reproducción de cada medición
(`scripts/holdout_eval.py`, `scripts/era_compare.py`, `scripts/pit_loss.py`,
`scripts/safety_car_rates.py`, entre otros) y los siete documentos de investigación en
`docs/research/`. Los datos no se versionan: se reconstruyen ejecutando
`uv run boxbox-ingest --seasons 2026`.

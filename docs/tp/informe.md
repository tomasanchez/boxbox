# BoxBox — Asistente de estrategia de neumáticos y paradas en Fórmula 1

**Propuesta de Trabajo Práctico Integral**
**Inteligencia Artificial Avanzada — Ingeniería en Sistemas de Información**
**Universidad Tecnológica Nacional — Facultad Regional Buenos Aires**

| Apellido y Nombres | E-Mail | Porcentaje de Aporte |
|---|---|---|
| _(completar)_ | _(completar)_ | _%_ |

**Fecha de Presentación:** _(completar)_

---

## Resumen

Este trabajo propone desarrollar un Sistema Inteligente que asista al ingeniero de estrategia de
Fórmula 1 en la decisión de parada en boxes: dado el estado de una carrera, estimar cuántas
paradas conviene hacer, en qué ventana de vueltas y con qué compuesto de neumático.

El sistema **no buscará predecir el resultado de la carrera**, sino el *plan de neumáticos*. Se
trabajará exclusivamente sobre la temporada **2026**, la primera bajo el nuevo reglamento
técnico, por dos motivos: la jerarquía de degradación de compuestos se invirtió respecto de años
anteriores —lo que impide mezclar temporadas— y ningún trabajo publicado puede haber utilizado
estos datos.

Se propone una **arquitectura híbrida de tres capas**: un modelo de regresión que estima la
degradación del neumático, un motor de reglas de producción que toma la decisión de forma
auditable, y una simulación Monte Carlo que emite una **distribución** de estrategias posibles en
lugar de un valor puntual.

Como parte de la elaboración de esta propuesta se realizó un **estudio de factibilidad** sobre
los datos disponibles, cuyos hallazgos se presentan a lo largo del documento porque son los que
justifican cada decisión de diseño. En particular, ese estudio mostró que la predicción puntual
no es alcanzable con estos datos y que la medición agregada sí lo es, lo que determinó el enfoque
distribucional aquí propuesto.

---

## 1. Introducción

Durante una carrera de Fórmula 1 el ingeniero de estrategia debe decidir, vuelta a vuelta, si su
piloto entra a boxes y con qué compuesto continúa. La decisión debe tomarse en segundos y combina
el desgaste del neumático actual, el ritmo de los rivales cercanos, la pérdida de tiempo del
pit-lane del circuito, la dificultad para adelantar y la posibilidad de un evento de pista
—Safety Car, Virtual Safety Car o bandera roja— que altere por completo el cálculo.

### 1.1. Objetivo del Sistema Inteligente

Construir un prototipo que, dado el estado de una carrera de la temporada 2026, **estime la
estrategia de neumáticos y paradas** y **justifique** cada recomendación con las reglas que la
produjeron.

Concretamente, el prototipo deberá emitir para cada piloto:

- la probabilidad de que la carrera se resuelva con una, dos o tres paradas;
- la secuencia modal de compuestos;
- un intervalo creíble para la vuelta de la primera parada;
- la traza de reglas que sustentan la recomendación.

La recomendación será **asistiva**: no reemplaza al ingeniero de estrategia, le ofrece una
segunda opinión cuantificada y trazable.

### 1.2. Alcance

**Dentro del alcance:** temporada 2026, carreras en seco y mixtas, estrategia de neumáticos,
eventos de pista, y las restricciones reglamentarias de compuesto.

**Fuera del alcance, y declarado explícitamente:** la **gestión de energía**. Bajo el reglamento
2026 aproximadamente el 50% de la potencia proviene del MGU-K, y el estado de carga de la batería
junto con el modo *Manual Override* son hoy parte real del cálculo estratégico. **La Fórmula 1 no
publica esos datos**, lo que se verificó sobre los canales de telemetría disponibles y está
confirmado por el mantenedor de la biblioteca a utilizar. El sistema modelará la mitad
correspondiente a neumáticos y posición en pista, y declara la otra fuera de alcance.

También quedan fuera: fallas mecánicas, penalizaciones deportivas, órdenes de equipo, sesiones de
clasificación y carreras sprint.

---

## 2. Materiales Disponibles

### 2.1. Fuentes de información

| Fuente | Tipo | Uso previsto |
|---|---|---|
| Biblioteca `fastf1` v3.8.3 (licencia MIT) | Datos | Tiempos por vuelta, compuesto, edad de neumático, stint, posición, clima, estado de pista |
| *2026 Formula 1 Sporting Regulations*, Sección B, Issue 05 | Conocimiento experto | Reglas duras: artículos B6.1.1, B6.1.2 y B6.3.8 sobre obligación de compuestos |
| Sesiones de entrenamiento libre (FP1, FP2, FP3) | Datos | Estimación del ritmo del circuito antes de la carrera |
| API `jolpica-f1` (sucesora de Ergast) | Datos | Fuente secundaria de resultados históricos |
| Prensa técnica y análisis públicos de estrategia | Conocimiento experto | Heurísticas de *undercut* y *overcut* |

### 2.2. Descripción de los datos disponibles

Verificado sobre las rondas ya disputadas de 2026:

| | |
|---|---|
| Vueltas | 14.095 |
| Stints | 756 |
| Pilotos-carrera | 257 |
| Paradas registradas | 527 |
| Carreras disponibles hoy | 12 de 23 |
| Grilla | 11 equipos, 22 pilotos (se incorporan Audi y Cadillac) |

**Completitud verificada** de las columnas críticas: `Stint`, `Compound`, `TyreLife`,
`FreshTyre`, `TrackStatus` e `IsAccurate` al **100%**; `LapTime` 99,4%; `Position` 99,8%.
`PitInTime` aparece en el 3,3% de las vueltas — esa escasez **es la etiqueta**.

**El conjunto crecerá durante el cuatrimestre.** Restan 11 carreras hasta Abu Dhabi
(2026-12-06), de modo que al cierre de las entregas se dispondrá de casi el doble de datos.

**Limitación operativa detectada:** `fastf1` impone un tope de **500 llamadas por hora**. Una
ingesta de varias temporadas lo supera y descarta silenciosamente las carreras restantes. Se
trabajará construyendo el caché por tandas.

### 2.3. Técnicas de preparación que se aplicarán sobre los datos

El estudio de factibilidad permitió identificar seis transformaciones necesarias. Cada una
responde a un problema concreto verificado en los datos, no a una precaución teórica.

**a. Marcado de vueltas representativas.** Se excluirán del ajuste de ritmo las vueltas de
entrada y salida de boxes —que contienen el tránsito por el pit-lane—, las anuladas por los
comisarios y las que no superan la verificación de sincronía de `fastf1`. Quedan utilizables el
**90,0%**. No se eliminarán del conjunto: una vuelta de entrada a boxes es exactamente donde vive
la etiqueta.

**b. Corrección por carga de combustible.** Un auto con combustible para `n` vueltas más es
aproximadamente `0,035 × n` segundos más lento. Se restará ese término para que una vuelta 8 sea
comparable con una vuelta 45. *(El coeficiente deberá reajustarse con datos de 2026: los autos
son unos 32 kg más livianos que en la era anterior.)*

**c. Cálculo de la posición dentro del stint.** No puede usarse `TyreLife`: un piloto que arranca
con un juego usado en clasificación comienza la carrera con `TyreLife = 4`. Se derivará
`stint_lap` contando dentro del stint; `FreshTyre` responde la pregunta distinta de si el juego
era nuevo.

**d. Decodificación del estado de pista.** `TrackStatus` es una **cadena concatenada**, no un
código: una vuelta en verde es `"1"` y una donde se desplegó y terminó el VSC es `"167"`. Se
evaluará por contención, nunca por igualdad.

**e. Separación de paradas libres.** Un cambio de neumáticos bajo **bandera roja es gratuito**:
la carrera está detenida. La etiqueta derivada de `PitInTime` no puede distinguirlo de una parada
estratégica que cuesta ~20 s. Se verificó que el **8,1%** de las paradas son libres, con
concentraciones extremas (Zandvoort 2026: 30,9%). Se emitirán dos etiquetas separadas.

**f. Desfase temporal de las variables de ritmo (control de fuga).** El más importante. Las
variables de degradación están presentes en el **87,2%** de las vueltas normales y en el **0,0%**
de las vueltas con parada, porque una vuelta de entrada a boxes nunca es representativa. Un
modelo alimentado con ellas en crudo lee la respuesta en el patrón de faltantes. **Todas las
variables de ritmo se desfasarán una vuelta**: la pregunta será "¿boxeará al final de esta
vuelta?" usando sólo lo conocido al comenzarla.

### 2.4. Método de selección de datos para entrenamiento, validación y prueba

**La unidad de partición será la carrera, no la vuelta.** Vueltas consecutivas de un mismo stint
son casi duplicados; partir por vuelta pondría datos del mismo stint a ambos lados y filtraría
información.

Se reservará como conjunto de prueba el **25% de las carreras**, tomando las **más recientes** en
lugar de una selección aleatoria, porque replica la tarea real: pronosticar rondas que aún no
ocurrieron. Ese conjunto no se usará para entrenar ni para ajustar hiperparámetros.

Con las 12 carreras disponibles hoy la partición queda así, y se recalculará a medida que avance
la temporada:

| Partición | Rondas | Carreras | Vueltas | Paradas | Tasa |
|---|---|---|---|---|---|
| Entrenamiento + validación | 1 a 9 | 9 (75%) | 10.143 | 350 | 3,45% |
| **Prueba** | **10 a 12** | **3 (25%)** | **3.501 (25,7%)** | **118** | **3,37%** |

Las tasas de parada de ambas particiones resultan casi idénticas, lo que indica que la partición
temporal no introduce un desbalance adicional.

Dentro del conjunto de entrenamiento la validación se hará con **`GroupKFold` de 4 particiones
agrupadas por carrera**, de modo que ninguna carrera aparezca a la vez en entrenamiento y
validación de un mismo pliegue.

---

## 3. Solución Propuesta

### 3.1. Arquitectura: tres capas

La recomendación **no** se producirá con un único modelo extremo a extremo. Un ingeniero de
carrera no actúa sobre una recomendación que no puede interrogar, y —como se argumenta en la
sección 6— un clasificador puramente estadístico puede además emitir una estrategia **ilegal**.

| Capa | Técnica | Unidad del programa | Rol |
|---|---|---|---|
| **1. Simulador de carrera** | Monte Carlo sobre degradación estimada y sorteo de eventos | — (infraestructura) | Entorno de evaluación. No es una técnica de IA: es el banco de pruebas de las que sí lo son |
| **2. Optimización de la estrategia** | **Algoritmo Genético** (DEAP) | **Unidad 3 — Sistemas Evolutivos** | **Técnica principal.** Busca el mejor plan de carrera |
| **3. Decisión secuencial** | **Aprendizaje por Refuerzo** | **Unidad 5 — Agentes Inteligentes** | Modelo de contraste: decidir vuelta a vuelta en lugar de planificar de antemano |
| Capa transversal | Restricciones reglamentarias (B6.3.8) | — | Define qué soluciones son **viables**. Garantiza legalidad |

**Capa 1 — el simulador.** Para cada carrera se estimará la degradación por compuesto en ese
circuito, se sortearán realizaciones de Safety Car, VSC y bandera roja a partir de las tasas
empíricas medidas, y se ejecutará la carrera vuelta a vuelta. Repetido algunos miles de veces,
produce la **distribución** de resultados de un plan dado. Es la **función de aptitud** de la capa
2 y el **entorno** de la capa 3.

**Capa 2 — Algoritmo Genético (técnica principal).** El problema es combinatorio, con
restricciones duras y una función de aptitud costosa de evaluar: el escenario natural de un
algoritmo evolutivo.

| Elemento | Definición |
|---|---|
| **Cromosoma** | El plan de carrera: vector de longitudes de stint y secuencia de compuestos, p. ej. `[(18, M), (25, H), (14, S)]` |
| **Función de aptitud** | Posición final simulada, promediada sobre varias realizaciones Monte Carlo. Se optimiza **posición, no segundos** |
| **Restricciones** | El artículo B6.3.8 determina qué cromosomas son viables; los inviables se reparan o penalizan |
| **Operadores** | Cruza de un punto sobre la secuencia de stints; mutación que alarga o acorta un stint, o cambia un compuesto |
| **Selección** | Torneo, con elitismo |

Obsérvese el cambio de pregunta respecto de la predicción puntual: no se pregunta *"¿qué hizo el
equipo?"* sino *"¿cuál es el mejor plan?"*. La primera pregunta resultó no ser respondible con
estos datos; la segunda sí lo es, porque se evalúa contra un simulador y no contra una etiqueta
histórica.

**Capa 3 — Agente de Aprendizaje por Refuerzo (contraste).** Un agente que decide `BOX` /
`SEGUIR` vuelta a vuelta dentro del mismo simulador. Estado: el vector de situación de carrera.
Acción: binaria más elección de compuesto. Recompensa: posiciones ganadas al final. Permite
comparar **optimización global** —el AG planifica la carrera completa de antemano— contra
**decisión secuencial** —el agente reacciona a lo que ocurre—. Esa comparación es en sí misma un
resultado.

**Línea futura declarada:** modelar la incertidumbre de Safety Car y VSC con una **red bayesiana**
(Unidad 4, herramienta GeNIe) que alimente los sorteos del simulador. Se declara como línea futura
y no como compromiso: el trabajo es individual y prometer cuatro técnicas para entregar una sería
peor que proponer dos y cumplirlas.

### 3.2. Las restricciones reglamentarias como filtro duro

La elección de compuesto se modelará en **dos etapas**, porque el reglamento restringe el
conjunto de opciones *antes* de que la estrategia elija dentro de él:

1. **Filtro reglamentario** → construye `compuestos_admisibles`.
2. **Elección estratégica** → toma la preferencia de mayor prioridad dentro de ese conjunto.

El artículo **B6.3.8** exige al menos **dos especificaciones distintas** de neumático de seco, de
las cuales **al menos una debe ser una especificación obligatoria de carrera** que la FIA anuncia
dos semanas antes de cada competición (artículo **B6.1.2 b ii**, hasta un máximo de dos). En
**Mónaco** se exige además un mínimo de **tres juegos**: una doble parada obligatoria. El
incumplimiento se sanciona con **descalificación**.

El módulo de selección tendrá por invariante que **no puede** devolver un compuesto fuera del
conjunto admisible: una recomendación ilegal será tratada como defecto, no como estrategia
agresiva.

### 3.3. Tecnología, topología y herramientas

| Componente | Herramienta | Motivo de la elección |
|---|---|---|
| Lenguaje | Python 3.13 | Ecosistema de datos y compatibilidad con `fastf1` |
| Adquisición | `fastf1` 3.8.3 | Única fuente pública de timing por vuelta con datos de neumático |
| Manipulación | `pandas` 2.x, `numpy` 2.x, `pyarrow` | Estándar; Parquet para persistencia |
| **Computación evolutiva** | **`DEAP`** | Biblioteca recomendada por la cátedra para algoritmos genéticos (Unidad 3) |
| **Aprendizaje por refuerzo** | `gymnasium` + demo `demoRL` de la cátedra | Entorno estándar y convenciones del curso (Unidad 5) |
| Modelos de regresión | `LightGBM` 4.x | Componente de degradación dentro del simulador |
| Métricas y partición | `scikit-learn` 1.5 | `GroupKFold`, curvas precisión-exhaustividad |
| Estadística | `scipy` | Ajuste por máxima verosimilitud del *prior* Beta-Binomial |
| Entorno | `uv` | Reproducibilidad de dependencias |
| Calidad | `ruff`, `pytest` | Linting y pruebas |
| Backend | FastAPI + PostgreSQL | Exposición del sistema como servicio |
| Frontend | React 19 + Vite + TypeScript | Interfaz de demostración |

**Topología prevista del Algoritmo Genético:** población de 100 individuos, 200 generaciones,
selección por torneo de tamaño 3 con elitismo, probabilidad de cruza 0,7 y de mutación 0,2. Cada
evaluación de aptitud promedia 200 realizaciones Monte Carlo.

**Topología prevista del regresor de degradación:** LightGBM, 400 árboles, tasa 0,05, 31 hojas.

**Topología prevista del clasificador de contraste:** LightGBM, 300 árboles, tasa 0,05, 31 hojas,
con `scale_pos_weight` igual a la razón entre clases para compensar el desbalance de 28:1.

**Alternativa descartada:** una red neuronal profunda extremo a extremo. La estrategia exige
justificación, 12 carreras no sostienen esa complejidad, y además el MLP ya fue la técnica del
antecedente propio de 2025 (sección 6.2), con resultados limitados.

---

## 4. Desarrollo

Esta sección describe **el plan de trabajo**. El prototipo aún no está construido; lo que sí está
hecho es el estudio de factibilidad que se resume en 4.2 y que sustenta el plan.

### 4.1. Plan de construcción

| Etapa | Contenido | Estado |
|---|---|---|
| Infraestructura | Monorepo con backend, workspace de ML y frontend | **Hecho** |
| Adquisición y preparación | Pipeline `ingest → features` con las seis transformaciones de 2.3 | **Hecho** |
| Estudio de factibilidad | Verificación de que los datos sostienen el planteo | **Hecho** |
| **Capa 1** — regresor de degradación | Entrenamiento y ajuste sobre el conjunto de 2026 | Pendiente |
| **Capa 2** — motor de reglas | Implementación de R1–R14 y las tablas de decisión | Pendiente |
| **Capa 3** — simulador Monte Carlo | Sorteo de eventos y ejecución del motor | **Pendiente — es el entregable central** |
| Modelo de contraste | Clasificador supervisado como línea base declarada | Pendiente |
| Validación prospectiva | Pronósticos fechados sobre las carreras restantes | Pendiente |

### 4.2. Estudio de factibilidad: seis problemas ya detectados

Antes de comprometerse con un diseño se construyó el pipeline y se midió. Se hallaron seis
problemas que habrían corrompido silenciosamente los resultados:

| # | Problema | Cómo se resolvió |
|---|---|---|
| 1 | Fuga por patrón de faltantes (87,2% contra 0,0%) | Desfase de una vuelta en las variables de ritmo |
| 2 | Paradas gratuitas bajo bandera roja: 21 de 22 pilotos "boxearon" en la vuelta 2 en Zandvoort | Separación de `free_stop` y `strategic_stop` |
| 3 | Nombres de circuito inestables entre temporadas (`Monaco` contra `Monte Carlo`) | Tabla de alias |
| 4 | *Prior* estimado por método de momentos: fuerza de 0,79 pseudo-visitas, es decir ningún encogimiento | Máxima verosimilitud Beta-Binomial (24,1 pseudo-visitas) |
| 5 | Objetivo del regresor mal planteado: predecía tiempo absoluto en circuitos nunca vistos | Reformulado a degradación relativa al stint |
| 6 | Tope de 500 llamadas/hora de la API | Caché por tandas y modo *offline* |

### 4.3. Hallazgos preliminares que determinan el diseño

**La predicción puntual no funciona.** Se ensayaron cuatro objetivos puntuales distintos y
ninguno superó a un modelo ingenuo:

| Objetivo | Resultado | Ingenuo |
|---|---|---|
| Tiempo de vuelta absoluto | MAE 13,05 s | 9,39 s |
| Degradación por vuelta | MAE 0,937 s | 0,716 s |
| Duración del stint | MAE 8,13 vueltas | 8,02 |
| Cantidad de paradas | 32,1% exacto | 32,0% |

**La medición agregada sí funciona.** Toda medición agregada dio resultados nítidos:

- **La jerarquía de compuestos se invirtió en 2026.** El blando pasó de ser el que más se degrada
  (0,0673 s/vuelta en 2024) al que menos (0,0142); el duro es ahora el que más. Esto es lo que
  impide mezclar temporadas.
- **Una parada bajo neutralización cuesta 0 posiciones**, contra 2 en verde — aunque en segundos
  parezca más cara (32,6 s contra 22,2 s), porque bajo Safety Car el pelotón circula agrupado.
- **Los equipos lo explotan:** el 9,6% de las vueltas están neutralizadas pero allí se toma el
  **30,8%** de las paradas, una sobrerrepresentación de **3,20×**.
- **El reglamento se cumple:** de los 177 pilotos que terminaron una carrera en seco, los 177
  usaron dos o más compuestos. Cero violaciones.

Este contraste —lo agregado se mide bien, lo puntual no— es la razón por la cual se propone un
sistema que emita **distribuciones** y no valores puntuales.

---

## 5. Resultados

El prototipo aún no ha sido probado. Esta sección define **qué resultados se producirán y cómo se
medirán**, de modo que el criterio de éxito quede fijado antes de construir.

### 5.1. Métricas que se calcularán

| Componente | Métrica | Criterio de éxito |
|---|---|---|
| Regresor de degradación | MAE en s/vuelta sobre el conjunto de prueba | Superar al modelo ingenuo de la mediana |
| Clasificador de contraste | PR-AUC, F1, precisión, exhaustividad, matriz de confusión | Reportar siempre la **mejora sobre el azar**, no la métrica sola |
| **Sistema completo** | **Cobertura del intervalo** | ¿La estrategia real cayó dentro del intervalo pronosticado? |
| **Sistema completo** | **Calibración** | De las carreras a las que se asigne 70% de probabilidad de una parada, ¿ocurre en ~70%? |
| Sistema completo | Delta de posiciones contrafáctico | Posiciones ganadas o perdidas simulando la estrategia recomendada |
| Motor de reglas | Cobertura y legalidad | Porcentaje resuelto por regla explícita; **cero** recomendaciones ilegales |

### 5.2. La exactitud queda excluida del informe

"Nunca boxear" acierta el **96,6%** de las vueltas del conjunto de prueba. Pero además de
inútil, **esa estrategia es ilegal**: el artículo B6.3.8 la sanciona con **descalificación**.

Un clasificador que maximice exactitud converge por lo tanto a una estrategia que termina en
exclusión de los resultados. La métrica no premia algo poco informativo, premia algo prohibido.

### 5.3. Ejemplos de casos que se documentarán

Se reportarán casos resueltos con éxito y casos fallidos. El estudio de factibilidad ya
identificó un caso fallido paradigmático que servirá de referencia:

**GP de Países Bajos 2026 (Zandvoort).** Bandera roja en la vuelta 2, dos períodos de VSC, y
estrategias modales de tres paradas. El 40% de las paradas cayó en vueltas neutralizadas contra
un 15% de vueltas neutralizadas. Ninguna variable previa a la carrera podía anticiparlo. Un
pronóstico puntual de "tres paradas" habría acertado por casualidad y por la razón equivocada: la
moda de tres incluye un cambio gratuito que nadie eligió.

Un pronóstico distribucional, en cambio, habría dicho algo honesto y puntuable: *"lo más probable
son dos paradas estratégicas; entre 15% y 20% de probabilidad de una carrera de tres o más
dirigida por neutralizaciones"*.

### 5.4. Validación prospectiva

Se propone **publicar un pronóstico fechado y congelado antes de cada carrera restante** y
puntuarlo después. Restan 11 carreras:

| Ronda | Circuito | Fecha | Formato |
|---|---|---|---|
| 13 | Monza | 2026-09-06 | Convencional |
| 14 | Barcelona | 2026-09-13 | Convencional |
| 15 | Bakú | 2026-09-26 | Convencional |
| 16 | Sakhir | 2026-10-04 | Convencional |
| 17 | Marina Bay | 2026-10-11 | Sprint |
| 18–23 | Austin → Abu Dhabi | oct–dic | Convencional |

Diez de las once son fines de semana convencionales con FP1, FP2 y FP3 completos. Este
mecanismo **no admite fuga de datos ni ajuste a posteriori**, y el calendario coincide con el
cuatrimestre.

---

## 6. Análisis de los Resultados

Esta sección define **cómo se analizarán** los resultados una vez obtenidos.

### 6.1. Comparación contra líneas base

Todo resultado se reportará contra dos referencias obligatorias: el **modelo ingenuo**
correspondiente (mediana para regresión, tasa positiva para clasificación) y el **azar**. Una
métrica sin su línea base no se considerará informativa.

### 6.2. Antecedente propio y su relación con este trabajo

Integrantes de este grupo desarrollaron en 2025, para la asignatura Inteligencia Artificial, el
TP N.º 2 *"Clasificación de Compuesto para la Fórmula 1 utilizando una Red Neuronal Artificial
del Tipo Multiperceptrón"* (Pasqualino et al., 2025), también sobre datos de FastF1. **Se declara
explícitamente**, y la comparación forma parte del análisis previsto.

| Dimensión | TP2 — IA 2025 | Este trabajo |
|---|---|---|
| Temporadas | 2020–2022 | **2026**, primer año del nuevo reglamento |
| Pregunta | ¿Qué compuesto elegir? | **¿Cuándo parar y cuántas veces?** |
| Salida | Clase puntual (S/M/H) | **Distribución** de estrategias |
| Técnica | MLP puro | **Híbrido**: regresión + reglas + Monte Carlo |
| Volumen | 782 registros | **14.095 vueltas**, 756 stints |
| Partición | 80/20 aleatoria | **Por carrera**, 25%, más pronóstico prospectivo |
| Reglamento | No modelado | **Filtro duro** (B6.3.8, B6.1.2) |

Aquel trabajo obtuvo entre 0,62 y 0,70 de exactitud con sobreajuste persistente, especialmente
sobre la clase SOFT. Este trabajo aporta una **explicación** de aquel resultado, que se
verificará como parte del análisis:

> En 2026 la elección de compuesto está en buena medida **determinada por el reglamento** —el
> artículo B6.3.8 obliga a usar una especificación obligatoria anunciada por la FIA— y la
> diferencia de degradación entre compuestos es de apenas 0,029 s/vuelta. La hipótesis es que no
> se trataba de un problema de arquitectura de red sino de un **problema mal planteado**: se
> intentaba aprender algo que en buena parte es una restricción, no un patrón.

Por ese motivo, aquí la elección de compuesto se resuelve mediante un **filtro reglamentario** y
no mediante un clasificador, y el esfuerzo de aprendizaje se traslada al momento de la parada.

Se incorporan además tres correcciones metodológicas señaladas por la corrección de aquel
trabajo: **ponderación explícita del desbalanceo** (aquí 28:1, peor que el de entonces), **uso de
*early stopping***, y **partición agrupada por carrera** para evitar la fuga que una partición
aleatoria sobre registros de parada probablemente introdujo.

### 6.3. Comparación con el estado del arte

El trabajo de referencia (Chaudhary et al., 2025) reporta **F1 = 0,81** con Bi-LSTM sobre datos
de 2020–2024. Se comparará contra esa cifra explicando las diferencias metodológicas: ellos
modelan el stint como **secuencia** y no como instantáneas tabulares por vuelta, entrenan con
unas 100 carreras contra nuestras 12, y su definición de ventana puede ser más amplia.

**La novedad de este trabajo no es el problema sino la temporada.** El problema está trabajado;
ningún trabajo publicado puede haber usado datos de 2026, porque el reglamento cambió este año.
Citar el antecedente y explicar por qué su modelo **no transfiere** es un aporte concreto.

### 6.4. Discrepancia ya detectada con análisis publicado

Un análisis público sostiene que la dispersión de degradación entre compuestos en 2026 es de
0,008 s/vuelta, la más baja de la era. **No se reproduce:** medimos 0,0293 s/vuelta en 2026
contra 0,0297 en 2024. La inversión de la jerarquía sí se reproduce; el colapso de la dispersión
no. La causa probable es el estimador. Se resolverá agregando un estimador por stint y **no se
citará ninguna de las dos cifras como establecida** hasta entonces.

### 6.5. Análisis de la curva de aprendizaje

Al entrenar con 3, 6, 9 y 12 carreras, el PR-AUC bajó de 0,3163 a 0,1028. Se analizará
explícitamente: **no** es que los datos perjudiquen, sino que con tres carreras cada pliegue de
validación es una sola carrera y el modelo se aferra a particularidades de circuito que se
repiten. Es optimismo de muestra pequeña. La consecuencia práctica es que **esperar más carreras
no rescatará el planteo puntual** — otro argumento a favor del enfoque distribucional.

---

## 7. Conclusiones

Esta propuesta plantea un Sistema Inteligente de estrategia de neumáticos para la temporada 2026
de Fórmula 1, con una arquitectura híbrida de tres capas y salida distribucional.

Las decisiones de diseño no son preferencias: cada una responde a una medición del estudio de
factibilidad.

1. **Salida distribucional en lugar de puntual**, porque cuatro objetivos puntuales distintos
   empataron o perdieron contra modelos ingenuos, mientras que toda medición agregada dio
   resultados nítidos.
2. **Costo medido en posiciones y no en segundos**, porque bajo neutralización una parada cuesta
   0 posiciones contra 2 en verde, y los equipos lo explotan 3,20× por encima del azar.
3. **Motor de reglas como capa decisoria**, porque un clasificador que maximice exactitud
   converge a "nunca boxear", que es descalificación. El motor de reglas hace esa salida
   **irrepresentable**.
4. **Temporada 2026 exclusivamente**, porque la jerarquía de compuestos se invirtió.
5. **La mitad energética declarada fuera de alcance**, porque el dato no existe públicamente.

### 7.1. Cursos de acción y viabilidad

| Acción | Justificación | Viabilidad |
|---|---|---|
| **Construir el simulador Monte Carlo** | Único planteo compatible con la evidencia | **Alta.** Los tres insumos —degradación, tasas de neutralización, costo en posiciones— ya están medidos |
| **Emitir pronósticos prospectivos fechados** | No admite fuga ni ajuste a posteriori | **Alta.** Restan 11 carreras dentro del cuatrimestre |
| Reajustar el coeficiente de combustible con datos 2026 | Está fijo en 0,035 s/vuelta, calibrado en la era anterior; hoy es el supuesto más débil | **Alta** |
| Completar el caché de 2022 a 2025 | Elevaría de 4 a 8 visitas por circuito y permitiría decidir si los efectos por circuito existen | **Alta**, limitada por el tope de 500 llamadas/hora |
| Modelo de secuencia sobre el historial del stint | Única diferencia metodológica clara contra el estado del arte | Media |
| Modelo de supervivencia con censura | Se descartan 178 stints que terminaron en bandera a cuadros | Media |
| Aprendizaje por refuerzo sobre el simulador | Abordaje ideal una vez que exista el simulador | Baja para este cuatrimestre |

**Riesgo principal asumido:** un pronóstico congelado puede fallar en público. Es deliberado. Se
puntuará la **calibración**, no el acierto puntual.

---

## Referencias

Chaudhary, S. et al. (2025). *Data-driven pit stop decision support for Formula 1 using deep
learning models*. Frontiers in Artificial Intelligence, vol. 8.
https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full

Pasqualino, F.; Denoya, A.; Sánchez, C.; Sánchez, T.; Lingeri, M. (2025). *Clasificación de
Compuesto para la Fórmula 1 utilizando una Red Neuronal Artificial del Tipo Multiperceptrón*.
Trabajo Práctico N.º 2, Inteligencia Artificial, Universidad Tecnológica Nacional — Facultad
Regional Buenos Aires. https://github.com/FrancoP08/TP2-IA-2025

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
Contiene el paquete `boxbox_ml`, los scripts que reproducen cada medición del estudio de
factibilidad (`scripts/holdout_eval.py`, `scripts/era_compare.py`, `scripts/pit_loss.py`,
`scripts/safety_car_rates.py`, entre otros) y los documentos de investigación en
`docs/research/`. Los datos no se versionan: se reconstruyen ejecutando
`uv run boxbox-ingest --seasons 2026`.

# BoxBox — Estrategia de neumáticos en Fórmula 1

**Propuesta de Trabajo Práctico Integral**
Inteligencia Artificial Avanzada — UTN FRBA — 2do Cuatrimestre 2026

| Apellido y Nombres | E-Mail | Aporte |
|---|---|---|
| Sánchez, Tomás Agustín | _(completar)_ | 100% |

**Fecha de Presentación:** _(completar)_

---

## Resumen

En una carrera de Fórmula 1, el equipo tiene que decidir cuándo parar en boxes y qué neumático
poner. Es una decisión difícil: depende del desgaste de la goma, de los rivales cercanos y de si
sale un Safety Car.

Este trabajo propone un sistema que **arma el plan de neumáticos de una carrera**: cuántas
paradas hacer, en qué vueltas y con qué compuesto. No predice quién gana.

El foco está en la temporada **2026**, la primera del nuevo reglamento. Para entrenar se usan
además las temporadas anteriores: se midió que agregarlas mejora el modelo un 56%, aunque el
orden de desgaste de los compuestos se haya invertido este año.

La idea central es un **simulador de carrera** y, sobre él, un **Algoritmo Genético** que busca
el mejor plan. Como comparación se usa un **agente de Aprendizaje por Refuerzo** que decide
vuelta a vuelta.

---

## 1. Introducción

Cada vuelta, el ingeniero de estrategia tiene que responder una pregunta simple de enunciar y
difícil de contestar: ¿entro a boxes ahora o sigo?

Si entra, pierde unos 20 segundos. Si no entra, pierde tiempo con la goma gastada. Y si sale un
Safety Car justo después, la decisión que parecía buena se convierte en mala.

**Objetivo:** construir un sistema que, para una carrera dada, calcule el plan de neumáticos más
conveniente y explique por qué.

El sistema entrega, para cada piloto:

- la probabilidad de que convenga 1, 2 o 3 paradas;
- la secuencia de compuestos más probable;
- un rango de vueltas para la primera parada.

**Qué queda afuera:** la gestión de energía. En 2026 la mitad de la potencia es eléctrica y el
manejo de la batería es parte de la estrategia. Pero **la Fórmula 1 no publica esos datos**. Lo
verificamos: los canales de telemetría no los traen. Entonces el sistema trabaja con la parte de
neumáticos y posición, y esto se aclara desde el principio.

---

## 2. Materiales Disponibles

### Datos

Se usa la librería **`fastf1`** de Python, que da los datos oficiales de cronometraje.

Las columnas que importan (compuesto, edad del neumático, número de stint, estado de pista)
están completas al 100%. De 2026 salen 14.095 vueltas, 756 stints (tandas con un juego de gomas)
y 527 paradas.

### Cómo quedó armado el conjunto de datos

`fastf1` tiene un tope de **500 llamadas por hora**. Al bajar varias temporadas de una vez, el
tope se alcanza a mitad de camino y las carreras restantes se descartan **sin aviso**. Nos pasó:
durante un tiempo el caché tenía 2023 y 2024 cortadas por la mitad y **2025 no estaba en
absoluto**, no por criterio sino por accidente.

Se descargó lo que faltaba por tandas. Estado actual:

| Temporada | Calendario | Descargadas | Estado |
|---|---|---|---|
| 2022 | 22 | 22 | Completa |
| 2023 | 22 | 22 | Completa |
| 2024 | 24 | 24 | Completa |
| 2025 | 24 | 24 | Completa |
| 2026 | 23 | 12 | Al día — la temporada está en curso |
| **Total** | | **104 carreras** | ~112.000 vueltas |

Vale la pena dejar constancia de dos cosas que aprendimos ahí:

**El caché incompleto sesgaba las estimaciones sin que se notara.** De 2023 y 2024 teníamos sólo
la primera mitad del año, así que los circuitos de fin de temporada —Austin, México, Brasil, Las
Vegas, Qatar— estaban sub-representados. Al completar los datos, la degradación medida del
compuesto blando en 2023 pasó de 0,0664 a **0,0403 s/vuelta**. Era un 60% de error, invisible
hasta que se comparó.

**Un tope de API que descarta en silencio es un riesgo de datos, no una molestia técnica.** Por
eso el proceso de descarga ahora informa cuántas carreras trajo y cuántas falló.

### Qué datos se usan para qué

Al principio decidimos usar **sólo 2026**, porque este año se invirtió el orden de desgaste de
los compuestos: el blando pasó de ser el que más se gastaba al que menos. La idea era que
entrenar con años anteriores le enseñaría al modelo lo contrario de lo que pasa hoy.

**Lo medimos y la decisión estaba mal.** Entrenando y probando siempre sobre las mismas carreras
de 2026:

| Entrenamiento | Vueltas | PR-AUC | Sobre el azar |
|---|---|---|---|
| Sólo 2026 | 10.143 | 0,1430 | 4,24× |
| **Con 2022–2025 sumadas** | **107.308** | **0,2238** | **6,64×** |

Mezclar mejora un **56%**. El error de razonamiento fue este: la inversión afecta **una** de las
diecinueve variables. Las otras —diferencias con los rivales, vuelta del stint, vueltas
restantes, estado de pista— sirven igual en cualquier temporada.

Probamos también agregar la temporada como variable, para que el modelo pudiera distinguir las
eras. **Empeora** (0,1896 contra 0,2238). Aprende mejor los patrones generales si no se lo invita
a separar por año.

Así que la regla no es global, **depende del componente**:

| Para qué | Qué datos | Por qué |
|---|---|---|
| Entrenar los modelos | Todas las temporadas | Medido: 56% mejor |
| Tasas de Safety Car por circuito | Todas las temporadas | Con 12 carreras hay **una sola visita** por circuito; con una temporada es imposible estimarlo |
| Costo de parar en boxes | Todas las temporadas | Depende del largo del pit lane, no del auto |
| **Desgaste por compuesto** | **Sólo 2026** | Acá sí cambió el comportamiento |
| **Efecto del combustible** | **Sólo 2026** | Los autos son ~32 kg más livianos |
| Reglamento | **Sólo 2026** | El artículo B6.3.8 es de este año |

Conviene aclarar que el trabajo **sigue siendo sobre 2026**. Lo nuevo es la temporada que se
analiza y se pronostica, no la cantidad de datos con la que se entrena. Usar menos datos para
poder decir "sólo 2026" habría sido perder precisión a cambio de una frase.

También se usa el **Reglamento Deportivo 2026 de la FIA**, que obliga a usar al menos dos
compuestos distintos de seco por carrera. Si no se cumple, el piloto queda descalificado.

### Preparación de los datos

Al armar el pipeline aparecieron cuatro problemas que hay que corregir sí o sí:

**1. Las vueltas de entrada y salida de boxes no sirven para medir ritmo.** Incluyen el paso por
el pit lane. Se marcan aparte. Quedan usables el 90% de las vueltas.

**2. El combustible.** Un auto con más nafta es más lento. Se resta ese efecto para poder
comparar la vuelta 8 con la vuelta 45.

**3. `TyreLife` no es lo mismo que "vueltas de este stint".** Un piloto que arranca con gomas ya
usadas en clasificación empieza la carrera con `TyreLife = 4`. Hay que contar las vueltas dentro
del stint aparte.

**4. Los cambios de goma bajo bandera roja son gratis.** Con la carrera detenida, cambiar
neumáticos no cuesta tiempo. En Zandvoort 2026, 21 de 22 pilotos "pararon" en la vuelta 2 por una
bandera roja. Si eso se mezcla con las paradas normales, el modelo aprende que parar a veces sale
gratis. Se separan en dos etiquetas distintas.

### Cómo se separan los datos

**Se separa por carrera, no por vuelta.** Dos vueltas seguidas de la misma tanda son casi
iguales; si quedan una en entrenamiento y otra en prueba, el modelo hace trampa sin querer.

**La prueba se hace siempre sobre 2026.** No tendría sentido medir en 2024 un sistema pensado
para el reglamento de este año.

Se reservan **las últimas 3 carreras de 2026 de las 12 disponibles: el 25%**. Se eligen las más
recientes y no tres al azar, porque eso se parece a lo que el sistema tiene que hacer realmente:
predecir carreras que todavía no pasaron.

| | Carreras | Vueltas | Paradas |
|---|---|---|---|
| **Prueba** — 2026 R10–12 | **3 de 12 de 2026 (25%)** | **3.501** | **118** |
| Entrenamiento — 2026 R1–9 | 9 | 10.143 | 350 |
| Entrenamiento — más 2022–2025 | 92 | 97.165 | ~3.000 |

O sea: el 25% de prueba se cumple sobre las carreras de 2026, que es el universo que importa. Las
temporadas anteriores **sólo entran en entrenamiento**, nunca en prueba.

Dentro del entrenamiento se valida con `GroupKFold` agrupando por carrera, así ninguna carrera
aparece a la vez en entrenamiento y validación.

---

## 3. Solución Propuesta

Tres piezas:

**1. Simulador de carrera (la base).** Simula una carrera vuelta a vuelta: cuánto se degrada cada
goma, cuánto cuesta parar, y si sale o no un Safety Car. Se corre miles de veces para ver todos
los escenarios posibles. No es una técnica de IA: es el banco de pruebas de las que sí lo son.

**2. Algoritmo Genético (la técnica principal — Unidad 3).**

| | |
|---|---|
| **Cromosoma** | El plan de carrera. Ejemplo: `[(18, Medio), (25, Duro), (14, Blando)]` |
| **Aptitud** | La posición final que da el simulador |
| **Restricción** | El reglamento decide qué planes son válidos |
| **Operadores** | Cruza de un punto; mutación que alarga, acorta o cambia una tanda |

Se usa **DEAP**, la librería que recomienda la cátedra. Se van a comparar distintos operadores de
selección y cruza, no elegir uno solo.

**3. Agente de Aprendizaje por Refuerzo (comparación — Unidad 5).** Un agente que decide "paro o
sigo" vuelta a vuelta dentro del mismo simulador. Sirve para comparar dos formas de pensar:
planificar toda la carrera de antemano (el algoritmo genético) contra reaccionar a lo que va
pasando (el agente).

El simulador se programa con la interfaz **`gymnasium`**, así sirve para las dos cosas sin
escribirlo dos veces.

**Herramientas:** Python, `fastf1`, `pandas`, `DEAP`, `gymnasium`, `LightGBM`, Google Colab.

**Línea futura:** una red bayesiana con `pgmpy` para modelar la incertidumbre del Safety Car. Se
declara como línea futura y no como promesa: el trabajo es individual y prometer cuatro técnicas
para entregar una es peor que proponer dos y cumplirlas.

---

## 4. Desarrollo

### Lo que ya está hecho

- El pipeline de datos completo: descarga, limpieza y cálculo de variables.
- Un estudio previo para verificar que los datos alcanzan.

### Lo que falta

- El simulador de carrera.
- El algoritmo genético.
- El agente de refuerzo.

### Lo que encontramos al probar

Hicimos pruebas antes de decidir el diseño. **El resultado más importante es negativo:**
predecir un valor exacto no funciona.

| Lo que intentamos predecir | Nuestro modelo | Predecir siempre la mediana | |
|---|---|---|---|
| Tiempo de vuelta | 13,05 s de error | 9,39 s | pierde |
| Degradación por vuelta, sólo 2026 | 0,937 s | 0,716 s | pierde |
| **Degradación por vuelta, con todas las temporadas** | **0,698 s** | 0,726 s | **gana** |
| Duración de una tanda | 8,13 vueltas | 8,02 | empata |
| Cantidad de paradas | 32,1% de acierto | 32,0% | empata |

**Acá hay que matizar lo que dijimos antes.** Con sólo 2026 los cuatro intentos perdían o
empataban. Al completar los datos, el modelo de degradación **pasa a ganarle al modelo tonto**.
O sea que «no se puede predecir» era en parte falta de datos, no una propiedad del problema.

Las otras dos pruebas —duración de tanda y cantidad de paradas— todavía no se repitieron con el
conjunto completo. Hay que hacerlo antes de afirmar nada sobre ellas.

**En cambio, medir promedios sí funciona bien:**

- En 2026 **se invirtió el orden de desgaste**: el blando pasó de ser el que más se gastaba
  (0,0673 s/vuelta en 2024) al que menos (0,0142). Es un cambio real y grande.
- Parar bajo Safety Car **cuesta 0 posiciones**, contra 2 posiciones en carrera normal.
- Los equipos lo saben: el 9,6% de las vueltas están neutralizadas, pero ahí se toma el **30,8%**
  de las paradas.

**También cambiamos de idea sobre los datos.** La primera versión de esta propuesta decía que no
se podían mezclar temporadas. Al medirlo resultó lo contrario: mezclar mejora un 56% (sección 2).
Se deja asentado porque una propuesta que esconde en qué se equivocó no sirve de nada.

**Conclusión:** el argumento a favor de dar un rango en vez de un número **no es** que los
modelos no den. Es que buena parte de lo que decide una estrategia —una bandera roja en la vuelta
2, un Safety Car a mitad de carrera— es **imposible de saber de antemano**, por más datos que se
tengan. La estrategia depende más de lo que pasa en la carrera que de la física del
neumático. Por eso el sistema tiene que dar **un rango de posibilidades, no un número exacto**.

---

## 5. Resultados

Todavía no hay prototipo, así que acá se define **qué se va a medir**.

| Qué | Cómo se mide | Cuándo está bien |
|---|---|---|
| Simulador | Error del modelo de degradación | Mejor que predecir la mediana |
| Algoritmo genético | Posiciones ganadas contra la estrategia real del equipo | Ganar posiciones en promedio |
| Sistema completo | **¿La estrategia real cayó dentro del rango que predijimos?** | La métrica principal |
| Sistema completo | **Calibración**: si decimos 70% de chance de una parada, ¿pasa el 70% de las veces? | |
| Reglamento | Planes ilegales generados | **Cero** |

### La exactitud no se usa como métrica

"No parar nunca" acierta el **96,6%** de las vueltas. Pero además de inútil, **es ilegal**: el
reglamento obliga a usar dos compuestos y no hacerlo es descalificación.

O sea: un modelo que busque maximizar exactitud termina proponiendo algo que te deja afuera de la
carrera. Por eso el reglamento va como filtro y no como sugerencia.

### Prueba en carreras futuras

Quedan 11 carreras. La idea es **publicar la predicción antes de cada carrera y después
compararla con lo que pasó**. Empezando por Monza, el 6 de septiembre.

Esto tiene una ventaja grande: no se puede hacer trampa. La predicción queda escrita antes.

---

## 6. Análisis de los Resultados

**Contra modelos simples.** Todo resultado se compara siempre contra "predecir la mediana" o
"tirar al azar". Un número solo, sin esa comparación, no dice nada.

**Contra trabajos previos.** Hay un paper de 2025 (Chaudhary et al.) que hace algo parecido con
redes neuronales sobre datos de 2020 a 2024, y llega a F1 = 0,81. Se va a comparar contra eso
explicando las diferencias. **Lo nuevo acá no es el problema, es la temporada:** ningún trabajo
publicado pudo usar datos de 2026, porque el reglamento cambió este año.

**Contra un trabajo propio.** En 2025 hice el TP de la materia Inteligencia Artificial sobre este
mismo tema: clasificar el compuesto con una red neuronal MLP, con datos de 2020 a 2022. Se
declara acá y se compara:

| | TP de IA 2025 | Este trabajo |
|---|---|---|
| Datos | 2020–2022, 782 registros | 2026, 14.095 vueltas |
| Pregunta | ¿Qué compuesto? | ¿Cuándo parar y cuántas veces? |
| Técnica | Red neuronal MLP (Unidad 2) | Algoritmo Genético y Refuerzo (Unidades 3 y 5) |
| Resultado | 0,62–0,70 de exactitud, con sobreajuste | — |

Aquel trabajo trató de **aprender** qué compuesto elegir y no le fue del todo bien. Este trabajo
propone una explicación: en 2026 esa elección está **decidida en buena parte por el reglamento**,
y la diferencia de desgaste entre compuestos es de apenas 0,029 s/vuelta. No era un problema de
la red neuronal: era una pregunta mal planteada.

---

## 7. Conclusiones

1. **Predecir un valor exacto es difícil, pero no imposible.** Con sólo 2026 los cuatro intentos
   perdían. Con las cinco temporadas, el modelo de degradación ya gana. Lo que sigue sin poder
   anticiparse son los **eventos de carrera**, y eso no se arregla con más datos.
2. **Medir promedios sí se puede**, y alcanza para armar un sistema útil.
3. **El costo de parar se mide en posiciones, no en segundos.** Bajo Safety Car son 0 posiciones
   contra 2 en carrera normal.
4. **El reglamento es una ventaja, no una molestia.** Impide que el sistema proponga algo ilegal.
5. **Las temporadas anteriores sí sirven, pero no para todo.** Mezclarlas mejora el clasificador
   un 56% (de 4,24× a 6,64× sobre el azar). Pero las magnitudes de degradación por compuesto y el
   efecto del combustible se toman sólo de 2026, porque ahí sí cambió el comportamiento.

### Qué sigue

| Acción | Por qué | ¿Se puede? |
|---|---|---|
| Armar el simulador | Es la base de todo lo demás | Sí, los datos que necesita ya están medidos |
| Algoritmo genético con DEAP | Es la técnica principal | Sí, para la Entrega 2 |
| Agente de refuerzo | Comparación | Sí, si el genético ya está listo |
| Red bayesiana | Modelar el Safety Car | Sólo como línea futura |
| Reajustar el efecto del combustible | Hoy es un número fijo de la era anterior | Sí, es rápido |

**Riesgo que se asume:** publicar una predicción antes de la carrera puede salir mal en público.
Es a propósito. Se evalúa si el rango estaba bien calculado, no si se acertó justo.

---

## Referencias

Chaudhary, S. et al. (2025). *Data-driven pit stop decision support for Formula 1 using deep
learning models*. Frontiers in Artificial Intelligence, vol. 8.

Fédération Internationale de l'Automobile (2026). *2026 Formula 1 Sporting Regulations —
Section B*, Issue 05. Artículos B6.1.1, B6.1.2 y B6.3.8. https://www.fia.com/regulation/category/110

Schäfer, P. et al. (2026). *FastF1*, versión 3.8.3. https://docs.fastf1.dev/

Fortin, F. et al. (2012). *DEAP: Evolutionary Algorithms Made Easy*. Journal of Machine Learning
Research, vol. 13, pp. 2171–2175.

Ke, G. et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*. NIPS 2017.

Pasqualino, F.; Denoya, A.; Sánchez, C.; Sánchez, T.; Lingeri, M. (2025). *Clasificación de
Compuesto para la Fórmula 1 utilizando una Red Neuronal Artificial del Tipo Multiperceptrón*.
TP N.º 2, Inteligencia Artificial, UTN FRBA. https://github.com/FrancoP08/TP2-IA-2025

**Repositorio:** _(completar)_

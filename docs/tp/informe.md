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
el mejor plan. Como comparación se propone un **agente de Aprendizaje por Refuerzo** que decide
vuelta a vuelta.

**Estado.** El pipeline de datos, el simulador y el algoritmo genético están construidos y
medidos; el agente de refuerzo no. El algoritmo le gana entre 7 y 11 segundos de carrera a
cualquier regla que se pueda enunciar de antemano, y lo que gana es el valor de acertar la cantidad
de paradas.

Ese resultado corrige una versión anterior de este informe, que reportaba que el algoritmo apenas
le ganaba a una regla simple. Esa conclusión salía de una comparación mal armada, a favor de la
regla, y de cuatro defectos de método en la búsqueda. Las secciones 4 y 5 documentan los siete
errores propios que se encontraron y corrigieron, porque todos daban números confiados y plausibles
hasta que algo aguas abajo salió absurdo.

La prueba más dura la dio Monza 2026, cuatro fechas después de la carrera sobre la que está armado
el simulador: **el modelo se equivocó por veintiún segundos**, y por qué se equivocó es el
resultado más útil del trabajo. Está en la sección 6.

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

Un algoritmo genético busca la mejor solución imitando la evolución: prueba muchas opciones, se
queda con las mejores, las combina entre sí y repite el proceso muchas veces.

Acá cada "individuo" es **un plan de carrera completo**. Por ejemplo:

> *Arrancar con neumático Medio y parar en la vuelta 18. Poner Duro y parar en la vuelta 43.
> Terminar con Blando.*

El procedimiento es:

1. **Se generan 100 planes al azar.**
2. **Se le pone una nota a cada uno.** Se simula la carrera con ese plan y se mira en qué
   posición termina el auto. Cuanto más adelante, mejor la nota. A eso se lo llama **función de
   aptitud**.
3. **Se eligen los mejores y se combinan.** De dos planes buenos sale uno nuevo que toma el
   principio de uno y el final del otro. Eso es el **cruce**.
4. **De vez en cuando se cambia algo al azar:** alargar un stint dos vueltas, acortarlo, o
   cambiar el compuesto. Eso es la **mutación**, y sirve para que la búsqueda no se quede
   siempre dando vueltas alrededor de las mismas ideas.
5. **Se repite 200 veces.** Los planes malos se descartan, los buenos se mezclan entre sí, y al
   final queda el mejor que se encontró.

**El reglamento actúa como filtro.** Un plan que use un solo compuesto de seco queda descartado
de entrada, porque en la carrera real sería descalificación. Nunca llega a competir.

**Sobre DEAP.** La propuesta decía que se iba a usar DEAP, la librería que recomienda la
cátedra. La implementación quedó escrita a medida, porque el genoma es de largo variable —un plan
tiene una, dos o tres paradas— y necesita reglas de reparación propias: ordenar las paradas,
separarlas al menos seis vueltas y forzar una parada cuando la tanda excede lo que la evidencia
puede cotizar. Eso no encaja cómodo en los operadores estándar. Portarlo a DEAP no cambia el
modelo y queda como tarea pendiente, declarada acá y no escondida.

**3. Agente de Aprendizaje por Refuerzo (comparación — Unidad 5).**

El algoritmo genético arma el plan **antes de largar**. Pero en una carrera real las cosas
cambian: sale un Safety Car, empieza a llover, un rival para antes de lo previsto. Un agente de
aprendizaje por refuerzo decide **sobre la marcha**.

La idea es la de enseñarle a jugar a alguien que no sabe las reglas, sólo si le fue bien o mal:

1. **El agente ve el estado de la carrera** en cada vuelta: en qué posición está, cuánto se
   degradó su goma, a cuánto tiene al de adelante y al de atrás, si hay Safety Car.
2. **Elige una acción:** seguir en pista, o boxear y con qué compuesto.
3. **Se simula la carrera hasta el final** y se le da un **premio**: las posiciones que ganó o
   perdió.
4. **Se repite miles de carreras.** Al principio decide cualquier cosa. Con el tiempo aprende
   solo que boxear con Safety Car sale barato y que quedarse demasiado con la goma gastada sale
   caro. Nadie se lo programó: lo dedujo de los premios.

La demo de la cátedra sobre Blackjack (`Q-Blackjack.ipynb`) es el mismo problema con otra ropa:
decidir "pido carta o me planto" bajo incertidumbre, donde seguir conviene hasta cierto punto y
después arruina la mano. Cambiar eso por "sigo o boxeo" es casi cambiarle el nombre.

**Lo interesante es la comparación:** planificar todo de antemano (el genético) contra reaccionar
a lo que va pasando (el agente). Cuál gana, y en qué tipo de carreras gana cada uno, es en sí un
resultado del trabajo.

El simulador se programa con la interfaz **`gymnasium`**, que es la que usa la demo de la
cátedra, así sirve para las dos técnicas sin escribirlo dos veces.

**Herramientas:** Python, `fastf1`, `pandas`, `DEAP`, `gymnasium`, `LightGBM`, Google Colab.

**Línea futura:** una red bayesiana con `pgmpy` para modelar la incertidumbre del Safety Car. Se
declara como línea futura y no como promesa: el trabajo es individual y prometer cuatro técnicas
para entregar una es peor que proponer dos y cumplirlas.

---

## 4. Desarrollo

### Lo que ya está hecho

- **El pipeline de datos completo**: descarga, limpieza y cálculo de variables, sobre 103
  carreras y 114.414 vueltas.
- **El simulador de carrera**, con todo lo que sortea medido: desgaste, pérdida de boxes,
  Safety Car, ruido de ritmo y tráfico.
- **El algoritmo genético**, que para cada auto busca el plan de paradas con mejor distribución
  de resultados sobre cientos de carreras sorteadas.
- **Una interfaz de simulación** que muestra la carrera corriendo con los insights de estrategia
  encima del trazado, al estilo de las gráficas de la transmisión.
- **Tres cuadernos Jupyter** que dejan el registro reproducible de los datos, la limpieza y cada
  medición, con el cálculo a la vista y no sólo el resultado.

### Lo que falta

- El agente de Aprendizaje por Refuerzo, que era la comparación propuesta.
- Portar el genético a **DEAP**. Está escrito a medida porque el genoma es de largo variable con
  reglas de reparación, pero DEAP es la herramienta que recomienda la cátedra y conviene alinearse.
- El tráfico de **rezagados**. El 23,1% de los pilotos terminan al menos una vuelta abajo, y la
  medición actual los excluye por construcción.
- La **ventana de parada** sale hoy de una heurística y debería salir del propio genético.

### Lo que encontramos al probar

Esta sección es la más larga a propósito. La mayoría de lo que sigue son resultados negativos o
correcciones de errores propios, y son la parte del trabajo que más costó.

#### Predecir un valor exacto no funciona bien

| Lo que intentamos predecir | Nuestro modelo | Predecir siempre la mediana | |
|---|---|---|---|
| Tiempo de vuelta | 13,05 s de error | 9,39 s | pierde |
| Degradación por vuelta, sólo 2026 | 0,937 s | 0,716 s | pierde |
| **Degradación por vuelta, con todas las temporadas** | **0,698 s** | 0,726 s | **gana** |
| Duración de una tanda | 8,13 vueltas | 8,02 | empata |
| Cantidad de paradas | 32,1% de acierto | 32,0% | empata |

Con sólo 2026 los cuatro intentos perdían o empataban. Al completar los datos, el modelo de
degradación **pasa a ganarle al modelo tonto**. O sea que «no se puede predecir» era en parte
falta de datos, no una propiedad del problema.

#### La incertidumbre es más grande que la señal

El dato que justifica todo el diseño: en 2026 el **desvío** del ritmo de caída de una tanda
(0,069 s/vuelta en duro, 0,112 en medio, 0,178 en blando) es **más grande que la mediana del
ritmo mismo** (≈0,045 en los tres). Cuánto va a gastar una tanda determinada es, en buena medida,
impredecible.

Eso no es un defecto de la medición: es el motivo por el que el sistema devuelve distribuciones
y no números.

#### El desgaste no se distribuye normal

Medida sobre Zandvoort, la curtosis del ritmo de caída da **48,6 en duro, 32,8 en medio y 20,2 en
blando**. Una normal tiene cero. Unas pocas tandas catastróficas estiran la cola y hacen que el
desvío mienta: el blando tiene desvío 0,66 s/vuelta pero entre el percentil 5 y el 95 va de −0,18
a 0,14. El simulador no asume forma: guarda nueve cortes de la distribución medida y sortea
interpolando.

#### Hubo que ajustar el efecto del combustible, y no fue rápido

La propuesta anterior decía que reajustarlo era «rápido». No lo fue, y el problema es
instructivo.

Dos cosas hacen que las vueltas tardías sean más rápidas: el tanque que se vacía y la pista que
se engoma. **Dentro de una carrera las dos son lineales en el número de vuelta**, así que son
indistinguibles. Un primer diseño metió un efecto fijo por carrera-piloto y regresó contra las
dos juntas: no funciona, y no falla a los gritos. Con el largo de carrera fijo dentro del grupo
los dos regresores son afines —correlación exactamente −1,000— y el ajuste devolvió **−0,043
s/vuelta**, o sea que llevar combustible te haría más rápido.

Para medir desgaste la separación no hace falta: lo que hay que sacarle al tiempo de vuelta es el
efecto completo. Ese sí se identifica, y da **0,056 s/vuelta** sobre 1.627 carreras-piloto,
estable entre 0,047 y 0,062 en las cinco temporadas. Los **0,035** que estaban asumidos sacaban
apenas el **63%**.

Lo que desbloqueó:

| Diferencia de ritmo, mismo piloto y carrera | Con 0,035 | Con 0,056 |
|---|---|---|
| medio − duro | +0,189 s/vuelta | −0,024 |
| blando − medio | −0,160 | −0,015 |
| blando − duro | +0,187 | +0,040 |

Con la constante vieja el **duro salía el más rápido de los tres en las cinco temporadas**. No
era un dato del neumático: el duro se corre en la mediana del 61% de la carrera y el medio en el
26%, y una corrección corta le regala esa ventaja al que corre más tarde.

Corregido, **no hay diferencia de ritmo medible entre compuestos secos**: los tres quedan a menos
de 0,04 s/vuelta entre sí y los cuartiles cruzan el cero. Difieren en desgaste y en vida, no en
ritmo con goma nueva.

#### El desgaste medido se aplana, y es sesgo de supervivencia

Déficit promedio contra vuelta de tanda, sobre 91.000 vueltas: sube hasta la vuelta 20-25 y
después **baja**. Ningún neumático hace eso. Los juegos que llegan a las treinta vueltas son los
que aguantaron; los que no, se cambiaron.

Consecuencia: los datos **no pueden ponerle precio a una tanda larga**, y lo que dicen de ella es
optimista. En vez de inventar una caída sin evidencia, la búsqueda tiene prohibido proponer
tandas más largas que el percentil 90 medido —41 vueltas en duro, 31 en medio, 25 en blando—.
Es un límite a lo que el modelo puede afirmar, no una afirmación sobre la goma.

#### El ritmo de caída que trae cada auto casi no predice

Comparando la pendiente de cinco vueltas medida en la vuelta 10 contra lo que esas tandas
efectivamente hicieron después, sobre 2.492 tandas: **correlación 0,183**, y la estimación
rodante está 3,5 veces sobredispersa. Se encoge al 5%.

Proyectarla cruda no era un error chico: un auto de la foto arrastra −0,549 s/vuelta, que
extrapolado a treinta vueltas dice que va a ganar cuatro minutos, y la búsqueda recomendaba un
plan que lo hacía **ganar desde noveno**.

#### La granularidad por circuito casi nunca la sostienen los datos

Con cuatro o cinco carreras por circuito, la dispersión aparente entre ellos es en buena parte
ruido de una tarde. Se comprobó tres veces —dificultad para adelantar 0,209, corrección por avance
de carrera 0,150, costo del tráfico −0,042 de correlación entre eras— y en las tres se resolvió
usando un número global o encogiendo hacia él. Lo único que sobrevive en las tres es Mónaco,
extremo siempre.

La cuarta cantidad, el desgaste, es la excepción y se trata más abajo.

Este patrón hizo caer una afirmación propia. En una versión anterior se dijo que la dificultad
para adelantar modula el costo del tráfico, apoyado en agrupar circuitos por dificultad. Midiendo
el castigo **por circuito** los dos correlacionan a 0,384 — pero a **0,157 sacando Mónaco**. Y ese
agrupamiento le había asignado a Zandvoort un multiplicador de 1,31 cuando su castigo medido propio
da 0,68: casi el doble, en la dirección equivocada.

También se midió el tráfico en sí, que era el principal sospechoso de por qué el algoritmo no
lucía: **0,544 s/vuelta** a menos de un segundo del auto de adelante, sobre 81.719 vueltas, y el
23,4% de las vueltas verdes se corren ahí. Se implementó cobrándolo vuelta a vuelta —no una vez al
salir de boxes, que resultaba inerte porque el hueco al rejoin es de unos 16 segundos— y **no movió
el resultado**. La hipótesis era razonable y era equivocada.

#### Medir promedios sí funciona

- Parar bajo Safety Car **cuesta 0 posiciones**, contra 2 en carrera normal.
- Los equipos lo saben: el 36% de las paradas estratégicas de Zandvoort ocurren bajo
  neutralización, contra 23% global.
- **La cantidad de paradas depende del compuesto de largada**: largando en duro, 1 parada el 56%
  de las veces; largando en blando, 2 paradas el 55% y 3 el 26%.
- El costo efectivo de una parada es **22,6 s en verde y 19,5 bajo Safety Car**, pero el primer
  cuartil bajo Safety Car es **7,5 s**: reaccionar rápido y reaccionar tarde no son la misma
  decisión.

#### El escalón de ritmo entre compuestos existe, y no se puede usar todavía

Un compuesto tiene tres propiedades: ritmo con goma nueva, ritmo de caída y vida. El modelo tiene
las dos últimas. La primera se midió dentro de la carrera y dio 0,02 a 0,04 s/vuelta, de donde
salió la conclusión de que no había diferencia medible entre compuestos secos.

**Esa conclusión era falsa.** Medido en las prácticas —mismo piloto, misma sesión, poco
combustible, tandas separadas por minutos— sobre 8.422 vueltas:

| Par | n | Mediana |
|---|---|---|
| blando − medio | 279 | **−0,947 s/vuelta** |
| medio − duro | 44 | **−0,957** |
| blando − duro | 115 | −1,027 |

Un segundo entre compuestos vecinos: treinta veces lo que daba la carrera. No se puede medir dentro
de la carrera porque el medio se corre en la mediana del 26% de la distancia y el duro en el 61%, y
la corrección por avance no separa con esa precisión dos cosas que están veinticinco vueltas
apartadas.

Pero **meterlo también da mal**. Con el blando a −1,245 s/vuelta el optimizador recomienda blando
para toda la carrera, que no lo hace ningún equipo; bajando la escala al 10% sigue eligiendo
blando. Una vuelta de práctica mide el pico de agarre con poco combustible, y esa ventaja se
derrite con carga y con vueltas. La constante queda definida y **en cero**: poner la cifra de
práctica sería peor que no tener ninguna.

#### Las gomas no son infinitas

El buscador trata los compuestos como recurso ilimitado. Medido sobre 5.394 tandas, un auto monta
2,68 juegos por carrera y sólo 2,05 son frescos: **el 23,7% de los juegos montados en carrera ya
venía usado**. Y por compuesto, cuántos juegos **nuevos** monta un auto:

| Compuesto | Media | Reparto |
|---|---|---|
| Blando | 0,33 | el 73,7% no monta ninguno nuevo |
| Medio | 0,99 | el 73,1% monta exactamente uno |
| Duro | 0,87 | **sólo el 15,0% monta dos o más** |

La recomendación actual para toda la parrilla es H23-H24-H24, tres tandas al duro, que necesita dos
duros frescos además del de salida. **Para el 85% de los autos ese plan no es ejecutable**, y el
modelo no tiene forma de saberlo. La restricción cuesta entre 2,5 y 5,7 segundos, y a diferencia de
todo lo demás es una restricción dura: el plan directamente no existe.

#### Las tres banderas, no una sola

El simulador sorteaba un safety car por carrera y no conocía la bandera roja. Medido sobre 103
carreras, cuántos períodos de cada clase tiene una carrera y cuándo empiezan:

| | P(al menos uno) | Primer tercio | Duración mediana |
|---|---|---|---|
| Bandera roja | 0,117 | **50%** | 1 vuelta |
| Safety car | 0,544 | **53%** | 4 vueltas |
| VSC | 0,476 | 36% | 3 vueltas |

Las rojas y los safety car están cargados al principio, que es donde los autos van apretados. El
VSC es mucho más plano.

Y el número que más importa: **el 44,7% de las carreras tiene dos o más períodos de
neutralización**, y el modelo sorteaba uno. Ése era el agujero estructural, más que la bandera roja
en sí. Ahora se sortean las tres por separado, con cantidad, momento y duración medidos, y una
parada paga según la bandera que encuentre: verde 22,6 s, VSC 18,8, safety car 19,5, roja 0.

#### El desgaste por circuito es lo único que casi replica

Cuatro cantidades medidas por circuito, y su correlación entre la era 2022-23 y la 2024-26:

| Cantidad | Correlación entre eras |
|---|---|
| Dificultad para adelantar | 0,209 |
| Corrección por avance de carrera | 0,150 |
| Costo del tráfico | −0,042 |
| **Desgaste, por compuesto** | **0,26 a 0,45** |

Las tres primeras se resolvieron usando un número global. La cuarta es la que más se acerca a ser
usable, y es justamente la que más importa: en **Monza el medio degrada 0,0331 s/vuelta y en
Zandvoort 0,0640**, casi el doble, y en Monza degrada **menos que el duro** mientras que en
Zandvoort degrada más. El simulador corre todos los circuitos con los números de Zandvoort, y Monza
demuestra que eso invierte la recomendación.

#### Y un circuito nuevo: Madrid

Madrid es la fecha 14 y nunca se corrió. Un *leave-one-circuit-out* sobre los 25 circuitos
conocidos dice cuánto cuesta no tener historia:

| Compuesto | Promedio global | Con velocidad media | Desvío entre circuitos |
|---|---|---|---|
| Blando | **0,0408** | 0,0443 | 0,0551 |
| Medio | 0,0316 | **0,0315** | 0,0373 |
| Duro | **0,0249** | 0,0267 | 0,0322 |

La forma del circuito no predice el desgaste, y el error se parece al desvío entre circuitos:
predecir uno nuevo es apenas mejor que no saber nada. Las prácticas son la mejor señal por-circuito
de todo el trabajo —correlación **+0,455** con la carrera— pero llevan señal sin escala: usarlas
crudas da cinco veces más error que el promedio, y calibradas siguen perdiendo.

Para Madrid la respuesta honesta es el promedio global con la incertidumbre declarada: blando 0,072
± 0,041, medio 0,056 ± 0,032, duro 0,050 ± 0,025 s/vuelta. El error es del tamaño del efecto.

---

## 5. Resultados

### Lo que el sistema entrega

Para cada auto, un plan de paradas con su distribución. Desde la vuelta 30 de 72
de Zandvoort 2026:

| | Auto | Plan | Llega | Puntos | Objetivo |
|---|---|---|---|---|---|
| P1 | ANT | H19-H23 | 1,88 ± 0,86 | 19,9 | puntos |
| P5 | LEC | M6-H36 | 2,77 ± 1,29 | 16,6 | puntos |
| P11 | LIN | M6-H36 | 8,70 ± 1,13 | 2,9 | puntos |
| P18 | COL | H6-H36 | 16,02 ± 1,34 | 0,0 | posición |

### Qué es «ganar», y por qué no es lo mismo para todos

La aptitud son los **puntos absolutos** en la bandera. Mantener un puesto de
puntos gana por construcción: quedarse quinto paga 10 en cada sorteo, y un plan
que la mitad de las veces da tercero y la otra mitad octavo (0,5·15 + 0,5·4 =
9,5) no lo alcanza.

Pero para un auto cuyos planes suman cero, ese objetivo está **plano** y la
búsqueda no tiene nada que escalar. Medido: un auto 18.º con objetivo puntos
termina con la población repartida 0,21 / 0,33 / 0,17 / 0,29 entre una y cuatro
paradas, que es ruido. Con objetivo posición converge en una parada al 0,87.

**Un auto fuera de los puntos sí puede ganar, pero no con la misma vara, y usar
la equivocada no da una respuesta prudente sino una al azar.** Por eso el
objetivo es adaptativo.

### Contra qué se compara, y una comparación que estaba mal armada

La primera versión de esta sección decía que el algoritmo apenas le ganaba a una
regla simple. **Esa conclusión era producto de una comparación amañada**, y hay
que corregirla.

La «regla» contra la que se medía tomaba el **mínimo sobre una, dos y tres
paradas** y siempre calzaba duro. Eso no es una regla que alguien pueda seguir
antes de una carrera: es un oráculo al que ya le dijeron las dos respuestas
difíciles, dejándole a la búsqueda sólo las vueltas.

Separando las tres decisiones:

| Decisión | Cuánto vale |
|---|---|
| **Cuántas paradas** | **12,5 s de carrera** |
| A qué compuesto cambiar | 5,7 s entre la mejor y la peor combinación |
| En qué vuelta parar | 0,30 s |

Y el número correcto de paradas **no es el mismo para todos**: el que larga en
duro quiere una, los que largan en medio o blando quieren dos.

Contra reglas que sí se pueden enunciar de antemano:

| Regla | Ventaja del algoritmo |
|---|---|
| «siempre 1 parada, duro» | **+6,93 s** |
| «siempre 2 paradas, duro» | +0,00 |
| «siempre 3 paradas, duro» | **+10,65 s** |
| el oráculo | +0,00 |

**El algoritmo le gana a cualquier regla enunciable, y lo que gana es exactamente
el valor de acertar la cantidad de paradas.** Contra el oráculo empata, y ésa era
la comparación que se venía reportando como si fuera la relevante.

Matiz honesto: «siempre dos paradas al duro» queda a nada del algoritmo, porque
dos paradas es correcto para dos de los tres compuestos de salida. Lo que el
algoritmo agrega es acertar el caso del duro, donde la respuesta cambia.

### Cuatro errores de método en el camino

La conclusión anterior también estaba contaminada por defectos de la búsqueda
que se corrigieron:

1. **El hueco de la grilla se cobraba cada vuelta.** Con la carrera arrancando en
   la vuelta 1, el estimador de ritmo base ponía a un auto 19.º cinco minutos y
   medio atrás. Antes de largar no hay historia de la que inferir ritmo.
2. **Se reportaba el puntaje en muestra.** El máximo de muchas estimaciones
   ruidosas está sesgado hacia arriba, igual que evaluar un modelo sobre su
   entrenamiento: 8,0 s de optimismo con 200 sorteos.
3. **Los planes no se comparaban contra las mismas carreras.** El mismo plan
   puntuaba entre 126,6 y 136,0 s. Con números aleatorios comunes baja el error
   de la *diferencia* entre planes, que es lo único que la búsqueda usa.
4. **La población inicial era toda al azar.** De 118 planes de dos paradas
   sorteados, el mejor daba 93,3 s contra 91,0 de una división pareja hecha a
   mano: el espacio contenía la respuesta y las semillas no caían cerca. Ahora se
   siembra con las heurísticas, con lo cual la búsqueda arranca desde la regla y
   sólo puede mejorarla.

El piso de sorteos por defecto subió de 400 a 1.200. Con 400, la búsqueda salía
0,71 s por carrera **peor** que una regla; con 1.200 la iguala o la supera.

### Qué se mide

| Qué | Cómo | Estado |
|---|---|---|
| Simulador | Error del modelo de degradación | Mejor que la mediana ✅ |
| Algoritmo genético | Segundos contra reglas enunciables | +6,9 a +10,7 s ✅ |
| Sistema completo | ¿La estrategia real cayó en el rango? | Probado en Monza, ver §6 |
| Reglamento | Planes ilegales generados | Cero ✅ |

**La exactitud no se usa como métrica.** «No parar nunca» acierta el 96,6% de las
vueltas, y además de inútil **es ilegal**.

---

## 6. Análisis de los Resultados

### La prueba real: Monza 2026

El 6 de septiembre, cuatro fechas después de la carrera sobre la que está armado
el simulador, hubo un caso que pone a prueba todo el sistema. **Antonelli largó
19.º con duro, paró dos veces y ganó con medio.** El modelo, preguntado antes de
largar, recomienda una parada al duro.

Se equivocó, y por qué se equivocó es el resultado más útil del trabajo.

**Casi nadie pagó por parar.** Bandera roja en la vuelta 3: los 22 autos entran y
cambian gomas gratis. VSC en las vueltas 27 a 29: ahí paran los diez que hicieron
una segunda. El **90,6%** de las paradas estratégicas de esa carrera fueron bajo
neutralización, contra el 23% medido sobre 103 carreras.

| Escenario | Plan recomendado | Lo que hizo ANT | Diferencia |
|---|---|---|---|
| Paradas a 22,6 s | 57,95 s | 78,96 s | **+21,01** |
| Paradas gratis | 35,34 s | 33,84 s | **−1,50** |

El vuelco vale **22,5 segundos** de carrera, y la cantidad óptima se invierte: a
precio de lista una parada le gana a dos y a tres; con las paradas gratis el
orden se da vuelta por completo.

### Por qué se calza el duro si el medio degrada menos

En Monza el medio degrada **0,0331 s/vuelta y el duro 0,0463**: el medio es el
mejor neumático de ese circuito. Entonces, ¿por qué once autos corrieron
cincuenta vueltas con duro?

No porque sea mejor. Porque **B6.3.8 obliga a usar dos compuestos secos**. La
elección no es «cuál es más rápido» sino **en qué tanda tiro la obligación**.

La bandera roja lo hizo visible. Los veintidós corrieron una tanda de dos o tres
vueltas y cambiaron gratis: esa tanda corta es la **tanda de cumplimiento**.

| | Secuencia |
|---|---|
| **ANT** | **H3-M25-M25** |
| RUS, NOR, PIA, GAS, LIN, COL | M3-H50 |
| HAM, BOR | S3-M50 |

Antonelli puso el compuesto obligatorio en la tanda descartable y corrió el bueno
dos veces. Seis autos gastaron su medio ahí y después vivieron cincuenta vueltas
con el duro.

Con B6.3.8 aplicado, la bandera roja en el sorteo y el desgaste propio de Monza,
**el modelo pone el orden bien**: la estructura de ANT (69,09 s) por delante de la
del resto (69,26). Es la primera vez que reproduce una decisión estratégica real,
y hicieron falta las tres cosas juntas.

### Por qué dos paradas y no una

ANT y Hamilton corrieron los dos con medio. HAM hizo cincuenta vueltas con un
solo juego; ANT hizo dos tandas de veinticinco.

El medio en Monza degrada poco, pero no cero: un juego de 25 vueltas está **0,83
s/vuelta** más lento que uno nuevo, y uno de 50, **1,65**. En la vuelta 37 la goma
de HAM tenía 33 vueltas y la de ANT 8. ANT cayó de 2.º a 6.º al parar y en ocho
vueltas estaba de nuevo 2.º con HAM 5.º.

Degradar poco no es lo mismo que no degradar. Que el medio sea el mejor compuesto
de Monza es la razón para tener **dos juegos frescos**, no para estirar uno.

### Por qué es difícil ganarle a una regla razonable

Desde mitad de carrera el espacio de planes es casi unidimensional: una parada, y
la única pregunta es en qué vuelta. Esa dimensión vale 0,30 segundos. El objetivo
es suave ahí y su óptimo cae cerca del punto medio, así que una búsqueda va a
empatar con «elegí el punto medio» casi por construcción.

Donde el algoritmo se gana el sueldo es **antes de largar**, donde hay que
decidir cuántas paradas y con qué compuestos — y ahí la ventaja sobre una regla
enunciable es de 7 a 11 segundos.

### Contra trabajos previos

Hay un paper de 2025 (Chaudhary et al.) que hace algo parecido con redes
neuronales sobre datos de 2020 a 2024, y llega a F1 = 0,81. **Lo nuevo acá no es
el problema, es la temporada:** ningún trabajo publicado pudo usar datos de 2026.

### Contra un trabajo propio

En 2025 hice el TP de Inteligencia Artificial sobre este mismo tema: clasificar
el compuesto con una red neuronal MLP, con datos de 2020 a 2022.

| | TP de IA 2025 | Este trabajo |
|---|---|---|
| Datos | 2020–2022, 782 registros | 2022–2026, 114.414 vueltas |
| Pregunta | ¿Qué compuesto? | ¿Cuándo parar y cuántas veces? |
| Técnica | Red neuronal MLP | Algoritmo Genético sobre simulador Monte Carlo |
| Resultado | 0,62–0,70 de exactitud, con sobreajuste | Plan por auto, con su distribución |

Aquel trabajo trató de **aprender** qué compuesto elegir. Este da una explicación
mejor de por qué costaba: **la elección de compuesto está dominada por el
reglamento**, que obliga a usar dos, y por dónde conviene gastar esa obligación.
Es una decisión de asignación, no de clasificación.

### Sobre la comparación con AWS

Las gráficas de la transmisión se replicaron con nuestros propios números. AWS
calcula su estrategia recomendada en la primera vuelta combinando historia del
circuito, ritmo proyectado, datos de compuesto y clima; no puede estar
optimizando puntos esperados, porque antes de largar nadie sabe dónde va a
terminar nadie. Lo que optimiza es tiempo de carrera, que es un problema de un
solo auto.

La diferencia de fondo no es el modelo: **ellos tienen telemetría de 300 sensores
por auto y 1,1 millones de puntos por segundo, y nosotros tiempos por vuelta.**
Eso explica por qué pueden ver aire sucio y carga sobre el neumático con un
detalle que acá se aproxima con un promedio. Su metodología no está publicada.

---

## 7. Conclusiones

1. **La incertidumbre es más grande que la señal.** El desvío del ritmo de caída
   de una tanda supera a la mediana del ritmo mismo. Ése es el argumento central
   para devolver distribuciones y no números, y no es una preferencia de diseño:
   es lo que dicen los datos.

2. **El algoritmo genético vale lo que vale acertar la cantidad de paradas**, que
   son 12,5 segundos de carrera. Le gana entre 7 y 11 segundos a cualquier regla
   que se pueda enunciar de antemano, y empata con un oráculo al que ya le
   dijeron la respuesta. La vuelta exacta de la parada, que es lo que una primera
   versión de este informe estaba midiendo, vale 0,30 segundos.

3. **El plan óptimo depende de cuándo salen las neutralizaciones, y eso no se
   sabe.** Monza 2026 lo muestra en un caso concreto: el 90,6% de sus paradas
   fueron bajo bandera o safety car, y con las paradas gratis la cantidad óptima
   de paradas se invierte. Un número puntual habría estado mal por 21 segundos.

4. **El reglamento no es una molestia: es el que manda.** B6.3.8 obliga a usar
   dos compuestos, y la decisión estratégica real no es cuál es más rápido sino
   en qué tanda gastar la obligación. Antonelli ganó Monza poniendo el compuesto
   obligatorio en una tanda de tres vueltas que la bandera roja le regaló.

5. **La mitad del trabajo fue encontrar errores propios.** El coeficiente de
   combustible que sacaba el 63% del efecto; el ritmo de caída extrapolado que
   hacía ganar a un auto desde noveno; el hueco de grilla cobrado cada vuelta; la
   referencia de pérdida de boxes que hacía parecer cara la parada bajo safety
   car; el escalado por circuito que duplicaba el tráfico de Zandvoort al revés;
   los planes comparados contra carreras distintas; y una comparación amañada a
   favor de la regla que invertía la conclusión principal. Todos daban números
   confiados y plausibles hasta que algo aguas abajo salió absurdo.

6. **La granularidad por circuito casi nunca la sostienen los datos.** Cuatro
   cantidades, cuatro correlaciones entre eras: dificultad para adelantar 0,21,
   avance de carrera 0,15, tráfico −0,04, y desgaste 0,26 a 0,45. Sólo la última
   se acerca a ser usable — y es justamente la que más importa, porque en Monza el
   medio degrada la mitad que en Zandvoort e invierte la recomendación.

7. **Los datos tienen un techo y conviene nombrarlo.** El desgaste medido se
   aplana por supervivencia; el tráfico de rezagados queda afuera por
   construcción; el escalón de ritmo entre compuestos se mide en práctica pero no
   se puede llevar a carrera; la asignación de neumáticos no está, y hace que la
   recomendación actual no sea ejecutable para el 85% de los autos. El sistema es
   honesto dentro de ese techo y lo declara.

### Qué sigue

| Acción | Por qué | ¿Se puede? |
|---|---|---|
| **Desgaste por circuito**, encogido por la confiabilidad medida | Monza demuestra que correr todo con los números de Zandvoort da la respuesta equivocada | Sí, y es lo más urgente |
| El escalón de ritmo entre compuestos **en condiciones de carrera** | Sin él, el duro sólo existe por el reglamento | Necesita telemetría o un modelo de combustible mejor |
| Restricción de **asignación de neumáticos** | Sólo el 15% de los autos monta dos duros frescos, y la recomendación los pide | Sí, hay que decidir de dónde sale la asignación |
| Bajar **`MIN_STINT`** de seis vueltas | No puede representar la parada de bandera roja temprana, que hicieron los 22 autos de Monza | Sí |
| Portar a **DEAP** | Es la herramienta que recomienda la cátedra | Sí, no cambia el modelo |
| Tráfico de **rezagados** | 23,1% de los pilotos terminan una vuelta abajo | Requiere comparar por posición y no por vuelta |
| Agente de **Refuerzo** | La comparación propuesta: planificar contra reaccionar | Para la Entrega 2 |

**Lo que no se va a hacer:** más términos en la aptitud esperando que deje de ser
plana. El tráfico se midió, se implementó correctamente y no movió el resultado;
el escalón de compuestos se midió y no se pudo transferir. Dos negativos
seguidos son suficiente señal.

**Riesgo que se asume:** publicar una predicción antes de la carrera puede salir
mal en público. Es a propósito, y ya pasó: la predicción para Monza estuvo mal
por 21 segundos. Se evalúa si el rango estaba bien calculado, no si se acertó
justo — y el caso enseñó más que un acierto.

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

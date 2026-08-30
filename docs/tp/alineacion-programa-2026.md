# Alineación con el programa de IAA 2026 — revisión de la propuesta

Fuente: *IAA — Programa y Planificación, 2do Cuatrimestre de 2026*. Docente: Dr. Pablo Pytel.

## Hallazgo crítico

**El programa 2026 no incluye Ingeniería del Conocimiento, metodología IDEAL, sistemas expertos
ni sistemas de producción.** Las cinco unidades son:

| Unidad | Contenido | Clases |
|---|---|---|
| 1 | Re-introducción a la IA | 2–3 |
| 2 | **RNA y Deep Learning** — MLP, Kohonen SOM/LVQ, ConvNet, Object Detection, DAE, RNN, LLMs, Diffusion | 3–6 |
| 3 | **Sistemas Evolutivos** — Algoritmos Genéticos, Computación Evolutiva, Inteligencia de Enjambre | 7–8 |
| 4 | **Razonamiento Aproximado** — Naive Bayes, Redes Bayesianas | 11 |
| 5 | **Agentes Inteligentes** — Aprendizaje por Refuerzo, DQN, AlphaZero, Agentes LLM | 9–10 |

La conceptualización que se redactó (tablas Concepto-Atributo-Valor, pseudo-reglas, tablas de
decisión, modelos estáticos y dinámicos) proviene de los **TP de ejemplo de 2014–2020**, que sí
seguían la metodología IDEAL. **Ese material está desactualizado respecto del programa vigente.**

El motor de reglas no es un error de ingeniería —sigue siendo la capa que garantiza legalidad—
pero **no es una técnica de la asignatura** y no puede ser el entregable central.

## Calendario y entregas

| Hito | Fecha | Nota |
|---|---|---|
| **TP Entrega N.º 1** | **1 de septiembre de 2026** | Clase 4 |
| TP Entrega N.º 2 | 6 de octubre de 2026 | Clase 8 |
| TP Entrega N.º 3 | 17 de noviembre de 2026 | Clase 14 |
| TP Entrega N.º 4 | _(ver documento «IAA - Normas Aprobación»)_ | No figura en este PDF |
| Examen Parcial | 10 de noviembre de 2026 | |

**Son cuatro entregas, no cinco.** El detalle está en el documento *IAA - Normas Aprobación*,
que no se ha revisado — es lo primero que hay que conseguir.

Cobertura temática respecto de las entregas:

- Para la **Entrega 1** (1-sep) sólo se habrá visto Deep Learning parcialmente.
- Para la **Entrega 2** (6-oct) ya se habrán visto Algoritmos Genéticos.
- Para la **Entrega 3** (17-nov) estará todo el programa dictado.

## Herramientas que la cátedra espera

Del propio programa:

| Herramienta | Unidad | Uso previsto |
|---|---|---|
| **DEAP** | 3 | Biblioteca de computación evolutiva en Python |
| **GeNIe** (BayesFusion) | 4 | Construcción de redes bayesianas |
| `demoCESwarm` | 3 | Demo de la cátedra: computación evolutiva y enjambre |
| `demoRL` | 5 | Demo de la cátedra: aprendizaje por refuerzo y agentes |
| `demoML`, `demoConvNet-Letras`, `demoObjDet-Carteles` | 2 | Demos de ML y visión |
| Google Colab | — | Entorno de ejecución |

Repositorios: `https://github.com/PGP-MachineLearning/`

Usar DEAP y las demos de la cátedra es una señal explícita de alineación con el curso.

## Revisión de la propuesta

### Lo que se conserva

Todo el trabajo de datos sigue siendo válido y necesario: el pipeline, la degradación medida, las
tasas de neutralización, el costo de parada en posiciones y las restricciones reglamentarias. **No
se descarta nada.** Lo que cambia es qué papel juega cada pieza.

### Lo que cambia de rol

| Pieza | Rol anterior | Rol nuevo |
|---|---|---|
| Simulador Monte Carlo | Entregable central | **Entorno / función de aptitud** — infraestructura, no técnica de IA |
| Motor de reglas | Capa decisoria | **Capa de restricciones** — garantiza legalidad (B6.3.8) y sirve de línea base |
| Regresor de degradación | Modelo principal | **Componente del simulador** |
| — | — | **Algoritmo Genético (Unidad 3)** — nueva técnica principal |
| — | — | **Agente de Aprendizaje por Refuerzo (Unidad 5)** — modelo de contraste |

### Técnica principal propuesta: Algoritmo Genético

Es el mejor encaje entre el problema y el programa.

- **Cromosoma:** el plan de carrera — vector de longitudes de stint más la secuencia de
  compuestos. Por ejemplo `[(18, M), (25, H), (14, S)]`.
- **Función de aptitud:** posición final simulada, promediada sobre varias realizaciones Monte
  Carlo del Safety Car. Se optimiza **posición, no segundos**, según lo medido.
- **Restricciones:** el artículo B6.3.8 define qué cromosomas son viables. Los inviables se
  penalizan o se reparan.
- **Operadores genéticos:** cruza de un punto sobre la secuencia de stints; mutación que alarga o
  acorta un stint, o cambia un compuesto.
- **Herramienta:** DEAP, explícitamente recomendada por la cátedra.

El problema es **combinatorio con restricciones y una función de aptitud costosa de evaluar** —
exactamente el escenario en que un algoritmo genético es la respuesta natural. Y a diferencia de
la predicción puntual, aquí no se pregunta "¿qué hizo el equipo?" sino "¿cuál es el mejor plan?",
que es una pregunta que estos datos **sí** pueden responder.

### Técnica de contraste: Aprendizaje por Refuerzo

Un agente que decide `BOX` / `SEGUIR` vuelta a vuelta dentro del mismo simulador. Estado: el
vector de la conceptualización. Acción: binaria más elección de compuesto. Recompensa: posiciones
ganadas al final. Cubre la Unidad 5 y permite comparar **optimización global** (el AG planifica la
carrera completa de antemano) contra **decisión secuencial** (el agente reacciona a lo que pasa).

Esa comparación es, en sí misma, un buen resultado para la Entrega 3.

### Opcional, si sobra tiempo: Red Bayesiana

Modelar la incertidumbre de Safety Car, VSC y bandera roja con una red bayesiana en GeNIe, y
usarla para alimentar los sorteos del simulador. Cubre la Unidad 4 y aprovecha directamente lo ya
medido sobre tasas de neutralización.

## El solapamiento con el TP anterior queda resuelto

El TP de IA 2025 usó un **MLP**, que es contenido de la **Unidad 2**. Esta propuesta usa
**Unidades 3 y 5**. Ya no es el mismo dominio con la misma técnica: es el mismo dominio con
técnicas que la asignatura anterior no cubría, que es precisamente lo que significa que IAA
*"completa y profundiza"* a IA según el propio programa.

## Advertencia de alcance

El trabajo es **individual**. Los TP de ejemplo tenían de 4 a 5 integrantes. Implementar AG + RL +
red bayesiana + simulador es demasiado para una persona en un cuatrimestre.

**Prioridad recomendada:**

1. Simulador Monte Carlo — infraestructura, es el prerrequisito de todo lo demás.
2. **Algoritmo Genético con DEAP** — la técnica principal, para la Entrega 2.
3. Agente RL — sólo si el AG está terminado y validado, para la Entrega 3.
4. Red bayesiana — sólo como línea futura declarada.

Prometer las cuatro y entregar una es peor que proponer dos y entregar dos.

## Acciones inmediatas

- [ ] **Conseguir el documento «IAA - Normas Aprobación»**, que define las cuatro entregas. Sin
      eso no se puede saber qué pide exactamente la Entrega 1.
- [ ] **La Entrega 1 es el 1 de septiembre.**
- [ ] Revisar la sección 3 de la propuesta para reflejar AG como técnica principal.
- [ ] Marcar `conceptualizacion.md` como material de referencia y no como entregable, hasta
      confirmar si la cátedra sigue pidiendo modelos conceptuales.
- [ ] Clonar `demoCESwarm` y `demoRL` para seguir las convenciones de la cátedra.

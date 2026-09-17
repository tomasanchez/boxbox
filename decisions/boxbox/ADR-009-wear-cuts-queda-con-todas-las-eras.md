---
project: boxbox
adr: 009
title: WEAR_CUTS queda con todas las eras, y el conflicto queda declarado
category: data
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-009: WEAR_CUTS queda con todas las eras, y el conflicto queda declarado

## Context

Hay dos números de desgaste de Zandvoort en el repositorio y difieren un 63%:

| | MEDIO |
|---|---|
| `strategy.WEAR_CUTS` | 0,0625 s/vuelta |
| `RaceModel.for_circuit("Zandvoort")` | 0,0934 s/vuelta |

El origen está en `scripts/zandvoort_distributions.py`, que filtra
`dry[dry["circuit"] == CIRCUIT]` **sin filtro de año**: los cortes salen de
Zandvoort en todas las temporadas — 79 tandas de medio contra las 11 que tiene
2026. El docstring de `RaceModel` decía «Defaults are 2026 Zandvoort» y no lo
eran.

Eso contradice la política que el propio informe declara en su sección 2: el
desgaste por compuesto se mide **sólo con 2026**, porque este año se invirtió el
orden de los compuestos. Pooleamos eras justo en la única cantidad donde el
trabajo dice que no se puede.

`WEAR_CUTS` es el valor por omisión de `RaceModel`, así que lo usan
`prerace_strategy.py`, `monza_2026.py`, `risk_appetite.py`, `grid_position.py` y
**todas las cifras publicadas en el informe**.

## Decision

`WEAR_CUTS` **no se toca**. Se corrigen las etiquetas que afirmaban que era de
2026, se documenta el conflicto en el propio `strategy.py`, y `for_circuit` queda
como el camino que sí sigue la política declarada.

El cambio se posterga hasta terminar la vista pre-carrera.

## Alternatives Considered

- **Recalcular `WEAR_CUTS` con 2026 solamente**: es lo que la política dice, pero
  movería todas las cifras del informe por segunda vez en una semana, y con 11
  tandas de medio el número es fino. Si se hace, tiene que ser con el
  encogimiento por `n` de ADR-010 y no con la mediana cruda.
- **Hacer que `RaceModel()` use `for_circuit("Zandvoort")` por omisión**: más
  consistente, mismo problema — cambia todo lo publicado.
- **Dejarlo sin documentar**: descartado. El proyecto documenta sus errores; un
  número mal etiquetado que sostiene resultados publicados es exactamente lo que
  la sección de errores propios existe para registrar.

## Consequences

Durante un tiempo conviven dos definiciones de desgaste de Zandvoort, y eso está
declarado en el código y en este archivo en vez de quedar como sorpresa. Los
resultados publicados siguen siendo reproducibles tal como se publicaron.

La deuda queda anotada: cuando se cambie, hay que re-medir todo el informe, no
sólo la constante.

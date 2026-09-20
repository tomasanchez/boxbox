---
project: boxbox
adr: 011
title: Pit loss se sortea con nueve cortes empíricos, no con una triangular
category: data
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-011: Pit loss se sortea con nueve cortes empíricos, no con una triangular

## Context

El desgaste del simulador ya se sorteaba de su distribución empírica con nueve
cortes (`CUT_AT = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]`), con el
argumento de que una tanda puede salir muy mal de maneras en que no puede salir
igual de bien. Veinte líneas más abajo, en el mismo archivo
(`apps/ml/src/boxbox_ml/strategy.py`), la pérdida de boxes
(`pit_loss_green/sc/vsc/red` de `RaceModel`, sorteada por `_pit_cost`) usaba el
argumento contrario sin que nadie lo hubiera decidido así: una triangular
ajustada a tres cuartiles.

Una triangular no puede pasarse de su máximo, y ese máximo era el p75 medido. Un
cuarto de las paradas reales quedaba fuera del alcance del modelo por
construcción — y ese cuarto no es ruido simétrico: medió 31,5 s en verde y llegó
hasta 81,9 s. El modelo no podía representar una parada que sale mal.

Al revisar de dónde salían los cortes apareció un segundo problema, en la misma
familia que ADR-009 (qué medición de cortes de Zandvoort usar): la web
(`apps/web/src/tyres.ts`, `PIT_LOSS_CUTS` y `drawPitLoss`, consumido desde
`prerace.ts`) tomaba sus cortes de `zandvoort_distributions.py`, que mide contra
la mediana verde **de la carrera** (un solo número, con el combustible, la
evolución de la pista y el tráfico adentro), mientras el simulador mide con
`effective_pit_loss.py`, contra la mediana **del campo en esa misma vuelta**. Con
una triangular la diferencia entre ambas referencias era chica (19,8/22,7/26,7 s
contra 20,6/23,5/31,3 s) y pasaba inadvertida. Con nueve cortes la cola separa
las dos referencias: p95 de 41,1 s con la referencia buena contra 64,7 s con la
mala. Esa referencia mala ya figuraba en el informe como un error encontrado y
corregido en el script del simulador — pero sobrevivió en el camino que
alimenta la pantalla.

## Decision

`_pit_cost` sortea la pérdida de boxes con `_from_cuts`, la misma mecánica de
cortes empíricos que ya usa el desgaste. Se elimina `_triangular`. Los cortes
nuevos, medidos con `scripts/effective_pit_loss.py`:

| Condición | Cortes (s) | n |
|---|---|---|
| Verde | 16.8, 19.1, 20.2, 21.2, 22.6, 24.1, 25.5, 27.9, 34.3 | 2.614 |
| Safety car | -2.5, 2.1, 7.5, 13.7, 19.5, 24.7, 31.5, 43.3, 53.3 | 264 |
| VSC | 9.5, 12.0, 14.8, 16.6, 18.8, 23.0, 27.1, 33.8, 44.9 | 199 |

El p25, la mediana y el p75 de cada condición son exactamente los tres valores
de la triangular anterior: el centro no se movió, sólo se agregó la cola.

La bandera roja es el único caso no medido — `free_stop` la excluye por
definición, porque con la carrera detenida no hay campo contra el cual medir —
y sus cortes son la traducción exacta de la triangular anterior (0 · 0 · 0,5),
para que ese caso no cambie de comportamiento. Queda declarado como supuesto,
no como medición.

La web pasa a tomar sus cortes de la misma referencia que el simulador
(mediana del campo en la vuelta, vía `effective_pit_loss.py`), no de la
mediana de carrera de `zandvoort_distributions.py`:
`PIT_LOSS_CUTS = [15.8, 18.4, 19.8, 20.8, 22.7, 24.3, 26.7, 30.2, 41.1]`, sobre
172 paradas en verde de Zandvoort.

## Alternatives Considered

- **Dejar la triangular**: rechazada. No puede representar un cuarto de las
  paradas reales, y el proyecto ya usa el método correcto para el desgaste a
  veinte líneas de distancia — no había razón para tratar la parada distinto.
- **Modelar un efecto por equipo**: medido y rechazado. La varianza entre las
  medianas de los once equipos es 0,188 contra 10,699 dentro de cada uno — el
  equipo explica el 1,7% de la varianza, y el abanico entre el mejor y el peor
  es 1,7 s. No paga la complejidad frente a la cola, que sí importaba.
- **Medir la bandera roja**: imposible por construcción — `free_stop` no tiene
  campo contra el cual comparar. Queda como supuesto declarado, no como
  decisión de diseño.
- **Cambiar también el duelo de undercut** (`insights.py` y su espejo
  `battle.ts`, que sortea la *diferencia* entre las pérdidas de dos autos con
  una triangular): **no se hizo**, queda pendiente. Los nueve cortes medidos son
  los de una parada, no los de una diferencia entre dos paradas; usarlos ahí
  sería reemplazar una forma asumida por otra forma asumida, sin haber medido
  la que corresponde.

## Consequences

La media por parada sube +0,66 s en verde, +1,75 s bajo safety car, +1,77 s
bajo VSC. Cifras publicadas que se mueven: Monza +18,40 → +19,03 s; el vuelco
de Monza 21,6 → 22,2 s; el tiempo del plan del AG desde la vuelta 1, 91,7 →
93,3 s. Ninguna conclusión del informe se da vuelta.

El resultado que sí cambia de forma: el apetito de riesgo conservador deja de
comprar previsibilidad con una parada extra (antes elegía dos paradas) y pasa a
comprarla retrasando la única parada — ahora los dos apetitos paran una vez y
se separan en cuándo (conservador vuelta 26,9, arriesgado vuelta 18,0).

La web y el simulador quedan alineados en qué miden cuando hablan de pérdida de
boxes de Zandvoort, cerrando en este punto puntual el tipo de discrepancia que
ADR-009 dejó declarada y pendiente para el desgaste — acá la fuente incorrecta
se reemplaza directamente porque el propio informe ya la había señalado como
error corregido en el simulador.

Queda pendiente: el duelo de undercut sigue sorteando su diferencia de paradas
con una triangular sin cortes propios medidos.

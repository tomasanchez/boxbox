---
project: boxbox
adr: 012
title: Los rivales reaccionan a las banderas dentro del lazo, y al auto focal sólo al puntuar
category: architecture
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-012: Los rivales reaccionan a las banderas dentro del lazo, y al auto focal sólo al puntuar

## Context

Hoy `boxbox_ml.strategy.optimise(car, rivals, rival_plans, model, ...)` simula
a los rivales con un plan fijo sorteado. `race_trace()` traza cada auto por
separado y vectorizado sobre 1.200 sorteos; las trazas de los rivales se
construyen una sola vez fuera del lazo del algoritmo genético y se reusan para
las ~1.000 evaluaciones de plan que hace la búsqueda.

Se quiere que el auto focal corra su plan pre-carrera fijo y que el resto
reaccione, pero hay dos niveles de reactividad con costos muy distintos.
Reaccionar a las BANDERAS (SC/VSC/roja) y a la propia goma no depende del plan
focal: la traza del rival se puede seguir calculando una sola vez fuera del
lazo de aptitud, así que el costo dentro de la búsqueda es cero. Reaccionar AL
AUTO FOCAL (cubrir su parada, responder a un undercut) sí depende del plan que
se está evaluando en cada momento, obliga a re-simular los 21 rivales en cada
una de las ~1.000 evaluaciones, y además obliga a reestructurar `race_trace`
de «cada auto por separado» a «los 22 autos avanzan vuelta a vuelta en el
mismo lazo». Medido en costo: ~20× la búsqueda actual, el export pre-carrera
pasaría de ~10 minutos a ~3 horas.

## Decision

Dos niveles de reactividad. (a) Dentro del lazo del algoritmo genético, los
rivales reaccionan a las banderas y a su propia goma — costo cero, porque su
traza no depende del plan que se está evaluando. (b) La reacción al auto
focal — los vecinos cubren su parada — se aplica sólo al PUNTUAR el plan
ganador y al exportarlo, una vez por piloto en vez de mil veces. El export
pasa de ~10 a ~25 minutos.

## Alternatives Considered

- **Reacción al focal dentro del lazo, con 1.200 sorteos**: rechazada por
  costo — ~3 horas de export, inviable para iterar.
- **Reacción al focal dentro del lazo bajando a 400 sorteos**: rechazada — el
  propio repo ya midió que con 400 sorteos la búsqueda sale 0,71 s por carrera
  peor que una regla simple, así que bajar sorteos para pagar la reactividad
  se paga con peor calidad de plan.
- **Reactividad sólo de exhibición en la web**: rechazada — el plan quedaría
  optimizado contra un mundo distinto del que se le muestra al usuario.

## Consequences

El plan se optimiza contra un campo que reacciona a la carrera pero no a él,
y se REPORTA contra un campo que además lo cubre. Esa asimetría hay que
declararla en el informe. No es equilibrio y no hay que llamarlo así: es una
movida de anticipación, la que el informe ya identificó como el paso
intermedio alcanzable — pensar una movida más que ahora. `Search` sigue
conservando el histograma y el registro por generación de ADR-003, ahora
calculados contra el rival cubriendo en el paso de puntuación final.

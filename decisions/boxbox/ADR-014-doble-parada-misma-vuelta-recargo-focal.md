---
project: boxbox
adr: 014
title: Doble parada, la misma vuelta se permite y el segundo paga el recargo medido; el focal tiene prioridad
category: data
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-014: Doble parada, la misma vuelta se permite y el segundo paga el recargo medido; el focal tiene prioridad

## Context

Dos autos del mismo equipo no pueden ser ATENDIDOS a la vez — un box, una
cuadrilla — pero sí pueden entrar en la misma vuelta y el segundo hace cola.
Medido, equipo con los dos autos en carrera: SC ninguno para 43,3%, uno solo
28,0%, los dos 28,7% (n=571); VSC 63,5% / 24,0% / 12,4% (n=620). Cuando meten
los dos, el 70% es en la misma vuelta. Prohibir la misma vuelta contradiría
ese dato.

Cuando meten uno solo (n=309), entra el de goma más vieja el 51% si difieren
0-1 vuelta (44% de los casos, o sea no hay nada que elegir), 67% si difieren
2-5 (n=42), 91% si difieren más de 5 (n=128).

Costo de apilar, PAREADO dentro del mismo par, que es la comparación limpia:
el segundo paga +1,0 s de mediana en verde (n=63, pierde más en el 65% de los
pares), +3,5 s bajo SC (n=47, 72%), +3,2 s bajo VSC (n=42, 81%).

**Corrección de investigación que hay que dejar escrita**:
`docs/research/pit-loss-under-neutralisation.md` afirma que apilar infla el
número de safety car en ~12 s («Restricting to single stops brings SC down
from 32.6 s to 25.6 s»). Esa cifra salía de n=18 SIN parear. Medido pareado
dentro del mismo par con n=47, el recargo es +3,5 s, no +12. Eso CAMBIA la
conclusión estratégica: apilar sale barato, y por eso lo hacen el 70% de las
veces. Hay que corregir esa nota de investigación y el docstring de
`RaceModel.pit_loss_sc`, que hoy le atribuye la cola al apilamiento.

## Decision

Se permite la misma vuelta; el segundo del par paga el recargo medido y
pareado (+1,0 s en verde, +3,5 s bajo SC, +3,2 s bajo VSC). Cuando el equipo
mete UN SOLO auto, cuál entra sale de la medición por diferencia de edad de
goma (51% / 67% / 91% según difieran 0-1, 2-5, o más de 5 vueltas). **El auto
focal tiene prioridad** en la cola de su propio equipo: es el auto para el
que el muro está planificando, así que entra primero y el compañero paga el
recargo.

`docs/research/pit-loss-under-neutralisation.md` y el docstring de
`RaceModel.pit_loss_sc` se corrigen para reflejar el +3,5 s pareado en vez del
~12 s sin parear, y para dejar de atribuirle la cola al apilamiento.

## Alternatives Considered

- **Prohibición dura, el segundo corrido a la vuelta siguiente**: rechazada —
  contradice el 70% medido, y bajo VSC la vuelta siguiente puede ser ya
  verde, un castigo enorme que el dato no respalda.
- **Un umbral de decisión «apila si conviene»**: rechazada por ahora — el
  criterio sería un supuesto nuestro, y el recargo medido ya hace que a veces
  no convenga, sin necesidad de inventar la regla.
- **Prioridad por goma más vieja también para el focal**: rechazada — le mete
  al plan focal un riesgo de +3,5 s que depende de un auto que el usuario no
  eligió.

## Consequences

La dataclass `Car` no tiene campo de equipo y hay que agregarlo (`team: str |
None = None`, compatible hacia atrás). El mapeo auto→equipo existe río arriba
en `qualifying.py` y en el JSON exportado, y hay que propagarlo. No está
modelado el orden de llegada a boxes entre autos de equipos DISTINTOS, ni la
pit lane cerrada en las primeras vueltas de safety car: quedan declarados
como límites del modelo, en la misma línea que ADR-011 declara la roja como
supuesto no medido.

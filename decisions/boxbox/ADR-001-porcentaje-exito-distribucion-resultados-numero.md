---
project: boxbox
adr: 001
title: El «% de éxito» es una distribución de resultados, no un número
category: business
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-001: El «% de éxito» es una distribución de resultados, no un número

## Context

El pedido pide mostrar «estrategias con % de éxito». Ese dato no existe. Lo único parecido es `stop_distribution`, que es la confianza de la BÚSQUEDA sobre cuántas paradas — no una probabilidad de la carrera. Mostrarla como «% de éxito» sería incorrecto. Además el proyecto ya midió que «ganar» no significa lo mismo para todos: el objetivo ADAPTIVE usa puntos donde son alcanzables y posición donde no, porque para un auto fuera de los puntos el objetivo de puntos es PLANO y la búsqueda no tiene gradiente.

## Decision

La UI muestra cuatro probabilidades para el mismo plan — P(ganar), P(podio), P(zona de puntos) y P(mejorar la posición de largada) — más la llegada esperada como banda (media ± desvío). No se elige una definición única de éxito: se muestran las cuatro y el lector elige la que le importa según desde dónde larga su piloto.

## Alternatives Considered

- **Un solo número adaptativo**: coherente con el buscador, pero obliga a explicar en pantalla por qué el número significa algo distinto para cada auto.
- **Éxito = mejorar la posición**: una sola definición para los 20, fácil de defender, pero trata igual ganar un puesto desde la pole que desde el 19no.
- **No mostrar porcentaje**: máxima honestidad y mínima legibilidad; no contesta lo que se pidió.
- **Mostrar `stop_distribution` como «% de éxito»**: es una mentira — mide convergencia del optimizador, no resultado de carrera.

## Consequences

Obliga a tocar `boxbox_ml.strategy`: hoy `Search` calcula `mean_position` y `sd_position` y DESCARTA las muestras. Hay que conservar el histograma de posiciones de las carreras sorteadas y exportarlo (ver ADR-003). También obliga a correr la búsqueda pre-carrera CON campo — sin rivales no hay puesto de llegada — a diferencia de `prerace_strategy.py`, que corre con objetivo TIME y sin rivales.

## Status History

- 2026-09-17: accepted

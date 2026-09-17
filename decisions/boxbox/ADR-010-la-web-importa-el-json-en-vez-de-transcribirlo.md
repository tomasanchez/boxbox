---
project: boxbox
adr: 010
title: La web importa el JSON en vez de transcribirlo a TypeScript
category: architecture
date: 2026-09-17
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-010: La web importa el JSON en vez de transcribirlo a TypeScript

## Context

ADR-002 decidió que la búsqueda corre fuera de línea y la web consume un JSON
generado. Falta decidir **cómo** entra ese JSON a la aplicación.

El precedente vigente es `apps/web/src/plans.ts`: un módulo TypeScript con los
datos escritos a mano adentro, marcado «Generado. No editar a mano». Funcionó
mientras los datos eran veinte planes cortos.

El JSON nuevo (`docs/research/prerace-zandvoort.json`) pesa 149 KB: 22 autos, cada
uno con su histograma de puestos, sus cuatro probabilidades, la lista de
alternativas y **26 generaciones de historia del algoritmo**. Transcribir eso a
mano no es realista, y cada transcripción es una oportunidad de que el número en
pantalla deje de ser el número que se midió — que es justo lo que este proyecto
trata de que no pase.

## Decision

La vista **importa el JSON directamente**. Vite lo resuelve de forma nativa, y el
archivo se copia a `apps/web/src/` como parte de la generación, no se transcribe.
Los tipos de TypeScript se declaran aparte y describen la forma del archivo.

`plans.ts` queda como está: no se migra en esta iteración.

## Alternatives Considered

- **Transcribir a un módulo `.ts` como `plans.ts`**: coherente con lo que ya hay,
  pero con 149 KB y datos anidados es inviable a mano y frágil si se genera.
- **Servir el JSON por `fetch` desde `public/`**: evita agrandar el bundle, pero
  agrega un estado de carga y un modo de falla a una aplicación que hoy se abre y
  muestra. Para 149 KB no lo vale.
- **Migrar también `plans.ts`**: fuera del alcance de esta feature.

## Consequences

El bundle crece ~149 KB. A cambio, **lo que se muestra es literalmente lo que
midió la corrida**, sin paso manual en el medio, y regenerar el escenario es
correr el exportador y copiar un archivo.

Quedan dos formas de traer datos conviviendo en la misma aplicación — el módulo
transcripto y el JSON importado — hasta que alguien unifique.

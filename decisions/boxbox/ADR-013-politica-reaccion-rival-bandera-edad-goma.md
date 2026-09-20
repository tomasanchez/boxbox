---
project: boxbox
adr: 013
title: La política de reacción del rival, cuota por bandera, edad de goma, y un efecto de período
category: data
date: 2026-09-20
status: accepted
supersedes: null
authors: [tomasanchez]
---

# ADR-013: La política de reacción del rival, cuota por bandera, edad de goma, y un efecto de período

## Context

Definido en ADR-012 que los rivales reaccionan a las banderas dentro del
lazo, falta decidir CUÁNDO para un rival. Se midieron 2.828 casos
auto-por-período, temporadas 2022-2026:

1. Cuota de autos en carrera que paran durante el período: roja 94,9%
   (n=276), safety car 43,0% (n=1.198), VSC 24,2% (n=1.354).
2. Reparto por período: SC 63 períodos, mediana 0,47, p10=0,05 p90=0,85,
   nadie para en el 6%. VSC 72 períodos, mediana 0,20, p10=0,00 p90=0,60,
   nadie para en el 17%.
3. Sobredispersión: la varianza de la cuenta de paradas por período es 1,9×
   bajo SC y 2,8× bajo VSC la que darían monedas independientes con las mismas
   composiciones de período (35,34 ± 6,3 contra 18,90, y 18,19 ± 3,1 contra
   6,41). Una primera pasada reportó 9,4× y 5,6×: comparaba la varianza *entre*
   períodos contra la varianza binomial *dentro* de un período, y esa diferencia
   incluye que los períodos difieren en cuántos autos hay y en qué goma llevan,
   que es composición y no azar compartido. El exceso por período va de −9,8 a
   +16,6 autos.
4. Predictor dominante, edad de goma al empezar el período. SC: 0-5 vueltas
   17,0% | 6-10 47,3% | 11-15 60,5% | 16-20 73,0% | 21-25 82,5% | 26-30 73,7%
   | 31+ 93,8%. VSC: 8,8% | 16,9% | 35,6% | 32,4% | 24,6% | 44,4% | 44,7%.
5. Riesgo por vuelta en verde a la misma edad: 0,007 (0-5) hasta 0,051
   (26-30). Acumulado a 3 vueltas con goma de 16-20: 11,9% en verde contra
   73,0% bajo SC, o sea 6,1×.
6. B6.3.8 no predice limpio; está confundido con la edad de goma.

## Decision

Durante un período neutralizado, el rival para con la probabilidad medida
condicionada a (tipo de bandera, edad de goma) — tabla de la medición 4 —,
modulada por un **efecto de período compartido** por todos los autos de ese
sorteo, calibrado para reproducir la sobredispersión medida (1,9× bajo SC,
2,8× bajo VSC). El corrimiento es un desvío en escala logit, un solo parámetro,
y el valor que iguala la varianza observada es σ=1,80 bajo SC y σ=1,15 bajo VSC. Bajo verde el rival apunta a su **ventana proyectada por
`pit_window()`**.

Regla de no doble conteo: durante las vueltas neutralizadas manda la política
de neutralización y NO se aplica además el riesgo verde, porque las cuotas
medidas ya incluyen a los autos que iban a parar igual; contar las dos cosas
contaría la misma parada dos veces.

B6.3.8 no se usa como predictor, por la medición 6: está confundida con la
edad de goma y no aporta señal limpia.

## Alternatives Considered

- **Monedas independientes por auto, sin efecto de período**: rechazada —
  subestimaría la varianza casi a la mitad y nunca produciría ni la estampida ni el
  «paró todo el mundo menos yo», que es justo el escenario que le duele al
  plan focal.
- **Riesgo por vuelta puro, sin plan ni ventana**: rechazada — los rivales
  perderían su plan y la torre de la UI se quedaría sin qué mostrar antes de
  largar.
- **Usar B6.3.8 como predictor**: rechazada por la medición 6, confundida con
  la edad de goma.

## Consequences

`pit_window()` vive en `insights.py`, el motor de reglas, y el simulador no
debe importarlo — acoplaría dos cosas separadas a propósito. La ventana se
pasa como DATO, calculada por quien llama y guardada en el `Car`. Queda
declarado que los abandonos siguen fuera del modelo: un rival reactivo
inmortal compite hasta el final. Método en la misma familia que ADR-011:
distribuciones medidas, nada de formas asumidas.

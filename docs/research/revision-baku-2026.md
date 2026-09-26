# Bakú 2026: la predicción contra lo que pasó

La predicción está en [`prediccion-baku-2026.md`](prediccion-baku-2026.md),
congelada en el commit `418e90f` con la clasificación cargada y la carrera no.
Esto se escribe después. El orden es lo único que hace que el ejercicio mida algo.

Reproducible con `uv run python apps/ml/scripts/baku_2026_review.py`.

## El marcador: 1 de 4

| Criterio | Predicho | Real | |
|---|---|---|---|
| compuesto de salida | medio 12-17, duro 4-8, blando ≤3 | **medio 12, duro 0, blando 10** | ERROR |
| paradas | una, 60% o más | **dos, 94%** | ERROR |
| secuencia | medio → duro la más común | **medio → blando → blando** (8 de 16) | ERROR |
| neutralización | al menos una | **safety car, vueltas 29-38** | acierto |

Cuatro criterios escritos para no dejar lugar a acomodar la lectura después, y
tres cayeron. Conviene decirlo así de seco antes de explicar nada.

## Pero las tres que fallaron fallaron por lo mismo

**Bakú 2026 se decidió en un safety car de diez vueltas, no en el desgaste.**

```
paradas por vuelta:   20: 2 | 26: 1 | 30: 10 | 31: 7 | 32: 1 | 36: 17
vueltas neutralizadas:            29 30 31 32 33 34 35 36 37 38
```

**35 de las 38 paradas de la carrera se hicieron bajo neutralización (92%).**
Contando sólo las tomadas en verde —las únicas que fueron una decisión— el
reparto entre los dieciséis clasificados es: **catorce autos con cero paradas
estratégicas y dos con una.**

El safety car salió en la vuelta 29 y no se fue hasta la 38. El campo paró en la
30-31 y **volvió a parar en la 36**, sin que la neutralización hubiera terminado:
dos juegos gratis dentro del mismo período. Por eso la última tanda de los
dieciséis clasificados mide exactamente 15 vueltas, todas iguales.

Así que la cuenta cruda de «dos paradas» no refuta el pronóstico de una parada;
refuta una carrera que no hubo. Lo que sí es un error mío es haber escrito un
criterio de falsación sobre la cuenta cruda en vez de sobre las paradas en verde,
y eso no se arregla a posteriori: el criterio decía lo que decía, y perdió.

Esto es también algo que **el simulador no representa**: `draw_neutralisations`
sortea períodos y la política de rivales reactivos deja parar una vez por
período. Un segundo juego gratis bajo el mismo safety car no está en el modelo.

## El duro no existió

| compuesto | vueltas corridas |
|---|---|
| blando | 51,4% |
| medio | 48,6% |
| **duro** | **0,0%** |

Nadie calzó un duro en toda la carrera. Los veintidós cumplieron B6.3.8 con medio
+ blando.

**Y las dos predicciones lo tenían como segundo juego.** Yo dije «medio → duro, la
secuencia más común»; el modelo dijo duro para 9 de 22 en la largada. Ése es el
error compartido, y es el más caro de los dos.

La tanda más larga de la carrera fue de **32 vueltas** (el medio de HUL), que cae
exactamente en el tope que el simulador permite para el medio. No lo viola, pero
no sobra nada.

## Mi reparto contra el del modelo

El criterio estaba escrito de antemano: gana el que quede más cerca del real.

| compuesto | real | mío | modelo |
|---|---|---|---|
| blando | 10 (45%) | 3 (14%) | 7 (32%) |
| medio | 12 (55%) | 14 (64%) | 6 (27%) |
| duro | 0 (0%) | 5 (23%) | 9 (41%) |
| **desvío total** | | **64 pp** | **82 pp** |

Gana el historial. Pero la lectura honesta no es «gané»: **gané por el medio y
perdí por el blando**, que era mi afirmación más fuerte y más específica — «en
Bakú nunca largó nadie en blando, ni uno en cuatro años» — y largaron diez.

El modelo, que no tiene ningún motivo para preferir un compuesto sobre otro
porque `COMPOUND_OFFSET_S` vale cero, acertó que el blando iba a correr mucho.
Por la razón equivocada, pero acertó.

## El desgaste medido, y una advertencia sobre su signo

| | mediana s/vuelta | tandas |
|---|---|---|
| medio | **−0,0079** | 18 |
| blando | **−0,0484** | 19 |
| *promedio de la temporada 2026, con el que el simulador corrió Bakú* | *0,0554* | |

**El signo negativo no significa que la goma mejore.** `insights.py` ya lo declara:
el coeficiente de combustible es fijo (0,035 s/vuelta), está calibrado sobre la
era anterior y **sub-corrige** a los autos de 2026, así que la pendiente medida
sale por debajo de la real. Medio campo mide plano o negativo en cualquier vuelta
de cualquier carrera.

Por eso la comparación que vale es contra el promedio de 2026 y no contra el Bakú
histórico (0,0068): los dos números de 2026 salen del **mismo** pipeline
sub-corregido, así que la diferencia entre ellos es real. Comparar contra el
histórico cruza eras *y* pipelines, y es la pata débil del argumento.

Con esa salvedad puesta: **Bakú 2026 fue muchísimo más suave que la temporada
2026**, y eso se sostiene. `circuit_wear.py` había medido que el desgaste no se
transfiere entre eras (r = 0,143) y concluido que para un circuito sin datos del
año en curso corresponde el promedio de la temporada. Para Bakú esa regla eligió
mal. Es **un** caso contra una regla medida sobre 27 pares y no la da vuelta; lo
que muestra es dónde la regla es cara — en los circuitos cuya desviación respecto
del promedio es grande, que son justo los que más necesitan otra respuesta.

## Lo que sí acertó el algoritmo

Corriendo la búsqueda con el desgaste medido en la carrera:

```
búsqueda con el desgaste REAL:  M32-S19
lo que hizo RUS (ganador):      M31-S5-S15
```

**La primera tanda coincide dentro de una vuelta y el orden de compuestos
coincide entero.** Todo lo que las separa son las dos paradas que RUS hizo gratis
bajo el safety car.

La decisión estratégica de la carrera —hasta cuándo estirar el medio y qué calzar
después— el algoritmo la reproduce. Lo que no tiene manera de reproducir es un
regalo. Es la misma lectura que dejó Madrid: el algoritmo no estaba roto, los
insumos sí; y acá ni siquiera los insumos alcanzan a explicar la diferencia, la
explica la bandera.

**Con una salvedad, que se midió en vez de afirmarse.** ¿La búsqueda llega a M32
porque encontró que 32 es lo mejor, o porque el tope del medio la frena ahí? Se
levanta el tope y se vuelve a buscar: **da M51**. O sea que se estira, el tope
estaba atando la respuesta, y que M32 coincidiera con las 31 vueltas de RUS es en
parte mérito del tope y no del algoritmo.

## Lo que destapó ese contrafáctico

`M51` es una carrera entera con un solo juego de medios: **ilegal bajo B6.3.8**.

`_enforce_two_compounds` arregla una estrategia ilegal cambiando el compuesto de
la última parada, y su docstring dice que un plan sin ninguna parada «no se puede
hacer legal, y la aptitud lo va a castigar y va a perder». Con el desgaste de la
temporada eso es cierto: probado a 40, 44 y 51 vueltas la búsqueda devuelve
siempre un plan legal de una parada, aunque un solo juego de duros alcance para
la distancia.

Con el desgaste medido en Bakú deja de ser cierto, y se ve por qué: si la
pendiente es negativa, la goma vieja es más rápida, no parar nunca es óptimo, y
**no hay nada en la aptitud que lo penalice**.

O sea que el artefacto de la sección anterior no es sólo ruido de medición:
realimentado como insumo del modelo, vuelve preferible una estrategia ilegal. No
afecta ninguna cifra publicada —el simulador corre con desgastes positivos— pero
es la razón concreta por la que una pendiente medida no se puede enchufar como
insumo sin mirarle el signo.

## Qué se lleva el trabajo de acá

1. **Un criterio de falsación mal elegido cuenta como error aunque la intuición
   fuera buena.** Escribí «una parada, 60% o más» sobre la cuenta cruda; lo que
   quería decir era «una decisión de parar». Las dos cosas coinciden en una
   carrera sin safety car largo y no coinciden en ésta.
2. **La regla «sin datos del año, usá el promedio» tiene un costo medible**, y es
   mayor justo donde el circuito se aparta más del promedio.
3. **Un desgaste negativo no es un insumo válido**, y hoy nada en el código lo
   frena. Candidato a arreglo: pisar a cero, o rechazar el ajuste y caer al
   promedio, en vez de dejar que la búsqueda concluya que no hay que parar.
4. **Falta representar más de una parada por período de neutralización.** Bakú
   fue exactamente ese caso y el modelo no lo puede generar.

Lo que **no** se evalúa, igual que se escribió antes: quién ganó la carrera. Esto
es sobre estrategia.

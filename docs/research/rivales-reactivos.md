# Rivales que reaccionan: cómo se midió y cómo quedó armado

Este documento es el detalle de construcción y calibración de la reactividad de
los rivales. Vivía en §6 del informe, donde ocupaba la subsección más larga de
todo el trabajo —176 líneas— para una función que, como decía su propio título,
**no movió ninguna cifra publicada** porque está detrás de un interruptor.

Se movió acá para que el informe pese donde tiene que pesar: en si el sistema
predijo carreras o no. Nada se borró. Los dos hallazgos que sí son resultados
—que apilar no se puede decidir en segundos, y que un plan de vuelta fija no es
lo que hace un equipo— se quedaron en el informe, resumidos, con un puntero acá.

Reproducible con `scripts/rival_reaction.py` y `scripts/rivals_compare.py`.
Decisiones asociadas: ADR-012 a ADR-016.

---

## Rivales que reaccionan

Hasta acá el plan del auto elegido se puntuaba contra veintiún rivales que
corren un plan fijo: sale un safety car y no se mueve nadie. Eso evalúa el plan
en un mundo que no existe, y el escenario que de verdad le cuesta la carrera a
un plan —*paró todo el mundo menos yo*— era literalmente insorteable.

**Lo primero que hubo que medir es que una neutralización no es una parada
automática**, que era el supuesto implícito. Sobre 2.828 casos auto-por-período
de 2022 a 2026:

| | paran |
|---|---|
| bandera roja | 94,9% |
| safety car | 43,0% |
| VSC | **24,2%** |

Bajo VSC tres de cada cuatro autos **no** paran. Lo que decide es la edad de la
goma: bajo safety car va del 17,0% con menos de cinco vueltas al 93,8% pasadas
las treinta. La obligación de B6.3.8 no predice limpio —los que no deben parar
paran *más*— porque está confundida con la edad de goma, y no se usa.

**Y los autos no son monedas independientes.** Los períodos reales son
estampidas o congelamientos: bajo safety car la cuota del campo que entra va de
0,05 en el percentil diez a 0,85 en el noventa. Con monedas por auto la varianza
de la cuenta de paradas queda 1,9 veces por debajo de la observada bajo safety
car y 2,8 bajo VSC, y el campo se partiría al medio siempre. Por eso cada
período sortea **un solo corrimiento compartido**, calibrado contra esa varianza
en vez de elegido.

> **Una cifra propia que estuvo mal tres días.** La primera pasada reportó una
> sobredispersión de 9,4×. Comparaba la varianza de la cuenta de paradas *entre*
> períodos contra la varianza binomial *dentro* de un período: la primera incluye
> que los períodos difieren en cuántos autos hay y en qué goma llevan, y eso es
> composición, no azar compartido. Con la referencia correcta —una simulación con
> las mismas composiciones y sin efecto de período— da 1,9×, y bajo VSC resulta
> *mayor* que bajo safety car, al revés de lo que decía. El efecto existe y hacía
> falta; era la mitad de grande.

## Quién cubre una parada, y es el de adelante

Para que un rival responda a la parada del auto elegido hacía falta una tasa
medida. El control es el **espejo**: mismo hueco, un lado y el otro. Un auto dos
segundos adelante y otro dos segundos atrás están igual de cerca de la acción y
sólo uno está amenazado, así que la diferencia entre los dos es el efecto con la
cercanía ya descontada.

| hueco | adelante | atrás | efecto |
|---|---|---|---|
| 0-2 s | 0,237 | 0,159 | **+0,078** |
| 2-5 s | 0,260 | 0,189 | **+0,071** |
| 5-10 s | 0,192 | 0,157 | +0,035 |
| 10-20 s | 0,163 | 0,149 | +0,014 |
| 20-60 s | 0,162 | 0,091 | +0,071 ← artefacto |

El que reacciona es el que va **adelante**, no el que viene atrás, y visto
después es obvio: una parada desde atrás es un undercut apuntado a vos, y una
desde adelante no te deja nada que contestar. Es el mismo punto de vista que la
tarjeta de undercut de la pantalla ya tomaba.

La última fila se descartó, y el motivo está medido. El efecto se apaga de 0,078
a 0,014 y después *reaparece* con un intervalo estrechísimo, lo cual no puede ser
causal. A 0-2 s las dos mitades promedian 10,7 y 10,4 de puesto; a 20-60 s
promedian **5,0 y 13,6**. A esa distancia el espejo dejó de comparar autos
comparables y pasó a comparar frente de parrilla contra fondo. Más allá de cinco
segundos el diseño no puede separar el efecto del puesto, y se declara cero en
vez de publicar un número que se sabe contaminado.

## Cómo quedó armado, y qué reproduce

La reactividad va en dos niveles porque cuestan cosas muy distintas. Reaccionar
a las **banderas** no depende del plan que se está evaluando, así que la traza de
cada rival se sigue calculando una sola vez y la reactividad sale **gratis**
dentro de la búsqueda. Reaccionar **al auto elegido** sí depende de él, y se paga
una vez sobre el plan ganador en vez de mil veces adentro: 6,2 s por piloto pasan
a 6,9, un 11% y no veinte veces.

Contra lo que se ajustó, sobre los 22 planes reales y 3.000 carreras sorteadas:

| | modelo | medido |
|---|---|---|
| paran bajo bandera roja | 0,972 | 0,949 |
| paran bajo safety car | 0,381 | 0,430 |
| paran bajo VSC | 0,260 | 0,242 |
| el equipo mete los dos en la misma vuelta | 0,62 | 0,70 |
| cubre el que va hasta 5 s adelante | +0,058 | +0,071 |
| **reparto del equipo bajo SC** (ninguno/uno/dos) | 0,50 / 0,24 / 0,26 | 0,43 / 0,28 / 0,29 |

La última fila es la que más dice, porque **nadie se la enseñó al modelo**: cada
auto decide solo y el reparto de cuántos de sus dos autos mete un equipo sale
emergente, a cinco puntos de lo observado. El sorteo compartido por período es lo
que se lo gana; autos independientes casi nunca meterían los dos juntos.

Las dos filas del medio quedan cortas por la misma razón, y se informa en vez de
corregirlo: la probabilidad extra sólo alcanza a los autos que podían parar
igual, y uno que está dentro de `MIN_STINT` de su parada anterior no se mueve con
ninguno de los dos mecanismos. Subir las constantes para pegarle al número sería
ajustar alrededor de una restricción que está puesta a propósito.

## La doble parada no se puede decidir en segundos

Cuando un equipo mete los dos autos, el 70% de las veces es en la misma vuelta y
el segundo hace cola. Pareado dentro del mismo par —mismo equipo, misma vuelta,
misma carrera— esa cola cuesta **+1,0 s en verde, +3,5 bajo safety car y +3,2
bajo VSC**.

Eso corrige una nota de investigación propia que afirmaba doce segundos, medidos
comparando grupo contra grupo con n=18 y sin parear. Y da vuelta la lectura:
apilar sale **barato**, que es por qué lo hacen.

Lo interesante es que el modelo **no puede elegir** cuándo apilar. Medido en
segundos, partir gana fácil: retener un auto una vuelta cuesta como una décima
de desgaste y ahorra los 3,5 s enteros. Cualquier cosa que optimice ese reloj
partiría siempre y terminaría *más* lejos de la realidad que apilando siempre.
Los equipos apilan porque el segundo auto vuelve detrás del tráfico, que es
posición y no reloj. Es el mismo desacuerdo entre segundos y puestos que este
trabajo ya había encontrado para las paradas bajo neutralización, y la salida es
la misma: **sortear la coordinación a la tasa medida, no decidirla**.

## Y por qué nada de esto movió una sola cifra publicada

Todo lo anterior está detrás de un interruptor. `fixed` es el modelo como era y
tiene que seguir siéndolo; `reactive` es el nuevo. Regenerando el export en modo
fijo y comparándolo campo por campo contra el publicado hay **una sola
diferencia**, la clave que anota el modo. Todo lo demás idéntico.

Eso no salió gratis: la primera versión sorteaba el corrimiento de período sin
condición, y eso corre el flujo del generador **también en modo fijo**. Habría
movido en silencio cada número de este informe. Lo atajó un test.

En modo reactivo cambian **9 de los 22 planes**. Lo que *no* se puede leer es el
puntaje: mejora, pero no porque el plan mejore. Los rivales reactivos paran 2,11
veces contra 1,86 de los autos reales, y cada parada de más les cuesta tiempo —
sobre las mismas carreras el campo termina **1,35 s más lento**. El auto elegido
sube sin haber cambiado nada: no mejoró él, empeoró el campo. Y ese exceso de
paradas es el sesgo ya conocido, el del escalón de compuestos sin identificar.
Los puntajes se comparan dentro de un modo, no entre modos.

## El hallazgo que no entra en este modelo

Al construirlo apareció la limitación más grande de todas, y ésta sí tiene
medición. El desgaste del simulador **es** probabilístico, pero el plan fija la
vuelta y el auto para ahí en todos los sorteos, le esté sobrando goma o se le
esté cayendo a pedazos. El modelo sortea la incertidumbre y después la ignora.

Los equipos no. Estimando la caída sobre las **primeras ocho vueltas** de cada
tanda —ajustarla sobre la tanda entera sería usar el futuro para predecir el
futuro— y preguntando si predice cuánto va a durar, sobre 2.876 tandas:

| compuesto | correlación | goma que aguanta | goma que se cae |
|---|---|---|---|
| blando | −0,177 | 19,6 vueltas | 15,1 |
| medio | −0,145 | 22,7 | 18,9 |
| duro | −0,157 | 29,2 | 22,7 |

Entre tres y seis vueltas y media de tanda, según cómo venga la goma. Y no es el
combustible: dentro del **mismo compuesto y la misma tanda** el efecto sigue —el
medio en la primera tanda da −0,290, con 23,0 vueltas contra 18,5—.

Lo mismo pasa con qué se calza. Bajo VSC temprano el **75,4%** monta duro contra
el 62,3% de los que paran temprano en verde, esa tanda dura 29,7 vueltas contra
26,3, y el 37% llega a la bandera sin volver a parar contra el 24%. La
neutralización temprana no sólo adelanta la parada: cambia a qué se cambia.

Las dos cosas dicen lo mismo. **Un plan de vuelta fija no es lo que hace un
equipo**: el equipo sale con una intención y la corrige con lo que ve —la goma,
la bandera, el hueco de atrás—. Eso es una *política* y no un plan, y la forma de
la respuesta cambiaría de «parás en la 21 y en la 48» a «salís a duro; parás
cuando la caída pase de tanto o cuando salga una neutralización con más de tanta
goma; si tenés a alguien a menos de dos segundos, te cubrís primero».

Es un entregable distinto del que este trabajo define, y es exactamente la
comparación que el trabajo ya tenía anotada: **planificar contra reaccionar**.
Lo que se agrega hoy es que deja de ser una intuición y pasa a tener el tamaño
medido de lo que está en juego.


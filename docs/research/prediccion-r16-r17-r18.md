# Predicciones pre-registradas: fechas 16, 17 y 18 de 2026

**Escrito antes de ver ninguna de las tres carreras.** De las fechas 16 y 17 se
cargó **sólo la clasificación**; la sesión de carrera no se tocó. La fecha 18
—Austin, 25 de octubre— todavía no corrió, así que ahí no hay nada que mirar ni
siquiera queriendo.

Es la continuación del ejercicio de Bakú, que salió uno de cuatro. Tres casos más,
y los tres eligidos porque ponen a prueba cosas distintas.

## Antes de los números: qué se está evaluando, exactamente

Hay una confusión posible que conviene cerrar acá, porque atraviesa las tres
predicciones y porque ya hizo fallar un criterio en Bakú.

**En una carrera real, la salida de un safety car, un VSC o una bandera roja
cambia la estrategia en tiempo real.** El muro ve la bandera, calcula en segundos
si al auto le conviene entrar *ahora*, y decide. Esa decisión usa información que
no existía antes de largar: que la bandera salió, en qué vuelta, cuánto va a
durar y dónde está cada auto en ese momento.

**Este trabajo no hace eso, y no pretende hacerlo.** Lo que entrega es un plan
*pre-carrera*, y las neutralizaciones entran como lo único que se puede saber de
ellas antes de largar: **su probabilidad**. El simulador sortea mil doscientas
carreras en las que el safety car sale con la frecuencia medida, empieza donde
históricamente empieza y dura lo que históricamente dura, y el plan se elige por
cómo le va **en promedio sobre todas esas carreras**. No por cómo le iría en una.

De ahí salen dos consecuencias que hay que tener presentes al leer el marcador:

1. **Acertar «va a haber un safety car» no es acertar «hay que parar en la vuelta
   32».** El modelo puede tener razón sobre la distribución y equivocarse en la
   carrera concreta, y eso no lo refuta: es lo que una predicción probabilística
   hace. Lo que sí lo refutaría es que la distribución estuviera mal.
2. **Por eso los criterios de abajo se escriben sobre decisiones y no sobre
   resultados crudos.** En Bakú el criterio decía «una parada en el 60% de los
   casos» y la carrera dio dos en el 94% — pero treinta y cinco de las treinta y
   ocho paradas fueron **regaladas** por dos safety cars, y contando sólo las
   tomadas en verde, catorce de los dieciséis clasificados no pararon ninguna
   vez. El pronóstico de una parada describía bien la decisión y el criterio lo
   contó mal. **Ese error no se repite acá**: donde se cuenta paradas, se cuentan
   las tomadas bajo bandera verde, y las neutralizadas se informan aparte.

## Los tres casos, y qué pone a prueba cada uno

| | Circuito | Vueltas | Qué sabe el simulador | Qué pone a prueba |
|---|---|---|---|---|
| **R16** | Kuala Lumpur | 56 | **nada**: cero vueltas en el conjunto, de ninguna temporada | el caso más duro posible |
| **R17** | Marina Bay | 62 | 4.439 vueltas de 2022-2025, **nada de 2026** | ¿sirve el historial de un circuito en otra era? |
| **R18** | Austin | 56 | 4 carreras 2022-2025, **nada de 2026** | lo mismo, pero sin haber corrido todavía |

Los tres corren con el **promedio de desgaste de la temporada 2026** —duro 0,0613,
medio 0,0597, blando 0,0386 s/vuelta— porque ninguno tiene celdas propias del año.
Es la misma situación de Madrid y Bakú.

### Un resultado que ya se puede escribir, sin esperar ninguna carrera

El modelo devuelve **exactamente el mismo plan para Kuala Lumpur y para Austin**:
`H31-S25`, una parada. No es casualidad ni error: los dos son de 56 vueltas y
ninguno tiene datos de 2026, así que el modelo **no tiene con qué distinguirlos**.
Un circuito callejero tropical y uno permanente con veinte curvas rápidas reciben
la misma recomendación porque el sistema sólo los conoce por su longitud.

Eso ya es una medición del techo del sistema, y no depende de cómo salgan las
carreras.

## R16 · Kuala Lumpur

Sin historial propio de ninguna temporada. El historial general de 2026 dice:
blando 19,8%, medio 71,2%, duro 9,1%, y 2,00 paradas de media.

**Lo que digo yo**, apoyado en el perfil general de 2026 y en que es un circuito
de calor extremo y abrasivo:

1. **Medio domina la salida**: entre 11 y 17 de los 22.
2. **Dos paradas en verde** es lo modal, 50% o más de los clasificados.
3. **Al menos una neutralización.**

**Lo que dice el modelo**: largar en **duro**, `H31-S25`, **una** parada. Prefiere
duro sobre medio por 0,70 s y sobre blando por 0,83.

## R17 · Marina Bay

Historial de 69 clasificados en cuatro carreras:

| | |
|---|---|
| larga en medio | **56,5%** |
| larga en intermedio | 20,3% (2022 fue mojada) |
| larga en blando | 14,5% |
| larga en duro | 8,7% |
| **una parada** | **76,8%** |
| secuencia más común | **medio → duro**, 25 de 69 |
| neutralización | 2 de 4 años (2022 y 2023; 2024 y 2025 limpias) |

**Lo que digo yo:**

1. **Medio domina**: entre 12 y 18 de los 22.
2. **Una parada en verde** es lo modal, 60% o más.
3. **Medio → duro** la secuencia más común.
4. **Neutralización**: es lo más probable, pero el historial reciente dice que no
   siempre — me juego a que **sí sale al menos una**, sabiendo que dos de los
   últimos cuatro años fueron limpios.

**Lo que dice el modelo**: largar en **blando**, `S24-S24-H14`, **dos** paradas.
Es el único de los tres circuitos donde el modelo pide dos paradas, y contradice
de frente al historial en las dos cosas: compuesto y cantidad.

## R18 · Austin

Historial de 72 clasificados en cuatro carreras:

| | |
|---|---|
| larga en medio | **77,8%** |
| larga en duro | 18,1% |
| larga en blando | 4,2% |
| una parada | 47,2% |
| **dos paradas** | **50,0%** |
| secuencias | `M-S` 13, `M-H` 12, `M-M-H` 10, `M-H-M` 9 — **todas arrancan en medio** |
| neutralización | 3 de 4 años (SC 2022, SC 2024, VSC 2025) |

**Lo que digo yo:**

1. **Medio domina fuerte**: entre 14 y 19 de los 22. Es la apuesta más firme de
   las tres, porque las cuatro secuencias más comunes del circuito arrancan en
   medio y ninguna otra se le acerca.
2. **Paradas en verde repartidas entre una y dos**, sin que ninguna llegue al 65%.
   Austin es el único de los tres donde el historial no se decide.
3. **Al menos una neutralización**, que pasó en 3 de los últimos 4 años.

**Lo que dice el modelo**: largar en **duro**, `H31-S25`, **una** parada — idéntico
a Kuala Lumpur, por el motivo explicado arriba.

## Cómo se falsea cada una

Sin lugar para acomodar la lectura después.

- **Compuesto de salida.** Acierto si el conteo real cae dentro de la banda que
  di. Si el medio queda fuera de rango en cualquiera de las tres, me equivoqué en
  ésa.
- **Paradas.** Se cuentan **sólo las tomadas bajo bandera verde**. Las
  neutralizadas se informan aparte y no entran en el criterio, por el motivo
  explicado al principio. Acierto si la moda y el porcentaje que di se cumplen.
- **Secuencia** (sólo R17). Acierto si medio → duro es la más frecuente.
- **Neutralización.** Acierto si sale al menos una en cada carrera.
- **Modelo contra historial.** Gana el que quede más cerca del reparto real de
  compuestos de salida, en puntos porcentuales sumados. El modelo pide duro en
  dos de las tres y blando en la restante; el historial pide medio en las tres.
  **Es una discrepancia total: no hay forma de que los dos acierten.**

Lo que **no** se evalúa: quién gana. Esto es sobre estrategia.

## Lo que ya se sabe que va a pasar, y por qué no cuenta como acierto

El modelo va a errar el compuesto de salida en las tres, casi con seguridad. No
hace falta esperar: `COMPOUND_OFFSET_S` vale cero —el escalón de ritmo entre
compuestos es una falla de identificación declarada— así que el modelo elige por
durabilidad y nunca tiene motivo para preferir el medio, que es intermedio en
todo. Ya se midió sobre una grilla entera: pone medio **cero veces de veintidós**
cuando la realidad lo pone entre el 55% y el 85%.

Escribirlo antes es parte del ejercicio. Si el modelo acierta igual, el
razonamiento de arriba estaba mal y eso es información.

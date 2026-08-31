# ¿Sirven las temporadas anteriores? — sí, y la decisión anterior estaba mal

Medido 2026-08-31, **re-medido el mismo día con el conjunto completo** (104 carreras de 2022 a
2026, tras descargar las 47 que faltaban). Reproducible con
`uv run python scripts/era_pooling.py`.

> **Los números de la primera versión de este documento se midieron con un caché incompleto**
> (56 carreras) y quedaron cortos. Los de abajo son los definitivos.

## Corrección

Los documentos anteriores de este repositorio afirmaban que **no se pueden mezclar temporadas**
porque la jerarquía de degradación de compuestos se invirtió en 2026. **La medición no sostiene
esa conclusión.** Mezclar temporadas mejora el modelo de forma clara.

El error de razonamiento: la inversión de la jerarquía afecta **una** de las diecinueve variables.
El resto —diferencias con los rivales, vueltas en el stint, vueltas restantes, estado de pista—
transfiere sin problema. Se confundió «esta variable no transfiere» con «la temporada no sirve».

## El experimento

Mismo conjunto de prueba en los tres casos: 2026 R10–R12, nunca visto.

| Conjunto de entrenamiento | Vueltas |
|---|---|
| Solo 2026 (R1–R9) | 10.143 |
| Mezclado: 2022–2025 + 2026 R1–R9 | **107.308** (10,6×) |

### Clasificador de parada

| Entrenamiento | PR-AUC | Mejora sobre azar | F1 |
|---|---|---|---|
| Solo 2026 | 0,1430 | 4,24× | 0,2428 |
| **Mezclado, sin variable de era** | **0,2238** | **6,64×** | **0,2934** |
| Mezclado + `season` + `nueva_era` | 0,1896 | 5,63× | 0,2730 |

Mezclar mejora el PR-AUC un **56%** y sube la mejora sobre azar de 4,24× a 6,64×.

**La variable de era perjudica.** Con el conjunto completo, decirle al modelo de qué temporada
viene cada dato baja el PR-AUC de 0,2238 a 0,1896. Con el caché incompleto parecía ayudar un
poco; era ruido. La lectura es que el modelo aprende mejor los patrones generales sin que se lo
invite a separar por año.

### Regresor de degradación

| Entrenamiento | MAE | MAE ingenuo | ¿Gana? |
|---|---|---|---|
| Solo 2026 | 0,9372 | 0,7159 | No |
| **Mezclado, sin era** | **0,6975** | 0,7255 | **Sí** |
| Mezclado + era | 0,7416 | 0,7255 | No |

**Este es el cambio más importante.** Con el conjunto completo el regresor de degradación
**supera por primera vez al modelo ingenuo** (0,6975 contra 0,7255). Con sólo 2026 perdía por
amplio margen (0,9372 contra 0,7159).

Es decir: la conclusión anterior de que «el regresor no funciona» era en buena parte un artefacto
de tener pocos datos, no una propiedad del problema.

## La inversión es real, pero es un detalle

Degradación mediana por compuesto, s/vuelta:

| Temporada | DURO | MEDIO | BLANDO | Orden de desgaste |
|---|---|---|---|---|
| 2022 | 0,0085 | 0,0282 | 0,0774 | BLANDO > MEDIO > DURO |
| 2023 | 0,0204 | 0,0243 | 0,0403 | BLANDO > MEDIO > DURO |
| 2024 | 0,0287 | 0,0277 | 0,0638 | BLANDO > DURO > MEDIO |
| 2025 | 0,0136 | 0,0167 | 0,0475 | BLANDO > MEDIO > DURO |
| **2026** | **0,0436** | 0,0239 | **0,0142** | **DURO > MEDIO > BLANDO** |

Cuatro temporadas seguidas con el blando como el que más se gasta, y **2026 invertida por
completo**. El hallazgo original se confirma, y con el conjunto completo se ve más nítido.
Lo que no se confirma es la consecuencia que se le atribuyó.

Nótese que las cifras de 2023 y 2024 **cambiaron** respecto de la primera medición (el blando de
2023 pasó de 0,0664 a 0,0403). El caché incompleto también sesgaba estas estimaciones.

## Qué usar y para qué

La decisión correcta no es global: **depende del componente**.

| Componente | Ventana de datos | Motivo |
|---|---|---|
| Clasificador de parada | **Mezclar todo** | Medido: 56% mejor de PR-AUC |
| Simulador — comportamiento general | **Mezclar todo** | 10,6× más datos |
| **Magnitudes de degradación por compuesto** | **Solo 2026** | Acá sí muerde la inversión |
| **Coeficiente de combustible** | **Solo 2026** | Los autos son ~32 kg más livianos |
| Tasas de Safety Car y VSC por circuito | **Mezclar todo** | Con 12 carreras hay una visita por circuito; es imposible estimarlo con una sola temporada |
| Pérdida por parada en boxes | **Mezclar todo** | Depende del largo del pit-lane, no del auto |
| Restricciones reglamentarias | **Solo 2026** | El artículo B6.3.8 es de este año |

Nótese que el análisis de neutralizaciones de este repositorio **ya usaba 56 carreras de 2022 a
2026**, precisamente porque una temporada sola no alcanzaba. La regla de «solo 2026» ya estaba
siendo violada por necesidad, sin haberlo reconocido.

## ¿Y la novedad del trabajo?

El argumento de novedad **no depende** de entrenar sólo con 2026. Ningún trabajo publicado usó
datos de 2026 porque la temporada está en curso; eso sigue siendo cierto entrenando con 107.308
vueltas en lugar de 10.143.

La novedad está en **qué se analiza y qué se pronostica**, no en privar de datos al modelo.
Entrenar con menos datos para poder decir «solo 2026» sería sacrificar desempeño por una frase.

## Pendiente

- [x] ~~Completar el caché de 2025~~ — hecho: 104 carreras de 2022 a 2026, y los números de arriba
      son los del conjunto completo.
- [ ] Completar 2018 a 2021. La tendencia entre 56 y 104 carreras sugiere que todavía hay margen.
- [ ] Probar ponderar las carreras de 2026 más que las anteriores, en lugar de la variable
      categórica de era, que con el conjunto completo perjudica de forma clara.
- [ ] Verificar si la degradación **normalizada** (relativa a la mediana de la temporada)
      transfiere mejor que la absoluta.

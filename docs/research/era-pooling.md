# ¿Sirven las temporadas anteriores? — sí, y la decisión anterior estaba mal

Medido 2026-08-31. Reproducible con `uv run python scripts/era_pooling.py`.

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
| Mezclado: 2022–2024 + 2026 R1–R9 | **57.200** (5,6×) |

### Clasificador de parada

| Entrenamiento | PR-AUC | Mejora sobre azar | F1 |
|---|---|---|---|
| Solo 2026 | 0,1430 | 4,24× | 0,2428 |
| Mezclado, sin variable de era | 0,1895 | 5,62× | 0,2791 |
| **Mezclado + `season` + `nueva_era`** | **0,1922** | **5,70×** | **0,2842** |

Mezclar mejora el PR-AUC un **34%** y sube la mejora sobre azar de 4,24× a 5,70×. Y funciona
**incluso sin decirle al modelo de qué temporada viene cada dato**; agregar la variable de era
suma sólo un poco más.

### Regresor de degradación

| Entrenamiento | MAE | MAE ingenuo | ¿Gana? |
|---|---|---|---|
| Solo 2026 | 0,9372 | 0,7159 | No |
| **Mezclado, sin era** | **0,7831** | 0,7229 | No, pero casi |
| Mezclado + era | 0,8090 | 0,7229 | No |

Sigue sin superar al modelo ingenuo, pero pasa de 0,937 a **0,783**, casi cerrando la brecha.
Curiosamente, agregar la variable de era lo **empeora** (0,809 contra 0,783): con cuatro valores
posibles, parece que el modelo se apoya demasiado en ella.

## La inversión es real, pero es un detalle

Degradación mediana por compuesto, s/vuelta:

| Temporada | DURO | MEDIO | BLANDO | Orden de desgaste |
|---|---|---|---|---|
| 2022 | 0,0085 | 0,0282 | 0,0774 | BLANDO > MEDIO > DURO |
| 2023 | 0,0137 | 0,0160 | 0,0664 | BLANDO > MEDIO > DURO |
| 2024 | 0,0388 | 0,0376 | 0,0673 | BLANDO > DURO > MEDIO |
| **2026** | **0,0436** | 0,0239 | **0,0142** | **DURO > MEDIO > BLANDO** |

2022 y 2023 son consistentes, 2024 empieza a mezclarse y **2026 se invierte por completo**. El
hallazgo original se confirma. Lo que no se confirma es la consecuencia que se le atribuyó.

## Qué usar y para qué

La decisión correcta no es global: **depende del componente**.

| Componente | Ventana de datos | Motivo |
|---|---|---|
| Clasificador de parada | **Mezclar todo** | Medido: 34% mejor |
| Simulador — comportamiento general | **Mezclar todo** | 5,6× más datos |
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
datos de 2026 porque la temporada está en curso; eso sigue siendo cierto entrenando con 57.200
vueltas en lugar de 10.143.

La novedad está en **qué se analiza y qué se pronostica**, no en privar de datos al modelo.
Entrenar con menos datos para poder decir «solo 2026» sería sacrificar desempeño por una frase.

## Pendiente

- [ ] Completar el caché de 2018 a 2021 y 2025 y volver a medir. La tendencia sugiere que aún hay
      margen.
- [ ] Probar ponderar las carreras de 2026 más que las anteriores, en lugar de la variable
      categórica de era, que empeoró el regresor.
- [ ] Verificar si la degradación **normalizada** (relativa a la mediana de la temporada)
      transfiere mejor que la absoluta.

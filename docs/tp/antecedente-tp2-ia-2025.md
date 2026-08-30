# Antecedente directo — TP N.º 2, Inteligencia Artificial, 2025 (Grupo 12)

*Clasificación de Compuesto para la Fórmula 1 utilizando una Red Neuronal Artificial del Tipo
Multiperceptrón* — Pasqualino, Denoya, Sánchez C., **Sánchez T.**, Lingeri. Presentado
12/10/2025. **APROBADO.**

Este es un trabajo previo del mismo integrante, en el mismo dominio y con la misma biblioteca.
Debe declararse explícitamente en la propuesta de IAA. Ocultarlo sería el peor error posible; se
descubriría en la defensa.

## Qué hicieron

| | |
|---|---|
| Pregunta | ¿Qué compuesto (S / M / H) elegir en una parada? |
| Datos | FastF1, temporadas **2020–2022** |
| Registros | **782** (625 entrenamiento / 157 prueba) — una fila por parada |
| Partición | **80/20 aleatoria** |
| Modelo | MLP, tres experimentos: 32 neuronas tanh; 64 ReLU con descenso de gradiente; 2 capas (64, 32) ReLU + Adam |
| Herramientas | Google Colab, TensorFlow, scikit-learn, pandas, Gemini para limpieza |

### Resultados obtenidos

| Experimento | Exactitud entrenamiento | Exactitud prueba | F1 clase SOFT (prueba) |
|---|---|---|---|
| 1 — Adam, lr 0,01, 32 neuronas | 0,83 | **0,62** | 0,43 |
| 2 — SGD, lr 0,2, 64 neuronas | 0,82 | **0,70** | — |
| 3 — Adam, lr 0,001, 2 capas | 0,84 | **0,69** | 0,53 |

En los tres casos: **sobreajuste** (entrenamiento ~0,83, prueba ~0,65) y la clase **SOFT** siempre
la peor, con apenas 25 ejemplos en prueba.

## Lo que dijo el corrector

**Veredicto:** APROBADO. *"El trabajo práctico está bien realizado aplicando correctamente una
Red Neuronal Artificial… La construcción de cada red es adecuada y bien explicada… las
conclusiones se encuentran desarrolladas en forma completa y clara."*

**La única crítica:**

> *"El análisis presentado es consistente con los mismos, aunque **se podría haber elaborado un
> poco más**."*

**Anotaciones al margen:**

| Dónde | Comentario |
|---|---|
| 100 épocas | *"Podrían haber usado menos para validación…"* |
| Gráfico de error, exp. 1 | *"Se puede observar un sobre-aprendizaje del modelo… el modelo no 'generaliza' la clase SOFT correctamente."* |
| Exp. 2 | *"Aquí también se nota un sobre-aprendizaje pronunciado, aunque el modelo generaliza mejor."* |
| Exp. 3 | *"Nuevamente hay un sobre-aprendizaje lo cual influye en la capacidad de generalización de la clase SOFT."* |
| Sobre Adam | *"Sí, Adam es mucho más flexible por aplicar una tasa adaptativa."* |
| Sobre *"resuelve satisfactoriamente el problema"* | *"**Para la clase SOFT no del todo.**"* |
| Sobre el sobreajuste | *"Esto también se debe producir por el **desbalanceo de las clases**, al contar con menos ejemplos SOFT el modelo no los logra aprender tan bien. Entonces, se debería intentar **mejorar los datos**."* |

**Nota importante:** los resultados fueron débiles (0,62–0,70 de exactitud con sobreajuste
evidente) y el trabajo **igual fue aprobado**. El corrector atribuyó la debilidad a las
características de los datos y no la penalizó. Lo que sí marcó fue la **profundidad del
análisis**.

## Seis lecciones aplicables

1. **El análisis es lo que se califica, no el número.** Única crítica recibida. La propuesta de
   IAA es deliberadamente pesada en análisis por este motivo.
2. **El desbalanceo de clases fue el diagnóstico del corrector.** El nuestro es **28:1**, mucho
   peor que el de ellos. Debe estar en primer plano, con ponderación de clases y PR-AUC en lugar
   de exactitud.
3. **Nunca usaron *early stopping*** — declarado "NO aplicado" en los tres experimentos, y el
   corrector marcó sobreajuste tres veces. Corregible de forma trivial.
4. **Partición 80/20 aleatoria sobre registros de parada.** Con varias paradas por carrera, es
   casi seguro que hubo fuga entre carreras. Nuestra partición **por carrera** es una mejora
   metodológica concreta y citable.
5. **El corrector responde bien a la justificación técnica** (comentó a favor sobre Adam).
   Explicar *por qué* se eligió cada cosa suma.
6. **Los resultados débiles reportados con honestidad se aprueban.** Precedente directo para
   nuestro enfoque de reportar el fracaso de la predicción puntual.

## El riesgo de solapamiento, y cómo se resuelve

Mismo dominio, misma biblioteca, problema adyacente. Un corrector podría verlo como reciclaje.
La respuesta es declararlo y mostrar las diferencias sustantivas:

| Dimensión | TP2 — IA 2025 | BoxBox — IAA |
|---|---|---|
| **Temporadas** | 2020–2022 | **2026**, primer año del nuevo reglamento |
| **Pregunta** | ¿Qué compuesto? | **¿Cuándo parar y cuántas veces?** |
| **Salida** | Clase puntual (S/M/H) | **Distribución** de estrategias |
| **Técnica** | MLP puro | **Híbrido**: regresión + motor de reglas + Monte Carlo |
| **Volumen** | 782 registros | **14.095 vueltas**, 756 stints |
| **Validación** | 80/20 aleatoria | Por carrera, 25%, más **pronóstico prospectivo** |
| **Reglamento** | No modelado | **Filtro duro** B6.3.8 / B6.1.2 |

Hay además una continuidad intelectual que conviene explicitar, porque es un hallazgo genuino:

> El TP anterior intentó **aprender** la elección de compuesto y obtuvo 0,69 de exactitud con
> sobreajuste persistente. El trabajo actual muestra por qué: en 2026 la elección está en buena
> medida **determinada por el reglamento** —el artículo B6.3.8 obliga a usar una especificación
> obligatoria anunciada por la FIA— y la diferencia de degradación entre compuestos es de apenas
> 0,029 s/vuelta. **No era un problema de arquitectura de red: era un problema mal planteado.**
> Por eso aquí la elección de compuesto se resuelve con un filtro reglamentario y no con un
> clasificador.

Esa frase convierte el solapamiento en aporte: el trabajo nuevo **explica el resultado débil del
anterior**.

## Referencia

Pasqualino, F.; Denoya, A.; Sánchez, C.; Sánchez, T.; Lingeri, M. (2025). *Clasificación de
Compuesto para la Fórmula 1 utilizando una Red Neuronal Artificial del Tipo Multiperceptrón*.
Trabajo Práctico N.º 2, Inteligencia Artificial, UTN FRBA.
Repositorio: https://github.com/FrancoP08/TP2-IA-2025

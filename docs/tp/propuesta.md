# Propuesta de Trabajo Práctico Integral — BoxBox

**Inteligencia Artificial Avanzada — Ingeniería en Sistemas de Información**
**Versión 2, 2026-08-25.** Reemplaza la conceptualización inicial; los cambios están
justificados con mediciones propias, no con supuestos.

---

## 1. El problema

Asistir al ingeniero de estrategia de Fórmula 1 en la decisión de parada en boxes: dado el
estado de una carrera, **estimar la estrategia de neumáticos y paradas** que minimiza la
pérdida de posiciones.

**El sistema no predice el resultado de la carrera.** Predice el *plan*: cuántas paradas, en
qué ventana de vueltas, con qué secuencia de compuestos.

## 2. Qué cambió respecto de la propuesta original, y por qué

Se construyó el pipeline de datos y se midió antes de comprometerse con un diseño. Cinco
hallazgos obligaron a cambiar la propuesta. Cada uno está documentado en `docs/research/`.

| Hallazgo medido | Consecuencia sobre el diseño |
|---|---|
| La jerarquía de compuestos **se invirtió** en 2026: el blando pasó de ser el que más se degrada (0,0673 s/vuelta en 2024) al que menos (0,0142) | **No se pueden mezclar temporadas.** El TP usa exclusivamente 2026 |
| Predecir "¿boxea esta vuelta?" da PR-AUC 0,103 contra 0,037 de azar, y la curva de aprendizaje **baja** al agregar carreras | El clasificador **no es el entregable**; es una línea base declarada |
| El costo de una parada bajo SC/VSC es **0 posiciones** contra 2 en verde, aunque en segundos parezca mayor | El sistema optimiza **posiciones, no segundos** |
| No se detecta efecto por circuito en la tasa de Safety Car: todo se encoge a 0,86×–1,09× de la media global | El simulador sortea SC con **una tasa global**, no por circuito |
| F1 **no publica** datos de ERS, batería ni aero activa | La mitad energética de la estrategia 2026 queda **fuera de alcance, declarado** |

## 3. El Sistema Inteligente propuesto

Tres capas, cada una ubicada donde la evidencia la respalda:

| Capa | Técnica | Respaldo empírico |
|---|---|---|
| **1. Estimación de degradación** | Regresión (gradient boosting) sobre la curva de degradación por compuesto, circuito y temperatura | **22.378 pendientes ajustadas.** Es el componente con datos abundantes |
| **2. Motor de reglas** | Reglas de producción y tablas de decisión (R1–R12 de la conceptualización) sobre las estimaciones de la capa 1 | Auditable: cada recomendación viene con las reglas que se dispararon |
| **3. Simulación Monte Carlo** | Sorteo de eventos de pista + ejecución del motor de reglas vuelta a vuelta, algunos miles de veces | Produce una **distribución** de estrategias, que es lo que los datos sí sostienen |

**La salida no es un punto, es una distribución:** `P(1 parada)`, `P(2 paradas)`, secuencia modal
de compuestos, e intervalo creíble para la vuelta de la primera parada.

Esto no es una concesión: es el resultado de haber probado el enfoque puntual y haberlo visto
fallar. Predecir "Verstappen para en la vuelta 22" no es alcanzable con estos datos, y afirmarlo
sería lo más fácil de refutar — la carrera siguiente simplemente no coincide.

### 3.1. Modelo de contraste

Se entrena además un **clasificador supervisado** (`BOX` / `SEGUIR`) y se reporta honestamente
como línea base débil: F1 0,194, lift 2,8× sobre azar. Su valor para el informe es doble:
mostrar que la comparación se hizo, y mostrar que **la curva de aprendizaje decreciente es en sí
un hallazgo**, no un fracaso.

## 4. Alcance

**Dentro:** temporada 2026, carreras en seco y mixtas, estrategia de neumáticos y paradas,
decisión medida en posiciones, eventos de pista (SC, VSC, bandera roja).

**Fuera, y declarado:**

- **Gestión de energía y Manual Override.** Con ~50% de la potencia proveniente del MGU-K, el
  estado de carga es hoy parte real del cálculo estratégico. F1 no publica el dato — confirmado
  empíricamente y por el mantenedor de FastF1. El sistema modela la mitad de neumáticos y
  posición en pista, y lo dice explícitamente.
- Fallas mecánicas, penalizaciones deportivas, órdenes de equipo.
- Clasificación y carreras sprint.

Declarar este límite es más fuerte que ignorarlo: es la diferencia entre un trabajo que conoce
sus datos y uno que no.

## 5. Datos

| | |
|---|---|
| Fuente | `fastf1` 3.8.3 (MIT), Python 3.13 |
| Temporada | 2026, rondas 1–12 disponibles hoy; 23 al cierre |
| Volumen actual | 14.095 vueltas, 756 stints, 527 paradas |
| Completitud | `Stint`, `Compound`, `TyreLife`, `FreshTyre`, `TrackStatus` al **100%** |
| Límite operativo | FastF1 corta a **500 llamadas/hora**; el caché se construye por tandas |

El dataset **crece durante el cuatrimestre**: al cierre de las entregas habrá cerca del doble de
carreras que hoy.

## 6. Plan por entrega (metodología IDEAL)

| Entrega | Contenido | Referencia temporal |
|---|---|---|
| **E1 — Selección** | Problema, objetivos, alcance, fuentes. Incluye la declaración de que la mitad energética queda fuera | Septiembre |
| **E2 — Conceptualización** | Modelos estáticos (Concepto-Atributo-Valor, pseudo-reglas R1–R12, tablas y árbol de decisión) y dinámicos (descomposición funcional, módulos). **Corregida**: reglas R2/R3 expresadas en posiciones | Ya redactada, requiere revisión |
| **E3 — Formalización** | Elección de tecnología, arquitectura de tres capas, antecedentes y comparación con el estado del arte | Octubre |
| **E4 — Implementación** | Regresor de degradación, motor de reglas, simulador Monte Carlo. Métricas y ajuste | Noviembre |
| **E5 — Presentación** | Resultados, **calibración de los pronósticos emitidos**, problemas, líneas futuras | Noviembre |

### 6.1. El diferencial: pronóstico prospectivo

Quedan **11 carreras** entre hoy y el cierre de la temporada:

| Ronda | Circuito | Fecha |
|---|---|---|
| 13 | Monza | 2026-09-06 |
| 14 | Barcelona | 2026-09-13 |
| 15 | Bakú | 2026-09-26 |
| 16 | Sakhir | 2026-10-04 |
| 17 | Marina Bay | 2026-10-11 |
| 18–23 | Austin → Abu Dhabi | oct–dic |

La propuesta es **publicar un pronóstico fechado y congelado antes de cada carrera** y puntuarlo
después. Eso vale más que cualquier tabla de validación cruzada: no admite fuga de datos, no se
puede ajustar a posteriori, y casi ningún trabajo de cátedra lo hace.

Diez de las once son fines de semana convencionales con FP1, FP2 y FP3 completos.

## 7. Métricas

El clasificador y el regresor se evalúan de la forma habitual, pero **el sistema completo se
evalúa por calibración**:

| Métrica | Qué mide |
|---|---|
| MAE del regresor de degradación | Error en s/vuelta de la curva estimada |
| **Cobertura del intervalo** | ¿La estrategia real cayó dentro del intervalo pronosticado? |
| **Calibración** | De las carreras a las que se asignó 70% de probabilidad de 1 parada, ¿ocurrió en ~70%? |
| F1 y exhaustividad del clasificador | Línea base declarada, con su lift sobre azar |
| Delta de posiciones contrafáctico | Posiciones ganadas o perdidas simulando la estrategia recomendada |

### 7.1. Por qué la exactitud queda prohibida en el informe

"Nunca boxear" acierta el **96,3%** de las vueltas. Pero el argumento es más fuerte que eso:
**esa estrategia es ilegal.**

> **Artículo B6.3.8** — *2026 Formula 1 Sporting Regulations*, Issue 05, 27-02-2026:
> "Unless they have used intermediate or wet-weather tyres during the Race, each driver must use
> at least two (2) different specifications of dry-weather tyres during the Race, at least one (1)
> of which must be a mandatory dry-weather Race tyre specification."
>
> "Failure to comply with these requirements will result in the **disqualification** of the
> relevant driver from the Race results."

Es decir: un clasificador que maximice exactitud converge a una estrategia que termina en
**descalificación**. La métrica no premia algo inútil, premia algo prohibido.

Esto es, además, el mejor argumento a favor de la arquitectura propuesta. El motor de reglas
**no puede** emitir una estrategia ilegal: R12 y la tabla de decisión de compuesto ya codifican la
restricción. Un clasificador puramente estadístico no tiene forma de saberlo.

**Verificación sobre nuestros datos:** de los 177 pilotos que terminaron una carrera en seco en
2026, **los 177 usaron dos o más compuestos** (129 usaron exactamente dos, 48 usaron tres). Cero
violaciones. Es también una validación del pipeline de extracción de stints.

### 7.2. Mónaco es un caso aparte, y el simulador debe saberlo

El mismo artículo B6.3.8 impone en Mónaco un mínimo de **tres juegos de neumáticos** — una
**doble parada obligatoria** — además de la regla de dos compuestos. Por eso Mónaco 2026 registra
89 stints entre 22 pilotos (≈ 4,05 por piloto): no es caos, es reglamento.

El simulador debe tratar Mónaco como una restricción distinta, no como un circuito más.

## 8. Antecedentes

El problema general **está trabajado**, y el informe debe decirlo:

- *Data-driven pit stop decision support for Formula 1 using deep learning models*
  (Frontiers in AI, 2025): predice ventanas de parada con Bi-LSTM sobre datos FastF1 de
  **2020–2024**, F1 = 0,81.
- Varios proyectos públicos con XGBoost y aprendizaje por refuerzo sobre 2020–2024.

**La novedad no es el problema: es la temporada.** Ningún trabajo publicado puede haber usado
2026 — el reglamento cambió este año, la jerarquía de compuestos se invirtió y la ronda 12 se
corrió hace tres días. Citar el paper de 2025 como línea base y explicar por qué su modelo **no
transfiere** a 2026 es un aporte concreto, y más defendible que fingir que nadie tuvo la idea.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| La estrategia es **dirigida por eventos**, no por neumáticos: Zandvoort tuvo bandera roja en la vuelta 2 y 21 de 22 autos "pararon" gratis | Ya resuelto: `free_stop` separa las paradas libres. Es también el argumento a favor del enfoque distribucional |
| El coeficiente de combustible está fijo en 0,035 s/vuelta, calibrado en la era anterior | Ajustarlo con datos 2026 antes de E4. Es hoy el supuesto más débil del pipeline |
| Pocas carreras (12 hoy) para estimar efectos por circuito | Encogimiento jerárquico; se reporta la incertidumbre en lugar de ocultarla |
| Un pronóstico congelado puede fallar en público | Es el punto. Se puntúa la calibración, no el acierto puntual |

## 10. Estado actual

Ya construido y verificado en `E:\dev\boxbox`:

- Backend FastAPI generado (33 tests en verde), frontend Vite, workspace de ML
- Pipeline `ingest → features` funcionando sobre carreras reales
- Cinco documentos de investigación con mediciones reproducibles
- Dos bugs propios encontrados y corregidos (fuga por valores faltantes; paradas libres bajo
  bandera roja) y varias afirmaciones tempranas rectificadas

Lo que falta es el simulador Monte Carlo, que pasa a ser el entregable central.

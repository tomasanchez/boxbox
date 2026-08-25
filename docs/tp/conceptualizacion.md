# Idea 1 — Asistente de estrategia de neumáticos y parada en boxes (Fórmula 1)

**Inteligencia Artificial Avanzada — Ingeniería en Sistemas de Información**
**Entrega N.º 2 — Conceptualización (Metodología IDEAL)**

---

## 1. Introducción

Durante una carrera de Fórmula 1 el ingeniero de estrategia debe decidir, vuelta a vuelta,
si conviene que su piloto entre a boxes o permanezca en pista, y con qué compuesto de
neumático continuar. La decisión debe tomarse en pocos segundos, combinando el estado
degradado del neumático actual, el ritmo de los rivales cercanos, la pérdida de tiempo que
implica el pit-lane de ese circuito, la dificultad para adelantar y la posibilidad de un
evento de pista (Safety Car, Virtual Safety Car o lluvia) que cambie por completo el costo
de la parada.

Se propone construir un **Sistema Inteligente que asista al ingeniero de estrategia**: dado
el estado de la carrera en la vuelta *N*, el sistema recomienda **BOX** o **SEGUIR**, y en
caso de recomendar la parada indica el **compuesto destino** y una **estimación del tiempo
neto ganado o perdido** respecto de la alternativa contraria.

Cabe aclarar que la recomendación es de carácter **asistivo**: no reemplaza al ingeniero de
estrategia ni al director deportivo, sino que le ofrece una segunda opinión cuantificada y
trazable en el instante en que debe decidir.

### 1.1. Objetivo y alcance

**Objetivo.** Recomendar la decisión de parada en boxes y la elección de compuesto que
minimice el tiempo total de carrera del piloto propio.

**Dentro del alcance:**

- Carreras de Fórmula 1 desde la temporada 2018 en adelante (disponibilidad de datos de
  timing vuelta a vuelta).
- Condiciones de pista seca y mixta (seco a lluvia y lluvia a seco).
- Estrategias de una y dos paradas.
- Un único piloto de referencia por simulación, con sus dos rivales inmediatos (el de
  adelante y el de atrás).

**Fuera del alcance:**

- Fallas mecánicas, abandonos y penalizaciones deportivas.
- Órdenes de equipo y estrategia del compañero de equipo (*teammate stacking*).
- Carreras al sprint y sesiones de clasificación.
- Decisiones de setup del auto o de gestión de combustible más allá de la corrección de
  tiempo por carga.

### 1.2. Fuentes de conocimiento y de datos

| Fuente | Tipo | Uso |
|---|---|---|
| Biblioteca `fastf1` (Python) | Datos | Tiempos por vuelta, compuesto, edad de neumático, número de stint, sectores, posición, gaps, clima y banderas de SC/VSC, desde 2018 |
| API Ergast y su sucesor comunitario `jolpica-f1` | Datos | Resultados históricos, orden de llegada, paradas |
| Reglamento Deportivo FIA (artículos sobre neumáticos y SC/VSC) | Conocimiento experto | Reglas duras: obligación de usar dos compuestos, uso de intermedios y de lluvia |
| Transcripciones públicas de radio de equipo y análisis de prensa técnica | Conocimiento experto | Heurísticas de undercut y overcut, umbrales de degradación |

> El conjunto de datos resultante es del orden de **decenas de miles de vueltas etiquetadas**
> (aproximadamente 20 pilotos x 55 vueltas x 22 carreras x 6 temporadas), lo que hace viable
> el entrenamiento de un modelo supervisado.

---

## 2. Métodos disponibles

El problema admite dos abordajes complementarios, que en este trabajo se combinan:

1. **Razonamiento simbólico.** La estrategia de F1 está fuertemente reglamentada y la
   heurística de los ingenieros es explícita y verbalizable (*"si el gap con el de atrás es
   mayor que la pérdida de pit-lane, la parada es gratis"*). Esto se modela naturalmente con
   pseudo-reglas y tablas de decisión.

2. **Aprendizaje a partir de datos.** La **curva de degradación** de cada compuesto depende
   del circuito, la temperatura de pista y el estilo del piloto, y no puede expresarse como
   una regla fija. Se estima con un modelo de regresión entrenado sobre las vueltas
   históricas.

La combinación de ambos produce un **sistema híbrido**: el modelo aprendido alimenta con
números a la base de reglas, y la base de reglas aporta la trazabilidad que un modelo
puramente estadístico no ofrece, condición indispensable para que un ingeniero de estrategia
confíe en la recomendación.

### 2.1. Fórmulas empleadas

| Concepto | Fórmula | Notas |
|---|---|---|
| Tiempo de vuelta corregido por combustible | `t_corr = t_vuelta - B * (V_total - V_actual)` | `B` de aproximadamente 0,035 s por vuelta de combustible restante |
| Degradación acumulada del stint | `Deg(e) = t_corr(e) - t_corr(3)` | `e` es la edad del neumático en vueltas; se toma la vuelta 3 del stint como referencia estabilizada |
| Tasa de degradación | `TD = dDeg / de` (pendiente de las últimas 5 vueltas) | en s/vuelta |
| Pérdida por parada | `PitLoss = t_entrada + t_estacionario + t_salida` | Constante por circuito (entre 18 s y 28 s) |
| Pérdida por parada bajo SC/VSC | `PitLoss_SC = PitLoss * k`, con `k` de 0,45 (SC) y 0,60 (VSC) | El pelotón circula lento: la parada cuesta menos |
| Ganancia inmediata de neumático nuevo | `GanNuevo = Deg(e_actual) - Deg(0)` | Lo que se recupera por vuelta al montar goma fresca |
| Balance de undercut | `U = GanNuevo * V_ataque - PitLoss + Gap_delante` | `V_ataque` son las vueltas hasta que el rival reaccione (típicamente 2) |
| Balance de overcut | `O = (TD_rival - TD_propia) * V_extra - PitLoss + Gap_delante` | Conviene cuando la degradación propia es menor |
| Vida útil restante | `VidaRest = VidaEsp(compuesto, circuito) - e` | `VidaEsp` se estima del histórico del circuito |
| Costo de salir a tráfico | `CostoTrafico = V_atrapado * dt_sucio` | `dt_sucio` de aproximadamente 0,4 s/vuelta en aire sucio |
| **Beneficio neto de parar** | `BN = U - CostoTrafico` (o `O` según el caso) | Si `BN > 0` conviene parar |

---

## 3. Modelos conceptuales

### 3.1. Modelos estáticos

#### 3.1.1. Conocimientos estratégicos

Describen *cómo* se resuelve el problema, es decir, el orden en que el experto razona:

1. **Evaluar el estado del neumático actual.** A partir de la edad, el compuesto y la
   degradación medida en las últimas vueltas, determinar si está `Nuevo`, `Óptimo`,
   `Desgastado` o `Crítico`.
2. **Estimar la pérdida futura por vuelta.** Proyectar la curva de degradación para las
   vueltas restantes del stint hipotético.
3. **Evaluar la ventana de pits.** Verificar si con la vuelta actual el stint restante es
   alcanzable con el compuesto disponible, y si la parada respeta la obligación
   reglamentaria de usar dos compuestos distintos.
4. **Evaluar el entorno competitivo.** Calcular el balance de undercut y de overcut contra
   el rival de adelante, el riesgo de perder posición contra el de atrás y el costo de
   reincorporarse en tráfico.
5. **Evaluar los eventos de pista.** Si hay SC o VSC activo, o lluvia inminente, recalcular
   con el `PitLoss` reducido o cambiar directamente la familia de compuesto.
6. **Emitir la recomendación.** Decidir `BOX` o `SEGUIR`, el compuesto destino y el
   beneficio neto estimado, con la traza de las reglas que se dispararon.

#### 3.1.2. Conocimientos tácticos

Son las heurísticas y fórmulas que se aplican en cada paso. Además de las fórmulas de la
sección 2.1, se expresan las siguientes **pseudo-reglas**:

```text
R1.  SI (neumático.estado = Crítico)
     ENTONCES decisión = BOX                                  [prioridad máxima]

R2.  SI (evento_pista = SafetyCar) Y (neumático.edad > 8)
         Y (parada_obligatoria_pendiente = Sí)
     ENTONCES decisión = BOX

R3.  SI (evento_pista = VirtualSafetyCar) Y (beneficio_neto_SC > 0)
     ENTONCES decisión = BOX

R4.  SI (clima.lluvia = Inminente) Y (neumático.familia = Seco)
     ENTONCES decisión = BOX Y compuesto_destino = Intermedio

R5.  SI (clima.pista = Secándose) Y (neumático.familia = Mojado)
         Y (vueltas_desde_fin_lluvia > 3)
     ENTONCES decisión = BOX Y compuesto_destino = Blando

R6.  SI (gap_atrás > PitLoss + 2)
     ENTONCES riesgo_perder_posición = Nulo
     SINO riesgo_perder_posición = Alto

R7.  SI (balance_undercut > 0) Y (riesgo_perder_posición = Nulo)
         Y (neumático.estado <> Nuevo)
     ENTONCES decisión = BOX

R8.  SI (degradación_propia < degradación_rival_delante)
         Y (gap_delante < 2) Y (circuito.dificultad_adelantar = Alta)
     ENTONCES decisión = SEGUIR                               [overcut]

R9.  SI (vueltas_restantes < VidaRest) Y (neumático.estado <> Crítico)
         Y (parada_obligatoria_cumplida = Sí)
     ENTONCES decisión = SEGUIR                               [ir hasta el final]

R10. SI (costo_tráfico > beneficio_neto)
     ENTONCES decisión = SEGUIR

R11. SI (vueltas_restantes <= 3) Y (neumático.estado <> Crítico)
     ENTONCES decisión = SEGUIR

R12. SI (parada_obligatoria_pendiente = Sí) Y (vueltas_restantes <= 5)
     ENTONCES decisión = BOX                                  [regla dura FIA]
```

**Tabla de decisión — determinar `neumático.estado`**

| Condiciones \ Caminos | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| `edad / vida_esperada` | < 0,25 | 0,25 a 0,70 | 0,70 a 0,95 | > 0,95 |
| `tasa_degradación` | — | < 0,10 s/v | 0,10 a 0,25 s/v | > 0,25 s/v |
| **`neumático.estado`** | **Nuevo** | **Óptimo** | **Desgastado** | **Crítico** |

**Tabla de decisión — determinar `decisión`**

| Condiciones \ Caminos | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| `neumático.estado` | Crítico | — | — | Desgastado | Óptimo o Nuevo | Desgastado |
| `evento_pista` | — | SC o VSC | Ninguno | Ninguno | Ninguno | Ninguno |
| `clima.lluvia` | — | — | Inminente | No | No | No |
| `beneficio_neto` | — | > 0 | — | > 0 | — | <= 0 |
| `riesgo_perder_posición` | — | — | — | Nulo | — | — |
| **Decisión** | **BOX** | **BOX** | **BOX** | **BOX** | **SEGUIR** | **SEGUIR** |

**Tabla de decisión — determinar `compuesto_destino`**

| Condiciones \ Caminos | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `clima.pista` | Mojada | Húmeda | Seca | Seca | Seca |
| `vueltas_restantes` | — | — | <= 18 | 19 a 35 | > 35 |
| **Compuesto destino** | **Lluvia extrema** | **Intermedio** | **Blando** | **Medio** | **Duro** |

> Restricción reglamentaria transversal: en carrera seca el piloto debe haber usado al menos
> **dos compuestos de seco distintos** al finalizar. Si el compuesto elegido violara esa
> restricción, se selecciona el siguiente candidato admisible de la tabla.

#### 3.1.3. Árbol de decisión

```text
                        ¿Evento de pista activo?
                        /                      \
                      SÍ                        NO
                       |                         |
        ¿SC/VSC y parada pendiente?      ¿Lluvia inminente?
          /             \                  /            \
        SÍ              NO               SÍ             NO
         |               |                |              |
       BOX      ¿Beneficio_SC > 0?   BOX (Interm.)  ¿estado = Crítico?
                  /        \                          /          \
                SÍ         NO                       SÍ            NO
                 |          |                        |             |
                BOX      SEGUIR                     BOX     ¿Beneficio_neto > 0?
                                                             /            \
                                                           SÍ              NO
                                                            |               |
                                                ¿riesgo_posición = Nulo?  SEGUIR
                                                    /            \
                                                  SÍ             NO
                                                   |              |
                                                  BOX          SEGUIR
```

#### 3.1.4. Conocimientos fácticos

**Diccionario de conceptos**

| Nombre | Identificador | Unidad |
|---|---|---|
| Tiempo de vuelta | `t_vuelta` | s |
| Tiempo de vuelta corregido por combustible | `t_corr` | s |
| Edad del neumático | `e` | vueltas |
| Tasa de degradación | `TD` | s/vuelta |
| Pérdida por parada en boxes | `PitLoss` | s |
| Distancia al rival de adelante | `Gap_delante` | s |
| Distancia al rival de atrás | `Gap_atrás` | s |
| Vueltas restantes de carrera | `V_rest` | vueltas |
| Vida esperada del compuesto | `VidaEsp` | vueltas |
| Beneficio neto de parar | `BN` | s |

**Tabla Concepto – Atributo – Valor**

| Concepto | Atributo | Valor |
|---|---|---|
| **Neumático** | Compuesto | { Blando, Medio, Duro, Intermedio, Lluvia extrema } |
| | Familia | { Seco, Mojado } |
| | Edad | Numérico (vueltas) |
| | Tasa de degradación | Numérico (s/vuelta) |
| | Estado | { Nuevo, Óptimo, Desgastado, Crítico } |
| **Piloto propio** | Posición | Numérico (1 a 20) |
| | Número de stint | Numérico |
| | Compuestos ya usados | Conjunto de Compuesto |
| | Parada obligatoria cumplida | { Sí, No } |
| **Rival** | Rol | { Delante, Atrás } |
| | Gap | Numérico (s) |
| | Compuesto | Compuesto |
| | Edad de neumático | Numérico (vueltas) |
| | Ha parado | { Sí, No } |
| **Circuito** | Nombre | Texto |
| | Pérdida de pit-lane | Numérico (s) |
| | Dificultad para adelantar | { Alta, Media, Baja } |
| | Vueltas totales | Numérico |
| | Abrasividad | { Alta, Media, Baja } |
| **Clima** | Estado de pista | { Seca, Húmeda, Mojada, Secándose } |
| | Lluvia | { No, Inminente, Presente } |
| | Temperatura de pista | Numérico (grados C) |
| **Evento de pista** | Tipo | { Ninguno, Bandera amarilla, VSC, Safety Car, Bandera roja } |
| | Vueltas activo | Numérico |
| **Recomendación** | Decisión | { BOX, SEGUIR } |
| | Compuesto destino | Compuesto o No aplica |
| | Beneficio neto estimado | Numérico (s) |
| | Confianza | Numérico (0 a 1) |
| | Reglas disparadas | Lista de identificadores |

**Identificación de relaciones entre conceptos**

```text
Circuito       1 --- N   Carrera
Carrera        1 --- N   Vuelta
Vuelta         1 --- N   EstadoPiloto        (una fila por piloto y vuelta)
EstadoPiloto   1 --- 1   Neumático           (el montado en esa vuelta)
EstadoPiloto   1 --- 2   Rival               (delante y atrás)
Vuelta         1 --- 1   Clima
Vuelta         1 --- 1   EventoPista

EstadoPiloto + Clima + EventoPista + Circuito          ==>  Recomendación
Neumático.Compuesto + Circuito.Abrasividad + TempPista ==>  VidaEsp
Neumático.Edad + VidaEsp + TD                          ==>  Neumático.Estado
```

### 3.2. Modelos dinámicos

#### 3.2.1. Árbol de descomposición funcional

```text
                    Recomendar estrategia de parada
                                  |
     +--------------+-------------+--------------+---------------+
     |              |             |              |               |
 Adquirir      Estimar        Evaluar       Evaluar         Emitir
 estado de     degradación    entorno       eventos de      recomendación
 carrera       y vida útil    competitivo   pista
     |              |             |              |               |
  Normalizar    Corregir      Calcular      Detectar        Aplicar base
  telemetría    por combust.  undercut      SC / VSC        de reglas
     |              |             |              |               |
  Derivar       Ajustar        Calcular      Detectar        Calcular
  gaps          curva de       overcut       lluvia          beneficio neto
                degradación       |                              |
                    |          Estimar                       Generar
                Proyectar      costo de                      traza de
                pérdida        tráfico                       decisión
```

#### 3.2.2. Descripción de los módulos

**Módulo 1 — Recomendar estrategia de parada** *(principal)*

| Ítem | Contenido |
|---|---|
| **Descripción** | A partir del estado de la carrera en la vuelta *N*, produce la recomendación de parada, el compuesto destino y su justificación. |
| **Propósito** | Determinar si el piloto debe entrar a boxes en la vuelta actual. |
| **Entrada – Origen** | Estado de carrera de la vuelta *N* (telemetría de timing), parámetros del circuito y compuestos disponibles. Origen: sistema de timing o base de datos histórica. |
| **Razonamiento** | Se ejecutan en secuencia los submódulos 1.1 a 1.5. El 1.5 integra los resultados numéricos de los anteriores contra la base de reglas y resuelve los conflictos por prioridad. |
| **Salida – Destino** | `Recomendación { decisión, compuesto_destino, beneficio_neto, confianza, reglas_disparadas }`. Destino: pantalla del ingeniero de estrategia. |

**Módulo 1.1 — Estimar degradación y vida útil**

| Ítem | Contenido |
|---|---|
| **Propósito** | Cuantificar cuánto tiempo por vuelta se está perdiendo por desgaste y cuántas vueltas útiles restan. |
| **Entrada necesaria** | `Neumático.Compuesto`, `Neumático.Edad`, serie de `t_vuelta` del stint, `Circuito.Abrasividad`, `Clima.TempPista`, `V_rest` |
| **Acciones** | 1) Corregir cada `t_vuelta` por carga de combustible. 2) Calcular `Deg(e)` respecto de la vuelta 3 del stint. 3) Ajustar la tasa `TD` sobre las últimas 5 vueltas. 4) Consultar el modelo de regresión para obtener `VidaEsp`. 5) Derivar `Neumático.Estado` con la tabla de decisión correspondiente. |
| **Salida producida** | `TD`, `VidaRest`, `Neumático.Estado`, `GanNuevo` |

**Módulo 1.2 — Evaluar entorno competitivo**

| Ítem | Contenido |
|---|---|
| **Propósito** | Determinar si la parada gana o pierde posición neta frente a los rivales inmediatos. |
| **Entrada necesaria** | `Gap_delante`, `Gap_atrás`, `Rival.Compuesto`, `Rival.EdadNeumático`, `PitLoss`, `GanNuevo`, `Circuito.DificultadAdelantar` |
| **Acciones** | 1) Calcular el balance de undercut `U`. 2) Calcular el balance de overcut `O`. 3) Estimar `CostoTrafico` proyectando en qué posición se reincorpora. 4) Determinar `riesgo_perder_posición` según R6. |
| **Salida producida** | `U`, `O`, `CostoTrafico`, `riesgo_perder_posición` |

**Módulo 1.3 — Evaluar eventos de pista**

| Ítem | Contenido |
|---|---|
| **Propósito** | Detectar condiciones que alteren el costo o la familia de la parada. |
| **Entrada necesaria** | `EventoPista.Tipo`, `EventoPista.VueltasActivo`, `Clima.EstadoPista`, `Clima.Lluvia` |
| **Acciones** | 1) Si hay SC o VSC, recalcular `PitLoss_SC` con el factor `k`. 2) Si hay lluvia inminente o pista secándose, forzar el cambio de familia de compuesto. |
| **Salida producida** | `PitLoss_efectivo`, `familia_requerida`, `evento_activo` |

**Módulo 1.4 — Seleccionar compuesto destino**

| Ítem | Contenido |
|---|---|
| **Propósito** | Elegir el compuesto con el que se reincorpora, respetando el reglamento. |
| **Entrada necesaria** | `V_rest`, `Clima.EstadoPista`, `Piloto.CompuestosYaUsados`, `familia_requerida`, juegos de neumáticos disponibles |
| **Acciones** | 1) Aplicar la tabla de decisión de compuesto. 2) Verificar la restricción de dos compuestos distintos. 3) Verificar la disponibilidad física del juego; si no hay, tomar el siguiente candidato. |
| **Salida producida** | `compuesto_destino` |

**Módulo 1.5 — Emitir recomendación**

| Ítem | Contenido |
|---|---|
| **Propósito** | Integrar todo lo anterior en una decisión única y trazable. |
| **Entrada necesaria** | Salidas de 1.1, 1.2, 1.3 y 1.4 |
| **Acciones** | 1) Calcular `BN`. 2) Evaluar la base de pseudo-reglas R1 a R12 en orden de prioridad. 3) Resolver conflictos: gana la regla de mayor prioridad. 4) Consultar el clasificador aprendido y comparar con la decisión simbólica; si difieren, bajar la `confianza` y exponer ambas. 5) Registrar las reglas disparadas. |
| **Salida producida** | `Recomendación` completa, informada al ingeniero de estrategia |

---

## 4. Tipo de Sistema Inteligente propuesto

Se propone un **sistema híbrido de dos capas**:

**Capa 1 — Modelo de aprendizaje supervisado (regresión).** Estima la curva de degradación
`t_corr = f(compuesto, edad, circuito, temp_pista, piloto)`. Se propone comenzar con un
modelo de *gradient boosting* sobre datos tabulares (XGBoost o LightGBM) por su desempeño en
este tipo de datos y por la interpretabilidad que aportan las importancias de variables.
Métrica: **MAE** en segundos por vuelta.

**Capa 2 — Sistema basado en reglas de producción.** Consume las estimaciones de la capa 1 y
aplica la base de pseudo-reglas y tablas de decisión de la sección 3.1.2. Aporta la
**trazabilidad**: toda recomendación viene acompañada de las reglas que la produjeron.

**Modelo de contraste.** En paralelo se entrena un **clasificador supervisado**
(`BOX` o `SEGUIR`) sobre las decisiones reales tomadas por los equipos, usado como control
del sistema de reglas y como línea base de comparación.

### 4.1. Métricas de evaluación previstas

| Métrica | Qué mide |
|---|---|
| MAE del regresor de degradación | Error en segundos por vuelta de la curva estimada |
| Exactitud, precisión, exhaustividad y F1 del clasificador | Coincidencia con la decisión real del equipo |
| Matriz de confusión | Distribución de falsos BOX y falsos SEGUIR |
| **Delta de tiempo contrafáctico** | Segundos netos ganados o perdidos al simular la estrategia recomendada frente a la efectivamente ejecutada. Es la métrica que da valor al trabajo. |
| Cobertura de la base de reglas | Porcentaje de vueltas resueltas por regla explícita frente a las resueltas por el modelo |

### 4.2. Alternativas evaluadas y descartadas

| Alternativa | Motivo del descarte |
|---|---|
| Red neuronal profunda extremo a extremo | La estrategia de F1 exige justificación; una caja negra no es aceptable para un ingeniero de carrera. Además el volumen de datos no justifica la complejidad. |
| Aprendizaje por refuerzo sobre un simulador de carrera | Conceptualmente el abordaje ideal, pero requiere construir primero un simulador fiel, lo que excede el alcance del cuatrimestre. Se propone como línea futura. |
| Red bayesiana | Adecuada para modelar la incertidumbre del Safety Car, pero débil para la parte numérica de degradación. Se considera para el submódulo 1.3. |
| Sistema puramente basado en reglas | Los umbrales de degradación varían por circuito, compuesto y temperatura; fijarlos a mano produciría un sistema frágil. |

---

## 5. Riesgos identificados

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Ruido en los tiempos de vuelta (tráfico, banderas amarillas locales, vueltas de entrada y salida de boxes) | Alto | Filtrar las vueltas no representativas antes de ajustar la curva de degradación |
| Etiqueta débil: la decisión real del equipo no siempre fue la óptima | Alto | No usar la decisión real como única verdad; apoyarse en la métrica contrafáctica |
| El cambio de reglamento técnico de 2022 (efecto suelo) altera las curvas de degradación | Medio | Entrenar por era reglamentaria o incluir la temporada como variable |
| Clases desbalanceadas: se para unas 2 veces en unas 55 vueltas | Alto | Ponderación de clases, submuestreo de la clase mayoritaria y evaluación por F1 en lugar de exactitud |
| Discontinuación de la API Ergast | Bajo | Usar `fastf1` como fuente primaria y el sucesor comunitario como respaldo |

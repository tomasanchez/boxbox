# Brief de diseño — UI del simulador de estrategia

Documento para delegar a un agente de diseño. Contiene el contrato de datos real, no inventado:
todos los valores de ejemplo salen de mediciones sobre carreras de 2026.

---

## 1. Qué es esto

Una interfaz para un sistema que **arma el plan de neumáticos de una carrera de Fórmula 1**:
cuántas paradas, en qué vueltas, con qué compuesto. La referencia visual son las gráficas de
*F1 Insights* que aparecen en la transmisión — «Pit Window: vueltas 24–31», «si BEA para ahora,
sale a 0,3 s de HUL».

## 2. La restricción de diseño más importante

> **Nunca mostrar una vuelta exacta como si fuera un dato cierto.**

El sistema entrega **distribuciones**, no valores puntuales, y esto no es un detalle de
implementación: es la conclusión central del trabajo. Se midió que predecir un valor exacto no
funciona, porque la estrategia depende de eventos imposibles de anticipar (una bandera roja en la
vuelta 2, un Safety Car a mitad de carrera).

En la práctica:

| Prohibido | Correcto |
|---|---|
| «Para en la vuelta 22» | «Ventana: vueltas 19–26» |
| «Va a hacer 2 paradas» | «2 paradas: 48% · 1 parada: 31% · 3 paradas: 21%» |
| «El undercut funciona» | «Sale adelante — 1,9 s, 83% de probabilidad» |
| Un número sin contexto | El número con su incertidumbre al lado |

Un diseñador sin esta instrucción va a producir predicciones puntuales, porque quedan más
limpias. Sería un error que invalida la tesis del trabajo.

**Segunda regla:** cuando la confianza está entre 35% y 65%, el sistema dice literalmente **«a
cara o cruz»**. Hay que diseñar ese estado, no esconderlo.

## 3. Contrato de datos

### 3.1. Estado de un piloto en una vuelta

```json
{
  "code": "VER",
  "team": "Red Bull Racing",
  "position": 3,
  "compound": "HARD",
  "tyre_age": 16,
  "degradation_s": -0.50,
  "degradation_rate": 0.099,
  "gap_ahead_s": 1.45,
  "gap_behind_s": 0.98
}
```

- `compound` ∈ `SOFT | MEDIUM | HARD | INTERMEDIATE | WET`
- `degradation_s`: segundos por vuelta que está perdiendo por desgaste. **Puede ser negativo**
  (el auto todavía está mejorando porque quema combustible).
- `tyre_age`: vueltas con esa goma. **Puede arrancar en más de 0** si el juego se usó en
  clasificación.

### 3.2. Ventana de boxes

```json
{ "opens_lap": 30, "closes_lap": 48 }
```

o bien:

```json
null
```

**El `null` es frecuente y hay que diseñarlo.** Cerca de la mitad de la parrilla, a mitad de
carrera, no tiene ventana proyectable porque su degradación es plana o negativa. La UI debe decir
algo honesto («sin proyectar») y no inventar un rango ni dejar la celda vacía.

### 3.3. Duelo de estrategia

```json
{
  "chaser": "NOR", "leader": "PIA",
  "gap_now": 0.98,
  "response_laps": 2,
  "per_lap_gain": 1.41,
  "gap_after": -1.85,
  "probability": 0.83,
  "verdict": "SALE_ADELANTE"
}
```

- `gap_after` **negativo** = el perseguidor sale adelante.
- `verdict` ∈ `SALE_ADELANTE (p≥0,65) | CARA_O_CRUZ (0,35–0,65) | SIGUE_ATRAS (p≤0,35)`
- El veredicto lo manda la **probabilidad**, no el valor proyectado.

### 3.4. Distribución de estrategias (salida del algoritmo genético)

```json
{
  "driver": "LEC",
  "stop_distribution": { "1": 0.31, "2": 0.48, "3": 0.19, "4": 0.02 },
  "modal_plan": [
    { "compound": "MEDIUM", "laps": 18 },
    { "compound": "HARD",   "laps": 25 },
    { "compound": "SOFT",   "laps": 14 }
  ],
  "first_stop_interval": { "low": 16, "high": 23, "median": 19 },
  "expected_positions_gained": 1.4
}
```

### 3.5. Contexto de carrera

```json
{
  "season": 2026, "round": 12, "circuit": "Zandvoort",
  "total_laps": 72, "current_lap": 30,
  "track_status": "GREEN",
  "sc_probability": 0.57,
  "mandatory_compounds": ["MEDIUM", "HARD"],
  "min_sets": 2
}
```

- `track_status` ∈ `GREEN | YELLOW | VSC | SC | RED`
- `min_sets` vale 2 salvo en **Mónaco, donde vale 3** (doble parada obligatoria).

## 4. Pantallas

### P1 — Panel de carrera *(prioridad alta — es la pantalla principal)*

Análoga a la transmisión. Para una carrera y una vuelta dadas:

- **Ventanas de boxes** de los primeros 8–10 pilotos: posición, código, compuesto con su color,
  edad de goma, ventana o «sin proyectar», degradación actual.
- **Duelos activos**: pares de autos a menos de 6 segundos, ordenados por probabilidad.
- **Barra de estado de pista** siempre visible. Bajo Safety Car o VSC toda la pantalla cambia de
  carácter: parar cuesta **0 posiciones en vez de 2**, y eso tiene que ser inmediatamente obvio.

Datos reales para maquetar (2026 Budapest, vuelta 30 de 70):

| Pos | Piloto | Compuesto | Edad | Ventana | Degradación |
|---|---|---|---|---|---|
| 1 | PIA | HARD | 14 | 30–48 | +1,58 s |
| 2 | NOR | HARD | 13 | 30–48 | +1,21 s |
| 3 | VER | HARD | 16 | sin proyectar | −0,50 s |
| 4 | LEC | HARD | 14 | 30–48 | +1,10 s |
| 5 | ANT | HARD | 8 | 31–48 | +0,90 s |
| 6 | HAM | HARD | 17 | sin proyectar | +0,00 s |
| 7 | HAD | HARD | 11 | 42–48 | +0,90 s |
| 8 | RUS | HARD | 3 | sin proyectar | −0,15 s |

Duelo real de esa vuelta: **NOR vs PIA**, gap 0,98 s, gana 1,41 s por vuelta, proyectado −1,85 s,
**83%**.

### P2 — Explorador de estrategias *(prioridad alta)*

La salida del algoritmo genético para un piloto: la distribución de paradas, el plan modal como
barra de stints, y el intervalo de la primera parada.

La barra de stints es el elemento visual central: un rectángulo por stint, ancho proporcional a
las vueltas, coloreado por compuesto, con la vuelta de parada marcada.

### P3 — Pronóstico y resultado *(prioridad alta — es el diferencial del trabajo)*

El TP publica un pronóstico **fechado y congelado antes de cada carrera** y lo puntúa después.
Necesita dos estados:

- **Antes:** el pronóstico con su fecha de emisión visible y un sello de «congelado».
- **Después:** el mismo pronóstico con lo que realmente pasó superpuesto, y si cayó dentro del
  intervalo.

La honestidad acá es el punto. **Un pronóstico fallado se muestra igual de grande que uno
acertado.**

### P4 — Calibración *(prioridad media)*

La métrica principal del sistema: de las veces que dijimos 70%, ¿pasó el 70%? Un diagrama de
calibración —probabilidad dicha contra frecuencia observada, con la diagonal de referencia— y el
conteo de casos por tramo.

### P5 — Comparación GA vs Agente *(prioridad baja, para la entrega final)*

Las dos técnicas resolviendo la misma carrera: el plan del algoritmo genético contra las
decisiones del agente, y cuál terminó mejor.

## 5. Lenguaje visual

**Colores de compuesto (convención del deporte, no negociable):**

| Compuesto | Color |
|---|---|
| SOFT | rojo |
| MEDIUM | amarillo |
| HARD | blanco / gris muy claro |
| INTERMEDIATE | verde |
| WET | azul |

Ojo con el HARD: sobre fondo claro necesita borde. No usar sólo color para distinguirlos —
agregar la inicial (S/M/H/I/W), porque el rojo y el verde juntos son un problema de accesibilidad.

**Estados de pista:** verde, amarillo, VSC (amarillo con trama), SC (amarillo pleno), rojo. El
estado de pista cambia el significado de todo lo demás en pantalla, así que tiene que ser lo
primero que se ve.

**Tono:** panel de ingeniería, no videojuego. Denso en información, legible de un vistazo,
tipografía de números tabular para que las columnas alineen. La referencia es una pantalla de
muro de boxes.

**Idioma:** español. Los códigos de piloto y compuesto van en inglés porque así se usan.

## 6. Restricciones técnicas

- **React 19 + Vite + TypeScript**, ya scaffoldeado en `apps/web`. Hoy sólo tiene React y
  `react-dom`: la elección de librería de UI y de gráficos está abierta.
- Los datos llegan de una API FastAPI (`apps/api`), hoy sin endpoints de dominio.
- **Modo claro y oscuro.** El uso real es una pantalla de análisis; el oscuro es el esperado.
- Responsive hasta tablet. No hace falta móvil: nadie analiza estrategia en un teléfono.
- Sin dependencias de red externas para fuentes o assets.

## 7. Lo que NO hay que hacer

1. **No inventar datos.** Todos los ejemplos de este documento son mediciones reales. Si hace
   falta un caso más, pedirlo — hay 104 carreras cargadas.
2. **No mostrar exactitud como métrica.** «No parar nunca» acierta el 96,6% de las vueltas y es
   **descalificación** por reglamento. Las métricas son intervalo, calibración y posiciones.
3. **No esconder los estados feos.** «Sin proyectar», «a cara o cruz» y los pronósticos fallados
   son parte del producto.
4. **No diseñar una app de apuestas.** Esto asiste a un ingeniero, no pronostica ganadores.
5. **No usar segundos como medida del costo de parar.** Se mide en **posiciones**: bajo Safety
   Car una parada cuesta 0 posiciones contra 2 en verde, aunque en segundos parezca más cara.

## 8. Números reales disponibles para maquetar

| Dato | Valor medido |
|---|---|
| Pérdida por parada, verde | 22,2 s (p25 19,0 · p75 26,3) |
| Costo en posiciones: verde / VSC / SC | +2,0 / 0,0 / 0,0 |
| Vueltas neutralizadas | 9,6% |
| Paradas tomadas bajo neutralización | 30,8% (3,20× lo esperable) |
| Probabilidad global de Safety Car | 0,571 |
| Degradación 2026: DURO / MEDIO / BLANDO | 0,0436 / 0,0239 / 0,0142 s por vuelta |
| Distribución de paradas 2026 | 1: 35,4% · 2: 37,4% · 3: 18,3% · 4+: 5,1% |
| Parrilla 2026 | 22 pilotos, 11 equipos (entran Audi y Cadillac) |

**Caso extremo útil para probar la UI —** 2026 Zandvoort: 72 vueltas, bandera roja en la vuelta 2,
VSC en 52–57 y 67–70, estrategia modal de **3 paradas**, y 21 de 22 pilotos cambiando goma en la
vuelta 2. Si la interfaz sobrevive a esta carrera, sobrevive a cualquiera.

## 9. Decisión pendiente antes de arrancar

La cátedra trabaja en **Google Colab**: el entregable de código son cuadernos, no una aplicación
web. Esta UI **no es lo que se entrega para aprobar** — es para la demostración de la entrega
final y para uso propio.

Conviene decidir el alcance antes de invertir: si es sólo para la presentación, con P1 y P3
alcanza.

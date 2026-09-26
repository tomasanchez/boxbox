# Predicción pre-registrada: Bakú 2026

**Escrita antes de mirar la carrera.** Clasificación cargada, resultados no.
Fecha 15 de 2026, 51 vueltas. Pole de RUS en 102,526 s.

## Lo que se sabe de Bakú antes de empezar

**No está en la tabla de desgaste medido.** Esa tabla se arma sólo con 2026 y
con celdas de seis tandas o más, y Bakú todavía no corrió este año. Así que el
simulador lo corre con el **promedio de la temporada**, igual que hizo con Madrid.

Sí hay cuatro carreras de Bakú en 2022-2025, y de ahí sale casi todo lo que
sigue. Con una advertencia que este trabajo ya midió: **el desgaste no se
transfiere entre eras** (r = 0,143 sobre 27 pares). El duro en Bakú histórico
degrada 0,0068 s/vuelta y el promedio de 2026 da 0,0554 — ocho veces más. Ese
número no se puede prestar.

**Pero la estrategia sí se transfiere, y eso es nuevo.** Comparando las dos eras
sobre todos los circuitos:

| | blando | medio | duro | paradas (media) |
|---|---|---|---|---|
| 2026 | 19,8% | 71,2% | 9,1% | 2,00 |
| previo | 22,5% | 63,4% | 14,1% | 1,95 |

Casi idénticas. Que el desgaste no viaje no implica que nada viaje, y la
predicción de abajo se apoya en eso.

## El historial de Bakú, 2022-2025

Sobre 71 autos clasificados en cuatro carreras:

| | |
|---|---|
| larga en medio | **71,2%** |
| larga en duro | 28,7% |
| larga en blando | **0%** — ni uno |
| una parada | **79%** |
| secuencia más común | **medio → duro**, 46 de 71 |
| segunda | duro → medio, 17 |
| neutralización | **4 de 4 años**: VSC 2022, SC 2023, VSC 2024, SC 2025 |

Desgaste histórico: duro 0,0068 s/vuelta, medio 0,0271. Es un circuito callejero
de degradación muy baja, y por eso una parada alcanza.

## La predicción

**Se apuesta al historial, no al modelo.** Los dos van escritos porque el punto
del ejercicio es ver cuál acierta.

### Lo que digo yo

1. **Compuesto de salida.** Medio domina: **entre 12 y 17 de los 22**. Duro
   entre 4 y 8. Blando **3 o menos** — en Bakú nunca largó nadie en blando, y
   aunque 2026 usa blando un 20% del tiempo en general, este circuito no.
2. **Paradas.** Una parada es lo modal, **60% o más** de los clasificados.
3. **Secuencia.** **Medio → duro** es la más común de todas.
4. **Neutralización.** Sale al menos una, safety car o VSC.

### Lo que dice el modelo

Corrido con el promedio de la temporada, dejándolo elegir el compuesto:

| | |
|---|---|
| duro | 9 autos (41%) |
| blando | 7 (32%) |
| medio | 6 (27%) |
| paradas | **una, los 22** |

Coincide en el número de paradas y en que el segundo juego es duro. **Difiere
fuerte en con qué se larga**, y eso es esperable: `COMPOUND_OFFSET_S` vale cero
—el escalón de ritmo entre compuestos es una falla de identificación declarada—
así que el modelo no tiene ningún motivo para preferir el medio sobre el blando.
Ya se midió antes: elige medio 1 de 22 veces cuando la realidad da 74%.

## Cómo se falsea

Sin lugar para acomodar la lectura después:

- **Acierto en compuesto de salida** si el medio queda entre 12 y 17, y el blando
  en 3 o menos. Si el blando pasa de 3, me equivoqué.
- **Acierto en paradas** si una parada es lo modal con 60% o más.
- **Acierto en secuencia** si medio → duro es la más frecuente.
- **El modelo gana la comparación de compuestos** si su reparto 41/32/27 queda
  más cerca del real que mi 14/5/3. Si el blando real es alto, el modelo tenía
  razón y el historial no.

Lo que **no** se evalúa: quién gana la carrera. Esto es sobre estrategia.

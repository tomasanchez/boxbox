# Cuadernos

El registro reproducible de los datos, la limpieza y las mediciones del TP.

| Cuaderno | Qué contiene |
|---|---|
| `01-datos-y-limpieza` | De dónde salen los datos, las tres trampas del formato de FastF1, y cada decisión de limpieza con su antes y después medido |
| `02-mediciones` | Todo lo que el simulador sortea: pérdida de boxes, safety car, ruido de ritmo, distribución del desgaste, planes de parada, dificultad para adelantar |
| `03-busqueda-genetica` | El algoritmo genético, qué es «ganar», los dos errores que la búsqueda destapó en los datos, y la comparación contra una regla de servilleta |

## Cómo correrlos

```bash
cd apps/ml
uv sync --extra notebooks
uv run jupyter lab notebooks/
```

Los tres leen `data/laps_overtaking.parquet`, que es la ingesta cacheada de 103
carreras. Si no existe:

```bash
uv run python scripts/overtake_difficulty.py --offline    # lo escribe de paso
```

Eso tarda unos ocho minutos porque parsea el caché de FastF1 sesión por sesión.
Con el parquet en su lugar, los cuadernos 1 y 2 corren en segundos y el 3 en un
par de minutos.

## Por qué hay un `.py` y un `.ipynb` de cada uno

El `.py` es la **fuente**, en formato *percent* de jupytext: se lee y se
versiona como código, y un diff de git muestra qué cambió de verdad. El `.ipynb`
es el **producto**, con las salidas y los gráficos ya calculados, que es lo que
se entrega y lo que se puede leer sin ejecutar nada.

Para regenerar un `.ipynb` después de editar su `.py`:

```bash
uv run jupytext --to notebook --output notebooks/NOMBRE.ipynb notebooks/NOMBRE.py
uv run jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=3000 notebooks/NOMBRE.ipynb
```

Editar el `.ipynb` directamente también funciona, pero después conviene
sincronizar el `.py` con `uv run jupytext --to py:percent NOMBRE.ipynb` para que
el diff siga sirviendo.

## Relación con `docs/research/`

Los documentos de `docs/research/*.md` resumen las conclusiones en prosa y son
más cómodos para leer de corrido. **Los cuadernos son la fuente**: los números
del markdown se transcribieron de la salida de los scripts, así que ante una
discrepancia manda el cuaderno, que muestra el cálculo.

## Lo que estos cuadernos dicen que no funciona

Vale la pena adelantarlo, porque es fácil leer un cuaderno buscando sólo lo que
salió bien:

- ~~el coeficiente de combustible corrige de menos~~ **corregido**: se ajustó en
  `0,056 s/vuelta` sobre 1.627 carreras-piloto, contra los `0,035` asumidos, que
  sacaban el 63% del efecto. Eso desbloqueó el diferencial de ritmo entre
  compuestos —que resultó no existir de forma medible— y bajó del 42% al 37% la
  fracción de la parrilla sin ventana proyectable (cuaderno 1, §1.4);
- el ritmo de caída que trae cada auto en la foto **casi no predice** lo que la
  tanda va a hacer: correlación 0,183 (cuaderno 3, §3.4);
- el desgaste medido **se aplana y baja** después de la vuelta 25, que es sesgo
  de supervivencia y no comportamiento del neumático (cuaderno 2, §2.5);
- el ranking de dificultad para adelantar tiene una fiabilidad de **0,35**: dos
  tercios de la diferencia entre circuitos es ruido (cuaderno 2, §2.8);
- el algoritmo genético **casi no le gana a una regla de servilleta** (cuaderno
  3, §3.7). Ése es el resultado más importante del conjunto. Ajustar el
  coeficiente de avance de carrera triplicó su ventaja en la vuelta 30 —de +0,065
  a +0,179 puntos— pero sigue siendo menos de dos décimas, así que ese
  coeficiente era parte de la planitud y no toda. El principal sospechoso que
  queda es que el modelo no tiene tráfico.

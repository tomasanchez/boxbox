# Herramientas y convenciones de la cátedra

Repositorios clonados en `E:\dev\`: `demoML`, `demoCESwarm`, `demoRL`
(organización [`PGP-MachineLearning`](https://github.com/PGP-MachineLearning)).

## Conclusión operativa

**La cátedra trabaja en Google Colab, no en repositorios locales.** El README de `demoML` es
explícito: subir los `.ipynb` a Google Drive bajo `demosColab/<demo>/`, abrirlos con Google
Colaboratory y ejecutar todas las celdas.

Eso implica una decisión práctica para el TP: **el entregable de código debe ser un cuaderno
Colab**, no el paquete `boxbox_ml`. El paquete sigue siendo útil como motor —ingesta, features,
simulador— pero debe poder importarse o pegarse en un cuaderno que siga las convenciones del
curso.

## Bibliotecas confirmadas por unidad

| Unidad | Biblioteca | Verificado en |
|---|---|---|
| **3 — Sistemas Evolutivos** | **`deap`** (`pip install deap`) | `CE-*.ipynb`, `PG-*.ipynb` |
| **5 — Agentes** | **`gymnasium`** + `tensorflow` | `Q-Blackjack.ipynb`, `Q-Atari.ipynb` |
| **4 — Razonamiento Aproximado** | **`pgmpy`** (`pip install pgmpy`) + `pygraphviz` | `datos-RedBayesiana.ipynb` |
| 2 — RNA / Deep Learning | `keras` / `tensorflow`, `sklearn` | `datos-RNA-MLP.ipynb`, `datos-RNN.ipynb` |
| Transversal | `numpy`, `pandas`, `matplotlib`, `networkx`, `ipywidgets`, `joblib`, `tqdm` | todos |

> El programa menciona **GeNIe** para redes bayesianas, pero la demo de la cátedra usa **pgmpy**
> desde Python. Para integrarlo con nuestro pipeline, pgmpy es el camino.

## Los tres cuadernos que son análogos directos de nuestro problema

### 1. `demoCESwarm/CE-ViajeroProblem.ipynb` — el molde del Algoritmo Genético

El problema del viajante es el análogo estructural más cercano: optimizar una **secuencia** bajo
restricciones con una función de aptitud costosa. Patrón DEAP que usa:

```python
creator.create("Fitness", base.Fitness, weights=(-1.0,))   # minimizar
creator.create("Individual", list, fitness=creator.Fitness)

toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.puntos)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", funcAptitud)                  # devuelve una tupla: (res,)
toolbox.register("select",   tools.selTournament, tournsize=2)
toolbox.register("mate",     tools.cxOnePoint)             # o cxOrdered para permutaciones
toolbox.register("mutate",   tools.mutShuffleIndexes, indpb=1.0/cant_genes)
```

Ofrece además varias alternativas de selección comentadas —`selBest`, `selRoulette`,
`selRandom`, y una `selControlNroEsperado` propia— lo que sugiere que **se espera comparar
operadores**, no elegir uno y listo. Nuestra Entrega 2 debería hacer exactamente eso.

**Aplicación a BoxBox:** cromosoma = plan de carrera (longitudes de stint + compuestos), aptitud
= posición final simulada, `weights=(-1.0,)` porque se minimiza la posición.

### 2. `demoRL/Q-Blackjack.ipynb` — el molde del agente

Estructura del cuaderno:

1. `## Clases sobre el Problema a resolver`
2. `## Q-Learning`
3. `## Deep-Q-Network (DQN)`
4. `## Comparar Q-Learning y DQN`

**El Blackjack es sorprendentemente análogo a nuestro problema:** decisión secuencial de
*parar o seguir* bajo incertidumbre, donde seguir mejora la posición hasta cierto punto y luego
la arruina. Cambiar «pedir carta / plantarse» por «seguir en pista / boxear» es casi un cambio de
nombre.

Usa **`gymnasium`**, que es la API estándar de entornos de RL. **Decisión de diseño derivada: el
simulador Monte Carlo de BoxBox debe implementar la interfaz `gymnasium.Env`** (`reset`, `step`,
`observation_space`, `action_space`). Así sirve simultáneamente como función de aptitud del AG y
como entorno del agente, sin escribirlo dos veces.

La estructura «Q-Learning, después DQN, después comparar» es además un buen molde para la
Entrega 3.

### 3. `demoML/datos-RedBayesiana.ipynb` — línea futura

Estructura: `# Datos:` → `# Modelo:` → `### Evaluación del Modelo:` → `### Exportar el Modelo:`.
Usa `pgmpy`. Aplicable a nuestras tasas de neutralización si sobra tiempo.

## Convención de estructura de cuaderno

Los cuadernos de computación evolutiva siguen siempre el mismo esqueleto:

```
# Demo de implementación de <técnica> para resolver <problema>
# Definición del Problema a Resolver:
# Preparación del Algoritmo:
# Ejecución del Algoritmo:
```

Y los de datos:

```
# Datos:
# Modelo:
### Evaluación del Modelo:
### Exportar el Modelo:
```

Conviene adoptar estos títulos literalmente. Es señal barata y visible de alineación con el curso.

Usan `#@title` y `#@markdown` (formularios de Colab) para exponer parámetros ajustables, e
`ipywidgets` para controles interactivos.

## Conjuntos de datos de ejemplo

`demoML/datos/` trae IRIS, ANIMALES, CalidadVinos, cinematica, SUMAS, SerieFibonacci,
TestInteligencia2 y **ORO.csv** (serie temporal de precios). Ninguno es necesario para nosotros
—tenemos datos propios— pero `ORO.csv` confirma que la cátedra acepta problemas de series
temporales.

## Consecuencias para la propuesta

1. **Entregar cuadernos Colab**, no sólo el repositorio. El paquete `boxbox_ml` pasa a ser la
   biblioteca que el cuaderno importa.
2. **El simulador implementa `gymnasium.Env`.** Decisión concreta que unifica la capa 1 con la
   capa 3.
3. **Usar DEAP con el patrón de `CE-ViajeroProblem`**, y **comparar operadores de selección y
   cruza** en lugar de fijar uno.
4. **Adoptar los títulos de sección** de los cuadernos de la cátedra.
5. Añadir `deap`, `gymnasium` y `pgmpy` a las dependencias de `apps/ml`.

## Pendiente

- [ ] Revisar `demoCESwarm/NeuroEvolution/` y `demoRL/Modelos/`, que no se inspeccionaron.
- [ ] Conseguir el documento «IAA - Normas Aprobación» — sigue siendo el bloqueante principal.

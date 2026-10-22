"""Las figuras de validación y error del informe.

**Por qué no son las curvas que uno espera.** El entregable de este trabajo es un
algoritmo genético sobre un simulador Monte Carlo, no un clasificador: no hay
épocas, no hay clases y no hay una función de pérdida que baje. Dibujar «pérdida
de entrenamiento contra validación por época» sería inventar un eje que no
existe. Lo que sí existe, y es el mismo problema con otro nombre, es esto:

* **la generación hace de época**, y la aptitud del mejor plan hace de pérdida;
* **la partición entrenamiento/validación existe y ya estaba en el código**: la
  búsqueda optimiza contra un juego de carreras sorteadas y su resultado se
  vuelve a puntuar sobre otro juego que nunca vio. La diferencia entre las dos
  es :attr:`Search.optimism`, que es exactamente la brecha de sobreajuste;
* **y hay un clasificador de verdad**, el de parar o seguir, con su matriz de
  confusión y su precisión-exhaustividad, que `scripts/holdout_eval.py` ya medía
  sobre el 25% de carreras retenidas que pide la cátedra.

Tres figuras, entonces:

1. ``fig-ag-validacion.png`` — la curva de la búsqueda, en muestra contra
   retenida, y cómo se concentra la población. El análogo de pérdida/exactitud.
2. ``fig-error-degradacion.png`` — el error del regresor de degradación contra
   el baseline ingenuo, con la dispersión entre pliegues.
3. ``fig-matriz-confusion.png`` — el clasificador de parada: matriz de confusión
   y curva precisión-exhaustividad.

Los números de las figuras 2 y 3 salen de ``apps/ml/data/holdout_eval.json``, que
escribe ``scripts/holdout_eval.py``. Se leen de ahí en vez de copiarse para que la
figura y el número impreso no se puedan desincronizar — que es precisamente el
error que este proyecto ya cometió con el export de la interfaz.

Correr con ``uv run python scripts/validation_plots.py`` (después de
``holdout_eval.py``, que es el que deja el JSON).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, RaceModel, draw_neutralisations, race_time

warnings.filterwarnings("ignore")

RAIZ = Path(__file__).resolve().parents[3]
SALIDA = RAIZ / "docs" / "tp" / "figuras"
DATOS = Path(__file__).resolve().parents[1] / "data" / "holdout_eval.json"
PARADA = Path(__file__).resolve().parents[1] / "data" / "early_stopping.json"

#: Paleta sobria y legible impresa en blanco y negro: los dos trazos se
#: distinguen por tono y por estilo de línea, no sólo por color.
AZUL, NARANJA, GRIS, ROJO = "#2b6cb0", "#dd6b20", "#4a5568", "#c53030"

SEMILLA = 11
SORTEOS = 1200
GENERACIONES = 25
POBLACION = 40


def estilo() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 160,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


# ------------------------------------------- 1. la curva del algoritmo genético


def curva_del_ag() -> None:
    """Aptitud por generación sobre los sorteos de la búsqueda y sobre otros.

    La comparación es justa por construcción: **el mismo plan**, las mismas
    distribuciones, lo único que cambia es qué carreras se sortearon. El juego
    retenido se arma con otra semilla y la búsqueda nunca lo ve.
    """
    model = RaceModel()
    car = Car("FOC", "MEDIUM", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)

    hallado = strategy.optimise(
        car,
        [],
        [],
        model,
        objective=Objective.TIME,
        population=POBLACION,
        generations=GENERACIONES,
        draws=SORTEOS,
        seed=SEMILLA,
        instrument=True,
    )
    if not hallado.history:
        raise SystemExit("la búsqueda no devolvió historia: ¿se pidió instrument=True?")

    vacio = np.empty((0, model.total_laps - car.from_lap + 2, SORTEOS))

    def retenido(plan) -> float:
        """El tiempo del plan sobre carreras que la búsqueda nunca vio.

        Se replica *exactamente* cómo :func:`optimise` arma su juego retenido —
        misma semilla derivada, mismo generador alimentando el sorteo y después
        la traza— y se rearma de cero en cada generación. Así el último punto de
        esta curva es, por construcción, el ``score`` que el proyecto informa, y
        la figura no puede contar una historia distinta de la tabla.
        """
        gen = np.random.default_rng(SEMILLA + 9973)
        flags = draw_neutralisations(model, gen, SORTEOS)
        return float(race_time(plan, car, model, gen, SORTEOS, flags, vacio).mean())

    # `best_plan` es None sólo si la población llegó vacía, que no pasa; si
    # pasara, saltearlo en silencio desalinearía las curvas del eje x.
    registro = [g for g in hallado.history if g.best_plan is not None]
    generaciones = [g.index for g in registro]
    # `best` es la aptitud en muestra y para TIME vale menos el tiempo medio.
    entrenamiento = [-g.best for g in registro]
    validacion = [retenido(g.best_plan) for g in registro]
    # Cuánto de la población se fue concentrando en una sola cantidad de paradas.
    concentracion = [max(g.stop_distribution.values()) for g in registro]

    figura, (izq, der) = plt.subplots(1, 2, figsize=(9.2, 3.5))

    izq.plot(generaciones, entrenamiento, color=AZUL, lw=1.6, label="Entrenamiento")
    izq.plot(generaciones, validacion, color=NARANJA, lw=1.6, ls="--", label="Validación")
    izq.set_xlabel("Generación")
    izq.set_ylabel("Tiempo de carrera (s)")
    izq.set_title("Error del plan: menor es mejor")
    izq.legend(frameon=False)

    brecha = np.array(validacion) - np.array(entrenamiento)
    der.plot(generaciones, concentracion, color=AZUL, lw=1.6, label="Concentración")
    der.set_xlabel("Generación")
    der.set_ylabel("Mayor fracción de la población")
    der.set_ylim(0, 1.02)
    der.set_title("Convergencia: la población elige una cantidad de paradas")
    der.legend(frameon=False, loc="lower right")

    figura.tight_layout()
    destino = SALIDA / "fig-ag-validacion.png"
    figura.savefig(destino)
    plt.close(figura)

    print(f"  {destino.name}")
    print(f"    plan final: {hallado.best.describe(car, model.total_laps)}")
    print(f"    tiempo en muestra  {entrenamiento[-1]:.2f} s")
    print(f"    tiempo retenido    {validacion[-1]:.2f} s  (score informado: {-hallado.score:.2f})")
    print(
        f"    brecha final       {brecha[-1]:+.2f} s"
        f"   (optimismo informado: {hallado.optimism:+.2f})"
    )
    print(f"    concentración      {concentracion[0]:.2f} -> {concentracion[-1]:.2f}")


# ----------------------------------------- 2. el error del modelo de degradación


def error_del_regresor(datos: dict) -> None:
    """Lo medido contra el baseline ingenuo, con la dispersión entre pliegues."""
    reg = datos["regressor"]
    pliegues = reg["cv_mae"]

    figura, (izq, der) = plt.subplots(1, 2, figsize=(9.2, 3.5))

    etiquetas = ["Validación\n(4 pliegues)", "Prueba", "Prueba\n(mediana)"]
    valores = [reg["validation_mae"], reg["test_mae"], reg["test_mae_naive"]]
    colores = [AZUL, NARANJA, GRIS]
    barras = izq.bar(etiquetas, valores, color=colores, width=0.6)
    # Los pliegues, encima de su barra: una media sin dispersión esconde si los
    # cuatro dijeron lo mismo o si se promediaron dos respuestas distintas.
    # Desplazados un poco entre sí: cuatro puntos en la misma vertical se tapan y
    # dos pliegues iguales se leen como uno.
    reparto = np.linspace(-0.18, 0.18, len(pliegues))
    izq.scatter(reparto, pliegues, color="white", edgecolor=AZUL, zorder=3, s=20, linewidths=1.1)
    for barra, valor in zip(barras, valores, strict=True):
        izq.text(
            barra.get_x() + barra.get_width() / 2,
            valor + 0.02,
            f"{valor:.3f}",
            ha="center",
            fontsize=8,
        )
    izq.set_ylabel("MAE (s)")
    izq.set_title("Error del regresor de degradación")
    izq.set_ylim(0, max([*valores, *pliegues]) * 1.18)

    # El dato incómodo primero: en esta partición el modelo PIERDE contra la
    # mediana. El informe ya lo decía para 2026 solo; la figura no lo disimula.
    peor = reg["test_mae"] - reg["test_mae_naive"]
    der.axis("off")
    der.text(
        0.0,
        0.92,
        "Lo que dice esta partición",
        fontsize=10,
        fontweight="bold",
        va="top",
    )
    lineas = [
        f"Carreras de entrenamiento: {len(datos['split']['train_rounds'])}",
        f"Carreras retenidas:        {len(datos['split']['test_rounds'])}  "
        f"({len(datos['split']['test_rounds']) / 12:.0%})",
        f"Vueltas prueba:            {datos['split']['test_laps']:,}",
        "",
        f"R² en prueba:              {reg['test_r2']:.3f}",
        f"Contra la mediana:         {peor:+.3f} s  " + ("PIERDE" if peor > 0 else "gana"),
        "",
        "Es la partición de 2026 sola. Con todas",
        "las temporadas el modelo gana (0,698 contra",
        "0,726); el informe reporta las dos, §4.",
    ]
    der.text(0.0, 0.78, "\n".join(lineas), fontsize=8.5, va="top", family="monospace")

    figura.tight_layout()
    destino = SALIDA / "fig-error-degradacion.png"
    figura.savefig(destino)
    plt.close(figura)
    print(f"  {destino.name}")


# ------------------------------------- 3. el clasificador de parar o seguir


def matriz_de_confusion(datos: dict) -> None:
    """La matriz y la curva precisión-exhaustividad del clasificador de parada."""
    clf = datos["classifier"]
    c = clf["confusion"]
    matriz = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]], dtype=float)

    figura, (izq, der) = plt.subplots(1, 2, figsize=(9.2, 3.5))

    # Normalizada por fila: con 3.383 negativos contra 118 positivos, los valores
    # crudos pintan una matriz de un solo color y no se lee nada.
    proporcion = matriz / matriz.sum(axis=1, keepdims=True)
    izq.imshow(proporcion, cmap="Blues", vmin=0, vmax=1)
    izq.set_xticks([0, 1], ["predice seguir", "predice parar"])
    izq.set_yticks([0, 1], ["real: sigue", "real: para"])
    izq.grid(False)
    for i in range(2):
        for j in range(2):
            izq.text(
                j,
                i,
                f"{int(matriz[i, j]):,}\n{proporcion[i, j]:.0%}",
                ha="center",
                va="center",
                color="white" if proporcion[i, j] > 0.5 else "#1a202c",
                fontsize=9,
            )
    izq.set_title(f"Matriz de confusión (umbral {clf['threshold']:.3f})")

    der.plot(clf["curve"]["recall"], clf["curve"]["precision"], color=AZUL, lw=1.6)
    der.axhline(clf["chance"], color=ROJO, ls=":", lw=1.2, label=f"azar ({clf['chance']:.1%})")
    der.scatter(
        [clf["recall"]],
        [clf["precision"]],
        color=NARANJA,
        zorder=3,
        s=30,
        label=f"mejor F1 ({clf['f1']:.2f})",
    )
    der.set_xlabel("Exhaustividad")
    der.set_ylabel("Precisión")
    der.set_title(f"Precisión-exhaustividad  ·  PR-AUC {clf['pr_auc']:.3f}")
    der.set_ylim(0, max(0.5, clf["precision"] * 1.3))
    der.legend(frameon=False)

    figura.tight_layout()
    destino = SALIDA / "fig-matriz-confusion.png"
    figura.savefig(destino)
    plt.close(figura)
    print(f"  {destino.name}")
    print(
        f"    PR-AUC {clf['pr_auc']:.4f} contra azar {clf['chance']:.4f} "
        f"= {clf['pr_auc'] / clf['chance']:.2f}x"
    )


# ------------------------------------------------ 4. la parada temprana que falta


def parada_temprana(datos: dict) -> None:
    """Qué cuesta quedarse con la última generación en vez de la mejor.

    Es la figura que justifica haber dibujado las otras: la curva de validación
    sirve para ver que el entrenamiento siguió cuando ya no convenía, y acá se ve
    cuántas veces pasó y cuánto costó.
    """
    corridas = datos["corridas"]
    resumen = datos["resumen"]
    ultima = np.array([c["ultima_s"] for c in corridas])
    elegida = np.array([c["elegida_s"] for c in corridas])
    perdida = ultima - elegida

    figura, (izq, der) = plt.subplots(1, 2, figsize=(9.2, 3.5))

    borde = [min(elegida.min(), ultima.min()) - 0.1, max(elegida.max(), ultima.max()) + 0.1]
    izq.plot(borde, borde, color=GRIS, lw=1.0, ls=":", label="iguales")
    sin, con = perdida <= 0.01, perdida > 0.01
    izq.scatter(elegida[sin], ultima[sin], color=AZUL, s=26, label="empatan")
    izq.scatter(elegida[con], ultima[con], color=ROJO, s=26, label="parar antes gana")
    izq.set_xlabel("Generación elegida en validación (s)")
    izq.set_ylabel("Última generación (s)")
    izq.set_title("Cada punto es una corrida, puntuada en PRUEBA")
    izq.legend(frameon=False, fontsize=8)

    orden = np.argsort(perdida)[::-1]
    der.bar(
        range(len(perdida)),
        perdida[orden],
        color=[ROJO if v > 0.01 else AZUL for v in perdida[orden]],
        width=0.75,
    )
    der.set_xlabel("Corridas, ordenadas")
    der.set_ylabel("Segundos que gana parar antes")
    der.set_title(
        f"parar antes gana en {resumen['pierden']} de {resumen['total']}  ·  "
        f"media {resumen['perdida_media_global']:.2f} s"
    )
    der.set_xticks([])

    figura.tight_layout()
    destino = SALIDA / "fig-parada-temprana.png"
    figura.savefig(destino)
    plt.close(figura)
    print(f"  {destino.name}")
    print(
        f"    {resumen['pierden']}/{resumen['total']} pierden, "
        f"media {resumen['perdida_media_global']:.3f} s, "
        f"máxima {resumen['perdida_maxima']:.3f} s"
    )


def main() -> None:
    estilo()
    SALIDA.mkdir(parents=True, exist_ok=True)
    if not DATOS.exists():
        raise SystemExit(f"falta {DATOS}: correr antes scripts/holdout_eval.py")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))

    print("figuras escritas en", SALIDA)
    curva_del_ag()
    error_del_regresor(datos)
    matriz_de_confusion(datos)
    if PARADA.exists():
        parada_temprana(json.loads(PARADA.read_text(encoding="utf-8")))
    else:
        print(f"  (sin {PARADA.name}: correr scripts/early_stopping.py)")


if __name__ == "__main__":
    main()

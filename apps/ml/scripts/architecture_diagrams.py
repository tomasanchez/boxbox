"""Los tres diagramas de arquitectura del informe.

El equivalente a la «topología del modelo» que lleva un trabajo de redes
neuronales. Acá la técnica es un algoritmo genético sobre un simulador, así que
la topología no es una pila de capas: son tres cosas distintas y conviene
dibujarlas por separado en vez de amontonarlas en un diagrama ilegible.

1. ``fig-pipeline.png``  — de dónde salen los datos y en qué se convierten.
2. ``fig-cromosoma.png`` — cómo se codifica un plan y qué le hacen los
   operadores. Es el análogo más directo de la topología: define el espacio
   que la búsqueda recorre.
3. ``fig-aptitud.png``   — cómo se puntúa un plan, que es donde vive el
   simulador y donde se decide si la comparación entre dos planes es justa.

Las cifras que aparecen son las reales del sistema y se importan de
:mod:`boxbox_ml.strategy` donde se puede, para que el diagrama no envejezca
contra el código.

Correr con ``uv run python scripts/architecture_diagrams.py``.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from boxbox_ml import strategy

SALIDA = Path(__file__).resolve().parents[3] / "docs" / "tp" / "figuras"

#: El tope de paradas de un plan, que es `max_stops` en la firma de `optimise`.
TOPE_PARADAS = inspect.signature(strategy.optimise).parameters["max_stops"].default

AZUL, NARANJA, GRIS, VERDE = "#2b6cb0", "#dd6b20", "#4a5568", "#2f855a"
BORDE, TEXTO = "#cbd5e0", "#1a202c"


def estilo() -> None:
    plt.rcParams.update(
        {"figure.dpi": 160, "savefig.dpi": 160, "font.size": 8.5, "figure.facecolor": "white"}
    )


def caja(ax, x, y, ancho, alto, titulo, detalle="", color=AZUL, relleno="#f7fafc") -> None:
    """Una caja con título y, debajo, una línea de detalle más chica."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            ancho,
            alto,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            facecolor=relleno,
            edgecolor=color,
            linewidth=1.4,
        )
    )
    centro = y + alto / 2
    if detalle:
        ax.text(
            x + ancho / 2,
            centro + alto * 0.17,
            titulo,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=TEXTO,
        )
        ax.text(
            x + ancho / 2,
            centro - alto * 0.22,
            detalle,
            ha="center",
            va="center",
            fontsize=7.4,
            color=GRIS,
        )
    else:
        ax.text(
            x + ancho / 2,
            centro,
            titulo,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=TEXTO,
        )


def flecha(ax, desde, hasta, color=GRIS, etiqueta="", estilo_linea="-") -> None:
    ax.add_patch(
        FancyArrowPatch(
            desde,
            hasta,
            arrowstyle="-|>",
            mutation_scale=11,
            color=color,
            linewidth=1.2,
            linestyle=estilo_linea,
            shrinkA=2,
            shrinkB=2,
        )
    )
    if etiqueta:
        ax.text(
            (desde[0] + hasta[0]) / 2 + 0.012,
            (desde[1] + hasta[1]) / 2,
            etiqueta,
            fontsize=7,
            color=color,
            ha="left",
            va="center",
        )


def lienzo(alto_pulgadas: float):
    figura, ax = plt.subplots(figsize=(8.6, alto_pulgadas))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return figura, ax


def guardar(figura, nombre: str) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / nombre
    figura.tight_layout(pad=0.3)
    figura.savefig(destino)
    plt.close(figura)
    print(f"  {nombre}")


# --------------------------------------------------------------- 1. el pipeline


def pipeline() -> None:
    figura, ax = lienzo(5.6)
    etapas = [
        ("FastF1", "5 temporadas · 2022-2026 · 11.772 vueltas representativas", AZUL),
        ("Features", "corrección de combustible · posición en la tanda · banderas", AZUL),
        ("Distribuciones medidas", "desgaste · pérdida de boxes · neutralizaciones", VERDE),
        ("Simulador Monte Carlo", "1.200 carreras sorteadas · 22 autos · vectorizado", VERDE),
        (
            "Algoritmo Genético",
            "dos motores: DEAP y propio · población 40 · 25 generaciones",
            NARANJA,
        ),
        ("Plan + distribución", "paradas, compuestos y la confianza de la búsqueda", NARANJA),
        ("Export JSON → interfaz", "React 19 + Vite · anima un sorteo (ADR-002, ADR-010)", GRIS),
    ]
    alto, hueco = 0.095, 0.045
    y = 1.0 - alto
    for titulo, detalle, color in etapas:
        caja(ax, 0.06, y, 0.88, alto, titulo, detalle, color)
        if y > 0.1:
            flecha(ax, (0.5, y), (0.5, y - hueco))
        y -= alto + hueco
    ax.text(
        0.5,
        0.012,
        "Lo verde es el entorno; lo naranja, la técnica de la Unidad 3.",
        ha="center",
        fontsize=7.5,
        color=GRIS,
        style="italic",
    )
    guardar(figura, "fig-pipeline.png")


# -------------------------------------------------------------- 2. el cromosoma


def cromosoma() -> None:
    figura, ax = lienzo(5.2)

    ax.text(
        0.5,
        0.965,
        "Un individuo es un plan de paradas de largo variable",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color=TEXTO,
    )

    genes = [("Stop(24, HARD)", "vuelta + compuesto"), ("Stop(48, HARD)", "vuelta + compuesto")]
    x = 0.17
    for etiqueta, detalle in genes:
        caja(ax, x, 0.80, 0.27, 0.085, etiqueta, detalle, AZUL)
        x += 0.32
    ax.text(
        0.5,
        0.762,
        f"se lee  M24-H24-H24   ·   de 0 a {TOPE_PARADAS} paradas",
        ha="center",
        fontsize=8,
        color=GRIS,
    )

    ops = [
        ("Selección", "torneo", AZUL),
        ("Cruza", "intercambia paradas", AZUL),
        ("Mutación", "mueve la vuelta · cambia el\ncompuesto · agrega o quita", NARANJA),
        (
            "Reparación",
            f"MIN_STINT {strategy.MIN_STINT} · MAX_STINT\n"
            f"{strategy.MAX_STINT['HARD']}/{strategy.MAX_STINT['MEDIUM']}/"
            f"{strategy.MAX_STINT['SOFT']} · B6.3.8",
            VERDE,
        ),
        ("Evaluación", "ver el lazo de aptitud", GRIS),
    ]
    ancho, hueco = 0.155, 0.032
    x = (1 - (len(ops) * ancho + (len(ops) - 1) * hueco)) / 2
    for titulo, detalle, color in ops:
        caja(ax, x, 0.44, ancho, 0.17, titulo, detalle, color)
        if x + ancho < 0.9:
            flecha(ax, (x + ancho, 0.525), (x + ancho + hueco, 0.525))
        x += ancho + hueco

    # Entra al PRINCIPIO de la cadena: apuntando al centro caía en «Mutación», que
    # se leía como si el individuo naciera mutado.
    ax.annotate(
        "",
        xy=(0.126, 0.615),
        xytext=(0.5, 0.795),
        arrowprops={
            "arrowstyle": "-|>",
            "color": GRIS,
            "linewidth": 1.2,
            "connectionstyle": "arc3,rad=0.20",
        },
    )
    # Y el lazo vuelve por DEBAJO de la fila, no cruzando las cajas.
    ax.annotate(
        "",
        xy=(0.126, 0.435),
        xytext=(0.874, 0.435),
        arrowprops={
            "arrowstyle": "-|>",
            "color": GRIS,
            "linewidth": 1.2,
            # Radio NEGATIVO: con el positivo el lazo arqueaba por arriba y
            # cruzaba las cinco cajas.
            "connectionstyle": "arc3,rad=-0.22",
        },
    )
    ax.text(
        0.5,
        0.345,
        "la población vuelve al torneo · 25 generaciones",
        ha="center",
        fontsize=7.6,
        color=GRIS,
    )

    ax.text(
        0.5,
        0.155,
        "La reparación es lo que hace que el espacio sea recorrible: cualquier\n"
        "mutación cae en un plan legal, así que la búsqueda nunca gasta\n"
        "evaluaciones en planes que el reglamento no permite.",
        ha="center",
        fontsize=8,
        color=TEXTO,
    )
    ax.text(
        0.5,
        0.045,
        "Elitismo: el campeón pasa de generación intacta en el motor propio.\n"
        "En DEAP no, y por eso se agregó el salón de la fama al resultado.",
        ha="center",
        fontsize=7.4,
        color=GRIS,
        style="italic",
    )
    guardar(figura, "fig-cromosoma.png")


# ---------------------------------------------------------------- 3. la aptitud


def aptitud() -> None:
    figura, ax = lienzo(5.0)
    ax.text(
        0.5,
        0.96,
        "Cómo se puntúa un plan",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color=TEXTO,
    )

    caja(ax, 0.06, 0.80, 0.40, 0.10, "Plan candidato", "una secuencia de paradas", NARANJA)
    caja(
        ax,
        0.54,
        0.80,
        0.40,
        0.10,
        "1.200 carreras sorteadas",
        "banderas, desgaste y boxes de las\ndistribuciones medidas",
        VERDE,
    )
    caja(
        ax,
        0.06,
        0.60,
        0.88,
        0.10,
        "Traza de los 22 autos, vuelta por vuelta",
        "vectorizada sobre los sorteos · las MISMAS carreras para todos los candidatos",
        VERDE,
    )
    caja(ax, 0.06, 0.40, 0.42, 0.10, "Tiempo y puesto por sorteo", "", GRIS)
    caja(
        ax,
        0.52,
        0.40,
        0.42,
        0.10,
        "Objetivo y apetito de riesgo",
        "media, o la media del peor/mejor cuarto",
        AZUL,
    )
    caja(ax, 0.26, 0.20, 0.48, 0.09, "Aptitud", "un número por plan", NARANJA)

    flecha(ax, (0.26, 0.80), (0.33, 0.70))
    flecha(ax, (0.74, 0.80), (0.67, 0.70))
    flecha(ax, (0.27, 0.60), (0.27, 0.50))
    flecha(ax, (0.73, 0.50), (0.73, 0.50))
    flecha(ax, (0.48, 0.45), (0.52, 0.45))
    flecha(ax, (0.50, 0.40), (0.50, 0.29))

    ax.text(
        0.5,
        0.125,
        "**Números aleatorios comunes.** Todos los candidatos de una generación se\n"
        "puntúan sobre las mismas carreras. No baja el error de cada estimación, baja\n"
        "el de la DIFERENCIA entre dos planes, que es lo único que la selección usa.",
        ha="center",
        fontsize=8,
        color=TEXTO,
    )
    ax.text(
        0.5,
        0.02,
        "El plan ganador se vuelve a puntuar sobre un juego de carreras que la búsqueda\n"
        "nunca vio: la diferencia entre los dos puntajes es el optimismo informado.",
        ha="center",
        fontsize=7.4,
        color=GRIS,
        style="italic",
    )
    guardar(figura, "fig-aptitud.png")


def main() -> None:
    estilo()
    print("diagramas escritos en", SALIDA)
    pipeline()
    cromosoma()
    aptitud()


if __name__ == "__main__":
    main()
